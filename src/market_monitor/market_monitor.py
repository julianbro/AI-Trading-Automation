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
from src.exchanges import BitunixClient

logger = structlog.get_logger(__name__)


class MarketMonitor:
    """
    Market Monitor component.
    
    Fetches OHLCV data from exchanges and provides it to other components.
    """
    
    def __init__(self, symbol: Optional[str] = None, timeframes: Optional[List[str]] = None):
        """
        Initialize Market Monitor.
        
        Args:
            symbol: Trading symbol (e.g., "BTC/USDT")
            timeframes: List of timeframes to monitor (e.g., ["1d", "4h", "15m"])
        """
        self.symbol = symbol or config.trading.default_symbol
        self.timeframes = timeframes or config.trading.timeframes
        self.exchange_name = config.exchange.name.lower()
        
        # Initialize exchange - support both CCXT and custom clients
        if self.exchange_name == 'bitunix':
            logger.info("Using custom Bitunix client")
            self.exchange = BitunixClient(
                api_key=config.exchange.api_key,
                api_secret=config.exchange.api_secret,
                sandbox=config.exchange.paper_trading
            )
            self.is_bitunix = True
            
            if config.exchange.paper_trading:
                logger.info("Market Monitor initialized in PAPER TRADING mode (Bitunix)")
        else:
            logger.info(f"Using CCXT for exchange: {config.exchange.name}")
            try:
                exchange_class = getattr(ccxt, config.exchange.name)
                self.exchange = exchange_class({
                    'apiKey': config.exchange.api_key,
                    'secret': config.exchange.api_secret,
                    'enableRateLimit': True,
                    'options': {
                        'defaultType': 'future' if config.exchange.paper_trading else 'spot',
                    }
                })
                
                if config.exchange.paper_trading:
                    self.exchange.set_sandbox_mode(True)
                    logger.info("Market Monitor initialized in PAPER TRADING mode")
                    
                self.is_bitunix = False
            except AttributeError:
                logger.error(
                    f"Exchange '{config.exchange.name}' not supported by CCXT. "
                    "Please use 'bitunix' or another CCXT-supported exchange."
                )
                raise ValueError(f"Unsupported exchange: {config.exchange.name}")
        
        # In-memory cache for recent candles
        self.cache: Dict[str, pd.DataFrame] = {}
        
        logger.info(
            "Market Monitor initialized",
            symbol=self.symbol,
            timeframes=self.timeframes,
            exchange=config.exchange.name,
            is_custom_client=self.is_bitunix
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
                limit=limit
            )
            
            # Fetch from exchange
            ohlcv = self.exchange.fetch_ohlcv(
                symbol=self.symbol,
                timeframe=timeframe,
                limit=limit
            )
            
            # Update cache
            self.cache[timeframe] = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            
            # Create MarketData object
            market_data = MarketData(
                symbol=self.symbol,
                timeframe=Timeframe(timeframe),
                timestamp=datetime.now(),
                ohlcv=ohlcv
            )
            
            logger.debug(
                "OHLCV data fetched successfully",
                symbol=self.symbol,
                timeframe=timeframe,
                candles=len(ohlcv)
            )
            
            return market_data
            
        except Exception as e:
            logger.error(
                "Error fetching OHLCV data",
                symbol=self.symbol,
                timeframe=timeframe,
                error=str(e)
            )
            raise
    
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
                    "Failed to fetch timeframe data",
                    timeframe=timeframe,
                    error=str(e)
                )
                # Continue with other timeframes
                continue
        
        logger.info(
            "Fetched all timeframes",
            symbol=self.symbol,
            successful_timeframes=len(result),
            total_timeframes=len(self.timeframes)
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
            if self.is_bitunix:
                ticker = self.exchange.fetch_ticker(self.symbol)
                return ticker['last']
            else:
                ticker = self.exchange.fetch_ticker(self.symbol)
                return ticker['last']
        except Exception as e:
            logger.error("Error fetching latest price", error=str(e))
            raise
