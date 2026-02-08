"""
Common data models for the trading system.
"""
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class Timeframe(str, Enum):
    """Supported timeframes"""
    ONE_DAY = "1d"
    FOUR_HOURS = "4h"
    FIFTEEN_MIN = "15m"
    FIVE_MIN = "5m"


class MarketData(BaseModel):
    """Market data output from Market Monitor"""
    symbol: str
    timeframe: Timeframe
    timestamp: datetime
    ohlcv: List[List[float]]  # [[timestamp, open, high, low, close, volume], ...]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PatternType(str, Enum):
    """Supported trading pattern types"""
    BREAKOUT_RETEST = "breakout_retest"
    SUPPORT_BOUNCE = "support_bounce"
    RESISTANCE_REJECTION = "resistance_rejection"


class SetupEvent(BaseModel):
    """Setup event from Rule Engine"""
    event_id: str
    symbol: str
    pattern_type: PatternType
    timestamp: datetime
    timeframes: List[Timeframe]
    context_data: Dict[str, Any]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class AIDecision(str, Enum):
    """AI decision options"""
    TRADE = "TRADE"
    NO_TRADE = "NO_TRADE"
    WAIT = "WAIT"


class AIConfidence(str, Enum):
    """AI confidence levels"""
    LOW = "LOW"
    MID = "MID"
    HIGH = "HIGH"


class NextCheckType(str, Enum):
    """Type of next check for WAIT decisions"""
    TIME = "time"
    EVENT = "event"


class NextCheck(BaseModel):
    """Next check specification for WAIT decisions"""
    type: NextCheckType
    value: str  # e.g., "15m" for time, "close_above_level" for event


class AIDecisionOutput(BaseModel):
    """AI Decision Engine output"""
    decision: AIDecision
    confidence: AIConfidence
    reason_code: str  # e.g., "CLEAN_SETUP", "HTF_CONFLICT", "CHOPPY"
    next_check: Optional[NextCheck] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class OrderSide(str, Enum):
    """Order side"""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order type"""
    MARKET = "market"
    LIMIT = "limit"


class TradeOrder(BaseModel):
    """Trade order to be executed"""
    trade_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None  # For limit orders
    stop_loss: float
    take_profit: float
    risk_amount: float
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TradeStatus(str, Enum):
    """Trade status"""
    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class Trade(BaseModel):
    """Active trade"""
    trade_id: str
    symbol: str
    side: OrderSide
    entry_price: float
    quantity: float
    stop_loss: float
    take_profit: float
    status: TradeStatus
    opened_at: datetime
    closed_at: Optional[datetime] = None
    pnl: Optional[float] = None
    r_multiple: Optional[float] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
