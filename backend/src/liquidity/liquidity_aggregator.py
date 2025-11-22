"""
Multi-DEX liquidity aggregation for better depth and price discovery.

Features:
- Multi-DEX liquidity checking
- Optimal distribution calculation
- Cross-DEX aggregation
- Reduced slippage
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from solders.pubkey import Pubkey

from core.client import SolanaClient
from liquidity.liquidity_provider import LiquidityProvider
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DEXLiquidityInfo:
    """Liquidity information for a specific DEX."""

    dex: str
    pool_address: Optional[Pubkey]
    sol_reserves: float
    token_reserves: float
    price: float
    depth_score: float  # 0-100, higher is better


@dataclass
class AggregatedLiquidity:
    """Aggregated liquidity across multiple DEXs."""

    token_mint: Pubkey
    total_sol_liquidity: float
    total_token_liquidity: float
    dexes: List[DEXLiquidityInfo]
    optimal_distribution: Dict[str, float]  # DEX -> percentage
    aggregated_price: float
    depth_score: float  # Overall depth score


class LiquidityAggregator:
    """
    Multi-DEX liquidity aggregation system.
    
    Checks liquidity across multiple DEXs and creates optimal distribution.
    """

    def __init__(
        self,
        client: SolanaClient,
        liquidity_provider: Optional[LiquidityProvider] = None,
    ):
        """Initialize liquidity aggregator.

        Args:
            client: Solana RPC client
            liquidity_provider: Optional liquidity provider for creating pools
        """
        self.client = client
        self.liquidity_provider = liquidity_provider
        self.supported_dexes = ["raydium", "pumpswap", "orca"]

    async def check_liquidity_across_dexs(
        self, token_mint: Pubkey
    ) -> List[DEXLiquidityInfo]:
        """Check liquidity across all supported DEXs.

        Args:
            token_mint: Token mint address

        Returns:
            List of liquidity info for each DEX
        """
        logger.info(f"Checking liquidity across DEXs for {token_mint}")

        # In production, would query each DEX for pool info
        # For now, return placeholder data
        dex_info = []

        for dex in self.supported_dexes:
            # Placeholder: Would fetch actual pool data
            await asyncio.sleep(0.1)

            info = DEXLiquidityInfo(
                dex=dex,
                pool_address=Pubkey.new_unique(),  # Placeholder
                sol_reserves=100.0,  # Placeholder
                token_reserves=1000000.0,  # Placeholder
                price=0.0001,  # Placeholder
                depth_score=50.0,  # Placeholder
            )
            dex_info.append(info)

        return dex_info

    async def aggregate_liquidity(
        self,
        token_mint: Pubkey,
        target_amount_sol: float,
    ) -> AggregatedLiquidity:
        """Aggregate liquidity across multiple DEXs.

        Args:
            token_mint: Token mint address
            target_amount_sol: Target SOL amount for liquidity

        Returns:
            Aggregated liquidity information
        """
        logger.info(
            f"Aggregating liquidity: {target_amount_sol:.6f} SOL for {token_mint}"
        )

        # Check liquidity across all DEXs
        dex_info = await self.check_liquidity_across_dexs(token_mint)

        # Calculate total liquidity
        total_sol = sum(info.sol_reserves for info in dex_info)
        total_tokens = sum(info.token_reserves for info in dex_info)

        # Calculate optimal distribution
        # Strategy: Distribute based on depth score
        total_score = sum(info.depth_score for info in dex_info)
        optimal_distribution = {
            info.dex: (info.depth_score / total_score) if total_score > 0 else 1.0 / len(dex_info)
            for info in dex_info
        }

        # Calculate aggregated price (weighted average)
        total_value = sum(info.sol_reserves for info in dex_info)
        aggregated_price = (
            sum(info.price * info.sol_reserves for info in dex_info) / total_value
            if total_value > 0
            else 0.0
        )

        # Calculate overall depth score
        depth_score = sum(info.depth_score for info in dex_info) / len(dex_info)

        aggregated = AggregatedLiquidity(
            token_mint=token_mint,
            total_sol_liquidity=total_sol,
            total_token_liquidity=total_tokens,
            dexes=dex_info,
            optimal_distribution=optimal_distribution,
            aggregated_price=aggregated_price,
            depth_score=depth_score,
        )

        logger.info(
            f"✓ Aggregated liquidity: {total_sol:.6f} SOL across {len(dex_info)} DEX(s), "
            f"depth score: {depth_score:.1f}/100"
        )

        return aggregated

    async def create_aggregated_liquidity(
        self,
        token_mint: Pubkey,
        total_sol: float,
        total_tokens: float,
    ) -> AggregatedLiquidity:
        """Create liquidity across multiple DEXs with optimal distribution.

        Args:
            token_mint: Token mint address
            total_sol: Total SOL to distribute
            total_tokens: Total tokens to distribute

        Returns:
            Aggregated liquidity result
        """
        logger.info(
            f"Creating aggregated liquidity: {total_sol:.6f} SOL + {total_tokens:.6f} tokens "
            f"for {token_mint}"
        )

        # Get optimal distribution
        aggregated = await self.aggregate_liquidity(token_mint, total_sol)

        # Create liquidity on each DEX based on optimal distribution
        if self.liquidity_provider:
            tasks = []
            for dex_info in aggregated.dexes:
                sol_amount = total_sol * aggregated.optimal_distribution[dex_info.dex]
                token_amount = total_tokens * aggregated.optimal_distribution[dex_info.dex]

                tasks.append(
                    self.liquidity_provider.create_liquidity_pool(
                        token_mint=token_mint,
                        sol_amount=sol_amount,
                        token_amount=token_amount,
                        dex=dex_info.dex,
                    )
                )

            # Create pools concurrently
            await asyncio.gather(*tasks, return_exceptions=True)

        return aggregated

    def get_summary(self) -> Dict[str, Any]:
        """Get aggregator summary.

        Returns:
            Summary dictionary
        """
        return {
            "supported_dexes": self.supported_dexes,
            "aggregation_enabled": True,
        }

