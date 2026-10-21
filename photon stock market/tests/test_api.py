"""Automated test suite for Photon REST API endpoints and data models.

Tests cover:
- GET / (Homepage dashboard availability and HTML rendering)
- GET /api/stocks (Response structure, data schema, price bounds)
- GET /api/health (Health status, provider reporting, connection tracking)
- StockData model validations
- MockStockProvider generation and boundary safety
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models import StockData
from app.providers.mock_provider import MockStockProvider


@pytest.fixture
def client():
    """Create a FastAPI test client instance."""
    with TestClient(app) as test_client:
        yield test_client


def test_homepage_availability(client: TestClient):
    """Verify that GET / returns HTTP 200 and loads the dashboard HTML."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Photon" in response.text
    assert "Real-time WebSocket Stock Ticker" in response.text
    assert "SIMULATED DATA" in response.text
    # Verify presence of demo stock symbols
    for symbol in ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA"]:
        assert symbol in response.text


def test_api_stocks_response_structure(client: TestClient):
    """Verify that GET /api/stocks returns valid JSON and matches StockData schema."""
    response = client.get("/api/stocks")
    assert response.status_code == 200
    stocks = response.json()
    assert isinstance(stocks, list)
    assert len(stocks) >= 6

    # Verify each stock has all required fields with proper types
    symbols = set()
    for stock in stocks:
        validated = StockData.model_validate(stock)
        symbols.add(validated.symbol)
        assert validated.price > 0, "Price must be strictly positive"
        assert validated.previous_price > 0, "Previous price must be strictly positive"
        assert validated.currency == "USD"
        assert validated.is_simulated is True
        assert len(validated.company) > 0

    assert {"AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA"}.issubset(symbols)


def test_api_health_response(client: TestClient):
    """Verify that GET /api/health returns system operational metrics."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["provider"] == "mock"
    assert data["is_simulated"] is True
    assert isinstance(data["active_connections"], int)
    assert data["tracked_stocks"] >= 6
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_mock_provider_price_generation():
    """Verify that MockStockProvider creates non-negative price updates."""
    provider = MockStockProvider(update_interval=0.01)
    stocks = provider.get_initial_stocks()
    assert len(stocks) == 6

    # Generate 15 simulated updates
    for _ in range(15):
        update = await provider.generate_next_update()
        assert update is not None
        assert update.price >= 1.0, "Simulated price must stay above minimum floor"
        assert update.is_simulated is True
        assert update.previous_price > 0
        assert round(update.price - update.previous_price, 2) == update.change


def test_api_stock_detail_endpoint(client: TestClient):
    """Verify that GET /api/stocks/{symbol} returns full metrics and OHLC candles."""
    response = client.get("/api/stocks/AAPL")
    assert response.status_code == 200
    data = response.json()

    assert data["symbol"] == "AAPL"
    assert data["company"] == "Apple Inc."
    assert "sector" in data
    assert "market_cap" in data
    assert "pe_ratio" in data
    assert "day_high" in data
    assert "day_low" in data
    assert "volume" in data
    assert "fifty_two_week_high" in data
    assert "fifty_two_week_low" in data

    # Verify candles list
    candles = data.get("candles", [])
    assert isinstance(candles, list)
    assert len(candles) > 0

    for c in candles:
        assert "time" in c
        assert c["open"] > 0
        assert c["high"] >= min(c["open"], c["close"])
        assert c["low"] <= max(c["open"], c["close"])
        assert c["close"] > 0
        assert c["volume"] >= 0


def test_api_stock_detail_not_found(client: TestClient):
    """Verify that requesting an unknown stock returns 404 Not Found."""
    response = client.get("/api/stocks/INVALID_TICKER")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

