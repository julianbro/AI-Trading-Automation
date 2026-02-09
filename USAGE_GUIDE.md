# Usage Guide - AI Trading Automation System

## Quick Start

### 1. Installation

```bash
# Clone repository
git clone https://github.com/julianbro/AI-Trading-Automation.git
cd AI-Trading-Automation

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### 2. Configuration

Edit `.env` file with your settings:

```env
# Exchange Configuration
EXCHANGE_API_KEY=your_api_key_here
EXCHANGE_API_SECRET=your_api_secret_here
EXCHANGE_NAME=binance

# LLM Configuration  
OPENAI_API_KEY=your_openai_api_key_here
LLM_MODEL=gpt-4
LLM_TEMPERATURE=0.1

# Trading Configuration
PAPER_TRADING=true  # Start with paper trading!
DEFAULT_SYMBOL=BTC/USDT
TIMEFRAMES=1d,4h,15m,5m

# Risk Management
MAX_TRADES_PER_DAY=5
MAX_RISK_PER_DAY=10.0
MAX_DRAWDOWN=20.0
COOLDOWN_AFTER_LOSSES=3
```

### 4. Backtesting (Monitoring Focus)

Simulate day-by-day setup detection over the last N days and plot signals:

```python
from src.backtesting import BacktestEngine

engine = BacktestEngine()
signals = engine.run(
   symbol="BTC/USDT",
   days=60,
   timeframes=["1d", "4h", "15m"],
   use_mock_ai=True,  # set to False to use real AI
   plot_timeframe="1d",
)

print(f"Signals: {len(signals)}")
if signals:
   engine.plot_signal(signals[0], before=15, after=15)
```

Notes:
- Requires `1d` in `timeframes` to simulate day-by-day.
- `use_mock_ai=True` avoids external AI calls.
- Plots show entry/SL/TP lines when available.

### 3. Run Examples

**Paper Trading:**
```bash
python examples/paper_trading_example.py
```

**Setup Detection Only:**
```bash
python examples/setup_detection_example.py
```

## Component Usage

### Market Monitor

Fetch market data from exchanges:

```python
from src.market_monitor import MarketMonitor

# Initialize
monitor = MarketMonitor(
    symbol="BTC/USDT",
    timeframes=["1d", "4h", "15m"]
)

# Fetch data for all timeframes
market_data = monitor.fetch_all_timeframes(limit=100)

# Fetch specific timeframe
data_1d = monitor.fetch_ohlcv("1d", limit=50)

# Get latest price
price = monitor.get_latest_price()
```

### Rule Engine

Detect trading setups:

```python
from src.rule_engine import RuleEngine

# Initialize
engine = RuleEngine()

# Detect setups from market data
setups = engine.detect_setups(market_data)

for setup in setups:
    print(f"Pattern: {setup.pattern_type}")
    print(f"Symbol: {setup.symbol}")
    print(f"Context: {setup.context_data}")
```

**Supported Patterns:**
- `BREAKOUT_RETEST` - Price breaks resistance, retests, confirms
- `SUPPORT_BOUNCE` - Price bounces from support with rejection

### AI Decision Engine

Validate setups with LLM:

```python
from src.ai_decision import AIDecisionEngine

# Initialize
ai_engine = AIDecisionEngine()

# Validate a setup
decision = ai_engine.validate_setup(setup, market_data)

print(f"Decision: {decision.decision}")  # TRADE, NO_TRADE, WAIT
print(f"Confidence: {decision.confidence}")  # LOW, MID, HIGH
print(f"Reason: {decision.reason_code}")

# Handle WAIT decision
if decision.decision == "WAIT" and decision.next_check:
    print(f"Re-check: {decision.next_check.type} - {decision.next_check.value}")
```

**AI Output:**
- `TRADE` - Setup approved, ready to execute
- `NO_TRADE` - Setup rejected
- `WAIT` - Needs confirmation, re-check later

**Confidence Levels:**
- `HIGH` - All timeframes align, clean structure
- `MID` - Good setup with minor concerns
- `LOW` - Marginal setup

### Execution & Risk Engine

Execute trades with risk management:

```python
from src.execution_risk import ExecutionRiskEngine

# Initialize
exec_engine = ExecutionRiskEngine(account_balance=10000.0)

# Check if trade should be executed
if exec_engine.should_execute_trade(ai_decision):
    # Create order
    order = exec_engine.create_trade_order(
        setup,
        ai_decision,
        current_price
    )
    
    # Execute order
    trade = exec_engine.execute_order(order)
    print(f"Trade executed: {trade.trade_id}")
```

**Risk Mapping:**
```python
AI Confidence → Risk Amount
LOW  → 0.5R (0.5% of account)
MID  → 1.0R (1.0% of account)
HIGH → 2.0R (2.0% of account)
```

**Safety Checks:**
- Max trades per day
- Max risk per day
- Consecutive loss cooldown
- Max drawdown protection

### Trade Monitor

Monitor open trades:

```python
from src.trade_monitoring import TradeMonitor

# Initialize
monitor = TradeMonitor(exec_engine)

# Add trade to monitoring
monitor.add_trade(trade)

# Check trades against current prices
current_prices = {"BTC/USDT": 50000}
monitor.check_trades(current_prices)

# Get open trades
open_trades = monitor.get_open_trades()
```

**Monitoring:**
- Automatic SL/TP execution
- No trailing stops
- No manual intervention
- No AI during trade

### Complete Trading System

Use the orchestrator:

```python
from src.trading_system import TradingSystem

# Initialize
system = TradingSystem(
    symbol="BTC/USDT",
    timeframes=["1d", "4h", "15m", "5m"],
    account_balance=10000.0
)

# Run single cycle
system.run_cycle()

# Run continuous trading
system.run_continuous(interval_seconds=60)

# Get statistics
stats = system.get_statistics()
print(f"Win Rate: {stats['win_rate']:.2%}")
print(f"Total P&L: ${stats['total_pnl']:.2f}")
print(f"Account Balance: ${stats['account_balance']:.2f}")
```

## Trading Flow

```
1. Market Monitor fetches OHLCV data
   ↓
2. Rule Engine detects setups (deterministic)
   ↓
3. AI validates setup quality (advisory)
   ↓
4. Execution Engine checks risk rules
   ↓
5. Trade is executed (if approved)
   ↓
6. Trade Monitor watches for SL/TP
```

## WAIT/Re-evaluation Flow

When AI returns WAIT:

1. Setup is stored with timestamp
2. Re-check scheduled (time or event-based)
3. Limited to 5 re-checks
4. Same validation process
5. Eventually becomes TRADE or NO_TRADE

## Logging

All actions are logged to `trading_system.log`:

```json
{
  "event": "setup_detected",
  "event_id": "abc-123",
  "pattern_type": "breakout_retest",
  "symbol": "BTC/USDT",
  "timestamp": "2024-01-01T12:00:00"
}

{
  "event": "ai_validation",
  "event_id": "abc-123",
  "decision": "TRADE",
  "confidence": "HIGH",
  "reason_code": "CLEAN_SETUP"
}

{
  "event": "trade_executed",
  "trade_id": "xyz-456",
  "symbol": "BTC/USDT",
  "entry_price": 50000,
  "stop_loss": 49000,
  "take_profit": 52000
}
```

## Safety Features

### Hard-Coded Limits (Never AI-Controlled)

1. **Max Trades Per Day**: Prevents overtrading
2. **Max Risk Per Day**: Caps daily exposure
3. **Max Drawdown**: Stops system if threshold reached
4. **Cooldown Period**: Pauses after consecutive losses

### Risk Checks Before Every Trade

```python
✓ Daily trade limit not exceeded
✓ Daily risk limit not exceeded
✓ Not in cooldown period
✓ AI approved (TRADE decision)
✓ Position sizing calculated
✓ SL/TP levels set
```

## Best Practices

### Starting Out

1. **Always start with paper trading**
   - Set `PAPER_TRADING=true`
   - Test for at least 2 weeks
   - Verify all components work

2. **Start with conservative settings**
   - Max 2-3 trades per day
   - Max 5% daily risk
   - Use only HIGH confidence trades

3. **Monitor closely**
   - Check logs regularly
   - Review all trades
   - Understand AI decisions

### Going Live

1. **Gradual transition**
   - Start with small account
   - Increase slowly
   - Never risk more than you can lose

2. **Regular reviews**
   - Daily: Check open trades, logs
   - Weekly: Review statistics, win rate
   - Monthly: Assess overall performance

3. **Risk management**
   - Never exceed max drawdown
   - Respect cooldown periods
   - Trust the safety limits

## Troubleshooting

### Common Issues

**Issue: No setups detected**
- Market may not have suitable patterns
- Try different timeframes
- Adjust detection rules

**Issue: AI always returns NO_TRADE**
- Market conditions may be choppy
- Check LLM configuration
- Review AI prompt settings

**Issue: Trades not executing**
- Check daily limits
- Verify account balance
- Check if in cooldown

**Issue: API errors**
- Verify API keys in .env
- Check API rate limits
- Ensure sufficient permissions

### Debug Mode

Enable debug logging:

```env
LOG_LEVEL=DEBUG
```

This provides detailed information about:
- Market data fetching
- Setup detection logic
- AI input/output
- Risk calculations
- Order execution

## Advanced Usage

### Custom Patterns

Add new patterns to `rule_engine.py`:

```python
def _check_custom_pattern(self, market_data):
    # Your pattern logic here
    # Must return SetupEvent or None
    pass
```

### Custom Risk Mapping

Modify risk mapping in `.env` or code:

```python
config.risk.risk_mapping = {
    "LOW": 0.25,
    "MID": 0.5,
    "HIGH": 1.0,
}
```

### Multiple Symbols

Run separate instances:

```python
btc_system = TradingSystem(symbol="BTC/USDT")
eth_system = TradingSystem(symbol="ETH/USDT")

# Run in parallel (separate threads)
```

## Support

- GitHub Issues: https://github.com/julianbro/AI-Trading-Automation/issues
- Documentation: README.md
- Examples: examples/ directory

## Warning

⚠️ **Trading involves significant risk**

- Start with paper trading
- Never risk money you can't afford to lose
- The AI is advisory only
- Past performance doesn't guarantee future results
- You are responsible for all trades
