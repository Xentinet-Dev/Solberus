"""
Reversal Strategy - Buy on dips, sell on peaks

Mean reversion strategy that identifies oversold dips to buy and overbought peaks to sell.
Uses Bollinger Bands, RSI, and volume confirmation.
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from collections import deque
import time
import logging
import statistics

from .base_strategy import (
    BaseStrategy,
    StrategySignal,
    StrategyConfig,
    StrategyType
)

logger = logging.getLogger(__name__)


@dataclass
class ReversalConfig(StrategyConfig):
    """Configuration specific to reversal strategy"""
    # Dip detection
    dip_threshold: float = 0.15  # Buy after X% drop (default: -15%)
    dip_window: int = 5  # Minutes to detect dip
    min_dip_volume_spike: float = 1.5  # Volume must be 1.5x average during dip

    # Peak detection
    peak_threshold: float = 0.30  # Sell after X% rise from entry (default: +30%)
    peak_window: int = 10  # Minutes to detect peak
    min_peak_volume_spike: float = 2.0  # Volume spike at peak

    # Bollinger Bands
    bb_period: int = 20  # Period for moving average
    bb_std_dev: float = 2.0  # Standard deviations for bands
    bb_buy_threshold: float = 0.1  # Buy when price < lower_band + X% of band width
    bb_sell_threshold: float = 0.9  # Sell when price > lower_band + X% of band width

    # RSI settings
    rsi_period: int = 14
    rsi_oversold: float = 30.0  # Buy when RSI < this
    rsi_overbought: float = 70.0  # Sell when RSI > this

    # Support/Resistance
    use_support_resistance: bool = True
    sr_tolerance: float = 0.02  # 2% tolerance for support/resistance levels

    # Risk management
    max_dip_age: int = 300  # Only buy dips < 5 minutes old
    min_bounce_confirmation: float = 0.02  # Require 2% bounce from dip

    # Data requirements
    min_data_points: int = 20


class ReversalStrategy(BaseStrategy):
    """
    Reversal Strategy - Mean reversion trading

    Entry Criteria (Buy on Dips):
    - Price dropped > dip_threshold % in dip_window minutes
    - Volume spike during dip (> min_dip_volume_spike * avg)
    - Price below lower Bollinger Band
    - RSI < rsi_oversold (optional)
    - Near support level (optional)
    - Bounce confirmation (price recovering)

    Exit Criteria (Sell on Peaks):
    - Price reached peak_threshold % from entry
    - Price above upper Bollinger Band
    - RSI > rsi_overbought
    - Volume spike at peak
    - Standard: Stop-loss, take-profit, max hold time
    """

    def __init__(self, config: ReversalConfig = None):
        if config is None:
            config = ReversalConfig()

        super().__init__(config, StrategyType.REVERSAL)
        self.reversal_config: ReversalConfig = config

        # Price history: token_address -> deque of (timestamp, price, volume)
        self._price_history: Dict[str, deque] = {}

        # Support/Resistance levels: token_address -> {"support": [...], "resistance": [...]}
        self._sr_levels: Dict[str, Dict[str, List[float]]] = {}

        # Track detected dips: token_address -> (timestamp, dip_price, dip_percent)
        self._detected_dips: Dict[str, Tuple[float, float, float]] = {}

        logger.info(
            f"ReversalStrategy initialized: "
            f"dip_threshold={config.dip_threshold:.0%}, "
            f"peak_threshold={config.peak_threshold:.0%}, "
            f"RSI_oversold={config.rsi_oversold}"
        )

    def _update_price_history(self, token_address: str, price: float, volume: float, timestamp: float):
        """Update price and volume history"""
        if token_address not in self._price_history:
            self._price_history[token_address] = deque(maxlen=100)

        self._price_history[token_address].append((timestamp, price, volume))

    def _calculate_bollinger_bands(self, token_address: str) -> Optional[Tuple[float, float, float]]:
        """Calculate Bollinger Bands (middle, upper, lower)"""
        if token_address not in self._price_history:
            return None

        history = list(self._price_history[token_address])
        if len(history) < self.reversal_config.bb_period:
            return None

        # Get recent prices
        recent_prices = [p for _, p, _ in history[-self.reversal_config.bb_period:]]

        # Calculate middle band (SMA)
        middle_band = statistics.mean(recent_prices)

        # Calculate standard deviation
        std_dev = statistics.stdev(recent_prices)

        # Calculate upper and lower bands
        band_width = std_dev * self.reversal_config.bb_std_dev
        upper_band = middle_band + band_width
        lower_band = middle_band - band_width

        return (middle_band, upper_band, lower_band)

    def _calculate_rsi(self, token_address: str) -> Optional[float]:
        """Calculate RSI"""
        if token_address not in self._price_history:
            return None

        history = list(self._price_history[token_address])
        if len(history) < self.reversal_config.rsi_period + 1:
            return None

        prices = [p for _, p, _ in history]
        changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]

        gains = [max(0, change) for change in changes[-self.reversal_config.rsi_period:]]
        losses = [abs(min(0, change)) for change in changes[-self.reversal_config.rsi_period:]]

        avg_gain = sum(gains) / len(gains) if gains else 0
        avg_loss = sum(losses) / len(losses) if losses else 0

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _detect_dip(self, token_address: str, current_price: float, current_volume: float, current_time: float) -> Optional[Tuple[float, float]]:
        """Detect if there's a significant price dip"""
        if token_address not in self._price_history:
            return None

        history = list(self._price_history[token_address])
        if len(history) < 3:
            return None

        # Look for highest price in the dip_window
        window_seconds = self.reversal_config.dip_window * 60
        window_prices = [
            (ts, p, v) for ts, p, v in history
            if current_time - ts <= window_seconds
        ]

        if not window_prices:
            return None

        highest_price = max(p for _, p, _ in window_prices)
        avg_volume = statistics.mean([v for _, _, v in window_prices]) if window_prices else 0

        # Calculate dip percentage
        if highest_price == 0:
            return None

        dip_percent = (current_price - highest_price) / highest_price

        # Check if dip threshold met
        if dip_percent <= -abs(self.reversal_config.dip_threshold):
            # Check for volume spike
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0

            if volume_ratio >= self.reversal_config.min_dip_volume_spike:
                return (highest_price, dip_percent)

        return None

    def _check_bounce_confirmation(self, token_address: str, dip_price: float, current_price: float) -> bool:
        """Check if price is bouncing from the dip"""
        if dip_price == 0:
            return False

        bounce_percent = (current_price - dip_price) / dip_price
        return bounce_percent >= self.reversal_config.min_bounce_confirmation

    def _detect_peak(self, token_address: str, entry_price: float, current_price: float, current_volume: float) -> bool:
        """Detect if we're at a peak (time to exit)"""
        if entry_price == 0:
            return False

        # Calculate gain from entry
        gain_percent = (current_price - entry_price) / entry_price

        # Check if peak threshold reached
        if gain_percent >= self.reversal_config.peak_threshold:
            # Check for volume spike (suggests peak)
            if token_address in self._price_history:
                history = list(self._price_history[token_address])
                if len(history) > 10:
                    recent_volumes = [v for _, _, v in history[-10:]]
                    avg_volume = statistics.mean(recent_volumes)
                    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0

                    if volume_ratio >= self.reversal_config.min_peak_volume_spike:
                        return True

        return False

    def _find_support_levels(self, token_address: str) -> List[float]:
        """Identify support levels from price history"""
        if token_address not in self._price_history:
            return []

        history = list(self._price_history[token_address])
        if len(history) < 20:
            return []

        prices = [p for _, p, _ in history]

        # Find local minima (potential support)
        support_levels = []
        for i in range(1, len(prices) - 1):
            if prices[i] < prices[i-1] and prices[i] < prices[i+1]:
                # Local minimum found
                support_levels.append(prices[i])

        # Cluster similar support levels
        clustered = []
        for level in support_levels:
            # Check if similar to existing clustered level
            found = False
            for clustered_level in clustered:
                if abs(level - clustered_level) / clustered_level < 0.05:  # Within 5%
                    found = True
                    break
            if not found:
                clustered.append(level)

        return sorted(clustered)

    def _is_near_support(self, price: float, support_levels: List[float]) -> bool:
        """Check if price is near a support level"""
        if not support_levels:
            return False

        tolerance = self.reversal_config.sr_tolerance
        for level in support_levels:
            if abs(price - level) / level <= tolerance:
                return True

        return False

    async def analyze(self, market_data: Dict[str, Any]) -> StrategySignal:
        """Analyze for reversal opportunities (buy dips)"""
        token_address = market_data.get("token_address", "unknown")
        price = market_data.get("price", 0.0)
        volume = market_data.get("volume_1h", 0.0)
        timestamp = time.time()
        available_capital = market_data.get("available_capital", 0.0)
        security_score = market_data.get("security_score", 0)

        # Update price history
        self._update_price_history(token_address, price, volume, timestamp)

        # Check if we have enough data
        data_count = len(self._price_history.get(token_address, []))
        if data_count < self.reversal_config.min_data_points:
            return StrategySignal(
                strategy_name=self.name,
                action="hold",
                confidence=0.0,
                position_size=0.0,
                reason=f"Insufficient data: {data_count}/{self.reversal_config.min_data_points}",
                metadata={"token_address": token_address}
            )

        # Detect dip
        dip_info = self._detect_dip(token_address, price, volume, timestamp)
        if dip_info is None:
            return StrategySignal(
                strategy_name=self.name,
                action="hold",
                confidence=0.0,
                position_size=0.0,
                reason="No dip detected",
                metadata={"token_address": token_address}
            )

        highest_price, dip_percent = dip_info

        # Store detected dip
        self._detected_dips[token_address] = (timestamp, price, dip_percent)

        # Calculate indicators
        bb_data = self._calculate_bollinger_bands(token_address)
        rsi = self._calculate_rsi(token_address)
        support_levels = self._find_support_levels(token_address) if self.reversal_config.use_support_resistance else []

        # Entry checks
        checks = {
            "dip_detected": True,  # Already confirmed above
            "dip_recent": True,  # Dip is happening now
            "security_ok": security_score >= 50,
        }

        # Check bounce confirmation
        checks["bounce_confirmed"] = self._check_bounce_confirmation(token_address, price, price)

        # Check Bollinger Bands
        if bb_data:
            middle, upper, lower = bb_data
            band_width = upper - lower
            price_position = (price - lower) / band_width if band_width > 0 else 0.5
            checks["below_bb"] = price_position < self.reversal_config.bb_buy_threshold
        else:
            checks["below_bb"] = True  # Assume OK if no data

        # Check RSI
        if rsi is not None:
            checks["rsi_oversold"] = rsi < self.reversal_config.rsi_oversold
        else:
            checks["rsi_oversold"] = True  # Assume OK if no data

        # Check support level
        if self.reversal_config.use_support_resistance and support_levels:
            checks["near_support"] = self._is_near_support(price, support_levels)
        else:
            checks["near_support"] = True  # Not required or no data

        # Calculate confidence
        passed_checks = sum(checks.values())
        total_checks = len(checks)
        confidence = passed_checks / total_checks

        # Bonus confidence for strong dips
        if abs(dip_percent) > 0.20:  # >20% dip
            confidence = min(1.0, confidence + 0.10)
        if rsi and rsi < 25:  # Very oversold
            confidence = min(1.0, confidence + 0.05)

        logger.debug(
            f"Reversal analysis for {token_address}: "
            f"dip={dip_percent:.2%}, RSI={rsi}, "
            f"confidence={confidence:.2%}"
        )

        # Decision: Buy the dip or hold
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
                reason=f"Dip detected: {dip_percent:.2%} drop, RSI={rsi:.1f if rsi else 'N/A'}",
                metadata={
                    "token_address": token_address,
                    "checks": checks,
                    "dip_percent": dip_percent,
                    "highest_price": highest_price,
                    "rsi": rsi,
                    "bollinger_bands": bb_data,
                    "support_levels": support_levels,
                }
            )

        # Not a good reversal opportunity
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
                "dip_percent": dip_percent,
            }
        )

    async def should_enter(self, token_address: str, market_data: Dict[str, Any]) -> bool:
        """Check if we should enter on a dip"""
        signal = await self.analyze(market_data)
        return signal.action == "buy" and signal.confidence >= self.config.min_confidence

    async def should_exit(self, position: Dict[str, Any], market_data: Dict[str, Any]) -> bool:
        """Check if we should exit at a peak"""
        current_price = market_data.get("price", 0.0)
        current_time = time.time()
        current_volume = market_data.get("volume_1h", 0.0)

        # Check standard exit conditions
        should_exit, reason = self.check_exit_conditions(position, current_price, current_time)
        if should_exit:
            logger.info(f"Reversal exit triggered: {reason}")
            return True

        # Reversal-specific exit conditions
        token_address = position.get("token_address")
        entry_price = position.get("entry_price", 0.0)

        # Check for peak
        if self._detect_peak(token_address, entry_price, current_price, current_volume):
            logger.info(f"Reversal exit: Peak detected for {token_address}")
            return True

        # Check Bollinger Bands (exit if near upper band)
        bb_data = self._calculate_bollinger_bands(token_address)
        if bb_data:
            middle, upper, lower = bb_data
            band_width = upper - lower
            if band_width > 0:
                price_position = (current_price - lower) / band_width
                if price_position > self.reversal_config.bb_sell_threshold:
                    logger.info(
                        f"Reversal exit: Price at {price_position:.0%} of Bollinger Band width"
                    )
                    return True

        # Check RSI (exit if overbought)
        rsi = self._calculate_rsi(token_address)
        if rsi and rsi > self.reversal_config.rsi_overbought:
            logger.info(f"Reversal exit: RSI overbought at {rsi:.1f}")
            return True

        return False

    def clear_history(self, token_address: str = None):
        """Clear price history for a token or all tokens"""
        if token_address:
            self._price_history.pop(token_address, None)
            self._sr_levels.pop(token_address, None)
            self._detected_dips.pop(token_address, None)
            logger.info(f"Cleared history for {token_address}")
        else:
            self._price_history.clear()
            self._sr_levels.clear()
            self._detected_dips.clear()
            logger.info("Cleared all reversal strategy history")
