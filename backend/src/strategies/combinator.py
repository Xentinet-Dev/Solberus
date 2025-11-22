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

from interfaces.core import TokenInfo
from trading.base import TradeResult
from utils.logger import get_logger

logger = get_logger(__name__)


class StrategyType(Enum):
    """Types of trading strategies."""

    SNIPE = "snipe"  # Early entry on new tokens
    VOLUME_BOOST = "volume_boost"  # Add volume to boost token
    MARKET_MAKING = "market_making"  # Provide liquidity
    MOMENTUM = "momentum"  # Follow momentum
    REVERSAL = "reversal"  # Counter-trend
    WHALE_COPY = "whale_copy"  # Copy whale trades


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
            logger.debug(
                f"Executing {strategy_config.strategy_type.value} strategy "
                f"with {capital:.6f} SOL..."
            )

            # In production, this would:
            # 1. Check strategy confidence
            # 2. Execute strategy-specific logic
            # 3. Return trade result

            # Placeholder - would execute actual strategy
            # This would integrate with the actual trading system

            return None  # Placeholder

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

