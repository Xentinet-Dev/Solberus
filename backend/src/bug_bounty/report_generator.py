"""
Automated bug bounty report generator.

This module automatically generates Immunefi-compliant reports from threat detection results.
"""

from typing import List, Optional

from interfaces.core import TokenInfo
from security.comprehensive_threat_detector import (
    ThreatCategory,
    ThreatDetection,
    ThreatScore,
)
from utils.logger import get_logger

from bug_bounty.poc_generator import PoC, PoCGenerator
from bug_bounty.report_templates import (
    ImmunefiReport,
    ImmunefiReportTemplate,
    SeverityLevel,
)

logger = get_logger(__name__)


class BugBountyReporter:
    """Automatically generate bug bounty reports from threat detection."""

    def __init__(self, bounty_tracker=None):
        """Initialize bug bounty reporter.
        
        Args:
            bounty_tracker: Optional BountyTracker instance for tracking submissions
        """
        self.poc_generator = PoCGenerator()
        self.bounty_tracker = bounty_tracker
        self.reports_generated = 0

    def _map_severity(self, severity: str) -> SeverityLevel:
        """Map threat severity to Immunefi severity level.
        
        Args:
            severity: Threat severity string
            
        Returns:
            Immunefi severity level
        """
        severity_lower = severity.lower()
        if severity_lower in ["critical"]:
            return SeverityLevel.CRITICAL
        elif severity_lower in ["high"]:
            return SeverityLevel.HIGH
        elif severity_lower in ["medium"]:
            return SeverityLevel.MEDIUM
        elif severity_lower in ["low"]:
            return SeverityLevel.LOW
        else:
            return SeverityLevel.INFORMATIONAL

    def _calculate_potential_loss(
        self, threat: ThreatDetection, token_info: TokenInfo
    ) -> Optional[float]:
        """Estimate potential financial loss from threat.
        
        Args:
            threat: Detected threat
            token_info: Token information
            
        Returns:
            Estimated potential loss in USD (or None if cannot estimate)
        """
        # Use market cap as baseline for potential loss
        if token_info.market_cap_sol:
            # Estimate loss as percentage of market cap based on severity
            severity_multipliers = {
                "critical": 0.5,  # 50% of market cap
                "high": 0.25,  # 25% of market cap
                "medium": 0.10,  # 10% of market cap
                "low": 0.05,  # 5% of market cap
            }
            
            multiplier = severity_multipliers.get(
                threat.severity.lower(), 0.01
            )
            
            # Convert SOL to USD (rough estimate: 1 SOL = $150)
            sol_to_usd = 150.0
            potential_loss_sol = token_info.market_cap_sol * multiplier
            potential_loss_usd = potential_loss_sol * sol_to_usd
            
            return potential_loss_usd
        
        return None

    def _generate_title(
        self, threat: ThreatDetection, token_info: TokenInfo
    ) -> str:
        """Generate report title from threat.
        
        Args:
            threat: Detected threat
            token_info: Token information
            
        Returns:
            Report title
        """
        category_name = threat.category.value.replace("_", " ").title()
        return f"{category_name} Vulnerability in {token_info.symbol} ({token_info.name})"

    def _generate_summary(
        self, threat: ThreatDetection, token_info: TokenInfo
    ) -> str:
        """Generate executive summary from threat.
        
        Args:
            threat: Detected threat
            token_info: Token information
            
        Returns:
            Executive summary
        """
        return (
            f"A {threat.severity} severity vulnerability has been detected in "
            f"{token_info.symbol} ({token_info.name}). "
            f"{threat.description} "
            f"This vulnerability could potentially result in significant financial loss "
            f"or compromise of user funds."
        )

    def _generate_impact_description(
        self, threat: ThreatDetection, token_info: TokenInfo
    ) -> str:
        """Generate impact description from threat.
        
        Args:
            threat: Detected threat
            token_info: Token information
            
        Returns:
            Impact description
        """
        impact = threat.predicted_impact or threat.description
        
        if token_info.market_cap_sol:
            impact += (
                f" Given the current market cap of {token_info.market_cap_sol:.2f} SOL, "
                f"this vulnerability could affect a significant portion of the token's value."
            )
        
        return impact

    def _get_affected_contracts(
        self, threat: ThreatDetection, token_info: TokenInfo
    ) -> List[str]:
        """Get list of affected contract addresses.
        
        Args:
            threat: Detected threat
            token_info: Token information
            
        Returns:
            List of affected contract addresses
        """
        contracts = [str(token_info.mint)]
        
        if token_info.bonding_curve:
            contracts.append(str(token_info.bonding_curve))
        
        # Add any contracts from evidence
        if threat.evidence:
            if "contract_address" in threat.evidence:
                contracts.append(str(threat.evidence["contract_address"]))
            if "program_id" in threat.evidence:
                contracts.append(str(threat.evidence["program_id"]))
        
        return list(set(contracts))  # Remove duplicates

    def _generate_recommendations(
        self, threat: ThreatDetection
    ) -> List[str]:
        """Generate recommendations based on threat type.
        
        Args:
            threat: Detected threat
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        category = threat.category
        
        # Category-specific recommendations
        if category == ThreatCategory.HONEYPOT:
            recommendations.extend([
                "Implement proper sell functionality in the token contract",
                "Remove any transfer restrictions that prevent users from selling",
                "Ensure all token holders can freely transfer their tokens",
            ])
        elif category == ThreatCategory.ORACLE_MANIPULATION:
            recommendations.extend([
                "Implement multiple oracle sources for price feeds",
                "Add time-weighted average price (TWAP) mechanisms",
                "Implement circuit breakers for extreme price deviations",
            ])
        elif category == ThreatCategory.RUG_PULL_IMMINENT:
            recommendations.extend([
                "Lock liquidity pool tokens in a time-locked contract",
                "Implement multi-signature controls for critical operations",
                "Add transparency mechanisms for creator actions",
            ])
        elif category == ThreatCategory.FLASH_LOAN_MANIPULATION:
            recommendations.extend([
                "Implement flash loan attack prevention mechanisms",
                "Add reentrancy guards to critical functions",
                "Use time-weighted pricing to prevent manipulation",
            ])
        else:
            # Generic recommendations
            recommendations.extend([
                "Conduct a comprehensive security audit",
                "Implement additional security checks and validations",
                "Add monitoring and alerting for suspicious activities",
            ])
        
        return recommendations

    async def generate_report_from_threat(
        self,
        threat: ThreatDetection,
        token_info: TokenInfo,
        threat_score: Optional[ThreatScore] = None,
    ) -> Optional[ImmunefiReport]:
        """Generate Immunefi report from a detected threat.
        
        Args:
            threat: Detected threat
            token_info: Token information
            threat_score: Optional comprehensive threat score
            
        Returns:
            Immunefi-compliant report, or None if threat is not reportable
        """
        # Only generate reports for high/critical severity threats
        if threat.severity.lower() not in ["critical", "high"]:
            logger.debug(
                f"Skipping report generation for {threat.severity} severity threat: "
                f"{threat.category.value}"
            )
            return None
        
        logger.info(
            f"Generating bug bounty report for {threat.severity} threat: "
            f"{threat.category.value} in {token_info.symbol}"
        )
        
        try:
            # Generate PoC
            poc = await self.poc_generator.generate_poc(threat, token_info)
            
            # Calculate potential loss
            potential_loss = self._calculate_potential_loss(threat, token_info)
            
            # Generate report
            report = ImmunefiReportTemplate.create_from_vulnerability(
                title=self._generate_title(threat, token_info),
                summary=self._generate_summary(threat, token_info),
                severity=self._map_severity(threat.severity),
                impact=self._generate_impact_description(threat, token_info),
                affected_contracts=self._get_affected_contracts(threat, token_info),
                poc_description=poc.description,
                poc_code=poc.code,
                poc_steps=poc.steps,
                recommendations=self._generate_recommendations(threat),
                vulnerability_type=threat.category.value,
                potential_loss=potential_loss,
            )
            
            self.reports_generated += 1
            
            # Create submission record if tracker available
            if self.bounty_tracker:
                submission = self.bounty_tracker.create_submission(
                    report, platform="immunefi"
                )
                logger.info(
                    f"Created submission record: {submission.submission_id} "
                    f"for report: {report.title}"
                )
            
            logger.info(
                f"Generated bug bounty report: {report.title} "
                f"(Estimated bounty: ${report.estimated_bounty:,.2f} USD)"
            )
            
            return report
            
        except Exception as e:
            logger.exception(f"Error generating report from threat: {e}")
            return None

    async def generate_reports_from_scan(
        self,
        threat_score: ThreatScore,
        token_info: TokenInfo,
    ) -> List[ImmunefiReport]:
        """Generate reports from comprehensive threat scan.
        
        Args:
            threat_score: Comprehensive threat score
            token_info: Token information
            
        Returns:
            List of generated reports
        """
        reports = []
        
        # Generate reports for each high/critical threat
        for threat in threat_score.detected_threats:
            if threat.severity.lower() in ["critical", "high"]:
                report = await self.generate_report_from_threat(
                    threat, token_info, threat_score
                )
                if report:
                    reports.append(report)
        
        logger.info(
            f"Generated {len(reports)} bug bounty reports from threat scan "
            f"for {token_info.symbol}"
        )
        
        return reports

    def get_statistics(self) -> dict:
        """Get reporter statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            "reports_generated": self.reports_generated,
        }

