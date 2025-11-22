"""
Arbitrage Engine - Execute arbitrage trades across DEXs.

This module detects and executes arbitrage opportunities by:
- Monitoring prices across platforms
- Calculating profitability after fees
- Executing buy/sell trades atomically
- Managing risk and capital
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime

from solders.pubkey import Pubkey

from core.client import SolanaClient
from core.wallet import Wallet
from interfaces.core import Platform, TokenInfo
from arbitrage.price_monitor import PriceMonitor, PriceData
from trading.platform_aware import PlatformAwareBuyer, PlatformAwareSeller
from core.priority_fee.manager import PriorityFeeManager
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ArbitrageConfig:
    """Configuration for arbitrage trading."""
    
    # Token to arbitrage (if None, monitor all tokens)
    token_mint: Optional[Pubkey] = None
    
    # Platforms to monitor
    platforms: List[Platform] = None
    
    # Profitability thresholds
    min_profit_percentage: float = 0.02  # 2% minimum profit
    min_profit_sol: float = 0.01  # 0.01 SOL minimum profit
    
    # Trading parameters
    max_trade_size_sol: float = 0.5  # Maximum trade size
    min_trade_size_sol: float = 0.05  # Minimum trade size
    
    # Fee estimation
    transaction_fee_sol: float = 0.000005  # ~0.000005 SOL per transaction
    slippage: float = 0.01  # 1% slippage tolerance
    
    # Risk management
    max_position_size_sol: float = 2.0  # Maximum total position
    max_concurrent_trades: int = 3  # Maximum concurrent arbitrage trades
    
    # Execution
    priority_fee: int = 200_000  # Priority fee in microlamports
    use_atomic_execution: bool = True  # Use Jito for atomic execution


@dataclass
class ArbitrageResult:
    """Result of an arbitrage execution."""
    
    success: bool
    token_mint: Pubkey
    buy_platform: Platform
    sell_platform: Platform
    amount_sol: float
    profit_sol: float
    profit_percentage: float
    buy_signature: Optional[str] = None
    sell_signature: Optional[str] = None
    timestamp: datetime = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class ArbitrageEngine:
    """
    Execute arbitrage trades across multiple DEXs.
    
    Monitors prices, detects opportunities, and executes
    profitable arbitrage trades.
    """
    
    def __init__(
        self,
        client: SolanaClient,
        wallet: Wallet,
        config: ArbitrageConfig,
    ):
        """Initialize arbitrage engine.
        
        Args:
            client: Solana RPC client
            wallet: Wallet to use for trading
            config: Arbitrage configuration
        """
        self.client = client
        self.wallet = wallet
        self.config = config
        
        # Initialize price monitor
        self.price_monitor = PriceMonitor(
            client=client,
            platforms=config.platforms or [Platform.PUMP_FUN, Platform.LETS_BONK],
            update_interval_seconds=1.0,
        )
        
        # Add token to monitor if specified
        if config.token_mint:
            self.price_monitor.add_token(config.token_mint)
        
        # Initialize priority fee manager
        self.priority_fee_manager = PriorityFeeManager(
            client=client,
            enable_fixed_fee=True,
            fixed_fee=config.priority_fee,
        )
        
        # Statistics
        self.total_trades = 0
        self.successful_trades = 0
        self.total_profit = 0.0
        self.total_volume = 0.0
        
        # Active trades
        self.active_trades: Dict[str, asyncio.Task] = {}
        
        # Active state
        self.is_active = False
        self.arbitrage_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start arbitrage engine."""
        if self.is_active:
            logger.warning("Arbitrage engine already active")
            return
        
        self.is_active = True
        
        # Start price monitoring
        await self.price_monitor.start()
        
        # Start arbitrage loop
        self.arbitrage_task = asyncio.create_task(self._arbitrage_loop())
        
        logger.info("Started arbitrage engine")
    
    async def stop(self):
        """Stop arbitrage engine."""
        self.is_active = False
        
        # Stop price monitoring
        await self.price_monitor.stop()
        
        # Cancel arbitrage task
        if self.arbitrage_task:
            self.arbitrage_task.cancel()
            try:
                await self.arbitrage_task
            except asyncio.CancelledError:
                pass
        
        # Cancel active trades
        for trade_id, task in self.active_trades.items():
            task.cancel()
        
        logger.info("Stopped arbitrage engine")
    
    def add_token(self, token_mint: Pubkey):
        """Add a token to monitor for arbitrage.
        
        Args:
            token_mint: Token mint address
        """
        self.price_monitor.add_token(token_mint)
    
    async def _arbitrage_loop(self):
        """Main arbitrage detection and execution loop."""
        while self.is_active:
            try:
                # Check for arbitrage opportunities
                if len(self.active_trades) < self.config.max_concurrent_trades:
                    opportunity = await self._detect_opportunity()
                    
                    if opportunity:
                        # Execute arbitrage
                        token_mint, buy_platform, sell_platform, trade_size = opportunity
                        trade_id = f"{token_mint}_{buy_platform.value}_{sell_platform.value}_{datetime.utcnow().timestamp()}"
                        task = asyncio.create_task(
                            self._execute_arbitrage(token_mint, buy_platform, sell_platform, trade_size)
                        )
                        self.active_trades[trade_id] = task
                        
                        # Clean up completed trades
                        self._cleanup_completed_trades()
                
                # Wait before next check
                await asyncio.sleep(0.5)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Error in arbitrage loop: {e}")
                await asyncio.sleep(5)
    
    async def _detect_opportunity(self) -> Optional[tuple[Pubkey, Platform, Platform, float]]:
        """Detect arbitrage opportunity.
        
        Returns:
            Tuple of (token_mint, buy_platform, sell_platform, profit_percentage) or None
        """
        # Get monitored tokens
        tokens = self.config.token_mint and [self.config.token_mint] or self.price_monitor.monitored_tokens
        
        for token_mint in tokens:
            # Find price difference
            price_diff = self.price_monitor.find_price_difference(
                token_mint, self.config.min_profit_percentage
            )
            
            if price_diff:
                buy_platform, sell_platform, profit_percentage = price_diff
                
                # Get prices for profitability calculation
                buy_price_data = self.price_monitor.get_price(token_mint, buy_platform)
                sell_price_data = self.price_monitor.get_price(token_mint, sell_platform)
                
                if not buy_price_data or not sell_price_data:
                    continue
                
                # Calculate profitability for different trade sizes
                for trade_size in [self.config.min_trade_size_sol, self.config.max_trade_size_sol]:
                    profit = self._calculate_profit(
                        trade_size, buy_price_data.price_sol, sell_price_data.price_sol
                    )
                    
                    if profit >= self.config.min_profit_sol:
                        return (token_mint, buy_platform, sell_platform, trade_size)
        
        return None
    
    def _calculate_profit(
        self, trade_size_sol: float, buy_price: float, sell_price: float
    ) -> float:
        """Calculate profit after fees and slippage.
        
        Args:
            trade_size_sol: Trade size in SOL
            buy_price: Buy price per token
            sell_price: Sell price per token
            
        Returns:
            Profit in SOL after fees
        """
        # Calculate token amounts
        tokens_bought = trade_size_sol / buy_price
        sol_received = tokens_bought * sell_price
        
        # Apply slippage
        sol_received_after_slippage = sol_received * (1 - self.config.slippage)
        
        # Subtract fees (2 transactions: buy + sell)
        total_fees = self.config.transaction_fee_sol * 2
        
        # Calculate profit
        profit = sol_received_after_slippage - trade_size_sol - total_fees
        
        return profit
    
    async def _execute_arbitrage(
        self, token_mint: Pubkey, buy_platform: Platform, sell_platform: Platform, trade_size: float
    ) -> ArbitrageResult:
        """Execute an arbitrage trade.
        
        Args:
            token_mint: Token to arbitrage
            buy_platform: Platform to buy from
            sell_platform: Platform to sell on
            trade_size: Trade size in SOL
            
        Returns:
            ArbitrageResult
        """
        try:
            logger.info(
                f"Executing arbitrage: {token_mint} "
                f"Buy on {buy_platform.value}, Sell on {sell_platform.value}, "
                f"Size: {trade_size:.6f} SOL"
            )
            
            # Get prices
            buy_price_data = self.price_monitor.get_price(token_mint, buy_platform)
            sell_price_data = self.price_monitor.get_price(token_mint, sell_platform)
            
            if not buy_price_data or not sell_price_data:
                return ArbitrageResult(
                    success=False,
                    token_mint=token_mint,
                    buy_platform=buy_platform,
                    sell_platform=sell_platform,
                    amount_sol=trade_size,
                    profit_sol=0.0,
                    profit_percentage=0.0,
                    error_message="Price data not available"
                )
            
            # Calculate expected profit
            expected_profit = self._calculate_profit(
                trade_size, buy_price_data.price_sol, sell_price_data.price_sol
            )
            
            if expected_profit < self.config.min_profit_sol:
                return ArbitrageResult(
                    success=False,
                    token_mint=token_mint,
                    buy_platform=buy_platform,
                    sell_platform=sell_platform,
                    amount_sol=trade_size,
                    profit_sol=0.0,
                    profit_percentage=0.0,
                    error_message="Profit below threshold"
                )
            
            # Execute buy on buy_platform
            buy_result = await self._execute_buy(token_mint, buy_platform, trade_size)
            
            if not buy_result.success:
                return ArbitrageResult(
                    success=False,
                    token_mint=token_mint,
                    buy_platform=buy_platform,
                    sell_platform=sell_platform,
                    amount_sol=trade_size,
                    profit_sol=0.0,
                    profit_percentage=0.0,
                    error_message=f"Buy failed: {buy_result.error_message}"
                )
            
            # Wait briefly for buy to settle
            await asyncio.sleep(0.5)
            
            # Execute sell on sell_platform
            sell_result = await self._execute_sell(token_mint, sell_platform)
            
            if not sell_result.success:
                return ArbitrageResult(
                    success=False,
                    token_mint=token_mint,
                    buy_platform=buy_platform,
                    sell_platform=sell_platform,
                    amount_sol=trade_size,
                    profit_sol=0.0,
                    profit_percentage=0.0,
                    error_message=f"Sell failed: {sell_result.error_message}"
                )
            
            # Calculate actual profit
            tokens_bought = buy_result.amount or 0.0
            sol_received = sell_result.amount * (sell_result.price or 0.0) if sell_result.amount else 0.0
            actual_profit = sol_received - trade_size - (self.config.transaction_fee_sol * 2)
            profit_percentage = (actual_profit / trade_size) * 100 if trade_size > 0 else 0.0
            
            result = ArbitrageResult(
                success=True,
                token_mint=token_mint,
                buy_platform=buy_platform,
                sell_platform=sell_platform,
                amount_sol=trade_size,
                profit_sol=actual_profit,
                profit_percentage=profit_percentage,
                buy_signature=buy_result.tx_signature,
                sell_signature=sell_result.tx_signature,
            )
            
            # Update statistics
            self.total_trades += 1
            self.successful_trades += 1
            self.total_profit += actual_profit
            self.total_volume += trade_size
            
            logger.info(
                f"Arbitrage successful! Profit: {actual_profit:.6f} SOL "
                f"({profit_percentage:.2f}%)"
            )
            
            return result
            
        except Exception as e:
            logger.exception(f"Error executing arbitrage: {e}")
            return ArbitrageResult(
                success=False,
                token_mint=token_mint,
                buy_platform=buy_platform,
                sell_platform=sell_platform,
                amount_sol=trade_size,
                profit_sol=0.0,
                profit_percentage=0.0,
                error_message=str(e)
            )
    
    async def _execute_buy(
        self, token_mint: Pubkey, platform: Platform, amount_sol: float
    ):
        """Execute buy on a platform.
        
        Args:
            token_mint: Token to buy
            platform: Platform to buy on
            amount_sol: Amount in SOL
            
        Returns:
            TradeResult
        """
        try:
            # Get token info
            token_info = await self._get_token_info(token_mint, platform)
            if not token_info:
                from trading.base import TradeResult
                return TradeResult(
                    success=False,
                    platform=platform,
                    error_message="Could not get token info"
                )
            
            # Execute buy
            buyer = PlatformAwareBuyer(
                client=self.client,
                wallet=self.wallet,
                priority_fee_manager=self.priority_fee_manager,
                amount=amount_sol,
                slippage=self.config.slippage,
            )
            
            return await buyer.execute(token_info)
            
        except Exception as e:
            logger.exception(f"Error executing buy: {e}")
            from trading.base import TradeResult
            return TradeResult(
                success=False,
                platform=platform,
                error_message=str(e)
            )
    
    async def _execute_sell(self, token_mint: Pubkey, platform: Platform):
        """Execute sell on a platform.
        
        Args:
            token_mint: Token to sell
            platform: Platform to sell on
            
        Returns:
            TradeResult
        """
        try:
            # Get token info
            token_info = await self._get_token_info(token_mint, platform)
            if not token_info:
                from trading.base import TradeResult
                return TradeResult(
                    success=False,
                    platform=platform,
                    error_message="Could not get token info"
                )
            
            # Execute sell
            seller = PlatformAwareSeller(
                client=self.client,
                wallet=self.wallet,
                priority_fee_manager=self.priority_fee_manager,
                slippage=self.config.slippage,
            )
            
            return await seller.execute(token_info)
            
        except Exception as e:
            logger.exception(f"Error executing sell: {e}")
            from trading.base import TradeResult
            return TradeResult(
                success=False,
                platform=platform,
                error_message=str(e)
            )
    
    async def _get_token_info(self, token_mint: Pubkey, platform: Platform) -> Optional[TokenInfo]:
        """Get token info for a platform.
        
        Args:
            token_mint: Token mint address
            platform: Platform
            
        Returns:
            TokenInfo or None if error
        """
        try:
            from platforms import get_platform_implementations
            
            implementations = get_platform_implementations(platform, self.client)
            address_provider = implementations.address_provider
            
            bonding_curve = address_provider.derive_pool_address(token_mint)
            associated_bonding_curve = address_provider.derive_associated_bonding_curve(
                token_mint, bonding_curve
            )
            
            return TokenInfo(
                name="Arbitrage Token",
                symbol="ARB",
                uri="",
                mint=token_mint,
                platform=platform,
                bonding_curve=bonding_curve,
                associated_bonding_curve=associated_bonding_curve,
                user=self.wallet.pubkey(),
            )
            
        except Exception as e:
            logger.exception(f"Error getting token info: {e}")
            return None
    
    def _cleanup_completed_trades(self):
        """Remove completed trades from active trades."""
        completed = []
        for trade_id, task in self.active_trades.items():
            if task.done():
                completed.append(trade_id)
        
        for trade_id in completed:
            del self.active_trades[trade_id]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get arbitrage statistics.
        
        Returns:
            Dictionary with stats
        """
        success_rate = (
            self.successful_trades / self.total_trades
            if self.total_trades > 0
            else 0.0
        )
        
        return {
            "total_trades": self.total_trades,
            "successful_trades": self.successful_trades,
            "success_rate": success_rate,
            "total_profit_sol": self.total_profit,
            "total_volume_sol": self.total_volume,
            "average_profit_per_trade": (
                self.total_profit / self.successful_trades
                if self.successful_trades > 0
                else 0.0
            ),
            "active_trades": len(self.active_trades),
            "is_active": self.is_active,
        }

