"""
Base Strategy Interface for Solberus Trading Bot

Defines the abstract base class that all trading strategies must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum
import time
import logging

logger = logging.getLogger(__name__)


class StrategyType(Enum):
    """Available strategy types"""
    SNIPE = "snipe"
    VOLUME_BOOST = "volume_boost"
    MOMENTUM = "momentum"
    REVERSAL = "reversal"
    WHALE_COPY = "whale_copy"
    MARKET_MAKING = "market_making"
    SOCIAL_SIGNALS = "social_signals"


@dataclass
class StrategySignal:
    """Signal emitted by a strategy"""
    strategy_name: str
    action: str  # "buy", "sell", "hold"
    confidence: float  # 0.0 to 1.0
    position_size: float  # SOL amount
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "strategy_name": self.strategy_name,
            "action": self.action,
            "confidence": self.confidence,
            "position_size": self.position_size,
            "reason": self.reason,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


@dataclass
class StrategyConfig:
    """Base configuration for all strategies"""
    enabled: bool = True
    capital_allocation: float = 1.0  # % of available capital (0.0 to 1.0)
    max_position_size: float = 10.0  # SOL
    stop_loss: float = -0.10  # -10%
    take_profit: float = 0.50  # +50%
    max_hold_time: int = 3600  # seconds (1 hour default)
    min_confidence: float = 0.75  # Minimum confidence to act

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "enabled": self.enabled,
            "capital_allocation": self.capital_allocation,
            "max_position_size": self.max_position_size,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "max_hold_time": self.max_hold_time,
            "min_confidence": self.min_confidence,
        }


@dataclass
class StrategyPerformance:
    """Track strategy performance metrics"""
    trades_count: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    total_fees: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    total_volume: float = 0.0
    avg_hold_time: float = 0.0
    last_trade_time: Optional[float] = None

    def get_win_rate(self) -> float:
        """Calculate win rate"""
        if self.trades_count == 0:
            return 0.0
        return self.wins / self.trades_count

    def get_avg_pnl(self) -> float:
        """Calculate average P&L per trade"""
        if self.trades_count == 0:
            return 0.0
        return self.total_pnl / self.trades_count

    def get_net_pnl(self) -> float:
        """Calculate net P&L (after fees)"""
        return self.total_pnl - self.total_fees

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "trades_count": self.trades_count,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": self.get_win_rate(),
            "total_pnl": self.total_pnl,
            "total_fees": self.total_fees,
            "net_pnl": self.get_net_pnl(),
            "avg_pnl": self.get_avg_pnl(),
            "best_trade": self.best_trade,
            "worst_trade": self.worst_trade,
            "total_volume": self.total_volume,
            "avg_hold_time": self.avg_hold_time,
            "last_trade_time": self.last_trade_time,
        }


class BaseStrategy(ABC):
    """Abstract base class for all trading strategies"""

    def __init__(self, config: StrategyConfig, strategy_type: StrategyType):
        self.config = config
        self.strategy_type = strategy_type
        self.name = self.__class__.__name__
        self.enabled = config.enabled
        self.performance = StrategyPerformance()

        # Cache for strategy-specific data
        self._cache: Dict[str, Any] = {}

        logger.info(f"Initialized {self.name} (type={strategy_type.value}, enabled={self.enabled})")

    @abstractmethod
    async def analyze(self, market_data: Dict[str, Any]) -> StrategySignal:
        """
        Analyze market data and return a trading signal

        Args:
            market_data: Dict containing:
                - token_address: str
                - price: float
                - liquidity_sol: float
                - volume_24h: float
                - market_cap_usd: float
                - holder_count: int
                - age_seconds: int
                - security_score: int (0-100)
                - available_capital: float
                - current_positions: List[Dict]
                - Additional strategy-specific data

        Returns:
            StrategySignal with action recommendation
        """
        pass

    @abstractmethod
    async def should_enter(self, token_address: str, market_data: Dict[str, Any]) -> bool:
        """
        Determine if strategy should enter a position

        Args:
            token_address: Token address to evaluate
            market_data: Market data for the token

        Returns:
            True if should enter, False otherwise
        """
        pass

    @abstractmethod
    async def should_exit(self, position: Dict[str, Any], market_data: Dict[str, Any]) -> bool:
        """
        Determine if strategy should exit a position

        Args:
            position: Current position data
                - token_address: str
                - entry_price: float
                - current_price: float
                - entry_time: float
                - amount: float
                - strategy: str
            market_data: Current market data

        Returns:
            True if should exit, False otherwise
        """
        pass

    def calculate_position_size(
        self,
        available_capital: float,
        market_data: Dict[str, Any]
    ) -> float:
        """
        Calculate position size based on capital allocation and risk

        Args:
            available_capital: Available capital in SOL
            market_data: Market data for sizing decisions

        Returns:
            Position size in SOL
        """
        # Base calculation: allocated capital
        allocated = available_capital * self.config.capital_allocation

        # Apply max position size limit
        position_size = min(allocated, self.config.max_position_size)

        # Adjust based on security score (lower security = smaller position)
        security_score = market_data.get("security_score", 50)
        if security_score < 70:
            security_multiplier = security_score / 70.0
            position_size *= security_multiplier

        # Ensure minimum viable position (0.1 SOL minimum)
        if position_size < 0.1:
            return 0.0

        return round(position_size, 4)

    async def on_trade_enter(
        self,
        token_address: str,
        entry_price: float,
        amount: float,
        fees: float = 0.0
    ):
        """
        Called when strategy enters a trade

        Args:
            token_address: Token address
            entry_price: Entry price
            amount: Position size in SOL
            fees: Transaction fees
        """
        self.performance.total_volume += amount
        self.performance.total_fees += fees
        logger.info(
            f"{self.name} entered trade: {token_address} at {entry_price} "
            f"with {amount} SOL (fees: {fees})"
        )

    async def on_trade_exit(
        self,
        token_address: str,
        entry_price: float,
        exit_price: float,
        amount: float,
        hold_time: float,
        fees: float = 0.0
    ):
        """
        Called when strategy exits a trade

        Args:
            token_address: Token address
            entry_price: Entry price
            exit_price: Exit price
            amount: Position size in SOL
            hold_time: Hold time in seconds
            fees: Transaction fees
        """
        # Calculate P&L
        pnl_percent = (exit_price - entry_price) / entry_price
        pnl_sol = amount * pnl_percent
        was_win = pnl_sol > 0

        # Update performance metrics
        self.performance.trades_count += 1
        self.performance.total_pnl += pnl_sol
        self.performance.total_fees += fees
        self.performance.last_trade_time = time.time()

        if was_win:
            self.performance.wins += 1
        else:
            self.performance.losses += 1

        # Update best/worst trades
        if pnl_sol > self.performance.best_trade:
            self.performance.best_trade = pnl_sol
        if pnl_sol < self.performance.worst_trade:
            self.performance.worst_trade = pnl_sol

        # Update average hold time
        if self.performance.trades_count == 1:
            self.performance.avg_hold_time = hold_time
        else:
            # Weighted average
            total_time = self.performance.avg_hold_time * (self.performance.trades_count - 1)
            self.performance.avg_hold_time = (total_time + hold_time) / self.performance.trades_count

        logger.info(
            f"{self.name} exited trade: {token_address} "
            f"P&L: {pnl_sol:.4f} SOL ({pnl_percent:.2%}) "
            f"Hold: {hold_time:.0f}s (fees: {fees})"
        )

    def check_exit_conditions(
        self,
        position: Dict[str, Any],
        current_price: float,
        current_time: float
    ) -> tuple[bool, str]:
        """
        Check standard exit conditions (stop-loss, take-profit, max hold time)

        Args:
            position: Position data
            current_price: Current token price
            current_time: Current timestamp

        Returns:
            Tuple of (should_exit, reason)
        """
        entry_price = position.get("entry_price")
        entry_time = position.get("entry_time")

        if not entry_price or not entry_time:
            return False, ""

        # Calculate P&L percentage
        pnl_percent = (current_price - entry_price) / entry_price

        # Check take-profit
        if pnl_percent >= self.config.take_profit:
            return True, f"Take-profit reached ({pnl_percent:.2%})"

        # Check stop-loss
        if pnl_percent <= self.config.stop_loss:
            return True, f"Stop-loss triggered ({pnl_percent:.2%})"

        # Check max hold time
        hold_time = current_time - entry_time
        if hold_time >= self.config.max_hold_time:
            return True, f"Max hold time reached ({hold_time:.0f}s)"

        return False, ""

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics"""
        stats = self.performance.to_dict()
        stats.update({
            "name": self.name,
            "type": self.strategy_type.value,
            "enabled": self.enabled,
            "config": self.config.to_dict(),
        })
        return stats

    def reset_performance(self):
        """Reset performance metrics (useful for testing)"""
        self.performance = StrategyPerformance()
        logger.info(f"{self.name} performance metrics reset")

    def enable(self):
        """Enable the strategy"""
        self.enabled = True
        self.config.enabled = True
        logger.info(f"{self.name} enabled")

    def disable(self):
        """Disable the strategy"""
        self.enabled = False
        self.config.enabled = False
        logger.info(f"{self.name} disabled")
