#!/usr/bin/env python3
"""
Example: Single Setup Detection

This example demonstrates how to use individual components
to detect and validate a single setup.
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.market_monitor import MarketMonitor
from src.rule_engine import RuleEngine
from src.ai_decision import AIDecisionEngine


def main():
    """Run single setup detection example."""
    print("=" * 60)
    print("AI Trading Automation - Setup Detection Example")
    print("=" * 60)
    print()
    
    # Initialize components
    print("Initializing components...")
    market_monitor = MarketMonitor(
        symbol="BTC/USDT",
        timeframes=["1d", "4h", "15m"]
    )
    rule_engine = RuleEngine()
    ai_engine = AIDecisionEngine()
    
    print("Components initialized!")
    print()
    
    # Step 1: Fetch market data
    print("Step 1: Fetching market data...")
    market_data = market_monitor.fetch_all_timeframes(limit=50)
    print(f"  Fetched data for {len(market_data)} timeframes")
    print()
    
    # Step 2: Detect setups
    print("Step 2: Detecting setups...")
    setups = rule_engine.detect_setups(market_data)
    print(f"  Detected {len(setups)} setup(s)")
    print()
    
    if not setups:
        print("No setups detected. Try again later!")
        return
    
    # Step 3: Validate with AI
    print("Step 3: Validating setups with AI...")
    
    # Get current price for AI validation
    current_price = market_monitor.get_latest_price()
    print(f"Current Price: ${current_price:.2f}")
    
    for i, setup in enumerate(setups, 1):
        print(f"\n  Setup {i}:")
        print(f"    Pattern: {setup.pattern_type}")
        print(f"    Symbol: {setup.symbol}")
        print(f"    Timeframes: {', '.join(str(tf) for tf in setup.timeframes)}")
        
        # Get AI decision with SL/TP
        ai_decision = ai_engine.validate_setup(setup, market_data, current_price)
        
        print(f"    AI Decision: {ai_decision.decision}")
        print(f"    Confidence: {ai_decision.confidence}")
        print(f"    Reason: {ai_decision.reason_code}")
        
        # Show AI-defined trade parameters for TRADE decisions
        if ai_decision.decision.value == "TRADE":
            print(f"\n    📊 AI-Defined Trade Parameters:")
            print(f"      Entry Price: ${ai_decision.entry_price or current_price:.2f}")
            print(f"      Stop Loss: ${ai_decision.stop_loss:.2f}")
            print(f"      Take Profit: ${ai_decision.take_profit:.2f}")
            print(f"      Side: {ai_decision.side.upper()}")
            
            # Calculate and show R:R
            entry = ai_decision.entry_price or current_price
            risk = abs(entry - ai_decision.stop_loss)
            reward = abs(ai_decision.take_profit - entry)
            rr_ratio = reward / risk if risk > 0 else 0
            print(f"      Risk/Reward: 1:{rr_ratio:.2f}")
        
        if ai_decision.next_check:
            print(f"    Next Check: {ai_decision.next_check.type} - {ai_decision.next_check.value}")
    
    print()
    print("Setup detection complete!")


if __name__ == "__main__":
    main()
