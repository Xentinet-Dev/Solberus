"""
Sandwich Attack Module - Execute sandwich attacks on pending transactions.

A sandwich attack involves:
1. Front-running: Buy before a large transaction
2. Victim transaction executes (causes price increase)
3. Back-running: Sell immediately after (profit from price increase)
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from solders.pubkey import Pubkey
from solders.transaction import Transaction

from core.client import SolanaClient
from core.wallet import Wallet
from mev.mempool_monitor import MEVOpportunity, PendingTransaction
from mev.jito_integration import JitoBundleManager, check_jito_availability
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SandwichResult:
    """Result of a sandwich attack execution."""
    
    success: bool
    front_run_signature: Optional[str] = None
    back_run_signature: Optional[str] = None
    victim_signature: Optional[str] = None
    profit_sol: float = 0.0
    profit_tokens: float = 0.0
    total_cost: float = 0.0
    error_message: Optional[str] = None


class SandwichAttacker:
    """
    Execute sandwich attacks on profitable transactions.
    
    A sandwich attack profits from the price impact of a large transaction
    by buying before it and selling after it.
    """
    
    def __init__(
        self,
        client: SolanaClient,
        wallet: Wallet,
        use_jito_bundler: bool = True,
        jito_endpoint: str = "https://mainnet.relayer.jito.wtf",
        min_profit_threshold: float = 0.01,  # Minimum profit in SOL
        max_slippage: float = 0.05,  # 5% max slippage
    ):
        """Initialize sandwich attacker.
        
        Args:
            client: Solana RPC client
            wallet: Wallet to use for attacks
            use_jito_bundler: Use Jito bundler for atomic execution
            jito_endpoint: Jito relayer endpoint
            min_profit_threshold: Minimum profit to execute (SOL)
            max_slippage: Maximum acceptable slippage
        """
        self.client = client
        self.wallet = wallet
        self.use_jito_bundler = use_jito_bundler
        self.min_profit_threshold = min_profit_threshold
        self.max_slippage = max_slippage
        
        # Initialize Jito bundle manager if requested
        if use_jito_bundler:
            if check_jito_availability():
                try:
                    self.jito_manager = JitoBundleManager(
                        relayer_endpoint=jito_endpoint
                    )
                    logger.info(f"Jito bundler initialized: {jito_endpoint}")
                except Exception as e:
                    logger.warning(f"Failed to initialize Jito bundler: {e}")
                    self.jito_manager = None
                    self.use_jito_bundler = False
            else:
                logger.warning(
                    "Jito SDK not available. Install with: pip install jito-solana-py"
                )
                self.jito_manager = None
                self.use_jito_bundler = False
        else:
            self.jito_manager = None
        
        self.executed_attacks: List[SandwichResult] = []
        self.total_profit = 0.0
        self.total_attacks = 0
        self.successful_attacks = 0
    
    async def execute_sandwich(
        self, opportunity: MEVOpportunity
    ) -> SandwichResult:
        """Execute a sandwich attack.
        
        Args:
            opportunity: MEV opportunity to exploit
            
        Returns:
            SandwichResult with execution details
        """
        if opportunity.opportunity_type != "sandwich":
            return SandwichResult(
                success=False,
                error_message="Not a sandwich opportunity"
            )
        
        if opportunity.estimated_profit < self.min_profit_threshold:
            return SandwichResult(
                success=False,
                error_message=f"Profit below threshold: {opportunity.estimated_profit}"
            )
        
        try:
            logger.info(
                f"Executing sandwich attack on {opportunity.pending_tx.signature[:8]}..."
            )
            
            if self.use_jito_bundler:
                return await self._execute_jito_sandwich(opportunity)
            else:
                return await self._execute_standard_sandwich(opportunity)
                
        except Exception as e:
            logger.exception(f"Error executing sandwich attack: {e}")
            return SandwichResult(
                success=False,
                error_message=str(e)
            )
    
    async def _execute_jito_sandwich(
        self, opportunity: MEVOpportunity
    ) -> SandwichResult:
        """Execute sandwich using Jito bundler for atomic execution.
        
        Args:
            opportunity: MEV opportunity
            
        Returns:
            SandwichResult
        """
        if not self.jito_manager:
            return SandwichResult(
                success=False,
                error_message="Jito bundler not initialized"
            )
        
        try:
            # Jito bundler ensures atomic execution:
            # 1. Front-run transaction
            # 2. Victim transaction (included in bundle)
            # 3. Back-run transaction
            # All execute in same block or none execute
            
            strategy = opportunity.execution_strategy
            pending_tx = opportunity.pending_tx
            
            # Build front-run transaction
            front_run_tx = await self._build_front_run_transaction(
                pending_tx,
                strategy.get("front_run_amount", pending_tx.amount_sol * 0.5)
            )
            
            # Build back-run transaction
            back_run_tx = await self._build_back_run_transaction(
                pending_tx,
                strategy.get("back_run_amount", pending_tx.amount_sol * 0.5)
            )
            
            # Get victim transaction
            victim_tx = pending_tx.transaction
            
            # Submit bundle via Jito
            bundle_result = await self.jito_manager.submit_sandwich_bundle(
                front_run_tx=front_run_tx,
                victim_tx=victim_tx,
                back_run_tx=back_run_tx,
                tip_lamports=strategy.get("tip_lamports", 10_000)
            )
            
            if bundle_result.success:
                # Calculate profit (would need actual transaction results)
                profit = opportunity.estimated_profit
                
                result = SandwichResult(
                    success=True,
                    front_run_signature=bundle_result.bundle_id,
                    back_run_signature=bundle_result.bundle_id,
                    victim_signature=pending_tx.signature,
                    profit_sol=profit,
                )
                
                self.executed_attacks.append(result)
                self.total_profit += profit
                self.total_attacks += 1
                self.successful_attacks += 1
                
                logger.info(
                    f"Sandwich attack successful via Jito! "
                    f"Bundle: {bundle_result.bundle_id}, Profit: {profit:.6f} SOL"
                )
                
                return result
            else:
                return SandwichResult(
                    success=False,
                    error_message=bundle_result.error_message or "Bundle submission failed"
                )
            
        except Exception as e:
            logger.exception(f"Error in Jito sandwich execution: {e}")
            return SandwichResult(
                success=False,
                error_message=str(e)
            )
    
    async def _execute_standard_sandwich(
        self, opportunity: MEVOpportunity
    ) -> SandwichResult:
        """Execute sandwich without Jito (higher risk, may fail).
        
        Args:
            opportunity: MEV opportunity
            
        Returns:
            SandwichResult
        """
        try:
            # Without Jito, we need to:
            # 1. Submit front-run with high priority fee
            # 2. Hope victim transaction executes
            # 3. Submit back-run immediately after
            
            # This is riskier because transactions may not execute atomically
            # Victim transaction might execute without our front-run
            
            strategy = opportunity.execution_strategy
            pending_tx = opportunity.pending_tx
            
            # Build and submit front-run
            front_run_tx = await self._build_front_run_transaction(
                pending_tx,
                strategy.get("front_run_amount", pending_tx.amount_sol * 0.5)
            )
            
            # Submit with high priority fee
            front_run_sig = await self._submit_with_high_priority(front_run_tx)
            
            # Wait briefly for front-run to confirm
            await asyncio.sleep(0.5)
            
            # Check if front-run succeeded
            front_run_confirmed = await self._check_confirmation(front_run_sig)
            
            if not front_run_confirmed:
                return SandwichResult(
                    success=False,
                    error_message="Front-run transaction failed"
                )
            
            # Wait for victim transaction (or detect it executed)
            await asyncio.sleep(1.0)
            
            # Build and submit back-run
            back_run_tx = await self._build_back_run_transaction(
                pending_tx,
                strategy.get("back_run_amount", pending_tx.amount_sol * 0.5)
            )
            
            back_run_sig = await self._submit_with_high_priority(back_run_tx)
            
            # Calculate profit (would need actual transaction results)
            profit = opportunity.estimated_profit
            
            result = SandwichResult(
                success=True,
                front_run_signature=front_run_sig,
                back_run_signature=back_run_sig,
                victim_signature=pending_tx.signature,
                profit_sol=profit,
            )
            
            self.executed_attacks.append(result)
            self.total_profit += profit
            self.total_attacks += 1
            self.successful_attacks += 1
            
            logger.info(f"Sandwich attack successful! Profit: {profit:.6f} SOL")
            
            return result
            
        except Exception as e:
            logger.exception(f"Error in standard sandwich execution: {e}")
            return SandwichResult(
                success=False,
                error_message=str(e)
            )
    
    async def _build_front_run_transaction(
        self, pending_tx: PendingTransaction, amount: float
    ) -> Transaction:
        """Build front-run transaction (buy before victim).
        
        Args:
            pending_tx: Victim transaction
            amount: Amount to buy in SOL
            
        Returns:
            Transaction to execute
        """
        try:
            if not pending_tx.token_mint:
                raise ValueError("Token mint not found in pending transaction")
            
            # Get platform implementations
            from platforms import get_platform_implementations
            from interfaces.core import TokenInfo, Platform
            from core.pubkeys import LAMPORTS_PER_SOL, TOKEN_DECIMALS
            from core.priority_fee.manager import PriorityFeeManager
            
            # Detect platform from token mint or transaction
            # For now, assume pump.fun (would detect from program ID)
            platform = Platform.PUMP_FUN
            implementations = get_platform_implementations(platform, self.client)
            address_provider = implementations.address_provider
            instruction_builder = implementations.instruction_builder
            curve_manager = implementations.curve_manager
            
            # Derive addresses
            bonding_curve = address_provider.derive_pool_address(pending_tx.token_mint)
            associated_bonding_curve = address_provider.derive_associated_bonding_curve(
                pending_tx.token_mint, bonding_curve
            )
            
            # Create token info
            token_info = TokenInfo(
                name="MEV Token",
                symbol="MEV",
                uri="",
                mint=pending_tx.token_mint,
                platform=platform,
                bonding_curve=bonding_curve,
                associated_bonding_curve=associated_bonding_curve,
                user=self.wallet.pubkey(),
            )
            
            # Convert amount to lamports
            amount_lamports = int(amount * LAMPORTS_PER_SOL)
            
            # Calculate token amount
            token_price_sol = await curve_manager.calculate_price(bonding_curve)
            token_amount = amount / token_price_sol if token_price_sol > 0 else 0
            
            # Calculate minimum token amount with slippage
            slippage = self.max_slippage
            minimum_token_amount = token_amount * (1 - slippage)
            minimum_token_amount_raw = int(minimum_token_amount * 10**TOKEN_DECIMALS)
            
            # Calculate maximum SOL to spend with slippage
            max_amount_lamports = int(amount_lamports * (1 + slippage))
            
            # Build buy instructions
            instructions = await instruction_builder.build_buy_instruction(
                token_info,
                self.wallet.pubkey,
                max_amount_lamports,
                minimum_token_amount_raw,
                address_provider,
            )
            
            # Get accounts for priority fee calculation
            priority_accounts = instruction_builder.get_required_accounts_for_buy(
                token_info, self.wallet.pubkey, address_provider
            )
            
            # Calculate high priority fee (for front-running)
            fee_manager = PriorityFeeManager(
                client=self.client,
                enable_fixed_fee=True,
                fixed_fee=500_000,  # High priority for front-running
            )
            priority_fee = await fee_manager.calculate_priority_fee(priority_accounts)
            
            # Get compute unit limit
            compute_unit_limit = instruction_builder.get_buy_compute_unit_limit()
            
            # Build transaction
            transaction = await self.client.build_transaction(
                instructions=instructions,
                signer_keypair=self.wallet.keypair,
                priority_fee=priority_fee,
                compute_unit_limit=compute_unit_limit,
            )
            
            logger.debug(
                f"Built front-run transaction: {amount} SOL -> ~{token_amount:.6f} tokens"
            )
            
            return transaction
            
        except Exception as e:
            logger.exception(f"Error building front-run transaction: {e}")
            raise
    
    async def _build_back_run_transaction(
        self, pending_tx: PendingTransaction, amount: float
    ) -> Transaction:
        """Build back-run transaction (sell after victim).
        
        Args:
            pending_tx: Victim transaction
            amount: Amount to sell in SOL (will convert to tokens)
            
        Returns:
            Transaction to execute
        """
        try:
            if not pending_tx.token_mint:
                raise ValueError("Token mint not found in pending transaction")
            
            # Get platform implementations
            from platforms import get_platform_implementations
            from interfaces.core import TokenInfo, Platform
            from core.pubkeys import LAMPORTS_PER_SOL, TOKEN_DECIMALS
            from core.priority_fee.manager import PriorityFeeManager
            
            # Detect platform
            platform = Platform.PUMP_FUN
            implementations = get_platform_implementations(platform, self.client)
            address_provider = implementations.address_provider
            instruction_builder = implementations.instruction_builder
            curve_manager = implementations.curve_manager
            
            # Derive addresses
            bonding_curve = address_provider.derive_pool_address(pending_tx.token_mint)
            associated_bonding_curve = address_provider.derive_associated_bonding_curve(
                pending_tx.token_mint, bonding_curve
            )
            
            # Create token info
            token_info = TokenInfo(
                name="MEV Token",
                symbol="MEV",
                uri="",
                mint=pending_tx.token_mint,
                platform=platform,
                bonding_curve=bonding_curve,
                associated_bonding_curve=associated_bonding_curve,
                user=self.wallet.pubkey(),
            )
            
            # Get token balance (amount is in SOL, but we need to sell tokens)
            # For back-run, we typically sell all tokens we bought in front-run
            # Use bundler's token balance method
            from spl.token.instructions import get_associated_token_address
            
            ata = get_associated_token_address(self.wallet.pubkey(), pending_tx.token_mint)
            
            # Get account info
            try:
                account_info = await self.client.get_account_info(ata)
                if account_info and account_info.data and len(account_info.data) >= 72:
                    # Parse token balance
                    amount_bytes = account_info.data[64:72]
                    token_balance = int.from_bytes(amount_bytes, byteorder='little', signed=False)
                else:
                    # No tokens to sell
                    raise ValueError("No tokens to sell in back-run")
            except Exception as e:
                logger.warning(f"Could not get token balance: {e}")
                # Estimate token amount from SOL amount
                token_price_sol = await curve_manager.calculate_price(bonding_curve)
                token_balance = int((amount / token_price_sol) * 10**TOKEN_DECIMALS) if token_price_sol > 0 else 0
            
            if token_balance == 0:
                raise ValueError("No tokens to sell")
            
            # Calculate expected SOL output
            expected_sol_output = await curve_manager.calculate_sell_amount_out(
                bonding_curve, token_balance
            )
            
            # Calculate minimum SOL output with slippage
            slippage = self.max_slippage
            min_sol_output = int(expected_sol_output * (1 - slippage))
            
            # Build sell instructions
            instructions = await instruction_builder.build_sell_instruction(
                token_info,
                self.wallet.pubkey,
                token_balance,
                min_sol_output,
                address_provider,
            )
            
            # Get accounts for priority fee calculation
            priority_accounts = instruction_builder.get_required_accounts_for_sell(
                token_info, self.wallet.pubkey, address_provider
            )
            
            # Calculate high priority fee (for back-running)
            fee_manager = PriorityFeeManager(
                client=self.client,
                enable_fixed_fee=True,
                fixed_fee=500_000,  # High priority for back-running
            )
            priority_fee = await fee_manager.calculate_priority_fee(priority_accounts)
            
            # Get compute unit limit
            compute_unit_limit = instruction_builder.get_sell_compute_unit_limit()
            
            # Build transaction
            transaction = await self.client.build_transaction(
                instructions=instructions,
                signer_keypair=self.wallet.keypair,
                priority_fee=priority_fee,
                compute_unit_limit=compute_unit_limit,
            )
            
            logger.debug(
                f"Built back-run transaction: {token_balance / 10**TOKEN_DECIMALS:.6f} tokens -> "
                f"~{expected_sol_output / LAMPORTS_PER_SOL:.6f} SOL"
            )
            
            return transaction
            
        except Exception as e:
            logger.exception(f"Error building back-run transaction: {e}")
            raise
    
    async def _submit_with_high_priority(self, transaction: Transaction) -> str:
        """Submit transaction with high priority fee.
        
        Args:
            transaction: Transaction to submit (already has priority fee)
            
        Returns:
            Transaction signature
        """
        try:
            # Transaction already has priority fee from build_transaction
            # Just send it
            client = await self.client.get_client()
            from solana.rpc.types import TxOpts
            from solana.rpc.commitment import Confirmed
            
            response = await client.send_transaction(
                transaction,
                opts=TxOpts(skip_preflight=True, preflight_commitment=Confirmed)
            )
            
            signature = response.value
            logger.debug(f"Submitted transaction with high priority: {signature}")
            
            return signature
            
        except Exception as e:
            logger.exception(f"Error submitting transaction: {e}")
            raise
    
    async def _check_confirmation(self, signature: str) -> bool:
        """Check if transaction is confirmed.
        
        Args:
            signature: Transaction signature
            
        Returns:
            True if confirmed, False otherwise
        """
        try:
            status = await self.client.get_signature_status(signature)
            return status is not None and status.get("confirmationStatus") == "confirmed"
        except Exception:
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get sandwich attack statistics.
        
        Returns:
            Dictionary with stats
        """
        success_rate = (
            self.successful_attacks / self.total_attacks
            if self.total_attacks > 0
            else 0.0
        )
        
        return {
            "total_attacks": self.total_attacks,
            "successful_attacks": self.successful_attacks,
            "success_rate": success_rate,
            "total_profit_sol": self.total_profit,
            "average_profit": (
                self.total_profit / self.successful_attacks
                if self.successful_attacks > 0
                else 0.0
            ),
        }

