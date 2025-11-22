"""
Payment monitoring for bug bounty payments.

Monitors payment status and tracks when bounties are paid.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from bug_bounty.submission_status import PaymentStatus, SubmissionInfo
from utils.logger import get_logger

logger = get_logger(__name__)


class PaymentMonitor:
    """Monitor bug bounty payments."""

    def __init__(
        self,
        bounty_tracker,
        check_interval: int = 3600,  # 1 hour
        bounty_converter=None,  # Optional BountyToLiquidityConverter
    ):
        """Initialize payment monitor.
        
        Args:
            bounty_tracker: BountyTracker instance
            check_interval: Interval between payment checks (seconds)
            bounty_converter: Optional converter for auto-converting payments to liquidity
        """
        self.bounty_tracker = bounty_tracker
        self.check_interval = check_interval
        self.bounty_converter = bounty_converter
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self.payments_detected = 0

    async def start(self) -> None:
        """Start payment monitoring."""
        if self._running:
            return
        
        self._running = True
        logger.info("Starting payment monitor...")
        self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def stop(self) -> None:
        """Stop payment monitoring."""
        if not self._running:
            return
        
        self._running = False
        logger.info("Stopping payment monitor...")
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await self.check_payments()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in payment monitor loop")
                await asyncio.sleep(self.check_interval)

    async def check_payments(self) -> None:
        """Check for new payments.
        
        In production, this would:
        1. Query Immunefi API for payment status
        2. Check on-chain transactions
        3. Monitor wallet for incoming payments
        """
        # Get all submissions awaiting payment
        pending_submissions = self.bounty_tracker.get_all_submissions(
            status=None  # Check all statuses
        )
        
        pending = [
            s
            for s in pending_submissions
            if s.payment_status == PaymentStatus.PENDING
            and s.status in [
                SubmissionStatus.ACCEPTED,
                SubmissionStatus.TRIAGED,
            ]
        ]
        
        if not pending:
            logger.debug("No pending payments to check")
            return
        
        logger.info(f"Checking payment status for {len(pending)} submissions...")
        
        for submission in pending:
            await self._check_submission_payment(submission)

    async def _check_submission_payment(self, submission: SubmissionInfo) -> None:
        """Check payment status for a specific submission.
        
        Args:
            submission: Submission to check
        """
        # In production, this would:
        # 1. Query platform API for payment status
        # 2. Check on-chain transactions
        # 3. Monitor wallet for incoming payments
        
        # For now, simulate checking
        logger.debug(
            f"Checking payment for submission {submission.submission_id} "
            f"({submission.report_title})"
        )
        
        # Simulate: Check if payment should be detected
        # In production, would query actual payment status
        
        # Example: If submission was accepted more than 7 days ago, mark as paid
        # (This is just a simulation - real implementation would check actual payments)
        if submission.submitted_at:
            days_since_submission = (
                datetime.utcnow() - submission.submitted_at
            ).days
            
            # Simulate payment after 7 days (for testing)
            if days_since_submission >= 7 and submission.status == SubmissionStatus.ACCEPTED:
                logger.info(
                    f"Simulating payment for submission {submission.submission_id} "
                    f"(would check actual payment in production)"
                )
                # In production, would check actual payment and amount
                # For now, use estimated bounty as actual
                self.bounty_tracker.record_payment(
                    submission.submission_id,
                    amount=submission.estimated_bounty or 0,
                    notes="Payment detected (simulated)",
                )
                self.payments_detected += 1
                
                # Trigger automatic conversion to liquidity
                if hasattr(self, 'bounty_converter') and self.bounty_converter:
                    try:
                        updated_submission = self.bounty_tracker.get_submission(
                            submission.submission_id
                        )
                        if updated_submission:
                            await self.bounty_converter.convert_bounty_to_liquidity(
                                updated_submission,
                                use_aeon=True,
                            )
                            logger.info(
                                f"Automatically converted bounty to liquidity "
                                f"for submission {submission.submission_id}"
                            )
                    except Exception as e:
                        logger.exception(
                            f"Error auto-converting bounty to liquidity: {e}"
                        )

    async def check_payment_status(
        self, submission_id: str
    ) -> Optional[PaymentStatus]:
        """Check payment status for a specific submission.
        
        Args:
            submission_id: Submission ID
            
        Returns:
            Payment status or None
        """
        submission = self.bounty_tracker.get_submission(submission_id)
        if not submission:
            return None
        
        # In production, would query platform API
        # For now, return current status
        return submission.payment_status

    async def get_pending_payments(self) -> List[SubmissionInfo]:
        """Get all submissions with pending payments.
        
        Returns:
            List of submissions awaiting payment
        """
        all_submissions = self.bounty_tracker.get_all_submissions()
        
        return [
            s
            for s in all_submissions
            if s.payment_status == PaymentStatus.PENDING
            and s.status in [
                SubmissionStatus.ACCEPTED,
                SubmissionStatus.TRIAGED,
            ]
        ]

    def get_statistics(self) -> Dict[str, any]:
        """Get payment monitoring statistics.
        
        Returns:
            Statistics dictionary
        """
        pending = self.bounty_tracker.get_all_submissions()
        pending_payments = [
            s
            for s in pending
            if s.payment_status == PaymentStatus.PENDING
        ]
        completed_payments = [
            s
            for s in pending
            if s.payment_status == PaymentStatus.COMPLETED
        ]
        
        total_pending = sum(
            s.estimated_bounty or 0 for s in pending_payments
        )
        total_completed = sum(
            s.actual_bounty or 0 for s in completed_payments
        )
        
        return {
            "payments_detected": self.payments_detected,
            "pending_payments_count": len(pending_payments),
            "pending_amount_usd": total_pending,
            "completed_payments_count": len(completed_payments),
            "completed_amount_usd": total_completed,
        }

