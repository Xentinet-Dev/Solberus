"""
Jito Integration for MEV Extraction.

This module provides integration with Jito's MEV infrastructure
for atomic transaction bundling and MEV extraction.

Since there's no official Python SDK, we use direct HTTP requests
to Jito's relayer API.

Reference: https://jito-foundation.gitbook.io/mev/jito-solana/building-the-software
"""

import asyncio
import base64
import json
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

import aiohttp
from solders.transaction import Transaction
from solders.pubkey import Pubkey

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class BundleResult:
    """Result of bundle submission."""
    
    success: bool
    bundle_id: Optional[str] = None
    error_message: Optional[str] = None
    estimated_inclusion_slot: Optional[int] = None


class JitoBundleManager:
    """
    Manages Jito bundle submission for MEV extraction.
    
    Jito allows atomic execution of multiple transactions in a single block,
    enabling sandwich attacks and other MEV strategies.
    
    This implementation uses direct HTTP requests to Jito's relayer API
    since there's no official Python SDK.
    
    Reference: https://jito-foundation.gitbook.io/mev/
    """
    
    def __init__(
        self,
        relayer_endpoint: str = "https://mainnet.relayer.jito.wtf",
        auth_keypair: Optional[Any] = None,
    ):
        """Initialize Jito bundle manager.
        
        Args:
            relayer_endpoint: Jito relayer endpoint
                - Mainnet: https://mainnet.relayer.jito.wtf
                - Testnet: https://testnet.relayer.jito.wtf
            auth_keypair: Optional keypair for authenticated endpoints
        """
        self.relayer_endpoint = relayer_endpoint.rstrip('/')
        self.auth_keypair = auth_keypair
        self.session: Optional[aiohttp.ClientSession] = None
        
        self.submitted_bundles: List[str] = []
        self.successful_bundles: List[str] = []
        self.failed_bundles: List[Dict[str, Any]] = []
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        """Close the HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def _serialize_transaction(self, transaction: Transaction) -> str:
        """Serialize transaction to base64 string.
        
        Args:
            transaction: Transaction to serialize
            
        Returns:
            Base64-encoded transaction
        """
        # Serialize transaction to bytes
        tx_bytes = bytes(transaction)
        # Encode to base64
        return base64.b64encode(tx_bytes).decode('utf-8')
    
    async def submit_sandwich_bundle(
        self,
        front_run_tx: Transaction,
        victim_tx: Transaction,
        back_run_tx: Transaction,
        tip_lamports: int = 10_000,  # 0.00001 SOL tip
    ) -> BundleResult:
        """Submit a sandwich attack bundle.
        
        A sandwich bundle contains:
        1. Front-run transaction (buy before victim)
        2. Victim transaction (the target transaction)
        3. Back-run transaction (sell after victim)
        
        All execute atomically in the same block.
        
        Args:
            front_run_tx: Front-running transaction
            victim_tx: Victim transaction (to be sandwiched)
            back_run_tx: Back-running transaction
            tip_lamports: Tip amount in lamports for bundle inclusion
            
        Returns:
            BundleResult with submission details
        """
        transactions = [front_run_tx, victim_tx, back_run_tx]
        return await self.submit_custom_bundle(transactions, tip_lamports)
    
    async def submit_front_run_bundle(
        self,
        front_run_tx: Transaction,
        victim_tx: Transaction,
        tip_lamports: int = 10_000,
    ) -> BundleResult:
        """Submit a front-running bundle.
        
        A front-run bundle contains:
        1. Front-run transaction (executes first)
        2. Victim transaction (executes after)
        
        Args:
            front_run_tx: Front-running transaction
            victim_tx: Victim transaction
            tip_lamports: Tip amount in lamports
            
        Returns:
            BundleResult with submission details
        """
        transactions = [front_run_tx, victim_tx]
        return await self.submit_custom_bundle(transactions, tip_lamports)
    
    async def submit_custom_bundle(
        self,
        transactions: List[Transaction],
        tip_lamports: int = 10_000,
    ) -> BundleResult:
        """Submit a custom transaction bundle.
        
        Args:
            transactions: List of transactions to bundle
            tip_lamports: Tip amount in lamports
            
        Returns:
            BundleResult with submission details
        """
        try:
            if not transactions:
                return BundleResult(
                    success=False,
                    error_message="No transactions provided"
                )
            
            # Serialize all transactions to base64
            serialized_txs = [
                self._serialize_transaction(tx) for tx in transactions
            ]
            
            # Prepare bundle payload
            # Jito API expects transactions as base64 strings in an array
            bundle_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "sendBundle",
                "params": [serialized_txs]
            }
            
            # Submit bundle via HTTP POST
            session = await self._get_session()
            
            headers = {
                "Content-Type": "application/json",
            }
            
            # Add authentication if provided
            if self.auth_keypair:
                # Would need to sign request with keypair
                # For now, assume public endpoint
                pass
            
            async with session.post(
                f"{self.relayer_endpoint}/api/v1/bundles",
                json=bundle_payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    result_data = await response.json()
                    
                    # Extract bundle ID from response
                    # Jito API format may vary, adjust based on actual response
                    bundle_id = result_data.get("result", {}).get("bundleId") or result_data.get("bundle_id")
                    
                    if bundle_id:
                        self.submitted_bundles.append(bundle_id)
                        logger.info(
                            f"Bundle submitted successfully: {bundle_id} "
                            f"({len(transactions)} transactions)"
                        )
                        
                        return BundleResult(
                            success=True,
                            bundle_id=bundle_id,
                        )
                    else:
                        # Try alternative response format
                        if "result" in result_data:
                            # Response might be the bundle ID directly
                            bundle_id = result_data.get("result")
                            if isinstance(bundle_id, str):
                                self.submitted_bundles.append(bundle_id)
                                return BundleResult(
                                    success=True,
                                    bundle_id=bundle_id,
                                )
                        
                        error_msg = f"Bundle submitted but no bundle ID in response: {result_data}"
                        logger.warning(error_msg)
                        return BundleResult(
                            success=False,
                            error_message=error_msg
                        )
                else:
                    error_text = await response.text()
                    error_msg = f"HTTP {response.status}: {error_text}"
                    logger.error(f"Bundle submission failed: {error_msg}")
                    
                    self.failed_bundles.append({
                        "error": error_msg,
                        "status": response.status
                    })
                    
                    return BundleResult(
                        success=False,
                        error_message=error_msg
                    )
                    
        except aiohttp.ClientError as e:
            error_msg = f"Network error submitting bundle: {e}"
            logger.exception(error_msg)
            self.failed_bundles.append({
                "error": str(e),
                "type": "network_error"
            })
            return BundleResult(
                success=False,
                error_message=error_msg
            )
        except Exception as e:
            logger.exception(f"Error submitting bundle: {e}")
            self.failed_bundles.append({
                "error": str(e),
                "type": "unknown"
            })
            return BundleResult(
                success=False,
                error_message=str(e)
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get bundle submission statistics.
        
        Returns:
            Dictionary with stats
        """
        success_rate = (
            len(self.successful_bundles) / len(self.submitted_bundles)
            if self.submitted_bundles
            else 0.0
        )
        
        return {
            "total_submitted": len(self.submitted_bundles),
            "successful": len(self.successful_bundles),
            "failed": len(self.failed_bundles),
            "success_rate": success_rate,
            "endpoint": self.relayer_endpoint,
        }
    
    @staticmethod
    def is_available() -> bool:
        """Check if Jito integration is available.
        
        Returns:
            True (always available via HTTP)
        """
        return True
    
    @staticmethod
    def get_jito_tip_account() -> Pubkey:
        """Get Jito tip payment account.
        
        Returns:
            Pubkey of Jito tip account
        """
        # Jito tip payment program account
        # Reference: https://jito-foundation.gitbook.io/mev/mev-payment-and-distribution/tip-payment-program
        return Pubkey.from_string(
            "96gYZGLnJYVFmbjzopPSU6QiEV5fGqZNyN9nmNhvrZU4"
        )


# Convenience function for checking availability
def check_jito_availability() -> bool:
    """Check if Jito integration is available.
    
    Returns:
        True (always available via HTTP)
    """
    return JitoBundleManager.is_available()
