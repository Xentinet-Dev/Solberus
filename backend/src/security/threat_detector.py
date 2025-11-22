"""
Enhanced Threat Detection System - Unified threat detection integrating all security modules.

This is the core threat detection system that integrates:
- Governance attack detection
- Time-weighted oracle detection
- Upgrade exploit detection
- Social engineering detection
- Advanced rug detection (planned)
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from solders.pubkey import Pubkey

from core.client import SolanaClient
from interfaces.core import TokenInfo
from utils.logger import get_logger

logger = get_logger(__name__)

# Import security modules
try:
    from security.governance_detector import GovernanceAttackDetector
    from security.social_detector import SocialEngineeringDetector
    from security.time_weighted_oracle import TimeWeightedOracleScanner
    from security.upgrade_detector import UpgradeExploitDetector

    SECURITY_MODULES_AVAILABLE = True
except ImportError:
    SECURITY_MODULES_AVAILABLE = False
    logger.warning("Security modules not available, threat detection will be limited")


@dataclass
class ThreatScore:
    """Represents a comprehensive threat score for a token."""

    total_score: float  # 0.0 to 1.0 (higher = more risky)
    risk_level: str  # "safe", "low", "medium", "high", "critical"
    threats: List[Dict[str, Any]]
    recommendations: List[str]


class EnhancedThreatDetector:
    """
    Enhanced threat detection system that integrates all security modules.

    Provides comprehensive threat analysis for tokens and protocols.
    """

    def __init__(
        self,
        client: SolanaClient,
        enable_governance_scan: bool = True,
        enable_oracle_scan: bool = True,
        enable_upgrade_scan: bool = True,
        enable_social_scan: bool = True,
    ):
        """Initialize the enhanced threat detector.

        Args:
            client: Solana RPC client
            enable_governance_scan: Enable governance attack detection
            enable_oracle_scan: Enable oracle manipulation detection
            enable_upgrade_scan: Enable upgrade exploit detection
            enable_social_scan: Enable social engineering detection
        """
        self.client = client
        self.enable_governance_scan = enable_governance_scan
        self.enable_oracle_scan = enable_oracle_scan
        self.enable_upgrade_scan = enable_upgrade_scan
        self.enable_social_scan = enable_social_scan

        # Initialize security modules
        if SECURITY_MODULES_AVAILABLE:
            if enable_governance_scan:
                self.governance_detector = GovernanceAttackDetector(client)
            else:
                self.governance_detector = None

            if enable_oracle_scan:
                self.oracle_scanner = TimeWeightedOracleScanner(client)
            else:
                self.oracle_scanner = None

            if enable_upgrade_scan:
                self.upgrade_detector = UpgradeExploitDetector(client)
            else:
                self.upgrade_detector = None

            if enable_social_scan:
                self.social_detector = SocialEngineeringDetector()
            else:
                self.social_detector = None
        else:
            self.governance_detector = None
            self.oracle_scanner = None
            self.upgrade_detector = None
            self.social_detector = None
            logger.warning("Security modules not available, threat detection limited")

        self.scan_history: Dict[str, ThreatScore] = {}

    async def scan_token(self, token_info: TokenInfo) -> ThreatScore:
        """Scan a token for threats.

        Args:
            token_info: Token information to scan

        Returns:
            Threat score with all detected threats
        """
        logger.info(f"Scanning token {token_info.mint} for threats...")

        all_threats: List[Dict[str, Any]] = []
        recommendations: List[str] = []

        # Scan token mint address
        mint_threats = await self._scan_address(token_info.mint)
        all_threats.extend(mint_threats)

        # Scan bonding curve if available
        if token_info.bonding_curve:
            curve_threats = await self._scan_address(token_info.bonding_curve)
            all_threats.extend(curve_threats)

        # Scan creator address
        if token_info.creator:
            creator_threats = await self._scan_address(token_info.creator)
            all_threats.extend(creator_threats)

        # Calculate threat score
        threat_score = self._calculate_threat_score(all_threats)

        # Generate recommendations
        recommendations = self._generate_recommendations(threat_score, all_threats)

        # Store scan result
        self.scan_history[str(token_info.mint)] = threat_score

        logger.info(
            f"Token {token_info.mint} threat score: {threat_score.total_score:.2f} "
            f"({threat_score.risk_level})"
        )

        return threat_score

    async def _scan_address(self, address: Pubkey) -> List[Dict[str, Any]]:
        """Scan an address for threats.

        Args:
            address: Address to scan

        Returns:
            List of detected threats
        """
        threats: List[Dict[str, Any]] = []

        try:
            # Scan for upgrade exploits
            if self.upgrade_detector:
                upgrade_threats = await self.upgrade_detector.scan_contract(address)
                for threat in upgrade_threats:
                    threats.append(
                        {
                            "type": "upgrade_exploit",
                            "severity": threat.severity,
                            "description": threat.description,
                            "confidence": threat.confidence,
                        }
                    )

            # Scan for governance attacks (if applicable)
            if self.governance_detector:
                # Only scan if this looks like a governance protocol
                # (simplified - in production would check program type)
                try:
                    governance_threats = await self.governance_detector.scan_governance_protocol(
                        address
                    )
                    for threat in governance_threats:
                        threats.append(
                            {
                                "type": "governance_attack",
                                "severity": threat.severity,
                                "description": threat.description,
                                "confidence": threat.confidence,
                            }
                        )
                except Exception:
                    # Not a governance protocol, skip
                    pass

        except Exception as e:
            logger.exception(f"Error scanning address {address}: {e}")

        return threats

    def _calculate_threat_score(self, threats: List[Dict[str, Any]]) -> ThreatScore:
        """Calculate overall threat score from detected threats.

        Args:
            threats: List of detected threats

        Returns:
            Threat score
        """
        if not threats:
            return ThreatScore(
                total_score=0.0,
                risk_level="safe",
                threats=[],
                recommendations=["Token appears safe"],
            )

        # Weight threats by severity
        severity_weights = {
            "critical": 1.0,
            "high": 0.7,
            "medium": 0.4,
            "low": 0.2,
        }

        # Calculate weighted score
        total_weight = 0.0
        for threat in threats:
            severity = threat.get("severity", "low")
            confidence = threat.get("confidence", 0.5)
            weight = severity_weights.get(severity, 0.2)
            total_weight += weight * confidence

        # Normalize to 0.0-1.0
        max_possible_weight = len(threats) * 1.0  # All critical with 1.0 confidence
        if max_possible_weight > 0:
            total_score = min(total_weight / max_possible_weight, 1.0)
        else:
            total_score = 0.0

        # Determine risk level
        if total_score >= 0.8:
            risk_level = "critical"
        elif total_score >= 0.6:
            risk_level = "high"
        elif total_score >= 0.4:
            risk_level = "medium"
        elif total_score >= 0.2:
            risk_level = "low"
        else:
            risk_level = "safe"

        return ThreatScore(
            total_score=total_score,
            risk_level=risk_level,
            threats=threats,
            recommendations=[],
        )

    def _generate_recommendations(
        self, threat_score: ThreatScore, threats: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate recommendations based on threat score.

        Args:
            threat_score: Calculated threat score
            threats: List of detected threats

        Returns:
            List of recommendations
        """
        recommendations: List[str] = []

        if threat_score.risk_level == "critical":
            recommendations.append("⚠️ CRITICAL RISK: Do not trade this token")
            recommendations.append("Multiple critical vulnerabilities detected")
        elif threat_score.risk_level == "high":
            recommendations.append("⚠️ HIGH RISK: Exercise extreme caution")
            recommendations.append("Consider avoiding this token")
        elif threat_score.risk_level == "medium":
            recommendations.append("⚠️ MEDIUM RISK: Proceed with caution")
            recommendations.append("Monitor closely if trading")
        elif threat_score.risk_level == "low":
            recommendations.append("✓ LOW RISK: Generally safe")
            recommendations.append("Standard precautions recommended")
        else:
            recommendations.append("✓ SAFE: No significant threats detected")

        # Add specific recommendations based on threat types
        threat_types = {t.get("type") for t in threats}
        if "upgrade_exploit" in threat_types:
            recommendations.append("Upgrade vulnerabilities detected - potential for exploits")
        if "governance_attack" in threat_types:
            recommendations.append("Governance attack vectors detected - high-value bug bounty potential")

        return recommendations

    def should_trade(self, threat_score: ThreatScore, max_risk_level: str = "medium") -> bool:
        """Determine if trading should proceed based on threat score.

        Args:
            threat_score: Threat score to evaluate
            max_risk_level: Maximum acceptable risk level

        Returns:
            True if trading should proceed, False otherwise
        """
        risk_levels = ["safe", "low", "medium", "high", "critical"]
        max_index = risk_levels.index(max_risk_level)
        current_index = risk_levels.index(threat_score.risk_level)

        return current_index <= max_index

    def get_scan_summary(self) -> Dict[str, Any]:
        """Get summary of all scans.

        Returns:
            Summary dictionary
        """
        total_scans = len(self.scan_history)
        risk_distribution = {
            "safe": 0,
            "low": 0,
            "medium": 0,
            "high": 0,
            "critical": 0,
        }

        for score in self.scan_history.values():
            risk_distribution[score.risk_level] = risk_distribution.get(
                score.risk_level, 0
            ) + 1

        return {
            "total_scans": total_scans,
            "risk_distribution": risk_distribution,
            "modules_enabled": {
                "governance": self.enable_governance_scan and self.governance_detector is not None,
                "oracle": self.enable_oracle_scan and self.oracle_scanner is not None,
                "upgrade": self.enable_upgrade_scan and self.upgrade_detector is not None,
                "social": self.enable_social_scan and self.social_detector is not None,
            },
        }

