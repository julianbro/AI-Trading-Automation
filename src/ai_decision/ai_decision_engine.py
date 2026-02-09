"""
AI Decision Engine - Setup Validation.

This component is responsible for:
- Qualitative validation of detected setups
- Functions as a pattern validator
- AI can agree/disagree or request to wait
- AI cannot: trade, invent prices, set positions/SL/TP
- Purely advisory role
"""
import json
from typing import Dict
import structlog
from openai import OpenAI

from src.common.models import (
    SetupEvent, 
    MarketData, 
    AIDecisionOutput, 
    AIDecision, 
    AIConfidence,
    NextCheck,
    NextCheckType
)
from src.config import config

logger = structlog.get_logger(__name__)


class AIDecisionEngine:
    """
    AI Decision Engine for setup validation.
    
    Uses LLM to validate trading setups detected by the Rule Engine.
    """
    
    def __init__(self):
        """Initialize AI Decision Engine."""
        self.client = OpenAI(api_key=config.llm.api_key)
        self.model = config.llm.model
        self.temperature = config.llm.temperature
        
        logger.info(
            "AI Decision Engine initialized",
            model=self.model,
            temperature=self.temperature
        )
    
    def validate_setup(self, setup: SetupEvent, market_data: Dict[str, MarketData], current_price: float) -> AIDecisionOutput:
        """
        Validate a trading setup using AI.
        
        Args:
            setup: SetupEvent to validate
            market_data: Market data for context
            current_price: Current market price
            
        Returns:
            AIDecisionOutput with validation result
        """
        logger.info(
            "Validating setup with AI",
            event_id=setup.event_id,
            pattern_type=setup.pattern_type,
            current_price=current_price
        )
        
        try:
            # Prepare input for AI
            ai_input = self._prepare_ai_input(setup, market_data, current_price)
            
            # Get AI decision
            response = self._call_llm(ai_input)
            
            # Parse response
            decision = self._parse_ai_response(response)
            
            logger.info(
                "AI validation complete",
                event_id=setup.event_id,
                decision=decision.decision,
                confidence=decision.confidence,
                reason_code=decision.reason_code,
                entry_price=decision.entry_price,
                stop_loss=decision.stop_loss,
                take_profit=decision.take_profit
            )
            
            return decision
            
        except Exception as e:
            logger.error(
                "Error during AI validation",
                event_id=setup.event_id,
                error=str(e)
            )
            # Return safe default: NO_TRADE
            return AIDecisionOutput(
                decision=AIDecision.NO_TRADE,
                confidence=AIConfidence.LOW,
                reason_code="AI_ERROR"
            )
    
    def _prepare_ai_input(self, setup: SetupEvent, market_data: Dict[str, MarketData], current_price: float) -> dict:
        """
        Prepare input data for the AI.
        
        Args:
            setup: SetupEvent to validate
            market_data: Market data for context
            current_price: Current market price
            
        Returns:
            Dictionary with structured input for AI
        """
        # Extract relevant OHLCV data
        ohlcv_data = {}
        for timeframe_str, data in market_data.items():
            # Get last 20 candles for context
            recent_candles = data.ohlcv[-20:] if len(data.ohlcv) > 20 else data.ohlcv
            ohlcv_data[timeframe_str] = recent_candles
        
        return {
            "setup": {
                "event_id": setup.event_id,
                "symbol": setup.symbol,
                "pattern_type": setup.pattern_type,
                "timestamp": setup.timestamp.isoformat(),
                "context_data": setup.context_data,
            },
            "current_price": current_price,
            "market_data": {
                timeframe: candles for timeframe, candles in ohlcv_data.items()
            }
        }
    
    def _call_llm(self, ai_input: dict) -> str:
        """
        Call the LLM with prepared input.
        
        Args:
            ai_input: Prepared input dictionary
            
        Returns:
            LLM response as string
        """
        system_prompt = """You are a professional trading setup validator with deep expertise in risk management.

Your role is to:
1. Validate the quality of detected trading setups
2. Define precise entry, stop-loss, and take-profit levels
3. Apply strict trading principles

🔴 CRITICAL TRADING PRINCIPLES:

1️⃣ PATTERN VALIDITY REQUIRES CONTEXT
A pattern alone is never enough. Always consider:
- Trend: Is this with or against the higher timeframe trend?
- Market Phase: Is this a range, trend, or reversal?
- Level: Is this at a logical support/resistance, VWAP, or high/low?

📌 RULE: Only trade patterns that form at logical market levels.

2️⃣ CLEAR INVALIDATION - NO TRADE WITHOUT STOP LOGIC
You must know where you are wrong BEFORE entering.
- Stop-loss goes where the pattern is objectively broken
- No "let's see what happens"
- No moving stops out of fear

📌 RULE: If you can't explain the stop-loss in 5 seconds → NO_TRADE

3️⃣ RISK > SETUP (Position sizing matters more than the pattern)
Think in R-multiples, not percentages or money:
- Fixed risk per trade (typically 0.5-1R)
- Same patterns, same logic, same risk rules
- Losses are part of statistics, not personal failure

📌 RULE: Survive bad streaks - profits come automatically

RESPONSE FORMAT - You MUST respond with valid JSON:
{
  "decision": "TRADE" | "NO_TRADE" | "WAIT",
  "confidence": "LOW" | "MID" | "HIGH",
  "reason_code": "CLEAN_SETUP" | "HTF_CONFLICT" | "CHOPPY" | "INSUFFICIENT_MOMENTUM" | "GOOD_STRUCTURE" | "NO_CLEAR_INVALIDATION" | "POOR_RR",
  "entry_price": <number> (only if TRADE),
  "stop_loss": <number> (only if TRADE),
  "take_profit": <number> (only if TRADE),
  "side": "buy" | "sell" (only if TRADE),
  "next_check": {
    "type": "time" | "event",
    "value": "15m" | "close_above_level"
  } (only if WAIT)
}

Decision guidelines:
- TRADE: Clean setup at logical level, clear invalidation point, good risk/reward
- NO_TRADE: Poor structure, no clear stop logic, conflicting timeframes, bad risk/reward
- WAIT: Setup forming but needs confirmation (provide next_check)

Confidence guidelines:
- HIGH: Perfect alignment across timeframes, textbook setup, clear levels, excellent RR (>2:1)
- MID: Good setup with minor concerns, acceptable RR (>1.5:1)
- LOW: Marginal setup, minimal RR (>1:1) - rare, usually better to pass

For TRADE decisions, you MUST provide:
- entry_price: Specific price to enter (be precise)
- stop_loss: Where the setup is invalidated (must be logical, typically at a structural level)
- take_profit: Target based on market structure and risk/reward (aim for 2:1 or better)
- side: "buy" for long, "sell" for short

Stop-loss validation rules:
- Must be at a logical level (below support for long, above resistance for short)
- Should not be more than 5-10% from entry in normal market conditions
- Should represent actual pattern invalidation, not arbitrary percentage

Take-profit validation rules:
- Should target logical resistance (for long) or support (for short)
- Minimum risk/reward ratio of 1.5:1, ideally 2:1 or better
- Consider market structure and recent price action

Focus on:
- Higher timeframe trend alignment
- Quality of support/resistance levels
- Clear pattern invalidation point
- Realistic risk/reward ratio
- Market phase (trending vs ranging)"""

        user_prompt = f"""Validate this trading setup:

Setup Information:
{json.dumps(ai_input['setup'], indent=2)}

Market Data Summary:
Symbol: {ai_input['setup']['symbol']}
Current Price: {ai_input.get('current_price', 'N/A')}
Timeframes Available: {', '.join(ai_input['market_data'].keys())}

Recent Price Action (OHLCV - last 20 candles per timeframe available in data)

Analyze the setup considering:
1. Is this pattern at a logical market level?
2. Where is the clear invalidation point for stop-loss?
3. What is the risk/reward ratio?
4. Does the higher timeframe support this trade?

Respond ONLY with the JSON decision object. No explanations or additional text."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error("Error calling LLM", error=str(e))
            raise
    
    def _parse_ai_response(self, response: str) -> AIDecisionOutput:
        """
        Parse AI response into AIDecisionOutput.
        
        Args:
            response: JSON response from LLM
            
        Returns:
            AIDecisionOutput object
        """
        try:
            data = json.loads(response)
            
            # Extract next_check if present
            next_check = None
            if "next_check" in data and data["next_check"]:
                next_check = NextCheck(
                    type=NextCheckType(data["next_check"]["type"]),
                    value=data["next_check"]["value"]
                )
            
            # Extract trade parameters if present (for TRADE decisions)
            entry_price = data.get("entry_price")
            stop_loss = data.get("stop_loss")
            take_profit = data.get("take_profit")
            side = data.get("side")
            
            decision = AIDecisionOutput(
                decision=AIDecision(data["decision"]),
                confidence=AIConfidence(data["confidence"]),
                reason_code=data["reason_code"],
                next_check=next_check,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                side=side
            )
            
            return decision
            
        except Exception as e:
            logger.error("Error parsing AI response", error=str(e), response=response)
            # Return safe default
            return AIDecisionOutput(
                decision=AIDecision.NO_TRADE,
                confidence=AIConfidence.LOW,
                reason_code="PARSE_ERROR"
            )
