"""
Sum-Positive Engine - Ensures value creation exceeds consumption.

Critical Requirements:
- Value created > Value consumed
- Regenerative feedback loops
- Sustainable growth
- Self-sustaining operations
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SumPositiveMetrics:
    """Sum-positive metrics for an operation or the ecosystem."""

    value_created: float  # SOL
    value_consumed: float  # SOL
    ratio: float  # Created / Consumed
    is_sum_positive: bool
    sustainability_score: float  # 0.0 to 1.0


class SumPositiveEngine:
    """
    Ensures sum-positive economics throughout the ecosystem.

    Tracks:
    - Value creation vs consumption
    - Sum-positive ratios
    - Sustainability metrics
    - Regenerative flows
    """

    def __init__(self, min_ratio: float = 1.1):
        """Initialize sum-positive engine.

        Args:
            min_ratio: Minimum sum-positive ratio (default 1.1 = 10% positive)
        """
        self.min_ratio = min_ratio
        self.operations: List[Dict[str, Any]] = []

    def validate_operation(
        self, value_created: float, value_consumed: float
    ) -> SumPositiveMetrics:
        """Validate that an operation is sum-positive.

        Args:
            value_created: Value created by operation (SOL)
            value_consumed: Value consumed by operation (SOL)

        Returns:
            Sum-positive metrics
        """
        ratio = value_created / value_consumed if value_consumed > 0 else float("inf")
        is_sum_positive = ratio >= self.min_ratio

        # Calculate sustainability score (0.0 to 1.0)
        if ratio >= 2.0:
            sustainability_score = 1.0
        elif ratio >= 1.5:
            sustainability_score = 0.8
        elif ratio >= 1.2:
            sustainability_score = 0.6
        elif ratio >= 1.0:
            sustainability_score = 0.4
        else:
            sustainability_score = 0.0

        metrics = SumPositiveMetrics(
            value_created=value_created,
            value_consumed=value_consumed,
            ratio=ratio,
            is_sum_positive=is_sum_positive,
            sustainability_score=sustainability_score,
        )

        if not is_sum_positive:
            logger.warning(
                f"⚠️ Operation NOT sum-positive: "
                f"Ratio: {ratio:.2f} (Created: {value_created:.6f}, "
                f"Consumed: {value_consumed:.6f})"
            )
        else:
            logger.info(
                f"✓ Operation is sum-positive: "
                f"Ratio: {ratio:.2f}x (Created: {value_created:.6f}, "
                f"Consumed: {value_consumed:.6f})"
            )

        # Store operation
        self.operations.append(
            {
                "value_created": value_created,
                "value_consumed": value_consumed,
                "ratio": ratio,
                "is_sum_positive": is_sum_positive,
                "sustainability_score": sustainability_score,
            }
        )

        return metrics

    def calculate_ecosystem_sustainability(
        self, total_created: float, total_consumed: float
    ) -> SumPositiveMetrics:
        """Calculate overall ecosystem sustainability.

        Args:
            total_created: Total value created (SOL)
            total_consumed: Total value consumed (SOL)

        Returns:
            Ecosystem sustainability metrics
        """
        return self.validate_operation(total_created, total_consumed)

    def get_sustainability_report(self) -> Dict[str, Any]:
        """Get sustainability report.

        Returns:
            Report dictionary
        """
        if not self.operations:
            return {
                "total_operations": 0,
                "sum_positive_operations": 0,
                "average_ratio": 0.0,
                "sustainability_score": 0.0,
            }

        sum_positive_count = sum(1 for op in self.operations if op["is_sum_positive"])
        total_created = sum(op["value_created"] for op in self.operations)
        total_consumed = sum(op["value_consumed"] for op in self.operations)
        avg_ratio = (
            total_created / total_consumed if total_consumed > 0 else 0.0
        )
        avg_sustainability = (
            sum(op["sustainability_score"] for op in self.operations)
            / len(self.operations)
        )

        return {
            "total_operations": len(self.operations),
            "sum_positive_operations": sum_positive_count,
            "sum_positive_percentage": (
                (sum_positive_count / len(self.operations)) * 100
                if self.operations
                else 0.0
            ),
            "total_value_created": total_created,
            "total_value_consumed": total_consumed,
            "average_ratio": avg_ratio,
            "sustainability_score": avg_sustainability,
        }

