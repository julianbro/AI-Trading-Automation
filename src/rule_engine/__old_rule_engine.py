"""
Rule Engine - Setup Detection.

This component is responsible for:
- Checking hard, deterministic rules
- Recognizing defined trading setups
- No trade decisions, only setup detection
- 100% deterministic, boolean logic
"""

import uuid
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime
import structlog

from src.common.models import MarketData, SetupEvent, PatternType, Timeframe
from src.config import config

logger = structlog.get_logger(__name__)


class RuleEngine:
    """
    Rule Engine for setup detection.

    Applies deterministic rules to identify trading setups.
    """

    def __init__(self):
        """Initialize Rule Engine."""
        logger.info("Rule Engine initialized")

    def detect_setups(self, market_data: Dict[str, MarketData]) -> List[SetupEvent]:
        """
        Detect trading setups from market data.

        Args:
            market_data: Dictionary of timeframe -> MarketData

        Returns:
            List of detected SetupEvents
        """
        if self._has_open_htf_bar(market_data):
            logger.info("Skipping setup detection: HTF bar not closed")
            return []

        setups = []

        # Check for breakout retest pattern
        breakout_setup = self._check_breakout_retest(market_data)
        if breakout_setup:
            setups.append(breakout_setup)

        # Check for support bounce pattern
        support_setup = self._check_support_bounce(market_data)
        if support_setup:
            setups.append(support_setup)

        logger.info(f"Detected {len(setups)} setups", setup_count=len(setups))
        return setups

    def _has_open_htf_bar(self, market_data: Dict[str, MarketData]) -> bool:
        """
        Check if any higher timeframe bar is still open.

        Args:
            market_data: Dictionary of timeframe -> MarketData

        Returns:
            True if any HTF bar is open, False otherwise
        """
        for timeframe in ("1d", "4h"):
            data = market_data.get(timeframe)
            if data is not None and not data.is_closed:
                return True
        return False

    def _check_breakout_retest(
        self, market_data: Dict[str, MarketData]
    ) -> Optional[SetupEvent]:
        """
        Check for breakout retest pattern.

        Rules:
        1. Price breaks above resistance on higher timeframe
        2. Price pulls back to resistance (now support)
        3. Price shows bullish confirmation on lower timeframe
        4. ATR is above minimum threshold

        Args:
            market_data: Dictionary of timeframe -> MarketData

        Returns:
            SetupEvent if pattern is detected, None otherwise
        """
        try:
            # Need at least 1d and 15m data
            if "1d" not in market_data or "15m" not in market_data:
                return None

            daily_data = market_data["1d"]
            intraday_data = market_data["15m"]

            # Convert to DataFrame for easier analysis
            daily_df = pd.DataFrame(
                daily_data.ohlcv,
                columns=["timestamp", "open", "high", "low", "close", "volume"],
            )
            intraday_df = pd.DataFrame(
                intraday_data.ohlcv,
                columns=["timestamp", "open", "high", "low", "close", "volume"],
            )

            if len(daily_df) < 20 or len(intraday_df) < 20:
                return None

            # Calculate resistance level (previous high)
            resistance = daily_df["high"].iloc[-20:-1].max()

            # Check if current price broke above resistance recently
            current_price = daily_df["close"].iloc[-1]
            recent_high = daily_df["high"].iloc[-5:].max()

            if recent_high <= resistance:
                return None  # No breakout

            # Check for pullback to resistance (now support)
            pullback_range_min = resistance * 0.98  # Allow 2% tolerance
            pullback_range_max = resistance * 1.02

            if not (pullback_range_min <= current_price <= pullback_range_max):
                return None  # Not in retest zone

            # Check for bullish confirmation on lower timeframe
            last_candle = intraday_df.iloc[-1]
            candle_close_above_resistance = last_candle["close"] > resistance

            if not candle_close_above_resistance:
                return None  # No confirmation

            # Calculate ATR (simplified)
            daily_df["tr"] = daily_df[["high", "low"]].apply(
                lambda x: x["high"] - x["low"], axis=1
            )
            atr = daily_df["tr"].iloc[-14:].mean()
            min_atr = current_price * 0.01  # Minimum 1% ATR

            if atr < min_atr:
                return None  # Insufficient volatility

            # Setup detected!
            setup_event = SetupEvent(
                event_id=str(uuid.uuid4()),
                symbol=daily_data.symbol,
                pattern_type=PatternType.BREAKOUT_RETEST,
                timestamp=datetime.now(),
                timeframes=[Timeframe.ONE_DAY, Timeframe.FIFTEEN_MIN],
                context_data={
                    "levels": {
                        "resistance": float(resistance),
                        "current_price": float(current_price),
                        "atr": float(atr),
                    },
                    "trigger_price": float(resistance),
                    "confirmation": "bullish_candle_close",
                },
            )

            logger.info(
                "Breakout retest setup detected",
                event_id=setup_event.event_id,
                symbol=setup_event.symbol,
                resistance=resistance,
                current_price=current_price,
            )

            return setup_event

        except Exception as e:
            logger.error("Error checking breakout retest pattern", error=str(e))
            return None

    def _check_support_bounce(
        self, market_data: Dict[str, MarketData]
    ) -> Optional[SetupEvent]:
        """
        Check for support bounce pattern.

        Rules:
        1. Price approaches a known support level
        2. Price shows bullish rejection (long lower wick)
        3. Price closes above support

        Args:
            market_data: Dictionary of timeframe -> MarketData

        Returns:
            SetupEvent if pattern is detected, None otherwise
        """
        try:
            # Need at least 4h data
            if "4h" not in market_data:
                return None

            data = market_data["4h"]
            df = pd.DataFrame(
                data.ohlcv,
                columns=["timestamp", "open", "high", "low", "close", "volume"],
            )

            if len(df) < 20:
                return None

            # Calculate support level (previous low)
            support = df["low"].iloc[-20:-1].min()

            # Check if current price is near support
            current_price = df["close"].iloc[-1]
            last_candle = df.iloc[-1]

            support_zone_min = support * 0.98
            support_zone_max = support * 1.02

            if not (support_zone_min <= current_price <= support_zone_max):
                return None  # Not in support zone

            # Check for bullish rejection (long lower wick)
            candle_body = abs(last_candle["close"] - last_candle["open"])
            lower_wick = (
                min(last_candle["open"], last_candle["close"]) - last_candle["low"]
            )

            if lower_wick < candle_body * 1.5:
                return None  # Wick not long enough

            # Check close above support
            if last_candle["close"] < support:
                return None  # Closed below support

            # Setup detected!
            setup_event = SetupEvent(
                event_id=str(uuid.uuid4()),
                symbol=data.symbol,
                pattern_type=PatternType.SUPPORT_BOUNCE,
                timestamp=datetime.now(),
                timeframes=[Timeframe.FOUR_HOURS],
                context_data={
                    "levels": {
                        "support": float(support),
                        "current_price": float(current_price),
                        "lower_wick_length": float(lower_wick),
                    },
                    "trigger_price": float(support),
                    "confirmation": "bullish_rejection",
                },
            )

            logger.info(
                "Support bounce setup detected",
                event_id=setup_event.event_id,
                symbol=setup_event.symbol,
                support=support,
                current_price=current_price,
            )

            return setup_event

        except Exception as e:
            logger.error("Error checking support bounce pattern", error=str(e))
            return None
