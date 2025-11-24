"""
Whale Copy Strategy - Copy trades from successful whale wallets

Monitors successful wallets and copies their trading patterns.
Ideal for following smart money and proven traders.
"""

from typing import Dict, Any, List, Set, Optional
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
class WhaleCopyConfig(StrategyConfig):
    """Configuration specific to whale copy strategy"""
    # Whale criteria
    min_whale_balance: float = 100.0  # Minimum wallet balance in SOL
    min_whale_success_rate: float = 0.70  # 70% win rate minimum
    min_whale_trades: int = 20  # Minimum trades to be considered
    min_whale_profit: float = 10.0  # Minimum total profit in SOL

    # Copy settings
    copy_delay: int = 0  # Seconds to wait before copying (0 = instant)
    max_copy_delay: int = 60  # Don't copy if trade is older than this
    copy_position_ratio: float = 0.10  # Copy 10% of whale's position size
    min_copy_amount: float = 0.5  # Minimum SOL to copy
    max_copy_amount: float = 5.0  # Maximum SOL to copy per trade

    # Whale tracking
    whale_whitelist: List[str] = None  # Specific whales to copy (optional)
    whale_blacklist: List[str] = None  # Whales to ignore
    max_tracked_whales: int = 100  # Maximum whales to track
    whale_rescore_interval: int = 3600  # Re-evaluate whales every hour

    # Exit strategy
    follow_whale_exits: bool = True  # Exit when whale exits
    use_independent_exits: bool = True  # Use own stop-loss/take-profit
    max_hold_multiplier: float = 2.0  # Hold at most 2x whale's hold time

    def __post_init__(self):
        if self.whale_whitelist is None:
            self.whale_whitelist = []
        if self.whale_blacklist is None:
            self.whale_blacklist = []


@dataclass
class WhaleTradeInfo:
    """Information about a whale's trade"""
    whale_address: str
    token_address: str
    action: str  # "buy" or "sell"
    amount: float  # SOL amount
    price: float
    timestamp: float
    whale_success_rate: float
    whale_recent_performance: float  # Recent win rate (last 10 trades)


class WhaleCopyStrategy(BaseStrategy):
    """
    Whale Copy Strategy - Follow successful traders

    Entry Criteria:
    - Whale makes a buy transaction
    - Whale meets minimum criteria (balance, success rate, trade count)
    - Trade is recent (< max_copy_delay)
    - Token passes basic security checks
    - Not in whale blacklist

    Exit Criteria:
    - Whale exits position (if follow_whale_exits=True)
    - Standard: Stop-loss, take-profit, max hold time
    - Max hold time based on whale's typical hold duration
    """

    def __init__(self, config: WhaleCopyConfig = None):
        if config is None:
            config = WhaleCopyConfig()

        super().__init__(config, StrategyType.WHALE_COPY)
        self.whale_config: WhaleCopyConfig = config

        # Tracked whales: address -> whale_info
        self._tracked_whales: Dict[str, Dict[str, Any]] = {}

        # Whale scores: address -> score (0-100)
        self._whale_scores: Dict[str, float] = {}

        # Last whale rescore time
        self._last_rescore: float = 0

        # Copied trades: token_address -> whale_trade_info
        self._copied_trades: Dict[str, WhaleTradeInfo] = {}

        # Whale trade history for scoring: whale_address -> list of trades
        self._whale_history: Dict[str, List[Dict[str, Any]]] = {}

        logger.info(
            f"WhaleCopyStrategy initialized: "
            f"min_success_rate={config.min_whale_success_rate:.0%}, "
            f"copy_ratio={config.copy_position_ratio:.0%}, "
            f"copy_delay={config.copy_delay}s"
        )

    def _is_whale_qualified(self, whale_info: Dict[str, Any]) -> bool:
        """Check if whale meets minimum criteria"""
        balance = whale_info.get("balance", 0.0)
        success_rate = whale_info.get("success_rate", 0.0)
        total_trades = whale_info.get("total_trades", 0)
        total_profit = whale_info.get("total_profit", 0.0)
        address = whale_info.get("address", "")

        # Check whitelist
        if self.whale_config.whale_whitelist and address not in self.whale_config.whale_whitelist:
            return False

        # Check blacklist
        if address in self.whale_config.whale_blacklist:
            return False

        # Check minimum criteria
        checks = {
            "balance": balance >= self.whale_config.min_whale_balance,
            "success_rate": success_rate >= self.whale_config.min_whale_success_rate,
            "trades": total_trades >= self.whale_config.min_whale_trades,
            "profit": total_profit >= self.whale_config.min_whale_profit,
        }

        return all(checks.values())

    def _calculate_whale_score(self, whale_info: Dict[str, Any]) -> float:
        """Calculate a composite score for a whale (0-100)"""
        success_rate = whale_info.get("success_rate", 0.0)
        recent_success_rate = whale_info.get("recent_success_rate", success_rate)
        total_profit = whale_info.get("total_profit", 0.0)
        avg_profit_per_trade = whale_info.get("avg_profit_per_trade", 0.0)
        consistency = whale_info.get("consistency", 0.5)  # 0-1, how consistent returns are

        # Weighted scoring
        score = (
            success_rate * 30 +  # 30% weight on overall success rate
            recent_success_rate * 35 +  # 35% weight on recent performance
            min(total_profit / 100.0, 1.0) * 15 +  # 15% weight on total profit
            min(avg_profit_per_trade / 5.0, 1.0) * 10 +  # 10% weight on avg profit
            consistency * 10  # 10% weight on consistency
        )

        return min(100.0, score)

    def _rescore_whales(self):
        """Rescore all tracked whales"""
        current_time = time.time()

        if current_time - self._last_rescore < self.whale_config.whale_rescore_interval:
            return  # Too soon to rescore

        logger.info(f"Rescoring {len(self._tracked_whales)} tracked whales...")

        for address, whale_info in self._tracked_whales.items():
            if self._is_whale_qualified(whale_info):
                score = self._calculate_whale_score(whale_info)
                self._whale_scores[address] = score
            else:
                # Whale no longer qualified, remove
                self._whale_scores.pop(address, None)
                logger.info(f"Whale {address} no longer qualified, removed from tracking")

        self._last_rescore = current_time

        # Keep only top whales if we exceed max
        if len(self._whale_scores) > self.whale_config.max_tracked_whales:
            # Sort by score and keep top N
            sorted_whales = sorted(
                self._whale_scores.items(),
                key=lambda x: x[1],
                reverse=True
            )
            self._whale_scores = dict(sorted_whales[:self.whale_config.max_tracked_whales])

    def register_whale(self, whale_info: Dict[str, Any]):
        """Register a whale for tracking"""
        address = whale_info.get("address")
        if not address:
            return

        if self._is_whale_qualified(whale_info):
            self._tracked_whales[address] = whale_info
            score = self._calculate_whale_score(whale_info)
            self._whale_scores[address] = score
            logger.info(f"Registered whale {address} with score {score:.1f}")

    async def analyze(self, market_data: Dict[str, Any]) -> StrategySignal:
        """Analyze whale trade and decide whether to copy"""
        # Rescore whales if needed
        self._rescore_whales()

        # Extract whale trade information
        whale_trade = market_data.get("whale_trade")
        if not whale_trade:
            return StrategySignal(
                strategy_name=self.name,
                action="hold",
                confidence=0.0,
                position_size=0.0,
                reason="No whale trade detected",
                metadata={}
            )

        whale_address = whale_trade.get("whale_address", "")
        token_address = whale_trade.get("token_address", "")
        action = whale_trade.get("action", "")
        whale_amount = whale_trade.get("amount", 0.0)
        trade_timestamp = whale_trade.get("timestamp", time.time())
        price = whale_trade.get("price", 0.0)

        # Only copy buy actions (sells are handled in exit logic)
        if action != "buy":
            return StrategySignal(
                strategy_name=self.name,
                action="hold",
                confidence=0.0,
                position_size=0.0,
                reason="Not a buy action",
                metadata={"whale_address": whale_address}
            )

        # Check if whale is tracked and qualified
        if whale_address not in self._whale_scores:
            return StrategySignal(
                strategy_name=self.name,
                action="hold",
                confidence=0.0,
                position_size=0.0,
                reason="Whale not tracked or not qualified",
                metadata={"whale_address": whale_address}
            )

        whale_score = self._whale_scores[whale_address]
        whale_info = self._tracked_whales.get(whale_address, {})

        # Check trade freshness
        trade_age = time.time() - trade_timestamp
        if trade_age > self.whale_config.max_copy_delay:
            return StrategySignal(
                strategy_name=self.name,
                action="hold",
                confidence=0.0,
                position_size=0.0,
                reason=f"Trade too old ({trade_age:.0f}s > {self.whale_config.max_copy_delay}s)",
                metadata={"whale_address": whale_address}
            )

        # Wait for copy delay if configured
        if self.whale_config.copy_delay > 0:
            await asyncio.sleep(self.whale_config.copy_delay)

        # Extract additional data
        available_capital = market_data.get("available_capital", 0.0)
        security_score = market_data.get("security_score", 0)

        # Entry checks
        checks = {
            "whale_qualified": True,  # Already checked above
            "trade_fresh": True,  # Already checked above
            "security_ok": security_score >= 40,  # More lenient, trust the whale
            "whale_score_good": whale_score >= 50,
        }

        # Calculate confidence based on whale score
        confidence = whale_score / 100.0

        # Adjust confidence based on whale's recent performance
        recent_success_rate = whale_info.get("recent_success_rate", 0.7)
        if recent_success_rate > 0.80:
            confidence = min(1.0, confidence + 0.10)
        elif recent_success_rate < 0.60:
            confidence = max(0.0, confidence - 0.10)

        # Calculate position size
        copy_amount = whale_amount * self.whale_config.copy_position_ratio
        copy_amount = max(self.whale_config.min_copy_amount, copy_amount)
        copy_amount = min(self.whale_config.max_copy_amount, copy_amount)

        # Apply capital limits
        if copy_amount > available_capital:
            copy_amount = available_capital

        if copy_amount < self.whale_config.min_copy_amount:
            return StrategySignal(
                strategy_name=self.name,
                action="hold",
                confidence=confidence,
                position_size=0.0,
                reason="Insufficient capital to copy",
                metadata={"whale_address": whale_address, "required": self.whale_config.min_copy_amount}
            )

        # Decision: Copy the trade
        logger.info(
            f"Copying whale {whale_address} trade: "
            f"{copy_amount:.4f} SOL of {token_address} "
            f"(whale score: {whale_score:.1f}, confidence: {confidence:.0%})"
        )

        # Store copied trade info
        self._copied_trades[token_address] = WhaleTradeInfo(
            whale_address=whale_address,
            token_address=token_address,
            action="buy",
            amount=copy_amount,
            price=price,
            timestamp=time.time(),
            whale_success_rate=whale_info.get("success_rate", 0.0),
            whale_recent_performance=recent_success_rate,
        )

        return StrategySignal(
            strategy_name=self.name,
            action="buy",
            confidence=confidence,
            position_size=copy_amount,
            reason=f"Copying whale {whale_address[:8]}... (score: {whale_score:.1f})",
            metadata={
                "whale_address": whale_address,
                "whale_score": whale_score,
                "whale_amount": whale_amount,
                "copy_ratio": self.whale_config.copy_position_ratio,
                "trade_age": trade_age,
                "whale_success_rate": whale_info.get("success_rate"),
                "recent_success_rate": recent_success_rate,
            }
        )

    async def should_enter(self, token_address: str, market_data: Dict[str, Any]) -> bool:
        """Check if we should copy a whale's entry"""
        signal = await self.analyze(market_data)
        return signal.action == "buy" and signal.confidence >= self.config.min_confidence

    async def should_exit(self, position: Dict[str, Any], market_data: Dict[str, Any]) -> bool:
        """Check if we should exit a copied position"""
        current_price = market_data.get("price", 0.0)
        current_time = time.time()
        token_address = position.get("token_address")

        # Check standard exit conditions
        should_exit, reason = self.check_exit_conditions(position, current_price, current_time)
        if should_exit and self.whale_config.use_independent_exits:
            logger.info(f"Whale copy exit triggered: {reason}")
            return True

        # Check if whale has exited
        if self.whale_config.follow_whale_exits:
            whale_exit = market_data.get("whale_exit")
            if whale_exit:
                whale_address = whale_exit.get("whale_address")
                exit_token = whale_exit.get("token_address")

                # Check if this is our copied trade
                copied_trade = self._copied_trades.get(token_address)
                if copied_trade and copied_trade.whale_address == whale_address and exit_token == token_address:
                    logger.info(f"Whale copy exit: Whale {whale_address[:8]}... exited {token_address}")
                    return True

        # Check max hold time based on whale's behavior
        if token_address in self._copied_trades:
            copied_trade = self._copied_trades[token_address]
            whale_info = self._tracked_whales.get(copied_trade.whale_address, {})
            whale_avg_hold_time = whale_info.get("avg_hold_time", self.config.max_hold_time)

            max_hold = whale_avg_hold_time * self.whale_config.max_hold_multiplier
            entry_time = position.get("entry_time", current_time)
            hold_time = current_time - entry_time

            if hold_time >= max_hold:
                logger.info(
                    f"Whale copy exit: Exceeded max hold time "
                    f"({hold_time:.0f}s > {max_hold:.0f}s)"
                )
                return True

        return False

    def get_tracked_whales(self) -> Dict[str, float]:
        """Get all tracked whales with their scores"""
        return self._whale_scores.copy()

    def get_top_whales(self, count: int = 10) -> List[tuple]:
        """Get top N whales by score"""
        sorted_whales = sorted(
            self._whale_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_whales[:count]

    def clear_history(self):
        """Clear all whale tracking history"""
        self._tracked_whales.clear()
        self._whale_scores.clear()
        self._copied_trades.clear()
        self._whale_history.clear()
        logger.info("Cleared all whale copy strategy history")
