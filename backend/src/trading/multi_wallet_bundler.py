"""
Multi-Wallet Bundler - Coordinate transactions across multiple wallets using Jito.

This module implements multi-wallet operations inspired by the Solana Bundler Tool:
https://github.com/alexisssol/Solana-Bundler-tool

Features:
- Multi-wallet coordinated buys/sells
- Jito bundle submission for atomic execution
- Tip optimization for bundle landing
- Percentage-based selling
- WSOL management
"""

import asyncio
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from solders.pubkey import Pubkey
from solders.transaction import Transaction

from core.client import SolanaClient
from core.wallet import Wallet
from mev.jito_integration import JitoBundleManager, BundleResult
from volume.wallet_pool_manager import WalletPoolManager
from interfaces.core import TokenInfo, Platform
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class BundleExecutionResult:
    """Result of multi-wallet bundle execution."""
    
    success: bool
    bundle_id: Optional[str] = None
    transactions_submitted: int = 0
    tip_paid: int = 0
    error_message: Optional[str] = None
    wallet_results: Dict[int, bool] = None  # wallet_index -> success


class MultiWalletBundler:
    """
    Coordinate transactions across multiple wallets using Jito bundles.
    
    Inspired by: https://github.com/alexisssol/Solana-Bundler-tool
    
    This class enables atomic execution of transactions across multiple wallets,
    perfect for token launches, volume generation, and coordinated trading.
    """
    
    def __init__(
        self,
        client: SolanaClient,
        wallet_pool: WalletPoolManager,
        jito_manager: Optional[JitoBundleManager] = None,
        initial_tip_lamports: int = 100_000_000,  # 0.1 SOL
        max_tip_lamports: int = 1_000_000_000,  # 1 SOL
        tip_increment: int = 50_000_000,  # 0.05 SOL
    ):
        """Initialize multi-wallet bundler.
        
        Args:
            client: Solana RPC client
            wallet_pool: Wallet pool manager
            jito_manager: Jito bundle manager (creates if None)
            initial_tip_lamports: Initial tip amount
            max_tip_lamports: Maximum tip amount
            tip_increment: Tip increment for retries
        """
        self.client = client
        self.wallet_pool = wallet_pool
        
        if jito_manager is None:
            self.jito_manager = JitoBundleManager()
        else:
            self.jito_manager = jito_manager
        
        self.initial_tip = initial_tip_lamports
        self.max_tip = max_tip_lamports
        self.tip_increment = tip_increment
        
        self.executed_bundles: List[BundleExecutionResult] = []
        self.total_bundles = 0
        self.successful_bundles = 0
    
    async def execute_multi_wallet_buy(
        self,
        token_info: TokenInfo,
        amount_per_wallet: float,
        wallet_indices: Optional[List[int]] = None,
        tip_lamports: Optional[int] = None,
    ) -> BundleExecutionResult:
        """Execute coordinated buy across multiple wallets.
        
        Args:
            token_info: Token to buy
            amount_per_wallet: Amount per wallet in SOL
            wallet_indices: Specific wallets to use (None = all)
            tip_lamports: Tip amount (None = use initial_tip)
            
        Returns:
            BundleExecutionResult
        """
        try:
            # Get wallets to use
            if wallet_indices is None:
                wallet_indices = list(range(self.wallet_pool.get_wallet_count()))
            
            logger.info(
                f"Building multi-wallet buy bundle: {len(wallet_indices)} wallets, "
                f"{amount_per_wallet} SOL each"
            )
            
            # Build transactions for all wallets
            transactions: List[Transaction] = []
            wallet_tx_map: Dict[int, Transaction] = {}
            
            for wallet_idx in wallet_indices:
                try:
                    wallet = self.wallet_pool.get_wallet(wallet_idx)
                    tx = await self._build_buy_transaction(
                        wallet, token_info, amount_per_wallet
                    )
                    transactions.append(tx)
                    wallet_tx_map[wallet_idx] = tx
                except Exception as e:
                    logger.warning(
                        f"Failed to build transaction for wallet {wallet_idx}: {e}"
                    )
                    continue
            
            if not transactions:
                return BundleExecutionResult(
                    success=False,
                    error_message="No transactions built"
                )
            
            # Submit bundle with retry logic
            tip = tip_lamports or self.initial_tip
            result = await self._submit_bundle_with_retry(
                transactions, tip, max_retries=3
            )
            
            if result.success:
                # Mark all wallets as successful
                wallet_results = {
                    idx: True for idx in wallet_indices[:len(transactions)]
                }
                
                bundle_result = BundleExecutionResult(
                    success=True,
                    bundle_id=result.bundle_id,
                    transactions_submitted=len(transactions),
                    tip_paid=tip,
                    wallet_results=wallet_results,
                )
                
                self.executed_bundles.append(bundle_result)
                self.total_bundles += 1
                self.successful_bundles += 1
                
                logger.info(
                    f"Multi-wallet buy successful! Bundle: {result.bundle_id}, "
                    f"Wallets: {len(transactions)}, Tip: {tip / 1e9:.6f} SOL"
                )
                
                return bundle_result
            else:
                return BundleExecutionResult(
                    success=False,
                    error_message=result.error_message,
                    transactions_submitted=len(transactions),
                    tip_paid=tip,
                )
                
        except Exception as e:
            logger.exception(f"Error in multi-wallet buy: {e}")
            return BundleExecutionResult(
                success=False,
                error_message=str(e)
            )
    
    async def execute_percentage_sell(
        self,
        token_info: TokenInfo,
        percentage: float,  # 0.0 to 1.0
        wallet_indices: Optional[List[int]] = None,
        tip_lamports: Optional[int] = None,
    ) -> BundleExecutionResult:
        """Execute percentage-based sell across multiple wallets.
        
        Sells a specific percentage of tokens from each wallet.
        Inspired by the Solana Bundler Tool's percentage selling.
        
        Args:
            token_info: Token to sell
            percentage: Percentage to sell (0.0 to 1.0)
            wallet_indices: Specific wallets to use (None = all)
            tip_lamports: Tip amount
            
        Returns:
            BundleExecutionResult
        """
        try:
            # Get wallets to use
            if wallet_indices is None:
                wallet_indices = list(range(self.wallet_pool.get_wallet_count()))
            
            logger.info(
                f"Building percentage sell bundle: {len(wallet_indices)} wallets, "
                f"{percentage * 100}% each"
            )
            
            # Build transactions for all wallets
            transactions: List[Transaction] = []
            
            for wallet_idx in wallet_indices:
                try:
                    wallet = self.wallet_pool.get_wallet(wallet_idx)
                    
                    # Get token balance
                    token_balance = await self._get_token_balance(
                        wallet, token_info.mint
                    )
                    
                    # Calculate sell amount
                    sell_amount = int(token_balance * percentage)
                    
                    if sell_amount <= 0:
                        continue
                    
                    # Build sell transaction
                    tx = await self._build_sell_transaction(
                        wallet, token_info, sell_amount
                    )
                    transactions.append(tx)
                    
                except Exception as e:
                    logger.warning(
                        f"Failed to build sell transaction for wallet {wallet_idx}: {e}"
                    )
                    continue
            
            if not transactions:
                return BundleExecutionResult(
                    success=False,
                    error_message="No transactions built"
                )
            
            # Submit bundle
            tip = tip_lamports or self.initial_tip
            result = await self._submit_bundle_with_retry(
                transactions, tip, max_retries=3
            )
            
            if result.success:
                bundle_result = BundleExecutionResult(
                    success=True,
                    bundle_id=result.bundle_id,
                    transactions_submitted=len(transactions),
                    tip_paid=tip,
                )
                
                self.executed_bundles.append(bundle_result)
                self.total_bundles += 1
                self.successful_bundles += 1
                
                logger.info(
                    f"Percentage sell successful! Bundle: {result.bundle_id}, "
                    f"Wallets: {len(transactions)}, Percentage: {percentage * 100}%"
                )
                
                return bundle_result
            else:
                return BundleExecutionResult(
                    success=False,
                    error_message=result.error_message,
                    transactions_submitted=len(transactions),
                )
                
        except Exception as e:
            logger.exception(f"Error in percentage sell: {e}")
            return BundleExecutionResult(
                success=False,
                error_message=str(e)
            )
    
    async def _build_buy_transaction(
        self, wallet: Wallet, token_info: TokenInfo, amount: float
    ) -> Transaction:
        """Build buy transaction for a wallet.
        
        Args:
            wallet: Wallet to use
            token_info: Token to buy
            amount: Amount in SOL
            
        Returns:
            Transaction (built and signed, ready for bundling)
        """
        try:
            from platforms import get_platform_implementations
            from core.pubkeys import LAMPORTS_PER_SOL, TOKEN_DECIMALS
            from core.priority_fee.manager import PriorityFeeManager
            
            # Get platform-specific implementations
            implementations = get_platform_implementations(
                token_info.platform, self.client
            )
            address_provider = implementations.address_provider
            instruction_builder = implementations.instruction_builder
            curve_manager = implementations.curve_manager
            
            # Convert amount to lamports
            amount_lamports = int(amount * LAMPORTS_PER_SOL)
            
            # Get pool address for price calculation
            pool_address = address_provider.derive_pool_address(token_info.mint)
            
            # Calculate token amount
            token_price_sol = await curve_manager.calculate_price(pool_address)
            token_amount = amount / token_price_sol if token_price_sol > 0 else 0
            
            # Calculate minimum token amount with slippage (30%)
            slippage = 0.3
            minimum_token_amount = token_amount * (1 - slippage)
            minimum_token_amount_raw = int(minimum_token_amount * 10**TOKEN_DECIMALS)
            
            # Calculate maximum SOL to spend with slippage
            max_amount_lamports = int(amount_lamports * (1 + slippage))
            
            # Build buy instructions
            instructions = await instruction_builder.build_buy_instruction(
                token_info,
                wallet.pubkey,
                max_amount_lamports,  # amount_in (SOL)
                minimum_token_amount_raw,  # minimum_amount_out (tokens)
                address_provider,
            )
            
            # Get accounts for priority fee calculation
            priority_accounts = instruction_builder.get_required_accounts_for_buy(
                token_info, wallet.pubkey, address_provider
            )
            
            # Calculate priority fee (low for bundles)
            fee_manager = PriorityFeeManager(
                client=self.client,
                enable_fixed_fee=True,
                fixed_fee=100_000,  # Low priority for bundle
            )
            priority_fee = await fee_manager.calculate_priority_fee(priority_accounts)
            
            # Get compute unit limit
            compute_unit_limit = instruction_builder.get_buy_compute_unit_limit()
            
            # Build transaction (don't send)
            transaction = await self.client.build_transaction(
                instructions=instructions,
                signer_keypair=wallet.keypair,
                priority_fee=priority_fee,
                compute_unit_limit=compute_unit_limit,
            )
            
            logger.debug(
                f"Built buy transaction for wallet {wallet.pubkey}: "
                f"{amount} SOL -> ~{token_amount:.6f} tokens"
            )
            
            return transaction
            
        except Exception as e:
            logger.exception(f"Error building buy transaction: {e}")
            raise
    
    async def _build_sell_transaction(
        self, wallet: Wallet, token_info: TokenInfo, token_amount: int
    ) -> Transaction:
        """Build sell transaction for a wallet.
        
        Args:
            wallet: Wallet to use
            token_info: Token to sell
            token_amount: Amount in tokens (raw units)
            
        Returns:
            Transaction (built and signed, ready for bundling)
        """
        try:
            from platforms import get_platform_implementations
            from core.pubkeys import LAMPORTS_PER_SOL, TOKEN_DECIMALS
            from core.priority_fee.manager import PriorityFeeManager
            
            # Get platform-specific implementations
            implementations = get_platform_implementations(
                token_info.platform, self.client
            )
            address_provider = implementations.address_provider
            instruction_builder = implementations.instruction_builder
            curve_manager = implementations.curve_manager
            
            # Get pool address for price calculation
            pool_address = address_provider.derive_pool_address(token_info.mint)
            
            # Calculate expected SOL output
            expected_sol_output = await curve_manager.calculate_sell_amount_out(
                pool_address, token_amount
            )
            
            # Calculate minimum SOL output with slippage (30%)
            slippage = 0.3
            min_sol_output = int(expected_sol_output * (1 - slippage))
            
            # Build sell instructions
            instructions = await instruction_builder.build_sell_instruction(
                token_info,
                wallet.pubkey,
                token_amount,  # amount_in (tokens)
                min_sol_output,  # minimum_amount_out (SOL)
                address_provider,
            )
            
            # Get accounts for priority fee calculation
            priority_accounts = instruction_builder.get_required_accounts_for_sell(
                token_info, wallet.pubkey, address_provider
            )
            
            # Calculate priority fee (low for bundles)
            fee_manager = PriorityFeeManager(
                client=self.client,
                enable_fixed_fee=True,
                fixed_fee=100_000,  # Low priority for bundle
            )
            priority_fee = await fee_manager.calculate_priority_fee(priority_accounts)
            
            # Get compute unit limit
            compute_unit_limit = instruction_builder.get_sell_compute_unit_limit()
            
            # Build transaction (don't send)
            transaction = await self.client.build_transaction(
                instructions=instructions,
                signer_keypair=wallet.keypair,
                priority_fee=priority_fee,
                compute_unit_limit=compute_unit_limit,
            )
            
            logger.debug(
                f"Built sell transaction for wallet {wallet.pubkey}: "
                f"{token_amount / 10**TOKEN_DECIMALS:.6f} tokens -> "
                f"~{expected_sol_output / LAMPORTS_PER_SOL:.6f} SOL"
            )
            
            return transaction
            
        except Exception as e:
            logger.exception(f"Error building sell transaction: {e}")
            raise
    
    async def _get_token_balance(self, wallet: Wallet, mint: Pubkey) -> int:
        """Get token balance for a wallet.
        
        Args:
            wallet: Wallet to check
            mint: Token mint
            
        Returns:
            Token balance in raw units
        """
        try:
            from spl.token.instructions import get_associated_token_address
            from spl.token.client import Token
            
            # Get associated token account
            ata = get_associated_token_address(wallet.pubkey(), mint)
            
            # Get account info
            account_info = await self.client.get_account_info(ata)
            
            if account_info and account_info.data:
                # Parse token account data
                # Token account data structure:
                # - mint: 32 bytes
                # - owner: 32 bytes
                # - amount: 8 bytes (u64)
                
                account_data = account_info.data
                if len(account_data) >= 72:  # Minimum size for token account
                    # Amount is at offset 64 (32 + 32)
                    amount_bytes = account_data[64:72]
                    amount = int.from_bytes(amount_bytes, byteorder='little', signed=False)
                    return amount
            
            return 0
            
        except Exception as e:
            logger.debug(f"Token account may not exist: {e}")
            return 0
    
    async def _submit_bundle_with_retry(
        self,
        transactions: List[Transaction],
        initial_tip: int,
        max_retries: int = 3,
    ) -> BundleResult:
        """Submit bundle with retry logic and tip optimization.
        
        Inspired by the Solana Bundler Tool's retry approach.
        
        Args:
            transactions: Transactions to bundle
            initial_tip: Initial tip amount
            max_retries: Maximum retry attempts
            
        Returns:
            BundleResult
        """
        tip = initial_tip
        
        for attempt in range(max_retries):
            logger.info(
                f"Submitting bundle (attempt {attempt + 1}/{max_retries}), "
                f"tip: {tip / 1e9:.6f} SOL"
            )
            
            result = await self.jito_manager.submit_custom_bundle(
                transactions, tip_lamports=tip
            )
            
            if result.success:
                logger.info(f"Bundle landed successfully: {result.bundle_id}")
                return result
            
            # Increase tip for next attempt
            if attempt < max_retries - 1:
                tip = min(tip + self.tip_increment, self.max_tip)
                logger.warning(
                    f"Bundle failed, retrying with higher tip: {tip / 1e9:.6f} SOL"
                )
                await asyncio.sleep(1)  # Brief delay before retry
        
        logger.error(f"Bundle failed after {max_retries} attempts")
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """Get bundler statistics.
        
        Returns:
            Dictionary with stats
        """
        success_rate = (
            self.successful_bundles / self.total_bundles
            if self.total_bundles > 0
            else 0.0
        )
        
        return {
            "total_bundles": self.total_bundles,
            "successful_bundles": self.successful_bundles,
            "success_rate": success_rate,
            "wallet_count": self.wallet_pool.get_wallet_count(),
        }

