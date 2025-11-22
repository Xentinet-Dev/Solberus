"""
Position Sizer - Kelly Criterion and risk-adjusted position sizing.

Features:
- Kelly Criterion implementation
- Risk-adjusted sizing
- Capital efficiency optimization
"""

import math
from dataclasses import dataclass
from typing import Any, Dict, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PositionSize:
    """Calculated position size."""

    size: float  # SOL
    kelly_fraction: float  # Kelly Criterion fraction
    risk_adjusted: bool
    confidence: float  # 0.0 to 1.0


class PositionSizer:
    """
    Position sizing using Kelly Criterion and risk adjustment.

    Calculates optimal position sizes based on:
    - Win rate
    - Average win/loss ratio
    - Risk tolerance
    - Capital efficiency
    """

    def __init__(
        self,
        total_capital: float = 10.0,  # SOL
        risk_tolerance: float = 0.25,  # Fraction of Kelly (25% = quarter Kelly)
        min_position: float = 0.01,  # Minimum position size
        max_position: float = 2.0,  # Maximum position size
    ):
        """Initialize position sizer.

        Args:
            total_capital: Total capital available
            risk_tolerance: Risk tolerance (fraction of Kelly)
            min_position: Minimum position size
            max_position: Maximum position size
        """
        self.total_capital = total_capital
        self.risk_tolerance = risk_tolerance
        self.min_position = min_position
        self.max_position = max_position

    def calculate_kelly_size(
        self,
        win_rate: float,  # 0.0 to 1.0
        avg_win: float,  # Average win amount
        avg_loss: float,  # Average loss amount
        confidence: float = 1.0,  # Confidence in the trade
    ) -> PositionSize:
        """Calculate position size using Kelly Criterion.

        Args:
            win_rate: Historical win rate
            avg_win: Average win amount
            avg_loss: Average loss amount
            confidence: Confidence in this specific trade

        Returns:
            Calculated position size
        """
        try:
            # Kelly Criterion: f = (p * b - q) / b
            # where:
            #   f = fraction of capital to bet
            #   p = probability of winning
            #   q = probability of losing (1 - p)
            #   b = win/loss ratio

            if avg_loss == 0:
                logger.warning("Average loss is zero, using conservative sizing")
                kelly_fraction = 0.01  # 1% conservative
            else:
                win_loss_ratio = avg_win / abs(avg_loss)
                q = 1.0 - win_rate

                # Kelly fraction
                kelly_fraction = (win_rate * win_loss_ratio - q) / win_loss_ratio

                # Ensure non-negative
                kelly_fraction = max(0.0, kelly_fraction)

            # Apply risk tolerance (fractional Kelly)
            adjusted_fraction = kelly_fraction * self.risk_tolerance

            # Apply confidence
            confidence_adjusted = adjusted_fraction * confidence

            # Calculate position size
            position_size = self.total_capital * confidence_adjusted

            # Apply min/max constraints
            position_size = max(self.min_position, min(position_size, self.max_position))

            logger.debug(
                f"Kelly sizing: win_rate={win_rate:.2%}, "
                f"kelly_fraction={kelly_fraction:.2%}, "
                f"position_size={position_size:.6f} SOL"
            )

            return PositionSize(
                size=position_size,
                kelly_fraction=kelly_fraction,
                risk_adjusted=True,
                confidence=confidence,
            )

        except Exception as e:
            logger.exception(f"Error calculating Kelly size: {e}")
            # Fallback to conservative sizing
            return PositionSize(
                size=self.min_position,
                kelly_fraction=0.0,
                risk_adjusted=False,
                confidence=0.0,
            )

    def calculate_risk_adjusted_size(
        self,
        base_size: float,
        risk_level: str,  # "low", "medium", "high", "critical"
        confidence: float = 1.0,
    ) -> PositionSize:
        """Calculate risk-adjusted position size.

        Args:
            base_size: Base position size
            risk_level: Risk level
            confidence: Confidence in the trade

        Returns:
            Risk-adjusted position size
        """
        risk_multipliers = {
            "low": 1.0,
            "medium": 0.7,
            "high": 0.4,
            "critical": 0.1,
        }

        multiplier = risk_multipliers.get(risk_level, 0.5)
        adjusted_size = base_size * multiplier * confidence

        # Apply constraints
        adjusted_size = max(
            self.min_position, min(adjusted_size, self.max_position)
        )

        return PositionSize(
            size=adjusted_size,
            kelly_fraction=0.0,  # Not using Kelly
            risk_adjusted=True,
            confidence=confidence,
        )

