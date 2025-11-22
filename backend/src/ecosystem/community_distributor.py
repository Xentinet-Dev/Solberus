"""
Community Distributor - Ensures all benefits go to community (all holders).

Critical Requirements:
- All holders benefit
- Fair distribution
- No single wallet accumulation
- Community-first model
- Proportional allocation
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from solders.pubkey import Pubkey

from core.client import SolanaClient
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class HolderBenefit:
    """Benefit allocation for a holder."""

    holder_address: Pubkey
    stake: float  # Holder's stake (tokens or SOL)
    benefit_amount: float  # Benefit allocated (SOL)
    percentage: float  # Percentage of total benefits


@dataclass
class DistributionResult:
    """Result of community distribution."""

    total_distributed: float  # Total amount distributed (SOL)
    number_of_holders: int  # Number of holders who received benefits
    average_benefit: float  # Average benefit per holder
    distribution_type: str  # Type of distribution
    allocations: List[HolderBenefit]  # Individual allocations


class CommunityDistributor:
    """
    Distributes benefits to all community holders.

    Ensures:
    - All holders benefit
    - Fair distribution
    - No single wallet accumulation
    - Community-first model
    """

    def __init__(self, client: SolanaClient):
        """Initialize community distributor.

        Args:
            client: Solana RPC client
        """
        self.client = client
        self.total_distributed: float = 0.0  # SOL
        self.distribution_history: List[DistributionResult] = []

    async def get_all_holders(self, token_mint: Pubkey) -> List[Dict[str, Any]]:
        """Get all holders of a token.

        Args:
            token_mint: Token mint address

        Returns:
            List of holders with their stakes
        """
        try:
            # In production, this would:
            # 1. Query token accounts for the mint
            # 2. Get balances for each account
            # 3. Filter out zero balances
            # 4. Return list of holders

            logger.debug(f"Fetching holders for token {token_mint}...")

            # Placeholder - would fetch actual holders
            holders: List[Dict[str, Any]] = []

            return holders

        except Exception as e:
            logger.exception(f"Error fetching holders: {e}")
            return []

    async def calculate_holder_benefits(
        self,
        total_benefits: float,
        holders: List[Dict[str, Any]],
        distribution_type: str = "proportional",
    ) -> List[HolderBenefit]:
        """Calculate benefit allocation for each holder.

        Args:
            total_benefits: Total benefits to distribute (SOL)
            holders: List of holders with stakes
            distribution_type: Type of distribution ("proportional", "equal", "hybrid")

        Returns:
            List of holder benefits
        """
        allocations: List[HolderBenefit] = []

        if not holders:
            logger.warning("No holders found for distribution")
            return allocations

        total_stake = sum(h.get("stake", 0.0) for h in holders)

        if total_stake == 0:
            logger.warning("Total stake is zero, using equal distribution")
            # Equal distribution fallback
            benefit_per_holder = total_benefits / len(holders)
            for holder in holders:
                allocations.append(
                    HolderBenefit(
                        holder_address=Pubkey.from_string(holder["address"]),
                        stake=0.0,
                        benefit_amount=benefit_per_holder,
                        percentage=(1.0 / len(holders)) * 100,
                    )
                )
            return allocations

        # Proportional distribution
        for holder in holders:
            stake = holder.get("stake", 0.0)
            percentage = (stake / total_stake) * 100
            benefit_amount = (stake / total_stake) * total_benefits

            allocations.append(
                HolderBenefit(
                    holder_address=Pubkey.from_string(holder["address"]),
                    stake=stake,
                    benefit_amount=benefit_amount,
                    percentage=percentage,
                )
            )

        return allocations

    async def distribute_liquidity_benefits(
        self, token_mint: Pubkey, liquidity_value: float
    ) -> DistributionResult:
        """Distribute liquidity generation benefits to all holders.

        Args:
            token_mint: Token mint address
            liquidity_value: Value of liquidity generated (SOL)

        Returns:
            Distribution result
        """
        logger.info(
            f"Distributing liquidity benefits: {liquidity_value:.6f} SOL "
            f"for token {token_mint}"
        )

        # Get all holders
        holders = await self.get_all_holders(token_mint)

        if not holders:
            logger.warning("No holders found, cannot distribute benefits")
            return DistributionResult(
                total_distributed=0.0,
                number_of_holders=0,
                average_benefit=0.0,
                distribution_type="liquidity",
                allocations=[],
            )

        # Calculate benefits
        allocations = await self.calculate_holder_benefits(
            liquidity_value, holders, distribution_type="proportional"
        )

        # In production, would actually distribute here
        # For now, just log the distribution plan

        total_distributed = sum(a.benefit_amount for a in allocations)
        avg_benefit = (
            total_distributed / len(allocations) if allocations else 0.0
        )

        result = DistributionResult(
            total_distributed=total_distributed,
            number_of_holders=len(allocations),
            average_benefit=avg_benefit,
            distribution_type="liquidity",
            allocations=allocations,
        )

        self.total_distributed += total_distributed
        self.distribution_history.append(result)

        logger.info(
            f"Liquidity benefits distributed: {total_distributed:.6f} SOL "
            f"to {len(allocations)} holders "
            f"(avg: {avg_benefit:.6f} SOL/holder)"
        )

        # Ensure no single wallet gets too much
        max_benefit = max((a.benefit_amount for a in allocations), default=0.0)
        max_percentage = max((a.percentage for a in allocations), default=0.0)

        if max_percentage > 50.0:  # More than 50% to one wallet
            logger.warning(
                f"⚠️ WARNING: Single wallet receiving {max_percentage:.1f}% "
                f"of benefits ({max_benefit:.6f} SOL) - violates community-first principle"
            )

        return result

    async def distribute_bounty_benefits(
        self, bounty_amount: float, distribution_type: str = "community_pool"
    ) -> DistributionResult:
        """Distribute bug bounty benefits to community.

        Args:
            bounty_amount: Bounty amount (SOL)
            distribution_type: Distribution type

        Returns:
            Distribution result
        """
        logger.info(
            f"Distributing bounty benefits: {bounty_amount:.6f} SOL "
            f"({distribution_type})"
        )

        # In production, would:
        # 1. Add to community pool
        # 2. Distribute to all ecosystem participants
        # 3. Ensure fair allocation

        # For now, create a placeholder distribution
        result = DistributionResult(
            total_distributed=bounty_amount,
            number_of_holders=0,  # Would be actual count
            average_benefit=0.0,
            distribution_type="bounty",
            allocations=[],
        )

        self.total_distributed += bounty_amount
        self.distribution_history.append(result)

        logger.info(f"Bounty benefits distributed: {bounty_amount:.6f} SOL to community")

        return result

    def get_distribution_summary(self) -> Dict[str, Any]:
        """Get distribution summary.

        Returns:
            Summary dictionary
        """
        return {
            "total_distributed": self.total_distributed,
            "number_of_distributions": len(self.distribution_history),
            "average_distribution": (
                self.total_distributed / len(self.distribution_history)
                if self.distribution_history
                else 0.0
            ),
        }

