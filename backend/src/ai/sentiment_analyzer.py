"""
Sentiment Analyzer - LLM-powered sentiment analysis with manipulation detection.

Features:
- LLM integration (OpenAI/Anthropic)
- Coordinated campaign detection
- Bot account identification
- Hype pattern recognition
- AI-generated content detection
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)

# Optional LLM integration
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
class SentimentAnalysis:
    """Result of sentiment analysis."""

    overall_sentiment: str  # "positive", "neutral", "negative"
    sentiment_score: float  # -1.0 to 1.0
    confidence: float  # 0.0 to 1.0
    is_manipulated: bool
    manipulation_indicators: List[str]
    bot_accounts_detected: int
    hype_level: str  # "low", "medium", "high", "extreme"


class SentimentAnalyzer:
    """
    Advanced sentiment analyzer with LLM integration and manipulation detection.

    Analyzes:
    - Overall sentiment
    - Coordinated campaigns
    - Bot accounts
    - Hype patterns
    - AI-generated content
    """

    def __init__(
        self,
        enable_llm: bool = True,
        llm_provider: str = "openai",  # "openai" or "anthropic"
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",  # OpenAI model or "claude-3-haiku-20240307" for Anthropic
    ):
        """Initialize sentiment analyzer.

        Args:
            enable_llm: Enable LLM-powered analysis
            llm_provider: LLM provider to use ("openai" or "anthropic")
            openai_api_key: OpenAI API key (or from env OPENAI_API_KEY)
            anthropic_api_key: Anthropic API key (or from env ANTHROPIC_API_KEY)
            model: Model to use (e.g., "gpt-4o-mini", "gpt-4", "claude-3-haiku-20240307")
        """
        import os
        
        self.enable_llm = enable_llm and LLM_AVAILABLE
        self.llm_provider = llm_provider
        self.model = model
        self.analyzed_content: List[Dict[str, Any]] = []
        
        # Get API keys
        if llm_provider == "openai" and OPENAI_AVAILABLE:
            self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
            if not self.openai_api_key:
                logger.warning("OpenAI API key not provided. LLM features disabled.")
                self.enable_llm = False
            else:
                openai.api_key = self.openai_api_key
        elif llm_provider == "anthropic" and ANTHROPIC_AVAILABLE:
            self.anthropic_api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
            if not self.anthropic_api_key:
                logger.warning("Anthropic API key not provided. LLM features disabled.")
                self.enable_llm = False
            else:
                self.anthropic_client = anthropic.Anthropic(api_key=self.anthropic_api_key)
        else:
            if enable_llm:
                logger.warning(f"LLM provider '{llm_provider}' not available. Install openai or anthropic package.")
            self.enable_llm = False

    async def analyze_sentiment(
        self,
        content: str,
        source: str = "unknown",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SentimentAnalysis:
        """Analyze sentiment of content.

        Args:
            content: Content to analyze
            source: Source of content (URL, channel, etc.)
            metadata: Additional metadata

        Returns:
            Sentiment analysis result
        """
        logger.debug(f"Analyzing sentiment from {source}...")

        try:
            # Basic sentiment analysis (placeholder)
            sentiment_score = 0.0  # Would use actual analysis
            overall_sentiment = "neutral"

            # LLM-powered analysis if available
            trading_signal = None
            llm_confidence = None
            key_indicators = None
            llm_manipulation_reasons = []
            
            if self.enable_llm:
                llm_analysis = await self._llm_analyze(content)
                sentiment_score = llm_analysis.get("sentiment_score", 0.0)
                overall_sentiment = llm_analysis.get("sentiment", "neutral")
                trading_signal = llm_analysis.get("trading_signal")
                llm_confidence = llm_analysis.get("confidence")
                key_indicators = llm_analysis.get("key_indicators", [])
                
                # Merge LLM manipulation detection
                if llm_analysis.get("manipulation_detected", False):
                    llm_manipulation_reasons = llm_analysis.get("manipulation_reasons", [])

            # Detect manipulation (merge with LLM results)
            is_manipulated, indicators = await self._detect_manipulation(content)
            
            # Merge LLM manipulation indicators
            if llm_manipulation_reasons:
                indicators.extend(llm_manipulation_reasons)
                is_manipulated = True

            # Detect bot accounts
            bot_count = await self._detect_bot_accounts(content, metadata)

            # Detect hype patterns (use LLM if available, otherwise fallback)
            if self.enable_llm and llm_analysis.get("hype_level"):
                hype_level = llm_analysis.get("hype_level", "low")
            else:
                hype_level = await self._detect_hype_patterns(content)

            # Use LLM confidence if available, otherwise use default
            final_confidence = llm_confidence if llm_confidence is not None else 0.7
            
            analysis = SentimentAnalysis(
                overall_sentiment=overall_sentiment,
                sentiment_score=sentiment_score,
                confidence=final_confidence,
                is_manipulated=is_manipulated,
                manipulation_indicators=indicators,
                bot_accounts_detected=bot_count,
                hype_level=hype_level,
                trading_signal=trading_signal,
                llm_confidence=llm_confidence,
                key_indicators=key_indicators,
            )

            self.analyzed_content.append(
                {
                    "content": content[:100],  # Store preview
                    "source": source,
                    "analysis": analysis,
                }
            )

            if is_manipulated:
                logger.warning(
                    f"Manipulation detected in content from {source}: {indicators}"
                )

            return analysis

        except Exception as e:
            logger.exception(f"Error analyzing sentiment: {e}")
            return SentimentAnalysis(
                overall_sentiment="neutral",
                sentiment_score=0.0,
                confidence=0.0,
                is_manipulated=False,
                manipulation_indicators=[],
                bot_accounts_detected=0,
                hype_level="low",
            )

    async def _llm_analyze(self, content: str) -> Dict[str, Any]:
        """Analyze content using LLM.

        Args:
            content: Content to analyze

        Returns:
            LLM analysis results
        """
        if not self.enable_llm:
            return {}

        try:
            prompt = f"""Analyze this cryptocurrency/token social media content for trading signals:

Content: "{content[:2000]}"

Provide a JSON response with:
1. sentiment: "positive", "neutral", or "negative"
2. sentiment_score: float from -1.0 (very negative) to 1.0 (very positive)
3. manipulation_detected: boolean (true if appears to be pump scheme, bot activity, or manipulation)
4. manipulation_reasons: array of strings explaining why manipulation is suspected
5. hype_level: "low", "medium", "high", or "extreme"
6. trading_signal: "strong_buy", "buy", "hold", "sell", or "strong_sell"
7. confidence: float from 0.0 to 1.0
8. key_indicators: array of important signals (e.g., "coordinated posting", "fake engagement", "genuine community interest")

Focus on detecting:
- Pump and dump schemes
- Coordinated campaigns
- Bot-generated content
- Fake engagement
- Genuine community interest vs manipulation

Respond ONLY with valid JSON, no other text."""

            if self.llm_provider == "openai" and OPENAI_AVAILABLE:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=self.openai_api_key)
                
                response = await client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert cryptocurrency trading analyst specializing in detecting market manipulation and genuine trading opportunities. Always respond with valid JSON only."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.3,
                    response_format={"type": "json_object"}
                )
                
                result_text = response.choices[0].message.content
                import json
                result = json.loads(result_text)
                
                return {
                    "sentiment": result.get("sentiment", "neutral"),
                    "sentiment_score": float(result.get("sentiment_score", 0.0)),
                    "manipulation_detected": result.get("manipulation_detected", False),
                    "manipulation_reasons": result.get("manipulation_reasons", []),
                    "hype_level": result.get("hype_level", "low"),
                    "trading_signal": result.get("trading_signal", "hold"),
                    "confidence": float(result.get("confidence", 0.5)),
                    "key_indicators": result.get("key_indicators", []),
                }
                
            elif self.llm_provider == "anthropic" and ANTHROPIC_AVAILABLE:
                response = await self.anthropic_client.messages.create(
                    model=self.model,
                    max_tokens=1000,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.3,
                )
                
                result_text = response.content[0].text
                import json
                # Extract JSON from response
                import re
                json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    result = json.loads(result_text)
                
                return {
                    "sentiment": result.get("sentiment", "neutral"),
                    "sentiment_score": float(result.get("sentiment_score", 0.0)),
                    "manipulation_detected": result.get("manipulation_detected", False),
                    "manipulation_reasons": result.get("manipulation_reasons", []),
                    "hype_level": result.get("hype_level", "low"),
                    "trading_signal": result.get("trading_signal", "hold"),
                    "confidence": float(result.get("confidence", 0.5)),
                    "key_indicators": result.get("key_indicators", []),
                }
            else:
                return {}

        except Exception as e:
            logger.exception(f"Error in LLM analysis: {e}")
            return {}

    async def _detect_manipulation(
        self, content: str
    ) -> tuple[bool, List[str]]:
        """Detect manipulation in content.

        Args:
            content: Content to analyze

        Returns:
            Tuple of (is_manipulated, indicators)
        """
        indicators: List[str] = []

        try:
            # Check for coordinated campaign patterns
            if "pump" in content.lower() and "moon" in content.lower():
                indicators.append("Pump and moon language detected")

            # Check for AI-generated content patterns
            if self._is_ai_generated(content):
                indicators.append("AI-generated content detected")

            # Check for hype patterns
            hype_words = ["🚀", "moon", "gem", "100x", "to the moon"]
            hype_count = sum(1 for word in hype_words if word.lower() in content.lower())
            if hype_count >= 3:
                indicators.append("Extreme hype language detected")

            return len(indicators) > 0, indicators

        except Exception as e:
            logger.exception(f"Error detecting manipulation: {e}")
            return False, []

    def _is_ai_generated(self, content: str) -> bool:
        """Detect if content is AI-generated.

        Args:
            content: Content to check

        Returns:
            True if likely AI-generated
        """
        # Simple heuristics (would use actual AI detection model)
        ai_patterns = [
            "as an ai",
            "i'm an ai",
            "i cannot",
            "i don't have",
        ]

        content_lower = content.lower()
        return any(pattern in content_lower for pattern in ai_patterns)

    async def _detect_bot_accounts(
        self, content: str, metadata: Optional[Dict[str, Any]]
    ) -> int:
        """Detect bot accounts in content.

        Args:
            content: Content to analyze
            metadata: Additional metadata

        Returns:
            Number of bot accounts detected
        """
        try:
            # In production, this would:
            # 1. Analyze account patterns
            # 2. Check for bot-like behavior
            # 3. Return bot count

            # Placeholder
            return 0

        except Exception as e:
            logger.exception(f"Error detecting bot accounts: {e}")
            return 0

    async def _detect_hype_patterns(self, content: str) -> str:
        """Detect hype level in content.

        Args:
            content: Content to analyze

        Returns:
            Hype level ("low", "medium", "high", "extreme")
        """
        try:
            hype_words = ["🚀", "moon", "gem", "100x", "to the moon", "pump"]
            hype_count = sum(1 for word in hype_words if word.lower() in content.lower())

            if hype_count >= 5:
                return "extreme"
            elif hype_count >= 3:
                return "high"
            elif hype_count >= 1:
                return "medium"
            else:
                return "low"

        except Exception as e:
            logger.exception(f"Error detecting hype patterns: {e}")
            return "low"

    def get_statistics(self) -> Dict[str, Any]:
        """Get sentiment analyzer statistics.

        Returns:
            Statistics dictionary
        """
        total_analyzed = len(self.analyzed_content)
        manipulated = sum(
            1 for item in self.analyzed_content if item["analysis"].is_manipulated
        )

        return {
            "total_analyzed": total_analyzed,
            "manipulated_detected": manipulated,
            "llm_enabled": self.enable_llm,
            "llm_provider": self.llm_provider if self.enable_llm else None,
        }

