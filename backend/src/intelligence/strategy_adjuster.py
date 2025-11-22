"""
Strategy Adjuster - Automatically adjusts trading strategies based on social signals.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from interfaces.core import TokenInfo
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class StrategyAdjustment:
    """Strategy adjustment based on social signals."""
    
    token_address: str
    adjustment_type: str  # "buy_more", "sell_early", "hold_longer", "skip"
    confidence: float  # 0.0 to 1.0
    reason: str
    social_momentum: float  # -1.0 (negative) to 1.0 (positive)
    recommended_buy_amount_multiplier: float = 1.0  # Multiply base buy amount
    recommended_hold_time_multiplier: float = 1.0  # Multiply base hold time


class StrategyAdjuster:
    """
    Automatically adjusts trading strategies based on social media signals.
    
    Features:
    - Real-time social momentum tracking
    - Strategy adjustment recommendations
    - Risk-based position sizing
    - Hold time optimization
    """
    
    def __init__(
        self,
        base_buy_amount: float = 0.001,
        base_hold_time: int = 300,
        momentum_threshold: float = 0.7,  # High momentum threshold
        negative_momentum_threshold: float = -0.5,  # Negative momentum threshold
    ):
        """Initialize strategy adjuster.
        
        Args:
            base_buy_amount: Base SOL amount per trade
            base_hold_time: Base hold time in seconds
            momentum_threshold: Threshold for high positive momentum
            negative_momentum_threshold: Threshold for negative momentum
        """
        self.base_buy_amount = base_buy_amount
        self.base_hold_time = base_hold_time
        self.momentum_threshold = momentum_threshold
        self.negative_momentum_threshold = negative_momentum_threshold
        
        # Track social momentum per token
        self.token_momentum: Dict[str, List[float]] = {}  # {token: [momentum_scores]}
        self.token_signals: Dict[str, List[Dict[str, Any]]] = {}  # {token: [signals]}
    
    def update_social_signals(
        self,
        token_address: str,
        signals: List[Dict[str, Any]],
    ):
        """Update social signals for a token.
        
        Args:
            token_address: Token mint address
            signals: List of social signals (from SocialSignal)
        """
        if token_address not in self.token_signals:
            self.token_signals[token_address] = []
        
        # Add new signals
        for signal in signals:
            signal_dict = {
                "platform": signal.get("platform", "unknown"),
                "sentiment": signal.get("sentiment", "neutral"),
                "engagement": signal.get("engagement_score", 0.0),
                "virality": signal.get("virality_score", 0.0),
                "timestamp": signal.get("timestamp", datetime.utcnow()),
            }
            self.token_signals[token_address].append(signal_dict)
        
        # Keep only recent signals (last hour)
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        self.token_signals[token_address] = [
            s for s in self.token_signals[token_address]
            if s["timestamp"] > cutoff_time
        ]
        
        # Calculate momentum
        momentum = self._calculate_momentum(token_address)
        if token_address not in self.token_momentum:
            self.token_momentum[token_address] = []
        self.token_momentum[token_address].append(momentum)
        
        # Keep only recent momentum scores (last 10)
        if len(self.token_momentum[token_address]) > 10:
            self.token_momentum[token_address] = self.token_momentum[token_address][-10:]
    
    def _calculate_momentum(self, token_address: str) -> float:
        """Calculate social momentum for a token.
        
        Args:
            token_address: Token mint address
            
        Returns:
            Momentum score (-1.0 to 1.0)
        """
        if token_address not in self.token_signals:
            return 0.0
        
        signals = self.token_signals[token_address]
        if not signals:
            return 0.0
        
        # Weighted momentum calculation
        total_momentum = 0.0
        total_weight = 0.0
        
        for signal in signals:
            # Sentiment weight
            sentiment_score = {
                "positive": 1.0,
                "neutral": 0.0,
                "negative": -1.0,
            }.get(signal.get("sentiment", "neutral"), 0.0)
            
            # Engagement weight
            engagement = signal.get("engagement", 0.0)
            virality = signal.get("virality", 0.0)
            
            # Combined weight
            weight = engagement * 0.6 + virality * 0.4
            
            total_momentum += sentiment_score * weight
            total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        momentum = total_momentum / total_weight
        return max(-1.0, min(1.0, momentum))  # Clamp to [-1, 1]
    
    def get_current_momentum(self, token_address: str) -> float:
        """Get current social momentum for a token.
        
        Args:
            token_address: Token mint address
            
        Returns:
            Current momentum score (-1.0 to 1.0)
        """
        if token_address not in self.token_momentum or not self.token_momentum[token_address]:
            return 0.0
        
        # Return most recent momentum
        return self.token_momentum[token_address][-1]
    
    async def get_strategy_adjustment(
        self,
        token_info: TokenInfo,
    ) -> Optional[StrategyAdjustment]:
        """Get strategy adjustment recommendation for a token.
        
        Args:
            token_info: Token information
            
        Returns:
            Strategy adjustment recommendation or None
        """
        token_address = str(token_info.mint)
        momentum = self.get_current_momentum(token_address)
        
        # Determine adjustment type
        if momentum >= self.momentum_threshold:
            # High positive momentum - buy more, hold longer
            adjustment = StrategyAdjustment(
                token_address=token_address,
                adjustment_type="buy_more",
                confidence=min(momentum, 1.0),
                reason=f"High positive social momentum ({momentum:.2f})",
                social_momentum=momentum,
                recommended_buy_amount_multiplier=1.0 + (momentum * 0.5),  # Up to 1.5x
                recommended_hold_time_multiplier=1.0 + (momentum * 0.3),  # Up to 1.3x
            )
            logger.info(
                f"📈 High momentum detected for {token_info.symbol}: "
                f"Recommend buying {adjustment.recommended_buy_amount_multiplier:.2f}x more, "
                f"holding {adjustment.recommended_hold_time_multiplier:.2f}x longer"
            )
            return adjustment
        
        elif momentum <= self.negative_momentum_threshold:
            # Negative momentum - sell early or skip
            adjustment = StrategyAdjustment(
                token_address=token_address,
                adjustment_type="sell_early",
                confidence=abs(momentum),
                reason=f"Negative social momentum ({momentum:.2f})",
                social_momentum=momentum,
                recommended_buy_amount_multiplier=0.0,  # Skip trade
                recommended_hold_time_multiplier=0.5,  # Hold half as long
            )
            logger.warning(
                f"📉 Negative momentum detected for {token_info.symbol}: "
                f"Recommend skipping or selling early"
            )
            return adjustment
        
        elif momentum > 0.3:
            # Moderate positive momentum - slight increase
            adjustment = StrategyAdjustment(
                token_address=token_address,
                adjustment_type="hold_longer",
                confidence=momentum,
                reason=f"Moderate positive momentum ({momentum:.2f})",
                social_momentum=momentum,
                recommended_buy_amount_multiplier=1.0 + (momentum * 0.2),  # Up to 1.2x
                recommended_hold_time_multiplier=1.0 + (momentum * 0.2),  # Up to 1.2x
            )
            return adjustment
        
        # No significant momentum - no adjustment
        return None
    
    def get_adjusted_buy_amount(
        self,
        token_address: str,
        base_amount: Optional[float] = None,
    ) -> float:
        """Get adjusted buy amount based on social momentum.
        
        Args:
            token_address: Token mint address
            base_amount: Base buy amount (uses self.base_buy_amount if None)
            
        Returns:
            Adjusted buy amount
        """
        base = base_amount or self.base_buy_amount
        momentum = self.get_current_momentum(token_address)
        
        if momentum >= self.momentum_threshold:
            # High momentum - increase buy amount
            multiplier = 1.0 + (momentum * 0.5)
            return base * multiplier
        elif momentum <= self.negative_momentum_threshold:
            # Negative momentum - skip (return 0)
            return 0.0
        elif momentum > 0.3:
            # Moderate momentum - slight increase
            multiplier = 1.0 + (momentum * 0.2)
            return base * multiplier
        
        return base
    
    def get_adjusted_hold_time(
        self,
        token_address: str,
        base_hold_time: Optional[int] = None,
    ) -> int:
        """Get adjusted hold time based on social momentum.
        
        Args:
            token_address: Token mint address
            base_hold_time: Base hold time in seconds
            
        Returns:
            Adjusted hold time in seconds
        """
        base = base_hold_time or self.base_hold_time
        momentum = self.get_current_momentum(token_address)
        
        if momentum >= self.momentum_threshold:
            # High momentum - hold longer
            multiplier = 1.0 + (momentum * 0.3)
            return int(base * multiplier)
        elif momentum <= self.negative_momentum_threshold:
            # Negative momentum - hold shorter
            multiplier = 0.5
            return int(base * multiplier)
        elif momentum > 0.3:
            # Moderate momentum - slight increase
            multiplier = 1.0 + (momentum * 0.2)
            return int(base * multiplier)
        
        return base

