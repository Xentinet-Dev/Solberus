"""
Unit tests for Risk Verification Registry
"""

import pytest
import tempfile
import json
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai.risk_verification_registry import (
    RiskVerificationRegistry,
    TokenOutcome,
    RiskRecord
)


class TestRiskVerificationRegistry:
    """Test suite for Risk Verification Registry."""

    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage file."""
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        temp_file.close()
        yield temp_file.name
        # Cleanup
        Path(temp_file.name).unlink(missing_ok=True)

    @pytest.fixture
    def registry(self, temp_storage):
        """Create registry instance with temporary storage."""
        return RiskVerificationRegistry(storage_path=temp_storage)

    def test_initialization(self, registry):
        """Test registry initialization."""
        assert len(registry.registry) == 0
        assert registry.storage_path.exists()

    def test_record_scan_new_token(self, registry):
        """Test recording scan for new token."""
        mint = "test_mint_1"
        score = 0.65

        registry.record_scan(mint, score)

        assert mint in registry.registry
        record = registry.registry[mint]
        assert record.max_score == score
        assert record.min_score == score
        assert record.avg_score == score
        assert record.scan_count == 1

    def test_record_scan_existing_token(self, registry):
        """Test recording multiple scans for same token."""
        mint = "test_mint_1"

        registry.record_scan(mint, 0.5)
        registry.record_scan(mint, 0.7)
        registry.record_scan(mint, 0.4)

        record = registry.registry[mint]
        assert record.max_score == 0.7
        assert record.min_score == 0.4
        assert record.scan_count == 3
        assert abs(record.avg_score - 0.533) < 0.01  # (0.5 + 0.7 + 0.4) / 3

    def test_verify_outcome_success(self, registry):
        """Test successful outcome verification."""
        mint = "test_mint_1"

        # First record a scan
        registry.record_scan(mint, 0.8)

        # Then verify outcome
        success = registry.verify_outcome(mint, TokenOutcome.RUGGED, notes="Liquidity removed")

        assert success
        record = registry.registry[mint]
        assert record.final_outcome == TokenOutcome.RUGGED
        assert record.notes == "Liquidity removed"
        assert record.outcome_verified_time is not None

    def test_verify_outcome_token_not_found(self, registry):
        """Test outcome verification for non-existent token."""
        mint = "nonexistent_mint"

        success = registry.verify_outcome(mint, TokenOutcome.SAFE)

        assert not success

    def test_get_accuracy_metrics_no_data(self, registry):
        """Test accuracy metrics with no verified data."""
        metrics = registry.get_accuracy_metrics()

        assert metrics["confusion_matrix"]["total"] == 0
        assert metrics["metrics"]["precision"] == 0.0
        assert metrics["metrics"]["recall"] == 0.0

    def test_get_accuracy_metrics_with_data(self, registry):
        """Test accuracy metrics with verified data."""
        # True positive: high score + rugged
        registry.record_scan("tp_mint", 0.80)
        registry.verify_outcome("tp_mint", TokenOutcome.RUGGED)

        # False positive: high score + safe
        registry.record_scan("fp_mint", 0.75)
        registry.verify_outcome("fp_mint", TokenOutcome.SAFE)

        # True negative: low score + safe
        registry.record_scan("tn_mint", 0.30)
        registry.verify_outcome("tn_mint", TokenOutcome.SAFE)

        # False negative: low score + rugged
        registry.record_scan("fn_mint", 0.40)
        registry.verify_outcome("fn_mint", TokenOutcome.HONEYPOT)

        metrics = registry.get_accuracy_metrics(threshold=0.65)

        cm = metrics["confusion_matrix"]
        assert cm["true_positives"] == 1
        assert cm["false_positives"] == 1
        assert cm["true_negatives"] == 1
        assert cm["false_negatives"] == 1
        assert cm["total"] == 4

        # Check calculated metrics
        assert metrics["metrics"]["precision"] == 0.5  # 1 / (1 + 1)
        assert metrics["metrics"]["recall"] == 0.5  # 1 / (1 + 1)
        assert metrics["metrics"]["accuracy"] == 0.5  # (1 + 1) / 4

    def test_hall_of_fame(self, registry):
        """Test hall of fame (correct threat identifications)."""
        # Add high-risk tokens that were verified as threats
        registry.record_scan("threat1", 0.95)
        registry.verify_outcome("threat1", TokenOutcome.RUGGED)

        registry.record_scan("threat2", 0.85)
        registry.verify_outcome("threat2", TokenOutcome.HONEYPOT)

        registry.record_scan("safe1", 0.20)
        registry.verify_outcome("safe1", TokenOutcome.SAFE)

        hall = registry.get_hall_of_fame(limit=10)

        # Should only include verified threats
        assert len(hall) == 2

        # Should be sorted by max score descending
        assert hall[0]["max_score"] == 0.95
        assert hall[1]["max_score"] == 0.85

    def test_hall_of_shame(self, registry):
        """Test hall of shame (missed threats)."""
        # Add low-score token that was verified as threat (false negative)
        registry.record_scan("missed1", 0.30)
        registry.verify_outcome("missed1", TokenOutcome.RUGGED)

        registry.record_scan("missed2", 0.45)
        registry.verify_outcome("missed2", TokenOutcome.ABANDONED)

        # Add high-score threat (should not appear in shame)
        registry.record_scan("caught1", 0.80)
        registry.verify_outcome("caught1", TokenOutcome.RUGGED)

        shame = registry.get_hall_of_shame(limit=10)

        # Should only include low-score threats
        assert len(shame) == 2

        # Should be sorted by max score ascending (worst misses first)
        assert shame[0]["max_score"] == 0.30
        assert shame[1]["max_score"] == 0.45

    def test_get_record(self, registry):
        """Test retrieving individual records."""
        mint = "test_mint"

        registry.record_scan(mint, 0.65)

        record = registry.get_record(mint)
        assert record is not None
        assert record.mint == mint
        assert record.max_score == 0.65

        # Non-existent mint
        assert registry.get_record("nonexistent") is None

    def test_get_summary(self, registry):
        """Test registry summary."""
        # Add some records
        registry.record_scan("mint1", 0.5)
        registry.verify_outcome("mint1", TokenOutcome.RUGGED)

        registry.record_scan("mint2", 0.6)
        registry.verify_outcome("mint2", TokenOutcome.SAFE)

        registry.record_scan("mint3", 0.7)
        # Leave mint3 unverified

        summary = registry.get_summary()

        assert summary["total_tokens"] == 3
        assert summary["verified_outcomes"] == 2
        assert summary["pending_verification"] == 1
        assert "rugged" in summary["outcome_breakdown"]
        assert "safe" in summary["outcome_breakdown"]

    def test_persistence_save_load(self, temp_storage):
        """Test data persistence across instances."""
        # Create first registry and add data
        registry1 = RiskVerificationRegistry(storage_path=temp_storage)
        registry1.record_scan("mint1", 0.65)
        registry1.verify_outcome("mint1", TokenOutcome.RUGGED)
        registry1._save()

        # Create second registry from same file
        registry2 = RiskVerificationRegistry(storage_path=temp_storage)

        # Should load existing data
        assert "mint1" in registry2.registry
        record = registry2.registry["mint1"]
        assert record.max_score == 0.65
        assert record.final_outcome == TokenOutcome.RUGGED

    def test_confidence_filter(self, registry):
        """Test confidence filtering in accuracy metrics."""
        # Add high-confidence prediction (many scans)
        for i in range(10):
            registry.record_scan("high_conf", 0.8)
        registry.verify_outcome("high_conf", TokenOutcome.RUGGED)

        # Add low-confidence prediction (few scans)
        registry.record_scan("low_conf", 0.7)
        registry.verify_outcome("low_conf", TokenOutcome.SAFE)

        # Test with high confidence filter
        metrics_high = registry.get_accuracy_metrics(min_confidence="high")
        assert metrics_high["counts"]["verified"] == 1  # Only high_conf

        # Test with low confidence filter
        metrics_low = registry.get_accuracy_metrics(min_confidence="low")
        assert metrics_low["counts"]["verified"] == 2  # Both included

    def test_risk_record_serialization(self):
        """Test RiskRecord to_dict and from_dict."""
        record = RiskRecord(
            mint="test_mint",
            first_scan_time=1000.0,
            last_scan_time=2000.0,
            max_score=0.8,
            min_score=0.4,
            avg_score=0.6,
            scan_count=5,
            final_outcome=TokenOutcome.RUGGED,
            outcome_verified_time=2500.0,
            notes="Test note"
        )

        # Convert to dict
        data = record.to_dict()
        assert data["mint"] == "test_mint"
        assert data["max_score"] == 0.8
        assert data["final_outcome"] == "rugged"

        # Convert back to RiskRecord
        restored = RiskRecord.from_dict(data)
        assert restored.mint == record.mint
        assert restored.max_score == record.max_score
        assert restored.final_outcome == record.final_outcome

    def test_multiple_outcome_types(self, registry):
        """Test tracking different outcome types."""
        registry.record_scan("rugged", 0.9)
        registry.verify_outcome("rugged", TokenOutcome.RUGGED)

        registry.record_scan("honeypot", 0.85)
        registry.verify_outcome("honeypot", TokenOutcome.HONEYPOT)

        registry.record_scan("abandoned", 0.6)
        registry.verify_outcome("abandoned", TokenOutcome.ABANDONED)

        registry.record_scan("safe", 0.2)
        registry.verify_outcome("safe", TokenOutcome.SAFE)

        summary = registry.get_summary()

        assert summary["outcome_breakdown"]["rugged"] == 1
        assert summary["outcome_breakdown"]["honeypot"] == 1
        assert summary["outcome_breakdown"]["abandoned"] == 1
        assert summary["outcome_breakdown"]["safe"] == 1

    def test_threshold_sensitivity(self, registry):
        """Test accuracy metrics with different thresholds."""
        # Add token with score 0.60
        registry.record_scan("border", 0.60)
        registry.verify_outcome("border", TokenOutcome.RUGGED)

        # With threshold 0.50, should be TP
        metrics_low = registry.get_accuracy_metrics(threshold=0.50)
        assert metrics_low["confusion_matrix"]["true_positives"] == 1

        # With threshold 0.70, should be FN
        metrics_high = registry.get_accuracy_metrics(threshold=0.70)
        assert metrics_high["confusion_matrix"]["false_negatives"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
