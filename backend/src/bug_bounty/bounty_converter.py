"""
Bounty-to-Liquidity Converter.

Converts bug bounty payments into liquidity generation using AEON principles.
This completes the vulnerability-to-liquidity pipeline.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from solders.pubkey import Pubkey

from bug_bounty.submission_status import SubmissionInfo
from core.client import SolanaClient
from ecosystem.aeon_integration import AEONIntegration
from ecosystem.community_distributor import CommunityDistributor
from liquidity.liquidity_provider import LiquidityProvider
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ConversionResult:
    """Result of bounty-to-liquidity conversion."""

    success: bool
    bounty_amount: float  # USD
    liquidity_created: float  # SOL
    community_benefits: float  # SOL
    holders_benefited: int
    conversion_rate: float  # SOL per USD
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        """Initialize default values."""
        if self.metadata is None:
            self.metadata = {}


class BountyToLiquidityConverter:
    """
    Converts bug bounty payments to liquidity generation.
    
    Uses AEON principles:
    - Community-first distribution
    - All holders benefit
    - Regenerative economics
    - Sum-positive flows
    """

    def __init__(
        self,
        client: SolanaClient,
        community_distributor: Optional[CommunityDistributor] = None,
        liquidity_provider: Optional[LiquidityProvider] = None,
        aeon_integration: Optional[AEONIntegration] = None,
        usd_to_sol_rate: float = 150.0,  # Rough estimate: 1 SOL = $150 USD
        community_share_percentage: float = 0.9,  # 90% to community
    ):
        """Initialize bounty-to-liquidity converter.
        
        Args:
            client: Solana RPC client
            community_distributor: Community distributor instance
            liquidity_provider: Liquidity provider instance
            aeon_integration: AEON integration instance
            usd_to_sol_rate: USD to SOL conversion rate
            community_share_percentage: Percentage of bounty to distribute to community
        """
        self.client = client
        self.usd_to_sol_rate = usd_to_sol_rate
        self.community_share_percentage = community_share_percentage
        
        # Initialize components
        self.community_distributor = (
            community_distributor or CommunityDistributor(client)
        )
        self.liquidity_provider = (
            liquidity_provider or LiquidityProvider(
                client, community_distributor=self.community_distributor
            )
        )
        self.aeon_integration = (
            aeon_integration or AEONIntegration(
                client, community_distributor=self.community_distributor
            )
        )
        
        # Statistics
        self.total_bounties_converted: float = 0.0  # USD
        self.total_liquidity_created: float = 0.0  # SOL
        self.total_community_benefits: float = 0.0  # SOL
        self.conversions: List[ConversionResult] = []

    def _convert_usd_to_sol(self, usd_amount: float) -> float:
        """Convert USD amount to SOL.
        
        Args:
            usd_amount: Amount in USD
            
        Returns:
            Amount in SOL
        """
        return usd_amount / self.usd_to_sol_rate

    async def convert_bounty_to_liquidity(
        self,
        submission: SubmissionInfo,
        target_token: Optional[Pubkey] = None,
        use_aeon: bool = True,
    ) -> ConversionResult:
        """Convert a bounty payment to liquidity generation.
        
        Args:
            submission: Submission info with payment details
            target_token: Optional target token for liquidity (if None, uses ecosystem token)
            use_aeon: Whether to use AEON principles for conversion
            
        Returns:
            Conversion result
        """
        if not submission.actual_bounty:
            return ConversionResult(
                success=False,
                bounty_amount=0.0,
                liquidity_created=0.0,
                community_benefits=0.0,
                holders_benefited=0,
                conversion_rate=0.0,
                error_message="No bounty amount available",
            )
        
        bounty_usd = submission.actual_bounty
        bounty_sol = self._convert_usd_to_sol(bounty_usd)
        
        logger.info(
            f"Converting bounty to liquidity: ${bounty_usd:,.2f} USD "
            f"({bounty_sol:.6f} SOL) for submission {submission.submission_id}"
        )
        
        try:
            if use_aeon:
                # Use AEON integration for community-first liquidity
                result = await self._convert_via_aeon(
                    bounty_sol, target_token, submission
                )
            else:
                # Direct conversion without AEON
                result = await self._convert_direct(
                    bounty_sol, target_token, submission
                )
            
            # Update statistics
            self.total_bounties_converted += bounty_usd
            self.total_liquidity_created += result.liquidity_created
            self.total_community_benefits += result.community_benefits
            self.conversions.append(result)
            
            logger.info(
                f"✓ Bounty converted: ${bounty_usd:,.2f} USD → "
                f"{result.liquidity_created:.6f} SOL liquidity, "
                f"{result.community_benefits:.6f} SOL to {result.holders_benefited} holders"
            )
            
            return result
            
        except Exception as e:
            logger.exception(f"Error converting bounty to liquidity: {e}")
            return ConversionResult(
                success=False,
                bounty_amount=bounty_usd,
                liquidity_created=0.0,
                community_benefits=0.0,
                holders_benefited=0,
                conversion_rate=0.0,
                error_message=str(e),
            )

    async def _convert_via_aeon(
        self,
        bounty_sol: float,
        target_token: Optional[Pubkey],
        submission: SubmissionInfo,
    ) -> ConversionResult:
        """Convert bounty using AEON principles.
        
        Args:
            bounty_sol: Bounty amount in SOL
            target_token: Target token for liquidity
            submission: Submission info
            
        Returns:
            Conversion result
        """
        # Use AEON integration for community-first liquidity generation
        if target_token:
            aeon_result = await self.aeon_integration.generate_liquidity_aeon(
                token_mint=target_token,
                liquidity_amount=bounty_sol,
                community_benefit_percentage=self.community_share_percentage,
            )
        else:
            # Use ecosystem token (would need to define this)
            # For now, create a placeholder token mint
            ecosystem_token = Pubkey.new_unique()  # Placeholder
            aeon_result = await self.aeon_integration.generate_liquidity_aeon(
                token_mint=ecosystem_token,
                liquidity_amount=bounty_sol,
                community_benefit_percentage=self.community_share_percentage,
            )
        
        conversion_rate = (
            aeon_result.liquidity_created / (bounty_sol * self.usd_to_sol_rate)
            if bounty_sol > 0
            else 0.0
        )
        
        return ConversionResult(
            success=True,
            bounty_amount=bounty_sol * self.usd_to_sol_rate,
            liquidity_created=aeon_result.liquidity_created,
            community_benefits=aeon_result.community_benefits,
            holders_benefited=aeon_result.holders_benefited,
            conversion_rate=conversion_rate,
            metadata={
                "sum_positive": aeon_result.sum_positive,
                "sustainability_score": aeon_result.sustainability_score,
                "submission_id": submission.submission_id,
                "vulnerability_type": submission.metadata.get("vulnerability_type", ""),
            },
        )

    async def _convert_direct(
        self,
        bounty_sol: float,
        target_token: Optional[Pubkey],
        submission: SubmissionInfo,
    ) -> ConversionResult:
        """Convert bounty directly without AEON.
        
        Args:
            bounty_sol: Bounty amount in SOL
            target_token: Target token for liquidity
            submission: Submission info
            
        Returns:
            Conversion result
        """
        # Calculate community share
        community_share = bounty_sol * self.community_share_percentage
        protocol_share = bounty_sol - community_share
        
        # Create liquidity pool
        if target_token:
            # Calculate token amount (would need actual price)
            token_amount = 0.0  # Placeholder - would calculate from price
            
            liquidity_result = await self.liquidity_provider.create_liquidity_pool(
                token_mint=target_token,
                sol_amount=bounty_sol,
                token_amount=token_amount,
                dex="raydium",
                community_benefit_percentage=self.community_share_percentage,
            )
        else:
            # Use ecosystem token
            ecosystem_token = Pubkey.new_unique()  # Placeholder
            token_amount = 0.0  # Placeholder
            
            liquidity_result = await self.liquidity_provider.create_liquidity_pool(
                token_mint=ecosystem_token,
                sol_amount=bounty_sol,
                token_amount=token_amount,
                dex="raydium",
                community_benefit_percentage=self.community_share_percentage,
            )
        
        if not liquidity_result.success:
            return ConversionResult(
                success=False,
                bounty_amount=bounty_sol * self.usd_to_sol_rate,
                liquidity_created=0.0,
                community_benefits=0.0,
                holders_benefited=0,
                conversion_rate=0.0,
                error_message=liquidity_result.error_message,
            )
        
        # Distribute community benefits
        if target_token and self.community_distributor:
            distribution = await self.community_distributor.distribute_liquidity_benefits(
                token_mint=target_token,
                liquidity_value=community_share,
            )
            holders_benefited = distribution.number_of_holders
        else:
            holders_benefited = 0
        
        conversion_rate = (
            liquidity_result.pool.sol_amount / (bounty_sol * self.usd_to_sol_rate)
            if bounty_sol > 0
            else 0.0
        )
        
        return ConversionResult(
            success=True,
            bounty_amount=bounty_sol * self.usd_to_sol_rate,
            liquidity_created=liquidity_result.pool.sol_amount,
            community_benefits=community_share,
            holders_benefited=holders_benefited,
            conversion_rate=conversion_rate,
            metadata={
                "submission_id": submission.submission_id,
                "pool_address": str(liquidity_result.pool.pool_address),
                "dex": liquidity_result.pool.dex,
            },
        )

    async def convert_all_pending_bounties(
        self,
        target_token: Optional[Pubkey] = None,
        use_aeon: bool = True,
    ) -> List[ConversionResult]:
        """Convert all pending bounty payments to liquidity.
        
        Args:
            target_token: Optional target token for liquidity
            use_aeon: Whether to use AEON principles
            
        Returns:
            List of conversion results
        """
        # This would be called by payment monitor when payments are detected
        # For now, return empty list (would need bounty_tracker integration)
        logger.info("Converting all pending bounties to liquidity...")
        return []

    def get_statistics(self) -> Dict[str, Any]:
        """Get conversion statistics.
        
        Returns:
            Statistics dictionary
        """
        successful_conversions = [
            c for c in self.conversions if c.success
        ]
        
        return {
            "total_bounties_converted_usd": self.total_bounties_converted,
            "total_liquidity_created_sol": self.total_liquidity_created,
            "total_community_benefits_sol": self.total_community_benefits,
            "number_of_conversions": len(successful_conversions),
            "average_conversion_rate": (
                sum(c.conversion_rate for c in successful_conversions)
                / len(successful_conversions)
                if successful_conversions
                else 0.0
            ),
            "total_holders_benefited": sum(
                c.holders_benefited for c in successful_conversions
            ),
        }

