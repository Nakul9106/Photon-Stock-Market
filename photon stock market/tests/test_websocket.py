"""Automated test suite for Photon WebSocket endpoints and broadcast management.

Tests cover:
- WebSocket connection establishment
- Initial stock snapshot receipt
- Subscription system ('subscribe', 'unsubscribe', 'set')
- Invalid subscription actions and malformed payload handling
- Multiple simultaneous client connections
- Broadcast behavior and selective subscription filtering
- Safe client disconnection handling
"""

import asyncio
import pytest
from fastapi.testclient import TestClient
from app.connection_manager import ConnectionManager
from app.main import app
from app.models import StockData, get_current_utc_iso


@pytest.fixture
def client():
    """Create a FastAPI test client instance with application lifespan active."""
    with TestClient(app) as test_client:
        yield test_client


def test_websocket_connection_and_initial_snapshot(client: TestClient):
    """Verify that a client connects to /ws and immediately receives an initial snapshot."""
    with client.websocket_connect("/ws") as websocket:
        message = websocket.receive_json()
        assert message["type"] == "initial_snapshot"
        assert message["is_simulated"] is True
        assert isinstance(message["data"], list)
        assert len(message["data"]) >= 6

        symbols = {stock["symbol"] for stock in message["data"]}
        assert "AAPL" in symbols
        assert "GOOGL" in symbols


def test_websocket_subscription_set_action(client: TestClient):
    """Verify subscribing to a specific subset of stocks."""
    with client.websocket_connect("/ws") as websocket:
        # Drain initial snapshot
        snapshot = websocket.receive_json()
        assert snapshot["type"] == "initial_snapshot"

        # Send subscription request for AAPL and MSFT
        websocket.send_json({"action": "set", "symbols": ["AAPL", "MSFT"]})

        ack = websocket.receive_json()
        assert ack["type"] == "subscription_status"
        assert ack["status"] == "success"
        assert sorted(ack["subscribed_symbols"]) == ["AAPL", "MSFT"]


def test_websocket_subscription_incremental(client: TestClient):
    """Verify subscribing and unsubscribing incrementally."""
    with client.websocket_connect("/ws") as websocket:
        _ = websocket.receive_json()

        # Set subscription to AAPL
        websocket.send_json({"action": "set", "symbols": ["AAPL"]})
        ack1 = websocket.receive_json()
        assert ack1["subscribed_symbols"] == ["AAPL"]

        # Incrementally add TSLA
        websocket.send_json({"action": "subscribe", "symbols": ["TSLA"]})
        ack2 = websocket.receive_json()
        assert sorted(ack2["subscribed_symbols"]) == ["AAPL", "TSLA"]

        # Unsubscribe from AAPL
        websocket.send_json({"action": "unsubscribe", "symbols": ["AAPL"]})
        ack3 = websocket.receive_json()
        assert ack3["subscribed_symbols"] == ["TSLA"]


def test_websocket_invalid_subscription_message(client: TestClient):
    """Verify server gracefully handles malformed messages without terminating session."""
    with client.websocket_connect("/ws") as websocket:
        _ = websocket.receive_json()

        # Send invalid action payload
        websocket.send_json({"action": "unsupported_action", "symbols": ["AAPL"]})
        err_msg = websocket.receive_json()
        assert err_msg["type"] == "error"
        assert "Invalid subscription request" in err_msg["error"]

        # Ensure connection remains healthy by sending a valid subscription next
        websocket.send_json({"action": "set", "symbols": ["NVDA"]})
        ack = websocket.receive_json()
        assert ack["type"] == "subscription_status"
        assert ack["subscribed_symbols"] == ["NVDA"]


def test_websocket_unknown_stock_symbols(client: TestClient):
    """Verify that unknown stock symbols generate a warning but do not crash."""
    with client.websocket_connect("/ws") as websocket:
        _ = websocket.receive_json()

        # Request unknown ticker along with valid ticker
        websocket.send_json({"action": "set", "symbols": ["AAPL", "UNKNOWN_TICKER"]})
        ack = websocket.receive_json()
        assert ack["type"] == "subscription_status"
        assert ack["status"] == "warning"
        assert "UNKNOWN_TICKER" in ack["message"]
        assert ack["subscribed_symbols"] == ["AAPL"]


def test_multiple_simultaneous_connections(client: TestClient):
    """Verify that multiple browser/client connections operate concurrently."""
    with client.websocket_connect("/ws") as ws1:
        snapshot1 = ws1.receive_json()
        assert snapshot1["type"] == "initial_snapshot"

        with client.websocket_connect("/ws") as ws2:
            snapshot2 = ws2.receive_json()
            assert snapshot2["type"] == "initial_snapshot"

            # Client 1 subscribes to AAPL
            ws1.send_json({"action": "set", "symbols": ["AAPL"]})
            ack1 = ws1.receive_json()
            assert ack1["subscribed_symbols"] == ["AAPL"]

            # Client 2 subscribes to GOOGL and MSFT independently
            ws2.send_json({"action": "set", "symbols": ["GOOGL", "MSFT"]})
            ack2 = ws2.receive_json()
            assert sorted(ack2["subscribed_symbols"]) == ["GOOGL", "MSFT"]

            # Verify independence
            assert ack1["subscribed_symbols"] != ack2["subscribed_symbols"]


@pytest.mark.asyncio
async def test_connection_manager_broadcast_and_filtering():
    """Unit test ConnectionManager selective broadcast logic."""
    manager = ConnectionManager()

    # Mock fake websockets with queue-based receive
    class MockWebSocket:
        def __init__(self, client_id: str):
            self.client = client_id
            self.inbox = asyncio.Queue()
            self.is_closed = False

        async def accept(self):
            pass

        async def send_json(self, data: dict):
            if self.is_closed:
                raise RuntimeError("Socket closed")
            await self.inbox.put(data)

    stock_aapl = StockData(
        symbol="AAPL",
        company="Apple Inc.",
        price=180.00,
        previous_price=179.50,
        change=0.50,
        change_percent=0.28,
        is_simulated=True,
        timestamp=get_current_utc_iso(),
    )
    stock_tsla = StockData(
        symbol="TSLA",
        company="Tesla Inc.",
        price=220.00,
        previous_price=218.00,
        change=2.00,
        change_percent=0.91,
        is_simulated=True,
        timestamp=get_current_utc_iso(),
    )

    ws_client1 = MockWebSocket("client-1")
    ws_client2 = MockWebSocket("client-2")

    # Connect client 1 with initial stocks
    await manager.connect(ws_client1, [stock_aapl, stock_tsla], default_all=False)
    # Connect client 2 with initial stocks
    await manager.connect(ws_client2, [stock_aapl, stock_tsla], default_all=False)

    # Drain initial snapshots
    _ = await ws_client1.inbox.get()
    _ = await ws_client2.inbox.get()

    # Client 1 subscribes ONLY to AAPL
    await manager.handle_subscription_request(
        ws_client1, {"action": "set", "symbols": ["AAPL"]}, {"AAPL", "TSLA"}
    )
    _ = await ws_client1.inbox.get()

    # Client 2 subscribes ONLY to TSLA
    await manager.handle_subscription_request(
        ws_client2, {"action": "set", "symbols": ["TSLA"]}, {"AAPL", "TSLA"}
    )
    _ = await ws_client2.inbox.get()

    # Broadcast AAPL update: only client 1 should receive it
    await manager.broadcast_stock_update(stock_aapl)

    assert not ws_client1.inbox.empty()
    aapl_msg = await ws_client1.inbox.get()
    assert aapl_msg["type"] == "stock_update"
    assert aapl_msg["data"]["symbol"] == "AAPL"

    # Client 2 should NOT have received AAPL
    assert ws_client2.inbox.empty()

    # Broadcast TSLA update: only client 2 should receive it
    await manager.broadcast_stock_update(stock_tsla)

    assert not ws_client2.inbox.empty()
    tsla_msg = await ws_client2.inbox.get()
    assert tsla_msg["type"] == "stock_update"
    assert tsla_msg["data"]["symbol"] == "TSLA"
    assert ws_client1.inbox.empty()

    # Test safe disconnection
    await manager.disconnect(ws_client1)
    assert manager.active_connections_count == 1
    await manager.disconnect(ws_client2)
    assert manager.active_connections_count == 0
