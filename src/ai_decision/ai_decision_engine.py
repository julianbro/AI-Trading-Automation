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
    
    def validate_setup(self, setup: SetupEvent, market_data: Dict[str, MarketData]) -> AIDecisionOutput:
        """
        Validate a trading setup using AI.
        
        Args:
            setup: SetupEvent to validate
            market_data: Market data for context
            
        Returns:
            AIDecisionOutput with validation result
        """
        logger.info(
            "Validating setup with AI",
            event_id=setup.event_id,
            pattern_type=setup.pattern_type
        )
        
        try:
            # Prepare input for AI
            ai_input = self._prepare_ai_input(setup, market_data)
            
            # Get AI decision
            response = self._call_llm(ai_input)
            
            # Parse response
            decision = self._parse_ai_response(response)
            
            logger.info(
                "AI validation complete",
                event_id=setup.event_id,
                decision=decision.decision,
                confidence=decision.confidence,
                reason_code=decision.reason_code
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
    
    def _prepare_ai_input(self, setup: SetupEvent, market_data: Dict[str, MarketData]) -> dict:
        """
        Prepare input data for the AI.
        
        Args:
            setup: SetupEvent to validate
            market_data: Market data for context
            
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
        system_prompt = """You are a professional trading setup validator.
Your role is STRICTLY LIMITED to:
1. Validate the quality of an already-detected trading setup
2. Check for conflicts across timeframes
3. Assess market conditions (trending, choppy, clean)

You MUST respond ONLY with valid JSON in this exact format:
{
  "decision": "TRADE" | "NO_TRADE" | "WAIT",
  "confidence": "LOW" | "MID" | "HIGH",
  "reason_code": "CLEAN_SETUP" | "HTF_CONFLICT" | "CHOPPY" | "INSUFFICIENT_MOMENTUM" | "GOOD_STRUCTURE",
  "next_check": {
    "type": "time" | "event",
    "value": "15m" | "close_above_level"
  }
}

Decision guidelines:
- TRADE: Setup looks clean, timeframes align, good structure
- NO_TRADE: Conflicting signals, choppy, poor structure
- WAIT: Setup has potential but needs confirmation (provide next_check)

Confidence guidelines:
- HIGH: All timeframes align, clean structure, strong momentum
- MID: Setup is good but some minor concerns
- LOW: Setup is questionable or marginal

You CANNOT:
- Set prices, stop losses, or take profits
- Determine position sizes
- Execute trades
- Make predictions about future prices

Focus on:
- Timeframe alignment
- Market structure quality
- Momentum and trend strength
- Support/resistance clarity"""

        user_prompt = f"""Validate this trading setup:

Setup Information:
{json.dumps(ai_input['setup'], indent=2)}

Market Data (OHLCV - last 20 candles per timeframe):
Symbol: {ai_input['setup']['symbol']}

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
            
            decision = AIDecisionOutput(
                decision=AIDecision(data["decision"]),
                confidence=AIConfidence(data["confidence"]),
                reason_code=data["reason_code"],
                next_check=next_check
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
