"""
Time-Weighted Oracle Detection - Detects multi-block manipulation and gradual price skew.

This module identifies time-weighted average price (TWAP) manipulation attacks.
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from solders.pubkey import Pubkey

from core.client import SolanaClient
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class OracleThreat:
    """Represents a detected oracle manipulation threat."""

    threat_type: str
    severity: str  # "critical", "high", "medium", "low"
    description: str
    oracle_address: Optional[str] = None
    manipulation_duration: Optional[int] = None  # blocks
    price_skew_percentage: Optional[float] = None
    exploit_vector: Optional[str] = None
    confidence: float = 0.0  # 0.0 to 1.0


class TimeWeightedOracleScanner:
    """
    Detects time-weighted oracle manipulation including:
    - Multi-block price manipulation
    - Gradual price skew attacks
    - Long-tail poisoning
    - TWAP manipulation
    """

    def __init__(self, client: SolanaClient):
        """Initialize the time-weighted oracle scanner.

        Args:
            client: Solana RPC client
        """
        self.client = client
        self.detected_threats: List[OracleThreat] = []
        self.price_history: Dict[str, List[float]] = {}  # oracle -> price history

    async def scan_oracle(
        self, oracle_address: Pubkey, lookback_blocks: int = 100
    ) -> List[OracleThreat]:
        """Scan an oracle for time-weighted manipulation.

        Args:
            oracle_address: Address of the oracle
            lookback_blocks: Number of blocks to analyze

        Returns:
            List of detected threats
        """
        logger.info(f"Scanning oracle: {oracle_address} (last {lookback_blocks} blocks)")

        threats: List[OracleThreat] = []

        # Get price history
        price_history = await self._get_price_history(oracle_address, lookback_blocks)

        # Detect multi-block manipulation
        multi_block_threats = await self._detect_multi_block_manipulation(
            oracle_address, price_history
        )
        threats.extend(multi_block_threats)

        # Detect gradual price skew
        skew_threats = await self._detect_gradual_price_skew(
            oracle_address, price_history
        )
        threats.extend(skew_threats)

        # Detect long-tail poisoning
        poisoning_threats = await self._detect_long_tail_poisoning(
            oracle_address, price_history
        )
        threats.extend(poisoning_threats)

        # Detect TWAP manipulation
        twap_threats = await self._detect_twap_manipulation(
            oracle_address, price_history
        )
        threats.extend(twap_threats)

        self.detected_threats.extend(threats)
        logger.info(f"Detected {len(threats)} oracle manipulation threats")

        return threats

    async def _get_price_history(
        self, oracle_address: Pubkey, lookback_blocks: int
    ) -> List[float]:
        """Get price history for an oracle.

        Args:
            oracle_address: Oracle address
            lookback_blocks: Number of blocks to look back

        Returns:
            List of historical prices
        """
        try:
            # In production, this would:
            # 1. Fetch historical oracle updates
            # 2. Extract prices from each update
            # 3. Return ordered list of prices

            oracle_key = str(oracle_address)

            if oracle_key in self.price_history:
                return self.price_history[oracle_key][-lookback_blocks:]

            # Placeholder - would fetch from RPC
            return []

        except Exception as e:
            logger.exception(f"Error fetching price history: {e}")
            return []

    async def _detect_multi_block_manipulation(
        self, oracle_address: Pubkey, price_history: List[float]
    ) -> List[OracleThreat]:
        """Detect multi-block price manipulation.

        Multi-block manipulation occurs when an attacker:
        1. Gradually moves price over multiple blocks
        2. Stays below detection thresholds
        3. Achieves significant cumulative skew

        Args:
            oracle_address: Oracle address
            price_history: Historical prices

        Returns:
            List of detected multi-block manipulation threats
        """
        threats: List[OracleThreat] = []

        try:
            if len(price_history) < 10:
                return threats

            # Calculate price changes over blocks
            price_changes = [
                abs(price_history[i] - price_history[i - 1])
                / price_history[i - 1]
                for i in range(1, len(price_history))
            ]

            # Detect gradual manipulation (small changes over many blocks)
            window_size = 20
            for i in range(window_size, len(price_changes)):
                window_changes = price_changes[i - window_size : i]
                cumulative_change = sum(window_changes)

                # If cumulative change is significant but individual changes are small
                if cumulative_change > 0.05 and max(window_changes) < 0.01:
                    threat = OracleThreat(
                        threat_type="multi_block_manipulation",
                        severity="high",
                        description=f"Detected gradual price manipulation over {window_size} blocks",
                        oracle_address=str(oracle_address),
                        manipulation_duration=window_size,
                        price_skew_percentage=cumulative_change * 100,
                        confidence=0.7,
                    )
                    threats.append(threat)
                    logger.warning(
                        f"Multi-block manipulation detected: {cumulative_change*100:.2f}% skew over {window_size} blocks"
                    )

        except Exception as e:
            logger.exception(f"Error detecting multi-block manipulation: {e}")

        return threats

    async def _detect_gradual_price_skew(
        self, oracle_address: Pubkey, price_history: List[float]
    ) -> List[OracleThreat]:
        """Detect gradual price skew attacks.

        Args:
            oracle_address: Oracle address
            price_history: Historical prices

        Returns:
            List of detected gradual skew threats
        """
        threats: List[OracleThreat] = []

        try:
            if len(price_history) < 30:
                return threats

            # Calculate moving average
            window = 10
            moving_avg = [
                sum(price_history[i - window : i]) / window
                for i in range(window, len(price_history))
            ]

            # Detect if price is consistently deviating from moving average
            for i, price in enumerate(price_history[window:]):
                avg = moving_avg[i]
                deviation = abs(price - avg) / avg

                if deviation > 0.03:  # 3% deviation
                    threat = OracleThreat(
                        threat_type="gradual_price_skew",
                        severity="medium",
                        description=f"Detected gradual price skew: {deviation*100:.2f}% deviation from average",
                        oracle_address=str(oracle_address),
                        price_skew_percentage=deviation * 100,
                        confidence=0.6,
                    )
                    threats.append(threat)

        except Exception as e:
            logger.exception(f"Error detecting gradual price skew: {e}")

        return threats

    async def _detect_long_tail_poisoning(
        self, oracle_address: Pubkey, price_history: List[float]
    ) -> List[OracleThreat]:
        """Detect long-tail poisoning attacks.

        Long-tail poisoning occurs when an attacker:
        1. Manipulates price over extended period (hours)
        2. Stays below per-block thresholds
        3. Achieves significant cumulative effect

        Args:
            oracle_address: Oracle address
            price_history: Historical prices

        Returns:
            List of detected long-tail poisoning threats
        """
        threats: List[OracleThreat] = []

        try:
            if len(price_history) < 100:
                return threats

            # Analyze long-term trends
            # Check if price has been gradually moving in one direction
            # over extended period (e.g., 7200 seconds = 2 hours)

            # Calculate trend
            start_price = price_history[0]
            end_price = price_history[-1]
            total_change = abs(end_price - start_price) / start_price

            # If significant change over long period with small per-block changes
            if total_change > 0.10:  # 10% total change
                avg_block_change = total_change / len(price_history)
                if avg_block_change < 0.001:  # Small per-block changes
                    threat = OracleThreat(
                        threat_type="long_tail_poisoning",
                        severity="high",
                        description=f"Detected long-tail poisoning: {total_change*100:.2f}% change over {len(price_history)} blocks",
                        oracle_address=str(oracle_address),
                        manipulation_duration=len(price_history),
                        price_skew_percentage=total_change * 100,
                        confidence=0.8,
                    )
                    threats.append(threat)
                    logger.warning(
                        f"Long-tail poisoning detected: {total_change*100:.2f}% over {len(price_history)} blocks"
                    )

        except Exception as e:
            logger.exception(f"Error detecting long-tail poisoning: {e}")

        return threats

    async def _detect_twap_manipulation(
        self, oracle_address: Pubkey, price_history: List[float]
    ) -> List[OracleThreat]:
        """Detect TWAP (Time-Weighted Average Price) manipulation.

        Args:
            oracle_address: Oracle address
            price_history: Historical prices

        Returns:
            List of detected TWAP manipulation threats
        """
        threats: List[OracleThreat] = []

        try:
            if len(price_history) < 20:
                return threats

            # Calculate TWAP
            twap = sum(price_history) / len(price_history)

            # Check if recent prices are consistently skewed
            recent_prices = price_history[-10:]
            recent_avg = sum(recent_prices) / len(recent_prices)

            deviation = abs(recent_avg - twap) / twap

            if deviation > 0.05:  # 5% deviation from TWAP
                threat = OracleThreat(
                    threat_type="twap_manipulation",
                    severity="high",
                    description=f"Detected TWAP manipulation: {deviation*100:.2f}% deviation",
                    oracle_address=str(oracle_address),
                    price_skew_percentage=deviation * 100,
                    confidence=0.75,
                )
                threats.append(threat)

        except Exception as e:
            logger.exception(f"Error detecting TWAP manipulation: {e}")

        return threats

    def get_threat_summary(self) -> Dict[str, Any]:
        """Get a summary of all detected threats.

        Returns:
            Summary dictionary with threat counts and details
        """
        critical = [t for t in self.detected_threats if t.severity == "critical"]
        high = [t for t in self.detected_threats if t.severity == "high"]
        medium = [t for t in self.detected_threats if t.severity == "medium"]
        low = [t for t in self.detected_threats if t.severity == "low"]

        return {
            "total_threats": len(self.detected_threats),
            "critical": len(critical),
            "high": len(high),
            "medium": len(medium),
            "low": len(low),
            "threats": [
                {
                    "type": t.threat_type,
                    "severity": t.severity,
                    "description": t.description,
                    "confidence": t.confidence,
                    "price_skew": t.price_skew_percentage,
                }
                for t in self.detected_threats
            ],
        }

