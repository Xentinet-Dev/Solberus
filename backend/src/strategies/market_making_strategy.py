"""
Market Making Trading Strategy

Provides liquidity by placing buy and sell orders with a spread.
Profits from bid-ask spread while maintaining balanced inventory.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

from strategies.base_strategy import (
    BaseStrategy,
    StrategyType,
    StrategySignal,
    StrategyConfig,
)


@dataclass
class MarketMakingConfig(StrategyConfig):
    """Configuration for Market Making Strategy."""

    # Spread configuration
    spread_percentage: float = 0.02  # 2% spread (1% on each side)
    min_spread: float = 0.005  # 0.5% minimum spread
    max_spread: float = 0.10  # 10% maximum spread

    # Inventory management
    target_sol_ratio: float = 0.5  # 50% SOL, 50% tokens
    rebalance_threshold: float = 0.1  # Rebalance if ratio deviates by 10%
    max_inventory_imbalance: float = 0.3  # Max 30% imbalance

    # Trading parameters
    min_liquidity: float = 15.0  # Minimum liquidity in SOL
    max_trade_size_sol: float = 0.5  # Maximum order size
    min_trade_size_sol: float = 0.05  # Minimum order size
    max_slippage: float = 0.02  # 2% max slippage

    # Market conditions
    min_volume_24h: float = 100.0  # Minimum 24h volume
    min_security_score: int = 70  # Minimum security score
    min_holder_count: int = 100  # Minimum unique holders

    # Risk management
    max_position_size_sol: float = 5.0  # Maximum total position
    stop_loss_percentage: float = 0.15  # 15% stop loss
    volatility_threshold: float = 0.30  # Pause if volatility >30%

    # Timing
    rebalance_interval: int = 300  # Rebalance every 5 minutes
    quote_update_interval: int = 60  # Update quotes every minute

    # Confidence weights
    liquidity_weight: float = 0.30
    volume_weight: float = 0.25
    security_weight: float = 0.25
    holder_weight: float = 0.20


class MarketMakingStrategy(BaseStrategy):
    """
    Market Making Strategy - Provides liquidity with spread.

    Entry Criteria:
    - Sufficient liquidity (>15 SOL)
    - Adequate 24h volume (>100 SOL)
    - Good security score (>70/100)
    - Minimum holders (>100)
    - Low volatility (<30%)

    Operation:
    - Places buy orders below market price
    - Places sell orders above market price
    - Maintains balanced inventory
    - Rebalances when inventory imbalanced
    - Adjusts spread based on volatility

    Exit Criteria:
    - Stop loss: -15%
    - Security degradation
    - Liquidity drain
    - High volatility (>30%)
    - Threat detected
    """

    def __init__(self, config: Optional[MarketMakingConfig] = None):
        """Initialize Market Making Strategy."""
        self.mm_config = config or MarketMakingConfig()
        super().__init__(self.mm_config)
        self.strategy_type = StrategyType.MARKET_MAKING

        # Inventory tracking
        self.inventory_sol: Dict[str, float] = {}  # {token: SOL amount}
        self.inventory_tokens: Dict[str, float] = {}  # {token: token amount}
        self.last_rebalance: Dict[str, float] = {}  # {token: timestamp}

        # Quote tracking
        self.active_quotes: Dict[str, Dict[str, Any]] = {}  # {token: {bid, ask, timestamp}}
        self.last_quote_update: Dict[str, float] = {}  # {token: timestamp}

        # Performance tracking
        self.total_spread_profit = 0.0
        self.rebalances_performed = 0
        self.inventory_imbalances = 0

    async def analyze(self, market_data: Dict[str, Any]) -> StrategySignal:
        """Analyze market data for market making opportunities."""
        token_address = market_data.get("token_address", "")
        current_time = time.time()

        # Check if market is suitable for market making
        should_make_market, mm_data = await self.should_enter(market_data)

        if not should_make_market:
            return StrategySignal(
                strategy_name=self.strategy_type.value,
                action="hold",
                confidence=0.0,
                position_size=0.0,
                reason="Market conditions not suitable for market making",
                metadata={"status": "not_suitable"}
            )

        # Check if we need to rebalance
        needs_rebalance = await self._check_rebalance_needed(token_address, market_data)

        if needs_rebalance:
            return StrategySignal(
                strategy_name=self.strategy_type.value,
                action="rebalance",
                confidence=mm_data["confidence"],
                position_size=mm_data["position_size"],
                reason="Inventory imbalance detected - rebalancing",
                metadata={"type": "rebalance", "checks": mm_data["checks"]}
            )

        # Update quotes if needed
        if (token_address not in self.last_quote_update or
            current_time - self.last_quote_update[token_address] >= self.mm_config.quote_update_interval):

            bid_price, ask_price = self._calculate_quotes(market_data)
            self.active_quotes[token_address] = {
                "bid": bid_price,
                "ask": ask_price,
                "spread": ask_price - bid_price,
                "timestamp": current_time
            }
            self.last_quote_update[token_address] = current_time

            return StrategySignal(
                strategy_name=self.strategy_type.value,
                action="update_quotes",
                confidence=mm_data["confidence"],
                position_size=mm_data["position_size"],
                reason=f"Updated quotes: Bid {bid_price:.8f}, Ask {ask_price:.8f}",
                metadata={
                    "bid": bid_price,
                    "ask": ask_price,
                    "spread_pct": (ask_price - bid_price) / bid_price * 100
                }
            )

        return StrategySignal(
            strategy_name=self.strategy_type.value,
            action="hold",
            confidence=mm_data["confidence"],
            position_size=0.0,
            reason="Market making active - waiting for orders",
            metadata={"status": "active", "quotes": self.active_quotes.get(token_address, {})}
        )

    async def should_enter(self, market_data: Dict[str, Any]) -> tuple[bool, Dict[str, Any]]:
        """Determine if market conditions are suitable for market making."""
        liquidity = market_data.get("liquidity_sol", 0)
        volume_24h = market_data.get("volume_24h", 0)
        security_score = market_data.get("security_score", 0)
        holder_count = market_data.get("holder_count", 0)
        available_capital = market_data.get("available_capital", 0)
        slippage = market_data.get("slippage", 1.0)

        # Calculate volatility if price history available
        price_history = market_data.get("price_history", [])
        volatility = self._calculate_volatility(price_history) if price_history else 0.0

        # Entry checks
        checks = {
            "sufficient_liquidity": liquidity >= self.mm_config.min_liquidity,
            "adequate_volume": volume_24h >= self.mm_config.min_volume_24h,
            "security_ok": security_score >= self.mm_config.min_security_score,
            "enough_holders": holder_count >= self.mm_config.min_holder_count,
            "low_volatility": volatility <= self.mm_config.volatility_threshold,
            "acceptable_slippage": slippage <= self.mm_config.max_slippage,
            "capital_available": available_capital >= self.mm_config.min_trade_size_sol * 2,  # Need capital for both sides
        }

        # Count passed checks
        passed_checks = sum(1 for v in checks.values() if v)
        total_checks = len(checks)

        # Calculate confidence
        confidence = 0.0

        if checks["sufficient_liquidity"]:
            liquidity_score = min(1.0, liquidity / 50.0)
            confidence += self.mm_config.liquidity_weight * liquidity_score

        if checks["adequate_volume"]:
            volume_score = min(1.0, volume_24h / 500.0)
            confidence += self.mm_config.volume_weight * volume_score

        if checks["security_ok"]:
            security_score_normalized = security_score / 100.0
            confidence += self.mm_config.security_weight * security_score_normalized

        if checks["enough_holders"]:
            holder_score = min(1.0, holder_count / 300.0)
            confidence += self.mm_config.holder_weight * holder_score

        # Require minimum confidence
        if confidence < self.mm_config.min_confidence:
            return False, {}

        # Calculate initial position size
        position_size = min(
            available_capital * 0.3,  # Use 30% of capital
            self.mm_config.max_trade_size_sol
        )

        reason = (
            f"MARKET MAKING: Suitable conditions. "
            f"Liq: {liquidity:.1f} SOL, Vol: {volume_24h:.1f} SOL, "
            f"Security: {security_score}/100, Holders: {holder_count}. "
            f"Volatility: {volatility*100:.1f}%. "
            f"{passed_checks}/{total_checks} checks passed."
        )

        mm_data = {
            "confidence": confidence,
            "position_size": position_size,
            "reason": reason,
            "checks": checks,
            "volatility": volatility
        }

        return True, mm_data

    async def should_exit(self, market_data: Dict[str, Any], position_data: Dict[str, Any]) -> tuple[bool, str]:
        """Determine if we should exit market making position."""
        token_address = market_data.get("token_address", "")
        current_price = market_data.get("price", 0)
        entry_price = position_data.get("entry_price", 0)
        liquidity = market_data.get("liquidity_sol", 0)
        security_score = market_data.get("security_score", 100)
        price_history = market_data.get("price_history", [])

        # Calculate P&L
        if entry_price > 0:
            pnl_percent = (current_price - entry_price) / entry_price
        else:
            pnl_percent = 0

        # Calculate current volatility
        volatility = self._calculate_volatility(price_history) if price_history else 0.0

        # Exit condition 1: Stop loss
        if pnl_percent <= -self.mm_config.stop_loss_percentage:
            return True, f"Stop loss: {pnl_percent*100:.1f}% (limit: -{self.mm_config.stop_loss_percentage*100:.0f}%)"

        # Exit condition 2: High volatility
        if volatility > self.mm_config.volatility_threshold:
            return True, f"High volatility: {volatility*100:.1f}% (threshold: {self.mm_config.volatility_threshold*100:.0f}%)"

        # Exit condition 3: Liquidity drain
        if liquidity < self.mm_config.min_liquidity * 0.5:
            return True, f"Liquidity drain: {liquidity:.1f} SOL (threshold: {self.mm_config.min_liquidity * 0.5:.1f})"

        # Exit condition 4: Security degradation
        if security_score < 40:
            return True, f"Security degraded: {security_score}/100"

        # Exit condition 5: Threat detection
        threat_detected = market_data.get("threats", {})
        critical_threats = [t for t in threat_detected.values() if t and t[0] == "critical"]
        if critical_threats:
            return True, f"Critical threat: {critical_threats[0][2].get('reason', 'Unknown')}"

        return False, ""

    async def _check_rebalance_needed(self, token_address: str, market_data: Dict[str, Any]) -> bool:
        """Check if inventory needs rebalancing."""
        current_time = time.time()

        # Check rebalance interval
        if token_address in self.last_rebalance:
            if current_time - self.last_rebalance[token_address] < self.mm_config.rebalance_interval:
                return False

        # Calculate inventory ratio
        sol_value = self.inventory_sol.get(token_address, 0)
        token_value = self.inventory_tokens.get(token_address, 0) * market_data.get("price", 0)
        total_value = sol_value + token_value

        if total_value == 0:
            return False

        current_ratio = sol_value / total_value
        target_ratio = self.mm_config.target_sol_ratio

        # Check if rebalance needed
        if abs(current_ratio - target_ratio) > self.mm_config.rebalance_threshold:
            self.last_rebalance[token_address] = current_time
            self.rebalances_performed += 1
            self.inventory_imbalances += 1
            return True

        return False

    def _calculate_quotes(self, market_data: Dict[str, Any]) -> tuple[float, float]:
        """Calculate bid and ask prices with spread."""
        current_price = market_data.get("price", 0)
        price_history = market_data.get("price_history", [])

        # Calculate volatility-adjusted spread
        volatility = self._calculate_volatility(price_history) if price_history else 0.0
        spread = self.mm_config.spread_percentage

        # Increase spread in high volatility
        if volatility > 0.15:  # 15% volatility
            spread *= 1 + (volatility - 0.15) * 2  # Increase spread proportionally

        # Ensure spread within bounds
        spread = max(self.mm_config.min_spread, min(spread, self.mm_config.max_spread))

        # Calculate bid/ask
        bid_price = current_price * (1 - spread / 2)
        ask_price = current_price * (1 + spread / 2)

        return bid_price, ask_price

    def _calculate_volatility(self, price_history: list) -> float:
        """Calculate price volatility from history."""
        if len(price_history) < 2:
            return 0.0

        # Calculate returns
        returns = []
        for i in range(1, len(price_history)):
            if price_history[i-1] > 0:
                ret = (price_history[i] - price_history[i-1]) / price_history[i-1]
                returns.append(ret)

        if not returns:
            return 0.0

        # Calculate standard deviation
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        volatility = variance ** 0.5

        return volatility

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get strategy performance statistics."""
        stats = super().get_performance_stats()

        # Add market making specific stats
        stats["total_spread_profit"] = self.total_spread_profit
        stats["rebalances_performed"] = self.rebalances_performed
        stats["inventory_imbalances"] = self.inventory_imbalances
        stats["active_markets"] = len(self.active_quotes)

        return stats

    async def on_trade_enter(
        self,
        token_address: str,
        entry_price: float,
        position_size: float,
        confidence: float
    ):
        """Called when entering a market making position."""
        await super().on_trade_enter(token_address, entry_price, position_size, confidence)

        # Initialize inventory
        self.inventory_sol[token_address] = position_size / 2  # Half in SOL
        self.inventory_tokens[token_address] = (position_size / 2) / entry_price  # Half in tokens

    async def on_trade_exit(
        self,
        token_address: str,
        entry_price: float,
        exit_price: float,
        position_size: float,
        hold_time: float,
        confidence: float
    ):
        """Called when exiting a market making position."""
        await super().on_trade_exit(
            token_address,
            entry_price,
            exit_price,
            position_size,
            hold_time,
            confidence
        )

        # Calculate spread profit
        if entry_price > 0:
            spread_profit = (exit_price - entry_price) * position_size
            self.total_spread_profit += spread_profit

        # Clean up
        self.inventory_sol.pop(token_address, None)
        self.inventory_tokens.pop(token_address, None)
        self.active_quotes.pop(token_address, None)
