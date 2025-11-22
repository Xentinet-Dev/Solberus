"""
Submission status tracking for bug bounty reports.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


class SubmissionStatus(Enum):
    """Status of a bug bounty submission."""

    DRAFT = "draft"  # Report created but not submitted
    SUBMITTED = "submitted"  # Submitted to platform
    UNDER_REVIEW = "under_review"  # Platform is reviewing
    TRIAGED = "triaged"  # Platform has triaged the report
    ACCEPTED = "accepted"  # Report accepted, awaiting payment
    REJECTED = "rejected"  # Report rejected
    DUPLICATE = "duplicate"  # Duplicate of existing report
    PAID = "paid"  # Bounty paid
    DISPUTED = "disputed"  # Payment disputed


class PaymentStatus(Enum):
    """Status of bounty payment."""

    PENDING = "pending"  # Awaiting payment
    PROCESSING = "processing"  # Payment being processed
    COMPLETED = "completed"  # Payment completed
    FAILED = "failed"  # Payment failed
    DISPUTED = "disputed"  # Payment disputed


@dataclass
class SubmissionInfo:
    """Information about a bug bounty submission."""

    submission_id: str
    report_title: str
    platform: str  # "immunefi", "code4rena", etc.
    status: SubmissionStatus
    submitted_at: Optional[datetime] = None
    estimated_bounty: Optional[float] = None  # USD
    actual_bounty: Optional[float] = None  # USD
    payment_status: PaymentStatus = PaymentStatus.PENDING
    payment_date: Optional[datetime] = None
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "submission_id": self.submission_id,
            "report_title": self.report_title,
            "platform": self.platform,
            "status": self.status.value,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "estimated_bounty": self.estimated_bounty,
            "actual_bounty": self.actual_bounty,
            "payment_status": self.payment_status.value,
            "payment_date": self.payment_date.isoformat() if self.payment_date else None,
            "notes": self.notes,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubmissionInfo":
        """Create from dictionary."""
        return cls(
            submission_id=data["submission_id"],
            report_title=data["report_title"],
            platform=data["platform"],
            status=SubmissionStatus(data["status"]),
            submitted_at=datetime.fromisoformat(data["submitted_at"])
            if data.get("submitted_at")
            else None,
            estimated_bounty=data.get("estimated_bounty"),
            actual_bounty=data.get("actual_bounty"),
            payment_status=PaymentStatus(data.get("payment_status", "pending")),
            payment_date=datetime.fromisoformat(data["payment_date"])
            if data.get("payment_date")
            else None,
            notes=data.get("notes", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class PaymentInfo:
    """Information about a bounty payment."""

    payment_id: str
    submission_id: str
    amount: float  # USD
    currency: str = "USD"
    status: PaymentStatus = PaymentStatus.PENDING
    payment_date: Optional[datetime] = None
    transaction_hash: Optional[str] = None  # On-chain transaction
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "payment_id": self.payment_id,
            "submission_id": self.submission_id,
            "amount": self.amount,
            "currency": self.currency,
            "status": self.status.value,
            "payment_date": self.payment_date.isoformat() if self.payment_date else None,
            "transaction_hash": self.transaction_hash,
            "notes": self.notes,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PaymentInfo":
        """Create from dictionary."""
        return cls(
            payment_id=data["payment_id"],
            submission_id=data["submission_id"],
            amount=data["amount"],
            currency=data.get("currency", "USD"),
            status=PaymentStatus(data.get("status", "pending")),
            payment_date=datetime.fromisoformat(data["payment_date"])
            if data.get("payment_date")
            else None,
            transaction_hash=data.get("transaction_hash"),
            notes=data.get("notes", ""),
            metadata=data.get("metadata", {}),
        )

