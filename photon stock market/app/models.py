"""Pydantic data models for Photon stock ticker application.

Ensures strict validation, consistent serialization, and structured communication
between backend services, REST endpoints, and WebSocket clients.
"""

from datetime import datetime, timezone
from typing import Any, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


def get_current_utc_iso() -> str:
    """Return the current UTC timestamp formatted as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class StockData(BaseModel):
    """Represents a single stock's real-time price and movement metrics."""

    symbol: str = Field(..., description="Ticker symbol (e.g., AAPL)")
    company: str = Field(..., description="Full legal or commercial company name")
    price: float = Field(..., ge=0.01, description="Current simulated stock price in USD")
    previous_price: float = Field(..., ge=0.01, description="Previous recorded stock price in USD")
    change: float = Field(..., description="Absolute price difference (price - previous_price)")
    change_percent: float = Field(..., description="Percentage price movement")
    currency: str = Field(default="USD", description="Currency denomination")
    is_simulated: bool = Field(default=True, description="Flag indicating demonstration/simulated data")
    timestamp: str = Field(default_factory=get_current_utc_iso, description="ISO 8601 UTC timestamp")

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("price", "previous_price", "change")
    @classmethod
    def round_two_decimals(cls, v: float) -> float:
        return round(float(v), 2)

    @field_validator("change_percent")
    @classmethod
    def round_four_decimals(cls, v: float) -> float:
        return round(float(v), 4)


class CandleData(BaseModel):
    """OHLCV candlestick data point."""

    time: str = Field(..., description="Timestamp or time label (e.g. 09:30:00)")
    open: float = Field(..., ge=0.01)
    high: float = Field(..., ge=0.01)
    low: float = Field(..., ge=0.01)
    close: float = Field(..., ge=0.01)
    volume: int = Field(default=0)


class StockDetail(StockData):
    """Extended stock metrics including sector, valuation, 52-week ranges, and OHLC candles."""

    sector: str = Field(default="Technology")
    description: str = Field(default="")
    market_cap: str = Field(default="")
    pe_ratio: float = Field(default=0.0)
    day_open: float = Field(default=0.0)
    day_high: float = Field(default=0.0)
    day_low: float = Field(default=0.0)
    volume: int = Field(default=0)
    fifty_two_week_high: float = Field(default=0.0)
    fifty_two_week_low: float = Field(default=0.0)
    candles: List[CandleData] = Field(default_factory=list)


class StockUpdateMessage(BaseModel):
    """Message broadcast when a stock price changes."""

    type: Literal["stock_update"] = "stock_update"
    timestamp: str = Field(default_factory=get_current_utc_iso)
    data: StockData


class InitialSnapshotMessage(BaseModel):
    """Initial snapshot message sent to newly connected WebSocket clients."""

    type: Literal["initial_snapshot"] = "initial_snapshot"
    timestamp: str = Field(default_factory=get_current_utc_iso)
    is_simulated: bool = True
    data: List[StockData]


class SubscriptionRequest(BaseModel):
    """Client request to update stock subscriptions over WebSocket."""

    action: Literal["subscribe", "unsubscribe", "set"] = Field(
        ...,
        description="'subscribe' to add symbols, 'unsubscribe' to remove, 'set' to replace all"
    )
    symbols: List[str] = Field(
        default_factory=list,
        description="List of ticker symbols to modify subscription for"
    )

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, symbols: List[str]) -> List[str]:
        return [s.strip().upper() for s in symbols if isinstance(s, str) and s.strip()]


class SubscriptionStatusMessage(BaseModel):
    """Confirmation message sent back to client after subscription change."""

    type: Literal["subscription_status"] = "subscription_status"
    timestamp: str = Field(default_factory=get_current_utc_iso)
    status: Literal["success", "warning", "error"] = "success"
    subscribed_symbols: List[str]
    message: str


class ErrorMessage(BaseModel):
    """Error notification message for invalid WebSocket payloads or actions."""

    type: Literal["error"] = "error"
    timestamp: str = Field(default_factory=get_current_utc_iso)
    error: str


class HealthResponse(BaseModel):
    """System health check payload."""

    status: str = "ok"
    provider: str
    is_simulated: bool
    active_connections: int
    tracked_stocks: int
    timestamp: str = Field(default_factory=get_current_utc_iso)
