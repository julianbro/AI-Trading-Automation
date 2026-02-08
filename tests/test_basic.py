"""
Test configuration and models.
"""
import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_imports():
    """Test that all main modules can be imported."""
    from src.common.models import (
        Timeframe,
        MarketData,
        SetupEvent,
        AIDecisionOutput,
        TradeOrder,
        Trade
    )
    from src.config import config
    from src.market_monitor import MarketMonitor
    from src.rule_engine import RuleEngine
    from src.ai_decision import AIDecisionEngine
    from src.execution_risk import ExecutionRiskEngine
    from src.trade_monitoring import TradeMonitor
    from src.trading_system import TradingSystem
    
    assert Timeframe is not None
    assert MarketData is not None
    assert SetupEvent is not None
    assert AIDecisionOutput is not None
    assert TradeOrder is not None
    assert Trade is not None
    assert config is not None
    assert MarketMonitor is not None
    assert RuleEngine is not None
    assert AIDecisionEngine is not None
    assert ExecutionRiskEngine is not None
    assert TradeMonitor is not None
    assert TradingSystem is not None


def test_config():
    """Test configuration loading."""
    from src.config import config
    
    assert config is not None
    assert config.exchange is not None
    assert config.trading is not None
    assert config.risk is not None
    assert config.logging is not None


def test_models():
    """Test that models can be instantiated."""
    from src.common.models import (
        Timeframe,
        AIDecision,
        AIConfidence,
        OrderSide,
        OrderType,
        TradeStatus
    )
    
    # Test enums
    assert Timeframe.ONE_DAY.value == "1d"
    assert AIDecision.TRADE.value == "TRADE"
    assert AIConfidence.HIGH.value == "HIGH"
    assert OrderSide.BUY.value == "buy"
    assert OrderType.MARKET.value == "market"
    assert TradeStatus.OPEN.value == "open"
