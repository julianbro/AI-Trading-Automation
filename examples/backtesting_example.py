#!/usr/bin/env python3
"""
Example: Backtesting (Monitoring Focus)

Simulates historical day-by-day setup detection and AI validation.
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.backtesting import BacktestEngine


def main():
    print("=" * 60)
    print("AI Trading Automation - Backtesting Example")
    print("=" * 60)
    print()

    engine = BacktestEngine()

    signals = engine.run(
        symbol="BTC/USDT",
        days=60,
        timeframes=["1d", "4h", "15m"],
        use_mock_ai=True,
        plot_timeframe="1d",
    )

    print(f"Signals found: {len(signals)}")
    for i, s in enumerate(signals[:5], 1):
        print(
            f"{i}. {s.timestamp.date()} | {s.pattern_type.value} | {s.decision.value} | {s.reason_code}"
        )

    if signals:
        print("\nPlotting first signal...")
        engine.plot_signal(signals[0], before=15, after=15)


if __name__ == "__main__":
    main()
