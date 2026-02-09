"""
Test configuration and models.
"""
import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_basic_imports():
    """Test that basic modules can be imported."""
    # Import directly from modules to avoid importing ccxt/openai
    import importlib.util
    
    # Test common.models
    spec = importlib.util.spec_from_file_location(
        "models",
        "/home/runner/work/AI-Trading-Automation/AI-Trading-Automation/src/common/models.py"
    )
    models = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(models)
    
    assert models.Timeframe is not None
    assert models.MarketData is not None
    assert models.SetupEvent is not None
    assert models.AIDecisionOutput is not None
    assert models.TradeOrder is not None
    assert models.Trade is not None


def test_config():
    """Test configuration loading."""
    import importlib.util
    
    # Import config directly
    spec = importlib.util.spec_from_file_location(
        "config",
        "/home/runner/work/AI-Trading-Automation/AI-Trading-Automation/src/config/config.py"
    )
    config_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config_module)
    
    config = config_module.config
    assert config is not None
    assert config.exchange is not None
    assert config.trading is not None
    assert config.risk is not None
    assert config.logging is not None


def test_models():
    """Test that models can be instantiated."""
    import importlib.util
    
    # Import models directly
    spec = importlib.util.spec_from_file_location(
        "models",
        "/home/runner/work/AI-Trading-Automation/AI-Trading-Automation/src/common/models.py"
    )
    models = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(models)
    
    # Test enums
    assert models.Timeframe.ONE_DAY.value == "1d"
    assert models.AIDecision.TRADE.value == "TRADE"
    assert models.AIConfidence.HIGH.value == "HIGH"
    assert models.OrderSide.BUY.value == "buy"
    assert models.OrderType.MARKET.value == "market"
    assert models.TradeStatus.OPEN.value == "open"


def test_risk_mapping():
    """Test risk management configuration."""
    import importlib.util
    
    # Import config directly
    spec = importlib.util.spec_from_file_location(
        "config",
        "/home/runner/work/AI-Trading-Automation/AI-Trading-Automation/src/config/config.py"
    )
    config_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config_module)
    
    config = config_module.config
    # Check risk mapping
    assert config.risk.risk_mapping["LOW"] == 0.5
    assert config.risk.risk_mapping["MID"] == 1.0
    assert config.risk.risk_mapping["HIGH"] == 2.0


def test_model_creation():
    """Test creating model instances."""
    import importlib.util
    from datetime import datetime
    
    # Import models directly
    spec = importlib.util.spec_from_file_location(
        "models",
        "/home/runner/work/AI-Trading-Automation/AI-Trading-Automation/src/common/models.py"
    )
    models = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(models)
    
    # Create MarketData
    market_data = models.MarketData(
        symbol="BTC/USDT",
        timeframe=models.Timeframe.ONE_DAY,
        timestamp=datetime.now(),
        ohlcv=[[1234567890, 50000, 51000, 49000, 50500, 100]]
    )
    assert market_data.symbol == "BTC/USDT"
    
    # Create SetupEvent
    setup = models.SetupEvent(
        event_id="test-123",
        symbol="BTC/USDT",
        pattern_type=models.PatternType.BREAKOUT_RETEST,
        timestamp=datetime.now(),
        timeframes=[models.Timeframe.ONE_DAY],
        context_data={"test": "data"}
    )
    assert setup.event_id == "test-123"
    
    # Create AIDecisionOutput
    decision = models.AIDecisionOutput(
        decision=models.AIDecision.TRADE,
        confidence=models.AIConfidence.HIGH,
        reason_code="CLEAN_SETUP"
    )
    assert decision.decision == models.AIDecision.TRADE
