"""
Multi-Wallet Manager - Manages multiple wallets for coordinated trading.

Supports:
- Multiple wallet management
- Wallet switching
- Portfolio aggregation
- Separate statistics per wallet
- Coordinated entry/exit
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from solders.keypair import Keypair
from solders.pubkey import Pubkey

from core.wallet import Wallet
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class WalletStats:
    """Statistics for a single wallet."""

    wallet_id: str
    total_trades: int = 0
    successful_trades: int = 0
    total_profit: float = 0.0  # SOL
    total_volume: float = 0.0  # SOL
    active_positions: int = 0


class MultiWalletManager:
    """
    Manages multiple wallets for coordinated trading.

    Supports splitting large positions across wallets, simultaneous execution,
    and portfolio aggregation.
    """

    def __init__(self, wallets: List[Wallet]):
        """Initialize the multi-wallet manager.

        Args:
            wallets: List of wallets to manage
        """
        if not wallets:
            raise ValueError("At least one wallet is required")

        self.wallets = wallets
        self.wallet_stats: Dict[str, WalletStats] = {}
        self.active_wallet_index = 0

        # Initialize stats for each wallet
        for i, wallet in enumerate(self.wallets):
            wallet_id = f"wallet_{i}"
            self.wallet_stats[wallet_id] = WalletStats(wallet_id=wallet_id)

        logger.info(f"Initialized Multi-Wallet Manager with {len(wallets)} wallets")

    @property
    def active_wallet(self) -> Wallet:
        """Get the currently active wallet.

        Returns:
            Active wallet
        """
        return self.wallets[self.active_wallet_index]

    def switch_wallet(self, index: int) -> None:
        """Switch to a different wallet.

        Args:
            index: Wallet index to switch to
        """
        if 0 <= index < len(self.wallets):
            self.active_wallet_index = index
            logger.info(f"Switched to wallet {index}")
        else:
            raise ValueError(f"Invalid wallet index: {index}")

    def get_wallet(self, index: int) -> Wallet:
        """Get a specific wallet by index.

        Args:
            index: Wallet index

        Returns:
            Wallet at index
        """
        if 0 <= index < len(self.wallets):
            return self.wallets[index]
        raise ValueError(f"Invalid wallet index: {index}")

    def get_all_wallets(self) -> List[Wallet]:
        """Get all managed wallets.

        Returns:
            List of all wallets
        """
        return self.wallets.copy()

    def split_position(
        self, total_amount: float, num_wallets: Optional[int] = None
    ) -> List[float]:
        """Split a position amount across multiple wallets.

        Args:
            total_amount: Total amount to split (SOL)
            num_wallets: Number of wallets to use (None = use all)

        Returns:
            List of amounts per wallet
        """
        if num_wallets is None:
            num_wallets = len(self.wallets)
        else:
            num_wallets = min(num_wallets, len(self.wallets))

        if num_wallets == 0:
            return []

        # Split evenly
        amount_per_wallet = total_amount / num_wallets
        amounts = [amount_per_wallet] * num_wallets

        # Adjust for rounding
        total_allocated = sum(amounts)
        if total_allocated < total_amount:
            amounts[0] += total_amount - total_allocated

        logger.debug(
            f"Split {total_amount} SOL across {num_wallets} wallets: {amounts}"
        )

        return amounts

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get aggregated portfolio summary across all wallets.

        Returns:
            Portfolio summary dictionary
        """
        total_trades = sum(stats.total_trades for stats in self.wallet_stats.values())
        total_successful = sum(
            stats.successful_trades for stats in self.wallet_stats.values()
        )
        total_profit = sum(stats.total_profit for stats in self.wallet_stats.values())
        total_volume = sum(stats.total_volume for stats in self.wallet_stats.values())
        total_positions = sum(
            stats.active_positions for stats in self.wallet_stats.values()
        )

        success_rate = (
            total_successful / max(total_trades, 1) if total_trades > 0 else 0.0
        )

        return {
            "total_wallets": len(self.wallets),
            "total_trades": total_trades,
            "total_successful": total_successful,
            "success_rate": success_rate,
            "total_profit": total_profit,
            "total_volume": total_volume,
            "total_positions": total_positions,
            "wallet_stats": {
                wallet_id: {
                    "total_trades": stats.total_trades,
                    "successful_trades": stats.successful_trades,
                    "total_profit": stats.total_profit,
                    "total_volume": stats.total_volume,
                    "active_positions": stats.active_positions,
                }
                for wallet_id, stats in self.wallet_stats.items()
            },
        }

    def get_wallet_stats(self, wallet_id: str) -> Optional[WalletStats]:
        """Get statistics for a specific wallet.

        Args:
            wallet_id: Wallet identifier

        Returns:
            Wallet statistics if found, None otherwise
        """
        return self.wallet_stats.get(wallet_id)

    def update_wallet_stats(
        self,
        wallet_id: str,
        trade_success: bool = False,
        profit: float = 0.0,
        volume: float = 0.0,
    ) -> None:
        """Update statistics for a wallet.

        Args:
            wallet_id: Wallet identifier
            trade_success: Whether the trade was successful
            profit: Profit from the trade (SOL)
            volume: Trade volume (SOL)
        """
        if wallet_id in self.wallet_stats:
            stats = self.wallet_stats[wallet_id]
            stats.total_trades += 1
            if trade_success:
                stats.successful_trades += 1
            stats.total_profit += profit
            stats.total_volume += volume

    def get_wallet_keypairs(self) -> List[Keypair]:
        """Get keypairs for all wallets.

        Returns:
            List of keypairs
        """
        return [wallet.keypair for wallet in self.wallets]

    def get_wallet_pubkeys(self) -> List[Pubkey]:
        """Get public keys for all wallets.

        Returns:
            List of public keys
        """
        return [wallet.pubkey for wallet in self.wallets]

