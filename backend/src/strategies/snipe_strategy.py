"""
Snipe Strategy - Fast entry on new token launches

Detects new token launches and enters quickly if criteria are met.
Ideal for catching early momentum on legitimate new tokens.
"""

from typing import Dict, Any, Set
from dataclasses import dataclass
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
class SnipeConfig(StrategyConfig):
    """Configuration specific to snipe strategy"""
    min_liquidity: float = 5.0  # Minimum liquidity in SOL
    max_slippage: float = 0.20  # Maximum acceptable slippage (20%)
    entry_speed: str = "fast"  # "instant", "fast", "normal"
    max_market_cap: float = 50000.0  # Maximum market cap in USD
    min_holder_count: int = 10  # Minimum number of holders
    max_token_age: int = 300  # Maximum age in seconds (5 minutes)
    min_security_score: int = 50  # Minimum security score (0-100)
    blacklist_creators: list = None  # List of creator addresses to avoid
    require_locked_liquidity: bool = False  # Require locked liquidity
    min_liquidity_lock_days: int = 7  # Minimum lock duration if required

    def __post_init__(self):
        if self.blacklist_creators is None:
            self.blacklist_creators = []


class SnipeStrategy(BaseStrategy):
    """
    Snipe Strategy - Fast entry on new token launches

    Entry Criteria:
    - Token age < max_token_age (default: 5 minutes)
    - Liquidity >= min_liquidity (default: 5 SOL)
    - Slippage <= max_slippage (default: 20%)
    - Market cap <= max_market_cap (default: $50k)
    - Holder count >= min_holder_count (default: 10)
    - Security score >= min_security_score (default: 50/100)
    - Creator not blacklisted
    - Optional: Liquidity locked

    Exit Criteria:
    - Standard: Take-profit, stop-loss, max hold time
    - Security degradation (score drops below 30)
    - Liquidity removed (>50% decrease)
    """

    def __init__(self, config: SnipeConfig = None):
        if config is None:
            config = SnipeConfig()

        super().__init__(config, StrategyType.SNIPE)
        self.snipe_config: SnipeConfig = config

        # Track tokens we've already evaluated to avoid re-sniping
        self._seen_tokens: Set[str] = set()

        # Track failed snipes (blacklist temporarily)
        self._failed_snipes: Dict[str, float] = {}  # token -> fail_time

        logger.info(
            f"SnipeStrategy initialized: "
            f"min_liquidity={config.min_liquidity} SOL, "
            f"max_slippage={config.max_slippage:.0%}, "
            f"max_age={config.max_token_age}s"
        )

    async def analyze(self, market_data: Dict[str, Any]) -> StrategySignal:
        """Analyze if token is snipe-worthy"""
        token_address = market_data.get("token_address", "unknown")

        # Check if we've already seen this token
        if token_address in self._seen_tokens:
            return StrategySignal(
                strategy_name=self.name,
                action="hold",
                confidence=0.0,
                position_size=0.0,
                reason="Token already evaluated",
                metadata={"token_address": token_address}
            )

        # Check if this token previously failed (cooldown: 1 hour)
        if token_address in self._failed_snipes:
            fail_time = self._failed_snipes[token_address]
            if time.time() - fail_time < 3600:  # 1 hour cooldown
                return StrategySignal(
                    strategy_name=self.name,
                    action="hold",
                    confidence=0.0,
                    position_size=0.0,
                    reason="Token in failed snipes cooldown",
                    metadata={"token_address": token_address}
                )
            else:
                # Cooldown expired, remove from failed list
                del self._failed_snipes[token_address]

        # Mark as seen
        self._seen_tokens.add(token_address)

        # Extract market data with safe defaults
        liquidity = market_data.get("liquidity_sol", 0.0)
        slippage = market_data.get("slippage", 1.0)
        token_age = market_data.get("age_seconds", float('inf'))
        market_cap = market_data.get("market_cap_usd", 0.0)
        holder_count = market_data.get("holder_count", 0)
        creator = market_data.get("creator", "")
        security_score = market_data.get("security_score", 0)
        available_capital = market_data.get("available_capital", 0.0)
        price = market_data.get("price", 0.0)

        # Additional checks
        liquidity_locked = market_data.get("liquidity_locked", False)
        liquidity_lock_days = market_data.get("liquidity_lock_days", 0)
        has_mint_authority = market_data.get("has_mint_authority", False)
        has_freeze_authority = market_data.get("has_freeze_authority", False)

        # Perform entry checks
        checks = {
            "new_token": token_age <= self.snipe_config.max_token_age,
            "sufficient_liquidity": liquidity >= self.snipe_config.min_liquidity,
            "acceptable_slippage": slippage <= self.snipe_config.max_slippage,
            "market_cap_ok": market_cap <= self.snipe_config.max_market_cap if market_cap > 0 else True,
            "holder_count_ok": holder_count >= self.snipe_config.min_holder_count,
            "creator_not_blacklisted": creator not in self.snipe_config.blacklist_creators,
            "security_ok": security_score >= self.snipe_config.min_security_score,
            "no_mint_authority": not has_mint_authority,  # Prefer tokens without mint authority
            "no_freeze_authority": not has_freeze_authority,  # Prefer tokens without freeze authority
        }

        # Optional: Liquidity lock check
        if self.snipe_config.require_locked_liquidity:
            checks["liquidity_locked"] = (
                liquidity_locked and
                liquidity_lock_days >= self.snipe_config.min_liquidity_lock_days
            )

        # Calculate confidence based on passed checks
        passed_checks = sum(checks.values())
        total_checks = len(checks)
        confidence = passed_checks / total_checks

        # Adjust confidence based on entry speed preference
        speed_multipliers = {
            "instant": 1.0,  # No adjustment, take any good opportunity
            "fast": 0.95,    # Slightly higher threshold
            "normal": 0.90   # Higher threshold, more selective
        }
        speed_multiplier = speed_multipliers.get(self.snipe_config.entry_speed, 1.0)
        required_confidence = self.config.min_confidence * speed_multiplier

        # Bonus confidence for extra-safe tokens
        if liquidity_locked and liquidity_lock_days >= 30:
            confidence = min(1.0, confidence + 0.05)  # +5% bonus
        if security_score >= 80:
            confidence = min(1.0, confidence + 0.05)  # +5% bonus

        # Log the analysis
        logger.debug(
            f"Snipe analysis for {token_address}: "
            f"{passed_checks}/{total_checks} checks passed, "
            f"confidence={confidence:.2%}"
        )

        # Decision: Enter or hold
        if confidence >= required_confidence and available_capital > 0:
            position_size = self.calculate_position_size(available_capital, market_data)

            if position_size < 0.1:  # Minimum viable position
                return StrategySignal(
                    strategy_name=self.name,
                    action="hold",
                    confidence=confidence,
                    position_size=0.0,
                    reason="Position size too small",
                    metadata={
                        "token_address": token_address,
                        "checks": checks,
                        "calculated_position": position_size
                    }
                )

            return StrategySignal(
                strategy_name=self.name,
                action="buy",
                confidence=confidence,
                position_size=position_size,
                reason=f"Snipe opportunity: {passed_checks}/{total_checks} checks passed",
                metadata={
                    "token_address": token_address,
                    "checks": checks,
                    "liquidity": liquidity,
                    "slippage": slippage,
                    "token_age": token_age,
                    "security_score": security_score,
                    "entry_speed": self.snipe_config.entry_speed,
                }
            )

        # Not a good snipe opportunity
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
                "failed_checks": failed_checks
            }
        )

    async def should_enter(self, token_address: str, market_data: Dict[str, Any]) -> bool:
        """Check if we should enter a snipe position"""
        signal = await self.analyze(market_data)
        return signal.action == "buy" and signal.confidence >= self.config.min_confidence

    async def should_exit(self, position: Dict[str, Any], market_data: Dict[str, Any]) -> bool:
        """Check if we should exit a snipe position"""
        current_price = market_data.get("price", 0.0)
        current_time = time.time()

        # Check standard exit conditions
        should_exit, reason = self.check_exit_conditions(position, current_price, current_time)
        if should_exit:
            logger.info(f"Snipe exit triggered: {reason}")
            return True

        # Snipe-specific exit conditions
        token_address = position.get("token_address")
        security_score = market_data.get("security_score", 100)
        liquidity = market_data.get("liquidity_sol", 0.0)
        initial_liquidity = position.get("initial_liquidity", liquidity)

        # Exit if security score drops significantly
        if security_score < 30:
            logger.warning(
                f"Snipe exit: Security score degraded to {security_score} "
                f"for {token_address}"
            )
            return True

        # Exit if liquidity removed (rug pull in progress)
        if initial_liquidity > 0:
            liquidity_change = (liquidity - initial_liquidity) / initial_liquidity
            if liquidity_change < -0.50:  # >50% liquidity removed
                logger.warning(
                    f"Snipe exit: Liquidity dropped {liquidity_change:.0%} "
                    f"for {token_address} (possible rug pull)"
                )
                return True

        # Exit if whale dump detected (large sell in recent blocks)
        whale_dump = market_data.get("whale_dump_detected", False)
        if whale_dump:
            logger.warning(f"Snipe exit: Whale dump detected for {token_address}")
            return True

        return False

    async def on_trade_enter(
        self,
        token_address: str,
        entry_price: float,
        amount: float,
        fees: float = 0.0
    ):
        """Called when snipe strategy enters a trade"""
        await super().on_trade_enter(token_address, entry_price, amount, fees)

        # Store entry metadata for exit decisions
        if not hasattr(self, '_position_metadata'):
            self._position_metadata = {}

        self._position_metadata[token_address] = {
            "entry_time": time.time(),
            "entry_price": entry_price,
            "amount": amount,
        }

    async def on_trade_exit(
        self,
        token_address: str,
        entry_price: float,
        exit_price: float,
        amount: float,
        hold_time: float,
        fees: float = 0.0
    ):
        """Called when snipe strategy exits a trade"""
        await super().on_trade_exit(
            token_address, entry_price, exit_price, amount, hold_time, fees
        )

        # Clean up metadata
        if hasattr(self, '_position_metadata') and token_address in self._position_metadata:
            del self._position_metadata[token_address]

        # If trade was a loss, add to failed snipes
        pnl_percent = (exit_price - entry_price) / entry_price
        if pnl_percent < -0.05:  # >5% loss
            self._failed_snipes[token_address] = time.time()
            logger.info(
                f"Added {token_address} to failed snipes list "
                f"(loss: {pnl_percent:.2%})"
            )

    def reset_seen_tokens(self):
        """Reset the seen tokens cache (useful for testing or new session)"""
        self._seen_tokens.clear()
        logger.info("Snipe strategy: Cleared seen tokens cache")

    def get_seen_tokens_count(self) -> int:
        """Get count of seen tokens"""
        return len(self._seen_tokens)

    def get_failed_snipes_count(self) -> int:
        """Get count of failed snipes in cooldown"""
        current_time = time.time()
        # Clean up expired cooldowns
        expired = [
            token for token, fail_time in self._failed_snipes.items()
            if current_time - fail_time >= 3600
        ]
        for token in expired:
            del self._failed_snipes[token]

        return len(self._failed_snipes)
