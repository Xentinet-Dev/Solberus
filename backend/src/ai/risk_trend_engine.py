"""
Risk Trend Engine

Tracks MHTI risk scores over time and detects accelerating danger patterns.
This provides actual predictive behavior by analyzing risk velocity and acceleration.
"""

import time
import logging
from typing import Dict, List, Tuple, Optional, Any

logger = logging.getLogger(__name__)


class RiskTrendEngine:
    """
    Tracks MHTI risk scores over time and detects accelerating danger.

    Features:
    - Maintains rolling history of risk scores per token
    - Calculates risk velocity (rate of change)
    - Detects risk acceleration (change in rate of change)
    - Generates alerts for rapid risk increases
    - Provides trend visualization data
    """

    def __init__(self, history_size: int = 10, alert_threshold: float = 0.15):
        """
        Initialize Risk Trend Engine.

        Args:
            history_size: Number of historical data points to maintain per token
            alert_threshold: Threshold for triggering acceleration alerts
        """
        # mint -> [(timestamp, score), ...]
        self.history: Dict[str, List[Tuple[float, float]]] = {}

        self.history_size = history_size
        self.alert_threshold = alert_threshold

        logger.info(
            f"[RiskTrendEngine] Initialized with history_size={history_size}, "
            f"alert_threshold={alert_threshold}"
        )

    def update(self, mint: str, score: float) -> None:
        """
        Record a new risk score for a token.

        Args:
            mint: Token mint address
            score: MHTI risk score (0-1)
        """
        ts = time.time()

        # Initialize history for new token
        if mint not in self.history:
            self.history[mint] = []

        # Append new data point
        self.history[mint].append((ts, score))

        # Trim to history_size
        if len(self.history[mint]) > self.history_size:
            self.history[mint] = self.history[mint][-self.history_size:]

        logger.debug(
            f"[RiskTrendEngine] Updated {mint}: score={score:.3f}, "
            f"history_points={len(self.history[mint])}"
        )

    def analyze(self, mint: str) -> Dict[str, Any]:
        """
        Analyze risk trend for a token.

        Args:
            mint: Token mint address

        Returns:
            Dictionary containing:
            - trend: Risk velocity (change per unit time)
            - acceleration: Risk acceleration (change in velocity)
            - alert: Alert message if risk accelerating
            - confidence: Confidence in trend analysis (based on data points)
            - direction: "increasing", "decreasing", or "stable"
            - history: Historical data points for visualization
        """
        # Check if we have enough data
        if mint not in self.history:
            return {
                "trend": 0.0,
                "acceleration": 0.0,
                "alert": None,
                "confidence": "none",
                "direction": "unknown",
                "history": [],
                "data_points": 0
            }

        history = self.history[mint]
        data_points = len(history)

        # Need at least 2 points for trend, 3 for acceleration
        if data_points < 2:
            return {
                "trend": 0.0,
                "acceleration": 0.0,
                "alert": None,
                "confidence": "insufficient",
                "direction": "unknown",
                "history": history,
                "data_points": data_points
            }

        # Calculate trend (linear regression slope)
        trend = self._calculate_trend(history)

        # Calculate acceleration if we have enough points
        acceleration = 0.0
        if data_points >= 3:
            acceleration = self._calculate_acceleration(history)

        # Determine direction
        if abs(trend) < 0.05:
            direction = "stable"
        elif trend > 0:
            direction = "increasing"
        else:
            direction = "decreasing"

        # Determine confidence based on data points
        if data_points < 3:
            confidence = "low"
        elif data_points < 5:
            confidence = "medium"
        else:
            confidence = "high"

        # Generate alerts
        alert = self._generate_alert(trend, acceleration, direction, confidence)

        return {
            "trend": trend,
            "acceleration": acceleration,
            "alert": alert,
            "confidence": confidence,
            "direction": direction,
            "history": history,
            "data_points": data_points
        }

    def _calculate_trend(self, history: List[Tuple[float, float]]) -> float:
        """
        Calculate risk velocity using linear regression.

        Args:
            history: List of (timestamp, score) tuples

        Returns:
            Trend value (positive = increasing risk, negative = decreasing risk)
        """
        if len(history) < 2:
            return 0.0

        # Normalize time to 0-1 range for consistent trend values
        timestamps = [ts for ts, _ in history]
        scores = [score for _, score in history]

        t_min = min(timestamps)
        t_max = max(timestamps)

        # Avoid division by zero for same-time samples
        if t_max - t_min < 1e-6:
            return 0.0

        # Normalize timestamps to 0-1
        norm_times = [(t - t_min) / (t_max - t_min) for t in timestamps]

        # Calculate linear regression slope
        n = len(history)
        mean_t = sum(norm_times) / n
        mean_s = sum(scores) / n

        numerator = sum((t - mean_t) * (s - mean_s) for t, s in zip(norm_times, scores))
        denominator = sum((t - mean_t) ** 2 for t in norm_times)

        if denominator < 1e-6:
            return 0.0

        slope = numerator / denominator
        return slope

    def _calculate_acceleration(self, history: List[Tuple[float, float]]) -> float:
        """
        Calculate risk acceleration (change in velocity).

        Args:
            history: List of (timestamp, score) tuples

        Returns:
            Acceleration value (positive = accelerating risk increase)
        """
        if len(history) < 3:
            return 0.0

        # Split into two halves and compare trends
        midpoint = len(history) // 2
        first_half = history[:midpoint+1]
        second_half = history[midpoint:]

        trend1 = self._calculate_trend(first_half)
        trend2 = self._calculate_trend(second_half)

        # Acceleration is change in trend
        return trend2 - trend1

    def _generate_alert(
        self,
        trend: float,
        acceleration: float,
        direction: str,
        confidence: str
    ) -> Optional[str]:
        """
        Generate alert message based on trend analysis.

        Args:
            trend: Risk velocity
            acceleration: Risk acceleration
            direction: Trend direction
            confidence: Analysis confidence

        Returns:
            Alert message or None
        """
        # Only generate alerts with sufficient confidence
        if confidence == "low" or confidence == "insufficient":
            return None

        # Critical: Rapid risk increase
        if trend > self.alert_threshold and direction == "increasing":
            if acceleration > 0.1:
                return "🚨 CRITICAL: Risk accelerating rapidly - immediate attention required"
            else:
                return "⚠️  WARNING: Risk increasing steadily - monitor closely"

        # Severe acceleration even from low base
        if acceleration > 0.2:
            return "⚠️  WARNING: Rapid risk acceleration detected"

        # Positive: Risk decreasing
        if trend < -self.alert_threshold and direction == "decreasing":
            return "✅ POSITIVE: Risk decreasing - conditions improving"

        return None

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics for all tracked tokens.

        Returns:
            Dictionary with summary statistics
        """
        if not self.history:
            return {
                "tracked_tokens": 0,
                "high_risk_tokens": 0,
                "accelerating_tokens": 0,
                "improving_tokens": 0
            }

        high_risk = 0
        accelerating = 0
        improving = 0

        for mint in self.history.keys():
            analysis = self.analyze(mint)

            # Check latest score
            if self.history[mint]:
                _, latest_score = self.history[mint][-1]
                if latest_score > 0.7:
                    high_risk += 1

            # Check trend
            if analysis["direction"] == "increasing" and analysis["trend"] > 0.1:
                accelerating += 1
            elif analysis["direction"] == "decreasing" and analysis["trend"] < -0.1:
                improving += 1

        return {
            "tracked_tokens": len(self.history),
            "high_risk_tokens": high_risk,
            "accelerating_tokens": accelerating,
            "improving_tokens": improving
        }

    def clear_stale_data(self, max_age_seconds: float = 3600) -> int:
        """
        Clear data older than specified age.

        Args:
            max_age_seconds: Maximum age of data to keep (default: 1 hour)

        Returns:
            Number of tokens cleared
        """
        current_time = time.time()
        cutoff_time = current_time - max_age_seconds

        tokens_to_remove = []

        for mint, history in self.history.items():
            # Check if latest data point is too old
            if history and history[-1][0] < cutoff_time:
                tokens_to_remove.append(mint)

        # Remove stale tokens
        for mint in tokens_to_remove:
            del self.history[mint]

        if tokens_to_remove:
            logger.info(
                f"[RiskTrendEngine] Cleared {len(tokens_to_remove)} "
                f"stale tokens (age > {max_age_seconds}s)"
            )

        return len(tokens_to_remove)
