"""Stock service layer orchestrating data providers and streaming lifecycle.

Provides unified, consistent data access for both REST API endpoints and
WebSocket broadcasting routines.
"""

import asyncio
import logging
from typing import Callable, Coroutine, Dict, List, Optional, Set
from app.models import StockData, StockDetail
from app.providers.base import BaseStockProvider
from app.providers.mock_provider import MockStockProvider

logger = logging.getLogger("photon.stock_service")


class StockService:
    """Core service managing stock data state and asynchronous update generation."""

    def __init__(self, provider: Optional[BaseStockProvider] = None) -> None:
        self.provider: BaseStockProvider = provider or MockStockProvider()
        self._stream_task: Optional[asyncio.Task] = None
        self._is_running: bool = False

    @property
    def provider_name(self) -> str:
        return self.provider.provider_name

    @property
    def is_simulated(self) -> bool:
        return self.provider.is_simulated

    def get_all_stocks(self) -> List[StockData]:
        """Return the current snapshot of all tracked stocks."""
        stocks_dict = self.provider.get_current_stocks()
        return list(stocks_dict.values())

    def get_stock(self, symbol: str) -> Optional[StockData]:
        """Return the current data for an individual stock symbol."""
        return self.provider.get_stock(symbol)

    def get_stock_detail(self, symbol: str) -> Optional[StockDetail]:
        """Return rich metrics, fundamental valuations, and OHLC candle history."""
        return self.provider.get_stock_detail(symbol)

    def get_valid_symbols(self) -> Set[str]:
        """Return the set of valid uppercase ticker symbols tracked by the service."""
        return set(self.provider.get_current_stocks().keys())

    async def start_streaming(
        self,
        on_update: Callable[[StockData], Coroutine[None, None, None]]
    ) -> None:
        """Start the background streaming task that emits real-time updates.

        Args:
            on_update: Async callback function called whenever a new stock update is ready.
        """
        if self._is_running:
            logger.warning("Stock streaming service is already running.")
            return

        self._is_running = True
        self._stream_task = asyncio.create_task(self._stream_loop(on_update))
        logger.info(
            f"Started stock data streamer using '{self.provider_name}' provider."
        )

    async def stop_streaming(self) -> None:
        """Gracefully stop and cancel the background streaming task."""
        if not self._is_running:
            return

        self._is_running = False
        if self._stream_task and not self._stream_task.done():
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass
            logger.info("Stock data streaming task cancelled successfully.")

    async def _stream_loop(
        self,
        on_update: Callable[[StockData], Coroutine[None, None, None]]
    ) -> None:
        """Continuously query provider for updates and forward to callback."""
        while self._is_running:
            try:
                update = await self.provider.generate_next_update()
                if update is not None and self._is_running:
                    await on_update(update)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error generating stock price update: {e}", exc_info=True)
                # Brief pause before retrying on unforeseen errors
                await asyncio.sleep(1.0)
