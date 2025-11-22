"""
Market Maker - Provide liquidity through strategic buy/sell operations.

For bonding curve DEXs like pump.fun, market making involves:
- Strategic buying when price is low (below target)
- Strategic selling when price is high (above target)
- Maintaining inventory balance
- Adjusting spread based on volatility
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime

from solders.pubkey import Pubkey

from core.client import SolanaClient
from core.wallet import Wallet
from interfaces.core import TokenInfo, Platform
from market_making.inventory_manager import InventoryManager, InventoryState
from market_making.spread_calculator import SpreadCalculator
from trading.platform_aware import PlatformAwareBuyer, PlatformAwareSeller
from core.priority_fee.manager import PriorityFeeManager
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MarketMakingConfig:
    """Configuration for market making."""
    
    # Token to market make
    token_mint: Pubkey
    platform: Platform
    
    # Inventory management
    target_sol_ratio: float = 0.5  # Target ratio of SOL to total value (0.5 = 50% SOL, 50% tokens)
    min_sol_balance: float = 0.1  # Minimum SOL to keep
    min_token_balance: float = 0.0  # Minimum tokens to keep
    
    # Trading parameters
    spread_percentage: float = 0.02  # 2% spread (buy 1% below, sell 1% above)
    max_trade_size_sol: float = 0.1  # Maximum trade size in SOL
    min_trade_size_sol: float = 0.01  # Minimum trade size in SOL
    
    # Rebalancing
    rebalance_threshold: float = 0.1  # Rebalance when ratio deviates by 10%
    rebalance_interval_seconds: int = 60  # Check rebalancing every 60 seconds
    
    # Volatility adjustment
    volatility_window: int = 10  # Number of price points for volatility calculation
    high_volatility_multiplier: float = 1.5  # Increase spread in high volatility
    
    # Risk management
    max_position_size_sol: float = 1.0  # Maximum total position size
    stop_loss_percentage: float = 0.1  # Stop loss at 10% loss
    take_profit_percentage: float = 0.2  # Take profit at 20% gain
    
    # Execution
    slippage: float = 0.01  # 1% slippage tolerance
    priority_fee: int = 100_000  # Priority fee in microlamports


@dataclass
class MarketMakingResult:
    """Result of a market making operation."""
    
    success: bool
    operation_type: str  # "buy", "sell", "rebalance", "none"
    amount_sol: float = 0.0
    amount_tokens: float = 0.0
    price: float = 0.0
    profit_sol: float = 0.0
    timestamp: datetime = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class MarketMaker:
    """
    Market maker for bonding curve DEXs.
    
    Provides liquidity by strategically buying and selling tokens
    to maintain inventory balance and profit from spread.
    """
    
    def __init__(
        self,
        client: SolanaClient,
        wallet: Wallet,
        config: MarketMakingConfig,
    ):
        """Initialize market maker.
        
        Args:
            client: Solana RPC client
            wallet: Wallet to use for trading
            config: Market making configuration
        """
        self.client = client
        self.wallet = wallet
        self.config = config
        
        # Initialize components
        self.inventory_manager = InventoryManager(
            client=client,
            wallet=wallet,
            token_mint=config.token_mint,
            target_sol_ratio=config.target_sol_ratio,
            min_sol_balance=config.min_sol_balance,
            min_token_balance=config.min_token_balance,
        )
        
        self.spread_calculator = SpreadCalculator(
            base_spread=config.spread_percentage,
            volatility_window=config.volatility_window,
            high_volatility_multiplier=config.high_volatility_multiplier,
        )
        
        # Initialize priority fee manager
        self.priority_fee_manager = PriorityFeeManager(
            client=client,
            enable_fixed_fee=True,
            fixed_fee=config.priority_fee,
        )
        
        # Price history for volatility calculation
        self.price_history: List[float] = []
        
        # Statistics
        self.total_trades = 0
        self.total_profit = 0.0
        self.total_volume = 0.0
        self.last_rebalance_time = datetime.utcnow()
        
        # Active state
        self.is_active = False
        self.market_making_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start market making."""
        if self.is_active:
            logger.warning("Market maker already active")
            return
        
        self.is_active = True
        self.market_making_task = asyncio.create_task(self._market_making_loop())
        logger.info(f"Started market making for token {self.config.token_mint}")
    
    async def stop(self):
        """Stop market making."""
        self.is_active = False
        if self.market_making_task:
            self.market_making_task.cancel()
            try:
                await self.market_making_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped market making")
    
    async def _market_making_loop(self):
        """Main market making loop."""
        while self.is_active:
            try:
                # Check if rebalancing is needed
                if self._should_rebalance():
                    result = await self._rebalance()
                    if result.success:
                        logger.info(f"Rebalanced: {result.operation_type}")
                
                # Check for market making opportunities
                result = await self._check_and_execute_trade()
                
                if result.success and result.operation_type != "none":
                    logger.info(
                        f"Market making trade: {result.operation_type}, "
                        f"Amount: {result.amount_sol:.6f} SOL, "
                        f"Profit: {result.profit_sol:.6f} SOL"
                    )
                
                # Wait before next iteration
                await asyncio.sleep(self.config.rebalance_interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Error in market making loop: {e}")
                await asyncio.sleep(5)
    
    async def _check_and_execute_trade(self) -> MarketMakingResult:
        """Check for trading opportunities and execute if profitable.
        
        Returns:
            MarketMakingResult
        """
        try:
            # Get current price
            current_price = await self._get_current_price()
            if current_price is None:
                return MarketMakingResult(
                    success=False,
                    operation_type="none",
                    error_message="Could not get current price"
                )
            
            # Update price history
            self.price_history.append(current_price)
            if len(self.price_history) > self.config.volatility_window * 2:
                self.price_history.pop(0)
            
            # Calculate volatility-adjusted spread
            spread = self.spread_calculator.calculate_spread(self.price_history)
            
            # Get inventory state
            inventory = await self.inventory_manager.get_inventory_state()
            
            # Calculate target price based on inventory
            target_price = self._calculate_target_price(inventory, current_price, spread)
            
            # Determine if we should buy or sell
            price_diff = (current_price - target_price) / target_price if target_price > 0 else 0
            
            # Buy if price is below target (with spread)
            if price_diff < -spread / 2:
                return await self._execute_buy(current_price, inventory)
            
            # Sell if price is above target (with spread)
            elif price_diff > spread / 2:
                return await self._execute_sell(current_price, inventory)
            
            # No trade needed
            return MarketMakingResult(
                success=True,
                operation_type="none",
                price=current_price
            )
            
        except Exception as e:
            logger.exception(f"Error checking for trades: {e}")
            return MarketMakingResult(
                success=False,
                operation_type="none",
                error_message=str(e)
            )
    
    async def _execute_buy(self, current_price: float, inventory: InventoryState) -> MarketMakingResult:
        """Execute a buy order.
        
        Args:
            current_price: Current token price
            inventory: Current inventory state
            
        Returns:
            MarketMakingResult
        """
        try:
            # Calculate buy amount
            buy_amount = self._calculate_buy_amount(inventory, current_price)
            
            if buy_amount < self.config.min_trade_size_sol:
                return MarketMakingResult(
                    success=True,
                    operation_type="none",
                    price=current_price,
                    error_message="Buy amount too small"
                )
            
            # Check if we have enough SOL
            if inventory.sol_balance < buy_amount:
                return MarketMakingResult(
                    success=False,
                    operation_type="buy",
                    error_message="Insufficient SOL balance"
                )
            
            # Create token info
            token_info = await self._get_token_info()
            if not token_info:
                return MarketMakingResult(
                    success=False,
                    operation_type="buy",
                    error_message="Could not get token info"
                )
            
            # Execute buy
            buyer = PlatformAwareBuyer(
                client=self.client,
                wallet=self.wallet,
                priority_fee_manager=self.priority_fee_manager,
                amount=buy_amount,
                slippage=self.config.slippage,
            )
            
            result = await buyer.execute(token_info)
            
            if result.success:
                # Update statistics
                self.total_trades += 1
                self.total_volume += buy_amount
                
                # Calculate profit (would need to track entry prices)
                profit = 0.0  # Placeholder
                
                return MarketMakingResult(
                    success=True,
                    operation_type="buy",
                    amount_sol=buy_amount,
                    amount_tokens=result.amount or 0.0,
                    price=result.price or current_price,
                    profit_sol=profit,
                )
            else:
                return MarketMakingResult(
                    success=False,
                    operation_type="buy",
                    error_message=result.error_message or "Buy failed"
                )
                
        except Exception as e:
            logger.exception(f"Error executing buy: {e}")
            return MarketMakingResult(
                success=False,
                operation_type="buy",
                error_message=str(e)
            )
    
    async def _execute_sell(self, current_price: float, inventory: InventoryState) -> MarketMakingResult:
        """Execute a sell order.
        
        Args:
            current_price: Current token price
            inventory: Current inventory state
            
        Returns:
            MarketMakingResult
        """
        try:
            # Calculate sell amount (in tokens)
            sell_amount_tokens = self._calculate_sell_amount(inventory, current_price)
            
            if sell_amount_tokens < self.config.min_token_balance:
                return MarketMakingResult(
                    success=True,
                    operation_type="none",
                    price=current_price,
                    error_message="Sell amount too small"
                )
            
            # Check if we have enough tokens
            if inventory.token_balance < sell_amount_tokens:
                return MarketMakingResult(
                    success=False,
                    operation_type="sell",
                    error_message="Insufficient token balance"
                )
            
            # Create token info
            token_info = await self._get_token_info()
            if not token_info:
                return MarketMakingResult(
                    success=False,
                    operation_type="sell",
                    error_message="Could not get token info"
                )
            
            # Execute sell (PlatformAwareSeller sells all tokens by default)
            # We need to sell a specific amount, so we'll need to handle this differently
            # For now, sell all tokens (would need to modify seller to support partial sells)
            seller = PlatformAwareSeller(
                client=self.client,
                wallet=self.wallet,
                priority_fee_manager=self.priority_fee_manager,
                slippage=self.config.slippage,
            )
            
            result = await seller.execute(token_info)
            
            if result.success:
                # Update statistics
                self.total_trades += 1
                self.total_volume += result.amount * (result.price or current_price) if result.amount else 0.0
                
                # Calculate profit (would need to track entry prices)
                profit = 0.0  # Placeholder
                
                return MarketMakingResult(
                    success=True,
                    operation_type="sell",
                    amount_tokens=result.amount or 0.0,
                    amount_sol=(result.amount or 0.0) * (result.price or current_price),
                    price=result.price or current_price,
                    profit_sol=profit,
                )
            else:
                return MarketMakingResult(
                    success=False,
                    operation_type="sell",
                    error_message=result.error_message or "Sell failed"
                )
                
        except Exception as e:
            logger.exception(f"Error executing sell: {e}")
            return MarketMakingResult(
                success=False,
                operation_type="sell",
                error_message=str(e)
            )
    
    async def _rebalance(self) -> MarketMakingResult:
        """Rebalance inventory to target ratio.
        
        Returns:
            MarketMakingResult
        """
        try:
            inventory = await self.inventory_manager.get_inventory_state()
            
            # Calculate target values
            total_value = inventory.sol_balance + (inventory.token_balance * inventory.token_price)
            target_sol = total_value * self.config.target_sol_ratio
            target_tokens_value = total_value * (1 - self.config.target_sol_ratio)
            target_tokens = target_tokens_value / inventory.token_price if inventory.token_price > 0 else 0
            
            # Calculate deviations
            sol_deviation = inventory.sol_balance - target_sol
            token_deviation = inventory.token_balance - target_tokens
            
            # Get current price
            current_price = await self._get_current_price()
            if current_price is None:
                return MarketMakingResult(
                    success=False,
                    operation_type="rebalance",
                    error_message="Could not get current price"
                )
            
            # Rebalance by buying or selling
            if sol_deviation > self.config.rebalance_threshold * total_value:
                # Too much SOL, buy tokens
                buy_amount = min(sol_deviation, self.config.max_trade_size_sol)
                return await self._execute_buy(current_price, inventory)
            
            elif token_deviation > self.config.rebalance_threshold * total_value / current_price:
                # Too many tokens, sell some
                sell_amount = min(token_deviation, self.config.max_trade_size_sol / current_price)
                return await self._execute_sell(current_price, inventory)
            
            # Already balanced
            self.last_rebalance_time = datetime.utcnow()
            return MarketMakingResult(
                success=True,
                operation_type="none",
                price=current_price
            )
            
        except Exception as e:
            logger.exception(f"Error rebalancing: {e}")
            return MarketMakingResult(
                success=False,
                operation_type="rebalance",
                error_message=str(e)
            )
    
    def _should_rebalance(self) -> bool:
        """Check if rebalancing is needed.
        
        Returns:
            True if rebalancing needed
        """
        time_since_rebalance = (datetime.utcnow() - self.last_rebalance_time).total_seconds()
        return time_since_rebalance >= self.config.rebalance_interval_seconds
    
    def _calculate_target_price(
        self, inventory: InventoryState, current_price: float, spread: float
    ) -> float:
        """Calculate target price based on inventory.
        
        Args:
            inventory: Current inventory state
            current_price: Current token price
            spread: Current spread
            
        Returns:
            Target price
        """
        # If we have too much SOL, target price should be lower (encourage buying)
        # If we have too many tokens, target price should be higher (encourage selling)
        
        total_value = inventory.sol_balance + (inventory.token_balance * inventory.token_price)
        current_sol_ratio = inventory.sol_balance / total_value if total_value > 0 else 0.5
        
        # Adjust target price based on inventory ratio
        ratio_diff = current_sol_ratio - self.config.target_sol_ratio
        
        # If we have too much SOL (ratio_diff > 0), lower target price
        # If we have too many tokens (ratio_diff < 0), raise target price
        adjustment = -ratio_diff * spread * 2  # Scale adjustment
        
        target_price = current_price * (1 + adjustment)
        
        return target_price
    
    def _calculate_buy_amount(
        self, inventory: InventoryState, current_price: float
    ) -> float:
        """Calculate buy amount.
        
        Args:
            inventory: Current inventory state
            current_price: Current token price
            
        Returns:
            Buy amount in SOL
        """
        # Calculate based on rebalancing needs and max trade size
        total_value = inventory.sol_balance + (inventory.token_balance * current_price)
        target_sol = total_value * self.config.target_sol_ratio
        sol_needed = target_sol - inventory.sol_balance
        
        # Buy amount should be a fraction of what's needed
        buy_amount = min(
            abs(sol_needed) * 0.5,  # 50% of rebalancing need
            self.config.max_trade_size_sol,
            inventory.sol_balance - self.config.min_sol_balance
        )
        
        return max(buy_amount, 0.0)
    
    def _calculate_sell_amount(
        self, inventory: InventoryState, current_price: float
    ) -> float:
        """Calculate sell amount in tokens.
        
        Args:
            inventory: Current inventory state
            current_price: Current token price
            
        Returns:
            Sell amount in tokens
        """
        # Calculate based on rebalancing needs
        total_value = inventory.sol_balance + (inventory.token_balance * current_price)
        target_tokens_value = total_value * (1 - self.config.target_sol_ratio)
        target_tokens = target_tokens_value / current_price if current_price > 0 else 0
        tokens_to_sell = inventory.token_balance - target_tokens
        
        # Sell amount should be a fraction of what's needed
        sell_amount = min(
            abs(tokens_to_sell) * 0.5,  # 50% of rebalancing need
            self.config.max_trade_size_sol / current_price,  # Max trade size in tokens
            inventory.token_balance - self.config.min_token_balance
        )
        
        return max(sell_amount, 0.0)
    
    async def _get_current_price(self) -> Optional[float]:
        """Get current token price.
        
        Returns:
            Current price in SOL per token, or None if error
        """
        try:
            from platforms import get_platform_implementations
            
            implementations = get_platform_implementations(self.config.platform, self.client)
            address_provider = implementations.address_provider
            curve_manager = implementations.curve_manager
            
            bonding_curve = address_provider.derive_pool_address(self.config.token_mint)
            price = await curve_manager.calculate_price(bonding_curve)
            
            return price
            
        except Exception as e:
            logger.exception(f"Error getting current price: {e}")
            return None
    
    async def _get_token_info(self) -> Optional[TokenInfo]:
        """Get token info for trading.
        
        Returns:
            TokenInfo or None if error
        """
        try:
            from platforms import get_platform_implementations
            
            implementations = get_platform_implementations(self.config.platform, self.client)
            address_provider = implementations.address_provider
            
            bonding_curve = address_provider.derive_pool_address(self.config.token_mint)
            associated_bonding_curve = address_provider.derive_associated_bonding_curve(
                self.config.token_mint, bonding_curve
            )
            
            return TokenInfo(
                name="Market Making Token",
                symbol="MM",
                uri="",
                mint=self.config.token_mint,
                platform=self.config.platform,
                bonding_curve=bonding_curve,
                associated_bonding_curve=associated_bonding_curve,
                user=self.wallet.pubkey(),
            )
            
        except Exception as e:
            logger.exception(f"Error getting token info: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get market making statistics.
        
        Returns:
            Dictionary with stats
        """
        return {
            "total_trades": self.total_trades,
            "total_profit_sol": self.total_profit,
            "total_volume_sol": self.total_volume,
            "average_profit_per_trade": (
                self.total_profit / self.total_trades
                if self.total_trades > 0
                else 0.0
            ),
            "is_active": self.is_active,
        }

