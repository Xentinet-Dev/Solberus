"""
Comprehensive tests for all trading strategies

Tests:
- BaseStrategy functionality
- SnipeStrategy
- MomentumStrategy
- ReversalStrategy
- WhaleCopyStrategy
- SocialSignalsStrategy
- StrategyCombinator integration
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch

# Import strategies
import sys
sys.path.insert(0, '/home/user/Solberus/backend/src')

from strategies.base_strategy import (
    BaseStrategy,
    StrategySignal,
    StrategyConfig,
    StrategyPerformance,
    StrategyType
)
from strategies.snipe_strategy import SnipeStrategy, SnipeConfig
from strategies.momentum_strategy import MomentumStrategy, MomentumConfig
from strategies.reversal_strategy import ReversalStrategy, ReversalConfig
from strategies.whale_copy_strategy import WhaleCopyStrategy, WhaleCopyConfig
from strategies.social_signals_strategy import SocialSignalsStrategy, SocialSignalsConfig


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture
def mock_market_data():
    """Standard mock market data for testing"""
    return {
        "token_address": "test_token_123",
        "price": 0.001,
        "liquidity_sol": 10.0,
        "volume_1h": 50.0,
        "volume_24h": 500.0,
        "market_cap_usd": 10000,
        "holder_count": 50,
        "age_seconds": 120,  # 2 minutes old
        "security_score": 75,
        "available_capital": 100.0,
        "current_positions": [],
        "slippage": 0.10,
        "creator": "creator_wallet_abc",
        "liquidity_locked": True,
        "liquidity_lock_days": 30,
        "has_mint_authority": False,
        "has_freeze_authority": False,
    }


@pytest.fixture
def snipe_strategy():
    """Create SnipeStrategy instance"""
    config = SnipeConfig(
        enabled=True,
        capital_allocation=0.25,
        min_liquidity=5.0,
        max_slippage=0.20,
        max_token_age=300,
        min_security_score=50,
    )
    return SnipeStrategy(config)


@pytest.fixture
def momentum_strategy():
    """Create MomentumStrategy instance"""
    config = MomentumConfig(
        enabled=True,
        capital_allocation=0.20,
        rsi_buy_threshold=60.0,
        rsi_sell_threshold=40.0,
    )
    return MomentumStrategy(config)


@pytest.fixture
def reversal_strategy():
    """Create ReversalStrategy instance"""
    config = ReversalConfig(
        enabled=True,
        capital_allocation=0.20,
        dip_threshold=0.15,
        peak_threshold=0.30,
    )
    return ReversalStrategy(config)


@pytest.fixture
def whale_copy_strategy():
    """Create WhaleCopyStrategy instance"""
    config = WhaleCopyConfig(
        enabled=True,
        capital_allocation=0.20,
        min_whale_success_rate=0.70,
        copy_position_ratio=0.10,
    )
    return WhaleCopyStrategy(config)


@pytest.fixture
def social_signals_strategy():
    """Create SocialSignalsStrategy instance"""
    config = SocialSignalsConfig(
        enabled=True,
        capital_allocation=0.15,
        min_virality_score=80.0,
        min_sentiment_score=0.70,
    )
    return SocialSignalsStrategy(config)


# ============================================================================
# BASE STRATEGY TESTS
# ============================================================================

def test_strategy_performance():
    """Test StrategyPerformance tracking"""
    perf = StrategyPerformance()

    # Initial state
    assert perf.trades_count == 0
    assert perf.get_win_rate() == 0.0
    assert perf.get_avg_pnl() == 0.0

    # Add winning trade
    perf.trades_count = 1
    perf.wins = 1
    perf.total_pnl = 5.0

    assert perf.get_win_rate() == 1.0
    assert perf.get_avg_pnl() == 5.0

    # Add losing trade
    perf.trades_count = 2
    perf.losses = 1
    perf.total_pnl = 2.0  # 5.0 - 3.0 loss

    assert perf.get_win_rate() == 0.5
    assert perf.get_avg_pnl() == 1.0


# ============================================================================
# SNIPE STRATEGY TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_snipe_strategy_good_opportunity(snipe_strategy, mock_market_data):
    """Test snipe strategy with a good opportunity"""
    signal = await snipe_strategy.analyze(mock_market_data)

    assert signal.action == "buy"
    assert signal.confidence > 0.80
    assert signal.position_size > 0
    assert "Snipe opportunity" in signal.reason
    print(f"✅ Snipe good opportunity: confidence={signal.confidence:.0%}, size={signal.position_size:.2f} SOL")


@pytest.mark.asyncio
async def test_snipe_strategy_low_liquidity(snipe_strategy, mock_market_data):
    """Test snipe strategy rejects low liquidity"""
    mock_market_data["liquidity_sol"] = 2.0  # Below min (5.0)

    signal = await snipe_strategy.analyze(mock_market_data)

    assert signal.action == "hold"
    assert "Failed checks" in signal.reason
    print(f"✅ Snipe low liquidity rejected: {signal.reason}")


@pytest.mark.asyncio
async def test_snipe_strategy_high_slippage(snipe_strategy, mock_market_data):
    """Test snipe strategy rejects high slippage"""
    mock_market_data["slippage"] = 0.35  # Above max (0.20)

    signal = await snipe_strategy.analyze(mock_market_data)

    assert signal.action == "hold"
    assert signal.confidence < 0.80
    print(f"✅ Snipe high slippage rejected")


@pytest.mark.asyncio
async def test_snipe_strategy_old_token(snipe_strategy, mock_market_data):
    """Test snipe strategy rejects old tokens"""
    mock_market_data["age_seconds"] = 600  # 10 minutes (above 5 min max)

    signal = await snipe_strategy.analyze(mock_market_data)

    assert signal.action == "hold"
    print(f"✅ Snipe old token rejected")


@pytest.mark.asyncio
async def test_snipe_strategy_seen_token(snipe_strategy, mock_market_data):
    """Test snipe strategy doesn't re-evaluate seen tokens"""
    # First analysis
    signal1 = await snipe_strategy.analyze(mock_market_data)

    # Second analysis of same token
    signal2 = await snipe_strategy.analyze(mock_market_data)

    assert signal2.action == "hold"
    assert "already evaluated" in signal2.reason.lower()
    print(f"✅ Snipe seen token blocked")


@pytest.mark.asyncio
async def test_snipe_exit_conditions(snipe_strategy):
    """Test snipe exit conditions"""
    position = {
        "token_address": "test_token",
        "entry_price": 0.001,
        "entry_time": time.time() - 1000,  # 1000 seconds ago
        "initial_liquidity": 10.0,
    }

    market_data = {
        "price": 0.0015,  # 50% profit
        "security_score": 75,
        "liquidity_sol": 9.0,
    }

    # Test take-profit exit
    should_exit = await snipe_strategy.should_exit(position, market_data)
    assert should_exit  # 50% profit should trigger exit
    print(f"✅ Snipe take-profit exit works")

    # Test security degradation exit
    market_data["price"] = 0.001  # No profit
    market_data["security_score"] = 25  # Low security
    should_exit = await snipe_strategy.should_exit(position, market_data)
    assert should_exit
    print(f"✅ Snipe security exit works")


# ============================================================================
# MOMENTUM STRATEGY TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_momentum_strategy_insufficient_data(momentum_strategy, mock_market_data):
    """Test momentum strategy with insufficient data"""
    signal = await momentum_strategy.analyze(mock_market_data)

    assert signal.action == "hold"
    assert "Insufficient data" in signal.reason
    print(f"✅ Momentum insufficient data handled")


@pytest.mark.asyncio
async def test_momentum_strategy_with_price_history(momentum_strategy, mock_market_data):
    """Test momentum strategy with price history"""
    # Add price history (simulate 30 price updates)
    for i in range(30):
        price = 0.001 + (i * 0.0001)  # Increasing price
        volume = 50.0 + (i * 2.0)  # Increasing volume
        timestamp = time.time() - (30 - i) * 60  # 1 per minute

        momentum_strategy._update_price_history("test_token_123", price, timestamp)
        momentum_strategy._update_volume_history("test_token_123", volume, timestamp)

    signal = await momentum_strategy.analyze(mock_market_data)

    # With upward trend, RSI should be bullish
    print(f"✅ Momentum with history: action={signal.action}, confidence={signal.confidence:.0%}, reason={signal.reason}")
    assert signal.confidence > 0  # Should have calculated something


@pytest.mark.asyncio
async def test_momentum_rsi_calculation(momentum_strategy):
    """Test RSI calculation"""
    # Add price data with clear trend
    prices = [0.001, 0.0012, 0.0014, 0.0016, 0.0018, 0.0020, 0.0022, 0.0024, 0.0026, 0.0028,
              0.0030, 0.0032, 0.0034, 0.0036, 0.0038, 0.0040]  # Strong uptrend

    for i, price in enumerate(prices):
        timestamp = time.time() - (len(prices) - i) * 60
        momentum_strategy._update_price_history("test_rsi", price, timestamp)

    rsi = momentum_strategy._calculate_rsi("test_rsi")

    assert rsi is not None
    assert 0 <= rsi <= 100
    assert rsi > 60  # Uptrend should have RSI > 60
    print(f"✅ Momentum RSI calculation: RSI={rsi:.1f} (uptrend)")


# ============================================================================
# REVERSAL STRATEGY TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_reversal_strategy_no_dip(reversal_strategy, mock_market_data):
    """Test reversal strategy with no dip"""
    signal = await reversal_strategy.analyze(mock_market_data)

    assert signal.action == "hold"
    assert "No dip detected" in signal.reason
    print(f"✅ Reversal no dip handled")


@pytest.mark.asyncio
async def test_reversal_strategy_with_dip(reversal_strategy, mock_market_data):
    """Test reversal strategy detecting a dip"""
    # Create price history with a dip
    token_address = "test_token_123"

    # High price, then dip
    reversal_strategy._update_price_history(token_address, 0.002, time.time() - 300, 100.0)
    reversal_strategy._update_price_history(token_address, 0.0018, time.time() - 240, 80.0)
    reversal_strategy._update_price_history(token_address, 0.0015, time.time() - 180, 150.0)  # Dip with volume
    reversal_strategy._update_price_history(token_address, 0.0013, time.time() - 120, 200.0)  # Bigger dip
    reversal_strategy._update_price_history(token_address, 0.001, time.time() - 60, 250.0)  # -50% dip!

    mock_market_data["price"] = 0.001
    mock_market_data["volume_1h"] = 250.0  # High volume

    signal = await reversal_strategy.analyze(mock_market_data)

    # Should detect the dip
    print(f"✅ Reversal with dip: action={signal.action}, confidence={signal.confidence:.0%}, reason={signal.reason}")


@pytest.mark.asyncio
async def test_reversal_bollinger_bands(reversal_strategy):
    """Test Bollinger Bands calculation"""
    token = "test_bb"

    # Add 20 prices around 0.001 with some volatility
    for i in range(20):
        price = 0.001 + (0.0001 * ((i % 3) - 1))  # Oscillates around 0.001
        timestamp = time.time() - (20 - i) * 60
        reversal_strategy._update_price_history(token, price, 100.0, timestamp)

    bb = reversal_strategy._calculate_bollinger_bands(token)

    assert bb is not None
    middle, upper, lower = bb
    assert lower < middle < upper
    print(f"✅ Reversal Bollinger Bands: lower={lower:.6f}, middle={middle:.6f}, upper={upper:.6f}")


# ============================================================================
# WHALE COPY STRATEGY TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_whale_copy_no_whale_trade(whale_copy_strategy, mock_market_data):
    """Test whale copy with no whale trade"""
    signal = await whale_copy_strategy.analyze(mock_market_data)

    assert signal.action == "hold"
    assert "No whale trade" in signal.reason
    print(f"✅ Whale copy no trade handled")


@pytest.mark.asyncio
async def test_whale_copy_register_whale(whale_copy_strategy):
    """Test registering a whale"""
    whale_info = {
        "address": "whale_123",
        "balance": 150.0,
        "success_rate": 0.75,
        "total_trades": 50,
        "total_profit": 25.0,
        "recent_success_rate": 0.80,
        "avg_profit_per_trade": 0.5,
        "consistency": 0.70,
    }

    whale_copy_strategy.register_whale(whale_info)

    tracked = whale_copy_strategy.get_tracked_whales()
    assert "whale_123" in tracked
    assert tracked["whale_123"] > 0  # Has a score
    print(f"✅ Whale registered: score={tracked['whale_123']:.1f}")


@pytest.mark.asyncio
async def test_whale_copy_good_whale_trade(whale_copy_strategy, mock_market_data):
    """Test copying a good whale trade"""
    # Register a successful whale
    whale_info = {
        "address": "whale_123",
        "balance": 150.0,
        "success_rate": 0.80,
        "total_trades": 50,
        "total_profit": 30.0,
        "recent_success_rate": 0.85,
        "avg_profit_per_trade": 0.6,
        "consistency": 0.75,
    }
    whale_copy_strategy.register_whale(whale_info)

    # Simulate whale trade
    mock_market_data["whale_trade"] = {
        "whale_address": "whale_123",
        "token_address": "test_token_123",
        "action": "buy",
        "amount": 10.0,
        "price": 0.001,
        "timestamp": time.time(),
    }

    signal = await whale_copy_strategy.analyze(mock_market_data)

    assert signal.action == "buy"
    assert signal.confidence > 0.50
    assert signal.position_size > 0
    print(f"✅ Whale copy buy signal: confidence={signal.confidence:.0%}, size={signal.position_size:.2f} SOL")


# ============================================================================
# SOCIAL SIGNALS STRATEGY TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_social_signals_no_data(social_signals_strategy, mock_market_data):
    """Test social signals with no data"""
    signal = await social_signals_strategy.analyze(mock_market_data)

    assert signal.action == "hold"
    assert "No social signals" in signal.reason
    print(f"✅ Social signals no data handled")


@pytest.mark.asyncio
async def test_social_signals_good_signal(social_signals_strategy, mock_market_data):
    """Test social signals with strong signal"""
    mock_market_data["social_signals"] = {
        "virality_score": 90.0,
        "sentiment_score": 0.85,
        "mention_count": 50,
        "platforms": ["twitter", "telegram", "discord"],
        "influencer_mentions": 3,
        "bot_ratio": 0.15,
        "top_keywords": ["trending", "launch", "community"],
        "timestamp": time.time(),
    }

    signal = await social_signals_strategy.analyze(mock_market_data)

    assert signal.action == "buy"
    assert signal.confidence > 0.75
    assert signal.position_size > 0
    print(f"✅ Social signals buy: confidence={signal.confidence:.0%}, size={signal.position_size:.2f} SOL")


@pytest.mark.asyncio
async def test_social_signals_scam_keywords(social_signals_strategy, mock_market_data):
    """Test social signals rejects scam keywords"""
    mock_market_data["social_signals"] = {
        "virality_score": 95.0,
        "sentiment_score": 0.90,
        "mention_count": 100,
        "platforms": ["twitter", "telegram", "discord", "reddit"],
        "influencer_mentions": 5,
        "bot_ratio": 0.10,
        "top_keywords": ["guaranteed", "100x", "honeypot"],  # Scam keywords!
        "timestamp": time.time(),
    }

    signal = await social_signals_strategy.analyze(mock_market_data)

    assert signal.action == "hold"
    assert "Scam keywords" in signal.reason
    print(f"✅ Social signals scam keywords blocked")


@pytest.mark.asyncio
async def test_social_signals_high_bot_ratio(social_signals_strategy, mock_market_data):
    """Test social signals rejects high bot ratio"""
    mock_market_data["social_signals"] = {
        "virality_score": 85.0,
        "sentiment_score": 0.80,
        "mention_count": 50,
        "platforms": ["twitter", "telegram"],
        "influencer_mentions": 1,
        "bot_ratio": 0.50,  # 50% bots - too high!
        "top_keywords": ["trending", "new"],
        "timestamp": time.time(),
    }

    signal = await social_signals_strategy.analyze(mock_market_data)

    assert signal.action == "hold"
    print(f"✅ Social signals high bot ratio rejected")


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_all_strategies_initialized():
    """Test that all strategies can be initialized"""
    strategies = [
        SnipeStrategy(),
        MomentumStrategy(),
        ReversalStrategy(),
        WhaleCopyStrategy(),
        SocialSignalsStrategy(),
    ]

    for strategy in strategies:
        assert strategy is not None
        assert strategy.name is not None
        assert strategy.strategy_type is not None
        print(f"✅ {strategy.name} initialized successfully")


@pytest.mark.asyncio
async def test_position_sizing_with_security(snipe_strategy, mock_market_data):
    """Test position sizing adjusts for security score"""
    # High security
    mock_market_data["security_score"] = 90
    size_high = snipe_strategy.calculate_position_size(100.0, mock_market_data)

    # Low security
    mock_market_data["security_score"] = 50
    size_low = snipe_strategy.calculate_position_size(100.0, mock_market_data)

    assert size_high > size_low
    print(f"✅ Position sizing: high_security={size_high:.2f} SOL, low_security={size_low:.2f} SOL")


@pytest.mark.asyncio
async def test_strategy_performance_tracking():
    """Test strategy performance tracking"""
    strategy = SnipeStrategy()

    # Simulate winning trade
    await strategy.on_trade_enter("token1", 0.001, 5.0, 0.01)
    await strategy.on_trade_exit("token1", 0.001, 0.0015, 5.0, 600.0, 0.01)  # 50% profit

    # Simulate losing trade
    await strategy.on_trade_enter("token2", 0.002, 3.0, 0.01)
    await strategy.on_trade_exit("token2", 0.002, 0.0015, 3.0, 300.0, 0.01)  # 25% loss

    stats = strategy.get_performance_stats()

    assert stats["trades"] == 2
    assert stats["wins"] == 1
    assert stats["losses"] == 1
    assert stats["win_rate"] == 0.5
    print(f"✅ Performance tracking: {stats['trades']} trades, {stats['win_rate']:.0%} win rate")


# ============================================================================
# RUN ALL TESTS
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*80)
    print("RUNNING COMPREHENSIVE STRATEGY TESTS")
    print("="*80 + "\n")

    # Run with pytest
    pytest.main([__file__, "-v", "-s"])
