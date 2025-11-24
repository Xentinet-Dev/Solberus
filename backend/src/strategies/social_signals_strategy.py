"""
Social Signals Strategy - Trade based on social media signals

Analyzes social media mentions, sentiment, and virality to identify trending tokens.
Integrates with Twitter, Telegram, Discord, and Reddit scanners.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import time
import logging

from .base_strategy import (
    BaseStrategy,
    StrategySignal,
    StrategyConfig,
    StrategyType
)

logger = logging.getLogger(__name__)


@dataclass
class SocialSignalsConfig(StrategyConfig):
    """Configuration specific to social signals strategy"""
    # Virality settings
    min_virality_score: float = 80.0  # Minimum virality score (0-100)
    virality_spike_threshold: float = 50.0  # Spike from baseline

    # Sentiment settings
    min_sentiment_score: float = 0.70  # Minimum positive sentiment (0-1)
    sentiment_threshold: float = 0.60  # Min sentiment to not exit

    # Mention settings
    min_mention_count: int = 10  # Minimum mentions across platforms
    mention_window: int = 600  # Time window for mentions (10 minutes)
    min_platforms: int = 2  # Minimum number of platforms mentioning

    # Influencer settings
    require_influencer: bool = False  # Require at least one influencer mention
    influencer_weight: float = 2.0  # Weight multiplier for influencer mentions
    min_influencer_followers: int = 10000  # Minimum followers to be considered influencer

    # Bot detection
    filter_bot_mentions: bool = True  # Filter out bot-driven mentions
    max_bot_ratio: float = 0.30  # Maximum acceptable bot mention ratio (30%)

    # Scam detection
    filter_scam_keywords: bool = True  # Filter tokens with scam keywords
    scam_keywords: List[str] = None  # Custom scam keywords

    # Timing
    max_signal_age: int = 300  # Only act on signals < 5 minutes old
    signal_freshness_bonus: float = 0.10  # Bonus confidence for fresh signals

    # Exit signals
    sentiment_reversal_threshold: float = -0.20  # Exit if sentiment drops 20%
    virality_decay_threshold: float = -0.30  # Exit if virality drops 30%

    def __post_init__(self):
        if self.scam_keywords is None:
            self.scam_keywords = [
                "honeypot", "scam", "rug", "fake", "steal",
                "guaranteed", "100x", "moonshot guaranteed", "insider"
            ]


@dataclass
class SocialSignal:
    """Social signal data"""
    token_address: str
    virality_score: float  # 0-100
    sentiment_score: float  # 0-1
    mention_count: int
    platforms: List[str]  # ["twitter", "telegram", "discord", "reddit"]
    influencer_mentions: int
    bot_ratio: float  # 0-1
    top_keywords: List[str]
    timestamp: float
    signal_strength: float  # Overall signal strength 0-1


class SocialSignalsStrategy(BaseStrategy):
    """
    Social Signals Strategy - Trade on social momentum

    Entry Criteria:
    - Virality score > min_virality_score
    - Positive sentiment > min_sentiment_score
    - Mentions >= min_mention_count across min_platforms
    - Bot ratio < max_bot_ratio
    - No scam keywords (if filter enabled)
    - Signal fresh (< max_signal_age)

    Exit Criteria:
    - Sentiment reverses (drops by sentiment_reversal_threshold)
    - Virality decays (drops by virality_decay_threshold)
    - Standard: Stop-loss, take-profit, max hold time
    """

    def __init__(self, config: SocialSignalsConfig = None):
        if config is None:
            config = SocialSignalsConfig()

        super().__init__(config, StrategyType.SOCIAL_SIGNALS)
        self.social_config: SocialSignalsConfig = config

        # Track social signals: token_address -> SocialSignal
        self._social_signals: Dict[str, SocialSignal] = {}

        # Track baseline virality for tokens: token_address -> baseline_virality
        self._virality_baseline: Dict[str, float] = {}

        # Track sentiment history for reversal detection: token_address -> [(timestamp, sentiment)]
        self._sentiment_history: Dict[str, List[tuple]] = {}

        logger.info(
            f"SocialSignalsStrategy initialized: "
            f"min_virality={config.min_virality_score}, "
            f"min_sentiment={config.min_sentiment_score:.0%}, "
            f"min_platforms={config.min_platforms}"
        )

    def _calculate_signal_strength(self, social_data: Dict[str, Any]) -> float:
        """Calculate overall signal strength (0-1)"""
        virality = social_data.get("virality_score", 0.0) / 100.0  # Normalize to 0-1
        sentiment = social_data.get("sentiment_score", 0.0)
        mention_count = social_data.get("mention_count", 0)
        platforms = len(social_data.get("platforms", []))
        influencer_mentions = social_data.get("influencer_mentions", 0)
        bot_ratio = social_data.get("bot_ratio", 0.0)

        # Weighted calculation
        signal = (
            virality * 0.35 +  # 35% weight on virality
            sentiment * 0.30 +  # 30% weight on sentiment
            min(mention_count / 50.0, 1.0) * 0.15 +  # 15% weight on mentions (capped at 50)
            min(platforms / 4.0, 1.0) * 0.10 +  # 10% weight on platform diversity
            min(influencer_mentions / 5.0, 1.0) * 0.10  # 10% weight on influencers (capped at 5)
        )

        # Penalty for bots
        bot_penalty = bot_ratio * 0.3  # Up to 30% penalty
        signal = max(0.0, signal - bot_penalty)

        return signal

    def _detect_scam_keywords(self, keywords: List[str]) -> bool:
        """Check if token mentions contain scam keywords"""
        if not self.social_config.filter_scam_keywords:
            return False

        keywords_lower = [k.lower() for k in keywords]
        for scam_keyword in self.social_config.scam_keywords:
            if scam_keyword.lower() in keywords_lower:
                logger.warning(f"Scam keyword detected: {scam_keyword}")
                return True

        return False

    def _update_sentiment_history(self, token_address: str, sentiment: float, timestamp: float):
        """Update sentiment history for reversal detection"""
        if token_address not in self._sentiment_history:
            self._sentiment_history[token_address] = []

        self._sentiment_history[token_address].append((timestamp, sentiment))

        # Keep only last 20 data points
        self._sentiment_history[token_address] = self._sentiment_history[token_address][-20:]

    def _detect_sentiment_reversal(self, token_address: str, current_sentiment: float) -> bool:
        """Detect if sentiment has reversed (dropped significantly)"""
        if token_address not in self._sentiment_history:
            return False

        history = self._sentiment_history[token_address]
        if len(history) < 3:
            return False  # Need enough history

        # Get recent average sentiment (exclude current)
        recent_sentiments = [s for _, s in history[-5:-1]] if len(history) > 1 else []
        if not recent_sentiments:
            return False

        avg_recent_sentiment = sum(recent_sentiments) / len(recent_sentiments)

        # Calculate sentiment change
        sentiment_change = current_sentiment - avg_recent_sentiment

        if sentiment_change <= self.social_config.sentiment_reversal_threshold:
            logger.warning(
                f"Sentiment reversal detected for {token_address}: "
                f"{sentiment_change:.2%} drop"
            )
            return True

        return False

    async def analyze(self, market_data: Dict[str, Any]) -> StrategySignal:
        """Analyze social signals and return trading signal"""
        # Extract social signal data
        social_data = market_data.get("social_signals")
        if not social_data:
            return StrategySignal(
                strategy_name=self.name,
                action="hold",
                confidence=0.0,
                position_size=0.0,
                reason="No social signals available",
                metadata={}
            )

        token_address = market_data.get("token_address", "unknown")
        available_capital = market_data.get("available_capital", 0.0)
        security_score = market_data.get("security_score", 0)

        # Extract social metrics
        virality_score = social_data.get("virality_score", 0.0)
        sentiment_score = social_data.get("sentiment_score", 0.0)
        mention_count = social_data.get("mention_count", 0)
        platforms = social_data.get("platforms", [])
        influencer_mentions = social_data.get("influencer_mentions", 0)
        bot_ratio = social_data.get("bot_ratio", 0.0)
        top_keywords = social_data.get("top_keywords", [])
        signal_timestamp = social_data.get("timestamp", time.time())

        # Update sentiment history
        self._update_sentiment_history(token_address, sentiment_score, signal_timestamp)

        # Check signal freshness
        signal_age = time.time() - signal_timestamp
        if signal_age > self.social_config.max_signal_age:
            return StrategySignal(
                strategy_name=self.name,
                action="hold",
                confidence=0.0,
                position_size=0.0,
                reason=f"Signal too old ({signal_age:.0f}s > {self.social_config.max_signal_age}s)",
                metadata={"token_address": token_address}
            )

        # Check for scam keywords
        if self._detect_scam_keywords(top_keywords):
            return StrategySignal(
                strategy_name=self.name,
                action="hold",
                confidence=0.0,
                position_size=0.0,
                reason="Scam keywords detected",
                metadata={"token_address": token_address, "keywords": top_keywords}
            )

        # Entry checks
        checks = {
            "virality_high": virality_score >= self.social_config.min_virality_score,
            "sentiment_positive": sentiment_score >= self.social_config.min_sentiment_score,
            "mentions_sufficient": mention_count >= self.social_config.min_mention_count,
            "platforms_diverse": len(platforms) >= self.social_config.min_platforms,
            "bot_ratio_ok": bot_ratio <= self.social_config.max_bot_ratio,
            "security_ok": security_score >= 50,
        }

        # Optional: Influencer requirement
        if self.social_config.require_influencer:
            checks["influencer_mentioned"] = influencer_mentions > 0
        else:
            checks["influencer_mentioned"] = True  # Not required

        # Check virality spike
        if token_address in self._virality_baseline:
            baseline = self._virality_baseline[token_address]
            virality_spike = virality_score - baseline
            checks["virality_spike"] = virality_spike >= self.social_config.virality_spike_threshold
        else:
            # First time seeing this token, set baseline
            self._virality_baseline[token_address] = virality_score
            checks["virality_spike"] = True  # Assume OK for first observation

        # Calculate confidence
        passed_checks = sum(checks.values())
        total_checks = len(checks)
        base_confidence = passed_checks / total_checks

        # Calculate signal strength
        signal_strength = self._calculate_signal_strength(social_data)

        # Combine base confidence with signal strength
        confidence = (base_confidence * 0.5) + (signal_strength * 0.5)

        # Bonus for fresh signals
        if signal_age < 60:  # < 1 minute
            confidence = min(1.0, confidence + self.social_config.signal_freshness_bonus)

        # Bonus for influencer mentions
        if influencer_mentions > 0:
            influencer_bonus = min(0.10, influencer_mentions * 0.02)  # 2% per influencer, max 10%
            confidence = min(1.0, confidence + influencer_bonus)

        logger.debug(
            f"Social signals analysis for {token_address}: "
            f"virality={virality_score:.1f}, sentiment={sentiment_score:.2f}, "
            f"mentions={mention_count}, platforms={len(platforms)}, "
            f"confidence={confidence:.0%}"
        )

        # Store signal
        self._social_signals[token_address] = SocialSignal(
            token_address=token_address,
            virality_score=virality_score,
            sentiment_score=sentiment_score,
            mention_count=mention_count,
            platforms=platforms,
            influencer_mentions=influencer_mentions,
            bot_ratio=bot_ratio,
            top_keywords=top_keywords,
            timestamp=signal_timestamp,
            signal_strength=signal_strength,
        )

        # Decision: Enter or hold
        if confidence >= self.config.min_confidence and available_capital > 0:
            position_size = self.calculate_position_size(available_capital, market_data)

            if position_size < 0.1:
                return StrategySignal(
                    strategy_name=self.name,
                    action="hold",
                    confidence=confidence,
                    position_size=0.0,
                    reason="Position size too small",
                    metadata={"token_address": token_address}
                )

            return StrategySignal(
                strategy_name=self.name,
                action="buy",
                confidence=confidence,
                position_size=position_size,
                reason=f"Social signal detected: virality={virality_score:.1f}, sentiment={sentiment_score:.0%}, platforms={len(platforms)}",
                metadata={
                    "token_address": token_address,
                    "checks": checks,
                    "virality_score": virality_score,
                    "sentiment_score": sentiment_score,
                    "mention_count": mention_count,
                    "platforms": platforms,
                    "influencer_mentions": influencer_mentions,
                    "bot_ratio": bot_ratio,
                    "signal_strength": signal_strength,
                    "signal_age": signal_age,
                }
            )

        # No strong signal
        failed_checks = [k for k, v in checks.items() if not v]
        return StrategySignal(
            strategy_name=self.name,
            action="hold",
            confidence=confidence,
            position_size=0.0,
            reason=f"Failed checks: {', '.join(failed_checks)}",
            metadata={
                "token_address": token_address,
                "checks": checks,
                "virality_score": virality_score,
                "sentiment_score": sentiment_score,
            }
        )

    async def should_enter(self, token_address: str, market_data: Dict[str, Any]) -> bool:
        """Check if we should enter based on social signals"""
        signal = await self.analyze(market_data)
        return signal.action == "buy" and signal.confidence >= self.config.min_confidence

    async def should_exit(self, position: Dict[str, Any], market_data: Dict[str, Any]) -> bool:
        """Check if we should exit based on social signal changes"""
        current_price = market_data.get("price", 0.0)
        current_time = time.time()

        # Check standard exit conditions
        should_exit, reason = self.check_exit_conditions(position, current_price, current_time)
        if should_exit:
            logger.info(f"Social signals exit triggered: {reason}")
            return True

        # Social-specific exit conditions
        token_address = position.get("token_address")

        # Get current social signals
        social_data = market_data.get("social_signals", {})
        current_sentiment = social_data.get("sentiment_score", 1.0)
        current_virality = social_data.get("virality_score", 100.0)

        # Check for sentiment reversal
        if self._detect_sentiment_reversal(token_address, current_sentiment):
            logger.info(f"Social signals exit: Sentiment reversed for {token_address}")
            return True

        # Check for virality decay
        if token_address in self._social_signals:
            entry_signal = self._social_signals[token_address]
            virality_change = (current_virality - entry_signal.virality_score) / entry_signal.virality_score

            if virality_change <= self.social_config.virality_decay_threshold:
                logger.info(
                    f"Social signals exit: Virality decayed {virality_change:.0%} "
                    f"for {token_address}"
                )
                return True

        # Exit if sentiment drops below threshold
        if current_sentiment < self.social_config.sentiment_threshold:
            logger.info(
                f"Social signals exit: Sentiment dropped to {current_sentiment:.0%} "
                f"for {token_address}"
            )
            return True

        return False

    def get_active_signals(self) -> Dict[str, SocialSignal]:
        """Get all active social signals"""
        return self._social_signals.copy()

    def clear_history(self, token_address: str = None):
        """Clear social signal history"""
        if token_address:
            self._social_signals.pop(token_address, None)
            self._virality_baseline.pop(token_address, None)
            self._sentiment_history.pop(token_address, None)
            logger.info(f"Cleared social signals history for {token_address}")
        else:
            self._social_signals.clear()
            self._virality_baseline.clear()
            self._sentiment_history.clear()
            logger.info("Cleared all social signals history")
