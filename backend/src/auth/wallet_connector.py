"""
Wallet connection handler for GUI and API.
Handles wallet connection and token verification.
"""

import asyncio
import logging
from typing import Optional

from solders.pubkey import Pubkey

from auth.token_verifier import TokenVerifier
from core.client import SolanaClient
from core.wallet import Wallet

logger = logging.getLogger(__name__)


class WalletConnector:
    """Handles wallet connection and access verification."""

    def __init__(
        self,
        client: SolanaClient,
        access_token_mint: Optional[str] = None,
        min_token_balance: int = 1,
    ):
        """Initialize wallet connector.

        Args:
            client: Solana client for RPC calls
            access_token_mint: Optional token mint address for access control
            min_token_balance: Minimum token balance required (default: 1)
        """
        self.client = client
        self.access_token_mint = access_token_mint
        self.min_token_balance = min_token_balance
        self.verifier: Optional[TokenVerifier] = None

        if access_token_mint:
            self.verifier = TokenVerifier(
                client=client,
                access_token_mint=access_token_mint,
                min_balance=min_token_balance,
            )

    async def connect_wallet(self, private_key: str) -> tuple[bool, Optional[Wallet], str]:
        """Connect wallet and verify access.

        Args:
            private_key: Base58 encoded private key

        Returns:
            Tuple of (success: bool, wallet: Optional[Wallet], message: str)
        """
        try:
            # Load wallet
            wallet = Wallet(private_key)

            # If token gating is enabled, verify access
            if self.verifier:
                has_access, message = await self.verifier.verify_wallet_access(wallet)
                if not has_access:
                    return False, None, message

                return True, wallet, message

            # No token gating, just return wallet
            return True, wallet, "Wallet connected successfully"

        except Exception as e:
            logger.error(f"Error connecting wallet: {e}")
            return False, None, f"Failed to connect wallet: {str(e)}"

    async def verify_access(self, wallet: Wallet) -> tuple[bool, str]:
        """Verify if connected wallet still has access.

        Args:
            wallet: Wallet to verify

        Returns:
            Tuple of (has_access: bool, message: str)
        """
        if not self.verifier:
            return True, "No access control enabled"

        return await self.verifier.verify_wallet_access(wallet)

    def is_token_gated(self) -> bool:
        """Check if token gating is enabled."""
        return self.verifier is not None

