"""
Front-Running Module - Execute front-running attacks on pending transactions.

Front-running involves identifying a profitable transaction in the mempool
and copying it with a higher priority fee to ensure execution first.
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from solders.pubkey import Pubkey
from solders.transaction import Transaction

from core.client import SolanaClient
from core.wallet import Wallet
from mev.mempool_monitor import MEVOpportunity, PendingTransaction
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FrontRunResult:
    """Result of a front-running execution."""
    
    success: bool
    front_run_signature: Optional[str] = None
    victim_signature: Optional[str] = None
    profit_sol: float = 0.0
    profit_tokens: float = 0.0
    priority_fee_paid: int = 0
    error_message: Optional[str] = None


class FrontRunner:
    """
    Execute front-running attacks on profitable transactions.
    
    Front-running involves copying a profitable transaction but executing
    it first with a higher priority fee.
    """
    
    def __init__(
        self,
        client: SolanaClient,
        wallet: Wallet,
        min_profit_threshold: float = 0.01,  # Minimum profit in SOL
        priority_fee_multiplier: float = 1.5,  # Multiply victim's priority fee
        max_priority_fee: int = 1_000_000,  # Maximum priority fee in lamports
    ):
        """Initialize front-runner.
        
        Args:
            client: Solana RPC client
            wallet: Wallet to use for front-running
            min_profit_threshold: Minimum profit to execute (SOL)
            priority_fee_multiplier: Multiplier for victim's priority fee
            max_priority_fee: Maximum priority fee to pay
        """
        self.client = client
        self.wallet = wallet
        self.min_profit_threshold = min_profit_threshold
        self.priority_fee_multiplier = priority_fee_multiplier
        self.max_priority_fee = max_priority_fee
        
        self.executed_front_runs: List[FrontRunResult] = []
        self.total_profit = 0.0
        self.total_attempts = 0
        self.successful_runs = 0
    
    async def execute_front_run(
        self, opportunity: MEVOpportunity
    ) -> FrontRunResult:
        """Execute a front-running attack.
        
        Args:
            opportunity: MEV opportunity to exploit
            
        Returns:
            FrontRunResult with execution details
        """
        if opportunity.opportunity_type != "front_run":
            return FrontRunResult(
                success=False,
                error_message="Not a front-run opportunity"
            )
        
        if opportunity.estimated_profit < self.min_profit_threshold:
            return FrontRunResult(
                success=False,
                error_message=f"Profit below threshold: {opportunity.estimated_profit}"
            )
        
        try:
            logger.info(
                f"Executing front-run on {opportunity.pending_tx.signature[:8]}..."
            )
            
            pending_tx = opportunity.pending_tx
            strategy = opportunity.execution_strategy
            
            # Calculate priority fee
            base_priority_fee = pending_tx.priority_fee
            our_priority_fee = min(
                int(base_priority_fee * self.priority_fee_multiplier),
                self.max_priority_fee
            )
            
            # Build front-run transaction
            front_run_tx = await self._build_front_run_transaction(
                pending_tx,
                strategy.get("buy_amount", pending_tx.amount_sol * 0.3),
                our_priority_fee
            )
            
            # Submit with high priority
            front_run_sig = await self._submit_transaction(front_run_tx, our_priority_fee)
            
            # Wait for confirmation
            await asyncio.sleep(0.5)
            confirmed = await self._check_confirmation(front_run_sig)
            
            if not confirmed:
                return FrontRunResult(
                    success=False,
                    error_message="Front-run transaction failed to confirm"
                )
            
            # Calculate profit (would need actual transaction results)
            profit = opportunity.estimated_profit
            
            result = FrontRunResult(
                success=True,
                front_run_signature=front_run_sig,
                victim_signature=pending_tx.signature,
                profit_sol=profit,
                priority_fee_paid=our_priority_fee,
            )
            
            self.executed_front_runs.append(result)
            self.total_profit += profit
            self.total_attempts += 1
            self.successful_runs += 1
            
            logger.info(
                f"Front-run successful! Profit: {profit:.6f} SOL, "
                f"Priority fee: {our_priority_fee / 1e9:.6f} SOL"
            )
            
            return result
            
        except Exception as e:
            logger.exception(f"Error executing front-run: {e}")
            return FrontRunResult(
                success=False,
                error_message=str(e)
            )
    
    async def _build_front_run_transaction(
        self, pending_tx: PendingTransaction, amount: float, priority_fee: int
    ) -> Transaction:
        """Build front-run transaction (copy victim's trade).
        
        Args:
            pending_tx: Victim transaction
            amount: Amount to trade in SOL
            priority_fee: Priority fee to pay (microlamports)
            
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
            
            # Determine if victim is buying or selling
            # For front-running, we typically copy the same action
            # If victim is buying, we buy first. If selling, we sell first.
            is_buy = pending_tx.transaction_type.value in ["buy", "swap"]
            
            if is_buy:
                # Front-run buy: Buy before victim buys
                amount_lamports = int(amount * LAMPORTS_PER_SOL)
                
                # Calculate token amount
                token_price_sol = await curve_manager.calculate_price(bonding_curve)
                token_amount = amount / token_price_sol if token_price_sol > 0 else 0
                
                # Calculate minimum token amount with slippage
                slippage = 0.05  # 5% slippage
                minimum_token_amount = token_amount * (1 - slippage)
                minimum_token_amount_raw = int(minimum_token_amount * 10**TOKEN_DECIMALS)
                
                # Calculate maximum SOL to spend
                max_amount_lamports = int(amount_lamports * (1 + slippage))
                
                # Build buy instructions
                instructions = await instruction_builder.build_buy_instruction(
                    token_info,
                    self.wallet.pubkey,
                    max_amount_lamports,
                    minimum_token_amount_raw,
                    address_provider,
                )
                
                # Get accounts for priority fee
                priority_accounts = instruction_builder.get_required_accounts_for_buy(
                    token_info, self.wallet.pubkey, address_provider
                )
                
                # Get compute unit limit
                compute_unit_limit = instruction_builder.get_buy_compute_unit_limit()
            else:
                # Front-run sell: Sell before victim sells
                # Get token balance
                from spl.token.instructions import get_associated_token_address
                
                ata = get_associated_token_address(self.wallet.pubkey(), pending_tx.token_mint)
                
                try:
                    account_info = await self.client.get_account_info(ata)
                    if account_info and account_info.data and len(account_info.data) >= 72:
                        amount_bytes = account_info.data[64:72]
                        token_balance = int.from_bytes(amount_bytes, byteorder='little', signed=False)
                    else:
                        raise ValueError("No tokens to sell")
                except Exception:
                    # Estimate from amount
                    token_price_sol = await curve_manager.calculate_price(bonding_curve)
                    token_balance = int((amount / token_price_sol) * 10**TOKEN_DECIMALS) if token_price_sol > 0 else 0
                
                if token_balance == 0:
                    raise ValueError("No tokens to sell for front-run")
                
                # Calculate expected SOL output
                expected_sol_output = await curve_manager.calculate_sell_amount_out(
                    bonding_curve, token_balance
                )
                
                # Calculate minimum SOL output
                slippage = 0.05
                min_sol_output = int(expected_sol_output * (1 - slippage))
                
                # Build sell instructions
                instructions = await instruction_builder.build_sell_instruction(
                    token_info,
                    self.wallet.pubkey,
                    token_balance,
                    min_sol_output,
                    address_provider,
                )
                
                # Get accounts for priority fee
                priority_accounts = instruction_builder.get_required_accounts_for_sell(
                    token_info, self.wallet.pubkey, address_provider
                )
                
                # Get compute unit limit
                compute_unit_limit = instruction_builder.get_sell_compute_unit_limit()
            
            # Build transaction with specified priority fee
            transaction = await self.client.build_transaction(
                instructions=instructions,
                signer_keypair=self.wallet.keypair,
                priority_fee=priority_fee,  # Use provided priority fee
                compute_unit_limit=compute_unit_limit,
            )
            
            logger.debug(
                f"Built front-run transaction: {amount} SOL, "
                f"Priority fee: {priority_fee / 1e9:.6f} SOL"
            )
            
            return transaction
            
        except Exception as e:
            logger.exception(f"Error building front-run transaction: {e}")
            raise
    
    async def _submit_transaction(
        self, transaction: Transaction, priority_fee: int
    ) -> str:
        """Submit transaction with priority fee.
        
        Args:
            transaction: Transaction to submit (already has priority fee)
            priority_fee: Priority fee in microlamports (for logging)
            
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
            logger.debug(
                f"Submitted front-run transaction: {signature}, "
                f"Priority fee: {priority_fee / 1e9:.6f} SOL"
            )
            
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
        """Get front-running statistics.
        
        Returns:
            Dictionary with stats
        """
        success_rate = (
            self.successful_runs / self.total_attempts
            if self.total_attempts > 0
            else 0.0
        )
        
        return {
            "total_attempts": self.total_attempts,
            "successful_runs": self.successful_runs,
            "success_rate": success_rate,
            "total_profit_sol": self.total_profit,
            "average_profit": (
                self.total_profit / self.successful_runs
                if self.successful_runs > 0
                else 0.0
            ),
        }

