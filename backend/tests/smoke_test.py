#!/usr/bin/env python3
"""
Solberus Trading Bot - Smoke Test

Quick validation that all core components are working.
Run this script to verify the system is functional.
"""

import asyncio
import sys
sys.path.insert(0, '/home/user/Solberus/backend/src')

from strategies.snipe_strategy import SnipeStrategy, SnipeConfig
from strategies.momentum_strategy import MomentumStrategy, MomentumConfig
from strategies.reversal_strategy import ReversalStrategy, ReversalConfig
from strategies.whale_copy_strategy import WhaleCopyStrategy, WhaleCopyConfig
from strategies.social_signals_strategy import SocialSignalsStrategy, SocialSignalsConfig


def print_header(text):
    """Print formatted header"""
    print("\n" + "="*80)
    print(f"  {text}")
    print("="*80)


def print_result(test_name, passed, details=""):
    """Print test result"""
    symbol = "✅" if passed else "❌"
    status = "PASS" if passed else "FAIL"
    print(f"{symbol} {test_name:50s} {status}")
    if details:
        print(f"   └─ {details}")


async def test_strategy_initialization():
    """Test 1: Can we initialize all strategies?"""
    print_header("TEST 1: Strategy Initialization")

    strategies = {
        "SnipeStrategy": SnipeStrategy(),
        "MomentumStrategy": MomentumStrategy(),
        "ReversalStrategy": ReversalStrategy(),
        "WhaleCopyStrategy": WhaleCopyStrategy(),
        "SocialSignalsStrategy": SocialSignalsStrategy(),
    }

    all_passed = True
    for name, strategy in strategies.items():
        passed = strategy is not None and strategy.enabled
        print_result(name, passed, f"Type: {strategy.strategy_type.value}")
        if not passed:
            all_passed = False

    return all_passed


async def test_signal_generation():
    """Test 2: Can strategies generate signals?"""
    print_header("TEST 2: Signal Generation")

    # Create a good market scenario
    market_data = {
        "token_address": "smoke_test_token",
        "price": 0.001,
        "liquidity_sol": 15.0,  # Good liquidity
        "volume_1h": 100.0,
        "volume_24h": 1000.0,
        "market_cap_usd": 20000,
        "holder_count": 100,
        "age_seconds": 120,  # 2 minutes - fresh!
        "security_score": 80,  # High security
        "available_capital": 50.0,
        "slippage": 0.08,  # Low slippage
        "creator": "good_creator",
        "liquidity_locked": True,
        "has_mint_authority": False,
        "has_freeze_authority": False,
    }

    snipe = SnipeStrategy()
    signal = await snipe.analyze(market_data)

    passed = signal is not None
    print_result("Signal Generation", passed,
                 f"Action: {signal.action}, Confidence: {signal.confidence:.0%}")

    if passed:
        print(f"   └─ Reason: {signal.reason[:60]}...")
        print(f"   └─ Position Size: {signal.position_size:.2f} SOL")

    return passed


async def test_position_sizing():
    """Test 3: Does position sizing work?"""
    print_header("TEST 3: Position Sizing")

    strategy = SnipeStrategy()

    market_data_high_sec = {"security_score": 90}
    market_data_low_sec = {"security_score": 40}

    size_high = strategy.calculate_position_size(100.0, market_data_high_sec)
    size_low = strategy.calculate_position_size(100.0, market_data_low_sec)

    passed = size_high > size_low > 0
    print_result("Position Sizing", passed,
                 f"High security: {size_high:.2f} SOL, Low security: {size_low:.2f} SOL")

    return passed


async def test_performance_tracking():
    """Test 4: Does performance tracking work?"""
    print_header("TEST 4: Performance Tracking")

    strategy = SnipeStrategy()

    # Simulate a winning trade
    await strategy.on_trade_enter("test_token", 0.001, 10.0, 0.05)
    await strategy.on_trade_exit("test_token", 0.001, 0.0015, 10.0, 600.0, 0.05)

    stats = strategy.get_performance_stats()
    passed = stats["trades_count"] == 1 and stats["wins"] == 1

    print_result("Performance Tracking", passed,
                 f"Trades: {stats['trades_count']}, Wins: {stats['wins']}, P&L: {stats['total_pnl']:.4f} SOL")

    return passed


async def test_multiple_strategies_parallel():
    """Test 5: Can multiple strategies run in parallel?"""
    print_header("TEST 5: Parallel Strategy Execution")

    market_data = {
        "token_address": "parallel_test",
        "price": 0.001,
        "liquidity_sol": 10.0,
        "volume_1h": 50.0,
        "security_score": 70,
        "available_capital": 100.0,
        "age_seconds": 180,
        "slippage": 0.15,
        "holder_count": 30,
    }

    # Run 3 strategies in parallel
    strategies = [
        SnipeStrategy(),
        MomentumStrategy(),
        ReversalStrategy(),
    ]

    tasks = [strategy.analyze(market_data) for strategy in strategies]
    signals = await asyncio.gather(*tasks)

    passed = len(signals) == 3 and all(s is not None for s in signals)
    print_result("Parallel Execution", passed,
                 f"Executed {len(signals)} strategies concurrently")

    for i, signal in enumerate(signals):
        print(f"   └─ Strategy {i+1}: {signal.action} ({signal.confidence:.0%} confidence)")

    return passed


async def test_whale_copy():
    """Test 6: Whale copy strategy functionality"""
    print_header("TEST 6: Whale Copy Strategy")

    whale = WhaleCopyStrategy()

    # Register a whale
    whale_info = {
        "address": "whale_test_123",
        "balance": 200.0,
        "success_rate": 0.80,
        "total_trades": 100,
        "total_profit": 50.0,
        "recent_success_rate": 0.85,
        "avg_profit_per_trade": 0.5,
        "consistency": 0.75,
    }

    whale.register_whale(whale_info)
    tracked = whale.get_tracked_whales()

    passed = "whale_test_123" in tracked and tracked["whale_test_123"] > 0
    print_result("Whale Registration", passed,
                 f"Whale score: {tracked.get('whale_test_123', 0):.1f}")

    return passed


async def test_social_signals():
    """Test 7: Social signals strategy"""
    print_header("TEST 7: Social Signals Strategy")

    social = SocialSignalsStrategy()

    market_data = {
        "token_address": "social_test",
        "security_score": 70,
        "available_capital": 50.0,
        "social_signals": {
            "virality_score": 85.0,
            "sentiment_score": 0.80,
            "mention_count": 75,
            "platforms": ["twitter", "telegram", "discord"],
            "influencer_mentions": 2,
            "bot_ratio": 0.20,
            "top_keywords": ["trending", "new", "community"],
            "timestamp": asyncio.get_event_loop().time(),
        }
    }

    signal = await social.analyze(market_data)

    passed = signal is not None
    print_result("Social Signals Analysis", passed,
                 f"Action: {signal.action}, Confidence: {signal.confidence:.0%}")

    return passed


async def run_all_tests():
    """Run all smoke tests"""
    print("\n" + "#"*80)
    print("#" + " "*20 + "SOLBERUS TRADING BOT - SMOKE TEST" + " "*26 + "#")
    print("#"*80)

    tests = [
        ("Strategy Initialization", test_strategy_initialization),
        ("Signal Generation", test_signal_generation),
        ("Position Sizing", test_position_sizing),
        ("Performance Tracking", test_performance_tracking),
        ("Parallel Execution", test_multiple_strategies_parallel),
        ("Whale Copy Strategy", test_whale_copy),
        ("Social Signals Strategy", test_social_signals),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name} - EXCEPTION: {str(e)}")
            results.append((name, False))

    # Print summary
    print_header("TEST SUMMARY")

    passed = sum(1 for _, result in results if result)
    total = len(results)
    percentage = (passed / total * 100) if total > 0 else 0

    print(f"\n  Total Tests: {total}")
    print(f"  Passed: {passed} ✅")
    print(f"  Failed: {total - passed} ❌")
    print(f"  Success Rate: {percentage:.0f}%")

    if passed == total:
        print("\n  🎉 ALL TESTS PASSED! System is functional.")
        print("  ✅ Ready for frontend integration and further testing.")
    elif passed >= total * 0.8:
        print("\n  ✅ MOSTLY PASSING! Core functionality works.")
        print("  ⚠️  Some minor issues need attention.")
    else:
        print("\n  ❌ MULTIPLE FAILURES! Review logs above.")
        print("  🔧 System needs debugging before proceeding.")

    print("\n" + "#"*80 + "\n")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
