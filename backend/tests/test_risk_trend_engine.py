"""
Unit tests for Risk Trend Engine
"""

import pytest
import time
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai.risk_trend_engine import RiskTrendEngine


class TestRiskTrendEngine:
    """Test suite for Risk Trend Engine."""

    @pytest.fixture
    def trend_engine(self):
        """Create trend engine instance."""
        return RiskTrendEngine(history_size=10, alert_threshold=0.15)

    def test_initialization(self, trend_engine):
        """Test trend engine initialization."""
        assert trend_engine.history_size == 10
        assert trend_engine.alert_threshold == 0.15
        assert len(trend_engine.history) == 0

    def test_update_single_token(self, trend_engine):
        """Test updating risk score for a single token."""
        mint = "test_mint_1"

        trend_engine.update(mint, 0.5)

        assert mint in trend_engine.history
        assert len(trend_engine.history[mint]) == 1
        assert trend_engine.history[mint][0][1] == 0.5

    def test_update_multiple_scores(self, trend_engine):
        """Test updating multiple scores for same token."""
        mint = "test_mint_1"

        for score in [0.3, 0.4, 0.5, 0.6]:
            trend_engine.update(mint, score)

        assert len(trend_engine.history[mint]) == 4

    def test_history_size_limit(self, trend_engine):
        """Test that history is limited to history_size."""
        mint = "test_mint_1"

        # Add more than history_size entries
        for i in range(15):
            trend_engine.update(mint, 0.5 + i * 0.01)

        # Should only keep last 10
        assert len(trend_engine.history[mint]) == 10

    def test_analyze_insufficient_data(self, trend_engine):
        """Test analysis with insufficient data."""
        mint = "test_mint_1"

        # No data
        analysis = trend_engine.analyze(mint)
        assert analysis["confidence"] == "none"
        assert analysis["data_points"] == 0

        # One data point
        trend_engine.update(mint, 0.5)
        analysis = trend_engine.analyze(mint)
        assert analysis["confidence"] == "insufficient"
        assert analysis["data_points"] == 1

    def test_analyze_increasing_trend(self, trend_engine):
        """Test detection of increasing risk trend."""
        mint = "test_mint_1"

        # Simulate increasing risk
        for i in range(5):
            trend_engine.update(mint, 0.3 + i * 0.1)
            time.sleep(0.01)  # Small delay to ensure different timestamps

        analysis = trend_engine.analyze(mint)

        assert analysis["direction"] == "increasing"
        assert analysis["trend"] > 0
        assert analysis["confidence"] == "high"

    def test_analyze_decreasing_trend(self, trend_engine):
        """Test detection of decreasing risk trend."""
        mint = "test_mint_1"

        # Simulate decreasing risk
        for i in range(5):
            trend_engine.update(mint, 0.7 - i * 0.1)
            time.sleep(0.01)

        analysis = trend_engine.analyze(mint)

        assert analysis["direction"] == "decreasing"
        assert analysis["trend"] < 0
        assert analysis["confidence"] == "high"

    def test_analyze_stable_trend(self, trend_engine):
        """Test detection of stable risk."""
        mint = "test_mint_1"

        # Simulate stable risk
        for i in range(5):
            trend_engine.update(mint, 0.5 + (i % 2) * 0.01)
            time.sleep(0.01)

        analysis = trend_engine.analyze(mint)

        assert analysis["direction"] == "stable"
        assert abs(analysis["trend"]) < 0.05

    def test_alert_rapid_increase(self, trend_engine):
        """Test alert generation for rapid risk increase."""
        mint = "test_mint_1"

        # Simulate rapid increase
        for i in range(5):
            trend_engine.update(mint, 0.2 + i * 0.15)
            time.sleep(0.01)

        analysis = trend_engine.analyze(mint)

        assert analysis["alert"] is not None
        assert "WARNING" in analysis["alert"] or "CRITICAL" in analysis["alert"]

    def test_alert_rapid_decrease(self, trend_engine):
        """Test alert generation for risk decrease."""
        mint = "test_mint_1"

        # Simulate rapid decrease
        for i in range(5):
            trend_engine.update(mint, 0.8 - i * 0.15)
            time.sleep(0.01)

        analysis = trend_engine.analyze(mint)

        assert analysis["alert"] is not None
        assert "POSITIVE" in analysis["alert"]

    def test_no_alert_for_low_confidence(self, trend_engine):
        """Test that alerts are not generated with low confidence."""
        mint = "test_mint_1"

        # Only 2 data points (low confidence)
        trend_engine.update(mint, 0.3)
        time.sleep(0.01)
        trend_engine.update(mint, 0.7)

        analysis = trend_engine.analyze(mint)

        # Should not generate alert despite large change
        assert analysis["alert"] is None

    def test_acceleration_detection(self, trend_engine):
        """Test detection of risk acceleration."""
        mint = "test_mint_1"

        # Simulate accelerating risk
        scores = [0.3, 0.35, 0.42, 0.52, 0.67]
        for score in scores:
            trend_engine.update(mint, score)
            time.sleep(0.01)

        analysis = trend_engine.analyze(mint)

        # Acceleration should be positive (increasing rate of change)
        assert analysis["acceleration"] > 0

    def test_summary_empty(self, trend_engine):
        """Test summary with no tracked tokens."""
        summary = trend_engine.get_summary()

        assert summary["tracked_tokens"] == 0
        assert summary["high_risk_tokens"] == 0
        assert summary["accelerating_tokens"] == 0
        assert summary["improving_tokens"] == 0

    def test_summary_with_data(self, trend_engine):
        """Test summary with tracked tokens."""
        # Add high-risk accelerating token
        mint1 = "high_risk_mint"
        for i in range(5):
            trend_engine.update(mint1, 0.6 + i * 0.05)
            time.sleep(0.01)

        # Add improving token
        mint2 = "improving_mint"
        for i in range(5):
            trend_engine.update(mint2, 0.8 - i * 0.05)
            time.sleep(0.01)

        summary = trend_engine.get_summary()

        assert summary["tracked_tokens"] == 2
        assert summary["high_risk_tokens"] >= 1
        assert summary["accelerating_tokens"] >= 0
        assert summary["improving_tokens"] >= 1

    def test_clear_stale_data(self, trend_engine):
        """Test clearing stale data."""
        # Add old data
        mint1 = "old_mint"
        trend_engine.update(mint1, 0.5)

        # Manually set timestamp to be old
        old_time = time.time() - 7200  # 2 hours ago
        trend_engine.history[mint1][0] = (old_time, 0.5)

        # Add recent data
        mint2 = "recent_mint"
        trend_engine.update(mint2, 0.6)

        # Clear stale data (max age 1 hour)
        cleared = trend_engine.clear_stale_data(max_age_seconds=3600)

        assert cleared == 1
        assert mint1 not in trend_engine.history
        assert mint2 in trend_engine.history

    def test_multiple_tokens(self, trend_engine):
        """Test tracking multiple tokens simultaneously."""
        mints = ["mint1", "mint2", "mint3"]

        # Add data for each mint
        for mint in mints:
            for i in range(3):
                trend_engine.update(mint, 0.5 + i * 0.1)

        # Verify all tracked
        assert len(trend_engine.history) == 3
        for mint in mints:
            assert mint in trend_engine.history
            assert len(trend_engine.history[mint]) == 3

    def test_trend_calculation_same_time(self, trend_engine):
        """Test trend calculation when all timestamps are the same."""
        mint = "test_mint"

        # Add multiple scores at same time (simulate)
        base_time = time.time()
        for i, score in enumerate([0.3, 0.4, 0.5]):
            trend_engine.history.setdefault(mint, []).append((base_time, score))

        analysis = trend_engine.analyze(mint)

        # Should handle gracefully (return 0 trend)
        assert analysis["trend"] == 0.0

    def test_confidence_levels(self, trend_engine):
        """Test confidence level classification."""
        mint = "test_mint"

        # 2 points = low confidence
        for i in range(2):
            trend_engine.update(mint, 0.5)
        analysis = trend_engine.analyze(mint)
        assert analysis["confidence"] == "low"

        # 4 points = medium confidence
        for i in range(2):
            trend_engine.update(mint, 0.5)
        analysis = trend_engine.analyze(mint)
        assert analysis["confidence"] == "medium"

        # 5+ points = high confidence
        for i in range(2):
            trend_engine.update(mint, 0.5)
        analysis = trend_engine.analyze(mint)
        assert analysis["confidence"] == "high"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
