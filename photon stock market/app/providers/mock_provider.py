"""Asynchronous mock stock data generator for Photon.

Simulates realistic, low-latency financial market price fluctuations, corporate fundamentals,
and OHLCV candlestick/graph data for demonstration purposes without requiring external APIs.
All generated data is explicitly marked as simulated.
"""

import asyncio
from datetime import datetime, timedelta, timezone
import random
from typing import Dict, List, Optional
from app.models import CandleData, StockData, StockDetail, get_current_utc_iso
from app.providers.base import BaseStockProvider


DEMO_STOCKS_METADATA = {
    "AAPL": {
        "company": "Apple Inc.",
        "initial_price": 182.50,
        "sector": "Technology",
        "market_cap": "$2.82 Trillion",
        "pe_ratio": 29.4,
        "fifty_two_week_high": 199.62,
        "fifty_two_week_low": 164.08,
        "base_volume": 42500000,
        "description": "Apple Inc. designs, manufactures, and markets smartphones, personal computers, tablets, wearables, and accessories, and sells a variety of related services.",
    },
    "GOOGL": {
        "company": "Alphabet Inc.",
        "initial_price": 155.30,
        "sector": "Communication Services",
        "market_cap": "$1.95 Trillion",
        "pe_ratio": 24.1,
        "fifty_two_week_high": 191.75,
        "fifty_two_week_low": 120.21,
        "base_volume": 24800000,
        "description": "Alphabet Inc. offers products and platforms including Google Search, Ads, Maps, Android, Chrome, Cloud, YouTube, and Google Play.",
    },
    "MSFT": {
        "company": "Microsoft Corporation",
        "initial_price": 420.75,
        "sector": "Technology",
        "market_cap": "$3.12 Trillion",
        "pe_ratio": 34.8,
        "fifty_two_week_high": 468.35,
        "fifty_two_week_low": 309.45,
        "base_volume": 18900000,
        "description": "Microsoft Corporation develops, licenses, and supports software products, services, devices, and AI cloud computing solutions worldwide.",
    },
    "AMZN": {
        "company": "Amazon.com Inc.",
        "initial_price": 178.90,
        "sector": "Consumer Cyclical",
        "market_cap": "$1.88 Trillion",
        "pe_ratio": 41.2,
        "fifty_two_week_high": 201.20,
        "fifty_two_week_low": 118.35,
        "base_volume": 33400000,
        "description": "Amazon.com, Inc. focuses on retail e-commerce, cloud computing (AWS), digital streaming, and artificial intelligence.",
    },
    "TSLA": {
        "company": "Tesla Inc.",
        "initial_price": 218.40,
        "sector": "Automotive & Clean Energy",
        "market_cap": "$695.4 Billion",
        "pe_ratio": 62.5,
        "fifty_two_week_high": 271.00,
        "fifty_two_week_low": 138.80,
        "base_volume": 67800000,
        "description": "Tesla, Inc. designs, manufactures, and sells fully electric vehicles, energy generation and storage systems, and autonomous driving tech.",
    },
    "NVDA": {
        "company": "NVIDIA Corporation",
        "initial_price": 128.60,
        "sector": "Semiconductors & AI",
        "market_cap": "$3.18 Trillion",
        "pe_ratio": 68.3,
        "fifty_two_week_high": 140.76,
        "fifty_two_week_low": 39.23,
        "base_volume": 79400000,
        "description": "NVIDIA Corporation pioneered GPU-accelerated computing to solve computational challenges across gaming, AI, and enterprise data centers.",
    },
}


class MockStockProvider(BaseStockProvider):
    """Generates continuous simulated market updates, metrics, and OHLC candles."""

    def __init__(self, update_interval: float = 1.0) -> None:
        self.update_interval = max(0.2, update_interval)
        self._stocks: Dict[str, StockData] = {}
        self._details: Dict[str, StockDetail] = {}
        self._candles: Dict[str, List[CandleData]] = {}
        self._symbols: List[str] = []
        self._candle_tick_counter: Dict[str, int] = {}
        self._initialize_stocks()

    def _generate_initial_candles(self, base_price: float, count: int = 45) -> List[CandleData]:
        """Generate realistic historical OHLC candles with pronounced, visible bodies and wicks."""
        candles: List[CandleData] = []
        now = datetime.now(timezone.utc)
        
        # Start ~1.5% to 2.5% away to create a realistic intraday movement curve
        price = max(1.0, base_price * (1.0 - random.uniform(-0.025, 0.025)))
        trend = random.choice([-1, 1]) * random.uniform(0.002, 0.005)
        trend_duration = random.randint(4, 8)

        for i in range(count, 0, -1):
            time_label = (now - timedelta(minutes=i)).strftime("%H:%M")
            open_p = price

            # Cycle trend waves to simulate authentic buyer/seller momentum
            trend_duration -= 1
            if trend_duration <= 0:
                trend = random.choice([-1, 1]) * random.uniform(0.002, 0.006)
                trend_duration = random.randint(3, 7)

            # Prominent candle body movement (0.3% to 1.4%)
            body_delta = open_p * (trend + random.gauss(0, 0.005))
            close_p = max(1.0, round(open_p + body_delta, 2))

            # Upper and lower wicks extending visibly beyond the body
            upper_wick = abs(open_p * random.uniform(0.002, 0.007))
            lower_wick = abs(open_p * random.uniform(0.002, 0.007))

            high_p = max(1.0, round(max(open_p, close_p) + upper_wick, 2))
            low_p = max(1.0, round(min(open_p, close_p) - lower_wick, 2))
            vol = random.randint(25000, 195000)

            candles.append(CandleData(
                time=time_label,
                open=round(open_p, 2),
                high=high_p,
                low=low_p,
                close=close_p,
                volume=vol,
            ))
            price = close_p

        # Ensure the final candle matches the current live base_price
        if candles:
            candles[-1].close = round(base_price, 2)
            candles[-1].high = max(candles[-1].high, round(base_price + abs(base_price * 0.003), 2))
            candles[-1].low = min(candles[-1].low, round(base_price - abs(base_price * 0.003), 2))

        return candles

    def _initialize_stocks(self) -> None:
        """Set up demonstration stocks with baseline prices, fundamentals, and candles."""
        timestamp = get_current_utc_iso()
        for symbol, meta in DEMO_STOCKS_METADATA.items():
            price = round(meta["initial_price"], 2)
            candles = self._generate_initial_candles(price, count=35)
            self._candles[symbol] = candles
            self._candle_tick_counter[symbol] = 0

            # Day High / Low from generated candles
            day_high = max(c.high for c in candles)
            day_low = min(c.low for c in candles)
            day_open = candles[0].open
            vol = meta["base_volume"] + sum(c.volume for c in candles)

            change = round(price - day_open, 2)
            change_pct = round(((price - day_open) / day_open) * 100, 4)

            stock_data = StockData(
                symbol=symbol,
                company=meta["company"],
                price=price,
                previous_price=price,
                change=change,
                change_percent=change_pct,
                currency="USD",
                is_simulated=True,
                timestamp=timestamp,
            )
            self._stocks[symbol] = stock_data

            detail = StockDetail(
                symbol=symbol,
                company=meta["company"],
                price=price,
                previous_price=price,
                change=change,
                change_percent=change_pct,
                currency="USD",
                is_simulated=True,
                timestamp=timestamp,
                sector=meta["sector"],
                description=meta["description"],
                market_cap=meta["market_cap"],
                pe_ratio=meta["pe_ratio"],
                day_open=day_open,
                day_high=day_high,
                day_low=day_low,
                volume=vol,
                fifty_two_week_high=meta["fifty_two_week_high"],
                fifty_two_week_low=meta["fifty_two_week_low"],
                candles=candles,
            )
            self._details[symbol] = detail
            self._symbols.append(symbol)

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def is_simulated(self) -> bool:
        return True

    def get_initial_stocks(self) -> Dict[str, StockData]:
        return {s: data.model_copy() for s, data in self._stocks.items()}

    def get_current_stocks(self) -> Dict[str, StockData]:
        return {s: data.model_copy() for s, data in self._stocks.items()}

    def get_stock(self, symbol: str) -> Optional[StockData]:
        stock = self._stocks.get(symbol.strip().upper())
        return stock.model_copy() if stock else None

    def get_stock_detail(self, symbol: str) -> Optional[StockDetail]:
        sym = symbol.strip().upper()
        detail = self._details.get(sym)
        if not detail:
            return None
        # Return deep copy with latest candles
        copy_detail = detail.model_copy()
        copy_detail.candles = [c.model_copy() for c in self._candles.get(sym, [])]
        return copy_detail

    async def generate_next_update(self) -> Optional[StockData]:
        """Generate a random price movement and update active candle data."""
        await asyncio.sleep(self.update_interval)

        if not self._symbols:
            return None

        # Pick one stock to update for realistic ticker pacing
        symbol = random.choice(self._symbols)
        current = self._stocks[symbol]

        previous_price = current.price
        # Delta percentage between -1.5% and +1.5%
        delta_pct = max(-0.025, min(0.025, random.gauss(0, 0.0075)))

        raw_new_price = previous_price * (1.0 + delta_pct)
        new_price = max(1.00, round(raw_new_price, 2))

        if new_price == previous_price:
            nudge = random.choice([-0.01, 0.01])
            new_price = max(1.00, round(previous_price + nudge, 2))

        change = round(new_price - previous_price, 2)
        change_pct = round(((new_price - previous_price) / previous_price) * 100, 4)
        timestamp = get_current_utc_iso()

        updated_stock = StockData(
            symbol=symbol,
            company=current.company,
            price=new_price,
            previous_price=previous_price,
            change=change,
            change_percent=change_pct,
            currency="USD",
            is_simulated=True,
            timestamp=timestamp,
        )
        self._stocks[symbol] = updated_stock

        # Update details and candles
        if symbol in self._details:
            detail = self._details[symbol]
            detail.price = new_price
            detail.previous_price = previous_price
            detail.change = round(new_price - detail.day_open, 2)
            detail.change_percent = round(((new_price - detail.day_open) / detail.day_open) * 100, 4)
            detail.day_high = max(detail.day_high, new_price)
            detail.day_low = min(detail.day_low, new_price)
            tick_vol = random.randint(500, 6000)
            detail.volume += tick_vol
            detail.timestamp = timestamp

            # Update live candle
            candles = self._candles.get(symbol, [])
            self._candle_tick_counter[symbol] += 1

            if candles:
                last_candle = candles[-1]
                last_candle.close = new_price
                last_candle.high = max(last_candle.high, new_price)
                last_candle.low = min(last_candle.low, new_price)
                last_candle.volume += tick_vol

                # Form new candle every 15 ticks
                if self._candle_tick_counter[symbol] >= 15:
                    self._candle_tick_counter[symbol] = 0
                    time_label = datetime.now(timezone.utc).strftime("%H:%M")
                    new_candle = CandleData(
                        time=time_label,
                        open=new_price,
                        high=new_price,
                        low=new_price,
                        close=new_price,
                        volume=tick_vol,
                    )
                    candles.append(new_candle)
                    # Keep maximum 60 candles in sliding window
                    if len(candles) > 60:
                        candles.pop(0)

        return updated_stock
