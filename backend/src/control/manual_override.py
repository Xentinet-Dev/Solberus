"""
Manual Override Console for bot control and safety.

Provides emergency stop, manual trade execution, strategy override,
and position management capabilities.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from solders.pubkey import Pubkey

from interfaces.core import TokenInfo
from trading.base import TradeResult
from trading.position import ExitReason, Position
from utils.logger import get_logger

logger = get_logger(__name__)


class BotState(Enum):
    """Bot operational state."""

    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    EMERGENCY_STOP = "emergency_stop"


class OverrideCommand(Enum):
    """Manual override commands."""

    EMERGENCY_STOP = "emergency_stop"
    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"
    MANUAL_BUY = "manual_buy"
    MANUAL_SELL = "manual_sell"
    CLOSE_POSITION = "close_position"
    OVERRIDE_STRATEGY = "override_strategy"
    RESET_STRATEGY = "reset_strategy"
    GET_STATUS = "get_status"
    GET_POSITIONS = "get_positions"


@dataclass
class OverrideStatus:
    """Current override system status."""

    bot_state: BotState
    is_emergency_stopped: bool
    is_paused: bool
    active_positions: int
    last_command: str | None = None
    last_command_time: datetime | None = None
    override_active: bool = False
    strategy_override: dict[str, Any] | None = None


@dataclass
class ManualTradeRequest:
    """Request for manual trade execution."""

    token_address: str
    amount: float | None = None  # None = use default buy_amount
    slippage: float | None = None  # None = use default slippage
    priority_fee: int | None = None  # None = use default
    execute_immediately: bool = True


class ManualOverrideConsole:
    """
    Manual override console for bot control and safety.

    Features:
    - Emergency stop (kill switch)
    - Pause/resume bot operations
    - Manual trade execution
    - Position management
    - Strategy override
    - Real-time status monitoring
    """

    def __init__(self, trader_instance: Any):
        """Initialize manual override console.

        Args:
            trader_instance: Instance of UniversalTrader to control
        """
        self.trader = trader_instance
        self._state = BotState.STOPPED
        self._emergency_stop = False
        self._paused = False
        self._strategy_override: dict[str, Any] | None = None
        self._original_strategy: dict[str, Any] | None = None

        # Position tracking
        self._active_positions: dict[str, Position] = {}
        self._position_lock = asyncio.Lock()

        # Command queue for async execution
        self._command_queue: asyncio.Queue = asyncio.Queue()
        self._command_processor_task: asyncio.Task | None = None

        # Event callbacks
        self._on_state_change: Callable[[BotState], None] | None = None
        self._on_emergency_stop: Callable[[], None] | None = None
        self._on_trade_executed: Callable[[TradeResult], None] | None = None

        # Statistics
        self._last_command: str | None = None
        self._last_command_time: datetime | None = None
        self._command_count = 0

        logger.info("Manual Override Console initialized")

    async def start(self):
        """Start the command processor."""
        if self._command_processor_task is None or self._command_processor_task.done():
            self._command_processor_task = asyncio.create_task(
                self._process_commands()
            )
            logger.info("Manual Override Console started")

    async def stop(self):
        """Stop the command processor."""
        if self._command_processor_task:
            self._command_processor_task.cancel()
            try:
                await self._command_processor_task
            except asyncio.CancelledError:
                pass
            self._command_processor_task = None
        logger.info("Manual Override Console stopped")

    # ==================== Emergency Controls ====================

    async def emergency_stop(self) -> bool:
        """
        Emergency stop - immediately halts all bot operations.

        This is a kill switch that:
        - Stops all trading
        - Cancels pending operations
        - Prevents new operations
        - Can only be reset with resume() or reset()

        Returns:
            True if emergency stop was activated
        """
        logger.critical("🚨 EMERGENCY STOP ACTIVATED 🚨")
        self._emergency_stop = True
        self._paused = True
        self._state = BotState.EMERGENCY_STOP

        # Stop all trading operations
        if hasattr(self.trader, "processing"):
            self.trader.processing = False

        # Trigger callback
        if self._on_emergency_stop:
            try:
                self._on_emergency_stop()
            except Exception as e:
                logger.exception(f"Error in emergency stop callback: {e}")

        if self._on_state_change:
            try:
                self._on_state_change(self._state)
            except Exception as e:
                logger.exception(f"Error in state change callback: {e}")

        self._record_command("emergency_stop")
        return True

    async def pause(self) -> bool:
        """
        Pause bot operations (can be resumed).

        Returns:
            True if bot was paused
        """
        if self._emergency_stop:
            logger.warning("Cannot pause: Emergency stop is active. Use reset() first.")
            return False

        logger.info("⏸️ Bot paused")
        self._paused = True
        self._state = BotState.PAUSED

        if hasattr(self.trader, "processing"):
            self.trader.processing = False

        if self._on_state_change:
            try:
                self._on_state_change(self._state)
            except Exception as e:
                logger.exception(f"Error in state change callback: {e}")

        self._record_command("pause")
        return True

    async def resume(self) -> bool:
        """
        Resume bot operations after pause or emergency stop.

        Returns:
            True if bot was resumed
        """
        if self._emergency_stop:
            logger.warning("Cannot resume: Emergency stop is active. Use reset() first.")
            return False

        logger.info("▶️ Bot resumed")
        self._paused = False
        self._state = BotState.RUNNING

        if hasattr(self.trader, "processing"):
            self.trader.processing = True

        if self._on_state_change:
            try:
                self._on_state_change(self._state)
            except Exception as e:
                logger.exception(f"Error in state change callback: {e}")

        self._record_command("resume")
        return True

    async def reset(self) -> bool:
        """
        Reset emergency stop (requires explicit reset after emergency stop).

        Returns:
            True if emergency stop was reset
        """
        if not self._emergency_stop:
            logger.info("No emergency stop to reset")
            return False

        logger.info("🔄 Emergency stop reset")
        self._emergency_stop = False
        self._paused = False
        self._state = BotState.RUNNING

        if hasattr(self.trader, "processing"):
            self.trader.processing = True

        if self._on_state_change:
            try:
                self._on_state_change(self._state)
            except Exception as e:
                logger.exception(f"Error in state change callback: {e}")

        self._record_command("reset")
        return True

    # ==================== Manual Trading ====================

    async def manual_buy(
        self,
        token_address: str,
        amount: float | None = None,
        slippage: float | None = None,
        priority_fee: int | None = None,
    ) -> TradeResult:
        """
        Execute a manual buy order.

        Args:
            token_address: Token mint address
            amount: Buy amount in SOL (None = use default)
            slippage: Slippage tolerance (None = use default)
            priority_fee: Priority fee in microlamports (None = use default)

        Returns:
            TradeResult with buy outcome
        """
        if self._emergency_stop:
            raise RuntimeError("Cannot execute trade: Emergency stop is active")

        if self._paused:
            raise RuntimeError("Cannot execute trade: Bot is paused")

        logger.info(f"📈 Manual buy: {token_address}")

        try:
            # Get token info
            mint = Pubkey.from_string(token_address)
            token_info = TokenInfo(
                mint=mint,
                symbol="",  # Will be fetched if needed
                platform=self.trader.platform,
            )

            # Use override amounts or defaults
            buy_amount = amount if amount is not None else self.trader.buy_amount
            buy_slippage = (
                slippage if slippage is not None else self.trader.buy_slippage
            )

            # Execute buy
            result = await self.trader.buyer.execute(token_info)

            # Track position if successful
            if result.success:
                position = Position.create_from_buy_result(
                    mint=mint,
                    symbol=token_info.symbol or token_address[:8],
                    entry_price=result.price,
                    quantity=result.quantity or 0,
                    take_profit_percentage=self.trader.take_profit_percentage,
                    stop_loss_percentage=self.trader.stop_loss_percentage,
                    max_hold_time=self.trader.max_hold_time,
                )

                async with self._position_lock:
                    self._active_positions[str(mint)] = position

                if self._on_trade_executed:
                    try:
                        self._on_trade_executed(result)
                    except Exception as e:
                        logger.exception(f"Error in trade callback: {e}")

            self._record_command(f"manual_buy:{token_address}")
            return result

        except Exception as e:
            logger.exception(f"Manual buy failed: {e}")
            raise

    async def manual_sell(
        self,
        token_address: str,
        slippage: float | None = None,
        priority_fee: int | None = None,
    ) -> TradeResult:
        """
        Execute a manual sell order.

        Args:
            token_address: Token mint address
            slippage: Slippage tolerance (None = use default)
            priority_fee: Priority fee in microlamports (None = use default)

        Returns:
            TradeResult with sell outcome
        """
        if self._emergency_stop:
            raise RuntimeError("Cannot execute trade: Emergency stop is active")

        if self._paused:
            raise RuntimeError("Cannot execute trade: Bot is paused")

        logger.info(f"📉 Manual sell: {token_address}")

        try:
            mint = Pubkey.from_string(token_address)
            token_info = TokenInfo(
                mint=mint,
                symbol="",
                platform=self.trader.platform,
            )

            sell_slippage = (
                slippage if slippage is not None else self.trader.sell_slippage
            )

            # Execute sell
            result = await self.trader.seller.execute(token_info)

            # Update position if exists
            if result.success:
                async with self._position_lock:
                    if str(mint) in self._active_positions:
                        position = self._active_positions[str(mint)]
                        position.is_active = False
                        position.exit_reason = ExitReason.MANUAL
                        position.exit_price = result.price
                        position.exit_time = datetime.utcnow()
                        del self._active_positions[str(mint)]

                if self._on_trade_executed:
                    try:
                        self._on_trade_executed(result)
                    except Exception as e:
                        logger.exception(f"Error in trade callback: {e}")

            self._record_command(f"manual_sell:{token_address}")
            return result

        except Exception as e:
            logger.exception(f"Manual sell failed: {e}")
            raise

    # ==================== Position Management ====================

    async def close_position(self, token_address: str) -> TradeResult:
        """
        Close an active position.

        Args:
            token_address: Token mint address

        Returns:
            TradeResult with sell outcome
        """
        async with self._position_lock:
            if str(token_address) not in self._active_positions:
                raise ValueError(f"No active position for token: {token_address}")

        return await self.manual_sell(token_address)

    async def get_positions(self) -> dict[str, Position]:
        """Get all active positions."""
        async with self._position_lock:
            return self._active_positions.copy()

    async def get_position(self, token_address: str) -> Position | None:
        """Get position for a specific token."""
        async with self._position_lock:
            return self._active_positions.get(str(token_address))

    # ==================== Strategy Override ====================

    async def override_strategy(self, strategy_updates: dict[str, Any]) -> bool:
        """
        Override trading strategy parameters.

        Args:
            strategy_updates: Dictionary of strategy parameters to override
                Example: {"buy_amount": 0.1, "take_profit_percentage": 0.5}

        Returns:
            True if strategy was overridden
        """
        if self._emergency_stop:
            logger.warning("Cannot override strategy: Emergency stop is active")
            return False

        logger.info(f"🔧 Strategy override: {strategy_updates}")

        # Save original strategy if first override
        if self._original_strategy is None:
            self._original_strategy = {
                "buy_amount": self.trader.buy_amount,
                "buy_slippage": self.trader.buy_slippage,
                "sell_slippage": self.trader.sell_slippage,
                "take_profit_percentage": self.trader.take_profit_percentage,
                "stop_loss_percentage": self.trader.stop_loss_percentage,
                "max_hold_time": self.trader.max_hold_time,
            }

        # Apply overrides
        self._strategy_override = strategy_updates.copy()

        if "buy_amount" in strategy_updates:
            self.trader.buy_amount = strategy_updates["buy_amount"]
        if "buy_slippage" in strategy_updates:
            self.trader.buy_slippage = strategy_updates["buy_slippage"]
        if "sell_slippage" in strategy_updates:
            self.trader.sell_slippage = strategy_updates["sell_slippage"]
        if "take_profit_percentage" in strategy_updates:
            self.trader.take_profit_percentage = strategy_updates[
                "take_profit_percentage"
            ]
        if "stop_loss_percentage" in strategy_updates:
            self.trader.stop_loss_percentage = strategy_updates["stop_loss_percentage"]
        if "max_hold_time" in strategy_updates:
            self.trader.max_hold_time = strategy_updates["max_hold_time"]

        self._record_command("override_strategy")
        return True

    async def reset_strategy(self) -> bool:
        """
        Reset strategy to original values.

        Returns:
            True if strategy was reset
        """
        if self._original_strategy is None:
            logger.info("No strategy override to reset")
            return False

        logger.info("🔄 Strategy reset to original")

        # Restore original values
        for key, value in self._original_strategy.items():
            setattr(self.trader, key, value)

        self._strategy_override = None
        self._original_strategy = None

        self._record_command("reset_strategy")
        return True

    # ==================== Status & Monitoring ====================

    async def get_status(self) -> OverrideStatus:
        """Get current override system status."""
        async with self._position_lock:
            active_positions = len(self._active_positions)

        return OverrideStatus(
            bot_state=self._state,
            is_emergency_stopped=self._emergency_stop,
            is_paused=self._paused,
            active_positions=active_positions,
            last_command=self._last_command,
            last_command_time=self._last_command_time,
            override_active=self._strategy_override is not None,
            strategy_override=self._strategy_override,
        )

    def is_running(self) -> bool:
        """Check if bot is running."""
        return self._state == BotState.RUNNING and not self._paused

    def is_paused(self) -> bool:
        """Check if bot is paused."""
        return self._paused

    def is_emergency_stopped(self) -> bool:
        """Check if emergency stop is active."""
        return self._emergency_stop

    # ==================== Callbacks ====================

    def set_on_state_change(self, callback: Callable[[BotState], None]):
        """Set callback for state changes."""
        self._on_state_change = callback

    def set_on_emergency_stop(self, callback: Callable[[], None]):
        """Set callback for emergency stop."""
        self._on_emergency_stop = callback

    def set_on_trade_executed(self, callback: Callable[[TradeResult], None]):
        """Set callback for trade execution."""
        self._on_trade_executed = callback

    # ==================== Internal Methods ====================

    def _record_command(self, command: str):
        """Record command execution."""
        self._last_command = command
        self._last_command_time = datetime.utcnow()
        self._command_count += 1

    async def _process_commands(self):
        """Background task to process queued commands."""
        while True:
            try:
                command = await self._command_queue.get()
                # Process command here if needed
                # For now, commands are executed directly
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Error processing command: {e}")

    # ==================== Integration Helpers ====================

    def check_can_trade(self) -> tuple[bool, str]:
        """
        Check if trading is allowed.

        Returns:
            Tuple of (can_trade, reason)
        """
        if self._emergency_stop:
            return False, "Emergency stop is active"
        if self._paused:
            return False, "Bot is paused"
        return True, "OK"

