"""
Backtesting Engine.

This component simulates historical day-by-day setup detection and AI validation.
Focus is on monitoring signals, not performance metrics (PnL added later).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import structlog
import matplotlib.pyplot as plt

from src.common.models import (
    MarketData,
    SetupEvent,
    PatternType,
    AIDecisionOutput,
    AIDecision,
    AIConfidence,
    Timeframe,
)
from src.market_monitor import MarketMonitor
from src.rule_engine import RuleEngine
from src.ai_decision import AIDecisionEngine

logger = structlog.get_logger(__name__)


_CANDLES_PER_DAY = {
    "1d": 1,
    "4h": 6,
    "1h": 24,
    "30m": 48,
    "15m": 96,
    "5m": 288,
}


@dataclass
class BacktestSignal:
    """Backtest signal record for monitoring and plotting."""

    timestamp: datetime
    symbol: str
    pattern_type: PatternType
    decision: AIDecision
    confidence: AIConfidence
    reason_code: str
    entry_price: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    side: Optional[str]
    plot_timeframe: str
    plot_ohlcv: List[List[float]]
    plot_index: int


class MockAIDecisionEngine:
    """Deterministic AI mock for backtesting without external calls."""

    def validate_setup(
        self,
        setup: SetupEvent,
        market_data: Dict[str, MarketData],
        current_price: float,
    ) -> AIDecisionOutput:
        levels = setup.context_data.get("levels", {}) if setup.context_data else {}
        decision = AIDecisionOutput(
            decision=AIDecision.NO_TRADE,
            confidence=AIConfidence.LOW,
            reason_code="MOCK_NO_TRADE",
        )

        if setup.pattern_type == PatternType.BREAKOUT_RETEST:
            resistance = levels.get("resistance")
            if resistance:
                entry = current_price
                stop_loss = resistance * 0.99
                take_profit = entry + (entry - stop_loss) * 2
                decision = self._build_trade(entry, stop_loss, take_profit, "buy")
        elif setup.pattern_type == PatternType.SUPPORT_BOUNCE:
            support = levels.get("support")
            if support:
                entry = current_price
                stop_loss = support * 0.99
                take_profit = entry + (entry - stop_loss) * 2
                decision = self._build_trade(entry, stop_loss, take_profit, "buy")

        return decision

    def _build_trade(
        self, entry: float, stop_loss: float, take_profit: float, side: str
    ) -> AIDecisionOutput:
        sl_distance_pct = abs(entry - stop_loss) / entry * 100
        if sl_distance_pct < 0.1 or sl_distance_pct > 10:
            return AIDecisionOutput(
                decision=AIDecision.NO_TRADE,
                confidence=AIConfidence.LOW,
                reason_code="MOCK_INVALID_SL",
            )

        rr = (
            abs(take_profit - entry) / abs(entry - stop_loss)
            if abs(entry - stop_loss) > 0
            else 0
        )
        if rr < 1.0:
            return AIDecisionOutput(
                decision=AIDecision.NO_TRADE,
                confidence=AIConfidence.LOW,
                reason_code="MOCK_POOR_RR",
            )

        return AIDecisionOutput(
            decision=AIDecision.TRADE,
            confidence=AIConfidence.MID,
            reason_code="MOCK_TRADE",
            entry_price=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            side=side,
        )


class BacktestEngine:
    """Backtesting engine for monitoring signal behavior over past days."""

    def __init__(self):
        self.rule_engine = RuleEngine()

    def run(
        self,
        symbol: str,
        days: int,
        timeframes: List[str],
        use_mock_ai: bool = True,
        plot_timeframe: str = "1d",
        lookback_candles: int = 50,
    ) -> List[BacktestSignal]:
        """
        Run a day-by-day backtest over the last N days.

        Args:
            symbol: Trading symbol (e.g., "BTC/USDT")
            days: Number of days to simulate
            timeframes: List of timeframes to include
            use_mock_ai: If True, use mock AI; otherwise use real AI
            plot_timeframe: Timeframe used for plotting
            lookback_candles: Extra candles needed for setup detection

        Returns:
            List of BacktestSignal objects
        """
        if "1d" not in timeframes:
            raise ValueError("Backtest requires '1d' timeframe to simulate day-by-day")
        if plot_timeframe not in timeframes:
            raise ValueError("Plot timeframe must be included in timeframes")
        for timeframe in timeframes:
            try:
                Timeframe(timeframe)
            except ValueError as exc:
                raise ValueError(
                    "Unsupported timeframe for backtest (must be one of: 1d, 4h, 15m, 5m)"
                ) from exc

        market_monitor = MarketMonitor(symbol=symbol, timeframes=timeframes)
        ai_engine = MockAIDecisionEngine() if use_mock_ai else AIDecisionEngine()

        logger.info(
            "Starting backtest",
            symbol=symbol,
            days=days,
            timeframes=timeframes,
            use_mock_ai=use_mock_ai,
            plot_timeframe=plot_timeframe,
        )

        # Fetch historical data for all timeframes
        all_data: Dict[str, List[List[float]]] = {}
        for timeframe in timeframes:
            candles_per_day = _CANDLES_PER_DAY.get(timeframe)
            if not candles_per_day:
                raise ValueError(f"Unsupported timeframe: {timeframe}")
            limit = days * candles_per_day + lookback_candles
            data = market_monitor.fetch_ohlcv(timeframe, limit=limit)
            all_data[timeframe] = data.ohlcv

        daily_candles = all_data["1d"]
        if len(daily_candles) < days:
            raise ValueError("Not enough daily candles for requested backtest period")

        start_index = max(0, len(daily_candles) - days)
        signals: List[BacktestSignal] = []

        for day_idx in range(start_index, len(daily_candles)):
            current_ts = daily_candles[day_idx][0]

            snapshot: Dict[str, MarketData] = {}
            for timeframe, candles in all_data.items():
                tf_slice = [c for c in candles if c[0] <= current_ts]
                if len(tf_slice) < 20:
                    continue
                snapshot[timeframe] = MarketData(
                    symbol=symbol,
                    timeframe=Timeframe(timeframe),
                    timestamp=datetime.fromtimestamp(current_ts / 1000),
                    ohlcv=tf_slice,
                    is_closed=True,
                )

            if not snapshot:
                continue

            setups = self.rule_engine.detect_setups(snapshot)
            if not setups:
                continue

            current_price = daily_candles[day_idx][4]

            for setup in setups:
                decision = ai_engine.validate_setup(setup, snapshot, current_price)
                plot_data = snapshot.get(plot_timeframe)
                if not plot_data:
                    continue

                signals.append(
                    BacktestSignal(
                        timestamp=datetime.fromtimestamp(current_ts / 1000),
                        symbol=symbol,
                        pattern_type=setup.pattern_type,
                        decision=decision.decision,
                        confidence=decision.confidence,
                        reason_code=decision.reason_code,
                        entry_price=decision.entry_price,
                        stop_loss=decision.stop_loss,
                        take_profit=decision.take_profit,
                        side=decision.side,
                        plot_timeframe=plot_timeframe,
                        plot_ohlcv=plot_data.ohlcv,
                        plot_index=len(plot_data.ohlcv) - 1,
                    )
                )

        logger.info("Backtest complete", signal_count=len(signals))
        return signals

    def plot_signal(
        self,
        signal: BacktestSignal,
        before: int = 20,
        after: int = 20,
        save_path: Optional[str] = None,
    ) -> None:
        """
        Plot price action around a chosen signal.

        Args:
            signal: BacktestSignal to plot
            before: Candles before the signal
            after: Candles after the signal
            save_path: Optional file path to save the figure
        """
        ohlcv = signal.plot_ohlcv
        idx = signal.plot_index
        start = max(0, idx - before)
        end = min(len(ohlcv), idx + after + 1)

        window = ohlcv[start:end]
        times = [datetime.fromtimestamp(c[0] / 1000) for c in window]

        plt.figure(figsize=(12, 6))

        # Candlestick rendering (no external deps)
        for i, candle in enumerate(window):
            _, open_p, high_p, low_p, close_p, _ = candle
            color = "#2ca02c" if close_p >= open_p else "#d62728"
            # High-low line
            plt.vlines(i, low_p, high_p, color=color, linewidth=1)
            # Body
            body_bottom = min(open_p, close_p)
            body_height = max(abs(close_p - open_p), 1e-9)
            plt.bar(
                i,
                body_height,
                bottom=body_bottom,
                width=0.6,
                color=color,
                edgecolor=color,
                align="center",
            )

        # Signal marker
        signal_x = idx - start
        plt.axvline(signal_x, color="orange", linestyle="--", label="Signal")

        # X-axis labels
        xtick_positions = list(range(0, len(times), max(1, len(times) // 6)))
        xtick_labels = [times[i].strftime("%Y-%m-%d") for i in xtick_positions]
        plt.xticks(xtick_positions, xtick_labels, rotation=30, ha="right")

        if signal.entry_price:
            plt.axhline(signal.entry_price, color="blue", linestyle=":", label="Entry")
        if signal.stop_loss:
            plt.axhline(signal.stop_loss, color="red", linestyle=":", label="Stop Loss")
        if signal.take_profit:
            plt.axhline(
                signal.take_profit, color="green", linestyle=":", label="Take Profit"
            )

        plt.title(
            f"{signal.symbol} {signal.pattern_type.value} | {signal.decision.value} | {signal.plot_timeframe}"
        )
        plt.xlabel("Time")
        plt.ylabel("Price")
        plt.legend()
        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=150)
            plt.close()
        else:
            plt.show()

    def plot_all_signals(
        self,
        signals: List[BacktestSignal],
        before: int = 20,
        after: int = 20,
        output_dir: str = ".",
        prefix: str = "signal",
    ) -> List[str]:
        """
        Plot and save all signals to the specified directory.

        Args:
            signals: List of BacktestSignal objects
            before: Candles before the signal
            after: Candles after the signal
            output_dir: Directory to store figures (default: current directory)
            prefix: Filename prefix

        Returns:
            List of saved file paths
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        saved_files: List[str] = []
        for idx, signal in enumerate(signals, 1):
            filename = (
                f"{prefix}_{idx:03d}_{signal.symbol.replace('/', '-')}_"
                f"{signal.pattern_type.value}_{signal.timestamp.strftime('%Y%m%d')}.png"
            )
            save_path = output_path / filename
            self.plot_signal(
                signal, before=before, after=after, save_path=str(save_path)
            )
            saved_files.append(str(save_path))

        return saved_files
