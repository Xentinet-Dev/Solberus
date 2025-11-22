"""
Bug bounty submission tracker.

Tracks submissions to bug bounty platforms (Immunefi, Code4rena, etc.)
and monitors their status.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

from bug_bounty.report_templates import ImmunefiReport
from bug_bounty.submission_status import (
    PaymentStatus,
    SubmissionInfo,
    SubmissionStatus,
)
from utils.logger import get_logger

logger = get_logger(__name__)


class BountyTracker:
    """Track bug bounty submissions and their status."""

    def __init__(self, storage_path: str = "bug_reports/submissions.json"):
        """Initialize bounty tracker.
        
        Args:
            storage_path: Path to store submission tracking data
        """
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.submissions: Dict[str, SubmissionInfo] = {}
        self._load_submissions()

    def _load_submissions(self) -> None:
        """Load submissions from storage."""
        if self.storage_path.exists():
            try:
                with self.storage_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.submissions = {
                        sub_id: SubmissionInfo.from_dict(sub_data)
                        for sub_id, sub_data in data.items()
                    }
                logger.info(f"Loaded {len(self.submissions)} tracked submissions")
            except Exception as e:
                logger.exception(f"Error loading submissions: {e}")
                self.submissions = {}

    def _save_submissions(self) -> None:
        """Save submissions to storage."""
        try:
            data = {
                sub_id: sub.to_dict()
                for sub_id, sub in self.submissions.items()
            }
            with self.storage_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.exception(f"Error saving submissions: {e}")

    def create_submission(
        self,
        report: ImmunefiReport,
        platform: str = "immunefi",
    ) -> SubmissionInfo:
        """Create a new submission record.
        
        Args:
            report: Bug bounty report
            platform: Platform name (immunefi, code4rena, etc.)
            
        Returns:
            Submission info
        """
        from datetime import datetime
        import uuid

        submission_id = str(uuid.uuid4())
        
        submission = SubmissionInfo(
            submission_id=submission_id,
            report_title=report.title,
            platform=platform,
            status=SubmissionStatus.DRAFT,
            estimated_bounty=report.estimated_bounty,
            notes=f"Report created: {report.vulnerability_type}",
        )
        
        self.submissions[submission_id] = submission
        self._save_submissions()
        
        logger.info(
            f"Created submission: {submission_id} "
            f"({report.title}, Estimated: ${report.estimated_bounty:,.2f} USD)"
        )
        
        return submission

    async def submit_to_platform(
        self,
        submission_id: str,
        platform: str = "immunefi",
    ) -> bool:
        """Submit report to bug bounty platform.
        
        Args:
            submission_id: Submission ID
            platform: Platform name
            
        Returns:
            True if submission successful, False otherwise
        """
        if submission_id not in self.submissions:
            logger.error(f"Submission not found: {submission_id}")
            return False
        
        submission = self.submissions[submission_id]
        
        # In production, this would:
        # 1. Use Immunefi API to submit report
        # 2. Get submission confirmation
        # 3. Update status
        
        # For now, simulate submission
        logger.info(
            f"Submitting {submission_id} to {platform}... "
            f"(Simulated - would use {platform} API in production)"
        )
        
        from datetime import datetime
        
        submission.status = SubmissionStatus.SUBMITTED
        submission.submitted_at = datetime.utcnow()
        submission.platform = platform
        submission.notes = f"Submitted to {platform} at {submission.submitted_at.isoformat()}"
        
        self._save_submissions()
        
        logger.info(f"Submission {submission_id} marked as submitted to {platform}")
        
        return True

    def update_submission_status(
        self,
        submission_id: str,
        status: SubmissionStatus,
        notes: Optional[str] = None,
    ) -> bool:
        """Update submission status.
        
        Args:
            submission_id: Submission ID
            status: New status
            notes: Optional notes
            
        Returns:
            True if updated, False otherwise
        """
        if submission_id not in self.submissions:
            logger.error(f"Submission not found: {submission_id}")
            return False
        
        submission = self.submissions[submission_id]
        old_status = submission.status
        submission.status = status
        
        if notes:
            submission.notes = notes
        
        self._save_submissions()
        
        logger.info(
            f"Updated submission {submission_id}: "
            f"{old_status.value} → {status.value}"
        )
        
        return True

    def record_payment(
        self,
        submission_id: str,
        amount: float,
        transaction_hash: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> bool:
        """Record bounty payment.
        
        Args:
            submission_id: Submission ID
            amount: Payment amount (USD)
            transaction_hash: Optional on-chain transaction hash
            notes: Optional notes
            
        Returns:
            True if recorded, False otherwise
        """
        if submission_id not in self.submissions:
            logger.error(f"Submission not found: {submission_id}")
            return False
        
        submission = self.submissions[submission_id]
        
        from datetime import datetime
        import uuid
        
        payment_id = str(uuid.uuid4())
        
        submission.actual_bounty = amount
        submission.payment_status = PaymentStatus.COMPLETED
        submission.payment_date = datetime.utcnow()
        submission.status = SubmissionStatus.PAID
        
        if notes:
            submission.notes = notes
        
        self._save_submissions()
        
        logger.info(
            f"Recorded payment for submission {submission_id}: "
            f"${amount:,.2f} USD"
        )
        
        return True

    def get_submission(self, submission_id: str) -> Optional[SubmissionInfo]:
        """Get submission by ID.
        
        Args:
            submission_id: Submission ID
            
        Returns:
            Submission info or None
        """
        return self.submissions.get(submission_id)

    def get_all_submissions(
        self,
        status: Optional[SubmissionStatus] = None,
        platform: Optional[str] = None,
    ) -> List[SubmissionInfo]:
        """Get all submissions, optionally filtered.
        
        Args:
            status: Optional status filter
            platform: Optional platform filter
            
        Returns:
            List of submissions
        """
        submissions = list(self.submissions.values())
        
        if status:
            submissions = [s for s in submissions if s.status == status]
        
        if platform:
            submissions = [s for s in submissions if s.platform == platform]
        
        return submissions

    def get_statistics(self) -> Dict[str, any]:
        """Get tracking statistics.
        
        Returns:
            Statistics dictionary
        """
        total_submissions = len(self.submissions)
        total_estimated = sum(
            s.estimated_bounty or 0 for s in self.submissions.values()
        )
        total_paid = sum(
            s.actual_bounty or 0
            for s in self.submissions.values()
            if s.payment_status == PaymentStatus.COMPLETED
        )
        
        status_counts = {}
        for status in SubmissionStatus:
            status_counts[status.value] = sum(
                1 for s in self.submissions.values() if s.status == status
            )
        
        return {
            "total_submissions": total_submissions,
            "total_estimated_bounty_usd": total_estimated,
            "total_paid_usd": total_paid,
            "status_counts": status_counts,
        }

