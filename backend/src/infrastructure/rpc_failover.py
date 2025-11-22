"""
RPC Failover System for multi-provider reliability.

Provides automatic failover, health monitoring, and load balancing
across multiple Solana RPC providers.
"""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import aiohttp
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment, Processed
from solana.rpc.types import TxOpts
from solders.hash import Hash
from solders.instruction import Instruction
from solders.keypair import Keypair
from solders.message import Message
from solders.pubkey import Pubkey
from solders.transaction import Transaction

from utils.logger import get_logger

logger = get_logger(__name__)


class ProviderStatus(Enum):
    """RPC provider health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ProviderHealth:
    """Health metrics for an RPC provider."""

    endpoint: str
    status: ProviderStatus = ProviderStatus.UNKNOWN
    last_check: float = 0.0
    latency_ms: float = 0.0
    success_rate: float = 1.0
    consecutive_failures: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    recent_latencies: deque = field(default_factory=lambda: deque(maxlen=100))
    last_error: str | None = None

    def update_success(self, latency_ms: float):
        """Update health metrics on successful request."""
        self.total_requests += 1
        self.successful_requests += 1
        self.consecutive_failures = 0
        self.recent_latencies.append(latency_ms)
        self.latency_ms = sum(self.recent_latencies) / len(self.recent_latencies)
        self.success_rate = self.successful_requests / self.total_requests
        self.last_check = time.time()
        self.status = ProviderStatus.HEALTHY
        self.last_error = None

    def update_failure(self, error: str):
        """Update health metrics on failed request."""
        self.total_requests += 1
        self.consecutive_failures += 1
        self.last_check = time.time()
        self.last_error = error

        # Update status based on failures
        if self.consecutive_failures >= 3:
            self.status = ProviderStatus.UNHEALTHY
        elif self.consecutive_failures >= 1:
            self.status = ProviderStatus.DEGRADED
        else:
            self.status = ProviderStatus.HEALTHY

        # Recalculate success rate
        self.success_rate = self.successful_requests / self.total_requests

    def get_score(self) -> float:
        """Calculate provider quality score (0-1, higher is better)."""
        if self.total_requests == 0:
            return 0.5  # Unknown provider gets neutral score

        # Base score from success rate
        score = self.success_rate

        # Penalize high latency (normalize to 0-1, assuming 1000ms is very bad)
        latency_penalty = min(self.latency_ms / 1000.0, 1.0) * 0.2
        score -= latency_penalty

        # Penalize consecutive failures
        failure_penalty = min(self.consecutive_failures / 5.0, 1.0) * 0.3
        score -= failure_penalty

        return max(0.0, min(1.0, score))


class RPCFailoverManager:
    """
    Manages multiple RPC providers with automatic failover and health monitoring.

    Features:
    - Automatic failover on provider failure
    - Health monitoring with latency tracking
    - Load balancing based on provider quality
    - State consistency checking
    - Retry logic with provider rotation
    """

    def __init__(
        self,
        providers: list[str],
        health_check_interval: float = 30.0,
        max_consecutive_failures: int = 3,
        min_success_rate: float = 0.8,
        max_latency_ms: float = 2000.0,
    ):
        """Initialize RPC failover manager.

        Args:
            providers: List of RPC endpoint URLs
            health_check_interval: Seconds between health checks
            max_consecutive_failures: Failures before marking unhealthy
            min_success_rate: Minimum success rate to be considered healthy
            max_latency_ms: Maximum acceptable latency in milliseconds
        """
        if not providers:
            raise ValueError("At least one RPC provider is required")

        self.providers = providers
        self.health_check_interval = health_check_interval
        self.max_consecutive_failures = max_consecutive_failures
        self.min_success_rate = min_success_rate
        self.max_latency_ms = max_latency_ms

        # Initialize health tracking
        self.health: dict[str, ProviderHealth] = {
            endpoint: ProviderHealth(endpoint=endpoint) for endpoint in providers
        }

        # Current active provider
        self._current_provider: str | None = None
        self._provider_lock = asyncio.Lock()

        # Client cache
        self._clients: dict[str, AsyncClient] = {}

        # Health check task
        self._health_check_task: asyncio.Task | None = None
        self._running = False

        # Cached blockhash (shared across providers)
        self._cached_blockhash: Hash | None = None
        self._blockhash_lock = asyncio.Lock()
        self._blockhash_updater_task: asyncio.Task | None = None

    async def start(self):
        """Start health monitoring and blockhash updater."""
        if self._running:
            return

        self._running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        self._blockhash_updater_task = asyncio.create_task(
            self._blockhash_updater_loop()
        )

        # Initial health check
        await self._check_all_providers()

        # Select best provider
        await self._select_best_provider()

    async def stop(self):
        """Stop health monitoring and cleanup."""
        self._running = False

        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        if self._blockhash_updater_task:
            self._blockhash_updater_task.cancel()
            try:
                await self._blockhash_updater_task
            except asyncio.CancelledError:
                pass

        # Close all clients
        for client in self._clients.values():
            try:
                await client.close()
            except Exception:
                pass
        self._clients.clear()

    async def _health_check_loop(self):
        """Background task to periodically check provider health."""
        while self._running:
            try:
                await self._check_all_providers()
                await self._select_best_provider()
            except Exception as e:
                logger.exception(f"Health check loop error: {e!s}")
            finally:
                await asyncio.sleep(self.health_check_interval)

    async def _blockhash_updater_loop(self, interval: float = 5.0):
        """Background task to update cached blockhash."""
        while self._running:
            try:
                blockhash = await self.get_latest_blockhash()
                async with self._blockhash_lock:
                    self._cached_blockhash = blockhash
            except Exception as e:
                logger.warning(f"Blockhash update failed: {e!s}")
            finally:
                await asyncio.sleep(interval)

    async def _check_all_providers(self):
        """Check health of all providers."""
        tasks = [self._check_provider_health(endpoint) for endpoint in self.providers]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _check_provider_health(self, endpoint: str):
        """Check health of a single provider."""
        start_time = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getHealth",
                    },
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    if response.status == 200:
                        latency_ms = (time.time() - start_time) * 1000
                        self.health[endpoint].update_success(latency_ms)
                        logger.debug(
                            f"Provider {endpoint} health check: OK ({latency_ms:.0f}ms)"
                        )
                    else:
                        self.health[endpoint].update_failure(
                            f"HTTP {response.status}"
                        )
        except asyncio.TimeoutError:
            self.health[endpoint].update_failure("Timeout")
        except Exception as e:
            self.health[endpoint].update_failure(str(e))

    async def _select_best_provider(self):
        """Select the best available provider based on health scores."""
        async with self._provider_lock:
            # Get healthy providers sorted by score
            healthy_providers = [
                (endpoint, health)
                for endpoint, health in self.health.items()
                if health.status in (ProviderStatus.HEALTHY, ProviderStatus.DEGRADED)
                and health.success_rate >= self.min_success_rate
                and health.latency_ms <= self.max_latency_ms
            ]

            if not healthy_providers:
                # No healthy providers, use best available
                healthy_providers = [
                    (endpoint, health)
                    for endpoint, health in self.health.items()
                ]
                logger.warning("No healthy providers available, using best available")

            # Sort by score (descending)
            healthy_providers.sort(key=lambda x: x[1].get_score(), reverse=True)

            if healthy_providers:
                best_endpoint = healthy_providers[0][0]
                if best_endpoint != self._current_provider:
                    logger.info(
                        f"Switching to provider: {best_endpoint} "
                        f"(score: {self.health[best_endpoint].get_score():.2f})"
                    )
                    self._current_provider = best_endpoint
            else:
                # Fallback to first provider
                self._current_provider = self.providers[0]
                logger.warning("No providers available, using fallback")

    async def get_current_provider(self) -> str:
        """Get the current active provider endpoint."""
        async with self._provider_lock:
            if self._current_provider is None:
                await self._select_best_provider()
            return self._current_provider or self.providers[0]

    async def get_client(self) -> AsyncClient:
        """Get AsyncClient for current provider."""
        provider = await self.get_current_provider()

        if provider not in self._clients:
            self._clients[provider] = AsyncClient(provider)

        return self._clients[provider]

    async def _execute_with_failover(
        self, func, *args, max_retries: int = 3, **kwargs
    ):
        """Execute a function with automatic failover on failure."""
        last_error = None
        attempted_providers = set()

        for attempt in range(max_retries):
            provider = await self.get_current_provider()

            # If we've tried all providers, reset
            if len(attempted_providers) >= len(self.providers):
                attempted_providers.clear()

            # Skip if we've already tried this provider
            if provider in attempted_providers:
                await self._select_best_provider()
                provider = await self.get_current_provider()

            attempted_providers.add(provider)

            try:
                start_time = time.time()
                result = await func(*args, **kwargs)
                latency_ms = (time.time() - start_time) * 1000

                # Update health on success
                self.health[provider].update_success(latency_ms)
                return result

            except Exception as e:
                last_error = e
                error_msg = str(e)
                self.health[provider].update_failure(error_msg)

                logger.warning(
                    f"Provider {provider} failed (attempt {attempt + 1}/{max_retries}): {error_msg}"
                )

                # Select new provider for next attempt
                await self._select_best_provider()

                # Wait before retry (exponential backoff)
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5 * (2**attempt))

        # All retries failed
        raise RuntimeError(
            f"All providers failed after {max_retries} attempts. Last error: {last_error!s}"
        ) from last_error

    async def get_latest_blockhash(self) -> Hash:
        """Get latest blockhash with failover."""
        client = await self.get_client()

        async def _get_blockhash():
            return await client.get_latest_blockhash(commitment=Processed)

        result = await self._execute_with_failover(_get_blockhash)
        return result.value.blockhash

    async def get_cached_blockhash(self) -> Hash:
        """Get cached blockhash."""
        async with self._blockhash_lock:
            if self._cached_blockhash is None:
                self._cached_blockhash = await self.get_latest_blockhash()
            return self._cached_blockhash

    async def send_transaction(
        self, transaction: Transaction, opts: TxOpts | None = None
    ) -> str:
        """Send transaction with failover."""
        client = await self.get_client()

        async def _send():
            return await client.send_transaction(transaction, opts=opts)

        result = await self._execute_with_failover(_send)
        return str(result.value)

    async def confirm_transaction(
        self, signature: str, commitment: Commitment = Processed
    ) -> bool:
        """Confirm transaction with failover."""
        client = await self.get_client()

        async def _confirm():
            await client.confirm_transaction(
                signature, commitment=commitment, sleep_seconds=1
            )
            return True

        try:
            await self._execute_with_failover(_confirm, max_retries=5)
            return True
        except Exception:
            logger.exception(f"Failed to confirm transaction {signature}")
            return False

    async def post_rpc(self, body: dict[str, Any]) -> dict[str, Any] | None:
        """Send raw RPC request with failover."""
        provider = await self.get_current_provider()

        async def _post():
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    provider,
                    json=body,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    response.raise_for_status()
                    return await response.json()

        try:
            return await self._execute_with_failover(_post)
        except Exception:
            logger.exception("RPC request failed after failover")
            return None

    def get_health_summary(self) -> dict[str, Any]:
        """Get health summary of all providers."""
        return {
            endpoint: {
                "status": health.status.value,
                "latency_ms": health.latency_ms,
                "success_rate": health.success_rate,
                "consecutive_failures": health.consecutive_failures,
                "total_requests": health.total_requests,
                "score": health.get_score(),
                "last_error": health.last_error,
            }
            for endpoint, health in self.health.items()
        }

    async def close(self):
        """Close all connections."""
        await self.stop()


