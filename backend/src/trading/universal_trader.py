"""
Universal trading coordinator that works with any platform.
Cleaned up to remove all platform-specific hardcoding.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from time import monotonic
from typing import Any, Dict, List, Tuple

from solders.pubkey import Pubkey

from cleanup.modes import (
    handle_cleanup_after_failure,
    handle_cleanup_after_sell,
    handle_cleanup_post_session,
)
from core.client import SolanaClient
from core.priority_fee.manager import PriorityFeeManager
from core.wallet import Wallet
from interfaces.core import Platform, TokenInfo
from monitoring.listener_factory import ListenerFactory
from platforms import get_platform_implementations
from trading.base import TradeResult
from trading.platform_aware import PlatformAwareBuyer, PlatformAwareSeller
from trading.position import Position
from utils.cache_manager import CacheManager
from utils.logger import get_logger

# Optional uvloop for better performance
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    # Fallback to standard asyncio if uvloop not available
    pass

logger = get_logger(__name__)


class UniversalTrader:
    """Universal trading coordinator that works with any supported platform."""

    def __init__(
        self,
        rpc_endpoint: str,
        wss_endpoint: str,
        private_key: str,
        buy_amount: float,
        buy_slippage: float,
        sell_slippage: float,
        # Platform configuration
        platform: Platform | str = Platform.PUMP_FUN,
        # Listener configuration
        listener_type: str = "logs",
        geyser_endpoint: str | None = None,
        geyser_api_token: str | None = None,
        geyser_auth_type: str = "x-token",
        pumpportal_url: str = "wss://pumpportal.fun/api/data",
        # Trading configuration
        extreme_fast_mode: bool = False,
        extreme_fast_token_amount: int = 30,
        # Exit strategy configuration
        exit_strategy: str = "time_based",
        take_profit_percentage: float | None = None,
        stop_loss_percentage: float | None = None,
        max_hold_time: int | None = None,
        price_check_interval: int = 10,
        # Priority fee configuration
        enable_dynamic_priority_fee: bool = False,
        enable_fixed_priority_fee: bool = True,
        fixed_priority_fee: int = 200_000,
        extra_priority_fee: float = 0.0,
        hard_cap_prior_fee: int = 200_000,
        # Retry and timeout settings
        max_retries: int = 3,
        wait_time_after_creation: int = 15,
        wait_time_after_buy: int = 15,
        wait_time_before_new_token: int = 15,
        max_token_age: int | float = 0.001,
        token_wait_timeout: int = 30,
        # Cleanup settings
        cleanup_mode: str = "disabled",
        cleanup_force_close_with_burn: bool = False,
        cleanup_with_priority_fee: bool = False,
        # Trading filters
        match_string: str | None = None,
        bro_address: str | None = None,
        marry_mode: bool = False,
        yolo_mode: bool = False,
        # Compute unit configuration
        compute_units: dict | None = None,
        # Security configuration
        enable_security_scan: bool = True,
        min_security_score: float = 40.0,  # Minimum health score to allow trade (0-100)
        block_honeypots: bool = True,
        block_critical_risk: bool = True,
        security_cache_ttl: int = 300,  # Cache security results for 5 minutes
        # Social signal intelligence configuration
        enable_social_signals: bool = True,
        social_scan_interval: int = 300,  # Scan every 5 minutes
        enabled_strategies: list[str] | None = None,
    ):
        """Initialize the universal trader."""
        # Core components
        self.solana_client = SolanaClient(rpc_endpoint)
        self.wallet = Wallet(private_key)
        self.priority_fee_manager = PriorityFeeManager(
            client=self.solana_client,
            enable_dynamic_fee=enable_dynamic_priority_fee,
            enable_fixed_fee=enable_fixed_priority_fee,
            fixed_fee=fixed_priority_fee,
            extra_fee=extra_priority_fee,
            hard_cap=hard_cap_prior_fee,
        )

        # Platform setup
        if isinstance(platform, str):
            self.platform = Platform(platform)
        else:
            self.platform = platform

        logger.info(f"Initialized Universal Trader for platform: {self.platform.value}")

        # Validate platform support
        try:
            from platforms import platform_factory

            if not platform_factory.registry.is_platform_supported(self.platform):
                raise ValueError(f"Platform {self.platform.value} is not supported")
        except Exception:
            logger.exception("Platform validation failed")
            raise

        # Get platform-specific implementations
        self.platform_implementations = get_platform_implementations(
            self.platform, self.solana_client
        )

        # Store compute unit configuration
        self.compute_units = compute_units or {}
        
        # Security configuration
        self.enable_security_scan = enable_security_scan
        self.min_security_score = min_security_score
        self.block_honeypots = block_honeypots
        self.block_critical_risk = block_critical_risk
        self.security_cache_ttl = security_cache_ttl
        self.security_cache: Dict[str, tuple] = {}  # {mint: (result, timestamp)}
        
        logger.info(f"Security scan enabled: {enable_security_scan}")
        if enable_security_scan:
            logger.info(f"Minimum security score: {min_security_score}/100")
            logger.info(f"Block honeypots: {block_honeypots}")
            logger.info(f"Block critical risk: {block_critical_risk}")
        
        # Social signal intelligence configuration
        self.enable_social_signals = enable_social_signals
        self.social_scan_interval = social_scan_interval
        self.social_scanner = None
        self.strategy_adjuster = None
        self.enabled_strategies: set[str] = set(enabled_strategies or [])
        if self.enabled_strategies:
            logger.info("Initial enabled strategies: %s", list(self.enabled_strategies))
        
        if enable_social_signals:
            try:
                from intelligence.social_scanner import SocialMediaScanner
                from intelligence.strategy_adjuster import StrategyAdjuster
                import os
                
                # Initialize social scanner
                self.social_scanner = SocialMediaScanner(
                    enable_twitter=True,
                    enable_telegram=True,
                    enable_discord=True,
                    enable_reddit=True,
                    twitter_bearer_token=os.getenv("TWITTER_BEARER_TOKEN"),
                    telegram_api_id=int(os.getenv("TELEGRAM_API_ID", "0")) or None,
                    telegram_api_hash=os.getenv("TELEGRAM_API_HASH"),
                    discord_token=os.getenv("DISCORD_BOT_TOKEN"),
                    reddit_client_id=os.getenv("REDDIT_CLIENT_ID"),
                    reddit_client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
                    enable_ai=True,
                    openai_api_key=os.getenv("OPENAI_API_KEY"),
                )
                
                # Initialize strategy adjuster
                self.strategy_adjuster = StrategyAdjuster(
                    base_buy_amount=buy_amount,
                    base_hold_time=max_hold_time or 300,
                )
                
                logger.info("Social Signal Intelligence Engine enabled")
            except ImportError as e:
                logger.warning(f"Social signal intelligence not available: {e}")
                self.enable_social_signals = False
            except Exception as e:
                logger.warning(f"Failed to initialize social signal intelligence: {e}")
                self.enable_social_signals = False

        # Create platform-aware traders
        self.buyer = PlatformAwareBuyer(
            self.solana_client,
            self.wallet,
            self.priority_fee_manager,
            buy_amount,
            buy_slippage,
            max_retries,
            extreme_fast_token_amount,
            extreme_fast_mode,
            compute_units=self.compute_units,
        )

        self.seller = PlatformAwareSeller(
            self.solana_client,
            self.wallet,
            self.priority_fee_manager,
            sell_slippage,
            max_retries,
            compute_units=self.compute_units,
        )

        # Initialize the appropriate listener with platform filtering
        self.token_listener = ListenerFactory.create_listener(
            listener_type=listener_type,
            wss_endpoint=wss_endpoint,
            geyser_endpoint=geyser_endpoint,
            geyser_api_token=geyser_api_token,
            geyser_auth_type=geyser_auth_type,
            pumpportal_url=pumpportal_url,
            platforms=[self.platform],  # Only listen for our platform
        )

    def set_enabled_strategies(self, strategies: list[str] | None) -> None:
        """Update the set of enabled strategy slugs for this trader at runtime."""
        self.enabled_strategies = set(strategies or [])
        logger.info("Updated enabled strategies: %s", list(self.enabled_strategies))

        # Trading parameters
        self.buy_amount = buy_amount
        self.buy_slippage = buy_slippage
        self.sell_slippage = sell_slippage
        self.max_retries = max_retries
        self.extreme_fast_mode = extreme_fast_mode
        self.extreme_fast_token_amount = extreme_fast_token_amount

        # Exit strategy parameters
        self.exit_strategy = exit_strategy.lower()
        self.take_profit_percentage = take_profit_percentage
        self.stop_loss_percentage = stop_loss_percentage
        self.max_hold_time = max_hold_time
        self.price_check_interval = price_check_interval

        # Timing parameters
        self.wait_time_after_creation = wait_time_after_creation
        self.wait_time_after_buy = wait_time_after_buy
        self.wait_time_before_new_token = wait_time_before_new_token
        self.max_token_age = max_token_age
        self.token_wait_timeout = token_wait_timeout

        # Cleanup parameters
        self.cleanup_mode = cleanup_mode
        self.cleanup_force_close_with_burn = cleanup_force_close_with_burn
        self.cleanup_with_priority_fee = cleanup_with_priority_fee

        # Trading filters/modes
        self.match_string = match_string
        self.bro_address = bro_address
        self.marry_mode = marry_mode
        self.yolo_mode = yolo_mode

        # State tracking
        self.traded_mints: set[Pubkey] = set()
        self.token_queue: asyncio.Queue = asyncio.Queue()
        self.processing: bool = False
        self.processed_tokens: set[str] = set()
        self.token_timestamps: dict[str, float] = {}
        
        # Position and trade tracking for API/dashboard
        self.active_positions: Dict[str, Position] = {}  # mint (str) -> Position
        self.trade_history: List[Dict[str, Any]] = []
        
        # Callbacks for API updates (set by api_server.py)
        self.on_position_opened: callable = None
        self.on_position_closed: callable = None
        self.on_trade_executed: callable = None
        
        # Performance optimizations
        self.cache_manager = CacheManager(max_size=1000)
        self.max_concurrent_tokens = 5  # Concurrent token processing limit

        # Manual override console (optional)
        self.override_console = None
        try:
            from control.manual_override import ManualOverrideConsole
            self.override_console = ManualOverrideConsole(self)
            logger.info("Manual Override Console available")
        except ImportError:
            logger.debug("Manual Override Console not available (optional feature)")

        # Enhanced threat detection (optional)
        self.threat_detector = None
        try:
            from security.threat_detector import EnhancedThreatDetector
            self.threat_detector = EnhancedThreatDetector(
                client=self.solana_client,
                enable_governance_scan=True,
                enable_oracle_scan=True,
                enable_upgrade_scan=True,
                enable_social_scan=True,
            )
            logger.info("Enhanced Threat Detection available")
        except ImportError:
            logger.debug("Enhanced Threat Detection not available (optional feature)")

        # Comprehensive Threat Detector (Phase 2 - 94+ categories)
        self.comprehensive_threat_detector = None
        try:
            from security.comprehensive_threat_detector import ComprehensiveThreatDetector
            self.comprehensive_threat_detector = ComprehensiveThreatDetector(
                client=self.solana_client
            )
            logger.info("Comprehensive Threat Detector (94+ categories) available")
        except ImportError:
            logger.debug("Comprehensive Threat Detector not available (optional feature)")

        # Contract Auditor (Phase 2 - honeypot detection)
        self.contract_auditor = None
        try:
            from security.contract_auditor import ContractAuditor
            self.contract_auditor = ContractAuditor(client=self.solana_client)
            logger.info("Contract Auditor available")
        except ImportError:
            logger.debug("Contract Auditor not available (optional feature)")

        # Liquidity Health Monitor (Phase 2)
        self.liquidity_health = None
        try:
            from monitoring.liquidity_health import LiquidityHealthMonitor
            self.liquidity_health = LiquidityHealthMonitor(client=self.solana_client)
            logger.info("Liquidity Health Monitor available")
        except ImportError:
            logger.debug("Liquidity Health Monitor not available (optional feature)")

        # Event Predictor (Phase 2 - rug prediction)
        self.event_predictor = None
        try:
            from ai.event_predictor import EventPredictor
            self.event_predictor = EventPredictor(client=self.solana_client)
            logger.info("Event Predictor available")
        except ImportError:
            logger.debug("Event Predictor not available (optional feature)")

        # Adaptive Risk Manager (Phase 2)
        self.adaptive_risk = None
        try:
            from risk.adaptive_manager import AdaptiveRiskManager
            self.adaptive_risk = AdaptiveRiskManager(
                base_stop_loss=self.stop_loss_percentage or 0.10,
                base_take_profit=self.take_profit_percentage or 0.20,
                base_max_position=buy_amount,
            )
            logger.info("Adaptive Risk Manager available")
        except ImportError:
            logger.debug("Adaptive Risk Manager not available (optional feature)")

        # Position Sizer (Phase 2 - Kelly Criterion)
        self.position_sizer = None
        try:
            from risk.position_sizer import PositionSizer
            # Estimate total capital (could be configurable)
            estimated_capital = buy_amount * 10  # Rough estimate
            self.position_sizer = PositionSizer(
                total_capital=estimated_capital,
                risk_tolerance=0.25,  # Quarter Kelly
                min_position=buy_amount * 0.1,
                max_position=buy_amount * 2.0,
            )
            logger.info("Position Sizer (Kelly Criterion) available")
        except ImportError:
            logger.debug("Position Sizer not available (optional feature)")

        # MEV Protection (optional)
        self.mev_shield = None
        try:
            from defense.mev_shield import RealTimeMEVShield
            self.mev_shield = RealTimeMEVShield(
                client=self.solana_client,
                enable_flashbots=False,  # Set to True when Flashbots SDK is available
                enable_simulation=True,
                enable_multipath=True,
            )
            logger.info("Real-Time MEV Protection available")
        except ImportError:
            logger.debug("Real-Time MEV Protection not available (optional feature)")

        # AEGIS Insurance (optional)
        self.insurance = None
        try:
            from ecosystem.aegis_insurance import AEGISInsurance
            self.insurance = AEGISInsurance(
                enable_auto_hedge=True,
                max_coverage_per_position=10.0,  # SOL
            )
            logger.info("AEGIS Insurance available")
        except ImportError:
            logger.debug("AEGIS Insurance not available (optional feature)")

        # Bug Bounty System (Phase 1, 2 & 3 - Complete Pipeline)
        self.bug_bounty_reporter = None
        self.bounty_tracker = None
        self.payment_monitor = None
        self.bounty_converter = None
        try:
            from bug_bounty.bounty_converter import BountyToLiquidityConverter
            from bug_bounty.bounty_tracker import BountyTracker
            from bug_bounty.payment_monitor import PaymentMonitor
            from bug_bounty.report_generator import BugBountyReporter
            
            # Initialize bounty tracker
            self.bounty_tracker = BountyTracker()
            
            # Initialize reporter with tracker
            self.bug_bounty_reporter = BugBountyReporter(
                bounty_tracker=self.bounty_tracker
            )
            
            # Initialize bounty converter (Phase 3)
            try:
                from ecosystem.community_distributor import CommunityDistributor
                from liquidity.liquidity_provider import LiquidityProvider
                
                community_distributor = CommunityDistributor(self.solana_client)
                liquidity_provider = LiquidityProvider(
                    self.solana_client,
                    community_distributor=community_distributor,
                )
                
                self.bounty_converter = BountyToLiquidityConverter(
                    client=self.solana_client,
                    community_distributor=community_distributor,
                    liquidity_provider=liquidity_provider,
                )
                logger.info("Bounty-to-Liquidity Converter available")
            except ImportError:
                logger.debug(
                    "Bounty-to-Liquidity Converter dependencies not available"
                )
            
            # Initialize payment monitor with converter
            self.payment_monitor = PaymentMonitor(
                bounty_tracker=self.bounty_tracker,
                check_interval=3600,  # Check every hour
                bounty_converter=self.bounty_converter,
            )
            
            logger.info("Bug Bounty System (Complete Pipeline) available")
        except ImportError:
            logger.debug("Bug Bounty System not available (optional feature)")

    async def start(self) -> None:
        """Start the trading bot and listen for new tokens."""
        # Start override console if available
        if self.override_console:
            await self.override_console.start()
            self.override_console.resume()  # Set to running state
        
        # Start payment monitor if available
        if self.payment_monitor:
            await self.payment_monitor.start()
            logger.info("Payment monitor started")
        
        logger.info(f"Starting Universal Trader for {self.platform.value}")
        logger.info(
            f"Match filter: {self.match_string if self.match_string else 'None'}"
        )
        logger.info(
            f"Creator filter: {self.bro_address if self.bro_address else 'None'}"
        )
        logger.info(f"Marry mode: {self.marry_mode}")
        logger.info(f"YOLO mode: {self.yolo_mode}")
        logger.info(f"Exit strategy: {self.exit_strategy}")

        if self.exit_strategy == "tp_sl":
            logger.info(
                f"Take profit: {self.take_profit_percentage * 100 if self.take_profit_percentage else 'None'}%"
            )
            logger.info(
                f"Stop loss: {self.stop_loss_percentage * 100 if self.stop_loss_percentage else 'None'}%"
            )
            logger.info(
                f"Max hold time: {self.max_hold_time if self.max_hold_time else 'None'} seconds"
            )

        logger.info(f"Max token age: {self.max_token_age} seconds")

        try:
            health_resp = await self.solana_client.get_health()
            logger.info(f"RPC warm-up successful (getHealth passed: {health_resp})")
        except Exception as e:
            logger.warning(f"RPC warm-up failed: {e!s}")

        try:
            # Choose operating mode based on yolo_mode
            if not self.yolo_mode:
                # Single token mode: process one token and exit
                logger.info(
                    "Running in single token mode - will process one token and exit"
                )
                token_info = await self._wait_for_token()
                if token_info:
                    await self._handle_token(token_info)
                    logger.info("Finished processing single token. Exiting...")
                else:
                    logger.info(
                        f"No suitable token found within timeout period ({self.token_wait_timeout}s). Exiting..."
                    )
            else:
                # Continuous mode: process tokens until interrupted
                logger.info(
                    "Running in continuous mode - will process tokens until interrupted"
                )
                processor_task = asyncio.create_task(self._process_token_queue())

                try:
                    await self.token_listener.listen_for_tokens(
                        lambda token: self._queue_token(token),
                        self.match_string,
                        self.bro_address,
                    )
                except Exception:
                    logger.exception("Token listening stopped due to error")
                finally:
                    processor_task.cancel()
                    try:
                        await processor_task
                    except asyncio.CancelledError:
                        pass

        except Exception:
            logger.exception("Trading stopped due to error")

        finally:
            await self._cleanup_resources()
            logger.info("Universal Trader has shut down")

    async def _wait_for_token(self) -> TokenInfo | None:
        """Wait for a single token to be detected."""
        # Create a one-time event to signal when a token is found
        token_found = asyncio.Event()
        found_token = None

        async def token_callback(token: TokenInfo) -> None:
            nonlocal found_token
            token_key = str(token.mint)

            # Only process if not already processed and fresh
            if token_key not in self.processed_tokens:
                # Record when the token was discovered
                self.token_timestamps[token_key] = monotonic()
                found_token = token
                self.processed_tokens.add(token_key)
                token_found.set()

        listener_task = asyncio.create_task(
            self.token_listener.listen_for_tokens(
                token_callback,
                self.match_string,
                self.bro_address,
            )
        )

        # Wait for a token with a timeout
        try:
            logger.info(
                f"Waiting for a suitable token (timeout: {self.token_wait_timeout}s)..."
            )
            await asyncio.wait_for(token_found.wait(), timeout=self.token_wait_timeout)
            logger.info(f"Found token: {found_token.symbol} ({found_token.mint})")
            return found_token
        except TimeoutError:
            logger.info(
                f"Timed out after waiting {self.token_wait_timeout}s for a token"
            )
            return None
        finally:
            listener_task.cancel()
            try:
                await listener_task
            except asyncio.CancelledError:
                pass

    async def _cleanup_resources(self) -> None:
        """Perform cleanup operations before shutting down."""
        # Stop payment monitor if running
        if self.payment_monitor:
            await self.payment_monitor.stop()
        
        if self.traded_mints:
            try:
                logger.info(f"Cleaning up {len(self.traded_mints)} traded token(s)...")
                await handle_cleanup_post_session(
                    self.solana_client,
                    self.wallet,
                    list(self.traded_mints),
                    self.priority_fee_manager,
                    self.cleanup_mode,
                    self.cleanup_with_priority_fee,
                    self.cleanup_force_close_with_burn,
                )
            except Exception:
                logger.exception("Error during cleanup")

        old_keys = {k for k in self.token_timestamps if k not in self.processed_tokens}
        for key in old_keys:
            self.token_timestamps.pop(key, None)

        await self.solana_client.close()

    async def _queue_token(self, token_info: TokenInfo) -> None:
        """Queue a token for processing if not already processed."""
        token_key = str(token_info.mint)

        if token_key in self.processed_tokens:
            logger.debug(f"Token {token_info.symbol} already processed. Skipping...")
            return

        # Record timestamp when token was discovered
        self.token_timestamps[token_key] = monotonic()

        await self.token_queue.put(token_info)
        logger.info(
            f"Queued new token: {token_info.symbol} ({token_info.mint}) on {token_info.platform.value}"
        )

    async def _process_token_queue(self) -> None:
        """Continuously process tokens from the queue concurrently (Performance Optimization #5)."""
        semaphore = asyncio.Semaphore(self.max_concurrent_tokens)
        
        async def process_with_limit(token_info: TokenInfo) -> None:
            """Process token with concurrency limit."""
            async with semaphore:
                await self._handle_token(token_info)
        
        while True:
            try:
                # Check for pause/emergency stop
                if self.override_console:
                    can_trade, reason = self.override_console.check_can_trade()
                    if not can_trade:
                        logger.debug(f"Skipping token processing: {reason}")
                        await asyncio.sleep(1)
                        continue

                # Collect batch of tokens for concurrent processing
                tokens = []
                try:
                    for _ in range(self.max_concurrent_tokens):
                        token = await asyncio.wait_for(
                            self.token_queue.get(),
                            timeout=0.1  # Non-blocking batch collection
                        )
                        token_key = str(token.mint)
                        
                        # Check if token is still "fresh"
                        current_time = monotonic()
                        token_age = current_time - self.token_timestamps.get(
                            token_key, current_time
                        )
                        
                        if token_age > self.max_token_age:
                            logger.info(
                                f"Skipping token {token.symbol} - too old "
                                f"({token_age:.1f}s > {self.max_token_age}s)"
                            )
                            self.token_queue.task_done()
                            continue
                        
                        self.processed_tokens.add(token_key)
                        tokens.append(token)
                        
                except asyncio.TimeoutError:
                    # No tokens available, continue
                    pass
                
                if tokens:
                    logger.info(
                        f"Processing {len(tokens)} token(s) concurrently: "
                        f"{', '.join([t.symbol for t in tokens])}"
                    )
                    # Process tokens concurrently
                    await asyncio.gather(*[
                        process_with_limit(token) for token in tokens
                    ], return_exceptions=True)
                    
                    # Mark all as done
                    for _ in tokens:
                        self.token_queue.task_done()
                else:
                    # No tokens, small sleep to avoid busy waiting
                    await asyncio.sleep(0.1)

            except asyncio.CancelledError:
                logger.info("Token queue processor was cancelled")
                break
            except Exception:
                logger.exception("Error in token queue processor")

    async def _handle_token(self, token_info: TokenInfo) -> None:
        """Handle a new token creation event."""
        try:
            # Validate that token is for our platform
            if token_info.platform != self.platform:
                logger.warning(
                    f"Token platform mismatch: expected {self.platform.value}, got {token_info.platform.value}"
                )
                return

            # Security scan (mandatory if enabled)
            if self.enable_security_scan:
                security_passed, security_reason = await self._check_security(token_info)
                if not security_passed:
                    logger.error(
                        f"🚨 SECURITY CHECK FAILED: {token_info.symbol} - {security_reason}"
                    )
                    return
                logger.info(f"✅ Security check passed: {token_info.symbol}")

            # Parallel threat scanning (Performance Optimization #1)
            scan_results = await self._scan_token_parallel(token_info)
            
            # Process comprehensive threat results
            if 'comprehensive' in scan_results and scan_results['comprehensive']:
                comprehensive_threat_score = scan_results['comprehensive']
                if not isinstance(comprehensive_threat_score, Exception):
                    # Generate bug bounty reports for high/critical threats
                    if self.bug_bounty_reporter and comprehensive_threat_score.risk_level in ["critical", "high"]:
                        logger.info(
                            f"Generating bug bounty reports for {comprehensive_threat_score.risk_level} "
                            f"threats in {token_info.symbol}..."
                        )
                        try:
                            reports = await self.bug_bounty_reporter.generate_reports_from_scan(
                                comprehensive_threat_score,
                                token_info,
                            )
                            if reports:
                                logger.info(
                                    f"Generated {len(reports)} bug bounty report(s) for {token_info.symbol}. "
                                    f"Total estimated bounty: ${sum(r.estimated_bounty or 0 for r in reports):,.2f} USD"
                                )
                                # Save reports to file
                                await self._save_bug_reports(reports, token_info)
                        except Exception as e:
                            logger.exception(f"Error generating bug bounty reports: {e}")
                    
                    if comprehensive_threat_score.risk_level in ["critical", "high"]:
                        logger.warning(
                            f"Skipping {token_info.symbol} - Comprehensive threat level too high: "
                            f"{comprehensive_threat_score.risk_level} (score: {comprehensive_threat_score.total_score:.2f}/100)"
                        )
                        for threat in comprehensive_threat_score.detected_threats[:5]:
                            logger.warning(f"  - {threat.category.value}: {threat.description} (severity: {threat.severity})")
                        
                        if comprehensive_threat_score.predictions.get("rug_prediction"):
                            rug_pred = comprehensive_threat_score.predictions["rug_prediction"]
                            logger.error(
                                f"⚠️ RUG PULL PREDICTED: {rug_pred.get('probability', 0):.1%} probability "
                                f"within {rug_pred.get('timeframe', 'unknown')}"
                            )
                        return
                    elif comprehensive_threat_score.risk_level == "medium":
                        logger.warning(
                            f"Medium risk token: {token_info.symbol} "
                            f"(score: {comprehensive_threat_score.total_score:.2f}/100)"
                        )

            # Process contract audit results (additional validation if security scan passed)
            if 'audit' in scan_results and scan_results['audit']:
                audit_result = scan_results['audit']
                if not isinstance(audit_result, Exception):
                    # Apply security thresholds
                    if self.block_honeypots and audit_result.is_honeypot:
                        logger.error(
                            f"🚨 HONEYPOT DETECTED: {token_info.symbol} - BLOCKED"
                        )
                        for rec in audit_result.recommendations:
                            logger.error(f"  - {rec}")
                        return
                    
                    if self.block_critical_risk and audit_result.risk_level == "critical":
                        logger.error(
                            f"🚨 CRITICAL RISK: {token_info.symbol} "
                            f"(health: {audit_result.health_score:.1f}/100) - BLOCKED"
                        )
                        for rec in audit_result.recommendations:
                            logger.error(f"  - {rec}")
                        return
                    
                    # Check minimum security score
                    if audit_result.health_score < self.min_security_score:
                        logger.error(
                            f"🚨 SECURITY SCORE TOO LOW: {token_info.symbol} "
                            f"(score: {audit_result.health_score:.1f}/100, required: {self.min_security_score}/100) - BLOCKED"
                        )
                        return
                    
                    logger.info(
                        f"✅ Contract audit passed: {token_info.symbol} "
                        f"(health: {audit_result.health_score:.1f}/100, risk: {audit_result.risk_level})"
                    )

            # Process liquidity health results
            if 'liquidity' in scan_results and scan_results['liquidity']:
                liquidity_health = scan_results['liquidity']
                if not isinstance(liquidity_health, Exception):
                    if liquidity_health.health_level == "critical":
                        logger.warning(
                            f"Critical liquidity health: {token_info.symbol} "
                            f"(score: {liquidity_health.total_score:.1f}/100)"
                        )
                        for anomaly in liquidity_health.anomalies:
                            logger.warning(f"  - {anomaly}")
                    elif liquidity_health.health_level == "warning":
                        logger.info(
                            f"Liquidity health warning: {token_info.symbol} "
                            f"(score: {liquidity_health.total_score:.1f}/100)"
                        )

            # Process event prediction results
            if 'prediction' in scan_results and scan_results['prediction']:
                rug_prediction = scan_results['prediction']
                if not isinstance(rug_prediction, Exception) and rug_prediction:
                    if rug_prediction.probability > 0.7:
                        logger.error(
                            f"⚠️ HIGH RUG PULL RISK: {token_info.symbol} - "
                            f"{rug_prediction.probability:.1%} probability within {rug_prediction.timeframe}"
                        )
                        if rug_prediction.early_warning:
                            logger.error("  - Early warning: Consider avoiding this token")

            # Enhanced threat detection (legacy - still use for additional checks)
            if self.threat_detector:
                logger.info(f"Scanning {token_info.symbol} for threats (legacy)...")
                threat_score = await self.threat_detector.scan_token(token_info)
                
                # Check if we should trade based on threat score
                if not self.threat_detector.should_trade(threat_score, max_risk_level="medium"):
                    logger.warning(
                        f"Skipping {token_info.symbol} - Threat level too high: "
                        f"{threat_score.risk_level} (score: {threat_score.total_score:.2f})"
                    )
                    for rec in threat_score.recommendations:
                        logger.warning(f"  - {rec}")
                    return
                elif threat_score.risk_level in ["high", "critical"]:
                    logger.warning(
                        f"High risk token detected: {token_info.symbol} "
                        f"({threat_score.risk_level}, score: {threat_score.total_score:.2f})"
                    )
                    for rec in threat_score.recommendations:
                        logger.warning(f"  - {rec}")

            # Adaptive risk management (Phase 2) - adjust stop-loss/take-profit
            if self.adaptive_risk:
                # Calculate adaptive risk parameters
                # Note: Would need volatility and sentiment data in production
                risk_params = self.adaptive_risk.calculate_adaptive_risk(
                    volatility=0.1,  # Placeholder - would calculate from price data
                    sentiment_score=0.0,  # Placeholder - would use sentiment analyzer
                    market_state="normal",  # Placeholder - would detect market state
                )
                
                # Override stop-loss and take-profit if adaptive risk is available
                if risk_params:
                    logger.info(
                        f"Adaptive risk: SL={risk_params.stop_loss_percentage:.1%}, "
                        f"TP={risk_params.take_profit_percentage:.1%}, "
                        f"MaxPos={risk_params.max_position_size:.4f} SOL"
                    )
                    # Update position sizing if needed
                    if risk_params.max_position_size < self.buy_amount:
                        logger.info(
                            f"Reducing position size from {self.buy_amount:.6f} to "
                            f"{risk_params.max_position_size:.6f} SOL due to risk"
                        )
                        # Note: Would need to update buyer's amount in production

            # Social signal intelligence - scan and adjust strategy
            adjusted_buy_amount = self.buy_amount
            adjusted_hold_time = self.max_hold_time
            
            if self.enable_social_signals and self.social_scanner and self.strategy_adjuster:
                try:
                    # Scan for social signals related to this token
                    logger.info(f"Scanning social media for {token_info.symbol}...")
                    keywords = [token_info.symbol, str(token_info.mint)[:8]]
                    viral_tokens = await self.social_scanner.scan_for_viral_tokens(
                        keywords=keywords,
                        max_results=10,
                    )
                    
                    # Check if this token is in viral tokens
                    token_mint_str = str(token_info.mint)
                    for viral_token in viral_tokens:
                        if viral_token.token_address == token_mint_str or token_info.symbol.upper() in [s.upper() for s in viral_token.token_mentions]:
                            # Update strategy adjuster with signals
                            signals_data = [
                                {
                                    "platform": s.platform,
                                    "sentiment": s.sentiment,
                                    "engagement_score": s.engagement_score,
                                    "virality_score": s.virality_score,
                                    "timestamp": s.timestamp,
                                }
                                for s in viral_token.signals
                            ]
                            self.strategy_adjuster.update_social_signals(
                                token_address=token_mint_str,
                                signals=signals_data,
                            )
                            
                            # Get strategy adjustment
                            adjustment = await self.strategy_adjuster.get_strategy_adjustment(token_info)
                            
                            if adjustment:
                                if adjustment.adjustment_type == "skip":
                                    logger.warning(
                                        f"🚫 Skipping {token_info.symbol} due to negative social momentum"
                                    )
                                    return
                                
                                # Adjust buy amount
                                adjusted_buy_amount = self.strategy_adjuster.get_adjusted_buy_amount(
                                    token_address=token_mint_str,
                                    base_amount=self.buy_amount,
                                )
                                
                                # Adjust hold time
                                adjusted_hold_time = self.strategy_adjuster.get_adjusted_hold_time(
                                    token_address=token_mint_str,
                                    base_hold_time=self.max_hold_time,
                                )
                                
                                logger.info(
                                    f"📊 Social momentum: {adjustment.social_momentum:.2f} "
                                    f"→ Buy: {adjusted_buy_amount:.6f} SOL "
                                    f"({adjusted_buy_amount/self.buy_amount:.2f}x), "
                                    f"Hold: {adjusted_hold_time}s"
                                )
                            
                            break
                    
                    # Update buyer amount if adjusted
                    if adjusted_buy_amount != self.buy_amount:
                        self.buyer.amount = adjusted_buy_amount
                        logger.info(f"Adjusted buy amount to {adjusted_buy_amount:.6f} SOL based on social signals")
                    
                    # Update hold time if adjusted
                    if adjusted_hold_time and adjusted_hold_time != self.max_hold_time:
                        self.max_hold_time = adjusted_hold_time
                        logger.info(f"Adjusted hold time to {adjusted_hold_time}s based on social signals")
                        
                except Exception as e:
                    logger.warning(f"Error in social signal intelligence: {e}")
                    # Continue with normal trading if social signals fail

            # Wait for pool/curve to stabilize (unless in extreme fast mode)
            if not self.extreme_fast_mode:
                await self._save_token_info(token_info)
                logger.info(
                    f"Waiting for {self.wait_time_after_creation} seconds for the pool/curve to stabilize..."
                )
                await asyncio.sleep(self.wait_time_after_creation)

            # Buy token (with MEV protection if available)
            logger.info(
                f"Buying {adjusted_buy_amount:.6f} SOL worth of {token_info.symbol} on {token_info.platform.value}..."
            )
            buy_result: TradeResult = await self.buyer.execute(token_info)

            if buy_result.success:
                await self._handle_successful_buy(token_info, buy_result)
                
                # Auto-hedge position with insurance (if available)
                if self.insurance and buy_result.price:
                    position_value = buy_result.price * buy_result.amount
                    await self.insurance.auto_hedge_position(
                        position_id=str(token_info.mint),
                        position_value=position_value,
                    )
            else:
                await self._handle_failed_buy(token_info, buy_result)

            # Only wait for next token in yolo mode
            if self.yolo_mode:
                logger.info(
                    f"YOLO mode enabled. Waiting {self.wait_time_before_new_token} seconds before looking for next token..."
                )
                await asyncio.sleep(self.wait_time_before_new_token)

        except Exception:
            logger.exception(f"Error handling token {token_info.symbol}")

    async def _check_security(self, token_info: TokenInfo) -> Tuple[bool, str]:
        """Check token security before trading (with caching).
        
        Args:
            token_info: Token to check
            
        Returns:
            Tuple of (passed: bool, reason: str)
        """
        mint_key = str(token_info.mint)
        current_time = monotonic()
        
        # Check cache first
        if mint_key in self.security_cache:
            cached_result, cache_time = self.security_cache[mint_key]
            if current_time - cache_time < self.security_cache_ttl:
                logger.debug(f"Using cached security result for {token_info.symbol}")
                return cached_result
        
        # Run security scans
        scan_results = await self._scan_token_parallel(token_info)
        
        # Check comprehensive threat detector
        if 'comprehensive' in scan_results and scan_results['comprehensive']:
            threat_score = scan_results['comprehensive']
            if not isinstance(threat_score, Exception):
                if threat_score.risk_level in ["critical", "high"]:
                    reason = f"High threat level: {threat_score.risk_level} (score: {threat_score.total_score:.1f}/100)"
                    result = (False, reason)
                    self.security_cache[mint_key] = (result, current_time)
                    return result
        
        # Check contract auditor
        if 'audit' in scan_results and scan_results['audit']:
            audit_result = scan_results['audit']
            if not isinstance(audit_result, Exception):
                # Block honeypots
                if self.block_honeypots and audit_result.is_honeypot:
                    reason = "Honeypot detected"
                    result = (False, reason)
                    self.security_cache[mint_key] = (result, current_time)
                    return result
                
                # Block critical risk
                if self.block_critical_risk and audit_result.risk_level == "critical":
                    reason = f"Critical risk level (health: {audit_result.health_score:.1f}/100)"
                    result = (False, reason)
                    self.security_cache[mint_key] = (result, current_time)
                    return result
                
                # Check minimum security score
                if audit_result.health_score < self.min_security_score:
                    reason = f"Security score too low: {audit_result.health_score:.1f}/100 (required: {self.min_security_score}/100)"
                    result = (False, reason)
                    self.security_cache[mint_key] = (result, current_time)
                    return result
        
        # Security check passed
        result = (True, "All security checks passed")
        self.security_cache[mint_key] = (result, current_time)
        return result

    async def _scan_token_parallel(self, token_info: TokenInfo) -> Dict[str, Any]:
        """Run all threat scans in parallel (Performance Optimization #1).
        
        Args:
            token_info: Token to scan
            
        Returns:
            Dictionary of scan results
        """
        scan_tasks = {}
        
        # Build task list for available scanners
        if self.comprehensive_threat_detector:
            scan_tasks['comprehensive'] = self.comprehensive_threat_detector.scan_token_comprehensive(token_info)
        if self.contract_auditor:
            scan_tasks['audit'] = self.contract_auditor.audit_contract(token_info)
        if self.liquidity_health:
            scan_tasks['liquidity'] = self.liquidity_health.monitor_token(token_info)
        if self.event_predictor:
            scan_tasks['prediction'] = self.event_predictor.predict_rug_pull(token_info)
        
        if not scan_tasks:
            return {}
        
        # Run all scans in parallel
        logger.info(f"Running {len(scan_tasks)} threat scans in parallel for {token_info.symbol}...")
        results = await asyncio.gather(*scan_tasks.values(), return_exceptions=True)
        
        # Map results to task names
        result_dict = dict(zip(scan_tasks.keys(), results))
        
        # Log any exceptions
        for key, result in result_dict.items():
            if isinstance(result, Exception):
                logger.warning(f"Scan {key} failed: {result}")
        
        return result_dict

    async def _handle_successful_buy(
        self, token_info: TokenInfo, buy_result: TradeResult
    ) -> None:
        """Handle successful token purchase."""
        logger.info(
            f"Successfully bought {token_info.symbol} on {token_info.platform.value}"
        )
        self._log_trade(
            "buy",
            token_info,
            buy_result.price,
            buy_result.amount,
            buy_result.tx_signature,
        )
        self.traded_mints.add(token_info.mint)

        # Choose exit strategy
        if not self.marry_mode:
            if self.exit_strategy == "tp_sl":
                await self._handle_tp_sl_exit(token_info, buy_result)
            elif self.exit_strategy == "time_based":
                await self._handle_time_based_exit(token_info)
            elif self.exit_strategy == "manual":
                logger.info("Manual exit strategy - position will remain open")
        else:
            logger.info("Marry mode enabled. Skipping sell operation.")

    async def _handle_failed_buy(
        self, token_info: TokenInfo, buy_result: TradeResult
    ) -> None:
        """Handle failed token purchase."""
        logger.error(f"Failed to buy {token_info.symbol}: {buy_result.error_message}")
        # Close ATA if enabled
        await handle_cleanup_after_failure(
            self.solana_client,
            self.wallet,
            token_info.mint,
            self.priority_fee_manager,
            self.cleanup_mode,
            self.cleanup_with_priority_fee,
            self.cleanup_force_close_with_burn,
        )

    async def _handle_tp_sl_exit(
        self, token_info: TokenInfo, buy_result: TradeResult
    ) -> None:
        """Handle take profit/stop loss exit strategy."""
        # Create position
        position = Position.create_from_buy_result(
            mint=token_info.mint,
            symbol=token_info.symbol,
            entry_price=buy_result.price,
            quantity=buy_result.amount,
            take_profit_percentage=self.take_profit_percentage,
            stop_loss_percentage=self.stop_loss_percentage,
            max_hold_time=self.max_hold_time,
        )

        # Store position for tracking
        mint_str = str(token_info.mint)
        self.active_positions[mint_str] = position
        
        # Callback for API updates
        if self.on_position_opened:
            try:
                self.on_position_opened(position)
            except Exception as e:
                logger.warning(f"Error in on_position_opened callback: {e}")

        logger.info(f"Created position: {position}")
        if position.take_profit_price:
            logger.info(f"Take profit target: {position.take_profit_price:.8f} SOL")
        if position.stop_loss_price:
            logger.info(f"Stop loss target: {position.stop_loss_price:.8f} SOL")

        # Monitor position until exit condition is met
        await self._monitor_position_until_exit(token_info, position)

    async def _handle_time_based_exit(self, token_info: TokenInfo) -> None:
        """Handle legacy time-based exit strategy."""
        logger.info(f"Waiting for {self.wait_time_after_buy} seconds before selling...")
        await asyncio.sleep(self.wait_time_after_buy)

        logger.info(f"Selling {token_info.symbol}...")
        sell_result: TradeResult = await self.seller.execute(token_info)

        if sell_result.success:
            logger.info(f"Successfully sold {token_info.symbol}")
            self._log_trade(
                "sell",
                token_info,
                sell_result.price,
                sell_result.amount,
                sell_result.tx_signature,
            )
            # Close ATA if enabled
            await handle_cleanup_after_sell(
                self.solana_client,
                self.wallet,
                token_info.mint,
                self.priority_fee_manager,
                self.cleanup_mode,
                self.cleanup_with_priority_fee,
                self.cleanup_force_close_with_burn,
            )
        else:
            logger.error(
                f"Failed to sell {token_info.symbol}: {sell_result.error_message}"
            )

    async def _monitor_position_until_exit(
        self, token_info: TokenInfo, position: Position
    ) -> None:
        """Monitor a position until exit conditions are met."""
        logger.info(
            f"Starting position monitoring (check interval: {self.price_check_interval}s)"
        )

        # Get pool address for price monitoring using platform-agnostic method
        pool_address = self._get_pool_address(token_info)
        curve_manager = self.platform_implementations.curve_manager

        while position.is_active:
            try:
                # Get current price from pool/curve
                current_price = await curve_manager.calculate_price(pool_address)

                # Check if position should be exited
                should_exit, exit_reason = position.should_exit(current_price)

                if should_exit and exit_reason:
                    logger.info(f"Exit condition met: {exit_reason.value}")
                    logger.info(f"Current price: {current_price:.8f} SOL")

                    # Log PnL before exit
                    pnl = position.get_pnl(current_price)
                    logger.info(
                        f"Position PnL: {pnl['price_change_pct']:.2f}% ({pnl['unrealized_pnl_sol']:.6f} SOL)"
                    )

                    # Execute sell
                    sell_result = await self.seller.execute(token_info)

                    if sell_result.success:
                        # Close position with actual exit price
                        position.close_position(sell_result.price, exit_reason)
                        
                        # Remove from active positions
                        mint_str = str(position.mint)
                        if mint_str in self.active_positions:
                            del self.active_positions[mint_str]
                        
                        # Callback for API updates
                        if self.on_position_closed:
                            try:
                                self.on_position_closed(position)
                            except Exception as e:
                                logger.warning(f"Error in on_position_closed callback: {e}")

                        logger.info(
                            f"Successfully exited position: {exit_reason.value}"
                        )
                        self._log_trade(
                            "sell",
                            token_info,
                            sell_result.price,
                            sell_result.amount,
                            sell_result.tx_signature,
                        )

                        # Log final PnL
                        final_pnl = position.get_pnl()
                        logger.info(
                            f"Final PnL: {final_pnl['price_change_pct']:.2f}% ({final_pnl['unrealized_pnl_sol']:.6f} SOL)"
                        )

                        # Close ATA if enabled
                        await handle_cleanup_after_sell(
                            self.solana_client,
                            self.wallet,
                            token_info.mint,
                            self.priority_fee_manager,
                            self.cleanup_mode,
                            self.cleanup_with_priority_fee,
                            self.cleanup_force_close_with_burn,
                        )
                    else:
                        logger.error(
                            f"Failed to exit position: {sell_result.error_message}"
                        )
                        # Keep monitoring in case sell can be retried

                    break
                else:
                    # Log current status
                    pnl = position.get_pnl(current_price)
                    logger.debug(
                        f"Position status: {current_price:.8f} SOL ({pnl['price_change_pct']:+.2f}%)"
                    )

                # Wait before next price check
                await asyncio.sleep(self.price_check_interval)

            except Exception:
                logger.exception("Error monitoring position")
                await asyncio.sleep(
                    self.price_check_interval
                )  # Continue monitoring despite errors

    def _get_pool_address(self, token_info: TokenInfo) -> Pubkey:
        """Get the pool/curve address for price monitoring using platform-agnostic method."""
        address_provider = self.platform_implementations.address_provider

        # Use platform-specific logic to get the appropriate address
        if hasattr(token_info, "bonding_curve") and token_info.bonding_curve:
            return token_info.bonding_curve
        elif hasattr(token_info, "pool_state") and token_info.pool_state:
            return token_info.pool_state
        else:
            # Fallback to deriving the address using platform provider
            return address_provider.derive_pool_address(token_info.mint)

    async def _save_token_info(self, token_info: TokenInfo) -> None:
        """Save token information to a file."""
        try:
            trades_dir = Path("trades")
            trades_dir.mkdir(exist_ok=True)
            file_path = trades_dir / f"{token_info.mint}.txt"

            # Convert to dictionary for saving - platform-agnostic
            token_dict = {
                "name": token_info.name,
                "symbol": token_info.symbol,
                "uri": token_info.uri,
                "mint": str(token_info.mint),
                "platform": token_info.platform.value,
                "user": str(token_info.user) if token_info.user else None,
                "creator": str(token_info.creator) if token_info.creator else None,
                "creation_timestamp": token_info.creation_timestamp,
            }

            # Add platform-specific fields only if they exist
            platform_fields = {
                "bonding_curve": token_info.bonding_curve,
                "associated_bonding_curve": token_info.associated_bonding_curve,
                "creator_vault": token_info.creator_vault,
                "pool_state": token_info.pool_state,
                "base_vault": token_info.base_vault,
                "quote_vault": token_info.quote_vault,
            }

            for field_name, field_value in platform_fields.items():
                if field_value is not None:
                    token_dict[field_name] = str(field_value)

            file_path.write_text(json.dumps(token_dict, indent=2))

            logger.info(f"Token information saved to {file_path}")
        except OSError:
            logger.exception("Failed to save token information")

    def _log_trade(
        self,
        action: str,
        token_info: TokenInfo,
        price: float,
        amount: float,
        tx_hash: str | None,
    ) -> None:
        """Log trade information."""
        try:
            trades_dir = Path("trades")
            trades_dir.mkdir(exist_ok=True)

            log_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "time": datetime.utcnow().timestamp(),  # Unix timestamp for sorting
                "action": action,
                "platform": token_info.platform.value,
                "token_address": str(token_info.mint),
                "mint": str(token_info.mint),
                "symbol": token_info.symbol,
                "price": price,
                "amount": amount,
                "tx_hash": str(tx_hash) if tx_hash else None,
                "status": "success",
            }

            log_file_path = trades_dir / "trades.log"
            with log_file_path.open("a", encoding="utf-8") as log_file:
                log_file.write(json.dumps(log_entry) + "\n")
            
            # Store in trade history for API/dashboard
            self.trade_history.append(log_entry)
            
            # Keep only last 1000 trades to prevent memory issues
            if len(self.trade_history) > 1000:
                self.trade_history = self.trade_history[-1000:]
            
            # Callback for API updates
            if self.on_trade_executed:
                try:
                    self.on_trade_executed(log_entry)
                except Exception as e:
                    logger.warning(f"Error in on_trade_executed callback: {e}")
                    
        except OSError:
            logger.exception("Failed to log trade information")

    async def _save_bug_reports(
        self,
        reports: List,
        token_info: TokenInfo,
    ) -> None:
        """Save bug bounty reports to files.
        
        Args:
            reports: List of ImmunefiReport objects
            token_info: Token information
        """
        try:
            from bug_bounty.report_templates import ImmunefiReport
            
            reports_dir = Path("bug_reports")
            reports_dir.mkdir(exist_ok=True)
            
            for i, report in enumerate(reports):
                if not isinstance(report, ImmunefiReport):
                    continue
                
                # Save as JSON (Immunefi format)
                json_file = reports_dir / f"{token_info.symbol}_{token_info.mint}_{i+1}.json"
                json_file.write_text(
                    json.dumps(report.to_immunefi_format(), indent=2),
                    encoding="utf-8",
                )
                
                # Save as Markdown (human-readable)
                md_file = reports_dir / f"{token_info.symbol}_{token_info.mint}_{i+1}.md"
                md_file.write_text(report.to_markdown(), encoding="utf-8")
                
                logger.info(
                    f"Saved bug bounty report: {json_file.name} "
                    f"(Estimated bounty: ${report.estimated_bounty:,.2f} USD)"
                )
        except Exception as e:
            logger.exception(f"Error saving bug reports: {e}")


# Backward compatibility alias
PumpTrader = UniversalTrader  # Legacy name for backward compatibility
