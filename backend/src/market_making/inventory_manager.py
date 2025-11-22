"""
Inventory Manager - Track and manage token and SOL inventory for market making.

This module manages the inventory state, tracking balances and ratios
to maintain target allocations for market making.
"""

from dataclasses import dataclass
from typing import Optional

from solders.pubkey import Pubkey

from core.client import SolanaClient
from core.wallet import Wallet
from core.pubkeys import LAMPORTS_PER_SOL, TOKEN_DECIMALS
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class InventoryState:
    """Current inventory state."""
    
    sol_balance: float
    token_balance: float
    token_price: float
    total_value: float
    sol_ratio: float  # Ratio of SOL to total value (0.0 to 1.0)
    token_ratio: float  # Ratio of tokens to total value (0.0 to 1.0)


class InventoryManager:
    """
    Manage inventory for market making.
    
    Tracks SOL and token balances, calculates ratios,
    and determines when rebalancing is needed.
    """
    
    def __init__(
        self,
        client: SolanaClient,
        wallet: Wallet,
        token_mint: Pubkey,
        target_sol_ratio: float = 0.5,
        min_sol_balance: float = 0.1,
        min_token_balance: float = 0.0,
    ):
        """Initialize inventory manager.
        
        Args:
            client: Solana RPC client
            wallet: Wallet to track
            token_mint: Token mint address
            target_sol_ratio: Target ratio of SOL to total value (0.5 = 50%)
            min_sol_balance: Minimum SOL to keep
            min_token_balance: Minimum tokens to keep
        """
        self.client = client
        self.wallet = wallet
        self.token_mint = token_mint
        self.target_sol_ratio = target_sol_ratio
        self.min_sol_balance = min_sol_balance
        self.min_token_balance = min_token_balance
    
    async def get_inventory_state(self) -> InventoryState:
        """Get current inventory state.
        
        Returns:
            InventoryState with current balances and ratios
        """
        try:
            # Get SOL balance
            sol_balance = await self._get_sol_balance()
            
            # Get token balance
            token_balance = await self._get_token_balance()
            
            # Get token price
            token_price = await self._get_token_price()
            
            # Calculate total value
            token_value = token_balance * token_price
            total_value = sol_balance + token_value
            
            # Calculate ratios
            sol_ratio = sol_balance / total_value if total_value > 0 else 0.0
            token_ratio = token_value / total_value if total_value > 0 else 0.0
            
            return InventoryState(
                sol_balance=sol_balance,
                token_balance=token_balance,
                token_price=token_price,
                total_value=total_value,
                sol_ratio=sol_ratio,
                token_ratio=token_ratio,
            )
            
        except Exception as e:
            logger.exception(f"Error getting inventory state: {e}")
            # Return default state on error
            return InventoryState(
                sol_balance=0.0,
                token_balance=0.0,
                token_price=0.0,
                total_value=0.0,
                sol_ratio=0.0,
                token_ratio=0.0,
            )
    
    async def _get_sol_balance(self) -> float:
        """Get SOL balance for wallet.
        
        Returns:
            SOL balance
        """
        try:
            client = await self.client.get_client()
            balance_response = await client.get_balance(self.wallet.pubkey())
            balance_lamports = balance_response.value
            return balance_lamports / LAMPORTS_PER_SOL
        except Exception as e:
            logger.exception(f"Error getting SOL balance: {e}")
            return 0.0
    
    async def _get_token_balance(self) -> float:
        """Get token balance for wallet.
        
        Returns:
            Token balance
        """
        try:
            from spl.token.instructions import get_associated_token_address
            
            ata = get_associated_token_address(self.wallet.pubkey(), self.token_mint)
            
            # Get account info
            account_info = await self.client.get_account_info(ata)
            
            if account_info and account_info.data and len(account_info.data) >= 72:
                # Parse token balance
                amount_bytes = account_info.data[64:72]
                balance_raw = int.from_bytes(amount_bytes, byteorder='little', signed=False)
                return balance_raw / 10**TOKEN_DECIMALS
            else:
                return 0.0
                
        except Exception as e:
            logger.debug(f"Token account may not exist: {e}")
            return 0.0
    
    async def _get_token_price(self) -> float:
        """Get current token price.
        
        Returns:
            Token price in SOL per token
        """
        try:
            from platforms import get_platform_implementations
            from interfaces.core import Platform
            
            # Detect platform (assume pump.fun for now)
            platform = Platform.PUMP_FUN
            implementations = get_platform_implementations(platform, self.client)
            address_provider = implementations.address_provider
            curve_manager = implementations.curve_manager
            
            bonding_curve = address_provider.derive_pool_address(self.token_mint)
            price = await curve_manager.calculate_price(bonding_curve)
            
            return price
            
        except Exception as e:
            logger.exception(f"Error getting token price: {e}")
            return 0.0
    
    def calculate_rebalance_needed(self, inventory: InventoryState) -> tuple[bool, float, float]:
        """Calculate if rebalancing is needed and by how much.
        
        Args:
            inventory: Current inventory state
            
        Returns:
            Tuple of (needs_rebalance, sol_adjustment, token_adjustment)
            - sol_adjustment: Positive = need to buy tokens, Negative = need to sell tokens
            - token_adjustment: Positive = need to sell tokens, Negative = need to buy tokens
        """
        target_sol_value = inventory.total_value * self.target_sol_ratio
        target_token_value = inventory.total_value * (1 - self.target_sol_ratio)
        
        current_sol_value = inventory.sol_balance
        current_token_value = inventory.token_balance * inventory.token_price
        
        sol_deviation = current_sol_value - target_sol_value
        token_deviation = current_token_value - target_token_value
        
        # Rebalance threshold (10% of total value)
        threshold = inventory.total_value * 0.1
        
        needs_rebalance = abs(sol_deviation) > threshold or abs(token_deviation) > threshold
        
        return needs_rebalance, sol_deviation, token_deviation

