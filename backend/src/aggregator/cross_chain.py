"""
Cross-Chain Aggregator - Unified scanner across all chains simultaneously.

This module scans multiple blockchains for vulnerabilities and opportunities.
"""

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


class Chain(Enum):
    """Supported blockchain networks."""

    SOLANA = "solana"
    ETHEREUM = "ethereum"
    BASE = "base"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    POLYGON = "polygon"
    AVALANCHE = "avalanche"
    BSC = "bsc"


@dataclass
class CrossChainOpportunity:
    """Represents an opportunity found across chains."""

    chain: Chain
    opportunity_type: str
    severity: str
    description: str
    address: Optional[str] = None
    estimated_value: Optional[float] = None
    confidence: float = 0.0


class CrossChainAggregator:
    """
    Aggregates opportunities and vulnerabilities across multiple blockchains.

    Scans all chains simultaneously and provides unified opportunity list.
    """

    def __init__(
        self,
        enabled_chains: Optional[List[Chain]] = None,
        scan_interval: int = 60,  # seconds
    ):
        """Initialize the cross-chain aggregator.

        Args:
            enabled_chains: List of chains to scan (None = all)
            scan_interval: Interval between scans in seconds
        """
        if enabled_chains is None:
            enabled_chains = list(Chain)

        self.enabled_chains = enabled_chains
        self.scan_interval = scan_interval
        self.opportunities: List[CrossChainOpportunity] = []
        self.chain_clients: Dict[Chain, Any] = {}
        self._running = False
        self._scan_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the cross-chain aggregator."""
        if self._running:
            return

        self._running = True
        logger.info(f"Starting cross-chain aggregator for {len(self.enabled_chains)} chains")
        self._scan_task = asyncio.create_task(self._scan_loop())

    async def stop(self):
        """Stop the cross-chain aggregator."""
        if not self._running:
            return

        self._running = False
        if self._scan_task:
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass

        logger.info("Cross-chain aggregator stopped")

    async def _scan_loop(self):
        """Main scanning loop."""
        while self._running:
            try:
                await self.scan_all_chains()
                await asyncio.sleep(self.scan_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Error in scan loop: {e}")
                await asyncio.sleep(self.scan_interval)

    async def scan_all_chains(self) -> List[CrossChainOpportunity]:
        """Scan all enabled chains for opportunities.

        Returns:
            List of all opportunities found
        """
        logger.info(f"Scanning {len(self.enabled_chains)} chains...")

        all_opportunities: List[CrossChainOpportunity] = []

        # Scan each chain in parallel
        tasks = [self.scan_chain(chain) for chain in self.enabled_chains]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for chain, result in zip(self.enabled_chains, results):
            if isinstance(result, Exception):
                logger.error(f"Error scanning {chain.value}: {result}")
                continue

            opportunities = result
            all_opportunities.extend(opportunities)
            logger.info(f"Found {len(opportunities)} opportunities on {chain.value}")

        # Update aggregated opportunities
        self.opportunities = all_opportunities

        logger.info(f"Total opportunities found: {len(all_opportunities)}")
        return all_opportunities

    async def scan_chain(self, chain: Chain) -> List[CrossChainOpportunity]:
        """Scan a specific chain for opportunities.

        Args:
            chain: Chain to scan

        Returns:
            List of opportunities found on this chain
        """
        logger.debug(f"Scanning {chain.value}...")

        opportunities: List[CrossChainOpportunity] = []

        try:
            # Chain-specific scanning logic
            if chain == Chain.SOLANA:
                opportunities = await self._scan_solana()
            elif chain == Chain.ETHEREUM:
                opportunities = await self._scan_ethereum()
            elif chain == Chain.BASE:
                opportunities = await self._scan_base()
            elif chain == Chain.ARBITRUM:
                opportunities = await self._scan_arbitrum()
            elif chain == Chain.OPTIMISM:
                opportunities = await self._scan_optimism()
            elif chain == Chain.POLYGON:
                opportunities = await self._scan_polygon()
            elif chain == Chain.AVALANCHE:
                opportunities = await self._scan_avalanche()
            elif chain == Chain.BSC:
                opportunities = await self._scan_bsc()

        except Exception as e:
            logger.exception(f"Error scanning {chain.value}: {e}")

        return opportunities

    async def _scan_solana(self) -> List[CrossChainOpportunity]:
        """Scan Solana for opportunities.

        Returns:
            List of Solana opportunities
        """
        opportunities: List[CrossChainOpportunity] = []

        try:
            # In production, this would:
            # 1. Connect to Solana RPC
            # 2. Scan for vulnerabilities
            # 3. Detect opportunities
            # 4. Return results

            logger.debug("Scanning Solana...")

            # Placeholder - would use actual Solana scanning
            # This would integrate with our existing Solana client

        except Exception as e:
            logger.exception(f"Error scanning Solana: {e}")

        return opportunities

    async def _scan_ethereum(self) -> List[CrossChainOpportunity]:
        """Scan Ethereum for opportunities.

        Returns:
            List of Ethereum opportunities
        """
        opportunities: List[CrossChainOpportunity] = []

        try:
            logger.debug("Scanning Ethereum...")

            # Placeholder - would use Ethereum RPC
            # This would integrate with Web3.py or similar

        except Exception as e:
            logger.exception(f"Error scanning Ethereum: {e}")

        return opportunities

    async def _scan_base(self) -> List[CrossChainOpportunity]:
        """Scan Base for opportunities."""
        return await self._scan_ethereum()  # Base is EVM-compatible

    async def _scan_arbitrum(self) -> List[CrossChainOpportunity]:
        """Scan Arbitrum for opportunities."""
        return await self._scan_ethereum()  # Arbitrum is EVM-compatible

    async def _scan_optimism(self) -> List[CrossChainOpportunity]:
        """Scan Optimism for opportunities."""
        return await self._scan_ethereum()  # Optimism is EVM-compatible

    async def _scan_polygon(self) -> List[CrossChainOpportunity]:
        """Scan Polygon for opportunities."""
        return await self._scan_ethereum()  # Polygon is EVM-compatible

    async def _scan_avalanche(self) -> List[CrossChainOpportunity]:
        """Scan Avalanche for opportunities."""
        return await self._scan_ethereum()  # Avalanche C-Chain is EVM-compatible

    async def _scan_bsc(self) -> List[CrossChainOpportunity]:
        """Scan BSC for opportunities."""
        return await self._scan_ethereum()  # BSC is EVM-compatible

    def get_opportunities_by_chain(
        self, chain: Chain
    ) -> List[CrossChainOpportunity]:
        """Get opportunities for a specific chain.

        Args:
            chain: Chain to filter by

        Returns:
            List of opportunities on this chain
        """
        return [opp for opp in self.opportunities if opp.chain == chain]

    def get_opportunities_by_severity(
        self, severity: str
    ) -> List[CrossChainOpportunity]:
        """Get opportunities by severity.

        Args:
            severity: Severity level ("critical", "high", "medium", "low")

        Returns:
            List of opportunities with this severity
        """
        return [opp for opp in self.opportunities if opp.severity == severity]

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all opportunities.

        Returns:
            Summary dictionary
        """
        by_chain = {}
        for chain in self.enabled_chains:
            by_chain[chain.value] = len(self.get_opportunities_by_chain(chain))

        by_severity = {
            "critical": len(self.get_opportunities_by_severity("critical")),
            "high": len(self.get_opportunities_by_severity("high")),
            "medium": len(self.get_opportunities_by_severity("medium")),
            "low": len(self.get_opportunities_by_severity("low")),
        }

        return {
            "total_opportunities": len(self.opportunities),
            "by_chain": by_chain,
            "by_severity": by_severity,
            "enabled_chains": [c.value for c in self.enabled_chains],
        }

