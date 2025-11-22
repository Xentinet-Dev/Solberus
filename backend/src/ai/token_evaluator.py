"""
Token Evaluator - AI-powered token analysis and trading decision support.
Uses LLM to evaluate tokens, detect scams, and provide trading recommendations.
"""

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)

# LLM integration
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

LLM_AVAILABLE = OPENAI_AVAILABLE or ANTHROPIC_AVAILABLE


@dataclass
class TokenEvaluation:
    """Result of token evaluation."""
    
    token_symbol: str
    token_address: str
    risk_score: float  # 0.0 (safe) to 1.0 (very risky)
    opportunity_score: float  # 0.0 (low) to 1.0 (high)
    scam_indicators: List[str]
    positive_indicators: List[str]
    trading_recommendation: str  # "strong_buy", "buy", "hold", "avoid", "scam"
    confidence: float
    reasoning: str
    price_prediction: Optional[str] = None  # Short-term price prediction
    market_sentiment: Optional[str] = None


class TokenEvaluator:
    """
    AI-powered token evaluator for trading decisions.
    
    Analyzes:
    - Token metadata (name, symbol, description)
    - Social media presence
    - Trading patterns
    - Contract analysis
    - Scam detection
    - Trading opportunities
    """
    
    def __init__(
        self,
        enable_llm: bool = True,
        llm_provider: str = "openai",
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
    ):
        """Initialize token evaluator.
        
        Args:
            enable_llm: Enable LLM-powered analysis
            llm_provider: "openai" or "anthropic"
            openai_api_key: OpenAI API key (or from env)
            anthropic_api_key: Anthropic API key (or from env)
            model: Model to use
        """
        import os
        
        self.enable_llm = enable_llm and LLM_AVAILABLE
        self.llm_provider = llm_provider
        self.model = model
        
        if llm_provider == "openai" and OPENAI_AVAILABLE:
            self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
            if not self.openai_api_key:
                logger.warning("OpenAI API key not provided. LLM features disabled.")
                self.enable_llm = False
        elif llm_provider == "anthropic" and ANTHROPIC_AVAILABLE:
            self.anthropic_api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
            if not self.anthropic_api_key:
                logger.warning("Anthropic API key not provided. LLM features disabled.")
                self.enable_llm = False
            else:
                self.anthropic_client = anthropic.Anthropic(api_key=self.anthropic_api_key)
        else:
            if enable_llm:
                logger.warning(f"LLM provider '{llm_provider}' not available.")
            self.enable_llm = False
    
    async def evaluate_token(
        self,
        token_symbol: str,
        token_address: str,
        metadata: Optional[Dict[str, Any]] = None,
        social_signals: Optional[List[Dict[str, Any]]] = None,
        price_data: Optional[Dict[str, Any]] = None,
    ) -> TokenEvaluation:
        """Evaluate a token using AI.
        
        Args:
            token_symbol: Token symbol
            token_address: Token mint address
            metadata: Token metadata (name, description, etc.)
            social_signals: Social media signals
            price_data: Price and trading data
            
        Returns:
            Token evaluation result
        """
        if not self.enable_llm:
            # Fallback to basic evaluation
            return TokenEvaluation(
                token_symbol=token_symbol,
                token_address=token_address,
                risk_score=0.5,
                opportunity_score=0.5,
                scam_indicators=[],
                positive_indicators=[],
                trading_recommendation="hold",
                confidence=0.3,
                reasoning="LLM analysis not available",
            )
        
        try:
            # Build context for LLM
            context = self._build_context(
                token_symbol, token_address, metadata, social_signals, price_data
            )
            
            # Get LLM analysis
            analysis = await self._llm_evaluate(context)
            
            return TokenEvaluation(
                token_symbol=token_symbol,
                token_address=token_address,
                risk_score=analysis.get("risk_score", 0.5),
                opportunity_score=analysis.get("opportunity_score", 0.5),
                scam_indicators=analysis.get("scam_indicators", []),
                positive_indicators=analysis.get("positive_indicators", []),
                trading_recommendation=analysis.get("trading_recommendation", "hold"),
                confidence=analysis.get("confidence", 0.5),
                reasoning=analysis.get("reasoning", ""),
                price_prediction=analysis.get("price_prediction"),
                market_sentiment=analysis.get("market_sentiment"),
            )
        except Exception as e:
            logger.exception(f"Error evaluating token: {e}")
            return TokenEvaluation(
                token_symbol=token_symbol,
                token_address=token_address,
                risk_score=0.5,
                opportunity_score=0.5,
                scam_indicators=[],
                positive_indicators=[],
                trading_recommendation="hold",
                confidence=0.0,
                reasoning=f"Evaluation error: {str(e)}",
            )
    
    def _build_context(
        self,
        token_symbol: str,
        token_address: str,
        metadata: Optional[Dict[str, Any]],
        social_signals: Optional[List[Dict[str, Any]]],
        price_data: Optional[Dict[str, Any]],
    ) -> str:
        """Build context string for LLM."""
        context_parts = [
            f"Token: {token_symbol}",
            f"Address: {token_address}",
        ]
        
        if metadata:
            context_parts.append(f"Name: {metadata.get('name', 'N/A')}")
            context_parts.append(f"Description: {metadata.get('description', 'N/A')[:500]}")
        
        if social_signals:
            context_parts.append(f"\nSocial Signals ({len(social_signals)}):")
            for signal in social_signals[:10]:  # Limit to 10
                context_parts.append(
                    f"- {signal.get('platform', 'unknown')}: {signal.get('content', '')[:200]}"
                )
        
        if price_data:
            context_parts.append(f"\nPrice Data:")
            context_parts.append(f"- Current Price: {price_data.get('price', 'N/A')}")
            context_parts.append(f"- Volume: {price_data.get('volume', 'N/A')}")
            context_parts.append(f"- Market Cap: {price_data.get('market_cap', 'N/A')}")
        
        return "\n".join(context_parts)
    
    async def _llm_evaluate(self, context: str) -> Dict[str, Any]:
        """Evaluate token using LLM."""
        prompt = f"""You are an expert cryptocurrency analyst. Evaluate this token for trading:

{context}

Provide a JSON response with:
1. risk_score: float 0.0-1.0 (0=safe, 1=very risky/scam)
2. opportunity_score: float 0.0-1.0 (0=no opportunity, 1=high opportunity)
3. scam_indicators: array of strings (red flags like "rug pull", "honeypot", "fake team")
4. positive_indicators: array of strings (good signs like "active community", "real use case")
5. trading_recommendation: "strong_buy", "buy", "hold", "avoid", or "scam"
6. confidence: float 0.0-1.0 (confidence in analysis)
7. reasoning: string explaining the evaluation
8. price_prediction: string with short-term price prediction (optional)
9. market_sentiment: "bullish", "bearish", or "neutral" (optional)

Focus on detecting:
- Rug pulls and scams
- Honeypot contracts
- Pump and dump schemes
- Legitimate projects with potential
- Market manipulation

Respond ONLY with valid JSON, no other text."""

        try:
            if self.llm_provider == "openai" and OPENAI_AVAILABLE:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=self.openai_api_key)
                
                response = await client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert cryptocurrency trading analyst. Always respond with valid JSON only."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.2,
                    response_format={"type": "json_object"}
                )
                
                result_text = response.choices[0].message.content
                return json.loads(result_text)
                
            elif self.llm_provider == "anthropic" and ANTHROPIC_AVAILABLE:
                response = await self.anthropic_client.messages.create(
                    model=self.model,
                    max_tokens=1500,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.2,
                )
                
                result_text = response.content[0].text
                import re
                json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                else:
                    return json.loads(result_text)
            else:
                return {}
        except Exception as e:
            logger.exception(f"Error in LLM evaluation: {e}")
            return {}

