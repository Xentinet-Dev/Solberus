"""
Unit tests for Multi-Headed Threat Index (MHTI)
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any, Optional, Tuple

# Add src to path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai.multi_headed_threat_index import MultiHeadedThreatIndex
from interfaces.core import TokenInfo, Platform
from solders.pubkey import Pubkey


class MockThreatDetector:
    """Mock threat detector for testing."""

    def __init__(self, threats: Dict[str, Optional[Tuple[str, float, Dict]]]):
        self.threats = threats

    async def detect_all_threats(self, token_info: TokenInfo) -> Dict[str, Optional[Tuple]]:
        """Return mocked threats."""
        return self.threats


@pytest.fixture
def sample_token_info():
    """Create sample TokenInfo for testing."""
    return TokenInfo(
        name="TestToken",
        symbol="TEST",
        uri="https://test.com",
        mint=Pubkey.from_string("11111111111111111111111111111111"),
        platform=Platform.PUMP_FUN,
        market_cap_sol=10.0,
        virtual_sol_reserves=50.0,
        additional_data={
            "volume_24h": 100.0,
            "holder_count": 150
        }
    )


@pytest.fixture
def mhti_instance():
    """Create MHTI instance for testing."""
    return MultiHeadedThreatIndex(risk_tolerance="medium")


class TestMultiHeadedThreatIndex:
    """Test suite for MHTI."""

    def test_initialization(self):
        """Test MHTI initialization with different risk tolerances."""
        # Test medium tolerance
        mhti = MultiHeadedThreatIndex(risk_tolerance="medium")
        assert mhti.weights["risk"] == 0.40
        assert mhti.weights["technical"] == 0.30
        assert mhti.weights["market"] == 0.30
        assert mhti.thresholds["safe"] == 0.30

        # Test conservative tolerance
        mhti_conservative = MultiHeadedThreatIndex(risk_tolerance="conservative")
        assert mhti_conservative.thresholds["safe"] == 0.15

        # Test aggressive tolerance
        mhti_aggressive = MultiHeadedThreatIndex(risk_tolerance="aggressive")
        assert mhti_aggressive.thresholds["safe"] == 0.45

    @pytest.mark.asyncio
    async def test_classify_basic(self, mhti_instance, sample_token_info):
        """Test basic MHTI classification."""
        # Mock threat detector to return no threats
        with patch('ai.multi_headed_threat_index.ComprehensiveThreatDetector') as mock_detector:
            mock_instance = MockThreatDetector({})
            mock_detector.return_value = mock_instance

            result = await mhti_instance.classify(sample_token_info)

            # Verify result structure
            assert "engine" in result
            assert result["engine"] == "Multi-Headed Threat Index (MHTI)"
            assert "score" in result
            assert "risk_level" in result
            assert "buckets" in result
            assert "top_factors" in result
            assert "confidence_interval" in result

            # Verify score range
            assert 0.0 <= result["score"] <= 1.0

            # Verify risk level
            assert result["risk_level"] in ["safe", "monitor", "high", "critical"]

    @pytest.mark.asyncio
    async def test_aggregate_threats_high_risk(self, mhti_instance, sample_token_info):
        """Test threat aggregation with high-risk threats."""
        # Mock high-risk threats
        mock_threats = {
            "honeypot": ("critical", 0.9, {"reason": "Cannot sell"}),
            "rug_pull": ("critical", 0.85, {"reason": "Liquidity drain detected"}),
            "wash_trading": ("medium", 0.6, {"reason": "Suspicious volume"})
        }

        with patch('ai.multi_headed_threat_index.ComprehensiveThreatDetector') as mock_detector:
            mock_instance = MockThreatDetector(mock_threats)
            mock_detector.return_value = mock_instance

            result = await mhti_instance.classify(sample_token_info)

            # Should have high risk score
            assert result["score"] > 0.5

            # Risk bucket should be elevated
            assert result["buckets"]["risk"] > 0.5

    @pytest.mark.asyncio
    async def test_aggregate_threats_low_risk(self, mhti_instance, sample_token_info):
        """Test threat aggregation with low-risk threats."""
        # Mock low-risk threats
        mock_threats = {
            "minor_issue": ("low", 0.3, {"reason": "Minor concern"}),
            "no_threat": None
        }

        with patch('ai.multi_headed_threat_index.ComprehensiveThreatDetector') as mock_detector:
            mock_instance = MockThreatDetector(mock_threats)
            mock_detector.return_value = mock_instance

            result = await mhti_instance.classify(sample_token_info)

            # Should have low risk score
            assert result["score"] < 0.5

    def test_technical_risk_calculation(self, mhti_instance, sample_token_info):
        """Test technical risk calculation."""
        # Test with no extension data
        risk1 = asyncio.run(mhti_instance._compute_technical_risk(sample_token_info))
        assert risk1 == 0.0

        # Test with risky extensions
        sample_token_info.additional_data = {
            "has_transfer_hook": True,
            "has_freeze_authority": True,
            "has_mint_authority": True
        }
        risk2 = asyncio.run(mhti_instance._compute_technical_risk(sample_token_info))
        assert risk2 == 0.75  # 3 * 0.25

    def test_market_risk_calculation(self, mhti_instance, sample_token_info):
        """Test market risk calculation."""
        # Test with healthy market metrics
        risk = mhti_instance._compute_market_risk(sample_token_info)

        # Should be inverse of health (high liquidity = low risk)
        assert 0.0 <= risk <= 1.0

        # Test with poor liquidity
        sample_token_info.market_cap_sol = 1.0
        sample_token_info.virtual_sol_reserves = 1.0
        sample_token_info.additional_data = {"volume_24h": 10.0, "holder_count": 5}

        risk_poor = mhti_instance._compute_market_risk(sample_token_info)
        assert risk_poor > risk  # Poor metrics = higher risk

    def test_risk_classification(self, mhti_instance):
        """Test risk level classification."""
        # Test different score ranges
        assert mhti_instance._classify(0.1) == "safe"
        assert mhti_instance._classify(0.45) == "monitor"
        assert mhti_instance._classify(0.70) == "high"
        assert mhti_instance._classify(0.90) == "critical"

    def test_confidence_interval_calculation(self, mhti_instance):
        """Test confidence interval calculation."""
        buckets = {"risk": 0.8, "technical": 0.6, "market": 0.7}
        ci = mhti_instance._compute_confidence_interval(0.7, buckets)

        # Verify structure
        assert "lower" in ci
        assert "upper" in ci
        assert "uncertainty" in ci

        # Verify bounds
        assert ci["lower"] <= 0.7
        assert ci["upper"] >= 0.7
        assert ci["lower"] >= 0.0
        assert ci["upper"] <= 1.0

        # Verify uncertainty classification
        assert ci["uncertainty"] in ["low", "medium", "high"]

    def test_top_factors_ranking(self, mhti_instance):
        """Test top factors ranking."""
        buckets = {"risk": 0.8, "technical": 0.3, "market": 0.5}
        factors = mhti_instance._rank_top_factors(buckets)

        # Verify structure
        assert len(factors) == 3
        assert all("factor" in f and "value" in f for f in factors)

        # Verify sorting (descending)
        assert factors[0]["factor"] == "risk"
        assert factors[1]["factor"] == "market"
        assert factors[2]["factor"] == "technical"

    @pytest.mark.asyncio
    async def test_caching(self, mhti_instance, sample_token_info):
        """Test MHTI caching mechanism."""
        with patch('ai.multi_headed_threat_index.ComprehensiveThreatDetector') as mock_detector:
            mock_instance = MockThreatDetector({})
            mock_detector.return_value = mock_instance

            # First call - should compute
            result1 = await mhti_instance.classify(sample_token_info)

            # Second call - should use cache
            result2 = await mhti_instance.classify(sample_token_info)

            # Results should be identical (cached)
            assert result1 == result2

            # Mock detector should only be called once
            assert mock_detector.call_count == 1

    def test_weights_sum_to_one(self, mhti_instance):
        """Test that bucket weights sum to 1.0."""
        total_weight = sum(mhti_instance.weights.values())
        assert abs(total_weight - 1.0) < 1e-6

    @pytest.mark.asyncio
    async def test_no_client_graceful_handling(self, sample_token_info):
        """Test graceful handling when no client is provided."""
        mhti = MultiHeadedThreatIndex(risk_tolerance="medium", client=None)

        result = await mhti.classify(sample_token_info)

        # Should still return valid result
        assert "score" in result
        assert "risk_level" in result

        # Risk bucket should be 0.0 (no threats detected)
        assert result["buckets"]["risk"] == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
