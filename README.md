# AI-Trading-Automation

AI-unterstütztes automatisiertes Trading-System

## Überblick

Ein regelbasiertes, automatisiertes Trading-System mit klarer Trennung von Verantwortlichkeiten:

- **Python-Code** erkennt Setups und führt Trades aus
- **AI (LLM)** bewertet ausschließlich die Qualität eines Setups
- Keine AI-Execution, kein "freies Denken", keine Heuristiken im Risiko
- Vollständige Nachvollziehbarkeit & Reproduzierbarkeit

**👉 AI denkt – Maschine entscheidet.**

## Architektur

Das System besteht aus klar getrennten, lose gekoppelten Komponenten:

```
Market Monitor (Datenlieferant)
      ↓
Rule Engine (Setup Detection)
      ↓
AI Decision Engine (Validation)
      ↓
Execution & Risk Engine (Ausführung)
      ↓
Trade Monitoring (Überwachung)
```

### Komponenten

1. **Market Monitor** - Lädt OHLCV-Daten von Exchanges, verwaltet mehrere Timeframes
2. **Rule Engine** - Prüft deterministische Regeln, erkennt Trading-Setups
3. **AI Decision Engine** - Validiert Setups qualitativ (LLM)
4. **Execution & Risk Engine** - Mechanische Trade-Ausführung mit fixen Risiko-Regeln
5. **Trade Monitoring** - Überwacht offene Trades, reagiert auf SL/TP

## Installation

### Voraussetzungen

- Python 3.8+
- Cryptocurrency Exchange Account (z.B. Binance)
- OpenAI API Key (für LLM)

### Setup

1. Repository klonen:
```bash
git clone https://github.com/julianbro/AI-Trading-Automation.git
cd AI-Trading-Automation
```

2. Abhängigkeiten installieren:
```bash
pip install -r requirements.txt
```

3. Umgebungsvariablen konfigurieren:
```bash
cp .env.example .env
# Bearbeiten Sie .env mit Ihren API-Keys
```

### Konfiguration

Bearbeiten Sie die `.env` Datei:

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
PAPER_TRADING=true  # WICHTIG: Setzen Sie auf false nur für echtes Trading!
DEFAULT_SYMBOL=BTC/USDT
TIMEFRAMES=1d,4h,15m,5m

# Risk Management
MAX_TRADES_PER_DAY=5
MAX_RISK_PER_DAY=10.0
MAX_DRAWDOWN=20.0
COOLDOWN_AFTER_LOSSES=3
```

## Verwendung

### Paper Trading Beispiel

Starten Sie das System im Paper Trading Modus:

```bash
python examples/paper_trading_example.py
```

### Setup Detection Beispiel

Testen Sie die Setup-Erkennung:

```bash
python examples/setup_detection_example.py
```

### Programmierbeispiel

```python
from src.trading_system import TradingSystem

# System initialisieren
system = TradingSystem(
    symbol="BTC/USDT",
    timeframes=["1d", "4h", "15m", "5m"],
    account_balance=10000.0
)

# Einzelner Zyklus
system.run_cycle()

# Kontinuierliches Trading (60 Sekunden Intervall)
system.run_continuous(interval_seconds=60)

# Statistiken abrufen
stats = system.get_statistics()
print(f"Win Rate: {stats['win_rate']:.2%}")
print(f"Total P&L: ${stats['total_pnl']:.2f}")
```

## Komponenten Details

### 1. Market Monitor

Lädt Marktdaten von Exchanges:

```python
from src.market_monitor import MarketMonitor

monitor = MarketMonitor(symbol="BTC/USDT", timeframes=["1d", "4h"])
market_data = monitor.fetch_all_timeframes(limit=100)
```

### 2. Rule Engine

Erkennt Trading-Setups basierend auf deterministischen Regeln:

```python
from src.rule_engine import RuleEngine

engine = RuleEngine()
setups = engine.detect_setups(market_data)
```

Unterstützte Patterns:
- `BREAKOUT_RETEST` - Breakout mit Retest
- `SUPPORT_BOUNCE` - Bounce von Support-Level

### 3. AI Decision Engine

Validiert Setups mit LLM:

```python
from src.ai_decision import AIDecisionEngine

ai_engine = AIDecisionEngine()
decision = ai_engine.validate_setup(setup, market_data)

print(f"Decision: {decision.decision}")  # TRADE, NO_TRADE, WAIT
print(f"Confidence: {decision.confidence}")  # LOW, MID, HIGH
print(f"Reason: {decision.reason_code}")
```

### 4. Execution & Risk Engine

Führt Trades mit striktem Risk Management aus:

```python
from src.execution_risk import ExecutionRiskEngine

exec_engine = ExecutionRiskEngine(account_balance=10000.0)

if exec_engine.should_execute_trade(ai_decision):
    order = exec_engine.create_trade_order(setup, ai_decision, current_price)
    trade = exec_engine.execute_order(order)
```

Risk Mapping:
- LOW Confidence → 0.5R
- MID Confidence → 1.0R  
- HIGH Confidence → 2.0R

### 5. Trade Monitor

Überwacht offene Trades:

```python
from src.trade_monitoring import TradeMonitor

monitor = TradeMonitor(exec_engine)
monitor.add_trade(trade)
monitor.check_trades(current_prices)
```

## Sicherheitsmechanismen

Das System hat hart codierte Sicherheitsgrenzen:

- ✅ Max Trades pro Tag
- ✅ Max Risiko pro Tag
- ✅ Max Drawdown → System Stop
- ✅ Cooldown nach Verlustserie

**Diese Limits sind NIE AI-gesteuert!**

## Logging

Alle Aktionen werden strukturiert geloggt:

- Setup Events
- AI Inputs & Outputs
- Trade-Details
- Ergebnisse (PnL, R-Multiple)

Logs werden in `trading_system.log` gespeichert.

## Datenmodelle

Das System verwendet Pydantic-Modelle für Type Safety:

```python
from src.common.models import (
    MarketData,
    SetupEvent,
    AIDecisionOutput,
    TradeOrder,
    Trade
)
```

## Projektstruktur

```
AI-Trading-Automation/
├── src/
│   ├── common/             # Gemeinsame Modelle und Utils
│   ├── config/             # Konfiguration
│   ├── market_monitor/     # Market Monitor Komponente
│   ├── rule_engine/        # Rule Engine Komponente
│   ├── ai_decision/        # AI Decision Engine Komponente
│   ├── execution_risk/     # Execution & Risk Engine Komponente
│   ├── trade_monitoring/   # Trade Monitoring Komponente
│   └── trading_system.py   # Haupt-Orchestrator
├── examples/               # Beispielskripte
├── tests/                  # Tests (TODO)
├── requirements.txt        # Python-Abhängigkeiten
├── .env.example           # Beispiel-Umgebungsvariablen
└── README.md              # Diese Datei
```

## Entwicklung

### Tests ausführen

```bash
pytest tests/
```

### Logging Level ändern

In `.env`:
```env
LOG_LEVEL=DEBUG  # oder INFO, WARNING, ERROR
```

## Roadmap

- [ ] Backtesting Framework
- [ ] Mehr Trading Patterns
- [ ] Web Dashboard
- [ ] Multi-Symbol Support
- [ ] Performance Analytics
- [ ] Telegram Notifications

## Sicherheitshinweise

⚠️ **WICHTIG:**

1. Starten Sie IMMER mit Paper Trading (`PAPER_TRADING=true`)
2. Testen Sie ausführlich bevor Sie zu Live Trading wechseln
3. Verwenden Sie niemals mehr Kapital als Sie verlieren können
4. Die AI ist beratend - finale Entscheidungen liegen beim Code
5. Überprüfen Sie regelmäßig Logs und Performance

## Lizenz

MIT License - siehe LICENSE Datei

## Support

Für Fragen und Support:
- GitHub Issues: https://github.com/julianbro/AI-Trading-Automation/issues

## Disclaimer

Dieses System ist für Bildungszwecke. Trading birgt erhebliche Risiken. 
Der Autor übernimmt keine Haftung für finanzielle Verluste.
