"""FastAPI application entrypoint for Photon - Real-time WebSocket Stock Ticker.

Configures REST API endpoints, WebSocket connection route, static assets,
Jinja2 template rendering, and background streaming task lifespan.
"""

from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.connection_manager import ConnectionManager
from app.models import HealthResponse, StockData, StockDetail, get_current_utc_iso
from app.stock_service import StockService

# Setup application logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("photon.app")

# Resolve directory paths
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Initialize singletons for connection management and stock data service
connection_manager = ConnectionManager()
stock_service = StockService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager handling background streaming service startup and teardown."""
    logger.info("Starting up Photon application services...")

    # Start the continuous stock streaming background task
    await stock_service.start_streaming(
        on_update=connection_manager.broadcast_stock_update
    )

    yield

    logger.info("Shutting down Photon application services...")
    await stock_service.stop_streaming()


app = FastAPI(
    title="Photon — Real-time WebSocket Stock Ticker",
    description="Live stock ticker web application powered by FastAPI WebSockets and simulated market data.",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount static asset directory
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Mount Jinja2 templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Return empty 204 No Content for favicon requests to prevent 404 warnings."""
    from fastapi.responses import Response
    return Response(status_code=204)


@app.get("/", response_class=HTMLResponse, summary="Serve Stock Dashboard")
async def get_dashboard(request: Request):
    """Serve the single-page real-time financial ticker dashboard."""
    initial_stocks = stock_service.get_all_stocks()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "title": "Photon — Real-time WebSocket Stock Ticker",
            "initial_stocks": initial_stocks,
            "is_simulated": stock_service.is_simulated,
        },
    )


@app.get(
    "/api/stocks",
    response_model=List[StockData],
    summary="Get Current Stock Prices",
)
async def get_stocks():
    """Return the current snapshot of all tracked stock prices and metadata in JSON."""
    return stock_service.get_all_stocks()


@app.get(
    "/api/stocks/{symbol}",
    response_model=StockDetail,
    summary="Get In-depth Stock Metrics and Candlestick History",
)
async def get_stock_detail(symbol: str):
    """Return comprehensive corporate profile, metrics, and OHLC candlestick history."""
    detail = stock_service.get_stock_detail(symbol)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Stock symbol '{symbol.upper()}' not found.")
    return detail


@app.get(
    "/api/health",
    response_model=HealthResponse,
    summary="Application Health Status",
)
async def get_health():
    """Return health status, active connection count, and provider info."""
    return HealthResponse(
        status="ok",
        provider=stock_service.provider_name,
        is_simulated=stock_service.is_simulated,
        active_connections=connection_manager.active_connections_count,
        tracked_stocks=len(stock_service.get_all_stocks()),
        timestamp=get_current_utc_iso(),
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Establish and maintain a persistent real-time WebSocket connection.

    1. Registers new connection.
    2. Sends initial snapshot of all stocks.
    3. Listens for client subscription requests.
    4. Handles disconnection and malformed JSON safely.
    """
    initial_stocks = stock_service.get_all_stocks()
    await connection_manager.connect(websocket, initial_stocks, default_all=True)

    try:
        while True:
            # Await client messages (subscription commands, pings, etc.)
            data = await websocket.receive_json()
            valid_symbols = stock_service.get_valid_symbols()
            await connection_manager.handle_subscription_request(
                websocket, data, valid_symbols
            )
    except WebSocketDisconnect:
        await connection_manager.disconnect(websocket)
    except Exception as exc:
        logger.warning(f"WebSocket client error ({websocket.client}): {exc}")
        await connection_manager.disconnect(websocket)
