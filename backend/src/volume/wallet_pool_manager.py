"""
Wallet Pool Manager - Manage a pool of wallets for volume generation.

This module manages a pool of wallets, including funding, rebalancing,
and rotation for volume generation.
"""

import asyncio
import base58
import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional

from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams
from solders.transaction import Transaction

from core.wallet import Wallet
from core.client import SolanaClient
from core.pubkeys import LAMPORTS_PER_SOL
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class WalletInfo:
    """Information about a wallet in the pool."""
    
    wallet: Wallet
    balance_sol: float = 0.0
    balance_tokens: float = 0.0
    total_trades: int = 0
    last_used: float = 0.0
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "private_key": str(self.wallet.keypair.secret()),  # For storage
            "balance_sol": self.balance_sol,
            "balance_tokens": self.balance_tokens,
            "total_trades": self.total_trades,
            "last_used": self.last_used,
        }


class WalletPoolManager:
    """
    Manage a pool of wallets for coordinated trading.
    
    This class handles wallet creation, funding, rebalancing,
    and rotation for volume generation.
    """
    
    def __init__(
        self,
        client: SolanaClient,
        num_wallets: int = 20,
        min_balance_sol: float = 0.1,
        target_balance_sol: float = 1.0,
        main_wallet: Optional[Wallet] = None,
        wallet_storage_path: Optional[str] = None,
    ):
        """Initialize wallet pool manager.
        
        Args:
            client: Solana RPC client
            num_wallets: Number of wallets in pool
            min_balance_sol: Minimum balance per wallet
            target_balance_sol: Target balance per wallet
            main_wallet: Main wallet to fund from (if None, must be set later)
            wallet_storage_path: Path to store wallet keypairs (if None, uses memory only)
        """
        self.client = client
        self.num_wallets = num_wallets
        self.min_balance_sol = min_balance_sol
        self.target_balance_sol = target_balance_sol
        self.main_wallet = main_wallet
        self.wallet_storage_path = wallet_storage_path
        
        self.wallets: List[WalletInfo] = []
        self._initialized = False
    
    async def initialize(self, main_wallet: Optional[Wallet] = None):
        """Initialize wallet pool (generate or load wallets).
        
        Args:
            main_wallet: Main wallet to fund from (if not set in __init__)
        """
        if main_wallet:
            self.main_wallet = main_wallet
        
        if not self.main_wallet:
            raise ValueError("Main wallet must be provided for initialization")
        
        if self._initialized:
            logger.warning("Wallet pool already initialized")
            return
        
        # Try to load existing wallets
        if self.wallet_storage_path and Path(self.wallet_storage_path).exists():
            await self._load_wallets()
        else:
            await self._generate_wallets()
        
        # Check and fund wallets
        await self._check_and_fund_wallets()
        
        self._initialized = True
        logger.info(f"Wallet pool initialized with {len(self.wallets)} wallets")
    
    async def _generate_wallets(self):
        """Generate new wallets for the pool."""
        logger.info(f"Generating {self.num_wallets} new wallets...")
        
        self.wallets = []
        
        for i in range(self.num_wallets):
            # Generate new keypair
            keypair = Keypair()
            wallet = Wallet(keypair.secret())
            
            wallet_info = WalletInfo(
                wallet=wallet,
                balance_sol=0.0,
            )
            
            self.wallets.append(wallet_info)
            
            logger.debug(f"Generated wallet {i+1}/{self.num_wallets}: {wallet.pubkey()}")
        
        # Save wallets if storage path provided
        if self.wallet_storage_path:
            await self._save_wallets()
    
    async def _load_wallets(self):
        """Load wallets from storage."""
        try:
            storage_path = Path(self.wallet_storage_path)
            if not storage_path.exists():
                logger.warning(f"Wallet storage not found: {storage_path}")
                await self._generate_wallets()
                return
            
            with open(storage_path, 'r') as f:
                data = json.load(f)
            
            self.wallets = []
            for wallet_data in data.get("wallets", []):
                private_key = wallet_data["private_key"]
                wallet = Wallet(private_key)
                
                wallet_info = WalletInfo(
                    wallet=wallet,
                    balance_sol=wallet_data.get("balance_sol", 0.0),
                    balance_tokens=wallet_data.get("balance_tokens", 0.0),
                    total_trades=wallet_data.get("total_trades", 0),
                    last_used=wallet_data.get("last_used", 0.0),
                )
                
                self.wallets.append(wallet_info)
            
            # Generate additional wallets if needed
            while len(self.wallets) < self.num_wallets:
                keypair = Keypair()
                wallet = Wallet(keypair.secret())
                self.wallets.append(WalletInfo(wallet=wallet))
            
            logger.info(f"Loaded {len(self.wallets)} wallets from storage")
            
        except Exception as e:
            logger.exception(f"Error loading wallets: {e}")
            await self._generate_wallets()
    
    async def _save_wallets(self):
        """Save wallets to storage."""
        if not self.wallet_storage_path:
            return
        
        try:
            storage_path = Path(self.wallet_storage_path)
            storage_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                "wallets": [wallet_info.to_dict() for wallet_info in self.wallets]
            }
            
            with open(storage_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved {len(self.wallets)} wallets to {storage_path}")
            
        except Exception as e:
            logger.exception(f"Error saving wallets: {e}")
    
    async def _check_and_fund_wallets(self):
        """Check wallet balances and fund if needed."""
        logger.info("Checking wallet balances...")
        
        total_needed = 0.0
        wallets_to_fund = []
        
        for i, wallet_info in enumerate(self.wallets):
            # Get current balance
            balance = await self._get_wallet_balance(wallet_info.wallet)
            wallet_info.balance_sol = balance
            
            if balance < self.min_balance_sol:
                amount_needed = self.target_balance_sol - balance
                total_needed += amount_needed
                wallets_to_fund.append((i, amount_needed))
        
        if wallets_to_fund:
            logger.info(f"Funding {len(wallets_to_fund)} wallets, total: {total_needed:.6f} SOL")
            
            # Check main wallet balance
            main_balance = await self._get_wallet_balance(self.main_wallet)
            
            if main_balance < total_needed + 0.01:  # +0.01 for fees
                logger.warning(
                    f"Insufficient balance in main wallet: {main_balance:.6f} SOL, "
                    f"needed: {total_needed:.6f} SOL"
                )
                return
            
            # Fund wallets
            for wallet_idx, amount in wallets_to_fund:
                await self._fund_wallet(wallet_idx, amount)
                await asyncio.sleep(0.1)  # Small delay between transfers
        else:
            logger.info("All wallets have sufficient balance")
    
    async def _fund_wallet(self, wallet_idx: int, amount_sol: float):
        """Fund a wallet from main wallet.
        
        Args:
            wallet_idx: Wallet index to fund
            amount_sol: Amount to fund in SOL
        """
        try:
            wallet_info = self.wallets[wallet_idx]
            target_wallet = wallet_info.wallet
            
            amount_lamports = int(amount_sol * LAMPORTS_PER_SOL)
            
            # Build transfer instruction
            transfer_ix = transfer(
                TransferParams(
                    from_pubkey=self.main_wallet.pubkey(),
                    to_pubkey=target_wallet.pubkey(),
                    lamports=amount_lamports,
                )
            )
            
            # Build and send transaction
            recent_blockhash = await self.client.get_cached_blockhash()
            from solders.message import Message
            message = Message([transfer_ix], self.main_wallet.pubkey())
            transaction = Transaction([self.main_wallet.keypair], message, recent_blockhash)
            
            # Send transaction
            client = await self.client.get_client()
            from solana.rpc.types import TxOpts
            from solana.rpc.commitment import Confirmed
            
            response = await client.send_transaction(
                transaction,
                opts=TxOpts(skip_preflight=True, preflight_commitment=Confirmed)
            )
            
            signature = response.value
            logger.info(
                f"Funded wallet {wallet_idx} ({target_wallet.pubkey()}): "
                f"{amount_sol:.6f} SOL, signature: {signature}"
            )
            
            # Update balance
            wallet_info.balance_sol += amount_sol
            
        except Exception as e:
            logger.exception(f"Error funding wallet {wallet_idx}: {e}")
    
    async def _get_wallet_balance(self, wallet: Wallet) -> float:
        """Get SOL balance for a wallet.
        
        Args:
            wallet: Wallet to check
            
        Returns:
            Balance in SOL
        """
        try:
            client = await self.client.get_client()
            balance_response = await client.get_balance(wallet.pubkey())
            balance_lamports = balance_response.value
            return balance_lamports / LAMPORTS_PER_SOL
        except Exception as e:
            logger.exception(f"Error getting wallet balance: {e}")
            return 0.0
    
    def get_wallet(self, index: int) -> Wallet:
        """Get wallet by index.
        
        Args:
            index: Wallet index
            
        Returns:
            Wallet instance
        """
        if index >= len(self.wallets):
            raise IndexError(f"Wallet index {index} out of range")
        
        return self.wallets[index].wallet
    
    def get_wallet_count(self) -> int:
        """Get number of wallets in pool.
        
        Returns:
            Number of wallets
        """
        return len(self.wallets)
    
    async def rebalance_wallets(self):
        """Rebalance wallets to maintain target balances."""
        logger.info("Rebalancing wallets...")
        
        # Get all balances
        total_balance = 0.0
        for wallet_info in self.wallets:
            balance = await self._get_wallet_balance(wallet_info.wallet)
            wallet_info.balance_sol = balance
            total_balance += balance
        
        # Calculate target total
        target_total = self.target_balance_sol * len(self.wallets)
        
        # If total is below target, fund from main wallet
        if total_balance < target_total:
            needed = target_total - total_balance
            logger.info(f"Total balance below target, funding {needed:.6f} SOL")
            
            # Distribute evenly
            per_wallet = needed / len(self.wallets)
            for i in range(len(self.wallets)):
                if self.wallets[i].balance_sol < self.target_balance_sol:
                    await self._fund_wallet(i, per_wallet)
                    await asyncio.sleep(0.1)
        
        # If some wallets have excess, redistribute (optional)
        # For now, just ensure minimum balance
    
    async def fund_wallet(self, index: int, amount_sol: float):
        """Fund a wallet.
        
        Args:
            index: Wallet index
            amount_sol: Amount to fund in SOL
        """
        await self._fund_wallet(index, amount_sol)
    
    async def get_all_balances(self) -> List[float]:
        """Get balances for all wallets.
        
        Returns:
            List of balances in SOL
        """
        balances = []
        for wallet_info in self.wallets:
            balance = await self._get_wallet_balance(wallet_info.wallet)
            wallet_info.balance_sol = balance
            balances.append(balance)
        return balances
    
    def get_stats(self) -> dict:
        """Get wallet pool statistics.
        
        Returns:
            Dictionary with stats
        """
        total_balance = sum(w.balance_sol for w in self.wallets)
        total_trades = sum(w.total_trades for w in self.wallets)
        
        return {
            "num_wallets": len(self.wallets),
            "total_balance_sol": total_balance,
            "average_balance": total_balance / len(self.wallets) if self.wallets else 0.0,
            "total_trades": total_trades,
            "min_balance": min((w.balance_sol for w in self.wallets), default=0.0),
            "max_balance": max((w.balance_sol for w in self.wallets), default=0.0),
        }
