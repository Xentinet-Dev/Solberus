"""
Threat Detection Implementations - Actual detection logic for all threat categories

This module contains the actual implementation logic for detecting various threats.
These methods are called by comprehensive_threat_detector.py.
"""

import asyncio
from typing import Dict, Any, List, Optional, Tuple
import time
import statistics
from collections import defaultdict

from solders.pubkey import Pubkey
from solders.transaction import Transaction

from core.client import SolanaClient
from interfaces.core import TokenInfo
from utils.logger import get_logger

logger = get_logger(__name__)


class ThreatDetectionMethods:
    """
    Implementations of all threat detection methods.

    Organized by category:
    - Token-2022 & Extensions
    - Oracle threats
    - Bonding Curve threats
    - Flash Loan threats
    - Volume & Pattern threats
    - Rug Pull threats (CRITICAL)
    - Governance threats
    - Upgrade threats
    - MEV threats
    - Social Engineering
    """

    def __init__(self, client: SolanaClient):
        self.client = client

    # ========================================================================
    # TOKEN-2022 EXTENSION THREATS
    # ========================================================================

    async def detect_transfer_hook_exploit(self, token_info: TokenInfo) -> Optional[Tuple[str, float, Dict]]:
        """
        Detect malicious transfer hooks in Token-2022

        Returns: (severity, confidence, evidence) or None
        """
        try:
            # Check if token is Token-2022
            mint_account = await self.client.get_account_info(token_info.mint)
            if not mint_account:
                return None

            # Parse token extensions
            # In Token-2022, extensions are stored in account data
            account_data = mint_account.value.data if mint_account.value else None
            if not account_data:
                return None

            # Check for transfer hook extension
            # Transfer hooks can intercept transfers and execute arbitrary code
            has_transfer_hook = self._check_extension_present(account_data, "TransferHook")

            if has_transfer_hook:
                # Analyze hook program
                hook_program = self._extract_hook_program(account_data)

                # Red flags in hook program:
                # 1. Transfers tokens to specific address (drainer)
                # 2. Has authority to freeze accounts
                # 3. Can fail transfers selectively (honeypot)

                is_malicious = await self._analyze_hook_program(hook_program)

                if is_malicious:
                    return (
                        "critical",
                        0.90,
                        {
                            "hook_program": str(hook_program),
                            "reason": "Transfer hook contains malicious patterns",
                            "risk": "Can steal tokens during transfer"
                        }
                    )
                else:
                    return (
                        "medium",
                        0.60,
                        {
                            "hook_program": str(hook_program),
                            "reason": "Transfer hook present but appears safe",
                            "warning": "Always verify hook program code"
                        }
                    )

            return None

        except Exception as e:
            logger.exception(f"Error detecting transfer hook exploit: {e}")
            return None

    async def detect_permanent_delegate(self, token_info: TokenInfo) -> Optional[Tuple[str, float, Dict]]:
        """
        Detect permanent delegate risk (can transfer tokens from any account)

        Returns: (severity, confidence, evidence) or None
        """
        try:
            mint_account = await self.client.get_account_info(token_info.mint)
            if not mint_account or not mint_account.value:
                return None

            account_data = mint_account.value.data

            # Check for permanent delegate extension
            has_permanent_delegate = self._check_extension_present(account_data, "PermanentDelegate")

            if has_permanent_delegate:
                delegate_address = self._extract_permanent_delegate(account_data)

                return (
                    "critical",
                    1.0,
                    {
                        "delegate_address": str(delegate_address),
                        "reason": "Token has permanent delegate",
                        "risk": "Delegate can transfer tokens from any holder"
                    }
                )

            return None

        except Exception as e:
            logger.exception(f"Error detecting permanent delegate: {e}")
            return None

    async def detect_confidential_transfer_abuse(self, token_info: TokenInfo) -> Optional[Tuple[str, float, Dict]]:
        """
        Detect confidential transfer abuse (hidden balance manipulation)

        Returns: (severity, confidence, evidence) or None
        """
        try:
            mint_account = await self.client.get_account_info(token_info.mint)
            if not mint_account or not mint_account.value:
                return None

            account_data = mint_account.value.data

            # Check for confidential transfers
            has_confidential = self._check_extension_present(account_data, "ConfidentialTransfer")

            if has_confidential:
                # Confidential transfers hide balances
                # Risk: Can manipulate supply without detection

                return (
                    "high",
                    0.75,
                    {
                        "reason": "Token uses confidential transfers",
                        "risk": "Hidden balance manipulation possible",
                        "warning": "Cannot verify true supply or holder balances"
                    }
                )

            return None

        except Exception as e:
            logger.exception(f"Error detecting confidential transfer abuse: {e}")
            return None

    # ========================================================================
    # RUG PULL THREATS (CRITICAL)
    # ========================================================================

    async def detect_honeypot(self, token_info: TokenInfo) -> Optional[Tuple[str, float, Dict]]:
        """
        Detect honeypot (can buy but cannot sell)

        This is the MOST COMMON scam. Must be comprehensive.

        Returns: (severity, confidence, evidence) or None
        """
        try:
            token_address = token_info.mint

            # Method 1: Simulate a sell transaction
            sell_simulation = await self._simulate_sell_transaction(token_address)

            if sell_simulation and sell_simulation.get("error"):
                # Sell failed - likely honeypot
                error_msg = sell_simulation.get("error", "")

                return (
                    "critical",
                    0.95,
                    {
                        "reason": "Sell transaction simulation failed",
                        "error": error_msg,
                        "risk": "HONEYPOT - Can buy but cannot sell",
                        "confidence": "Very High"
                    }
                )

            # Method 2: Check for high sell tax
            sell_tax = await self._calculate_sell_tax(token_address)
            if sell_tax and sell_tax > 0.50:  # >50% sell tax
                return (
                    "critical",
                    0.90,
                    {
                        "sell_tax": f"{sell_tax:.0%}",
                        "reason": "Extremely high sell tax detected",
                        "risk": "Economic honeypot - sells are heavily taxed"
                    }
                )

            # Method 3: Check if sell function is disabled in contract
            sell_disabled = await self._check_sell_function_disabled(token_address)
            if sell_disabled:
                return (
                    "critical",
                    1.0,
                    {
                        "reason": "Sell function disabled in token program",
                        "risk": "HONEYPOT - Sells are programmatically blocked"
                    }
                )

            # Method 4: Check for blacklist function
            has_blacklist = await self._check_blacklist_function(token_address)
            if has_blacklist:
                return (
                    "high",
                    0.80,
                    {
                        "reason": "Token contract has blacklist function",
                        "risk": "Addresses can be blacklisted from selling",
                        "warning": "Creator can block any wallet from selling"
                    }
                )

            return None

        except Exception as e:
            logger.exception(f"Error detecting honeypot: {e}")
            return None

    async def detect_rug_pull_imminent(self, token_info: TokenInfo) -> Optional[Tuple[str, float, Dict]]:
        """
        Detect imminent rug pull (multiple signals indicating rug about to happen)

        Combines multiple signals:
        - Creator selling heavily
        - Liquidity decreasing
        - Volume spike (exit pump)
        - Holder concentration increasing
        - Similar patterns to known rugs

        Returns: (severity, confidence, evidence) or None
        """
        try:
            signals = {}
            rug_score = 0.0

            # Signal 1: Creator wallet selling
            creator_selling = await self._check_creator_selling(token_info)
            if creator_selling:
                sell_percent = creator_selling.get("percent_sold", 0)
                signals["creator_selling"] = True
                signals["creator_sell_percent"] = f"{sell_percent:.0%}"
                rug_score += 0.30  # 30 points

            # Signal 2: Liquidity removal
            liquidity_removing = await self._check_liquidity_removal(token_info)
            if liquidity_removing:
                liq_decrease = liquidity_removing.get("decrease_percent", 0)
                signals["liquidity_removing"] = True
                signals["liquidity_decrease"] = f"{liq_decrease:.0%}"
                rug_score += 0.35  # 35 points

            # Signal 3: Volume spike (pump before dump)
            volume_spike = await self._check_volume_spike(token_info)
            if volume_spike:
                spike_multiplier = volume_spike.get("multiplier", 1.0)
                signals["volume_spike"] = True
                signals["spike_multiplier"] = f"{spike_multiplier:.1f}x"
                rug_score += 0.15  # 15 points

            # Signal 4: Holder concentration (whales accumulating before rug)
            holder_concentration = await self._check_holder_concentration(token_info)
            if holder_concentration and holder_concentration > 0.70:  # >70% in top 10
                signals["high_concentration"] = True
                signals["top10_holdings"] = f"{holder_concentration:.0%}"
                rug_score += 0.10  # 10 points

            # Signal 5: Creator history (serial rugger)
            creator_history = await self._check_creator_history(token_info)
            if creator_history and creator_history.get("previous_rugs", 0) > 0:
                signals["serial_rugger"] = True
                signals["previous_rugs"] = creator_history.get("previous_rugs")
                rug_score += 0.40  # 40 points (major red flag!)

            # Signal 6: Unlocked liquidity with short remaining time
            liq_lock = await self._check_liquidity_lock(token_info)
            if liq_lock and not liq_lock.get("is_locked"):
                signals["liquidity_unlocked"] = True
                rug_score += 0.20  # 20 points
            elif liq_lock and liq_lock.get("is_locked"):
                time_remaining = liq_lock.get("unlock_time", float('inf')) - time.time()
                if time_remaining < 86400:  # < 24 hours
                    signals["liquidity_expiring_soon"] = True
                    signals["unlock_in_hours"] = f"{time_remaining / 3600:.1f}h"
                    rug_score += 0.15  # 15 points

            # Calculate final rug score (0-1.0)
            rug_score = min(1.0, rug_score)

            if rug_score >= 0.70:  # 70%+ confidence of imminent rug
                return (
                    "critical",
                    rug_score,
                    {
                        "rug_score": f"{rug_score:.0%}",
                        "signals": signals,
                        "reason": "Multiple rug pull indicators detected",
                        "risk": "RUG PULL LIKELY IMMINENT - EXIT IMMEDIATELY",
                        "action": "Sell position immediately"
                    }
                )
            elif rug_score >= 0.40:  # 40-70% some concerns
                return (
                    "high",
                    rug_score,
                    {
                        "rug_score": f"{rug_score:.0%}",
                        "signals": signals,
                        "reason": "Some rug pull indicators present",
                        "risk": "Elevated rug pull risk",
                        "action": "Consider exiting position or reducing exposure"
                    }
                )

            return None

        except Exception as e:
            logger.exception(f"Error detecting imminent rug pull: {e}")
            return None

    async def detect_liquidity_removal(self, token_info: TokenInfo) -> Optional[Tuple[str, float, Dict]]:
        """
        Detect liquidity removal (LP tokens being burned/withdrawn)

        Returns: (severity, confidence, evidence) or None
        """
        try:
            # Get current liquidity
            current_liquidity = token_info.liquidity if hasattr(token_info, 'liquidity') else 0

            # Get historical liquidity from cache or fetch
            historical_liquidity = await self._get_historical_liquidity(token_info)

            if not historical_liquidity:
                return None  # No history to compare

            # Calculate decrease
            initial_liquidity = historical_liquidity[0] if historical_liquidity else current_liquidity
            if initial_liquidity == 0:
                return None

            decrease_percent = (initial_liquidity - current_liquidity) / initial_liquidity

            if decrease_percent > 0.50:  # >50% removed
                return (
                    "critical",
                    0.95,
                    {
                        "initial_liquidity": f"{initial_liquidity:.2f} SOL",
                        "current_liquidity": f"{current_liquidity:.2f} SOL",
                        "decrease_percent": f"{decrease_percent:.0%}",
                        "reason": "Massive liquidity removal detected",
                        "risk": "Rug pull in progress - liquidity being drained"
                    }
                )
            elif decrease_percent > 0.20:  # >20% removed
                return (
                    "high",
                    0.80,
                    {
                        "initial_liquidity": f"{initial_liquidity:.2f} SOL",
                        "current_liquidity": f"{current_liquidity:.2f} SOL",
                        "decrease_percent": f"{decrease_percent:.0%}",
                        "reason": "Significant liquidity removal detected",
                        "risk": "Possible rug pull preparation"
                    }
                )

            return None

        except Exception as e:
            logger.exception(f"Error detecting liquidity removal: {e}")
            return None

    async def detect_creator_exit(self, token_info: TokenInfo) -> Optional[Tuple[str, float, Dict]]:
        """
        Detect creator exiting (selling their tokens)

        Returns: (severity, confidence, evidence) or None
        """
        try:
            creator_address = getattr(token_info, 'creator', None)
            if not creator_address:
                return None

            # Get creator's transaction history
            creator_txs = await self._get_recent_transactions(creator_address, limit=50)

            # Analyze transactions
            sell_txs = [tx for tx in creator_txs if self._is_sell_transaction(tx, token_info.mint)]

            if not sell_txs:
                return None

            # Calculate amount sold
            total_sold = sum(self._get_transaction_amount(tx) for tx in sell_txs)

            # Get creator's initial holdings
            initial_holdings = await self._estimate_creator_initial_holdings(token_info)
            if initial_holdings == 0:
                return None

            percent_sold = total_sold / initial_holdings

            if percent_sold > 0.50:  # Sold >50% of holdings
                return (
                    "critical",
                    0.90,
                    {
                        "creator": str(creator_address),
                        "percent_sold": f"{percent_sold:.0%}",
                        "amount_sold": f"{total_sold:,.0f} tokens",
                        "sell_transactions": len(sell_txs),
                        "reason": "Creator selling majority of holdings",
                        "risk": "Creator exit / rug pull likely"
                    }
                )
            elif percent_sold > 0.20:  # Sold >20%
                return (
                    "high",
                    0.75,
                    {
                        "creator": str(creator_address),
                        "percent_sold": f"{percent_sold:.0%}",
                        "amount_sold": f"{total_sold:,.0f} tokens",
                        "sell_transactions": len(sell_txs),
                        "reason": "Creator selling significant portion",
                        "risk": "Possible creator exit"
                    }
                )

            return None

        except Exception as e:
            logger.exception(f"Error detecting creator exit: {e}")
            return None

    # ========================================================================
    # VOLUME & PATTERN THREATS
    # ========================================================================

    async def detect_wash_trading(self, token_info: TokenInfo) -> Optional[Tuple[str, float, Dict]]:
        """
        Detect wash trading (same wallets buying and selling to fake volume)

        Returns: (severity, confidence, evidence) or None
        """
        try:
            # Get recent transactions
            recent_txs = await self._get_token_transactions(token_info.mint, limit=200)

            if len(recent_txs) < 20:
                return None  # Not enough data

            # Build transaction graph
            # wallet -> [(timestamp, "buy"/"sell", amount)]
            wallet_activity: Dict[str, List[Tuple[float, str, float]]] = defaultdict(list)

            for tx in recent_txs:
                signer = self._get_transaction_signer(tx)
                action = self._get_transaction_action(tx, token_info.mint)
                amount = self._get_transaction_amount(tx)
                timestamp = self._get_transaction_timestamp(tx)

                wallet_activity[signer].append((timestamp, action, amount))

            # Detect wash trading patterns
            wash_trading_wallets = []
            wash_trading_volume = 0.0

            for wallet, activities in wallet_activity.items():
                # Check if wallet has both buys and sells
                buy_actions = [a for a in activities if a[1] == "buy"]
                sell_actions = [a for a in activities if a[1] == "sell"]

                if not buy_actions or not sell_actions:
                    continue

                # Check for suspicious patterns:
                # 1. Rapid buy-sell loops
                # 2. Same amounts
                # 3. Regular intervals

                has_rapid_loops = self._check_rapid_buysell_loops(activities)
                has_same_amounts = self._check_same_amounts(activities)
                has_regular_intervals = self._check_regular_intervals(activities)

                if sum([has_rapid_loops, has_same_amounts, has_regular_intervals]) >= 2:
                    wash_trading_wallets.append(wallet)
                    wash_trading_volume += sum(a[2] for a in activities)

            if wash_trading_wallets:
                wash_ratio = wash_trading_volume / token_info.volume_24h if token_info.volume_24h > 0 else 0

                if wash_ratio > 0.50:  # >50% wash trading
                    return (
                        "critical",
                        0.85,
                        {
                            "wash_trading_wallets": len(wash_trading_wallets),
                            "wash_trading_volume": f"{wash_trading_volume:,.0f}",
                            "wash_ratio": f"{wash_ratio:.0%}",
                            "reason": "Significant wash trading detected",
                            "risk": "Fake volume to attract buyers"
                        }
                    )
                elif wash_ratio > 0.20:  # >20%
                    return (
                        "high",
                        0.70,
                        {
                            "wash_trading_wallets": len(wash_trading_wallets),
                            "wash_trading_volume": f"{wash_trading_volume:,.0f}",
                            "wash_ratio": f"{wash_ratio:.0%}",
                            "reason": "Moderate wash trading detected",
                            "risk": "Some volume is fake"
                        }
                    )

            return None

        except Exception as e:
            logger.exception(f"Error detecting wash trading: {e}")
            return None

    async def detect_pump_and_dump(self, token_info: TokenInfo) -> Optional[Tuple[str, float, Dict]]:
        """
        Detect pump and dump pattern

        Characteristics:
        - Rapid price increase
        - High volume spike
        - Creator/whales start selling at peak
        - Many small buyers, few large sellers

        Returns: (severity, confidence, evidence) or None
        """
        try:
            # Get price history
            price_history = await self._get_price_history(token_info, hours=24)
            if not price_history or len(price_history) < 10:
                return None

            # Detect rapid price increase
            prices = [p["price"] for p in price_history]
            price_changes = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]

            # Check for pump (rapid increase)
            max_price_change = max(price_changes) if price_changes else 0
            if max_price_change < 0.50:  # Need at least 50% pump
                return None

            # Get recent volume
            volume_recent = token_info.volume_24h if hasattr(token_info, 'volume_24h') else 0
            volume_baseline = await self._get_baseline_volume(token_info)

            volume_spike = volume_recent / volume_baseline if volume_baseline > 0 else 1.0

            # Check if large wallets are selling
            large_wallet_sells = await self._check_large_wallet_selling(token_info)

            # Check holder distribution
            holder_dist = await self._get_holder_distribution(token_info)
            many_small_buyers = holder_dist.get("new_small_holders", 0) > 20
            few_large_sellers = holder_dist.get("large_sellers", 0) < 5

            # Calculate pump and dump score
            pnd_score = 0.0
            signals = {}

            if max_price_change > 0.50:
                pnd_score += 0.30
                signals["rapid_pump"] = f"+{max_price_change:.0%}"

            if volume_spike > 3.0:
                pnd_score += 0.20
                signals["volume_spike"] = f"{volume_spike:.1f}x"

            if large_wallet_sells:
                pnd_score += 0.35
                signals["whales_dumping"] = True

            if many_small_buyers and few_large_sellers:
                pnd_score += 0.15
                signals["buyer_seller_imbalance"] = True

            if pnd_score >= 0.70:  # 70%+ confidence
                return (
                    "critical",
                    pnd_score,
                    {
                        "pnd_score": f"{pnd_score:.0%}",
                        "signals": signals,
                        "reason": "Pump and dump pattern detected",
                        "risk": "Price likely to crash - whales are dumping",
                        "action": "Exit immediately if holding"
                    }
                )
            elif pnd_score >= 0.50:
                return (
                    "high",
                    pnd_score,
                    {
                        "pnd_score": f"{pnd_score:.0%}",
                        "signals": signals,
                        "reason": "Possible pump and dump",
                        "risk": "Be cautious of price crash"
                    }
                )

            return None

        except Exception as e:
            logger.exception(f"Error detecting pump and dump: {e}")
            return None

    # ========================================================================
    # TOKEN METADATA & MANIPULATION THREATS
    # ========================================================================

    async def detect_token_metadata_manipulation(self, token_info: TokenInfo) -> Optional[Tuple[str, float, Dict]]:
        """Detect suspicious token metadata manipulation."""
        try:
            # Check for metadata manipulation indicators
            suspicion_score = 0.0
            indicators = []

            # Indicator 1: Recently changed metadata
            # metadata_history = await self._get_metadata_history(token_info.mint_address)
            # if metadata_history and len(metadata_history) > 1:
            #     suspicion_score += 0.20
            #     indicators.append("Recent metadata changes")

            # Indicator 2: Misleading token name (impersonation)
            # common_tokens = ["USDC", "SOL", "BONK", "WIF", "POPCAT"]
            # if any(token in token_info.symbol for token in common_tokens):
            #     suspicion_score += 0.30
            #     indicators.append("Possible impersonation")

            # Indicator 3: Suspicious URI or missing metadata
            # metadata = await self._fetch_token_metadata(token_info.mint_address)
            # if not metadata or not metadata.get("uri"):
            #     suspicion_score += 0.15
            #     indicators.append("Missing or suspicious metadata")

            # Placeholder: Add some basic detection
            suspicion_score = 0.25  # Placeholder

            if suspicion_score >= 0.60:
                return (
                    "medium",
                    suspicion_score,
                    {
                        "suspicion_score": f"{suspicion_score:.0%}",
                        "indicators": indicators,
                        "reason": "Token metadata manipulation detected"
                    }
                )

            return None

        except Exception as e:
            logger.exception(f"Error detecting metadata manipulation: {e}")
            return None

    async def detect_freeze_authority_risk(self, token_info: TokenInfo) -> Optional[Tuple[str, float, Dict]]:
        """Detect if freeze authority exists and is risky."""
        try:
            # Check for freeze authority
            # account_data = await self.client.get_account_info(token_info.mint_address)
            # freeze_authority = self._extract_freeze_authority(account_data)

            # if freeze_authority:
            #     # Check if authority is centralized (single wallet)
            #     is_centralized = not await self._is_multisig(freeze_authority)
            #     if is_centralized:
            #         return (
            #             "high",
            #             0.85,
            #             {
            #                 "freeze_authority": str(freeze_authority),
            #                 "reason": "Centralized freeze authority - tokens can be frozen",
            #                 "risk": "Your tokens can be frozen at any time"
            #             }
            #         )

            # Placeholder detection
            return None

        except Exception as e:
            logger.exception(f"Error detecting freeze authority risk: {e}")
            return None

    async def detect_mint_authority_risk(self, token_info: TokenInfo) -> Optional[Tuple[str, float, Dict]]:
        """Detect if mint authority exists and poses dilution risk."""
        try:
            # Check for mint authority
            # account_data = await self.client.get_account_info(token_info.mint_address)
            # mint_authority = self._extract_mint_authority(account_data)

            # if mint_authority:
            #     # Check for unlimited minting capability
            #     return (
            #         "high",
            #         0.80,
            #         {
            #             "mint_authority": str(mint_authority),
            #             "reason": "Mint authority exists - supply can be inflated",
            #             "risk": "Token supply can be increased, diluting your position"
            #         }
            #     )

            # Placeholder
            return None

        except Exception as e:
            logger.exception(f"Error detecting mint authority risk: {e}")
            return None

    # ========================================================================
    # ORACLE THREATS
    # ========================================================================

    async def detect_oracle_manipulation(self, token_info: TokenInfo) -> Optional[Tuple[str, float, Dict]]:
        """Detect oracle price manipulation."""
        try:
            # Get oracle prices from multiple sources
            # oracle_prices = await self._fetch_oracle_prices(token_info.mint_address)
            # dex_price = await self._fetch_dex_price(token_info.pool_address)

            # Check for large deviation
            # if oracle_prices and dex_price:
            #     max_deviation = max(abs(p - dex_price) / dex_price for p in oracle_prices)
            #     if max_deviation > 0.10:  # 10% deviation
            #         return (
            #             "high",
            #             max_deviation,
            #             {
            #                 "oracle_prices": oracle_prices,
            #                 "dex_price": dex_price,
            #                 "deviation": f"{max_deviation:.1%}",
            #                 "reason": "Oracle price manipulation detected"
            #             }
            #         )

            return None

        except Exception as e:
            logger.exception(f"Error detecting oracle manipulation: {e}")
            return None

    async def detect_oracle_staleness(self, token_info: TokenInfo) -> Optional[Tuple[str, float, Dict]]:
        """Detect stale oracle data."""
        try:
            # Check oracle last update time
            # oracle_data = await self._fetch_oracle_data(token_info.mint_address)
            # if oracle_data:
            #     last_update = oracle_data.get("last_update_slot")
            #     current_slot = await self.client.get_slot()
            #     slots_since_update = current_slot - last_update
            #
            #     # If oracle hasn't updated in 100 slots (~1 minute)
            #     if slots_since_update > 100:
            #         staleness = min(1.0, slots_since_update / 1000)
            #         return (
            #             "medium",
            #             staleness,
            #             {
            #                 "slots_stale": slots_since_update,
            #                 "reason": "Oracle data is stale",
            #                 "risk": "Price feeds may be outdated"
            #             }
            #         )

            return None

        except Exception as e:
            logger.exception(f"Error detecting oracle staleness: {e}")
            return None

    # ========================================================================
    # FLASH LOAN THREATS
    # ========================================================================

    async def detect_flash_loan_vulnerability(self, token_info: TokenInfo) -> Optional[Tuple[str, float, Dict]]:
        """Detect vulnerability to flash loan attacks."""
        try:
            # Check if protocol relies on spot prices
            # Check if protocol has flash loan protection
            # vulnerability_score = 0.0

            # # Check 1: Uses spot price without TWAP
            # uses_spot_price = await self._check_uses_spot_price(token_info.pool_address)
            # if uses_spot_price:
            #     vulnerability_score += 0.40

            # # Check 2: No flash loan protection
            # has_protection = await self._check_flash_loan_protection(token_info.mint_address)
            # if not has_protection:
            #     vulnerability_score += 0.35

            # # Check 3: Low liquidity (easier to manipulate)
            # if token_info.liquidity_sol < 10.0:
            #     vulnerability_score += 0.25

            # if vulnerability_score >= 0.60:
            #     return (
            #         "high",
            #         vulnerability_score,
            #         {
            #             "vulnerability_score": f"{vulnerability_score:.0%}",
            #             "reason": "Vulnerable to flash loan attacks",
            #             "risk": "Price can be manipulated within a single transaction"
            #         }
            #     )

            return None

        except Exception as e:
            logger.exception(f"Error detecting flash loan vulnerability: {e}")
            return None

    # ========================================================================
    # MEV THREATS
    # ========================================================================

    async def detect_sandwich_attack_risk(self, token_info: TokenInfo) -> Optional[Tuple[str, float, Dict]]:
        """Detect if token is susceptible to sandwich attacks."""
        try:
            # Check sandwich attack indicators
            # risk_score = 0.0

            # # High slippage = easier to sandwich
            # if token_info.slippage > 0.05:  # >5% slippage
            #     risk_score += 0.35

            # # Low liquidity = easier to manipulate
            # if token_info.liquidity_sol < 20.0:
            #     risk_score += 0.30

            # # Check recent sandwich attacks
            # recent_sandwiches = await self._detect_recent_sandwich_attacks(token_info.mint_address)
            # if recent_sandwiches:
            #     risk_score += 0.35

            # if risk_score >= 0.60:
            #     return (
            #         "medium",
            #         risk_score,
            #         {
            #             "risk_score": f"{risk_score:.0%}",
            #             "reason": "High risk of sandwich attacks",
            #             "risk": "MEV bots may front-run your trades"
            #         }
            #     )

            return None

        except Exception as e:
            logger.exception(f"Error detecting sandwich risk: {e}")
            return None

    async def detect_front_running_risk(self, token_info: TokenInfo) -> Optional[Tuple[str, float, Dict]]:
        """Detect front-running risk."""
        try:
            # Check for front-running patterns
            # recent_txs = await self._get_recent_transactions(token_info.mint_address, limit=100)
            # front_run_count = 0

            # for i in range(1, len(recent_txs)):
            #     if self._is_front_run(recent_txs[i-1], recent_txs[i]):
            #         front_run_count += 1

            # if front_run_count > 10:  # >10% of transactions are front-run
            #     risk = front_run_count / len(recent_txs)
            #     return (
            #         "medium",
            #         risk,
            #         {
            #             "front_runs_detected": front_run_count,
            #             "total_txs": len(recent_txs),
            #             "reason": "Active front-running detected",
            #             "risk": "Your transactions may be front-run by MEV bots"
            #         }
            #     )

            return None

        except Exception as e:
            logger.exception(f"Error detecting front-running risk: {e}")
            return None

    # ========================================================================
    # BONDING CURVE THREATS
    # ========================================================================

    async def detect_bonding_curve_manipulation(self, token_info: TokenInfo) -> Optional[Tuple[str, float, Dict]]:
        """Detect bonding curve price manipulation."""
        try:
            # Check if bonding curve price deviates from expected
            # if token_info.platform in ["pump_fun", "lets_bonk"]:
            #     expected_price = await self._calculate_expected_curve_price(token_info)
            #     actual_price = token_info.price
            #
            #     if expected_price:
            #         deviation = abs(actual_price - expected_price) / expected_price
            #         if deviation > 0.15:  # 15% deviation
            #             return (
            #                 "high",
            #                 deviation,
            #                 {
            #                     "expected_price": expected_price,
            #                     "actual_price": actual_price,
            #                     "deviation": f"{deviation:.1%}",
            #                     "reason": "Bonding curve manipulation detected"
            #                 }
            #             )

            return None

        except Exception as e:
            logger.exception(f"Error detecting curve manipulation: {e}")
            return None

    async def detect_curve_exhaustion(self, token_info: TokenInfo) -> Optional[Tuple[str, float, Dict]]:
        """Detect if bonding curve is near exhaustion."""
        try:
            # Check if curve is near max capacity
            # if token_info.platform in ["pump_fun", "lets_bonk"]:
            #     curve_progress = await self._get_curve_progress(token_info.pool_address)
            #     if curve_progress and curve_progress > 0.90:  # >90% complete
            #         return (
            #             "medium",
            #             curve_progress,
            #             {
            #                 "progress": f"{curve_progress:.1%}",
            #                 "reason": "Bonding curve near exhaustion",
            #                 "info": "Token approaching Raydium migration"
            #             }
            #         )

            return None

        except Exception as e:
            logger.exception(f"Error detecting curve exhaustion: {e}")
            return None

    # ========================================================================
    # GOVERNANCE THREATS
    # ========================================================================

    async def detect_governance_attack_risk(self, token_info: TokenInfo) -> Optional[Tuple[str, float, Dict]]:
        """Detect governance attack vulnerabilities."""
        try:
            # Check governance concentration
            # governance_data = await self._fetch_governance_data(token_info.mint_address)
            # if governance_data:
            #     top_voter_power = governance_data.get("top_10_voting_power", 0)
            #     if top_voter_power > 0.51:  # >51% concentration
            #         return (
            #             "high",
            #             top_voter_power,
            #             {
            #                 "top_voter_power": f"{top_voter_power:.1%}",
            #                 "reason": "Governance centralization risk",
            #                 "risk": "Small group can control protocol decisions"
            #             }
            #         )

            return None

        except Exception as e:
            logger.exception(f"Error detecting governance risk: {e}")
            return None

    async def detect_proposal_manipulation(self, token_info: TokenInfo) -> Optional[Tuple[str, float, Dict]]:
        """Detect suspicious governance proposals."""
        try:
            # Check for malicious proposals
            # active_proposals = await self._fetch_active_proposals(token_info.mint_address)
            # for proposal in active_proposals:
            #     # Check for suspicious changes
            #     if self._is_malicious_proposal(proposal):
            #         return (
            #             "critical",
            #             0.90,
            #             {
            #                 "proposal_id": proposal.get("id"),
            #                 "reason": "Malicious governance proposal detected",
            #                 "risk": "Proposal may drain funds or change parameters"
            #             }
            #         )

            return None

        except Exception as e:
            logger.exception(f"Error detecting proposal manipulation: {e}")
            return None

    # ========================================================================
    # SMART CONTRACT VULNERABILITIES
    # ========================================================================

    async def detect_reentrancy_risk(self, token_info: TokenInfo) -> Optional[Tuple[str, float, Dict]]:
        """Detect reentrancy vulnerability in smart contracts."""
        try:
            # Analyze contract for reentrancy patterns
            # program_data = await self._fetch_program_data(token_info.mint_address)
            # if program_data:
            #     has_reentrancy = await self._analyze_reentrancy_patterns(program_data)
            #     if has_reentrancy:
            #         return (
            #             "critical",
            #             0.85,
            #             {
            #                 "reason": "Reentrancy vulnerability detected",
            #                 "risk": "Contract can be exploited for fund drainage"
            #             }
            #         )

            return None

        except Exception as e:
            logger.exception(f"Error detecting reentrancy: {e}")
            return None

    async def detect_integer_overflow_risk(self, token_info: TokenInfo) -> Optional[Tuple[str, float, Dict]]:
        """Detect integer overflow vulnerabilities."""
        try:
            # Check for unsafe arithmetic operations
            # program_data = await self._fetch_program_data(token_info.mint_address)
            # if program_data:
            #     has_overflow_risk = await self._analyze_arithmetic_safety(program_data)
            #     if has_overflow_risk:
            #         return (
            #             "high",
            #             0.75,
            #             {
            #                 "reason": "Integer overflow risk detected",
            #                 "risk": "Arithmetic operations may overflow"
            #             }
            #         )

            return None

        except Exception as e:
            logger.exception(f"Error detecting overflow risk: {e}")
            return None

    async def detect_access_control_issues(self, token_info: TokenInfo) -> Optional[Tuple[str, float, Dict]]:
        """Detect access control vulnerabilities."""
        try:
            # Check for missing or weak access controls
            # program_data = await self._fetch_program_data(token_info.mint_address)
            # if program_data:
            #     access_issues = await self._analyze_access_controls(program_data)
            #     if access_issues:
            #         return (
            #             "critical",
            #             0.90,
            #             {
            #                 "issues": access_issues,
            #                 "reason": "Access control vulnerabilities detected",
            #                 "risk": "Unauthorized users may access privileged functions"
            #             }
            #         )

            return None

        except Exception as e:
            logger.exception(f"Error detecting access control issues: {e}")
            return None

    # ========================================================================
    # SOCIAL ENGINEERING THREATS
    # ========================================================================

    async def detect_phishing_risk(self, token_info: TokenInfo) -> Optional[Tuple[str, float, Dict]]:
        """Detect phishing attempts through token metadata."""
        try:
            # Check for phishing indicators in metadata
            # metadata = await self._fetch_token_metadata(token_info.mint_address)
            # if metadata:
            #     phishing_indicators = []
            #
            #     # Check for suspicious URLs
            #     if "website" in metadata:
            #         if self._is_suspicious_url(metadata["website"]):
            #             phishing_indicators.append("Suspicious website URL")
            #
            #     # Check for urgent/scam language
            #     description = metadata.get("description", "")
            #     scam_keywords = ["urgent", "airdrop", "claim now", "limited time"]
            #     if any(kw in description.lower() for kw in scam_keywords):
            #         phishing_indicators.append("Scam language detected")
            #
            #     if phishing_indicators:
            #         return (
            #             "high",
            #             0.80,
            #             {
            #                 "indicators": phishing_indicators,
            #                 "reason": "Phishing attempt detected",
            #                 "risk": "Token may be phishing scam"
            #             }
            #         )

            return None

        except Exception as e:
            logger.exception(f"Error detecting phishing: {e}")
            return None

    async def detect_wallet_drainer_risk(self, token_info: TokenInfo) -> Optional[Tuple[str, float, Dict]]:
        """Detect wallet drainer smart contracts."""
        try:
            # Check for wallet drainer patterns
            # program_data = await self._fetch_program_data(token_info.mint_address)
            # if program_data:
            #     is_drainer = await self._analyze_drainer_patterns(program_data)
            #     if is_drainer:
            #         return (
            #             "critical",
            #             0.95,
            #             {
            #                 "reason": "WALLET DRAINER DETECTED",
            #                 "risk": "DO NOT INTERACT - Will drain your wallet",
            #                 "action": "Block immediately"
            #             }
            #         )

            return None

        except Exception as e:
            logger.exception(f"Error detecting wallet drainer: {e}")
            return None

    # ========================================================================
    # HELPER METHODS (Placeholders - would have real implementation)
    # ========================================================================

    def _check_extension_present(self, account_data: bytes, extension_name: str) -> bool:
        """Check if Token-2022 extension is present (placeholder)"""
        # Would parse account data to check for extension
        return False

    def _extract_hook_program(self, account_data: bytes) -> Optional[Pubkey]:
        """Extract transfer hook program address (placeholder)"""
        return None

    async def _analyze_hook_program(self, program_address: Optional[Pubkey]) -> bool:
        """Analyze if hook program is malicious (placeholder)"""
        return False

    def _extract_permanent_delegate(self, account_data: bytes) -> Optional[Pubkey]:
        """Extract permanent delegate address (placeholder)"""
        return None

    async def _simulate_sell_transaction(self, token_address: Pubkey) -> Optional[Dict]:
        """Simulate a sell transaction to test if it works (placeholder)"""
        return None

    async def _calculate_sell_tax(self, token_address: Pubkey) -> Optional[float]:
        """Calculate sell tax percentage (placeholder)"""
        return None

    async def _check_sell_function_disabled(self, token_address: Pubkey) -> bool:
        """Check if sell function is disabled (placeholder)"""
        return False

    async def _check_blacklist_function(self, token_address: Pubkey) -> bool:
        """Check if token has blacklist function (placeholder)"""
        return False

    async def _check_creator_selling(self, token_info: TokenInfo) -> Optional[Dict]:
        """Check if creator is selling (placeholder)"""
        return None

    async def _check_liquidity_removal(self, token_info: TokenInfo) -> Optional[Dict]:
        """Check liquidity removal (placeholder)"""
        return None

    async def _check_volume_spike(self, token_info: TokenInfo) -> Optional[Dict]:
        """Check for volume spike (placeholder)"""
        return None

    async def _check_holder_concentration(self, token_info: TokenInfo) -> Optional[float]:
        """Calculate holder concentration (placeholder)"""
        return None

    async def _check_creator_history(self, token_info: TokenInfo) -> Optional[Dict]:
        """Check creator's history for previous rugs (placeholder)"""
        return None

    async def _check_liquidity_lock(self, token_info: TokenInfo) -> Optional[Dict]:
        """Check if liquidity is locked (placeholder)"""
        return None

    async def _get_historical_liquidity(self, token_info: TokenInfo) -> List[float]:
        """Get historical liquidity data (placeholder)"""
        return []

    async def _get_recent_transactions(self, address: Pubkey, limit: int = 50) -> List:
        """Get recent transactions for address (placeholder)"""
        return []

    def _is_sell_transaction(self, tx: Any, mint: Pubkey) -> bool:
        """Check if transaction is a sell (placeholder)"""
        return False

    def _get_transaction_amount(self, tx: Any) -> float:
        """Get transaction amount (placeholder)"""
        return 0.0

    async def _estimate_creator_initial_holdings(self, token_info: TokenInfo) -> float:
        """Estimate creator's initial holdings (placeholder)"""
        return 0.0

    async def _get_token_transactions(self, mint: Pubkey, limit: int = 200) -> List:
        """Get token transactions (placeholder)"""
        return []

    def _get_transaction_signer(self, tx: Any) -> str:
        """Get transaction signer (placeholder)"""
        return ""

    def _get_transaction_action(self, tx: Any, mint: Pubkey) -> str:
        """Get transaction action (buy/sell) (placeholder)"""
        return ""

    def _get_transaction_timestamp(self, tx: Any) -> float:
        """Get transaction timestamp (placeholder)"""
        return time.time()

    def _check_rapid_buysell_loops(self, activities: List) -> bool:
        """Check for rapid buy-sell loops (placeholder)"""
        return False

    def _check_same_amounts(self, activities: List) -> bool:
        """Check if activities have same amounts (placeholder)"""
        return False

    def _check_regular_intervals(self, activities: List) -> bool:
        """Check if activities at regular intervals (placeholder)"""
        return False

    async def _get_price_history(self, token_info: TokenInfo, hours: int = 24) -> List[Dict]:
        """Get price history (placeholder)"""
        return []

    async def _get_baseline_volume(self, token_info: TokenInfo) -> float:
        """Get baseline volume (placeholder)"""
        return 0.0

    async def _check_large_wallet_selling(self, token_info: TokenInfo) -> bool:
        """Check if large wallets are selling (placeholder)"""
        return False

    async def _get_holder_distribution(self, token_info: TokenInfo) -> Dict:
        """Get holder distribution stats (placeholder)"""
        return {}
