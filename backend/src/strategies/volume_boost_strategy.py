"""
Volume Boost Trading Strategy

Enters tokens with sudden volume spikes, indicating potential momentum or attention.
Focuses on high-volume tokens that may be experiencing organic growth or coordinated buying.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Deque
from collections import deque

from strategies.base_strategy import (
    BaseStrategy,
    StrategyType,
    StrategySignal,
    StrategyConfig,
)


@dataclass
class VolumeBoostConfig(StrategyConfig):
    """Configuration for Volume Boost Strategy."""

    # Volume requirements
    min_volume_1h: float = 50.0  # Minimum 1h volume in SOL
    min_volume_24h: float = 500.0  # Minimum 24h volume in SOL
    volume_spike_threshold: float = 3.0  # 3x normal volume

    # Entry criteria
    min_liquidity: float = 10.0  # Minimum liquidity in SOL
    max_slippage: float = 0.15  # 15% max slippage
    min_security_score: int = 60  # Minimum security score
    min_holder_count: int = 50  # Minimum unique holders

    # Volume analysis window
    volume_window_seconds: int = 300  # 5 minute window for spike detection
    min_data_points: int = 5  # Minimum data points for analysis

    # Risk management
    default_stop_loss: float = 0.15  # 15% stop loss
    default_take_profit: float = 0.30  # 30% take profit
    max_hold_time: int = 3600  # 1 hour max hold

    # Confidence weights
    volume_weight: float = 0.35
    liquidity_weight: float = 0.20
    security_weight: float = 0.25
    holder_weight: float = 0.20


class VolumeBoostStrategy(BaseStrategy):
    """
    Volume Boost Strategy - Trades on volume spikes.

    Entry Criteria:
    - High 1h/24h volume (>50 SOL / >500 SOL)
    - Volume spike detected (3x+ normal volume)
    - Sufficient liquidity (>10 SOL)
    - Low slippage (<15%)
    - Adequate security score (>60/100)
    - Minimum holder count (>50)

    Exit Criteria:
    - Take profit: +30%
    - Stop loss: -15%
    - Time-based: 1 hour max hold
    - Volume dies (drops below threshold)
    - Threat detected (rug pull, honeypot, etc.)
    """

    def __init__(self, config: Optional[VolumeBoostConfig] = None):
        """Initialize Volume Boost Strategy."""
        self.volume_config = config or VolumeBoostConfig()
        super().__init__(self.volume_config)
        self.strategy_type = StrategyType.VOLUME_BOOST

        # Volume tracking
        self.volume_history: Dict[str, Deque[tuple[float, float]]] = {}  # {token: deque[(timestamp, volume)]}
        self.processed_tokens: set[str] = set()  # Tokens we've already acted on

        # Performance tracking
        self.volume_spikes_detected = 0
        self.false_positives = 0  # Spikes that didn't lead to profits

    async def analyze(self, market_data: Dict[str, Any]) -> StrategySignal:
        """Analyze market data for volume boost opportunities."""
        token_address = market_data.get("token_address", "")

        # Skip if already processed
        if token_address in self.processed_tokens:
            return StrategySignal(
                strategy_name=self.strategy_type.value,
                action="hold",
                confidence=0.0,
                position_size=0.0,
                reason="Already processed this token",
                metadata={"status": "skipped"}
            )

        # Check if we should enter
        should_enter, entry_data = await self.should_enter(market_data)

        if should_enter:
            self.processed_tokens.add(token_address)
            self.volume_spikes_detected += 1

            return StrategySignal(
                strategy_name=self.strategy_type.value,
                action="buy",
                confidence=entry_data["confidence"],
                position_size=entry_data["position_size"],
                reason=entry_data["reason"],
                metadata=entry_data["checks"]
            )

        return StrategySignal(
            strategy_name=self.strategy_type.value,
            action="hold",
            confidence=0.0,
            position_size=0.0,
            reason="No volume boost opportunity detected",
            metadata={"status": "waiting"}
        )

    async def should_enter(self, market_data: Dict[str, Any]) -> tuple[bool, Dict[str, Any]]:
        """Determine if we should enter a position based on volume boost."""
        token_address = market_data.get("token_address", "")
        volume_1h = market_data.get("volume_1h", 0)
        volume_24h = market_data.get("volume_24h", 0)
        liquidity = market_data.get("liquidity_sol", 0)
        slippage = market_data.get("slippage", 1.0)
        security_score = market_data.get("security_score", 0)
        holder_count = market_data.get("holder_count", 0)
        available_capital = market_data.get("available_capital", 0)
        current_time = time.time()

        # Track volume history
        if token_address not in self.volume_history:
            self.volume_history[token_address] = deque(maxlen=20)

        self.volume_history[token_address].append((current_time, volume_1h))

        # Entry checks
        checks = {
            "high_1h_volume": volume_1h >= self.volume_config.min_volume_1h,
            "high_24h_volume": volume_24h >= self.volume_config.min_volume_24h,
            "volume_spike_detected": False,  # Will be calculated
            "sufficient_liquidity": liquidity >= self.volume_config.min_liquidity,
            "acceptable_slippage": slippage <= self.volume_config.max_slippage,
            "security_ok": security_score >= self.volume_config.min_security_score,
            "enough_holders": holder_count >= self.volume_config.min_holder_count,
            "capital_available": available_capital > 0,
        }

        # Detect volume spike
        if len(self.volume_history[token_address]) >= self.volume_config.min_data_points:
            recent_volumes = [v for _, v in self.volume_history[token_address]]
            avg_volume = sum(recent_volumes[:-1]) / len(recent_volumes[:-1])
            current_volume = recent_volumes[-1]

            if avg_volume > 0 and current_volume >= avg_volume * self.volume_config.volume_spike_threshold:
                checks["volume_spike_detected"] = True

        # Count passed checks
        passed_checks = sum(1 for v in checks.values() if v)
        total_checks = len(checks)

        # Calculate confidence based on weighted criteria
        confidence = 0.0

        if checks["volume_spike_detected"]:
            confidence += self.volume_config.volume_weight

        if checks["sufficient_liquidity"]:
            # Scale by liquidity amount
            liquidity_score = min(1.0, liquidity / 50.0)
            confidence += self.volume_config.liquidity_weight * liquidity_score

        if checks["security_ok"]:
            # Scale by security score
            security_score_normalized = security_score / 100.0
            confidence += self.volume_config.security_weight * security_score_normalized

        if checks["enough_holders"]:
            # Scale by holder count
            holder_score = min(1.0, holder_count / 200.0)
            confidence += self.volume_config.holder_weight * holder_score

        # Require minimum confidence
        if confidence < self.volume_config.min_confidence:
            return False, {}

        # Calculate position size
        position_size = self.calculate_position_size(available_capital, market_data)

        # Build entry reason
        volume_multiple = (volume_1h / (sum([v for _, v in self.volume_history[token_address]][:-1]) / len(self.volume_history[token_address]) - 1)) if len(self.volume_history[token_address]) > 1 else 0

        reason = (
            f"VOLUME BOOST: {volume_multiple:.1f}x spike detected. "
            f"1h vol: {volume_1h:.1f} SOL, 24h vol: {volume_24h:.1f} SOL. "
            f"Liq: {liquidity:.1f} SOL, Holders: {holder_count}. "
            f"Security: {security_score}/100. "
            f"{passed_checks}/{total_checks} checks passed."
        )

        entry_data = {
            "confidence": confidence,
            "position_size": position_size,
            "reason": reason,
            "checks": checks
        }

        return True, entry_data

    async def should_exit(self, market_data: Dict[str, Any], position_data: Dict[str, Any]) -> tuple[bool, str]:
        """Determine if we should exit a position."""
        token_address = market_data.get("token_address", "")
        current_price = market_data.get("price", 0)
        entry_price = position_data.get("entry_price", 0)
        entry_time = position_data.get("entry_time", time.time())
        hold_time = time.time() - entry_time

        volume_1h = market_data.get("volume_1h", 0)
        security_score = market_data.get("security_score", 100)

        # Calculate P&L
        if entry_price > 0:
            pnl_percent = (current_price - entry_price) / entry_price
        else:
            pnl_percent = 0

        # Exit condition 1: Take profit
        if pnl_percent >= self.volume_config.default_take_profit:
            return True, f"Take profit: +{pnl_percent*100:.1f}% (target: {self.volume_config.default_take_profit*100:.0f}%)"

        # Exit condition 2: Stop loss
        if pnl_percent <= -self.volume_config.default_stop_loss:
            self.false_positives += 1
            return True, f"Stop loss: {pnl_percent*100:.1f}% (limit: -{self.volume_config.default_stop_loss*100:.0f}%)"

        # Exit condition 3: Max hold time
        if hold_time >= self.volume_config.max_hold_time:
            return True, f"Max hold time reached: {hold_time/60:.0f} minutes (limit: {self.volume_config.max_hold_time/60:.0f} min)"

        # Exit condition 4: Volume died
        if volume_1h < self.volume_config.min_volume_1h * 0.5:  # Dropped below 50% of minimum
            return True, f"Volume died: {volume_1h:.1f} SOL/h (threshold: {self.volume_config.min_volume_1h * 0.5:.1f})"

        # Exit condition 5: Security degradation
        if security_score < 40:  # Critical security threshold
            return True, f"Security degraded: {security_score}/100 (critical threshold)"

        # Exit condition 6: Threat detection
        threat_detected = market_data.get("threats", {})
        critical_threats = [t for t in threat_detected.values() if t and t[0] == "critical"]
        if critical_threats:
            return True, f"Critical threat detected: {critical_threats[0][2].get('reason', 'Unknown')}"

        return False, ""

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get strategy performance statistics."""
        stats = super().get_performance_stats()

        # Add volume-specific stats
        stats["volume_spikes_detected"] = self.volume_spikes_detected
        stats["false_positives"] = self.false_positives
        stats["spike_accuracy"] = (
            (self.volume_spikes_detected - self.false_positives) / self.volume_spikes_detected
            if self.volume_spikes_detected > 0 else 0.0
        )
        stats["tokens_tracked"] = len(self.volume_history)

        return stats

    async def on_trade_enter(
        self,
        token_address: str,
        entry_price: float,
        position_size: float,
        confidence: float
    ):
        """Called when entering a trade."""
        await super().on_trade_enter(token_address, entry_price, position_size, confidence)

    async def on_trade_exit(
        self,
        token_address: str,
        entry_price: float,
        exit_price: float,
        position_size: float,
        hold_time: float,
        confidence: float
    ):
        """Called when exiting a trade."""
        await super().on_trade_exit(
            token_address,
            entry_price,
            exit_price,
            position_size,
            hold_time,
            confidence
        )

        # Remove from processed set after exit (allow re-entry after some time)
        # Keep in set to prevent immediate re-entry
