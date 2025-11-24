"""
Multi-Headed Threat Index (MHTI)

Aggregates 30+ Solberus threat detectors, market metrics, and
contract-level signals into a unified 0-1 composite risk score
with confidence intervals and explainability.

This is NOT AI or ML - it's a weighted aggregation system that unifies
multiple data sources into a single risk score.
"""

import time
import logging
from typing import Dict, Any, Optional, Tuple

from interfaces.core import TokenInfo
from security.comprehensive_threat_detector import ComprehensiveThreatDetector
from core.client import SolanaClient

logger = logging.getLogger(__name__)


class MultiHeadedThreatIndex:
    """
    Multi-Headed Threat Index (MHTI)

    Aggregates 30+ Solberus threat detectors, market metrics, and
    contract-level signals into a unified 0-1 composite risk score
    with confidence intervals and explainability.
    """

    def __init__(self, risk_tolerance: str = "medium", client: Optional[SolanaClient] = None):
        """
        Initialize MHTI.

        Args:
            risk_tolerance: One of "conservative", "medium", or "aggressive"
            client: Optional SolanaClient instance (created if not provided)
        """
        # Bucket weights (must sum to 1.0)
        self.weights = {
            "risk": 0.40,      # Existing 30 threat detectors
            "technical": 0.30,  # Token-2022 flags, authorities
            "market": 0.30,     # Liquidity, volume, holder health
        }

        # Risk tolerance thresholds
        self.thresholds = {
            "conservative": {"safe": 0.15, "monitor": 0.40, "high": 0.65},
            "medium":       {"safe": 0.30, "monitor": 0.60, "high": 0.80},
            "aggressive":   {"safe": 0.45, "monitor": 0.75, "high": 0.90},
        }[risk_tolerance]

        # Cache for repeated queries
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = 60  # seconds

        # Client for threat detection
        self.client = client

    async def classify(self, token_info: TokenInfo) -> Dict[str, Any]:
        """
        Classify a token's risk level using MHTI.

        Args:
            token_info: Token information to analyze

        Returns:
            Dictionary containing score, risk level, bucket scores, confidence interval, and top factors
        """
        mint_str = str(token_info.mint)

        # Check cache
        cached = self.cache.get(mint_str)
        if cached and (time.time() - cached["timestamp"]) < self.cache_ttl:
            logger.info(f"[MHTI] Cache hit for {mint_str}")
            return cached["result"]

        # Compute index
        result = await self._compute_index(token_info)

        # Cache result
        self.cache[mint_str] = {"timestamp": time.time(), "result": result}

        logger.info(
            f"[MHTI] mint={mint_str} score={result['score']:.3f} "
            f"level={result['risk_level']}"
        )

        return result

    async def _compute_index(self, token_info: TokenInfo) -> Dict[str, Any]:
        """
        Compute the multi-headed threat index.

        Args:
            token_info: Token information

        Returns:
            Complete MHTI result dictionary
        """
        # Compute bucket scores
        risk_bucket = await self._aggregate_existing_threats(token_info)
        technical_bucket = await self._compute_technical_risk(token_info)
        market_bucket = self._compute_market_risk(token_info)

        # Calculate weighted composite score
        score = (
            risk_bucket * self.weights["risk"] +
            technical_bucket * self.weights["technical"] +
            market_bucket * self.weights["market"]
        )

        # Ensure score is in [0, 1]
        score = max(0.0, min(1.0, score))

        # Classify risk level
        level = self._classify(score)

        # Compute confidence interval
        ci = self._compute_confidence_interval(score, {
            "risk": risk_bucket,
            "technical": technical_bucket,
            "market": market_bucket
        })

        # Rank top factors
        top_factors = self._rank_top_factors({
            "risk": risk_bucket,
            "technical": technical_bucket,
            "market": market_bucket
        })

        return {
            "engine": "Multi-Headed Threat Index (MHTI)",
            "score": score,
            "risk_level": level,
            "buckets": {
                "risk": risk_bucket,
                "technical": technical_bucket,
                "market": market_bucket
            },
            "top_factors": top_factors,
            "confidence_interval": ci
        }

    async def _aggregate_existing_threats(self, token_info: TokenInfo) -> float:
        """
        Aggregate all 30+ existing threat detectors into a single risk score.

        Args:
            token_info: Token information

        Returns:
            Risk score from 0.0 (safe) to 1.0 (maximum risk)
        """
        if not self.client:
            logger.warning("[MHTI] No client provided, using placeholder risk score")
            return 0.0

        try:
            # Initialize threat detector
            detector = ComprehensiveThreatDetector(self.client)

            # Detect all threats
            threats = await detector.detect_all_threats(token_info)

            # Severity weights
            severity_weights = {
                "critical": 1.0,
                "high": 0.70,
                "medium": 0.40,
                "low": 0.15
            }

            total = 0.0
            count = 0

            # Aggregate threat scores
            for threat_name, result in threats.items():
                if not result:
                    continue

                severity, confidence, details = result
                weight = severity_weights.get(severity, 0.0)
                total += weight * confidence
                count += 1

            if count == 0:
                return 0.0

            # Return normalized average
            return min(1.0, total / count)

        except Exception as e:
            logger.error(f"[MHTI] Error aggregating threats: {e}")
            return 0.5  # Uncertain, return moderate risk

    async def _compute_technical_risk(self, token_info: TokenInfo) -> float:
        """
        Compute technical risk from Token-2022 features and authorities.

        This checks for risky Token-2022 extensions and centralized authorities.

        Args:
            token_info: Token information

        Returns:
            Technical risk score from 0.0 (safe) to 1.0 (maximum risk)
        """
        # For now, extract from token_info metadata
        # In a full implementation, this would query Token-2022 extensions directly
        risk = 0.0

        # Check if we have additional_data that might contain extension info
        if token_info.additional_data:
            data = token_info.additional_data

            # Check for risky extensions
            if data.get("has_transfer_hook"):
                risk += 0.25
            if data.get("has_freeze_authority"):
                risk += 0.25
            if data.get("has_mint_authority"):
                risk += 0.25
            if data.get("has_permanent_delegate"):
                risk += 0.25

        # If no extension data available, assume low technical risk
        return min(1.0, risk)

    def _compute_market_risk(self, token_info: TokenInfo) -> float:
        """
        Compute market risk from liquidity, volume, and holder metrics.

        Lower liquidity/volume/holders = higher risk

        Args:
            token_info: Token information

        Returns:
            Market risk score from 0.0 (healthy) to 1.0 (unhealthy)
        """
        # Extract market metrics from TokenInfo
        liquidity = token_info.market_cap_sol or 0.0

        # If virtual reserves are available, use them as liquidity proxy
        if token_info.virtual_sol_reserves:
            liquidity = max(liquidity, token_info.virtual_sol_reserves)

        # Calculate health scores (0.0 = unhealthy, 1.0 = healthy)
        liquidity_health = min(1.0, liquidity / 50.0) if liquidity > 0 else 0.0

        # For volume and holders, we may not have data - use conservative assumptions
        # In production, these would come from additional API calls
        volume_health = 0.5  # Neutral assumption
        holder_health = 0.5  # Neutral assumption

        # Extract from additional_data if available
        if token_info.additional_data:
            volume_24h = token_info.additional_data.get("volume_24h", 0)
            holder_count = token_info.additional_data.get("holder_count", 0)

            if volume_24h > 0:
                volume_health = min(1.0, volume_24h / 500.0)
            if holder_count > 0:
                holder_health = min(1.0, holder_count / 200.0)

        # Average health across metrics
        overall_health = (liquidity_health + volume_health + holder_health) / 3.0

        # Risk is inverse of health
        return 1.0 - overall_health

    def _classify(self, score: float) -> str:
        """
        Classify risk score into risk level category.

        Args:
            score: Risk score from 0.0 to 1.0

        Returns:
            Risk level: "safe", "monitor", "high", or "critical"
        """
        t = self.thresholds
        if score < t["safe"]:
            return "safe"
        if score < t["monitor"]:
            return "monitor"
        if score < t["high"]:
            return "high"
        return "critical"

    def _compute_confidence_interval(
        self,
        score: float,
        buckets: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Compute confidence interval based on data quality.

        Lower bucket scores indicate missing/low-quality data, increasing uncertainty.

        Args:
            score: Computed risk score
            buckets: Individual bucket scores

        Returns:
            Dictionary with lower, upper bounds and uncertainty classification
        """
        # Data quality is based on how complete our buckets are
        # Low scores in multiple buckets = missing data = high uncertainty
        data_quality = min(buckets.values())

        # Uncertainty increases with poor data quality
        uncertainty = 0.15 * (1.0 - data_quality)

        return {
            "lower": max(0.0, score - uncertainty),
            "upper": min(1.0, score + uncertainty),
            "uncertainty": (
                "high" if uncertainty > 0.10 else
                "medium" if uncertainty > 0.05 else
                "low"
            )
        }

    def _rank_top_factors(self, buckets: Dict[str, float]) -> list:
        """
        Rank the top contributing factors to risk score.

        Args:
            buckets: Dictionary of bucket scores

        Returns:
            List of factors sorted by contribution, highest first
        """
        sorted_factors = sorted(buckets.items(), key=lambda x: x[1], reverse=True)
        return [{"factor": k, "value": v} for (k, v) in sorted_factors]
