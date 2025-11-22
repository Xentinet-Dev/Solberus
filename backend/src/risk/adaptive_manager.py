"""
Adaptive Risk Manager - Dynamic risk management based on market conditions.

Features:
- Dynamic stop-loss calculation
- Volatility-based adjustments
- Sentiment-based risk
- Market state adaptation
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RiskParameters:
    """Adaptive risk parameters."""

    stop_loss_percentage: float
    take_profit_percentage: float
    max_position_size: float  # SOL
    risk_multiplier: float  # 0.0 to 2.0
    volatility_adjustment: float  # -1.0 to 1.0
    sentiment_adjustment: float  # -1.0 to 1.0


class AdaptiveRiskManager:
    """
    Adaptive risk management that adjusts based on market conditions.

    Adapts:
    - Stop-loss based on volatility
    - Position sizing based on risk
    - Risk levels based on sentiment
    - Parameters based on market state
    """

    def __init__(
        self,
        base_stop_loss: float = 0.10,  # 10%
        base_take_profit: float = 0.20,  # 20%
        base_max_position: float = 1.0,  # SOL
        volatility_sensitivity: float = 0.5,
        sentiment_sensitivity: float = 0.3,
    ):
        """Initialize adaptive risk manager.

        Args:
            base_stop_loss: Base stop-loss percentage
            base_take_profit: Base take-profit percentage
            base_max_position: Base maximum position size
            volatility_sensitivity: How much volatility affects risk
            sentiment_sensitivity: How much sentiment affects risk
        """
        self.base_stop_loss = base_stop_loss
        self.base_take_profit = base_take_profit
        self.base_max_position = base_max_position
        self.volatility_sensitivity = volatility_sensitivity
        self.sentiment_sensitivity = sentiment_sensitivity
        self.current_risk_params: Optional[RiskParameters] = None

    def calculate_adaptive_risk(
        self,
        volatility: float = 0.1,
        sentiment_score: float = 0.0,  # -1.0 to 1.0
        market_state: str = "normal",  # "bull", "bear", "normal", "volatile"
    ) -> RiskParameters:
        """Calculate adaptive risk parameters.

        Args:
            volatility: Current volatility (0.0 to 1.0)
            sentiment_score: Sentiment score (-1.0 to 1.0)
            market_state: Current market state

        Returns:
            Adaptive risk parameters
        """
        # Volatility adjustment
        # Higher volatility = tighter stop-loss
        volatility_adjustment = -volatility * self.volatility_sensitivity
        stop_loss = max(
            0.05, self.base_stop_loss * (1.0 + volatility_adjustment)
        )  # Min 5%

        # Sentiment adjustment
        # Negative sentiment = tighter stop-loss
        sentiment_adjustment = -sentiment_score * self.sentiment_sensitivity
        stop_loss = stop_loss * (1.0 + sentiment_adjustment)

        # Market state adjustment
        market_multipliers = {
            "bull": 1.2,  # Increase risk in bull market
            "bear": 0.8,  # Decrease risk in bear market
            "volatile": 0.7,  # Decrease risk in volatile market
            "normal": 1.0,
        }
        risk_multiplier = market_multipliers.get(market_state, 1.0)

        # Adjust position size based on risk
        max_position = self.base_max_position * risk_multiplier

        # Take profit adjustment (less aggressive in volatile markets)
        take_profit = self.base_take_profit * risk_multiplier

        risk_params = RiskParameters(
            stop_loss_percentage=stop_loss,
            take_profit_percentage=take_profit,
            max_position_size=max_position,
            risk_multiplier=risk_multiplier,
            volatility_adjustment=volatility_adjustment,
            sentiment_adjustment=sentiment_adjustment,
        )

        self.current_risk_params = risk_params

        logger.debug(
            f"Adaptive risk calculated: SL={stop_loss:.1%}, "
            f"TP={take_profit:.1%}, MaxPos={max_position:.4f} SOL"
        )

        return risk_params

    def get_current_risk(self) -> Optional[RiskParameters]:
        """Get current risk parameters.

        Returns:
            Current risk parameters if set, None otherwise
        """
        return self.current_risk_params

