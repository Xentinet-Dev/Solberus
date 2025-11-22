"""
Solana client abstraction for blockchain operations.
"""

import asyncio
import json
import struct
from typing import Any, List, Optional

import aiohttp
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Processed
from solana.rpc.types import TxOpts
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
from solders.hash import Hash
from solders.instruction import Instruction
from solders.keypair import Keypair
from solders.message import Message
from solders.pubkey import Pubkey
from solders.transaction import Transaction

from utils.logger import get_logger

logger = get_logger(__name__)

# Global connection pool for performance (Performance Optimization #3)
_session_pool: Optional[aiohttp.ClientSession] = None
_session_lock = asyncio.Lock()

# Optional import for failover support
try:
    from infrastructure.rpc_failover import RPCFailoverManager
    FAILOVER_AVAILABLE = True
except ImportError:
    FAILOVER_AVAILABLE = False
    RPCFailoverManager = None


def set_loaded_accounts_data_size_limit(bytes_limit: int) -> Instruction:
    """
    Create SetLoadedAccountsDataSizeLimit instruction to reduce CU consumption.

    By default, Solana transactions can load up to 64MB of account data,
    costing 16k CU (8 CU per 32KB). Setting a lower limit reduces CU
    consumption and improves transaction priority.

    NOTE: CU savings are NOT visible in "consumed CU" metrics, which only
    show execution CU. The 16k CU loaded accounts overhead is counted
    separately for transaction priority/cost calculation.

    Args:
        bytes_limit: Max account data size in bytes (e.g., 512_000 = 512KB)

    Returns:
        Compute Budget instruction with discriminator 4

    Reference:
        https://www.anza.xyz/blog/cu-optimization-with-setloadedaccountsdatasizelimit
    """
    COMPUTE_BUDGET_PROGRAM = Pubkey.from_string(
        "ComputeBudget111111111111111111111111111111"
    )

    data = struct.pack("<BI", 4, bytes_limit)
    return Instruction(COMPUTE_BUDGET_PROGRAM, data, [])


class SolanaClient:
    """Abstraction for Solana RPC client operations with optional failover support."""

    def __init__(
        self,
        rpc_endpoint: str | list[str],
        use_failover: bool | None = None,
        failover_config: dict[str, Any] | None = None,
    ):
        """Initialize Solana client with RPC endpoint(s).

        Args:
            rpc_endpoint: Single RPC endpoint URL (str) or list of endpoints for failover
            use_failover: If True, use failover manager when multiple endpoints provided.
                         If None, auto-detect (use failover if list provided and available).
            failover_config: Optional configuration for failover manager
        """
        # Handle single endpoint (backward compatible)
        if isinstance(rpc_endpoint, str):
            self.rpc_endpoints = [rpc_endpoint]
            self.rpc_endpoint = rpc_endpoint  # Keep for backward compatibility
            auto_failover = False
        else:
            self.rpc_endpoints = rpc_endpoint
            self.rpc_endpoint = rpc_endpoint[0] if rpc_endpoint else ""  # First for compatibility
            auto_failover = len(rpc_endpoint) > 1

        # Determine if we should use failover
        if use_failover is None:
            use_failover = auto_failover and FAILOVER_AVAILABLE
        else:
            use_failover = use_failover and FAILOVER_AVAILABLE

        self.use_failover = use_failover

        if self.use_failover:
            # Use failover manager
            failover_config = failover_config or {}
            self.failover_manager = RPCFailoverManager(
                providers=self.rpc_endpoints,
                **failover_config
            )
            self._client = None  # Will use failover manager's client
            self._cached_blockhash: Hash | None = None
            self._blockhash_lock = asyncio.Lock()
            self._failover_started = False
        else:
            # Use single endpoint (original behavior)
            self.failover_manager = None
            self._client = None
            self._cached_blockhash: Hash | None = None
            self._blockhash_lock = asyncio.Lock()
            self._blockhash_updater_task: Optional[asyncio.Task] = None
            self._blockhash_updater_started = False

    async def start_blockhash_updater(self, interval: float = 5.0):
        """Start background task to update recent blockhash (single endpoint mode)."""
        if self.use_failover:
            # Failover manager handles blockhash updates
            return
        
        while True:
            try:
                blockhash = await self.get_latest_blockhash()
                async with self._blockhash_lock:
                    self._cached_blockhash = blockhash
            except Exception as e:
                logger.warning(f"Blockhash fetch failed: {e!s}")
            finally:
                await asyncio.sleep(interval)

    def _ensure_blockhash_updater_started(self):
        """Start blockhash updater task if not already started and event loop is running."""
        if self.use_failover or self._blockhash_updater_started:
            return
        
        try:
            # Check if there's a running event loop
            loop = asyncio.get_running_loop()
            # Only create task if we have a running loop and task doesn't exist
            if self._blockhash_updater_task is None:
                self._blockhash_updater_task = loop.create_task(
                    self.start_blockhash_updater()
                )
                self._blockhash_updater_started = True
                logger.debug("Blockhash updater task started")
        except RuntimeError:
            # No running event loop - will start lazily when needed
            pass
    
    async def get_cached_blockhash(self) -> Hash:
        """Return the most recently cached blockhash."""
        if self.use_failover:
            return await self.failover_manager.get_cached_blockhash()
        
        # Ensure blockhash updater is started (lazy initialization)
        self._ensure_blockhash_updater_started()
        
        async with self._blockhash_lock:
            if self._cached_blockhash is None:
                # Fallback to fetching latest if not cached
                self._cached_blockhash = await self.get_latest_blockhash()
            return self._cached_blockhash

    async def get_client(self) -> AsyncClient:
        """Get or create the AsyncClient instance.

        Returns:
            AsyncClient instance
        """
        if self.use_failover:
            # Start failover manager if not already started
            if not self._failover_started:
                await self.failover_manager.start()
                self._failover_started = True
            return await self.failover_manager.get_client()
        
        if self._client is None:
            self._client = AsyncClient(self.rpc_endpoint)
        return self._client

    async def close(self):
        """Close the client connection and stop background tasks."""
        if self.use_failover:
            if self.failover_manager:
                await self.failover_manager.stop()
            return
        
        if self._blockhash_updater_task:
            self._blockhash_updater_task.cancel()
            try:
                await self._blockhash_updater_task
            except asyncio.CancelledError:
                pass

        if self._client:
            await self._client.close()
            self._client = None

    async def get_health(self) -> str | None:
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getHealth",
        }
        result = await self.post_rpc(body)
        if result and "result" in result:
            return result["result"]
        return None

    async def get_account_info(self, pubkey: Pubkey) -> dict[str, Any]:
        """Get account info from the blockchain.

        Args:
            pubkey: Public key of the account

        Returns:
            Account info response

        Raises:
            ValueError: If account doesn't exist or has no data
        """
        client = await self.get_client()
        response = await client.get_account_info(
            pubkey, encoding="base64"
        )  # base64 encoding for account data by default
        if not response.value:
            raise ValueError(f"Account {pubkey} not found")
        return response.value

    async def get_multiple_accounts(
        self, pubkeys: List[Pubkey]
    ) -> List[Optional[dict[str, Any]]]:
        """Batch get account info for multiple accounts (Performance Optimization #4).

        Args:
            pubkeys: List of public keys to fetch

        Returns:
            List of account info responses (None if account doesn't exist)
        """
        if not pubkeys:
            return []
        
        client = await self.get_client()
        response = await client.get_multiple_accounts(pubkeys, encoding="base64")
        
        if response.value:
            return [acc.data if acc else None for acc in response.value]
        return [None] * len(pubkeys)

    @staticmethod
    async def get_session() -> aiohttp.ClientSession:
        """Get or create shared HTTP session for connection pooling (Performance Optimization #3).

        Returns:
            Shared aiohttp.ClientSession
        """
        global _session_pool
        
        async with _session_lock:
            if _session_pool is None or _session_pool.closed:
                connector = aiohttp.TCPConnector(
                    limit=100,  # Total connection pool size
                    limit_per_host=10,  # Max connections per host
                    ttl_dns_cache=300,  # DNS cache TTL
                    force_close=False,  # Reuse connections
                )
                timeout = aiohttp.ClientTimeout(total=30, connect=10)
                _session_pool = aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout,
                )
                logger.debug("Created new HTTP session pool")
        
        return _session_pool

    @staticmethod
    async def close_session_pool() -> None:
        """Close the global session pool."""
        global _session_pool
        
        async with _session_lock:
            if _session_pool and not _session_pool.closed:
                await _session_pool.close()
                _session_pool = None
                logger.debug("Closed HTTP session pool")

    async def get_balance(self, pubkey: Pubkey) -> int:
        """Get SOL balance for an account.
        
        Args:
            pubkey: Public key of the account
            
        Returns:
            Balance in lamports
        """
        client = await self.get_client()
        response = await client.get_balance(pubkey)
        if response.value is not None:
            return response.value
        return 0

    async def get_token_account_balance(self, token_account: Pubkey) -> int:
        """Get token balance for an account.
        
        Args:
            token_account: Token account address
            
        Returns:
            Token balance as integer
        """
        client = await self.get_client()
        response = await client.get_token_account_balance(token_account)
        if response.value:
            return int(response.value.amount)
        return 0

    async def get_latest_blockhash(self) -> Hash:
        """Get the latest blockhash.

        Returns:
            Recent blockhash as string
        """
        if self.use_failover:
            return await self.failover_manager.get_latest_blockhash()
        
        client = await self.get_client()
        response = await client.get_latest_blockhash(commitment="processed")
        return response.value.blockhash

    async def build_and_send_transaction(
        self,
        instructions: list[Instruction],
        signer_keypair: Keypair,
        skip_preflight: bool = True,
        max_retries: int = 3,
        priority_fee: int | None = None,
        compute_unit_limit: int | None = None,
        account_data_size_limit: int | None = None,
    ) -> str:
        """
        Send a transaction with optional priority fee and compute unit limit.

        Args:
            instructions: List of instructions to include in the transaction.
            signer_keypair: Keypair to sign the transaction.
            skip_preflight: Whether to skip preflight checks.
            max_retries: Maximum number of retry attempts.
            priority_fee: Optional priority fee in microlamports.
            compute_unit_limit: Optional compute unit limit. Defaults to 85,000 if not provided.
            account_data_size_limit: Optional account data size limit in bytes (e.g., 512_000).
                                    Reduces CU cost from 16k to ~128 CU. Must be first instruction.

        Returns:
            Transaction signature.
        """
        client = await self.get_client()

        logger.info(
            f"Priority fee in microlamports: {priority_fee if priority_fee else 0}"
        )

        # Add compute budget instructions if applicable
        if (
            priority_fee is not None
            or compute_unit_limit is not None
            or account_data_size_limit is not None
        ):
            fee_instructions = []

            if account_data_size_limit is not None:
                fee_instructions.append(
                    set_loaded_accounts_data_size_limit(account_data_size_limit)
                )
                logger.info(f"Account data size limit: {account_data_size_limit} bytes")

            # Set compute unit limit (use provided value or default to 85,000)
            cu_limit = compute_unit_limit if compute_unit_limit is not None else 85_000
            fee_instructions.append(set_compute_unit_limit(cu_limit))

            # Set priority fee if provided
            if priority_fee is not None:
                fee_instructions.append(set_compute_unit_price(priority_fee))

            instructions = fee_instructions + instructions

        recent_blockhash = await self.get_cached_blockhash()
        message = Message(instructions, signer_keypair.pubkey())
        transaction = Transaction([signer_keypair], message, recent_blockhash)

        for attempt in range(max_retries):
            try:
                tx_opts = TxOpts(
                    skip_preflight=skip_preflight, preflight_commitment=Processed
                )
                response = await client.send_transaction(transaction, tx_opts)
                return response.value

            except Exception as e:
                if attempt == max_retries - 1:
                    logger.exception(
                        f"Failed to send transaction after {max_retries} attempts"
                    )
                    raise

                wait_time = 2**attempt
                logger.warning(
                    f"Transaction attempt {attempt + 1} failed: {e!s}, retrying in {wait_time}s"
                )
                await asyncio.sleep(wait_time)

    async def build_transaction(
        self,
        instructions: list[Instruction],
        signer_keypair: Keypair,
        priority_fee: int | None = None,
        compute_unit_limit: int | None = None,
        account_data_size_limit: int | None = None,
    ) -> Transaction:
        """
        Build a transaction without sending it (for bundling).
        
        Args:
            instructions: List of instructions to include in the transaction.
            signer_keypair: Keypair to sign the transaction.
            priority_fee: Optional priority fee in microlamports.
            compute_unit_limit: Optional compute unit limit. Defaults to 85,000 if not provided.
            account_data_size_limit: Optional account data size limit in bytes.
            
        Returns:
            Built and signed Transaction (ready for bundling).
        """
        # Add compute budget instructions if applicable
        if (
            priority_fee is not None
            or compute_unit_limit is not None
            or account_data_size_limit is not None
        ):
            fee_instructions = []

            if account_data_size_limit is not None:
                fee_instructions.append(
                    set_loaded_accounts_data_size_limit(account_data_size_limit)
                )

            # Set compute unit limit (use provided value or default to 85,000)
            cu_limit = compute_unit_limit if compute_unit_limit is not None else 85_000
            fee_instructions.append(set_compute_unit_limit(cu_limit))

            # Set priority fee if provided
            if priority_fee is not None:
                fee_instructions.append(set_compute_unit_price(priority_fee))

            instructions = fee_instructions + instructions

        # Get recent blockhash
        recent_blockhash = await self.get_cached_blockhash()
        
        # Build message
        message = Message(instructions, signer_keypair.pubkey())
        
        # Create and sign transaction
        transaction = Transaction([signer_keypair], message, recent_blockhash)
        
        return transaction

    async def confirm_transaction(
        self, signature: str, commitment: str = "confirmed"
    ) -> bool:
        """Wait for transaction confirmation.

        Args:
            signature: Transaction signature
            commitment: Confirmation commitment level

        Returns:
            Whether transaction was confirmed
        """
        if self.use_failover:
            return await self.failover_manager.confirm_transaction(signature, commitment)
        
        client = await self.get_client()
        try:
            await client.confirm_transaction(
                signature, commitment=commitment, sleep_seconds=1
            )
            return True
        except Exception:
            logger.exception(f"Failed to confirm transaction {signature}")
            return False

    async def post_rpc(self, body: dict[str, Any]) -> dict[str, Any] | None:
        """
        Send a raw RPC request to the Solana node (uses connection pool).

        Args:
            body: JSON-RPC request body.

        Returns:
            Optional[Dict[str, Any]]: Parsed JSON response, or None if the request fails.
        """
        if self.use_failover:
            return await self.failover_manager.post_rpc(body)
        
        try:
            # Use shared connection pool for better performance
            session = await self.get_session()
            async with session.post(
                self.rpc_endpoint,
                json=body,
            ) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError:
            logger.exception("RPC request failed")
            return None
        except json.JSONDecodeError:
            logger.exception("Failed to decode RPC response")
            return None
