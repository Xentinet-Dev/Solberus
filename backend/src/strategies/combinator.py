"""
Strategy Combinator - Combines multiple trading strategies for enhanced performance.

Supports:
- Strategy merging logic
- Atomic execution
- Capital allocation
- Performance tracking
"""

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional
import time

# Import new strategy implementations
from .base_strategy import BaseStrategy, StrategyType
from .snipe_strategy import SnipeStrategy, SnipeConfig
from .momentum_strategy import MomentumStrategy, MomentumConfig
from .reversal_strategy import ReversalStrategy, ReversalConfig
from .whale_copy_strategy import WhaleCopyStrategy, WhaleCopyConfig
from .social_signals_strategy import SocialSignalsStrategy, SocialSignalsConfig

from interfaces.core import TokenInfo
from trading.base import TradeResult
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class StrategyConfig:
    """Configuration for a trading strategy."""

    strategy_type: StrategyType
    enabled: bool = True
    capital_allocation: float = 0.0  # 0.0 to 1.0 (percentage of total capital)
    min_confidence: float = 0.5  # Minimum confidence to execute
    max_position_size: float = 1.0  # Maximum position size in SOL
    parameters: Dict[str, Any] = None


@dataclass
class CombinedStrategyResult:
    """Result of executing a combined strategy."""

    success: bool
    strategies_executed: List[str]
    total_capital_used: float
    results: List[TradeResult]
    combined_profit: float = 0.0
    error_message: Optional[str] = None


class StrategyCombinator:
    """
    Combines multiple trading strategies for enhanced performance.

    Supports strategy templates like:
    - Snipe + Volume Boost
    - Entry + Market Making
    - Multiple exit strategies
    """

    def __init__(
        self,
        strategies: List[StrategyConfig],
        total_capital: float = 1.0,  # SOL
    ):
        """Initialize the strategy combinator.

        Args:
            strategies: List of strategy configurations
            total_capital: Total capital available for trading
        """
        self.strategies = strategies
        self.total_capital = total_capital
        self.performance_tracking: Dict[str, Dict[str, Any]] = {}

        # Initialize strategy instances
        self.strategy_instances: Dict[StrategyType, BaseStrategy] = {}
        self._initialize_strategies()

        # Validate capital allocation
        total_allocation = sum(s.capital_allocation for s in strategies if s.enabled)
        if total_allocation > 1.0:
            logger.warning(
                f"Total capital allocation exceeds 100%: {total_allocation*100:.1f}%"
            )

        logger.info(
            f"Initialized Strategy Combinator with {len(strategies)} strategies, "
            f"{total_capital} SOL capital"
        )

    def _initialize_strategies(self):
        """Initialize all strategy instances"""
        # Initialize Snipe Strategy
        snipe_config = SnipeConfig(
            enabled=True,
            capital_allocation=0.25,
            min_liquidity=5.0,
            max_slippage=0.20,
            max_token_age=300,
        )
        self.strategy_instances[StrategyType.SNIPE] = SnipeStrategy(snipe_config)

        # Initialize Momentum Strategy
        momentum_config = MomentumConfig(
            enabled=True,
            capital_allocation=0.20,
            rsi_buy_threshold=60.0,
            rsi_sell_threshold=40.0,
        )
        self.strategy_instances[StrategyType.MOMENTUM] = MomentumStrategy(momentum_config)

        # Initialize Reversal Strategy
        reversal_config = ReversalConfig(
            enabled=True,
            capital_allocation=0.20,
            dip_threshold=0.15,
            peak_threshold=0.30,
        )
        self.strategy_instances[StrategyType.REVERSAL] = ReversalStrategy(reversal_config)

        # Initialize Whale Copy Strategy
        whale_config = WhaleCopyConfig(
            enabled=True,
            capital_allocation=0.20,
            min_whale_success_rate=0.70,
            copy_position_ratio=0.10,
        )
        self.strategy_instances[StrategyType.WHALE_COPY] = WhaleCopyStrategy(whale_config)

        # Initialize Social Signals Strategy
        social_config = SocialSignalsConfig(
            enabled=True,
            capital_allocation=0.15,
            min_virality_score=80.0,
            min_sentiment_score=0.70,
        )
        self.strategy_instances[StrategyType.SOCIAL_SIGNALS] = SocialSignalsStrategy(social_config)

        logger.info(f"Initialized {len(self.strategy_instances)} strategy instances")

    async def execute_combined_strategy(
        self, token_info: TokenInfo
    ) -> CombinedStrategyResult:
        """Execute a combined strategy for a token.

        Args:
            token_info: Token information

        Returns:
            Combined strategy execution result
        """
        logger.info(f"Executing combined strategy for {token_info.symbol}...")

        executed_strategies: List[str] = []
        results: List[TradeResult] = []
        total_capital_used = 0.0

        try:
            # Execute each enabled strategy
            for strategy_config in self.strategies:
                if not strategy_config.enabled:
                    continue

                # Calculate capital allocation
                capital_amount = self.total_capital * strategy_config.capital_allocation

                if capital_amount <= 0:
                    continue

                # Execute strategy
                strategy_result = await self._execute_strategy(
                    strategy_config, token_info, capital_amount
                )

                if strategy_result:
                    executed_strategies.append(strategy_config.strategy_type.value)
                    results.append(strategy_result)
                    total_capital_used += capital_amount

                    # Track performance
                    self._track_performance(strategy_config, strategy_result)

            # Calculate combined profit
            combined_profit = sum(
                (r.price * r.amount) if r.success else 0.0 for r in results
            )

            return CombinedStrategyResult(
                success=len(results) > 0,
                strategies_executed=executed_strategies,
                total_capital_used=total_capital_used,
                results=results,
                combined_profit=combined_profit,
            )

        except Exception as e:
            logger.exception(f"Error executing combined strategy: {e}")
            return CombinedStrategyResult(
                success=False,
                strategies_executed=executed_strategies,
                total_capital_used=total_capital_used,
                results=results,
                error_message=str(e),
            )

    async def _execute_strategy(
        self, strategy_config: StrategyConfig, token_info: TokenInfo, capital: float
    ) -> Optional[TradeResult]:
        """Execute a single strategy.

        Args:
            strategy_config: Strategy configuration
            token_info: Token information
            capital: Capital allocated to this strategy

        Returns:
            Trade result if executed, None otherwise
        """
        try:
            strategy_type = strategy_config.strategy_type
            logger.debug(
                f"Executing {strategy_type.value} strategy "
                f"with {capital:.6f} SOL..."
            )

            # Get strategy instance
            strategy = self.strategy_instances.get(strategy_type)
            if not strategy or not strategy.enabled:
                logger.debug(f"Strategy {strategy_type.value} not available or disabled")
                return None

            # Prepare market data
            market_data = {
                "token_address": str(token_info.address),
                "price": getattr(token_info, 'price', 0.0),
                "liquidity_sol": getattr(token_info, 'liquidity', 0.0),
                "volume_1h": getattr(token_info, 'volume_24h', 0.0),  # Use 24h as proxy
                "volume_24h": getattr(token_info, 'volume_24h', 0.0),
                "market_cap_usd": getattr(token_info, 'market_cap', 0.0),
                "holder_count": getattr(token_info, 'holder_count', 0),
                "age_seconds": int(time.time() - getattr(token_info, 'created_at', time.time())),
                "security_score": getattr(token_info, 'security_score', 50),
                "available_capital": capital,
                "current_positions": [],  # Would come from position manager
                # Additional fields that might be present
                "slippage": getattr(token_info, 'slippage', 0.1),
                "creator": getattr(token_info, 'creator', ""),
                "liquidity_locked": getattr(token_info, 'liquidity_locked', False),
                "has_mint_authority": getattr(token_info, 'has_mint_authority', False),
                "has_freeze_authority": getattr(token_info, 'has_freeze_authority', False),
            }

            # Add strategy-specific data
            if strategy_type == StrategyType.WHALE_COPY:
                # Whale trade would come from whale tracker
                market_data["whale_trade"] = None  # Placeholder
            elif strategy_type == StrategyType.SOCIAL_SIGNALS:
                # Social signals would come from social scanner
                market_data["social_signals"] = None  # Placeholder

            # Analyze with strategy
            signal = await strategy.analyze(market_data)

            # Check if strategy wants to act
            if signal.action == "buy" and signal.confidence >= strategy_config.min_confidence:
                logger.info(
                    f"{strategy_type.value} strategy signaling BUY: "
                    f"confidence={signal.confidence:.0%}, "
                    f"size={signal.position_size:.4f} SOL"
                )

                # Create trade result (in production, would actually execute trade)
                trade_result = TradeResult(
                    success=True,
                    amount=signal.position_size,
                    price=market_data.get("price", 0.0),
                    timestamp=time.time(),
                )

                return trade_result

            else:
                logger.debug(
                    f"{strategy_type.value} strategy decision: {signal.action} "
                    f"(confidence={signal.confidence:.0%}, reason={signal.reason})"
                )
                return None

        except Exception as e:
            logger.exception(f"Error executing strategy {strategy_config.strategy_type.value}: {e}")
            return None

    def _track_performance(
        self, strategy_config: StrategyConfig, result: TradeResult
    ) -> None:
        """Track performance of a strategy.

        Args:
            strategy_config: Strategy configuration
            result: Trade result
        """
        strategy_key = strategy_config.strategy_type.value

        if strategy_key not in self.performance_tracking:
            self.performance_tracking[strategy_key] = {
                "total_trades": 0,
                "successful_trades": 0,
                "total_profit": 0.0,
                "total_volume": 0.0,
            }

        stats = self.performance_tracking[strategy_key]
        stats["total_trades"] += 1

        if result.success:
            stats["successful_trades"] += 1
            profit = result.price * result.amount if result.price and result.amount else 0.0
            stats["total_profit"] += profit
            stats["total_volume"] += result.amount if result.amount else 0.0

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for all strategies.

        Returns:
            Performance summary dictionary
        """
        total_trades = sum(
            stats["total_trades"] for stats in self.performance_tracking.values()
        )
        total_successful = sum(
            stats["successful_trades"] for stats in self.performance_tracking.values()
        )
        total_profit = sum(
            stats["total_profit"] for stats in self.performance_tracking.values()
        )

        success_rate = (
            total_successful / max(total_trades, 1) if total_trades > 0 else 0.0
        )

        return {
            "total_trades": total_trades,
            "total_successful": total_successful,
            "success_rate": success_rate,
            "total_profit": total_profit,
            "strategy_performance": self.performance_tracking,
        }

    @staticmethod
    def create_snipe_volume_boost_combo(
        snipe_allocation: float = 0.7, volume_boost_allocation: float = 0.3
    ) -> List[StrategyConfig]:
        """Create a snipe + volume boost combination.

        Args:
            snipe_allocation: Capital allocation for snipe (0.0 to 1.0)
            volume_boost_allocation: Capital allocation for volume boost (0.0 to 1.0)

        Returns:
            List of strategy configurations
        """
        return [
            StrategyConfig(
                strategy_type=StrategyType.SNIPE,
                enabled=True,
                capital_allocation=snipe_allocation,
                min_confidence=0.8,
            ),
            StrategyConfig(
                strategy_type=StrategyType.VOLUME_BOOST,
                enabled=True,
                capital_allocation=volume_boost_allocation,
                min_confidence=0.6,
            ),
        ]

    @staticmethod
    def create_entry_market_making_combo(
        entry_allocation: float = 0.6, market_making_allocation: float = 0.4
    ) -> List[StrategyConfig]:
        """Create an entry + market making combination.

        Args:
            entry_allocation: Capital allocation for entry (0.0 to 1.0)
            market_making_allocation: Capital allocation for market making (0.0 to 1.0)

        Returns:
            List of strategy configurations
        """
        return [
            StrategyConfig(
                strategy_type=StrategyType.SNIPE,
                enabled=True,
                capital_allocation=entry_allocation,
                min_confidence=0.7,
            ),
            StrategyConfig(
                strategy_type=StrategyType.MARKET_MAKING,
                enabled=True,
                capital_allocation=market_making_allocation,
                min_confidence=0.5,
            ),
        ]

