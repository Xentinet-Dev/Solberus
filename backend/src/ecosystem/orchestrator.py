"""
Ecosystem Orchestrator - Manages self-sustaining sum-positive ecosystem.

Coordinates:
- Value distribution
- Community benefit allocation
- Sum-positive flow management
- Self-sustaining mechanisms
- Ecosystem health monitoring
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core.client import SolanaClient
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class EcosystemMetrics:
    """Ecosystem health metrics."""

    sum_positive_ratio: float  # Value created / Value consumed
    self_funding_percentage: float  # % of operations self-funded
    community_benefit_percentage: float  # % of benefits to community
    growth_rate: float  # % growth rate
    total_value_created: float  # Total value created (SOL)
    total_value_consumed: float  # Total value consumed (SOL)
    ecosystem_health: str  # "healthy", "warning", "critical"


class EcosystemOrchestrator:
    """
    Orchestrates the self-sustaining sum-positive ecosystem.

    Manages:
    - Value distribution
    - Community benefits
    - Sum-positive flows
    - Self-sustaining operations
    - Ecosystem health
    """

    def __init__(self, client: SolanaClient):
        """Initialize ecosystem orchestrator.

        Args:
            client: Solana RPC client
        """
        self.client = client
        self.value_created: float = 0.0  # SOL
        self.value_consumed: float = 0.0  # SOL
        self.community_benefits_distributed: float = 0.0  # SOL
        self.bug_bounty_funding: float = 0.0  # SOL
        self.liquidity_generated: float = 0.0  # SOL
        self.operations_funded: float = 0.0  # SOL

    async def record_value_creation(
        self, amount: float, source: str, description: str = ""
    ) -> None:
        """Record value creation in the ecosystem.

        Args:
            amount: Amount of value created (SOL)
            source: Source of value (e.g., "bug_bounty", "liquidity_generation")
            description: Optional description
        """
        self.value_created += amount

        if source == "bug_bounty":
            self.bug_bounty_funding += amount
        elif source == "liquidity_generation":
            self.liquidity_generated += amount

        logger.info(
            f"Value created: {amount:.6f} SOL from {source} "
            f"(Total: {self.value_created:.6f} SOL)"
        )

    async def record_value_consumption(
        self, amount: float, purpose: str, description: str = ""
    ) -> None:
        """Record value consumption in the ecosystem.

        Args:
            amount: Amount of value consumed (SOL)
            purpose: Purpose of consumption (e.g., "operations", "infrastructure")
            description: Optional description
        """
        self.value_consumed += amount

        if purpose == "operations":
            self.operations_funded += amount

        logger.info(
            f"Value consumed: {amount:.6f} SOL for {purpose} "
            f"(Total: {self.value_consumed:.6f} SOL)"
        )

    async def distribute_community_benefits(
        self, amount: float, distribution_type: str = "general"
    ) -> Dict[str, Any]:
        """Distribute benefits to the community.

        Args:
            amount: Amount to distribute (SOL)
            distribution_type: Type of distribution

        Returns:
            Distribution result
        """
        logger.info(f"Distributing {amount:.6f} SOL to community ({distribution_type})...")

        # In production, this would:
        # 1. Get all holders
        # 2. Calculate proportional shares
        # 3. Distribute to all holders
        # 4. Ensure no single wallet accumulation

        self.community_benefits_distributed += amount
        self.value_consumed += amount  # Distribution is consumption

        logger.info(
            f"Community benefits distributed: {amount:.6f} SOL "
            f"(Total: {self.community_benefits_distributed:.6f} SOL)"
        )

        return {
            "distributed": amount,
            "type": distribution_type,
            "total_distributed": self.community_benefits_distributed,
        }

    async def calculate_ecosystem_metrics(self) -> EcosystemMetrics:
        """Calculate ecosystem health metrics.

        Returns:
            Ecosystem metrics
        """
        # Sum-positive ratio
        if self.value_consumed > 0:
            sum_positive_ratio = self.value_created / self.value_consumed
        else:
            sum_positive_ratio = float("inf") if self.value_created > 0 else 1.0

        # Self-funding percentage
        if self.value_created > 0:
            self_funding = (self.operations_funded / self.value_created) * 100
        else:
            self_funding = 0.0

        # Community benefit percentage
        if self.value_created > 0:
            community_benefit = (
                self.community_benefits_distributed / self.value_created
            ) * 100
        else:
            community_benefit = 0.0

        # Growth rate (simplified - would use time-based calculation)
        growth_rate = (
            ((self.value_created - self.value_consumed) / max(self.value_consumed, 1))
            * 100
        )

        # Determine health
        if sum_positive_ratio >= 1.2 and self_funding >= 80 and community_benefit >= 90:
            health = "healthy"
        elif sum_positive_ratio >= 1.0 and self_funding >= 60 and community_benefit >= 70:
            health = "warning"
        else:
            health = "critical"

        metrics = EcosystemMetrics(
            sum_positive_ratio=sum_positive_ratio,
            self_funding_percentage=self_funding,
            community_benefit_percentage=community_benefit,
            growth_rate=growth_rate,
            total_value_created=self.value_created,
            total_value_consumed=self.value_consumed,
            ecosystem_health=health,
        )

        if health == "critical":
            logger.warning(
                f"⚠️ CRITICAL ecosystem health: "
                f"Sum-positive ratio: {sum_positive_ratio:.2f}, "
                f"Self-funding: {self_funding:.1f}%, "
                f"Community benefit: {community_benefit:.1f}%"
            )

        return metrics

    async def ensure_sum_positive_operation(
        self, operation_cost: float, expected_value: float
    ) -> bool:
        """Ensure an operation maintains sum-positive economics.

        Args:
            operation_cost: Cost of operation (SOL)
            expected_value: Expected value creation (SOL)

        Returns:
            True if operation is sum-positive, False otherwise
        """
        if expected_value <= operation_cost:
            logger.warning(
                f"⚠️ Operation not sum-positive: "
                f"Cost: {operation_cost:.6f} SOL, "
                f"Expected value: {expected_value:.6f} SOL"
            )
            return False

        ratio = expected_value / operation_cost
        logger.info(
            f"✓ Operation is sum-positive: "
            f"Ratio: {ratio:.2f}x (Cost: {operation_cost:.6f}, Value: {expected_value:.6f})"
        )
        return True

    def get_summary(self) -> Dict[str, Any]:
        """Get ecosystem summary.

        Returns:
            Summary dictionary
        """
        metrics = asyncio.create_task(self.calculate_ecosystem_metrics())
        # Note: In production, would await this properly

        return {
            "value_created": self.value_created,
            "value_consumed": self.value_consumed,
            "community_benefits": self.community_benefits_distributed,
            "bug_bounty_funding": self.bug_bounty_funding,
            "liquidity_generated": self.liquidity_generated,
            "operations_funded": self.operations_funded,
        }

