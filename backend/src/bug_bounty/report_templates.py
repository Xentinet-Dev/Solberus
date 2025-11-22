"""
Immunefi-compliant bug bounty report templates.

This module provides templates and formatting for bug bounty reports
that comply with Immunefi's reporting standards.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


class SeverityLevel(Enum):
    """Immunefi severity levels."""

    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    INFORMATIONAL = "Informational"


class ImpactType(Enum):
    """Types of impact for bug reports."""

    FINANCIAL = "Financial"
    ACCESS_CONTROL = "Access Control"
    DATA_INTEGRITY = "Data Integrity"
    AVAILABILITY = "Availability"
    PRIVACY = "Privacy"


@dataclass
class ImmunefiReport:
    """Immunefi-compliant bug bounty report."""

    # Required fields
    title: str
    summary: str
    severity: SeverityLevel
    impact: str
    affected_contracts: List[str]
    
    # Proof of Concept
    poc_description: str
    poc_code: Optional[str] = None
    poc_steps: List[str] = field(default_factory=list)
    
    # Additional information
    recommendations: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    
    # Metadata
    vulnerability_type: str = ""
    estimated_bounty: Optional[float] = None  # USD
    submission_date: datetime = field(default_factory=datetime.utcnow)
    
    # Impact details
    impact_type: ImpactType = ImpactType.FINANCIAL
    affected_users: Optional[int] = None
    potential_loss: Optional[float] = None  # USD
    
    def to_immunefi_format(self) -> Dict[str, Any]:
        """Convert report to Immunefi submission format.
        
        Returns:
            Dictionary in Immunefi-compliant format
        """
        return {
            "title": self.title,
            "summary": self.summary,
            "severity": self.severity.value,
            "impact": self.impact,
            "affected_contracts": self.affected_contracts,
            "proof_of_concept": {
                "description": self.poc_description,
                "code": self.poc_code or "",
                "steps": self.poc_steps,
            },
            "recommendations": self.recommendations,
            "references": self.references,
            "vulnerability_type": self.vulnerability_type,
            "estimated_bounty_usd": self.estimated_bounty,
            "impact_type": self.impact_type.value,
            "affected_users": self.affected_users,
            "potential_loss_usd": self.potential_loss,
        }
    
    def to_markdown(self) -> str:
        """Convert report to Markdown format for easy reading.
        
        Returns:
            Markdown-formatted report
        """
        md = f"""# {self.title}

## Summary
{self.summary}

## Severity
**{self.severity.value}**

## Impact
{self.impact}

## Affected Contracts
{chr(10).join(f"- {contract}" for contract in self.affected_contracts)}

## Proof of Concept

### Description
{self.poc_description}

"""
        
        if self.poc_steps:
            md += "### Steps to Reproduce\n"
            for i, step in enumerate(self.poc_steps, 1):
                md += f"{i}. {step}\n"
            md += "\n"
        
        if self.poc_code:
            md += f"### Code\n```solidity\n{self.poc_code}\n```\n\n"
        
        if self.recommendations:
            md += "## Recommendations\n"
            for rec in self.recommendations:
                md += f"- {rec}\n"
            md += "\n"
        
        if self.references:
            md += "## References\n"
            for ref in self.references:
                md += f"- {ref}\n"
            md += "\n"
        
        if self.estimated_bounty:
            md += f"## Estimated Bounty\n${self.estimated_bounty:,.2f} USD\n\n"
        
        md += f"## Submission Date\n{self.submission_date.isoformat()}\n"
        
        return md


class ImmunefiReportTemplate:
    """Template generator for Immunefi-compliant reports."""
    
    @staticmethod
    def estimate_bounty(severity: SeverityLevel, potential_loss: Optional[float] = None) -> float:
        """Estimate bounty amount based on severity and potential loss.
        
        Args:
            severity: Severity level
            potential_loss: Potential financial loss in USD
            
        Returns:
            Estimated bounty in USD
        """
        # Base bounty amounts (Immunefi typical ranges)
        base_bounties = {
            SeverityLevel.CRITICAL: 50_000,
            SeverityLevel.HIGH: 10_000,
            SeverityLevel.MEDIUM: 5_000,
            SeverityLevel.LOW: 1_000,
            SeverityLevel.INFORMATIONAL: 500,
        }
        
        base = base_bounties.get(severity, 1_000)
        
        # Adjust based on potential loss (if available)
        if potential_loss:
            # Bounty is typically 10-20% of potential loss, capped at base
            adjusted = min(potential_loss * 0.15, base * 2)
            return max(adjusted, base)
        
        return base
    
    @staticmethod
    def create_from_vulnerability(
        title: str,
        summary: str,
        severity: SeverityLevel,
        impact: str,
        affected_contracts: List[str],
        poc_description: str,
        poc_code: Optional[str] = None,
        poc_steps: Optional[List[str]] = None,
        recommendations: Optional[List[str]] = None,
        vulnerability_type: str = "",
        potential_loss: Optional[float] = None,
    ) -> ImmunefiReport:
        """Create an Immunefi report from vulnerability details.
        
        Args:
            title: Report title
            summary: Executive summary
            severity: Severity level
            impact: Impact description
            affected_contracts: List of affected contract addresses
            poc_description: PoC description
            poc_code: Optional PoC code
            poc_steps: Optional steps to reproduce
            recommendations: Optional recommendations
            vulnerability_type: Type of vulnerability
            potential_loss: Potential financial loss in USD
            
        Returns:
            Immunefi-compliant report
        """
        estimated_bounty = ImmunefiReportTemplate.estimate_bounty(severity, potential_loss)
        
        return ImmunefiReport(
            title=title,
            summary=summary,
            severity=severity,
            impact=impact,
            affected_contracts=affected_contracts,
            poc_description=poc_description,
            poc_code=poc_code,
            poc_steps=poc_steps or [],
            recommendations=recommendations or [],
            vulnerability_type=vulnerability_type,
            estimated_bounty=estimated_bounty,
            potential_loss=potential_loss,
        )

