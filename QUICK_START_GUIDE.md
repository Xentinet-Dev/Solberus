# Quick Start Guide - Implementation

This guide helps you start implementing the highest-priority features immediately.

## 🚀 Start Here: Week 1 Tasks

### Day 1-2: Strategy Base Class & Snipe Strategy
**Priority**: CRITICAL | **Effort**: 20 hours

#### Task 1: Create Strategy Interface (8 hours)

```bash
# Create the base strategy module
touch backend/src/strategies/base_strategy.py
```

**Implementation outline for `base_strategy.py`:**
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional
from enum import Enum

class StrategyType(Enum):
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
    action: str  # "buy", "sell", "hold"
    confidence: float  # 0.0 to 1.0
    position_size: float  # SOL amount
    reason: str
    metadata: Dict[str, Any]

@dataclass
class StrategyConfig:
    """Base configuration for all strategies"""
    enabled: bool = True
    capital_allocation: float = 1.0  # % of available capital
    max_position_size: float = 10.0  # SOL
    stop_loss: float = -0.10  # -10%
    take_profit: float = 0.50  # +50%
    max_hold_time: int = 3600  # seconds

class BaseStrategy(ABC):
    """Abstract base class for all trading strategies"""

    def __init__(self, config: StrategyConfig):
        self.config = config
        self.name = self.__class__.__name__
        self.enabled = config.enabled

        # Performance tracking
        self.trades_count = 0
        self.wins = 0
        self.losses = 0
        self.total_pnl = 0.0

    @abstractmethod
    async def analyze(self, market_data: Dict[str, Any]) -> StrategySignal:
        """
        Analyze market data and return a trading signal

        Args:
            market_data: Dict containing token info, price, volume, etc.

        Returns:
            StrategySignal with action recommendation
        """
        pass

    @abstractmethod
    async def should_enter(self, token_address: str, market_data: Dict[str, Any]) -> bool:
        """Determine if strategy should enter a position"""
        pass

    @abstractmethod
    async def should_exit(self, position: Dict[str, Any], market_data: Dict[str, Any]) -> bool:
        """Determine if strategy should exit a position"""
        pass

    def calculate_position_size(self, available_capital: float, market_data: Dict[str, Any]) -> float:
        """Calculate position size based on capital allocation"""
        allocated = available_capital * self.config.capital_allocation
        return min(allocated, self.config.max_position_size)

    async def on_trade_complete(self, pnl: float, was_win: bool):
        """Update strategy performance metrics"""
        self.trades_count += 1
        if was_win:
            self.wins += 1
        else:
            self.losses += 1
        self.total_pnl += pnl

    def get_win_rate(self) -> float:
        """Calculate win rate"""
        if self.trades_count == 0:
            return 0.0
        return self.wins / self.trades_count

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        return {
            "name": self.name,
            "enabled": self.enabled,
            "trades": self.trades_count,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": self.get_win_rate(),
            "total_pnl": self.total_pnl,
            "avg_pnl": self.total_pnl / self.trades_count if self.trades_count > 0 else 0.0
        }
```

#### Task 2: Implement Snipe Strategy Module (12 hours)

```bash
# Create the snipe strategy module
touch backend/src/strategies/snipe_strategy.py
```

**Implementation outline for `snipe_strategy.py`:**
```python
from typing import Dict, Any
from .base_strategy import BaseStrategy, StrategySignal, StrategyConfig
from dataclasses import dataclass
import time

@dataclass
class SnipeConfig(StrategyConfig):
    """Configuration specific to snipe strategy"""
    min_liquidity: float = 5.0  # SOL
    max_slippage: float = 0.20  # 20%
    entry_speed: str = "fast"  # "instant", "fast", "normal"
    max_market_cap: float = 50000.0  # USD
    min_holder_count: int = 10
    blacklist_creators: list = None

class SnipeStrategy(BaseStrategy):
    """
    Snipe Strategy - Fast entry on new token launches

    Entry Criteria:
    - New token detected (< 5 minutes old)
    - Liquidity >= min_liquidity
    - Slippage acceptable
    - No security threats detected
    """

    def __init__(self, config: SnipeConfig):
        super().__init__(config)
        self.snipe_config = config
        self.seen_tokens = set()  # Track tokens we've already evaluated

    async def analyze(self, market_data: Dict[str, Any]) -> StrategySignal:
        """Analyze if token is snipe-worthy"""
        token_address = market_data.get("token_address")

        # Check if we've already seen this token
        if token_address in self.seen_tokens:
            return StrategySignal(
                action="hold",
                confidence=0.0,
                position_size=0.0,
                reason="Already evaluated this token",
                metadata={}
            )

        self.seen_tokens.add(token_address)

        # Extract market data
        liquidity = market_data.get("liquidity_sol", 0.0)
        slippage = market_data.get("slippage", 1.0)
        token_age = market_data.get("age_seconds", float('inf'))
        market_cap = market_data.get("market_cap_usd", 0.0)
        holder_count = market_data.get("holder_count", 0)
        creator = market_data.get("creator")
        security_score = market_data.get("security_score", 0)

        # Entry checks
        checks = {
            "new_token": token_age < 300,  # < 5 minutes
            "sufficient_liquidity": liquidity >= self.snipe_config.min_liquidity,
            "acceptable_slippage": slippage <= self.snipe_config.max_slippage,
            "market_cap_ok": market_cap <= self.snipe_config.max_market_cap,
            "holder_count_ok": holder_count >= self.snipe_config.min_holder_count,
            "creator_not_blacklisted": creator not in (self.snipe_config.blacklist_creators or []),
            "security_ok": security_score >= 50,  # Minimum security threshold
        }

        passed_checks = sum(checks.values())
        confidence = passed_checks / len(checks)

        if confidence >= 0.85:  # 6/7 checks passed
            position_size = self.calculate_position_size(
                market_data.get("available_capital", 0.0),
                market_data
            )

            return StrategySignal(
                action="buy",
                confidence=confidence,
                position_size=position_size,
                reason=f"Snipe opportunity detected: {passed_checks}/{len(checks)} checks passed",
                metadata={
                    "checks": checks,
                    "liquidity": liquidity,
                    "slippage": slippage,
                    "token_age": token_age,
                }
            )

        return StrategySignal(
            action="hold",
            confidence=confidence,
            position_size=0.0,
            reason=f"Failed checks: {[k for k, v in checks.items() if not v]}",
            metadata={"checks": checks}
        )

    async def should_enter(self, token_address: str, market_data: Dict[str, Any]) -> bool:
        """Check if we should enter position"""
        signal = await self.analyze(market_data)
        return signal.action == "buy" and signal.confidence >= 0.85

    async def should_exit(self, position: Dict[str, Any], market_data: Dict[str, Any]) -> bool:
        """Check if we should exit position"""
        entry_price = position.get("entry_price")
        current_price = market_data.get("price")
        entry_time = position.get("entry_time")
        current_time = time.time()

        if not entry_price or not current_price:
            return False

        # Calculate P&L
        pnl_percent = (current_price - entry_price) / entry_price
        hold_time = current_time - entry_time

        # Exit conditions
        exit_conditions = {
            "take_profit": pnl_percent >= self.config.take_profit,
            "stop_loss": pnl_percent <= self.config.stop_loss,
            "max_hold_time": hold_time >= self.config.max_hold_time,
            "security_degraded": market_data.get("security_score", 100) < 30,
        }

        should_exit = any(exit_conditions.values())

        if should_exit:
            reason = [k for k, v in exit_conditions.items() if v][0]
            print(f"Exit triggered: {reason} (P&L: {pnl_percent:.2%})")

        return should_exit
```

---

### Day 3-4: Update Strategy Combinator (16 hours)

#### Task 3: Complete Strategy Combinator

**File to edit**: `backend/src/strategies/combinator.py`

**Key changes:**
1. Import the new base strategy and strategy modules
2. Replace `_execute_strategy()` placeholder
3. Add parallel strategy execution
4. Add performance tracking

**Code snippet to add:**
```python
from .base_strategy import BaseStrategy, StrategyType
from .snipe_strategy import SnipeStrategy, SnipeConfig

class StrategyCombinator:
    def __init__(self):
        self.strategies: Dict[StrategyType, BaseStrategy] = {}
        self._init_strategies()

    def _init_strategies(self):
        """Initialize all strategies"""
        # Snipe strategy
        snipe_config = SnipeConfig(
            enabled=True,
            capital_allocation=0.3,  # 30% of capital
            min_liquidity=5.0,
            max_slippage=0.20,
        )
        self.strategies[StrategyType.SNIPE] = SnipeStrategy(snipe_config)

        # Add other strategies as they're implemented
        # self.strategies[StrategyType.MOMENTUM] = MomentumStrategy(config)
        # ...

    async def _execute_strategy(
        self,
        strategy_type: StrategyType,
        market_data: Dict[str, Any]
    ) -> Optional[StrategySignal]:
        """Execute a specific strategy"""
        strategy = self.strategies.get(strategy_type)

        if not strategy or not strategy.enabled:
            return None

        try:
            signal = await strategy.analyze(market_data)
            return signal
        except Exception as e:
            print(f"Error executing {strategy_type.value}: {e}")
            return None

    async def get_combined_signal(
        self,
        market_data: Dict[str, Any]
    ) -> List[StrategySignal]:
        """Execute all enabled strategies in parallel"""
        tasks = []
        for strategy_type in StrategyType:
            tasks.append(self._execute_strategy(strategy_type, market_data))

        signals = await asyncio.gather(*tasks)
        return [s for s in signals if s is not None]
```

---

### Day 5: Testing (8 hours)

#### Task 4: Create Tests for Strategies

```bash
# Create test directory if it doesn't exist
mkdir -p backend/tests/strategies
touch backend/tests/strategies/test_snipe_strategy.py
```

**Test outline:**
```python
import pytest
from backend.src.strategies.snipe_strategy import SnipeStrategy, SnipeConfig

@pytest.mark.asyncio
async def test_snipe_strategy_basic():
    """Test basic snipe strategy functionality"""
    config = SnipeConfig(min_liquidity=5.0, max_slippage=0.20)
    strategy = SnipeStrategy(config)

    # Mock market data for a good snipe opportunity
    market_data = {
        "token_address": "test123",
        "liquidity_sol": 10.0,
        "slippage": 0.15,
        "age_seconds": 60,
        "market_cap_usd": 10000,
        "holder_count": 20,
        "creator": "creator123",
        "security_score": 80,
        "available_capital": 100.0,
        "price": 0.001,
    }

    signal = await strategy.analyze(market_data)

    assert signal.action == "buy"
    assert signal.confidence > 0.8
    assert signal.position_size > 0

@pytest.mark.asyncio
async def test_snipe_strategy_low_liquidity():
    """Test snipe strategy rejects low liquidity tokens"""
    config = SnipeConfig(min_liquidity=10.0)
    strategy = SnipeStrategy(config)

    market_data = {
        "token_address": "test456",
        "liquidity_sol": 3.0,  # Too low
        "slippage": 0.15,
        "age_seconds": 60,
        "market_cap_usd": 10000,
        "holder_count": 20,
        "creator": "creator123",
        "security_score": 80,
        "available_capital": 100.0,
    }

    signal = await strategy.analyze(market_data)

    assert signal.action == "hold"
    assert signal.confidence < 0.8

# Add more tests...
```

**Run tests:**
```bash
cd backend
pytest tests/strategies/test_snipe_strategy.py -v
```

---

## 📊 Week 1 Success Criteria

By end of Week 1, you should have:
- [✅] BaseStrategy interface created
- [✅] SnipeStrategy fully implemented
- [✅] StrategyCombinator updated to use new system
- [✅] Unit tests written and passing
- [✅] Integration test on testnet (optional but recommended)

---

## 🗓️ Week 2 Preview: Momentum & Reversal Strategies

Next week you'll implement:
1. **Momentum Strategy** (16 hours) - RSI, MACD, volume analysis
2. **Reversal Strategy** (16 hours) - Dip/peak detection, mean reversion
3. **Frontend Control Tab** (8 hours) - Start/stop bot UI
4. **Testing** (8 hours)

---

## 💡 Development Tips

### 1. Use Git Branches
```bash
# Create feature branch
git checkout -b feature/strategy-base-class

# Work on feature...

# Commit and push
git add .
git commit -m "Add base strategy interface and snipe strategy"
git push origin feature/strategy-base-class
```

### 2. Test on Devnet First
```python
# In your config, use devnet
SOLANA_RPC_URL = "https://api.devnet.solana.com"
```

### 3. Use Mock Data Initially
```python
# Create mock data generator for testing
def create_mock_token_launch():
    return {
        "token_address": f"test{random.randint(1000, 9999)}",
        "liquidity_sol": random.uniform(1, 20),
        "slippage": random.uniform(0.05, 0.30),
        # ...
    }
```

### 4. Log Everything
```python
import logging

logger = logging.getLogger(__name__)
logger.info(f"Strategy {self.name} analyzing {token_address}")
logger.debug(f"Signal: {signal}")
```

### 5. Start Small, Iterate
- Implement basic version first
- Test thoroughly
- Add features incrementally
- Refactor as needed

---

## 🆘 Common Issues & Solutions

### Issue 1: Strategy not executing
**Check:**
- Is strategy enabled in config?
- Is combinator calling the strategy?
- Are there errors in logs?

### Issue 2: False positives (bad snipes)
**Solution:**
- Increase confidence threshold (0.90 instead of 0.85)
- Add more stringent checks
- Integrate security scanner earlier

### Issue 3: Missing dependencies
**Solution:**
```bash
cd backend
pip install -r requirements.txt
```

### Issue 4: Slow execution
**Solution:**
- Use asyncio properly (await all async calls)
- Cache repeated calculations
- Optimize RPC calls

---

## 📚 Useful Resources

### Solana Development
- [Solana Cookbook](https://solanacookbook.com/)
- [Anchor Framework Docs](https://www.anchor-lang.com/)
- [pump.fun SDK](https://github.com/pumpfun/pump-sdk)

### Trading Strategy Design
- [Investopedia - Trading Strategies](https://www.investopedia.com/trading-4427765)
- [QuantStart - Algorithmic Trading](https://www.quantstart.com/)

### Python Async Programming
- [Real Python - Async IO](https://realpython.com/async-io-python/)
- [AsyncIO Documentation](https://docs.python.org/3/library/asyncio.html)

---

## 🎯 Your Next Command

Ready to start? Run this:

```bash
# 1. Create the base strategy file
touch backend/src/strategies/base_strategy.py

# 2. Open it in your editor
# Start implementing the BaseStrategy class from the outline above

# 3. Commit your progress frequently
git add backend/src/strategies/base_strategy.py
git commit -m "WIP: Add base strategy interface"
```

**Good luck! 🚀**

---

**Questions?** Refer to:
- **IMPLEMENTATION_PLAN.md** - Full 16-week roadmap
- **README.md** - Project overview
- **FEATURES_ROADMAP.md** - Feature descriptions

**Need help?** Check the existing implementations:
- `backend/src/trading/universal_trader.py` - Trading logic examples
- `backend/src/mev/front_runner.py` - Strategy pattern examples
- `backend/src/security/threat_detector.py` - Analysis examples
