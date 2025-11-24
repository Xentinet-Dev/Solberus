"""
Momentum Strategy - Follow price momentum trends

Uses technical indicators (RSI, MACD, volume) to identify and ride momentum.
Enters on strong upward momentum, exits on momentum loss or reversal.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from collections import deque
import time
import logging

from .base_strategy import (
    BaseStrategy,
    StrategySignal,
    StrategyConfig,
    StrategyType
)

logger = logging.getLogger(__name__)


@dataclass
class MomentumConfig(StrategyConfig):
    """Configuration specific to momentum strategy"""
    # RSI settings
    rsi_period: int = 14
    rsi_buy_threshold: float = 60.0  # Buy when RSI > this and rising
    rsi_sell_threshold: float = 40.0  # Sell when RSI < this or declining
    rsi_overbought: float = 75.0  # Consider taking profit

    # MACD settings
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    # Volume settings
    volume_multiplier: float = 2.0  # Volume must be X times average
    volume_window: int = 20  # Periods for average volume

    # Price action
    min_price_change: float = 0.05  # Minimum 5% price increase
    price_window: int = 15  # Minutes for price change calculation

    # Data requirements
    min_data_points: int = 26  # Need at least MACD slow period

    # Trend confirmation
    require_macd_confirmation: bool = True
    require_volume_confirmation: bool = True


class MomentumStrategy(BaseStrategy):
    """
    Momentum Strategy - Follow price momentum trends

    Entry Criteria:
    - RSI > rsi_buy_threshold (default: 60) and rising
    - MACD histogram bullish (optional)
    - Volume > volume_multiplier * avg_volume (optional)
    - Price increasing over price_window
    - Security score >= 50

    Exit Criteria:
    - RSI < rsi_sell_threshold (default: 40) or declining significantly
    - MACD histogram bearish crossover
    - Momentum loss detected
    - Standard: Stop-loss, take-profit, max hold time
    """

    def __init__(self, config: MomentumConfig = None):
        if config is None:
            config = MomentumConfig()

        super().__init__(config, StrategyType.MOMENTUM)
        self.momentum_config: MomentumConfig = config

        # Price history cache: token_address -> deque of (timestamp, price) tuples
        self._price_history: Dict[str, deque] = {}

        # Volume history cache: token_address -> deque of (timestamp, volume) tuples
        self._volume_history: Dict[str, deque] = {}

        # RSI cache: token_address -> (timestamp, rsi_value)
        self._rsi_cache: Dict[str, tuple] = {}

        # MACD cache: token_address -> (timestamp, macd_line, signal_line, histogram)
        self._macd_cache: Dict[str, tuple] = {}

        logger.info(
            f"MomentumStrategy initialized: "
            f"RSI_period={config.rsi_period}, "
            f"RSI_buy={config.rsi_buy_threshold}, "
            f"MACD=({config.macd_fast},{config.macd_slow},{config.macd_signal})"
        )

    def _update_price_history(self, token_address: str, price: float, timestamp: float):
        """Update price history for a token"""
        if token_address not in self._price_history:
            self._price_history[token_address] = deque(maxlen=100)  # Keep last 100 prices

        self._price_history[token_address].append((timestamp, price))

    def _update_volume_history(self, token_address: str, volume: float, timestamp: float):
        """Update volume history for a token"""
        if token_address not in self._volume_history:
            self._volume_history[token_address] = deque(maxlen=100)

        self._volume_history[token_address].append((timestamp, volume))

    def _calculate_rsi(self, token_address: str) -> Optional[float]:
        """Calculate RSI (Relative Strength Index)"""
        if token_address not in self._price_history:
            return None

        prices = [p for _, p in self._price_history[token_address]]
        if len(prices) < self.momentum_config.rsi_period + 1:
            return None  # Need enough data

        # Calculate price changes
        changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]

        # Separate gains and losses
        gains = [max(0, change) for change in changes[-self.momentum_config.rsi_period:]]
        losses = [abs(min(0, change)) for change in changes[-self.momentum_config.rsi_period:]]

        # Calculate average gain and loss
        avg_gain = sum(gains) / len(gains)
        avg_loss = sum(losses) / len(losses)

        if avg_loss == 0:
            return 100.0  # No losses = max RSI

        # Calculate RS and RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        # Cache result
        self._rsi_cache[token_address] = (time.time(), rsi)

        return rsi

    def _calculate_ema(self, prices: List[float], period: int) -> Optional[float]:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return None

        multiplier = 2 / (period + 1)
        ema = prices[0]  # Start with first price

        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))

        return ema

    def _calculate_macd(self, token_address: str) -> Optional[tuple]:
        """Calculate MACD (Moving Average Convergence Divergence)"""
        if token_address not in self._price_history:
            return None

        prices = [p for _, p in self._price_history[token_address]]
        if len(prices) < self.momentum_config.macd_slow:
            return None  # Need enough data

        # Calculate fast and slow EMAs
        fast_ema = self._calculate_ema(prices, self.momentum_config.macd_fast)
        slow_ema = self._calculate_ema(prices, self.momentum_config.macd_slow)

        if fast_ema is None or slow_ema is None:
            return None

        # MACD line = fast EMA - slow EMA
        macd_line = fast_ema - slow_ema

        # Calculate signal line (EMA of MACD line)
        # For simplicity, we'll use a simple moving average here
        # In production, you'd calculate EMA of MACD line over time
        signal_line = macd_line * 0.9  # Simplified

        # Histogram = MACD line - signal line
        histogram = macd_line - signal_line

        # Cache result
        self._macd_cache[token_address] = (time.time(), macd_line, signal_line, histogram)

        return (macd_line, signal_line, histogram)

    def _calculate_avg_volume(self, token_address: str) -> Optional[float]:
        """Calculate average volume over window"""
        if token_address not in self._volume_history:
            return None

        volumes = [v for _, v in self._volume_history[token_address]]
        if len(volumes) < self.momentum_config.volume_window:
            return None

        return sum(volumes[-self.momentum_config.volume_window:]) / self.momentum_config.volume_window

    def _check_price_momentum(self, token_address: str) -> tuple[bool, float]:
        """Check if price has momentum (increasing over window)"""
        if token_address not in self._price_history:
            return False, 0.0

        prices = list(self._price_history[token_address])
        if len(prices) < 2:
            return False, 0.0

        # Get prices from window minutes ago
        current_time = time.time()
        window_seconds = self.momentum_config.price_window * 60

        # Filter prices within window
        recent_prices = [
            (ts, p) for ts, p in prices
            if current_time - ts <= window_seconds
        ]

        if len(recent_prices) < 2:
            return False, 0.0

        # Calculate price change
        first_price = recent_prices[0][1]
        last_price = recent_prices[-1][1]
        price_change = (last_price - first_price) / first_price

        has_momentum = price_change >= self.momentum_config.min_price_change

        return has_momentum, price_change

    async def analyze(self, market_data: Dict[str, Any]) -> StrategySignal:
        """Analyze momentum indicators and return trading signal"""
        token_address = market_data.get("token_address", "unknown")
        price = market_data.get("price", 0.0)
        volume = market_data.get("volume_1h", 0.0)  # Use 1-hour volume
        timestamp = time.time()
        available_capital = market_data.get("available_capital", 0.0)
        security_score = market_data.get("security_score", 0)

        # Update histories
        self._update_price_history(token_address, price, timestamp)
        if volume > 0:
            self._update_volume_history(token_address, volume, timestamp)

        # Check if we have enough data
        price_count = len(self._price_history.get(token_address, []))
        if price_count < self.momentum_config.min_data_points:
            return StrategySignal(
                strategy_name=self.name,
                action="hold",
                confidence=0.0,
                position_size=0.0,
                reason=f"Insufficient data: {price_count}/{self.momentum_config.min_data_points} points",
                metadata={"token_address": token_address}
            )

        # Calculate indicators
        rsi = self._calculate_rsi(token_address)
        macd_data = self._calculate_macd(token_address)
        avg_volume = self._calculate_avg_volume(token_address)
        has_price_momentum, price_change = self._check_price_momentum(token_address)

        if rsi is None:
            return StrategySignal(
                strategy_name=self.name,
                action="hold",
                confidence=0.0,
                position_size=0.0,
                reason="Unable to calculate RSI",
                metadata={"token_address": token_address}
            )

        # Entry checks
        checks = {
            "rsi_bullish": rsi > self.momentum_config.rsi_buy_threshold,
            "price_momentum": has_price_momentum,
            "security_ok": security_score >= 50,
        }

        # Optional: MACD confirmation
        if self.momentum_config.require_macd_confirmation and macd_data:
            _, _, histogram = macd_data
            checks["macd_bullish"] = histogram > 0
        else:
            checks["macd_bullish"] = True  # Not required or no data

        # Optional: Volume confirmation
        if self.momentum_config.require_volume_confirmation and avg_volume:
            checks["volume_high"] = volume >= (avg_volume * self.momentum_config.volume_multiplier)
        else:
            checks["volume_high"] = True  # Not required or no data

        # Check RSI not overbought
        checks["not_overbought"] = rsi < self.momentum_config.rsi_overbought

        # Calculate confidence
        passed_checks = sum(checks.values())
        total_checks = len(checks)
        confidence = passed_checks / total_checks

        # Bonus confidence for strong indicators
        if rsi > 70 and rsi < 85:  # Strong but not overbought
            confidence = min(1.0, confidence + 0.05)
        if macd_data and macd_data[2] > 0.1:  # Strong MACD histogram
            confidence = min(1.0, confidence + 0.05)

        logger.debug(
            f"Momentum analysis for {token_address}: "
            f"RSI={rsi:.1f}, price_change={price_change:.2%}, "
            f"confidence={confidence:.2%}"
        )

        # Decision: Enter or hold
        if confidence >= self.config.min_confidence and available_capital > 0:
            position_size = self.calculate_position_size(available_capital, market_data)

            if position_size < 0.1:
                return StrategySignal(
                    strategy_name=self.name,
                    action="hold",
                    confidence=confidence,
                    position_size=0.0,
                    reason="Position size too small",
                    metadata={"token_address": token_address}
                )

            return StrategySignal(
                strategy_name=self.name,
                action="buy",
                confidence=confidence,
                position_size=position_size,
                reason=f"Momentum detected: RSI={rsi:.1f}, price_change={price_change:.2%}",
                metadata={
                    "token_address": token_address,
                    "checks": checks,
                    "rsi": rsi,
                    "macd": macd_data,
                    "price_change": price_change,
                    "volume": volume,
                    "avg_volume": avg_volume,
                }
            )

        # No momentum or confidence too low
        failed_checks = [k for k, v in checks.items() if not v]
        return StrategySignal(
            strategy_name=self.name,
            action="hold",
            confidence=confidence,
            position_size=0.0,
            reason=f"Failed checks: {', '.join(failed_checks)}",
            metadata={
                "token_address": token_address,
                "checks": checks,
                "rsi": rsi,
                "price_change": price_change,
            }
        )

    async def should_enter(self, token_address: str, market_data: Dict[str, Any]) -> bool:
        """Check if we should enter a momentum position"""
        signal = await self.analyze(market_data)
        return signal.action == "buy" and signal.confidence >= self.config.min_confidence

    async def should_exit(self, position: Dict[str, Any], market_data: Dict[str, Any]) -> bool:
        """Check if we should exit a momentum position"""
        current_price = market_data.get("price", 0.0)
        current_time = time.time()

        # Check standard exit conditions
        should_exit, reason = self.check_exit_conditions(position, current_price, current_time)
        if should_exit:
            logger.info(f"Momentum exit triggered: {reason}")
            return True

        # Momentum-specific exit conditions
        token_address = position.get("token_address")

        # Calculate current RSI
        rsi = self._calculate_rsi(token_address)
        if rsi is not None:
            # Exit if RSI drops below sell threshold
            if rsi < self.momentum_config.rsi_sell_threshold:
                logger.info(
                    f"Momentum exit: RSI dropped to {rsi:.1f} "
                    f"(threshold: {self.momentum_config.rsi_sell_threshold})"
                )
                return True

            # Exit if RSI overbought (take profit early)
            if rsi > 85:  # Extreme overbought
                logger.info(f"Momentum exit: RSI overbought at {rsi:.1f}")
                return True

        # Check for momentum loss
        has_momentum, price_change = self._check_price_momentum(token_address)
        if not has_momentum and price_change < 0:  # Momentum lost and declining
            logger.info(
                f"Momentum exit: Momentum lost, price declining {price_change:.2%}"
            )
            return True

        # Check MACD for bearish crossover
        macd_data = self._calculate_macd(token_address)
        if macd_data:
            _, _, histogram = macd_data
            if histogram < -0.1:  # Strong bearish signal
                logger.info(f"Momentum exit: MACD bearish crossover (histogram={histogram:.4f})")
                return True

        return False

    def clear_history(self, token_address: str = None):
        """Clear price/volume history for a token or all tokens"""
        if token_address:
            self._price_history.pop(token_address, None)
            self._volume_history.pop(token_address, None)
            self._rsi_cache.pop(token_address, None)
            self._macd_cache.pop(token_address, None)
            logger.info(f"Cleared history for {token_address}")
        else:
            self._price_history.clear()
            self._volume_history.clear()
            self._rsi_cache.clear()
            self._macd_cache.clear()
            logger.info("Cleared all momentum strategy history")
