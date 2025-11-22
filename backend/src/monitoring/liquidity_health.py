"""
Liquidity Health Monitor - Real-time health scoring, anomaly detection, and forecasting.

Provides:
- Real-time health scoring
- Anomaly detection
- Liquidity forecasting
- Stability analysis
- Alert system
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core.client import SolanaClient
from interfaces.core import TokenInfo
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class LiquidityHealthScore:
    """Liquidity health score for a token."""

    total_score: float  # 0.0 to 100.0
    stability_score: float  # 0.0 to 100.0
    depth_score: float  # 0.0 to 100.0
    volume_score: float  # 0.0 to 100.0
    health_level: str  # "healthy", "warning", "critical"
    anomalies: List[str]
    forecast: Dict[str, Any]


class LiquidityHealthMonitor:
    """
    Monitors liquidity health in real-time.

    Tracks:
    - Liquidity depth
    - Volume stability
    - Price stability
    - Anomaly detection
    - Forecasting
    """

    def __init__(self, client: SolanaClient):
        """Initialize liquidity health monitor.

        Args:
            client: Solana RPC client
        """
        self.client = client
        self.monitored_tokens: Dict[str, LiquidityHealthScore] = {}
        self.history: Dict[str, List[Dict[str, Any]]] = {}

    async def monitor_token(
        self, token_info: TokenInfo
    ) -> LiquidityHealthScore:
        """Monitor liquidity health for a token.

        Args:
            token_info: Token information

        Returns:
            Liquidity health score
        """
        logger.debug(f"Monitoring liquidity health for {token_info.symbol}...")

        try:
            # Get current liquidity metrics
            metrics = await self._get_liquidity_metrics(token_info)

            # Calculate scores
            stability_score = self._calculate_stability_score(metrics)
            depth_score = self._calculate_depth_score(metrics)
            volume_score = self._calculate_volume_score(metrics)

            # Calculate total score
            total_score = (stability_score + depth_score + volume_score) / 3.0

            # Detect anomalies
            anomalies = await self._detect_anomalies(token_info, metrics)

            # Generate forecast
            forecast = await self._forecast_liquidity(token_info, metrics)

            # Determine health level
            if total_score >= 70:
                health_level = "healthy"
            elif total_score >= 50:
                health_level = "warning"
            else:
                health_level = "critical"

            health_score = LiquidityHealthScore(
                total_score=total_score,
                stability_score=stability_score,
                depth_score=depth_score,
                volume_score=volume_score,
                health_level=health_level,
                anomalies=anomalies,
                forecast=forecast,
            )

            # Store monitoring result
            token_key = str(token_info.mint)
            self.monitored_tokens[token_key] = health_score

            # Update history
            if token_key not in self.history:
                self.history[token_key] = []
            self.history[token_key].append(
                {
                    "timestamp": asyncio.get_event_loop().time(),
                    "score": total_score,
                    "metrics": metrics,
                }
            )

            # Keep only recent history (last 100 entries)
            if len(self.history[token_key]) > 100:
                self.history[token_key] = self.history[token_key][-100:]

            if health_level == "critical":
                logger.warning(
                    f"CRITICAL liquidity health for {token_info.symbol}: "
                    f"{total_score:.1f}/100"
                )

            return health_score

        except Exception as e:
            logger.exception(f"Error monitoring liquidity health: {e}")
            return LiquidityHealthScore(
                total_score=0.0,
                stability_score=0.0,
                depth_score=0.0,
                volume_score=0.0,
                health_level="critical",
                anomalies=["Monitoring error"],
                forecast={},
            )

    async def _get_liquidity_metrics(
        self, token_info: TokenInfo
    ) -> Dict[str, Any]:
        """Get current liquidity metrics.

        Args:
            token_info: Token information

        Returns:
            Liquidity metrics dictionary
        """
        try:
            # In production, this would:
            # 1. Fetch current liquidity pool state
            # 2. Calculate depth, volume, stability
            # 3. Return metrics

            logger.debug("Fetching liquidity metrics...")

            return {
                "liquidity_depth": 0.0,  # SOL
                "volume_24h": 0.0,  # SOL
                "price_volatility": 0.0,
                "liquidity_stability": 0.0,
            }

        except Exception as e:
            logger.exception(f"Error fetching liquidity metrics: {e}")
            return {}

    def _calculate_stability_score(
        self, metrics: Dict[str, Any]
    ) -> float:
        """Calculate liquidity stability score.

        Args:
            metrics: Liquidity metrics

        Returns:
            Stability score (0-100)
        """
        try:
            volatility = metrics.get("price_volatility", 1.0)
            stability = metrics.get("liquidity_stability", 0.0)

            # Lower volatility = higher score
            volatility_score = max(0.0, 100.0 - (volatility * 100))
            stability_score = stability * 100

            return (volatility_score + stability_score) / 2.0

        except Exception as e:
            logger.exception(f"Error calculating stability score: {e}")
            return 0.0

    def _calculate_depth_score(self, metrics: Dict[str, Any]) -> float:
        """Calculate liquidity depth score.

        Args:
            metrics: Liquidity metrics

        Returns:
            Depth score (0-100)
        """
        try:
            depth = metrics.get("liquidity_depth", 0.0)

            # Score based on depth (more depth = higher score)
            # Scale: 0 SOL = 0, 10 SOL = 100
            depth_score = min(100.0, (depth / 10.0) * 100)

            return depth_score

        except Exception as e:
            logger.exception(f"Error calculating depth score: {e}")
            return 0.0

    def _calculate_volume_score(self, metrics: Dict[str, Any]) -> float:
        """Calculate volume score.

        Args:
            metrics: Liquidity metrics

        Returns:
            Volume score (0-100)
        """
        try:
            volume_24h = metrics.get("volume_24h", 0.0)

            # Score based on volume (more volume = higher score)
            # Scale: 0 SOL = 0, 50 SOL = 100
            volume_score = min(100.0, (volume_24h / 50.0) * 100)

            return volume_score

        except Exception as e:
            logger.exception(f"Error calculating volume score: {e}")
            return 0.0

    async def _detect_anomalies(
        self, token_info: TokenInfo, metrics: Dict[str, Any]
    ) -> List[str]:
        """Detect liquidity anomalies.

        Args:
            token_info: Token information
            metrics: Current metrics

        Returns:
            List of detected anomalies
        """
        anomalies: List[str] = []

        try:
            # Check for sudden liquidity drop
            depth = metrics.get("liquidity_depth", 0.0)
            if depth < 0.1:  # Less than 0.1 SOL
                anomalies.append("CRITICAL: Liquidity depth extremely low")

            # Check for volume anomalies
            volume = metrics.get("volume_24h", 0.0)
            if volume == 0.0:
                anomalies.append("WARNING: No trading volume in 24h")

            # Check for high volatility
            volatility = metrics.get("price_volatility", 0.0)
            if volatility > 0.5:  # 50% volatility
                anomalies.append("WARNING: Extremely high price volatility")

            # Check historical trends
            token_key = str(token_info.mint)
            if token_key in self.history and len(self.history[token_key]) > 5:
                recent_scores = [
                    entry["score"]
                    for entry in self.history[token_key][-5:]
                ]
                avg_recent = sum(recent_scores) / len(recent_scores)
                current_score = (
                    metrics.get("liquidity_depth", 0.0) / 10.0 * 100
                )  # Simplified

                if current_score < avg_recent * 0.5:  # 50% drop
                    anomalies.append(
                        "WARNING: Significant liquidity health decline"
                    )

        except Exception as e:
            logger.exception(f"Error detecting anomalies: {e}")

        return anomalies

    async def _forecast_liquidity(
        self, token_info: TokenInfo, metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Forecast future liquidity health.

        Args:
            token_info: Token information
            metrics: Current metrics

        Returns:
            Forecast dictionary
        """
        try:
            # In production, this would:
            # 1. Analyze historical trends
            # 2. Use ML models for prediction
            # 3. Forecast future health

            logger.debug("Forecasting liquidity...")

            # Placeholder forecast
            return {
                "predicted_score_1h": metrics.get("liquidity_depth", 0.0) / 10.0 * 100,
                "predicted_score_24h": metrics.get("liquidity_depth", 0.0) / 10.0 * 100,
                "trend": "stable",
                "confidence": 0.5,
            }

        except Exception as e:
            logger.exception(f"Error forecasting liquidity: {e}")
            return {}

    def get_health_summary(self) -> Dict[str, Any]:
        """Get summary of liquidity health monitoring.

        Returns:
            Summary dictionary
        """
        total_monitored = len(self.monitored_tokens)
        healthy = sum(
            1
            for score in self.monitored_tokens.values()
            if score.health_level == "healthy"
        )
        warning = sum(
            1
            for score in self.monitored_tokens.values()
            if score.health_level == "warning"
        )
        critical = sum(
            1
            for score in self.monitored_tokens.values()
            if score.health_level == "critical"
        )

        avg_score = (
            sum(score.total_score for score in self.monitored_tokens.values())
            / max(total_monitored, 1)
            if total_monitored > 0
            else 0.0
        )

        return {
            "total_monitored": total_monitored,
            "healthy": healthy,
            "warning": warning,
            "critical": critical,
            "average_score": avg_score,
        }

