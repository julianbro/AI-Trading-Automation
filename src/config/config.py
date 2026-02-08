"""
Configuration management for the trading system.
"""
import os
from typing import List
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class ExchangeConfig(BaseModel):
    """Exchange configuration"""
    name: str = Field(default_factory=lambda: os.getenv("EXCHANGE_NAME", "binance"))
    api_key: str = Field(default_factory=lambda: os.getenv("EXCHANGE_API_KEY", ""))
    api_secret: str = Field(default_factory=lambda: os.getenv("EXCHANGE_API_SECRET", ""))
    paper_trading: bool = Field(default_factory=lambda: os.getenv("PAPER_TRADING", "true").lower() == "true")


class LLMConfig(BaseModel):
    """LLM configuration"""
    api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    model: str = Field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4"))
    temperature: float = Field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.1")))


class TradingConfig(BaseModel):
    """Trading configuration"""
    default_symbol: str = Field(default_factory=lambda: os.getenv("DEFAULT_SYMBOL", "BTC/USDT"))
    timeframes: List[str] = Field(
        default_factory=lambda: os.getenv("TIMEFRAMES", "1d,4h,15m,5m").split(",")
    )


class RiskConfig(BaseModel):
    """Risk management configuration"""
    max_trades_per_day: int = Field(default_factory=lambda: int(os.getenv("MAX_TRADES_PER_DAY", "5")))
    max_risk_per_day: float = Field(default_factory=lambda: float(os.getenv("MAX_RISK_PER_DAY", "10.0")))
    max_drawdown: float = Field(default_factory=lambda: float(os.getenv("MAX_DRAWDOWN", "20.0")))
    cooldown_after_losses: int = Field(default_factory=lambda: int(os.getenv("COOLDOWN_AFTER_LOSSES", "3")))
    
    # Risk per confidence level (in R multiples)
    risk_mapping: dict = {
        "LOW": 0.5,
        "MID": 1.0,
        "HIGH": 2.0,
    }


class LoggingConfig(BaseModel):
    """Logging configuration"""
    level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    log_file: str = Field(default_factory=lambda: os.getenv("LOG_FILE", "trading_system.log"))


class Config(BaseModel):
    """Main configuration"""
    exchange: ExchangeConfig = Field(default_factory=ExchangeConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    trading: TradingConfig = Field(default_factory=TradingConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


# Global configuration instance
config = Config()
