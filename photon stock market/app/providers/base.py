"""Base interface for stock data providers in Photon.

All providers (mock, Alpaca, Finnhub, etc.) implement this contract,
ensuring clean separation of concerns and seamless plug-and-play capability.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional
from app.models import StockData, StockDetail


class BaseStockProvider(ABC):
    """Abstract base class establishing the contract for stock data providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider (e.g., 'mock', 'alpaca', 'finnhub')."""
        pass

    @property
    @abstractmethod
    def is_simulated(self) -> bool:
        """True if the data generated/provided is simulated demonstration data."""
        pass

    @abstractmethod
    def get_initial_stocks(self) -> Dict[str, StockData]:
        """Return the baseline dictionary of initialized stocks keyed by symbol."""
        pass

    @abstractmethod
    def get_current_stocks(self) -> Dict[str, StockData]:
        """Return the current snapshot of all tracked stocks."""
        pass

    @abstractmethod
    def get_stock(self, symbol: str) -> Optional[StockData]:
        """Retrieve the current data for a specific stock symbol."""
        pass

    @abstractmethod
    def get_stock_detail(self, symbol: str) -> Optional[StockDetail]:
        """Retrieve comprehensive metrics, sector info, and historical OHLC candles."""
        pass

    @abstractmethod
    async def generate_next_update(self) -> Optional[StockData]:
        """Generate or fetch the next stock price update asynchronously."""
        pass
