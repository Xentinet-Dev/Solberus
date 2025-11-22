"""
Social Engineering Detection - Detects phishing, fake admins, and wallet drainers.

This module integrates with ClarityShield SDK for anti-phishing protection.
"""

import asyncio
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)

# Optional ClarityShield integration
try:
    # Placeholder for ClarityShield SDK integration
    CLARITYSHIELD_AVAILABLE = False  # Set to True when SDK is integrated
except ImportError:
    CLARITYSHIELD_AVAILABLE = False


@dataclass
class SocialThreat:
    """Represents a detected social engineering threat."""

    threat_type: str
    severity: str  # "critical", "high", "medium", "low"
    description: str
    source: Optional[str] = None  # URL, message, etc.
    detected_pattern: Optional[str] = None
    confidence: float = 0.0  # 0.0 to 1.0


class SocialEngineeringDetector:
    """
    Detects social engineering attacks including:
    - Phishing attempts
    - Fake admin accounts
    - Wallet drainer links
    - Discord/Telegram scams
    - Support impersonation
    """

    def __init__(self, enable_clarityshield: bool = True):
        """Initialize the social engineering detector.

        Args:
            enable_clarityshield: Enable ClarityShield SDK integration
        """
        self.enable_clarityshield = enable_clarityshield and CLARITYSHIELD_AVAILABLE
        self.detected_threats: List[SocialThreat] = []
        self.phishing_patterns = self._load_phishing_patterns()
        self.drainer_patterns = self._load_drainer_patterns()

    def _load_phishing_patterns(self) -> List[re.Pattern]:
        """Load phishing detection patterns.

        Returns:
            List of compiled regex patterns
        """
        patterns = [
            r"support.*team",
            r"customer.*service",
            r"click.*here",
            r"verify.*wallet",
            r"connect.*wallet",
            r"claim.*reward",
            r"urgent.*action",
            r"your.*account.*suspended",
            r"verify.*identity",
            r"security.*alert",
        ]
        return [re.compile(pattern, re.IGNORECASE) for pattern in patterns]

    def _load_drainer_patterns(self) -> List[re.Pattern]:
        """Load wallet drainer detection patterns.

        Returns:
            List of compiled regex patterns
        """
        patterns = [
            r"drainer",
            r"wallet.*drain",
            r"approve.*all",
            r"unlimited.*approval",
            r"revoke.*access",
        ]
        return [re.compile(pattern, re.IGNORECASE) for pattern in patterns]

    async def scan_message(self, message: str, source: str = "unknown") -> List[SocialThreat]:
        """Scan a message for social engineering threats.

        Args:
            message: Message content to scan
            source: Source of the message (URL, channel, etc.)

        Returns:
            List of detected threats
        """
        threats: List[SocialThreat] = []

        # Check for phishing patterns
        phishing_threats = self._detect_phishing(message, source)
        threats.extend(phishing_threats)

        # Check for drainer patterns
        drainer_threats = self._detect_drainers(message, source)
        threats.extend(drainer_threats)

        # Check URLs if present
        url_threats = await self._detect_malicious_urls(message, source)
        threats.extend(url_threats)

        # Use ClarityShield if available
        if self.enable_clarityshield:
            clarityshield_threats = await self._clarityshield_scan(message, source)
            threats.extend(clarityshield_threats)

        self.detected_threats.extend(threats)
        return threats

    def _detect_phishing(self, message: str, source: str) -> List[SocialThreat]:
        """Detect phishing attempts in message.

        Args:
            message: Message content
            source: Message source

        Returns:
            List of detected phishing threats
        """
        threats: List[SocialThreat] = []

        for pattern in self.phishing_patterns:
            if pattern.search(message):
                threat = SocialThreat(
                    threat_type="phishing",
                    severity="high",
                    description=f"Phishing pattern detected: {pattern.pattern}",
                    source=source,
                    detected_pattern=pattern.pattern,
                    confidence=0.7,
                )
                threats.append(threat)
                logger.warning(f"Phishing threat detected: {pattern.pattern}")

        return threats

    def _detect_drainers(self, message: str, source: str) -> List[SocialThreat]:
        """Detect wallet drainer patterns.

        Args:
            message: Message content
            source: Message source

        Returns:
            List of detected drainer threats
        """
        threats: List[SocialThreat] = []

        for pattern in self.drainer_patterns:
            if pattern.search(message):
                threat = SocialThreat(
                    threat_type="wallet_drainer",
                    severity="critical",
                    description=f"Wallet drainer pattern detected: {pattern.pattern}",
                    source=source,
                    detected_pattern=pattern.pattern,
                    confidence=0.9,
                )
                threats.append(threat)
                logger.critical(f"Wallet drainer threat detected: {pattern.pattern}")

        return threats

    async def _detect_malicious_urls(
        self, message: str, source: str
    ) -> List[SocialThreat]:
        """Detect malicious URLs in message.

        Args:
            message: Message content
            source: Message source

        Returns:
            List of detected URL threats
        """
        threats: List[SocialThreat] = []

        # Extract URLs from message
        url_pattern = re.compile(r"https?://[^\s]+")
        urls = url_pattern.findall(message)

        for url in urls:
            # Check for suspicious domains
            suspicious_domains = [
                "wallet-connect",
                "verify-wallet",
                "claim-reward",
                "secure-wallet",
            ]

            if any(domain in url.lower() for domain in suspicious_domains):
                threat = SocialThreat(
                    threat_type="malicious_url",
                    severity="high",
                    description=f"Suspicious URL detected: {url}",
                    source=source,
                    detected_pattern=url,
                    confidence=0.8,
                )
                threats.append(threat)
                logger.warning(f"Malicious URL detected: {url}")

        return threats

    async def _clarityshield_scan(
        self, message: str, source: str
    ) -> List[SocialThreat]:
        """Scan using ClarityShield SDK.

        Args:
            message: Message content
            source: Message source

        Returns:
            List of detected threats from ClarityShield
        """
        threats: List[SocialThreat] = []

        if not self.enable_clarityshield:
            return threats

        try:
            # Placeholder for ClarityShield SDK integration
            # In production, this would call the ClarityShield API
            logger.debug("ClarityShield scan (placeholder)")

        except Exception as e:
            logger.exception(f"Error in ClarityShield scan: {e}")

        return threats

    async def detect_fake_admin(
        self, username: str, channel: str
    ) -> List[SocialThreat]:
        """Detect fake admin accounts.

        Args:
            username: Username to check
            channel: Channel where user appears

        Returns:
            List of detected fake admin threats
        """
        threats: List[SocialThreat] = []

        # Check for common fake admin patterns
        fake_patterns = [
            r"admin.*support",
            r"official.*support",
            r"team.*member",
            r"moderator",
        ]

        for pattern in fake_patterns:
            if re.search(pattern, username, re.IGNORECASE):
                threat = SocialThreat(
                    threat_type="fake_admin",
                    severity="high",
                    description=f"Potential fake admin detected: {username}",
                    source=channel,
                    detected_pattern=pattern,
                    confidence=0.6,
                )
                threats.append(threat)
                logger.warning(f"Fake admin detected: {username}")

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
                    "source": t.source,
                }
                for t in self.detected_threats
            ],
        }

