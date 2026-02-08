#!/usr/bin/env python3
"""
Example: Basic Paper Trading

This example demonstrates a basic paper trading setup with the AI Trading System.
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.trading_system import TradingSystem


def main():
    """Run basic paper trading example."""
    print("=" * 60)
    print("AI Trading Automation - Paper Trading Example")
    print("=" * 60)
    print()
    
    # Initialize trading system
    print("Initializing trading system...")
    system = TradingSystem(
        symbol="BTC/USDT",
        timeframes=["1d", "4h", "15m", "5m"],
        account_balance=10000.0
    )
    
    print("\nTrading system initialized successfully!")
    print(f"Symbol: BTC/USDT")
    print(f"Timeframes: 1d, 4h, 15m, 5m")
    print(f"Account Balance: $10,000")
    print(f"Mode: PAPER TRADING")
    print()
    
    # Run a single cycle
    print("Running single trading cycle...")
    print("-" * 60)
    system.run_cycle()
    print("-" * 60)
    print()
    
    # Display statistics
    stats = system.get_statistics()
    print("Trading Statistics:")
    print(f"  Total Trades: {stats['total_trades']}")
    print(f"  Open Trades: {stats['open_trades']}")
    print(f"  Closed Trades: {stats['closed_trades']}")
    print(f"  Win Rate: {stats['win_rate']:.2%}")
    print(f"  Total P&L: ${stats['total_pnl']:.2f}")
    print(f"  Account Balance: ${stats['account_balance']:.2f}")
    print(f"  Daily Trades: {stats['daily_trades']}")
    print(f"  Daily Risk Used: {stats['daily_risk_used']:.2f}%")
    print()
    
    # Ask user if they want to continue with continuous trading
    response = input("Run continuous trading? (y/n): ")
    if response.lower() == 'y':
        interval = int(input("Enter interval in seconds (e.g., 60): ") or 60)
        print(f"\nStarting continuous trading (interval: {interval}s)...")
        print("Press Ctrl+C to stop")
        print()
        system.run_continuous(interval_seconds=interval)
    else:
        print("\nPaper trading example complete!")


if __name__ == "__main__":
    main()
