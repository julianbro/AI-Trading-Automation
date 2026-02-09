"""
Trade Monitoring.

This component is responsible for:
- Monitoring open trades
- Reacting to stop loss and take profit levels
- No trailing stops
- No intervention
- No AI calls during trade
"""
from typing import Dict, List, Optional
import structlog

from src.common.models import Trade, TradeStatus, OrderSide
from src.execution_risk.execution_risk_engine import ExecutionRiskEngine

logger = structlog.get_logger(__name__)


class TradeMonitor:
    """
    Trade Monitor for tracking open trades.
    
    Monitors open trades and closes them when SL or TP is hit.
    """
    
    def __init__(self, execution_engine: ExecutionRiskEngine):
        """
        Initialize Trade Monitor.
        
        Args:
            execution_engine: Execution & Risk Engine for updating trades
        """
        self.execution_engine = execution_engine
        self.open_trades: Dict[str, Trade] = {}
        
        logger.info("Trade Monitor initialized")
    
    def add_trade(self, trade: Trade):
        """
        Add a trade to monitoring.
        
        Args:
            trade: Trade to monitor
        """
        self.open_trades[trade.trade_id] = trade
        logger.info(
            "Trade added to monitoring",
            trade_id=trade.trade_id,
            symbol=trade.symbol,
            total_open_trades=len(self.open_trades)
        )
    
    def check_trades(self, current_prices: Dict[str, float]):
        """
        Check all open trades against current prices.
        
        Args:
            current_prices: Dictionary of symbol -> current price
        """
        closed_trades = []
        
        for trade_id, trade in self.open_trades.items():
            if trade.symbol not in current_prices:
                continue
            
            current_price = current_prices[trade.symbol]
            
            # Check for stop loss or take profit
            close_reason = None
            exit_price = None
            
            if trade.side == OrderSide.BUY:
                # Long trade
                if current_price <= trade.stop_loss:
                    close_reason = "STOP_LOSS"
                    exit_price = trade.stop_loss
                elif current_price >= trade.take_profit:
                    close_reason = "TAKE_PROFIT"
                    exit_price = trade.take_profit
            else:
                # Short trade
                if current_price >= trade.stop_loss:
                    close_reason = "STOP_LOSS"
                    exit_price = trade.stop_loss
                elif current_price <= trade.take_profit:
                    close_reason = "TAKE_PROFIT"
                    exit_price = trade.take_profit
            
            # Close trade if triggered
            if close_reason:
                self.execution_engine.update_trade_result(trade, exit_price, close_reason)
                closed_trades.append(trade_id)
                
                logger.info(
                    "Trade closed",
                    trade_id=trade_id,
                    symbol=trade.symbol,
                    reason=close_reason,
                    exit_price=exit_price,
                    pnl=trade.pnl
                )
        
        # Remove closed trades from monitoring
        for trade_id in closed_trades:
            del self.open_trades[trade_id]
        
        if closed_trades:
            logger.info(
                "Trade monitoring update",
                closed_count=len(closed_trades),
                remaining_open=len(self.open_trades)
            )
    
    def get_open_trades(self) -> List[Trade]:
        """
        Get all open trades.
        
        Returns:
            List of open trades
        """
        return list(self.open_trades.values())
    
    def get_trade(self, trade_id: str) -> Optional[Trade]:
        """
        Get a specific trade by ID.
        
        Args:
            trade_id: Trade ID
            
        Returns:
            Trade if found, None otherwise
        """
        return self.open_trades.get(trade_id)
    
    def remove_trade(self, trade_id: str):
        """
        Remove a trade from monitoring.
        
        Args:
            trade_id: Trade ID to remove
        """
        if trade_id in self.open_trades:
            del self.open_trades[trade_id]
            logger.info("Trade removed from monitoring", trade_id=trade_id)
