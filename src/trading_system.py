"""
Main Trading System Orchestrator.

This module coordinates all components of the trading system.
"""
import time
from typing import Dict, List, Optional
from datetime import datetime
import structlog

from src.common.models import SetupEvent, AIDecision, Trade
from src.common.logging_utils import setup_logging
from src.config import config
from src.market_monitor import MarketMonitor
from src.rule_engine import RuleEngine
from src.ai_decision import AIDecisionEngine
from src.execution_risk import ExecutionRiskEngine
from src.trade_monitoring import TradeMonitor

logger = structlog.get_logger(__name__)


class TradingSystem:
    """
    Main Trading System coordinating all components.
    
    This class orchestrates the entire trading workflow:
    1. Market Monitor fetches data
    2. Rule Engine detects setups
    3. AI Decision Engine validates setups
    4. Execution & Risk Engine executes trades
    5. Trade Monitor tracks open trades
    """
    
    def __init__(
        self,
        symbol: Optional[str] = None,
        timeframes: Optional[List[str]] = None,
        account_balance: float = 10000.0
    ):
        """
        Initialize Trading System.
        
        Args:
            symbol: Trading symbol (e.g., "BTC/USDT")
            timeframes: List of timeframes to monitor
            account_balance: Initial account balance
        """
        # Setup logging
        setup_logging()
        
        logger.info("Initializing Trading System")
        
        # Initialize components
        self.market_monitor = MarketMonitor(symbol, timeframes)
        self.rule_engine = RuleEngine()
        self.ai_decision_engine = AIDecisionEngine()
        self.execution_engine = ExecutionRiskEngine(account_balance)
        self.trade_monitor = TradeMonitor(self.execution_engine)
        
        # State tracking
        self.pending_setups: Dict[str, SetupEvent] = {}  # For WAIT decisions
        self.trade_history: List[Trade] = []
        
        logger.info(
            "Trading System initialized",
            symbol=symbol or config.trading.default_symbol,
            timeframes=timeframes or config.trading.timeframes,
            paper_trading=config.exchange.paper_trading
        )
    
    def run_cycle(self):
        """
        Run one complete trading cycle.
        
        This includes:
        1. Fetching market data
        2. Detecting setups
        3. Validating with AI
        4. Executing trades
        5. Monitoring open positions
        """
        logger.info("Starting trading cycle")
        
        try:
            # Step 1: Fetch market data
            logger.info("Step 1: Fetching market data")
            market_data = self.market_monitor.fetch_all_timeframes()
            
            if not market_data:
                logger.warning("No market data fetched, skipping cycle")
                return
            
            # Step 2: Detect setups
            logger.info("Step 2: Detecting setups")
            setups = self.rule_engine.detect_setups(market_data)
            
            # Step 3: Process each setup
            for setup in setups:
                self._process_setup(setup, market_data)
            
            # Step 4: Re-evaluate pending setups (WAIT decisions)
            self._reevaluate_pending_setups(market_data)
            
            # Step 5: Monitor open trades
            logger.info("Step 5: Monitoring open trades")
            current_prices = {
                symbol: data.ohlcv[-1][4] if data.ohlcv else 0  # Get close price
                for symbol, data in market_data.items()
            }
            # Convert timeframe keys to symbol
            symbol = self.market_monitor.symbol
            if market_data:
                latest_price = list(market_data.values())[0].ohlcv[-1][4] if list(market_data.values())[0].ohlcv else 0
                self.trade_monitor.check_trades({symbol: latest_price})
            
            logger.info(
                "Trading cycle complete",
                open_trades=len(self.trade_monitor.get_open_trades()),
                pending_setups=len(self.pending_setups)
            )
            
        except Exception as e:
            logger.error("Error in trading cycle", error=str(e), exc_info=True)
    
    def _process_setup(self, setup: SetupEvent, market_data: Dict):
        """
        Process a detected setup.
        
        Args:
            setup: Detected setup event
            market_data: Current market data
        """
        logger.info(
            "Processing setup",
            event_id=setup.event_id,
            pattern_type=setup.pattern_type
        )
        
        # Get current price for AI validation
        current_price = self.market_monitor.get_latest_price()
        
        # Step 3: Validate with AI
        logger.info("Step 3: Validating setup with AI")
        ai_decision = self.ai_decision_engine.validate_setup(setup, market_data, current_price)
        
        # Handle AI decision
        if ai_decision.decision == AIDecision.TRADE:
            self._execute_trade(setup, ai_decision, current_price)
        elif ai_decision.decision == AIDecision.WAIT:
            self._handle_wait_decision(setup, ai_decision)
        else:
            logger.info(
                "Setup rejected by AI",
                event_id=setup.event_id,
                reason=ai_decision.reason_code
            )
    
    def _execute_trade(self, setup: SetupEvent, ai_decision, current_price: float):
        """
        Execute a trade for an approved setup.
        
        Args:
            setup: Setup event
            ai_decision: AI decision output
            current_price: Current market price
        """
        logger.info("Step 4: Executing trade")
        
        # Check if trade should be executed (risk checks)
        if not self.execution_engine.should_execute_trade(ai_decision):
            logger.warning("Trade execution blocked by risk checks")
            return
        
        # Create trade order using AI-provided SL/TP
        try:
            order = self.execution_engine.create_trade_order(setup, ai_decision, current_price)
        except ValueError as e:
            logger.error("Failed to create trade order", error=str(e))
            return
        
        # Execute order
        trade = self.execution_engine.execute_order(order)
        
        # Add to monitoring
        self.trade_monitor.add_trade(trade)
        self.trade_history.append(trade)
        
        logger.info(
            "Trade executed and added to monitoring",
            trade_id=trade.trade_id,
            symbol=trade.symbol
        )
    
    def _handle_wait_decision(self, setup: SetupEvent, ai_decision):
        """
        Handle a WAIT decision from AI.
        
        Args:
            setup: Setup event
            ai_decision: AI decision output with WAIT
        """
        logger.info(
            "Setup marked for re-evaluation",
            event_id=setup.event_id,
            next_check=ai_decision.next_check
        )
        
        # Store setup for re-evaluation
        self.pending_setups[setup.event_id] = {
            "setup": setup,
            "ai_decision": ai_decision,
            "timestamp": datetime.now(),
            "recheck_count": 0
        }
    
    def _reevaluate_pending_setups(self, market_data: Dict):
        """
        Re-evaluate pending setups marked with WAIT.
        
        Args:
            market_data: Current market data
        """
        if not self.pending_setups:
            return
        
        logger.info("Re-evaluating pending setups", count=len(self.pending_setups))
        
        completed_setups = []
        
        # Get current price for re-evaluation
        current_price = self.market_monitor.get_latest_price()
        
        for event_id, pending in self.pending_setups.items():
            setup = pending["setup"]
            recheck_count = pending["recheck_count"]
            
            # Limit re-checks to avoid infinite loops
            if recheck_count >= 5:
                logger.info(
                    "Setup expired after max re-checks",
                    event_id=event_id
                )
                completed_setups.append(event_id)
                continue
            
            # Re-validate with AI
            ai_decision = self.ai_decision_engine.validate_setup(setup, market_data, current_price)
            
            if ai_decision.decision == AIDecision.TRADE:
                self._execute_trade(setup, ai_decision, current_price)
                completed_setups.append(event_id)
            elif ai_decision.decision == AIDecision.NO_TRADE:
                logger.info("Pending setup rejected", event_id=event_id)
                completed_setups.append(event_id)
            else:
                # Still waiting, increment counter
                pending["recheck_count"] += 1
                logger.info(
                    "Setup still pending",
                    event_id=event_id,
                    recheck_count=pending["recheck_count"]
                )
        
        # Remove completed setups
        for event_id in completed_setups:
            del self.pending_setups[event_id]
    
    def run_continuous(self, interval_seconds: int = 60):
        """
        Run the trading system continuously.
        
        Args:
            interval_seconds: Seconds between cycles
        """
        logger.info(
            "Starting continuous trading",
            interval_seconds=interval_seconds
        )
        
        try:
            while True:
                self.run_cycle()
                logger.info(f"Waiting {interval_seconds} seconds until next cycle")
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            logger.info("Trading system stopped by user")
        except Exception as e:
            logger.error("Fatal error in trading system", error=str(e), exc_info=True)
    
    def get_statistics(self) -> dict:
        """
        Get trading statistics.
        
        Returns:
            Dictionary with statistics
        """
        total_trades = len(self.trade_history)
        closed_trades = [t for t in self.trade_history if t.status.value == "closed"]
        winning_trades = [t for t in closed_trades if t.pnl and t.pnl > 0]
        losing_trades = [t for t in closed_trades if t.pnl and t.pnl < 0]
        
        total_pnl = sum(t.pnl for t in closed_trades if t.pnl)
        win_rate = len(winning_trades) / len(closed_trades) if closed_trades else 0
        
        return {
            "total_trades": total_trades,
            "closed_trades": len(closed_trades),
            "open_trades": len(self.trade_monitor.get_open_trades()),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "account_balance": self.execution_engine.account_balance,
            "daily_trades": self.execution_engine.daily_trades,
            "daily_risk_used": self.execution_engine.daily_risk_used,
        }
