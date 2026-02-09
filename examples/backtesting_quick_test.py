#!/usr/bin/env python3
"""Quick test script to start BacktestEngine."""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.backtesting import BacktestEngine


def main():
    engine = BacktestEngine()
    signals = engine.run(
        symbol="BTC/USDT",
        days=60,
        timeframes=["1d", "4h", "15m"],
        use_mock_ai=True,
        plot_timeframe="1d",
    )

    print(f"Signals found: {len(signals)}")
    if signals:
        engine.plot_all_signals(signals, before=15, after=15)


if __name__ == "__main__":
    main()
