"""
Market Monitor - Fetches and manages market data.

This component is responsible for:
- Loading raw market data (OHLCV) from exchanges
- Managing multiple fixed timeframes
- No logic, no decisions - pure data provider
"""

import ccxt
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import structlog

from src.common.models import MarketData, Timeframe
from src.config import config

logger = structlog.get_logger(__name__)


class MarketMonitor:
    """
    Market Monitor component.

    Fetches OHLCV data from exchanges and provides it to other components.
    """

    def __init__(
        self, symbol: Optional[str] = None, timeframes: Optional[List[str]] = None
    ):
        """
        Initialize Market Monitor.

        Args:
            symbol: Trading symbol (e.g., "BTC/USDT")
            timeframes: List of timeframes to monitor (e.g., ["1d", "4h", "15m"])
        """
        self.symbol = symbol or config.trading.default_symbol
        self.timeframes = timeframes or config.trading.timeframes

        # Initialize exchange
        exchange_class = getattr(ccxt, config.exchange.name)
        self.exchange = exchange_class(
            {
                "apiKey": config.exchange.api_key,
                "secret": config.exchange.api_secret,
                "enableRateLimit": True,
                "options": {
                    "defaultType": (
                        "future" if config.exchange.paper_trading else "spot"
                    ),
                },
            }
        )

        if config.exchange.paper_trading:
            self.exchange.set_sandbox_mode(True)
            logger.info("Market Monitor initialized in PAPER TRADING mode")

        # In-memory cache for recent candles
        self.cache: Dict[str, pd.DataFrame] = {}

        logger.info(
            "Market Monitor initialized",
            symbol=self.symbol,
            timeframes=self.timeframes,
            exchange=config.exchange.name,
        )

    def fetch_ohlcv(self, timeframe: str, limit: int = 100) -> MarketData:
        """
        Fetch OHLCV data for a specific timeframe.

        Args:
            timeframe: Timeframe to fetch (e.g., "1d", "4h", "15m")
            limit: Number of candles to fetch

        Returns:
            MarketData object with OHLCV data
        """
        try:
            logger.debug(
                "Fetching OHLCV data",
                symbol=self.symbol,
                timeframe=timeframe,
                limit=limit,
            )

            # Fetch from exchange
            ohlcv = self.exchange.fetch_ohlcv(
                symbol=self.symbol, timeframe=timeframe, limit=limit
            )

            # Update cache
            self.cache[timeframe] = pd.DataFrame(
                ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )

            # Determine bar completeness (is the latest candle closed?)
            last_bar_closed = self._is_last_bar_closed(ohlcv, timeframe)

            # Create MarketData object
            market_data = MarketData(
                symbol=self.symbol,
                timeframe=Timeframe(timeframe),
                timestamp=datetime.now(),
                ohlcv=ohlcv,
                is_closed=last_bar_closed,
            )

            logger.debug(
                "OHLCV data fetched successfully",
                symbol=self.symbol,
                timeframe=timeframe,
                candles=len(ohlcv),
            )

            return market_data

        except Exception as e:
            logger.error(
                "Error fetching OHLCV data",
                symbol=self.symbol,
                timeframe=timeframe,
                error=str(e),
            )
            raise

    def _is_last_bar_closed(self, ohlcv: List[List[float]], timeframe: str) -> bool:
        """
        Determine if the latest bar is closed for the given timeframe.

        Args:
            ohlcv: OHLCV list returned by the exchange
            timeframe: Timeframe string (e.g., "1d", "4h", "15m")

        Returns:
            True if the last bar should be closed, False otherwise.
        """
        if not ohlcv:
            return True

        last_ts_ms = ohlcv[-1][0]
        last_open = datetime.utcfromtimestamp(last_ts_ms / 1000)
        delta = self._timeframe_to_timedelta(timeframe)
        last_close = last_open + delta

        return datetime.utcnow() >= last_close

    def _timeframe_to_timedelta(self, timeframe: str) -> timedelta:
        """
        Convert a timeframe string to a timedelta.

        Args:
            timeframe: Timeframe string (e.g., "1d", "4h", "15m")

        Returns:
            timedelta for the timeframe
        """
        if timeframe.endswith("d"):
            value = int(timeframe[:-1])
            return timedelta(days=value)
        if timeframe.endswith("h"):
            value = int(timeframe[:-1])
            return timedelta(hours=value)
        if timeframe.endswith("m"):
            value = int(timeframe[:-1])
            return timedelta(minutes=value)

        raise ValueError(f"Unsupported timeframe: {timeframe}")

    def fetch_all_timeframes(self, limit: int = 100) -> Dict[str, MarketData]:
        """
        Fetch OHLCV data for all configured timeframes.

        Args:
            limit: Number of candles to fetch per timeframe

        Returns:
            Dictionary mapping timeframe to MarketData
        """
        result = {}

        for timeframe in self.timeframes:
            try:
                market_data = self.fetch_ohlcv(timeframe, limit)
                result[timeframe] = market_data
            except Exception as e:
                logger.error(
                    "Failed to fetch timeframe data", timeframe=timeframe, error=str(e)
                )
                # Continue with other timeframes
                continue

        logger.info(
            "Fetched all timeframes",
            symbol=self.symbol,
            successful_timeframes=len(result),
            total_timeframes=len(self.timeframes),
        )

        return result

    def get_cached_data(self, timeframe: str) -> Optional[pd.DataFrame]:
        """
        Get cached data for a specific timeframe.

        Args:
            timeframe: Timeframe to retrieve

        Returns:
            DataFrame with cached OHLCV data or None if not cached
        """
        return self.cache.get(timeframe)

    def get_latest_price(self) -> float:
        """
        Get the latest price for the symbol.

        Returns:
            Latest price
        """
        try:
            ticker = self.exchange.fetch_ticker(self.symbol)
            return ticker["last"]
        except Exception as e:
            logger.error("Error fetching latest price", error=str(e))
            raise
