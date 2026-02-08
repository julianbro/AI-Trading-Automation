# Architecture Documentation

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      AI Trading System                           │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   Market Monitor                          │  │
│  │  - Fetches OHLCV data from exchanges                      │  │
│  │  - Manages multiple timeframes (1d, 4h, 15m, 5m)         │  │
│  │  - Pure data provider (no logic)                          │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │                                          │
│                       ▼                                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   Rule Engine                             │  │
│  │  - Deterministic setup detection                          │  │
│  │  - Boolean logic (100% reproducible)                      │  │
│  │  - Patterns: Breakout Retest, Support Bounce             │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │                                          │
│                       ▼                                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              AI Decision Engine (LLM)                     │  │
│  │  - Qualitative setup validation                           │  │
│  │  - Advisory role only                                     │  │
│  │  - Output: TRADE / NO_TRADE / WAIT                        │  │
│  │  - Confidence: LOW / MID / HIGH                           │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │                                          │
│                       ▼                                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │           Execution & Risk Engine                         │  │
│  │  - Mechanical trade execution                             │  │
│  │  - Fixed risk rules (no AI influence)                     │  │
│  │  - Risk mapping: LOW=0.5R, MID=1.0R, HIGH=2.0R          │  │
│  │  - Safety: Max trades, max risk, cooldown               │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │                                          │
│                       ▼                                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                Trade Monitor                              │  │
│  │  - Monitors open trades                                   │  │
│  │  - Executes SL/TP automatically                          │  │
│  │  - No trailing, no AI intervention                        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

### 1. Market Monitor
**Purpose:** Data acquisition
- Connects to exchange via ccxt
- Fetches OHLCV (Open, High, Low, Close, Volume)
- Caches recent candles
- No trading logic

**Output:** MarketData objects

### 2. Rule Engine
**Purpose:** Pattern recognition
- Applies deterministic rules
- Detects trading setups
- 100% reproducible
- No ML, no probabilities

**Input:** MarketData
**Output:** SetupEvent objects

**Patterns Implemented:**
- Breakout Retest
- Support Bounce

### 3. AI Decision Engine
**Purpose:** Setup quality assessment
- Validates detected setups
- Checks timeframe alignment
- Assesses market structure
- Can request additional confirmation (WAIT)

**Input:** SetupEvent + MarketData
**Output:** AIDecisionOutput (TRADE/NO_TRADE/WAIT + confidence + reason)

**AI Constraints:**
- Cannot set prices
- Cannot determine position sizes
- Cannot set SL/TP levels
- Advisory role only

### 4. Execution & Risk Engine
**Purpose:** Trade execution with risk management
- Creates trade orders
- Calculates position sizes
- Sets SL/TP levels
- Enforces safety limits

**Risk Mapping:**
```
AI Confidence  →  Risk (% of account)
LOW            →  0.5R
MID            →  1.0R
HIGH           →  2.0R
```

**Safety Mechanisms:**
- Max trades per day: Hard-coded limit
- Max risk per day: Percentage cap
- Max drawdown: Emergency stop
- Cooldown: After consecutive losses

### 5. Trade Monitor
**Purpose:** Position monitoring
- Tracks open trades
- Checks prices against SL/TP
- Closes trades automatically
- No manual intervention

## Data Flow

```
Exchange → Market Monitor → MarketData
                              ↓
                         Rule Engine → SetupEvent
                                        ↓
                              AI Decision Engine → AIDecisionOutput
                                                     ↓
                                        Execution & Risk Engine → Trade
                                                                    ↓
                                                        Trade Monitor
```

## Event-Based Communication

All components communicate via JSON-serializable objects:

```python
# Market Data Event
{
  "symbol": "BTCUSDT",
  "timeframe": "15m",
  "timestamp": "2024-01-01T12:00:00",
  "ohlcv": [[...], [...], ...]
}

# Setup Event
{
  "event_id": "uuid",
  "symbol": "BTCUSDT",
  "pattern_type": "breakout_retest",
  "timestamp": "2024-01-01T12:00:00",
  "timeframes": ["1d", "4h", "15m"],
  "context_data": {
    "levels": {...},
    "trigger_price": 62350
  }
}

# AI Decision
{
  "decision": "TRADE",
  "confidence": "HIGH",
  "reason_code": "CLEAN_SETUP",
  "next_check": null
}

# Trade Order
{
  "trade_id": "uuid",
  "symbol": "BTCUSDT",
  "side": "buy",
  "order_type": "market",
  "quantity": 0.1,
  "stop_loss": 61000,
  "take_profit": 64000,
  "risk_amount": 100
}
```

## State Management

### Active States
- **Open Trades:** Tracked in TradeMonitor
- **Pending Setups (WAIT):** Stored with re-check schedule
- **Daily Limits:** Reset at start of day
- **Cooldown Status:** Tracked after consecutive losses

### Stateless Components
- Market Monitor: Fetches fresh data each time
- Rule Engine: Pure functions
- AI Decision Engine: No state between calls

## Security & Safety

### Hard-Coded Limits (Never AI-Controlled)
1. **MAX_TRADES_PER_DAY:** Prevents overtrading
2. **MAX_RISK_PER_DAY:** Caps exposure
3. **MAX_DRAWDOWN:** Emergency shutdown
4. **COOLDOWN_AFTER_LOSSES:** Forced pause

### Validation Layers
1. Rule Engine: Validates pattern exists
2. AI Engine: Validates setup quality
3. Risk Engine: Validates risk limits
4. Trade Monitor: Validates SL/TP execution

## Logging & Observability

Every component logs:
- All inputs received
- All decisions made
- All outputs produced
- Timestamps for everything

Log format: Structured JSON via structlog

```json
{
  "timestamp": "2024-01-01T12:00:00",
  "level": "info",
  "event": "setup_detected",
  "event_id": "...",
  "pattern_type": "breakout_retest",
  "symbol": "BTCUSDT"
}
```

## Technology Stack

- **Language:** Python 3.8+
- **Exchange API:** ccxt (multi-exchange support)
- **LLM:** OpenAI API (GPT-4 recommended)
- **Data:** pandas, numpy
- **Validation:** pydantic
- **Logging:** structlog
- **Testing:** pytest

## Scalability

### Current MVP
- 1 symbol
- 1 exchange
- 4 timeframes
- 2 patterns
- 1 account

### Future Expansion
- Multiple symbols (parallel instances)
- Multiple exchanges (abstracted via ccxt)
- More patterns (pluggable architecture)
- More timeframes (configurable)
- Portfolio management

## Design Principles

1. **Separation of Concerns:** Each component has one job
2. **AI is Advisory:** Machine makes final decisions
3. **Reproducibility:** Deterministic rules, low-temp LLM
4. **Safety First:** Hard-coded limits, no AI override
5. **Observability:** Log everything
6. **Testability:** Isolated components, paper trading

## Trade Lifecycle

```
1. Market data fetched
2. Setup detected by rules
3. AI validates setup quality
4. Risk checks passed
5. Trade order created
6. Order executed (paper or live)
7. Trade added to monitoring
8. Price checked continuously
9. SL or TP hit
10. Trade closed
11. Results logged
12. Statistics updated
```

## Error Handling

- **Market Data Failure:** Skip cycle, log error
- **AI API Failure:** Default to NO_TRADE
- **Exchange API Failure:** Retry with backoff
- **Invalid Setup:** Log and discard
- **Risk Limit Hit:** Block trade, log reason

## Configuration

All settings in `.env`:
- Exchange credentials
- LLM configuration
- Trading parameters
- Risk limits
- Logging settings

No hard-coded values in production code.

## Testing Strategy

1. **Unit Tests:** Each component isolated
2. **Integration Tests:** Component interactions
3. **Paper Trading:** Live market, simulated execution
4. **Backtesting:** Historical data (future work)

## Maintenance

### Daily
- Check logs for errors
- Review open trades
- Monitor risk usage

### Weekly
- Review statistics
- Analyze AI decisions
- Adjust if needed

### Monthly
- Performance review
- Risk limit assessment
- Pattern effectiveness analysis
