"""
Price Monitor - Monitor token prices across multiple DEXs.

This module continuously monitors prices for the same token
across different platforms to detect arbitrage opportunities.
"""

import asyncio
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime

from solders.pubkey import Pubkey

from core.client import SolanaClient
from interfaces.core import Platform
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PriceData:
    """Price data for a token on a specific platform."""
    
    platform: Platform
    token_mint: Pubkey
    price_sol: float
    timestamp: datetime
    liquidity_sol: float = 0.0  # Available liquidity in SOL
    volume_24h: float = 0.0  # 24h volume in SOL


class PriceMonitor:
    """
    Monitor token prices across multiple platforms.
    
    Continuously fetches prices for tokens across different DEXs
    to enable arbitrage opportunity detection.
    """
    
    def __init__(
        self,
        client: SolanaClient,
        platforms: List[Platform] = None,
        update_interval_seconds: float = 1.0,
    ):
        """Initialize price monitor.
        
        Args:
            client: Solana RPC client
            platforms: List of platforms to monitor (if None, monitor all)
            update_interval_seconds: How often to update prices
        """
        self.client = client
        self.platforms = platforms or [Platform.PUMP_FUN, Platform.LETS_BONK]
        self.update_interval_seconds = update_interval_seconds
        
        # Price cache: token_mint -> platform -> PriceData
        self.price_cache: Dict[str, Dict[Platform, PriceData]] = {}
        
        # Monitored tokens
        self.monitored_tokens: List[Pubkey] = []
        
        # Active state
        self.is_active = False
        self.monitor_task: Optional[asyncio.Task] = None
    
    def add_token(self, token_mint: Pubkey):
        """Add a token to monitor.
        
        Args:
            token_mint: Token mint address
        """
        if token_mint not in self.monitored_tokens:
            self.monitored_tokens.append(token_mint)
            logger.info(f"Added token {token_mint} to price monitoring")
    
    def remove_token(self, token_mint: Pubkey):
        """Remove a token from monitoring.
        
        Args:
            token_mint: Token mint address
        """
        if token_mint in self.monitored_tokens:
            self.monitored_tokens.remove(token_mint)
            token_str = str(token_mint)
            if token_str in self.price_cache:
                del self.price_cache[token_str]
            logger.info(f"Removed token {token_mint} from price monitoring")
    
    async def start(self):
        """Start price monitoring."""
        if self.is_active:
            logger.warning("Price monitor already active")
            return
        
        self.is_active = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Started price monitoring")
    
    async def stop(self):
        """Stop price monitoring."""
        self.is_active = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped price monitoring")
    
    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self.is_active:
            try:
                # Update prices for all monitored tokens
                for token_mint in self.monitored_tokens:
                    await self._update_prices(token_mint)
                
                # Wait before next update
                await asyncio.sleep(self.update_interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Error in price monitoring loop: {e}")
                await asyncio.sleep(5)
    
    async def _update_prices(self, token_mint: Pubkey):
        """Update prices for a token across all platforms.
        
        Args:
            token_mint: Token mint address
        """
        token_str = str(token_mint)
        
        if token_str not in self.price_cache:
            self.price_cache[token_str] = {}
        
        for platform in self.platforms:
            try:
                price_data = await self._get_price(token_mint, platform)
                if price_data:
                    self.price_cache[token_str][platform] = price_data
            except Exception as e:
                logger.debug(f"Error getting price for {token_mint} on {platform.value}: {e}")
    
    async def _get_price(self, token_mint: Pubkey, platform: Platform) -> Optional[PriceData]:
        """Get current price for a token on a platform.
        
        Args:
            token_mint: Token mint address
            platform: Platform to check
            
        Returns:
            PriceData or None if error
        """
        try:
            from platforms import get_platform_implementations
            
            implementations = get_platform_implementations(platform, self.client)
            address_provider = implementations.address_provider
            curve_manager = implementations.curve_manager
            
            # Get pool address
            pool_address = address_provider.derive_pool_address(token_mint)
            
            # Get price
            price = await curve_manager.calculate_price(pool_address)
            
            # Get liquidity (approximate from reserves)
            pool_state = await curve_manager.get_pool_state(pool_address)
            liquidity = pool_state.get("virtual_sol_reserves", 0) / 1_000_000_000  # Convert to SOL
            
            return PriceData(
                platform=platform,
                token_mint=token_mint,
                price_sol=price,
                timestamp=datetime.utcnow(),
                liquidity_sol=liquidity,
            )
            
        except Exception as e:
            logger.debug(f"Error getting price for {token_mint} on {platform.value}: {e}")
            return None
    
    def get_price(self, token_mint: Pubkey, platform: Platform) -> Optional[PriceData]:
        """Get cached price for a token on a platform.
        
        Args:
            token_mint: Token mint address
            platform: Platform
            
        Returns:
            PriceData or None if not available
        """
        token_str = str(token_mint)
        if token_str in self.price_cache:
            return self.price_cache[token_str].get(platform)
        return None
    
    def get_all_prices(self, token_mint: Pubkey) -> Dict[Platform, PriceData]:
        """Get all cached prices for a token across platforms.
        
        Args:
            token_mint: Token mint address
            
        Returns:
            Dictionary of platform -> PriceData
        """
        token_str = str(token_mint)
        if token_str in self.price_cache:
            return self.price_cache[token_str].copy()
        return {}
    
    def find_price_difference(
        self, token_mint: Pubkey, min_difference_percentage: float = 0.01
    ) -> Optional[tuple[Platform, Platform, float]]:
        """Find price difference between platforms.
        
        Args:
            token_mint: Token mint address
            min_difference_percentage: Minimum difference to consider (0.01 = 1%)
            
        Returns:
            Tuple of (buy_platform, sell_platform, profit_percentage) or None
        """
        prices = self.get_all_prices(token_mint)
        
        if len(prices) < 2:
            return None
        
        # Find best buy and sell prices
        best_buy_platform = None
        best_buy_price = float('inf')
        best_sell_platform = None
        best_sell_price = 0.0
        
        for platform, price_data in prices.items():
            if price_data.price_sol < best_buy_price:
                best_buy_price = price_data.price_sol
                best_buy_platform = platform
            if price_data.price_sol > best_sell_price:
                best_sell_price = price_data.price_sol
                best_sell_platform = platform
        
        if best_buy_platform is None or best_sell_platform is None:
            return None
        
        if best_buy_platform == best_sell_platform:
            return None
        
        # Calculate profit percentage
        profit_percentage = (best_sell_price - best_buy_price) / best_buy_price
        
        if profit_percentage >= min_difference_percentage:
            return (best_buy_platform, best_sell_platform, profit_percentage)
        
        return None

