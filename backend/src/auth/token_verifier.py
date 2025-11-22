"""
Token verification for access control.
Checks if a wallet holds the required access token.
"""

import asyncio
import logging
from solders.pubkey import Pubkey
from spl.token.instructions import get_associated_token_address

from core.client import SolanaClient
from core.wallet import Wallet

logger = logging.getLogger(__name__)


class TokenVerifier:
    """Verifies if a wallet holds the required access token."""

    def __init__(
        self,
        client: SolanaClient,
        access_token_mint: str | Pubkey,
        min_balance: int = 1,
    ):
        """Initialize token verifier.

        Args:
            client: Solana client for RPC calls
            access_token_mint: Token mint address (string or Pubkey) required for access
            min_balance: Minimum token balance required (default: 1)
        """
        self.client = client
        if isinstance(access_token_mint, str):
            try:
                self.access_token_mint = Pubkey.from_string(access_token_mint)
            except Exception as e:
                raise ValueError(f"Invalid token mint address: {access_token_mint}") from e
        else:
            self.access_token_mint = access_token_mint
        self.min_balance = min_balance

    async def verify_wallet_access(self, wallet: Wallet) -> tuple[bool, str]:
        """Verify if a wallet has access (holds required token).

        Args:
            wallet: Wallet to verify

        Returns:
            Tuple of (has_access: bool, message: str)
        """
        try:
            # Get associated token account address
            token_account = get_associated_token_address(
                wallet.pubkey, self.access_token_mint
            )

            # Get token account balance
            client = await self.client.get_client()
            token_balance_response = await client.get_token_account_balance(token_account)

            if token_balance_response.value is None:
                return False, "Access token account not found. You need to hold the access token to use this bot."

            balance = int(token_balance_response.value.amount)

            if balance < self.min_balance:
                return (
                    False,
                    f"Insufficient access token balance. Required: {self.min_balance}, You have: {balance}",
                )

            return True, f"Access granted. Token balance: {balance}"

        except Exception as e:
            logger.error(f"Error verifying wallet access: {e}")
            # If account doesn't exist, it means no tokens
            if "Invalid param" in str(e) or "not found" in str(e).lower():
                return False, "Access token account not found. You need to hold the access token to use this bot."
            return False, f"Error verifying access: {str(e)}"

    async def verify_pubkey_access(self, pubkey: Pubkey) -> tuple[bool, str]:
        """Verify if a public key has access (holds required token).

        Args:
            pubkey: Public key to verify

        Returns:
            Tuple of (has_access: bool, message: str)
        """
        try:
            # Get associated token account address
            token_account = get_associated_token_address(pubkey, self.access_token_mint)

            # Get token account balance
            client = await self.client.get_client()
            token_balance_response = await client.get_token_account_balance(token_account)

            if token_balance_response.value is None:
                return False, "Access token account not found. You need to hold the access token to use this bot."

            balance = int(token_balance_response.value.amount)

            if balance < self.min_balance:
                return (
                    False,
                    f"Insufficient access token balance. Required: {self.min_balance}, You have: {balance}",
                )

            return True, f"Access granted. Token balance: {balance}"

        except Exception as e:
            logger.error(f"Error verifying pubkey access: {e}")
            # If account doesn't exist, it means no tokens
            if "Invalid param" in str(e) or "not found" in str(e).lower():
                return False, "Access token account not found. You need to hold the access token to use this bot."
            return False, f"Error verifying access: {str(e)}"

