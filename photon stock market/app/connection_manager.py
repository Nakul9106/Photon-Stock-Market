"""WebSocket Connection and Broadcast Manager for Photon.

Manages active client connections, handles client lifecycles, maintains
per-client stock subscription sets, and broadcasts updates reliably without
letting one failing connection block or degrade service to others.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Set
from fastapi import WebSocket
from app.models import (
    ErrorMessage,
    InitialSnapshotMessage,
    StockData,
    StockUpdateMessage,
    SubscriptionRequest,
    SubscriptionStatusMessage,
    get_current_utc_iso,
)

logger = logging.getLogger("photon.connection_manager")


class ConnectionManager:
    """Manages active WebSocket connections and per-client stock subscriptions.

    Attributes:
        _active_connections: Dict mapping WebSocket instance to set of subscribed symbols.
                              If the set is empty or None, it defaults to ALL tracked symbols.
        _lock: Asyncio lock protecting mutations to connection registry.
    """

    def __init__(self) -> None:
        # Map: WebSocket -> Set[str] (subscribed symbols). Empty set = subscribed to ALL stocks.
        self._subscriptions: Dict[WebSocket, Set[str]] = {}
        self._lock = asyncio.Lock()

    @property
    def active_connections_count(self) -> int:
        """Return the count of currently active WebSocket connections."""
        return len(self._subscriptions)

    async def connect(
        self,
        websocket: WebSocket,
        initial_stocks: List[StockData],
        default_all: bool = True
    ) -> None:
        """Accept new WebSocket connection, register default subscription, and send initial snapshot.

        Args:
            websocket: Incoming WebSocket connection.
            initial_stocks: Current snapshot of all available stocks.
            default_all: If True, client is initially subscribed to all stocks.
        """
        await websocket.accept()
        async with self._lock:
            # Default to all available symbols
            all_symbols = {s.symbol for s in initial_stocks} if default_all else set()
            self._subscriptions[websocket] = all_symbols

        logger.info(
            f"Client connected: {websocket.client}. Active connections: {len(self._subscriptions)}"
        )

        # Send initial snapshot immediately upon connection
        snapshot = InitialSnapshotMessage(
            timestamp=get_current_utc_iso(),
            is_simulated=True,
            data=initial_stocks,
        )
        await self.send_personal_message(websocket, snapshot.model_dump())

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a disconnected client from the registry safely."""
        async with self._lock:
            if websocket in self._subscriptions:
                del self._subscriptions[websocket]
                logger.info(
                    f"Client disconnected. Remaining connections: {len(self._subscriptions)}"
                )

    async def handle_subscription_request(
        self,
        websocket: WebSocket,
        raw_payload: dict,
        valid_symbols: Set[str]
    ) -> None:
        """Parse, validate, and apply subscription changes for a specific client.

        Args:
            websocket: Client WebSocket.
            raw_payload: Deserialized JSON received from client.
            valid_symbols: Set of all valid stock symbols available in system.
        """
        try:
            req = SubscriptionRequest.model_validate(raw_payload)
        except Exception as e:
            err_msg = ErrorMessage(
                error=f"Invalid subscription request payload: {str(e)}"
            )
            await self.send_personal_message(websocket, err_msg.model_dump())
            return

        async with self._lock:
            if websocket not in self._subscriptions:
                return

            current_subs = self._subscriptions[websocket]

            # Filter requested symbols against system valid symbols
            requested_valid = {s for s in req.symbols if s in valid_symbols}
            unknown_symbols = [s for s in req.symbols if s not in valid_symbols]

            if req.action == "subscribe":
                current_subs.update(requested_valid)
                status_text = f"Subscribed to {list(requested_valid)}"
            elif req.action == "unsubscribe":
                current_subs.difference_update(requested_valid)
                status_text = f"Unsubscribed from {list(requested_valid)}"
            elif req.action == "set":
                # Explicitly set entire subscription list
                self._subscriptions[websocket] = set(requested_valid)
                current_subs = self._subscriptions[websocket]
                status_text = f"Subscription updated to {list(requested_valid)}"
            else:
                status_text = "Unknown action ignored"

            final_subs = sorted(list(current_subs))

        warning_info = f" (Ignored unknown symbols: {unknown_symbols})" if unknown_symbols else ""
        resp = SubscriptionStatusMessage(
            status="warning" if unknown_symbols else "success",
            subscribed_symbols=final_subs,
            message=f"{status_text}{warning_info}",
        )
        await self.send_personal_message(websocket, resp.model_dump())

    async def broadcast_stock_update(self, stock: StockData) -> None:
        """Broadcast a stock update to all clients subscribed to this stock.

        Safely handles failed sends, removes stale/disconnected clients,
        and ensures no client delays or blocks other clients.
        """
        message = StockUpdateMessage(
            timestamp=stock.timestamp,
            data=stock,
        ).model_dump()

        # Capture snapshot of clients and check their subscriptions
        async with self._lock:
            eligible_clients: List[WebSocket] = []
            for ws, subs in self._subscriptions.items():
                # If subscription set is empty, treat as subscribed to ALL stocks
                if not subs or stock.symbol in subs:
                    eligible_clients.append(ws)

        if not eligible_clients:
            return

        # Broadcast concurrently across eligible clients
        dead_clients: List[WebSocket] = []

        async def _safe_send(ws: WebSocket) -> None:
            try:
                await ws.send_json(message)
            except Exception as exc:
                logger.debug(f"Failed send to client {ws.client}: {exc}")
                dead_clients.append(ws)

        # Run all sends in parallel with gather
        await asyncio.gather(*[_safe_send(ws) for ws in eligible_clients], return_exceptions=True)

        # Prune disconnected clients if any failed during broadcast
        if dead_clients:
            async with self._lock:
                for dead_ws in dead_clients:
                    self._subscriptions.pop(dead_ws, None)
            logger.info(
                f"Pruned {len(dead_clients)} stale connections. Active: {len(self._subscriptions)}"
            )

    async def send_personal_message(self, websocket: WebSocket, message: dict) -> None:
        """Send a JSON payload directly to a specific client safely."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"Error sending personal message to client: {e}")
            await self.disconnect(websocket)
