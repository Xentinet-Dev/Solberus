"""
PumpPortal Transaction API Integration.

This module provides integration with PumpPortal's Lightning and Local
Transaction APIs for fast Pump.fun transaction execution.

Reference: https://pumpportal.fun/
"""

import asyncio
import base64
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

import aiohttp
from solders.pubkey import Pubkey
from solders.transaction import Transaction

from core.client import SolanaClient
from core.wallet import Wallet
from trading.base import Trader, TradeResult
from interfaces.core import TokenInfo
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PumpPortalConfig:
    """Configuration for PumpPortal API."""
    
    api_key: Optional[str] = None
    use_lightning: bool = True  # Use Lightning API (fast) or Local API (secure)
    base_url: str = "https://pumpportal.fun/api"
    timeout: float = 10.0


class PumpPortalTrader(Trader):
    """
    Trader using PumpPortal's Lightning/Local Transaction APIs.
    
    PumpPortal provides optimized transaction execution for Pump.fun,
    achieving some of the lowest latencies possible on Solana.
    """
    
    def __init__(
        self,
        client: SolanaClient,
        wallet: Wallet,
        config: Optional[PumpPortalConfig] = None,
    ):
        """Initialize PumpPortal trader.
        
        Args:
            client: Solana RPC client (for Local API)
            wallet: Wallet for signing transactions
            config: PumpPortal configuration
        """
        self.client = client
        self.wallet = wallet
        self.config = config or PumpPortalConfig()
        
        self.session: Optional[aiohttp.ClientSession] = None
        self.total_trades = 0
        self.successful_trades = 0
        self.failed_trades = 0
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            headers = {}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            
            self.session = aiohttp.ClientSession(headers=headers)
        return self.session
    
    async def close(self):
        """Close the HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def execute(self, token_info: TokenInfo) -> TradeResult:
        """Execute buy operation using PumpPortal.
        
        Args:
            token_info: Token to buy
            
        Returns:
            TradeResult with execution details
        """
        if self.config.use_lightning:
            return await self._execute_lightning_buy(token_info)
        else:
            return await self._execute_local_buy(token_info)
    
    async def _execute_lightning_buy(self, token_info: TokenInfo) -> TradeResult:
        """Execute buy using PumpPortal Lightning API.
        
        PumpPortal handles the entire transaction execution.
        Lowest latency option.
        
        Args:
            token_info: Token to buy
            
        Returns:
            TradeResult
        """
        try:
            # Note: Lightning API requires authentication
            # You may need to sign a message or provide API key
            # Check PumpPortal docs for exact requirements
            
            session = await self._get_session()
            
            # Prepare request payload
            # Exact format depends on PumpPortal API - adjust based on docs
            payload = {
                "mint": str(token_info.mint),
                "amount": 0.1,  # Would need to get from token_info or config
                "slippage": 0.3,  # 30%
                "wallet": str(self.wallet.pubkey),
            }
            
            # Add signature if required
            if self.config.api_key:
                payload["apiKey"] = self.config.api_key
            
            url = f"{self.config.base_url}/lightning/buy"
            
            async with session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            ) as response:
                if response.status == 200:
                    result_data = await response.json()
                    
                    if result_data.get("success"):
                        signature = result_data.get("signature")
                        slot = result_data.get("slot")
                        
                        self.total_trades += 1
                        self.successful_trades += 1
                        
                        logger.info(
                            f"Lightning buy successful: {signature} "
                            f"(slot: {slot})"
                        )
                        
                        return TradeResult(
                            success=True,
                            signature=signature,
                            slot=slot,
                        )
                    else:
                        error_msg = result_data.get("error", "Unknown error")
                        logger.error(f"Lightning buy failed: {error_msg}")
                        
                        self.total_trades += 1
                        self.failed_trades += 1
                        
                        return TradeResult(
                            success=False,
                            error_message=error_msg
                        )
                else:
                    error_text = await response.text()
                    error_msg = f"HTTP {response.status}: {error_text}"
                    logger.error(f"Lightning buy request failed: {error_msg}")
                    
                    self.total_trades += 1
                    self.failed_trades += 1
                    
                    return TradeResult(
                        success=False,
                        error_message=error_msg
                    )
                    
        except Exception as e:
            logger.exception(f"Error in lightning buy: {e}")
            self.total_trades += 1
            self.failed_trades += 1
            
            return TradeResult(
                success=False,
                error_message=str(e)
            )
    
    async def _execute_local_buy(self, token_info: TokenInfo) -> TradeResult:
        """Execute buy using PumpPortal Local API.
        
        PumpPortal builds the transaction, you sign and send it.
        Full control and security.
        
        Args:
            token_info: Token to buy
            
        Returns:
            TradeResult
        """
        try:
            session = await self._get_session()
            
            # Request transaction from PumpPortal
            payload = {
                "mint": str(token_info.mint),
                "amount": 0.1,  # Would need to get from token_info or config
                "slippage": 0.3,
                "wallet": str(self.wallet.pubkey),
            }
            
            url = f"{self.config.base_url}/local/buy"
            
            async with session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            ) as response:
                if response.status == 200:
                    result_data = await response.json()
                    
                    # Get transaction from response
                    tx_base64 = result_data.get("transaction")
                    if not tx_base64:
                        return TradeResult(
                            success=False,
                            error_message="No transaction in response"
                        )
                    
                    # Decode transaction
                    tx_bytes = base64.b64decode(tx_base64)
                    # Parse transaction (would need proper parsing)
                    # transaction = Transaction.from_bytes(tx_bytes)
                    
                    # Sign transaction
                    # transaction.sign(self.wallet.keypair)
                    
                    # Send transaction via RPC
                    # signature = await self.client.send_transaction(transaction)
                    
                    # Placeholder - would need actual transaction parsing
                    logger.warning("Local API transaction building not yet fully implemented")
                    
                    return TradeResult(
                        success=False,
                        error_message="Local API implementation incomplete"
                    )
                else:
                    error_text = await response.text()
                    error_msg = f"HTTP {response.status}: {error_text}"
                    logger.error(f"Local buy request failed: {error_msg}")
                    
                    return TradeResult(
                        success=False,
                        error_message=error_msg
                    )
                    
        except Exception as e:
            logger.exception(f"Error in local buy: {e}")
            return TradeResult(
                success=False,
                error_message=str(e)
            )
    
    async def execute_sell(self, token_info: TokenInfo) -> TradeResult:
        """Execute sell operation using PumpPortal.
        
        Args:
            token_info: Token to sell
            
        Returns:
            TradeResult
        """
        if self.config.use_lightning:
            return await self._execute_lightning_sell(token_info)
        else:
            return await self._execute_local_sell(token_info)
    
    async def _execute_lightning_sell(self, token_info: TokenInfo) -> TradeResult:
        """Execute sell using Lightning API."""
        # Similar to _execute_lightning_buy but for sells
        # Placeholder implementation
        logger.warning("Lightning sell not yet implemented")
        return TradeResult(
            success=False,
            error_message="Not yet implemented"
        )
    
    async def _execute_local_sell(self, token_info: TokenInfo) -> TradeResult:
        """Execute sell using Local API."""
        # Similar to _execute_local_buy but for sells
        # Placeholder implementation
        logger.warning("Local sell not yet implemented")
        return TradeResult(
            success=False,
            error_message="Not yet implemented"
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get trading statistics.
        
        Returns:
            Dictionary with stats
        """
        success_rate = (
            self.successful_trades / self.total_trades
            if self.total_trades > 0
            else 0.0
        )
        
        return {
            "total_trades": self.total_trades,
            "successful_trades": self.successful_trades,
            "failed_trades": self.failed_trades,
            "success_rate": success_rate,
            "api_mode": "lightning" if self.config.use_lightning else "local",
        }

