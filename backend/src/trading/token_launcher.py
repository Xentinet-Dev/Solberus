"""
Pumpfun Token Launcher - Launch pumpfun tokens with multiple wallets.
"""

import asyncio
import base58
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from solders.keypair import Keypair
from solders.pubkey import Pubkey

from core.client import SolanaClient
from core.wallet import Wallet
from interfaces.core import Platform, TokenInfo
from trading.multi_wallet_bundler import MultiWalletBundler
from volume.wallet_pool_manager import WalletPoolManager, WalletInfo
from mev.jito_integration import JitoBundleManager
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TokenLaunchConfig:
    """Configuration for launching a token."""
    
    name: str
    symbol: str
    uri: str  # Metadata URI
    creator_wallet: str  # Private key of creator
    initial_buy_amount: float = 0.0  # SOL to buy immediately after creation
    num_wallets: int = 1  # Number of wallets to use for buying
    wallet_private_keys: Optional[List[str]] = None  # Optional: specific wallets to use
    buy_distribution: str = "equal"  # "equal", "weighted", "random"
    delay_between_buys: float = 0.5  # Seconds between buy transactions
    priority_fee: int = 1_000_000  # Priority fee in microlamports


@dataclass
class TokenLaunchResult:
    """Result of token launch."""
    
    success: bool
    mint_address: str
    bonding_curve_address: str
    creator_address: str
    transaction_signature: Optional[str] = None
    buy_results: List[Dict[str, Any]] = None
    error_message: Optional[str] = None


class PumpfunTokenLauncher:
    """
    Launches pumpfun tokens with support for multiple wallets.
    
    Features:
    - Create pumpfun tokens
    - Buy with multiple wallets
    - Configurable buy distribution
    - Automatic wallet management
    """
    
    def __init__(
        self,
        rpc_endpoint: str,
        wss_endpoint: Optional[str] = None,
        use_bundles: bool = True,
    ):
        """Initialize token launcher.
        
        Args:
            rpc_endpoint: Solana RPC endpoint
            wss_endpoint: Optional WebSocket endpoint
            use_bundles: Use Jito bundles for coordinated buys
        """
        self.client = SolanaClient(rpc_endpoint)
        self.wss_endpoint = wss_endpoint
        self.use_bundles = use_bundles
        
        # Initialize bundler if using bundles
        if use_bundles:
            try:
                jito_manager = JitoBundleManager()
                # Will create wallet pool when needed
                self.bundler = None  # Created when wallets are available
            except Exception as e:
                logger.warning(f"Failed to initialize bundler: {e}")
                self.use_bundles = False
                self.bundler = None
        else:
            self.bundler = None
        self.wallet_pool: WalletPoolManager | None = None
        
        logger.info("Pumpfun Token Launcher initialized")
    
    async def launch_token(
        self,
        config: TokenLaunchConfig,
    ) -> TokenLaunchResult:
        """Launch a pumpfun token.
        
        Args:
            config: Token launch configuration
            
        Returns:
            Token launch result
        """
        try:
            logger.info(f"Launching token: {config.name} ({config.symbol})")
            
            # Create creator wallet
            creator_wallet = Wallet(config.creator_wallet)
            creator_pubkey = creator_wallet.pubkey()
            
            # Generate mint keypair
            mint_keypair = Keypair()
            mint_address = str(mint_keypair.pubkey())
            
            logger.info(f"Mint address: {mint_address}")
            logger.info(f"Creator: {creator_pubkey}")
            
            # Create token on pumpfun
            # This would use the actual pumpfun program instruction
            # For now, this is a placeholder structure
            tx_signature = await self._create_token(
                mint_keypair,
                creator_wallet,
                config.name,
                config.symbol,
                config.uri,
            )
            
            if not tx_signature:
                return TokenLaunchResult(
                    success=False,
                    mint_address=mint_address,
                    bonding_curve_address="",
                    creator_address=str(creator_pubkey),
                    error_message="Failed to create token",
                )
            
            # Derive bonding curve address
            bonding_curve = self._derive_bonding_curve(mint_keypair.pubkey())
            
            logger.info(f"Token created successfully: {tx_signature}")
            logger.info(f"Bonding curve: {bonding_curve}")
            
            # Buy with multiple wallets if configured
            buy_results = []
            if config.initial_buy_amount > 0 and config.num_wallets > 0:
                buy_results = await self._buy_with_multiple_wallets(
                    mint_keypair.pubkey(),
                    bonding_curve,
                    config,
                )
            
            return TokenLaunchResult(
                success=True,
                mint_address=mint_address,
                bonding_curve_address=str(bonding_curve),
                creator_address=str(creator_pubkey),
                transaction_signature=tx_signature,
                buy_results=buy_results,
            )
        
        except Exception as e:
            logger.exception(f"Error launching token: {e}")
            return TokenLaunchResult(
                success=False,
                mint_address="",
                bonding_curve_address="",
                creator_address="",
                error_message=str(e),
            )
    
    async def _create_token(
        self,
        mint_keypair: Keypair,
        creator_wallet: Wallet,
        name: str,
        symbol: str,
        uri: str,
    ) -> Optional[str]:
        """Create token on pumpfun.
        
        Args:
            mint_keypair: Mint keypair
            creator_wallet: Creator wallet
            name: Token name
            symbol: Token symbol
            uri: Metadata URI
            
        Returns:
            Transaction signature if successful, None otherwise
        """
        try:
            # This would construct the actual pumpfun create instruction
            # Using the IDL and instruction builder from the codebase
            
            # Import here to avoid circular dependencies
            from platforms.pumpfun.instruction_builder import PumpFunInstructionBuilder
            
            instruction_builder = PumpFunInstructionBuilder(self.client)
            
            # Build create instruction
            # Note: This would need the actual instruction builder implementation
            # For now, we'll use the learning example pattern
            logger.info("Creating token transaction...")
            
            # Use the pattern from learning-examples/mint_and_buy.py
            # This is a placeholder - actual implementation would construct the full transaction
            # The real implementation would:
            # 1. Derive all required PDAs (bonding curve, metadata, etc.)
            # 2. Build the create instruction using the pumpfun IDL
            # 3. Sign and send the transaction
            
            # For now, return placeholder - full implementation would require
            # integrating with the actual pumpfun program instruction building
            logger.warning("Token creation is a placeholder - needs full implementation")
            return "placeholder_signature"
        
        except Exception as e:
            logger.exception(f"Error creating token: {e}")
            return None
    
    def _derive_bonding_curve(self, mint: Pubkey) -> Pubkey:
        """Derive bonding curve address from mint.
        
        Args:
            mint: Mint address
            
        Returns:
            Bonding curve address
        """
        # This would use the actual PDA derivation from pumpfun
        # For now, placeholder
        from platforms.pumpfun.address_provider import PumpFunAddressProvider
        
        address_provider = PumpFunAddressProvider()
        bonding_curve, _ = address_provider.get_bonding_curve_address(mint)
        
        return bonding_curve
    
    async def _buy_with_multiple_wallets(
        self,
        mint: Pubkey,
        bonding_curve: Pubkey,
        config: TokenLaunchConfig,
    ) -> List[Dict[str, Any]]:
        """Buy token with multiple wallets.
        
        Args:
            mint: Mint address
            bonding_curve: Bonding curve address
            config: Launch configuration
            
        Returns:
            List of buy results
        """
        results = []
        
        # Get wallets
        wallets = await self._get_wallets(config)
        
        if not wallets:
            logger.warning("No wallets available for buying")
            return results
        
        # Calculate buy amounts per wallet
        buy_amounts = self._calculate_buy_amounts(
            config.initial_buy_amount,
            len(wallets),
            config.buy_distribution,
        )
        
        logger.info(f"Buying with {len(wallets)} wallets, total: {config.initial_buy_amount} SOL")
        
        # Try to use bundler for coordinated execution if available
        if self.use_bundles and len(wallets) > 1:
            try:
                # Create token info
                token_info = TokenInfo(
                    name=config.name,
                    symbol=config.symbol,
                    uri=config.uri,
                    mint=mint,
                    platform=Platform.PUMP_FUN,
                    bonding_curve=bonding_curve,
                    associated_bonding_curve=bonding_curve,
                    user=wallets[0].pubkey(),
                )
                
                bundle_results = await self._try_bundled_buy(
                    wallets, token_info, buy_amounts
                )
                if bundle_results is not None:
                    return bundle_results
                
            except Exception as e:
                logger.debug(f"Bundler not available, using individual execution: {e}")
        
        # Execute buys with delay (or use bundler if available)
        for i, (wallet, amount) in enumerate(zip(wallets, buy_amounts)):
            if amount <= 0:
                continue
            
            try:
                logger.info(f"Wallet {i+1}/{len(wallets)}: Buying {amount:.6f} SOL worth")
                
                # Build buy instruction
                from trading.platform_aware import PlatformAwareBuyer
                from core.priority_fee.manager import PriorityFeeManager
                
                fee_manager = PriorityFeeManager(
                    client=self.client,
                    enable_fixed_fee=True,
                    fixed_fee=config.priority_fee,
                )
                
                buyer = PlatformAwareBuyer(
                    client=self.client,
                    wallet=wallet,
                    priority_fee_manager=fee_manager,
                    amount=amount,
                    slippage=0.3,  # 30% slippage
                )
                
                # Create token info for buying
                token_info = TokenInfo(
                    name=config.name,
                    symbol=config.symbol,
                    uri=config.uri,
                    mint=mint,
                    platform=Platform.PUMP_FUN,
                    bonding_curve=bonding_curve,
                    associated_bonding_curve=bonding_curve,  # Simplified
                    user=wallet.pubkey(),
                )
                
                # Execute buy
                buy_result = await buyer.execute(token_info)
                
                results.append({
                    "wallet": str(wallet.pubkey()),
                    "amount": amount,
                    "success": buy_result.success,
                    "tx_signature": buy_result.tx_signature if buy_result.success else None,
                    "tokens_received": buy_result.amount if buy_result.success else 0,
                    "price": buy_result.price if buy_result.success else 0,
                    "error": buy_result.error_message if not buy_result.success else None,
                })
                
                # Delay between buys
                if i < len(wallets) - 1:
                    await asyncio.sleep(config.delay_between_buys)
            
            except Exception as e:
                logger.exception(f"Error buying with wallet {i+1}: {e}")
                results.append({
                    "wallet": str(wallet.pubkey()),
                    "amount": amount,
                    "success": False,
                    "error": str(e),
                })
        
        successful_buys = sum(1 for r in results if r.get("success", False))
        logger.info(f"Completed {successful_buys}/{len(wallets)} buys")
        
        return results
    
    async def _try_bundled_buy(
        self,
        wallets: List[Wallet],
        token_info: TokenInfo,
        buy_amounts: List[float],
    ) -> Optional[List[Dict[str, Any]]]:
        """Attempt to execute a bundled buy using the wallet pool."""
        if not self.use_bundles or len(wallets) <= 1:
            return None

        if not buy_amounts:
            return None

        # Bundler currently supports even distribution only
        first_amount = buy_amounts[0]
        if any(abs(amount - first_amount) > 1e-9 for amount in buy_amounts):
            logger.debug("Skipping bundled buy because amounts are not uniform")
            return None

        if first_amount <= 0:
            return None

        try:
            # Initialize wallet pool lazily
            if self.wallet_pool is None or self.wallet_pool.get_wallet_count() != len(
                wallets
            ):
                wallet_pool = WalletPoolManager(self.client, num_wallets=len(wallets))
                wallet_pool.wallets = [WalletInfo(wallet=w) for w in wallets]
                wallet_pool._initialized = True
                self.wallet_pool = wallet_pool
                self.bundler = MultiWalletBundler(self.client, wallet_pool)
            elif self.bundler is None:
                self.bundler = MultiWalletBundler(self.client, self.wallet_pool)

            bundle_result = await self.bundler.execute_multi_wallet_buy(
                token_info, first_amount
            )
            if not bundle_result.success:
                logger.warning(
                    "Bundled buy failed: %s", bundle_result.error_message or "unknown"
                )
                return None

            used_wallets = wallets[: bundle_result.transactions_submitted or len(wallets)]
            results: List[Dict[str, Any]] = []
            for idx, wallet in enumerate(used_wallets):
                results.append(
                    {
                        "wallet": str(wallet.pubkey()),
                        "amount": first_amount,
                        "success": True,
                        "bundle_id": bundle_result.bundle_id,
                        "tip_paid_lamports": bundle_result.tip_paid,
                        "wallet_index": idx,
                    }
                )

            logger.info(
                "Executed bundled buy via Jito bundle %s (%s wallets)",
                bundle_result.bundle_id,
                len(used_wallets),
            )
            return results
        except Exception as e:
            logger.debug(f"Bundled buy unavailable: {e}")
            return None

    async def _get_wallets(self, config: TokenLaunchConfig) -> List[Wallet]:
        """Get wallets for buying.
        
        Args:
            config: Launch configuration
            
        Returns:
            List of wallets
        """
        wallets = []
        
        # Use provided wallets if available
        if config.wallet_private_keys:
            for private_key in config.wallet_private_keys[:config.num_wallets]:
                try:
                    wallet = Wallet(private_key)
                    wallets.append(wallet)
                except Exception as e:
                    logger.warning(f"Invalid wallet private key: {e}")
        
        # Generate additional wallets if needed
        while len(wallets) < config.num_wallets:
            # Generate new keypair
            keypair = Keypair()
            private_key = base58.b58encode(bytes(keypair)).decode('utf-8')
            
            # Note: These wallets won't have SOL unless funded
            # In production, you'd want to fund them first
            logger.warning(f"Generated wallet {len(wallets)+1} needs funding: {keypair.pubkey()}")
            
            try:
                wallet = Wallet(private_key)
                wallets.append(wallet)
            except Exception as e:
                logger.warning(f"Error creating wallet: {e}")
        
        return wallets[:config.num_wallets]
    
    def _calculate_buy_amounts(
        self,
        total_amount: float,
        num_wallets: int,
        distribution: str,
    ) -> List[float]:
        """Calculate buy amounts per wallet.
        
        Args:
            total_amount: Total amount to buy
            num_wallets: Number of wallets
            distribution: Distribution strategy
            
        Returns:
            List of amounts per wallet
        """
        if num_wallets == 0:
            return []
        
        if distribution == "equal":
            amount_per_wallet = total_amount / num_wallets
            return [amount_per_wallet] * num_wallets
        
        elif distribution == "weighted":
            # First wallet gets more, decreasing
            amounts = []
            remaining = total_amount
            for i in range(num_wallets):
                weight = (num_wallets - i) / sum(range(1, num_wallets + 1))
                amount = total_amount * weight
                amounts.append(amount)
                remaining -= amount
            return amounts
        
        elif distribution == "random":
            import random
            amounts = []
            remaining = total_amount
            for i in range(num_wallets - 1):
                # Random amount between 10% and 30% of remaining
                amount = remaining * random.uniform(0.1, 0.3)
                amounts.append(amount)
                remaining -= amount
            amounts.append(remaining)  # Last wallet gets remainder
            random.shuffle(amounts)
            return amounts
        
        else:
            # Default to equal
            amount_per_wallet = total_amount / num_wallets
            return [amount_per_wallet] * num_wallets

