"""
Risk Verification Registry

Tracks long-term accuracy of MHTI predictions.
Records predictions, verifies outcomes, and calculates performance metrics.

This proves MHTI value over time with quantifiable accuracy metrics.
"""

import time
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class TokenOutcome(Enum):
    """Possible outcomes for a token."""
    RUGGED = "rugged"           # Token was a rug pull
    HONEYPOT = "honeypot"       # Token was a honeypot
    ABANDONED = "abandoned"     # Project abandoned
    SAFE = "safe"               # Token is legitimate
    UNKNOWN = "unknown"         # Outcome not yet determined


@dataclass
class RiskRecord:
    """Record of MHTI risk prediction for a token."""
    mint: str
    first_scan_time: float
    last_scan_time: float
    max_score: float
    min_score: float
    avg_score: float
    scan_count: int
    final_outcome: Optional[TokenOutcome] = None
    outcome_verified_time: Optional[float] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        if self.final_outcome:
            data["final_outcome"] = self.final_outcome.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RiskRecord":
        """Create from dictionary."""
        if data.get("final_outcome"):
            data["final_outcome"] = TokenOutcome(data["final_outcome"])
        return cls(**data)


class RiskVerificationRegistry:
    """
    Tracks long-term accuracy of MHTI predictions.

    Features:
    - Records all MHTI scans with max/min/avg scores
    - Allows manual verification of token outcomes
    - Calculates precision, recall, F1 score
    - Generates accuracy reports
    - Persists data to disk for long-term tracking
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize Risk Verification Registry.

        Args:
            storage_path: Path to store registry data (default: backend/data/risk_registry.json)
        """
        if storage_path is None:
            storage_path = Path(__file__).parent.parent / "data" / "risk_registry.json"

        self.storage_path = Path(storage_path)
        self.registry: Dict[str, RiskRecord] = {}

        # Ensure storage directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing data
        self._load()

        logger.info(f"[RiskVerificationRegistry] Initialized with {len(self.registry)} records")

    def record_scan(self, mint: str, score: float) -> None:
        """
        Record an MHTI scan result.

        Args:
            mint: Token mint address
            score: MHTI risk score (0-1)
        """
        current_time = time.time()

        if mint in self.registry:
            # Update existing record
            record = self.registry[mint]
            record.last_scan_time = current_time
            record.max_score = max(record.max_score, score)
            record.min_score = min(record.min_score, score)

            # Update running average
            total = record.avg_score * record.scan_count + score
            record.scan_count += 1
            record.avg_score = total / record.scan_count
        else:
            # Create new record
            record = RiskRecord(
                mint=mint,
                first_scan_time=current_time,
                last_scan_time=current_time,
                max_score=score,
                min_score=score,
                avg_score=score,
                scan_count=1
            )
            self.registry[mint] = record

        logger.debug(f"[RiskVerificationRegistry] Recorded scan for {mint}: score={score:.3f}")

    def verify_outcome(
        self,
        mint: str,
        outcome: TokenOutcome,
        notes: Optional[str] = None
    ) -> bool:
        """
        Verify the final outcome of a token.

        Args:
            mint: Token mint address
            outcome: Verified outcome
            notes: Optional notes about the outcome

        Returns:
            True if verification successful, False if token not found
        """
        if mint not in self.registry:
            logger.warning(f"[RiskVerificationRegistry] Cannot verify {mint}: not found in registry")
            return False

        record = self.registry[mint]
        record.final_outcome = outcome
        record.outcome_verified_time = time.time()

        if notes:
            record.notes = notes

        logger.info(
            f"[RiskVerificationRegistry] Verified {mint}: "
            f"outcome={outcome.value}, max_score={record.max_score:.3f}"
        )

        # Persist after verification
        self._save()

        return True

    def get_accuracy_metrics(
        self,
        threshold: float = 0.65,
        min_confidence: str = "medium"
    ) -> Dict[str, Any]:
        """
        Calculate accuracy metrics for MHTI predictions.

        Uses confusion matrix approach:
        - True Positive: High score + negative outcome (correctly identified threat)
        - False Positive: High score + safe outcome (false alarm)
        - True Negative: Low score + safe outcome (correctly identified safe token)
        - False Negative: Low score + negative outcome (missed threat)

        Args:
            threshold: Risk score threshold for "high risk" classification (default: 0.65)
            min_confidence: Minimum confidence level ("low", "medium", "high")

        Returns:
            Dictionary containing:
            - confusion_matrix: TP, FP, TN, FN counts
            - precision: TP / (TP + FP)
            - recall: TP / (TP + FN)
            - f1_score: Harmonic mean of precision and recall
            - accuracy: (TP + TN) / total
            - false_positive_rate: FP / (FP + TN)
            - verified_count: Number of verified outcomes
            - pending_count: Number of unverified predictions
        """
        tp = fp = tn = fn = 0
        verified_count = 0
        pending_count = 0

        for mint, record in self.registry.items():
            # Apply confidence filter
            if min_confidence == "high" and record.scan_count < 5:
                continue
            elif min_confidence == "medium" and record.scan_count < 3:
                continue

            # Check if outcome is verified
            if record.final_outcome is None or record.final_outcome == TokenOutcome.UNKNOWN:
                pending_count += 1
                continue

            verified_count += 1

            # Determine if outcome was negative (threat)
            is_threat = record.final_outcome in [
                TokenOutcome.RUGGED,
                TokenOutcome.HONEYPOT,
                TokenOutcome.ABANDONED
            ]

            # Determine if MHTI predicted high risk
            predicted_high_risk = record.max_score >= threshold

            # Update confusion matrix
            if predicted_high_risk and is_threat:
                tp += 1  # Correctly identified threat
            elif predicted_high_risk and not is_threat:
                fp += 1  # False alarm
            elif not predicted_high_risk and not is_threat:
                tn += 1  # Correctly identified safe
            else:
                fn += 1  # Missed threat

        # Calculate metrics
        total = tp + fp + tn + fn

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1_score = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0 else 0.0
        )
        accuracy = (tp + tn) / total if total > 0 else 0.0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

        return {
            "threshold": threshold,
            "min_confidence": min_confidence,
            "confusion_matrix": {
                "true_positives": tp,
                "false_positives": fp,
                "true_negatives": tn,
                "false_negatives": fn,
                "total": total
            },
            "metrics": {
                "precision": round(precision, 3),
                "recall": round(recall, 3),
                "f1_score": round(f1_score, 3),
                "accuracy": round(accuracy, 3),
                "false_positive_rate": round(fpr, 3)
            },
            "counts": {
                "verified": verified_count,
                "pending": pending_count,
                "total_scans": len(self.registry)
            }
        }

    def get_hall_of_fame(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get tokens with highest risk scores that were verified as threats.
        (True positives - MHTI correctly identified the threat)

        Args:
            limit: Maximum number of results

        Returns:
            List of true positive cases
        """
        true_positives = []

        for mint, record in self.registry.items():
            if record.final_outcome in [
                TokenOutcome.RUGGED,
                TokenOutcome.HONEYPOT,
                TokenOutcome.ABANDONED
            ]:
                true_positives.append({
                    "mint": mint,
                    "max_score": record.max_score,
                    "outcome": record.final_outcome.value,
                    "scan_count": record.scan_count,
                    "notes": record.notes
                })

        # Sort by max score descending
        true_positives.sort(key=lambda x: x["max_score"], reverse=True)

        return true_positives[:limit]

    def get_hall_of_shame(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get tokens with low risk scores that were verified as threats.
        (False negatives - MHTI missed the threat)

        Args:
            limit: Maximum number of results

        Returns:
            List of false negative cases
        """
        false_negatives = []

        for mint, record in self.registry.items():
            if record.final_outcome in [
                TokenOutcome.RUGGED,
                TokenOutcome.HONEYPOT,
                TokenOutcome.ABANDONED
            ]:
                # Only include if score was low (< 0.5)
                if record.max_score < 0.5:
                    false_negatives.append({
                        "mint": mint,
                        "max_score": record.max_score,
                        "outcome": record.final_outcome.value,
                        "scan_count": record.scan_count,
                        "notes": record.notes
                    })

        # Sort by max score ascending (lowest scores = worst misses)
        false_negatives.sort(key=lambda x: x["max_score"])

        return false_negatives[:limit]

    def get_record(self, mint: str) -> Optional[RiskRecord]:
        """
        Get risk record for a specific token.

        Args:
            mint: Token mint address

        Returns:
            RiskRecord if found, None otherwise
        """
        return self.registry.get(mint)

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics for the registry.

        Returns:
            Summary statistics
        """
        if not self.registry:
            return {
                "total_tokens": 0,
                "verified_outcomes": 0,
                "pending_verification": 0,
                "outcome_breakdown": {}
            }

        verified = sum(
            1 for r in self.registry.values()
            if r.final_outcome and r.final_outcome != TokenOutcome.UNKNOWN
        )
        pending = len(self.registry) - verified

        # Outcome breakdown
        outcome_counts = {}
        for record in self.registry.values():
            if record.final_outcome:
                outcome = record.final_outcome.value
                outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1

        return {
            "total_tokens": len(self.registry),
            "verified_outcomes": verified,
            "pending_verification": pending,
            "outcome_breakdown": outcome_counts
        }

    def _save(self) -> None:
        """Persist registry to disk."""
        try:
            data = {
                "version": "1.0",
                "timestamp": time.time(),
                "records": {
                    mint: record.to_dict()
                    for mint, record in self.registry.items()
                }
            }

            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)

            logger.debug(f"[RiskVerificationRegistry] Saved {len(self.registry)} records")

        except Exception as e:
            logger.error(f"[RiskVerificationRegistry] Save failed: {e}")

    def _load(self) -> None:
        """Load registry from disk."""
        try:
            if not self.storage_path.exists():
                logger.info("[RiskVerificationRegistry] No existing registry found, starting fresh")
                return

            with open(self.storage_path, 'r') as f:
                data = json.load(f)

            records = data.get("records", {})
            self.registry = {
                mint: RiskRecord.from_dict(record_data)
                for mint, record_data in records.items()
            }

            logger.info(f"[RiskVerificationRegistry] Loaded {len(self.registry)} records")

        except Exception as e:
            logger.error(f"[RiskVerificationRegistry] Load failed: {e}")
            self.registry = {}
