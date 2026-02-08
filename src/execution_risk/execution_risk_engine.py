"""
Execution & Risk Engine.

This component is responsible for:
- Mechanical trade execution
- Implementation of fixed risk rules
- No AI influence
- No interpretation room
"""
import uuid
from typing import Optional
from datetime import datetime
import structlog

from src.common.models import (
    SetupEvent,
    AIDecisionOutput,
    AIDecision,
    AIConfidence,
    TradeOrder,
    OrderSide,
    OrderType,
    Trade,
    TradeStatus,
)
from src.config import config

logger = structlog.get_logger(__name__)


class ExecutionRiskEngine:
    """
    Execution & Risk Engine for trade execution.
    
    Executes trades based on AI decisions with strict risk management.
    """
    
    def __init__(self, account_balance: float = 10000.0):
        """
        Initialize Execution & Risk Engine.
        
        Args:
            account_balance: Initial account balance for risk calculation
        """
        self.account_balance = account_balance
        self.daily_trades = 0
        self.daily_risk_used = 0.0
        self.consecutive_losses = 0
        self.in_cooldown = False
        
        logger.info(
            "Execution & Risk Engine initialized",
            account_balance=account_balance
        )
    
    def should_execute_trade(self, ai_decision: AIDecisionOutput) -> bool:
        """
        Check if a trade should be executed based on risk rules.
        
        Args:
            ai_decision: AI decision output
            
        Returns:
            True if trade should be executed, False otherwise
        """
        # Check AI decision
        if ai_decision.decision != AIDecision.TRADE:
            logger.info("Trade rejected: AI decision is not TRADE", decision=ai_decision.decision)
            return False
        
        # Check daily trade limit
        if self.daily_trades >= config.risk.max_trades_per_day:
            logger.warning("Trade rejected: Daily trade limit reached")
            return False
        
        # Check daily risk limit
        risk_for_trade = config.risk.risk_mapping[ai_decision.confidence.value]
        if self.daily_risk_used + risk_for_trade > config.risk.max_risk_per_day:
            logger.warning("Trade rejected: Daily risk limit would be exceeded")
            return False
        
        # Check cooldown
        if self.in_cooldown:
            logger.warning("Trade rejected: In cooldown period")
            return False
        
        return True
    
    def create_trade_order(
        self,
        setup: SetupEvent,
        ai_decision: AIDecisionOutput,
        current_price: float
    ) -> TradeOrder:
        """
        Create a trade order based on setup and AI decision.
        
        Args:
            setup: Setup event
            ai_decision: AI decision output
            current_price: Current market price
            
        Returns:
            TradeOrder object
        """
        # Calculate risk amount based on AI confidence
        risk_r = config.risk.risk_mapping[ai_decision.confidence.value]
        risk_amount = self.account_balance * (risk_r / 100)
        
        # Determine order side based on pattern
        # For breakout retest and support bounce, we go long
        side = OrderSide.BUY
        
        # Calculate stop loss based on structure
        # Use support/resistance levels from setup
        if "levels" in setup.context_data:
            levels = setup.context_data["levels"]
            
            if side == OrderSide.BUY:
                # Stop loss below support/resistance
                stop_loss = levels.get("support", levels.get("resistance", current_price * 0.98))
                stop_loss = stop_loss * 0.995  # Small buffer
            else:
                # Stop loss above resistance
                stop_loss = levels.get("resistance", current_price * 1.02)
                stop_loss = stop_loss * 1.005  # Small buffer
        else:
            # Default stop loss: 2% below entry
            stop_loss = current_price * 0.98 if side == OrderSide.BUY else current_price * 1.02
        
        # Calculate position size based on risk
        risk_per_unit = abs(current_price - stop_loss)
        quantity = risk_amount / risk_per_unit
        
        # Calculate take profit (fixed RR ratio of 1:2)
        risk_distance = abs(current_price - stop_loss)
        if side == OrderSide.BUY:
            take_profit = current_price + (risk_distance * 2)
        else:
            take_profit = current_price - (risk_distance * 2)
        
        # Create order
        order = TradeOrder(
            trade_id=str(uuid.uuid4()),
            symbol=setup.symbol,
            side=side,
            order_type=OrderType.MARKET,  # Use market orders for simplicity
            quantity=quantity,
            price=None,  # Market order
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_amount=risk_amount
        )
        
        logger.info(
            "Trade order created",
            trade_id=order.trade_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            stop_loss=order.stop_loss,
            take_profit=order.take_profit,
            risk_amount=order.risk_amount
        )
        
        return order
    
    def execute_order(self, order: TradeOrder) -> Trade:
        """
        Execute a trade order.
        
        In paper trading mode, this simulates the execution.
        In live mode, this would place an actual order.
        
        Args:
            order: Trade order to execute
            
        Returns:
            Trade object representing the executed trade
        """
        # Update risk tracking
        self.daily_trades += 1
        risk_r = order.risk_amount / self.account_balance * 100
        self.daily_risk_used += risk_r
        
        # In paper trading mode, we simulate execution at market price
        # In live mode, use exchange API to place order
        if config.exchange.paper_trading:
            logger.info("Executing order in PAPER TRADING mode", trade_id=order.trade_id)
            entry_price = order.price if order.price else order.stop_loss * 1.02  # Simulate entry
        else:
            logger.info("Executing order in LIVE mode", trade_id=order.trade_id)
            # TODO: Implement actual order placement via exchange API
            entry_price = order.price if order.price else order.stop_loss * 1.02
        
        # Create trade record
        trade = Trade(
            trade_id=order.trade_id,
            symbol=order.symbol,
            side=order.side,
            entry_price=entry_price,
            quantity=order.quantity,
            stop_loss=order.stop_loss,
            take_profit=order.take_profit,
            status=TradeStatus.OPEN,
            opened_at=datetime.now()
        )
        
        logger.info(
            "Trade executed",
            trade_id=trade.trade_id,
            symbol=trade.symbol,
            entry_price=trade.entry_price,
            quantity=trade.quantity
        )
        
        return trade
    
    def update_trade_result(self, trade: Trade, exit_price: float, reason: str):
        """
        Update trade with result after closing.
        
        Args:
            trade: Trade to update
            exit_price: Exit price
            reason: Reason for closing (SL/TP)
        """
        # Calculate PnL
        if trade.side == OrderSide.BUY:
            pnl = (exit_price - trade.entry_price) * trade.quantity
        else:
            pnl = (trade.entry_price - exit_price) * trade.quantity
        
        # Calculate R-multiple
        risk = abs(trade.entry_price - trade.stop_loss) * trade.quantity
        r_multiple = pnl / risk if risk > 0 else 0
        
        # Update trade
        trade.status = TradeStatus.CLOSED
        trade.closed_at = datetime.now()
        trade.pnl = pnl
        trade.r_multiple = r_multiple
        
        # Update consecutive losses
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        
        # Check if cooldown needed
        if self.consecutive_losses >= config.risk.cooldown_after_losses:
            self.in_cooldown = True
            logger.warning(
                "Cooldown activated",
                consecutive_losses=self.consecutive_losses
            )
        
        # Update account balance
        self.account_balance += pnl
        
        logger.info(
            "Trade closed",
            trade_id=trade.trade_id,
            exit_price=exit_price,
            pnl=pnl,
            r_multiple=r_multiple,
            reason=reason,
            account_balance=self.account_balance
        )
    
    def reset_daily_limits(self):
        """Reset daily limits (call at start of new trading day)."""
        self.daily_trades = 0
        self.daily_risk_used = 0.0
        logger.info("Daily limits reset")
    
    def clear_cooldown(self):
        """Clear cooldown period."""
        self.in_cooldown = False
        self.consecutive_losses = 0
        logger.info("Cooldown cleared")
