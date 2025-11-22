"""
FastAPI server for bot web integration.

This module provides a REST API and WebSocket server to integrate
the trading bot with web applications.
"""
import asyncio
import time
import uuid
from typing import Dict, Any, List, Optional
from pathlib import Path

try:
    from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Request, status
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    from pydantic import BaseModel, Field
    from utils.logger import get_logger
    
    # Import bot components
    import sys
    if str(Path(__file__).parent.parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from config_loader import load_bot_config
    from trading.universal_trader import UniversalTrader
    from interfaces.core import Platform
    from auth.wallet_connector import WalletConnector
    from auth.token_verifier import TokenVerifier
    from auth.signature_verifier import SignatureVerifier
    from core.client import SolanaClient
    from core.wallet import Wallet
    from solders.pubkey import Pubkey
    from web.security import (
        RateLimiter,
        APIKeyAuth,
        SecurityMiddleware,
        SessionManager,
    )
    
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    logger = None

if FASTAPI_AVAILABLE:
    logger = get_logger(__name__)

    # Initialize FastAPI app
    app = FastAPI(
        title="Trading Bot API",
        description="REST API for pump.fun/letsbonk.fun trading bot",
        version="1.0.0"
    )
    
    # Authentication state
    import os
    from dotenv import load_dotenv
    
    # Load environment
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    
    # Strategy metadata/state
    strategy_definitions: list[dict[str, Any]] = [
        {
            "slug": "snipe",
            "name": "Snipe",
            "description": "Fast entry on new token launches",
            "config": {"min_liquidity": 1.0, "max_slippage": 30},
        },
        {
            "slug": "volume-boost",
            "name": "Volume Boost",
            "description": "Enter tokens with high volume",
            "config": {"min_volume": 10.0, "volume_window": 300},
        },
        {
            "slug": "market-making",
            "name": "Market Making",
            "description": "Provide liquidity with spread",
            "config": {"spread": 2.0, "target_ratio": 0.5},
        },
        {
            "slug": "momentum",
            "name": "Momentum",
            "description": "Follow price momentum trends",
            "config": {"momentum_threshold": 1.05, "lookback": 60},
        },
        {
            "slug": "reversal",
            "name": "Reversal",
            "description": "Buy on dips, sell on peaks",
            "config": {"dip_threshold": 0.95, "peak_threshold": 1.10},
        },
        {
            "slug": "whale-copy",
            "name": "Whale Copy",
            "description": "Copy trades from large wallets",
            "config": {"min_wallet_balance": 100.0, "follow_delay": 5},
        },
    ]
    strategy_state: dict[str, bool] = {item["slug"]: False for item in strategy_definitions}
    bot_strategy_state: dict[str, set[str]] = {}
    strategy_lookup = {item["slug"]: item for item in strategy_definitions}

    # Initialize authentication
    access_token_mint = os.getenv("ACCESS_TOKEN_MINT")
    min_token_balance = int(os.getenv("MIN_TOKEN_BALANCE", "1"))
    rpc_endpoint = os.getenv("SOLANA_NODE_RPC_ENDPOINT")
    
    # Initialize auth client lazily (don't create async tasks during import)
    # Will be created when first needed in request handlers
    _auth_client: Optional[SolanaClient] = None
    _wallet_connector: Optional[WalletConnector] = None
    _auth_client_config = {
        "rpc_endpoint": rpc_endpoint,
        "access_token_mint": access_token_mint,
        "min_token_balance": min_token_balance,
    }
    
    def get_auth_client() -> Optional[SolanaClient]:
        """Get or create auth client (lazy initialization)."""
        global _auth_client
        if _auth_client is None and _auth_client_config["rpc_endpoint"]:
            _auth_client = SolanaClient(rpc_endpoint=_auth_client_config["rpc_endpoint"])
        return _auth_client
    
    def get_wallet_connector() -> Optional[WalletConnector]:
        """Get or create wallet connector (lazy initialization)."""
        global _wallet_connector
        if _wallet_connector is None:
            client = get_auth_client()
            if client and _auth_client_config["access_token_mint"]:
                _wallet_connector = WalletConnector(
                    client=client,
                    access_token_mint=_auth_client_config["access_token_mint"],
                    min_token_balance=_auth_client_config["min_token_balance"],
                )
        return _wallet_connector
    
    # Initialize security components
    # Rate limiting configuration
    rate_limiter = RateLimiter(
        requests_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")),
        requests_per_hour=int(os.getenv("RATE_LIMIT_PER_HOUR", "1000")),
        burst_size=int(os.getenv("RATE_LIMIT_BURST", "10")),
    )
    
    # API Key authentication (optional)
    api_keys = os.getenv("API_KEYS", "").split(",") if os.getenv("API_KEYS") else None
    api_key_auth = APIKeyAuth(valid_api_keys=[k.strip() for k in api_keys] if api_keys else None)
    
    # Session management
    session_manager = SessionManager(
        session_timeout=int(os.getenv("SESSION_TIMEOUT", "3600")),  # 1 hour default
        max_sessions_per_ip=int(os.getenv("MAX_SESSIONS_PER_IP", "5")),
    )
    
    # Store authenticated wallets (legacy - will migrate to session_manager)
    authenticated_wallets: Dict[str, Wallet] = {}

    # Enable CORS for web integration
    allowed_origins = os.getenv("ALLOWED_ORIGINS", "*")
    if allowed_origins != "*":
        allowed_origins = [origin.strip() for origin in allowed_origins.split(",")]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
        max_age=3600,
    )
    
    # Add security middleware (rate limiting, API key auth)
    require_api_key = os.getenv("REQUIRE_API_KEY", "false").lower() == "true"
    app.add_middleware(
        SecurityMiddleware,
        rate_limiter=rate_limiter,
        api_key_auth=api_key_auth,
        require_auth=require_api_key,
    )

    # Store active bot instances
    active_bots: Dict[str, UniversalTrader] = {}
    bot_status: Dict[str, Dict[str, Any]] = {}
    websocket_connections: Dict[str, List[WebSocket]] = {}
    
    # Store active MEV, Market Making, and Arbitrage instances
    active_mev: Dict[str, Any] = {}  # {mev_id: {"monitor": MempoolMonitor, "attacker": SandwichAttacker, "front_runner": FrontRunner}}
    active_market_makers: Dict[str, Any] = {}  # {mm_id: MarketMaker}
    active_arbitrage: Dict[str, Any] = {}  # {arb_id: ArbitrageEngine}


    # Request/Response Models
    class BotConfig(BaseModel):
        """Bot configuration model."""
        rpc_endpoint: str
        wss_endpoint: str
        private_key: Optional[str] = None  # Optional - can use session wallet instead
        session_id: Optional[str] = None  # Session ID for wallet connection
        platform: str = "pump_fun"
        buy_amount: float = 0.01
        buy_slippage: float = 0.3
        sell_slippage: float = 0.3
        exit_strategy: str = "time_based"
        listener_type: str = "logs"
        extreme_fast_mode: bool = False
        take_profit_percentage: Optional[float] = None
        stop_loss_percentage: Optional[float] = None
        max_hold_time: Optional[int] = None
        strategies: Optional[List[str]] = None


    class BotResponse(BaseModel):
        """Bot operation response model."""
        bot_id: str
        status: str
        message: str


    class BotStatus(BaseModel):
        """Bot status model."""
        bot_id: str
        running: bool
        platform: str
        positions: Dict[str, Any]
        trade_history: List[Dict[str, Any]]
        wallet_balance: float
        error: Optional[str] = None
        strategies: List[str] = Field(default_factory=list)

    class StrategyToggleRequest(BaseModel):
        """Payload for enabling/disabling strategies."""

        strategy_slug: str
        enabled: bool
        bot_id: Optional[str] = None


    class MEVConfig(BaseModel):
        """MEV configuration model."""
        rpc_endpoint: str
        private_key: str
        min_profit_threshold: float = 0.01
        min_transaction_size: float = 0.1
        enable_sandwich: bool = False
        enable_front_run: bool = False
        sandwich_max_slippage: float = 0.05
        use_jito_bundler: bool = True
        frontrun_priority_multiplier: float = 1.5


    class MarketMakingConfig(BaseModel):
        """Market making configuration model."""
        rpc_endpoint: str
        private_key: str
        token_mint: str
        platform: str = "pump_fun"
        target_sol_ratio: float = 0.5
        spread_percentage: float = 0.02
        max_trade_size_sol: float = 0.1
        rebalance_interval_seconds: int = 60


    class ArbitrageConfig(BaseModel):
        """Arbitrage configuration model."""
        rpc_endpoint: str
        private_key: str
        token_mint: Optional[str] = None
        min_profit_percentage: float = 0.02
        min_profit_sol: float = 0.01
        max_trade_size_sol: float = 0.5
        max_concurrent_trades: int = 3


    class ConnectionManager:
        """Manages WebSocket connections."""
        
        def __init__(self):
            self.active_connections: Dict[str, List[WebSocket]] = {}
        
        async def connect(self, websocket: WebSocket, bot_id: str):
            """Connect a WebSocket for a bot."""
            await websocket.accept()
            if bot_id not in self.active_connections:
                self.active_connections[bot_id] = []
            self.active_connections[bot_id].append(websocket)
            logger.info(f"WebSocket connected for bot {bot_id}")
        
        def disconnect(self, websocket: WebSocket, bot_id: str):
            """Disconnect a WebSocket."""
            if bot_id in self.active_connections:
                if websocket in self.active_connections[bot_id]:
                    self.active_connections[bot_id].remove(websocket)
                if not self.active_connections[bot_id]:
                    del self.active_connections[bot_id]
            logger.info(f"WebSocket disconnected for bot {bot_id}")
        
        async def broadcast(self, bot_id: str, message: dict):
            """Broadcast message to all connections for a bot."""
            if bot_id in self.active_connections:
                disconnected = []
                for connection in self.active_connections[bot_id]:
                    try:
                        await connection.send_json(message)
                    except Exception as e:
                        logger.warning(f"Failed to send to WebSocket: {e}")
                        disconnected.append(connection)
                
                # Remove disconnected connections
                for conn in disconnected:
                    self.disconnect(conn, bot_id)

    manager = ConnectionManager()


    # Authentication models
    class WalletConnectRequest(BaseModel):
        wallet_address: str
        signature: List[int]  # Signature as array of bytes
        message: List[int]  # Original message as array of bytes
    
    class WalletConnectResponse(BaseModel):
        success: bool
        session_id: Optional[str] = None
        message: str
        wallet_address: Optional[str] = None
    
    def get_wallet_from_session(session_id: Optional[str]) -> Optional[Wallet]:
        """Get wallet from session ID."""
        if not session_id:
            return None
        return authenticated_wallets.get(session_id)
    
    @app.post("/auth/connect", response_model=WalletConnectResponse)
    async def connect_wallet(request: WalletConnectRequest, http_request: Request):
        """Connect wallet via signature verification and verify token access."""
        try:
            # Log the incoming request for debugging
            logger.info(f"Wallet connection request from: {request.wallet_address}")
            logger.info(f"Message length: {len(request.message)}, Signature length: {len(request.signature)}")
            
            # Verify signature
            signature_verifier = SignatureVerifier()
            is_valid, error_msg = signature_verifier.verify_signature(
                wallet_address=request.wallet_address,
                message=request.message,
                signature=request.signature,
            )
            
            if not is_valid:
                logger.error(f"❌ Signature verification failed: {error_msg}")
                logger.error(f"Wallet: {request.wallet_address}")
                logger.error(f"Message bytes: {request.message[:50]}... (showing first 50)")
                logger.error(f"Signature bytes: {request.signature[:20]}... (showing first 20)")
                return WalletConnectResponse(
                    success=False,
                    message=f"Signature verification failed: {error_msg}"
                )
            
            # Create wallet object from public key (for token verification)
            pubkey = Pubkey.from_string(request.wallet_address)
            # Create a minimal wallet object for token verification
            # Note: We can't create a full Wallet without private key, but we can verify token balance
            wallet_address_str = str(pubkey)
            
            # Verify token access if enabled
            connector = get_wallet_connector()
            if connector and connector.verifier:
                # Verify token balance using the public key directly
                has_access, access_message = await connector.verifier.verify_pubkey_access(pubkey)
                if not has_access:
                    logger.warning(f"Token access denied for {wallet_address_str}: {access_message}")
                    return WalletConnectResponse(
                        success=False,
                        message=access_message,
                    )
            
            # Get client IP
            client_ip = http_request.client.host if http_request.client else "unknown"
            forwarded_for = http_request.headers.get("X-Forwarded-For")
            if forwarded_for:
                client_ip = forwarded_for.split(",")[0].strip()
            
            # Create a session with wallet address (we don't have private key, so store pubkey)
            # We'll create a minimal wallet-like object for session storage
            class WalletProxy:
                """Proxy object to store wallet address without private key."""
                def __init__(self, pubkey_str: str):
                    self.pubkey_str = pubkey_str
                
                @property
                def pubkey(self):
                    return Pubkey.from_string(self.pubkey_str)
            
            wallet_proxy = WalletProxy(wallet_address_str)
            session_id = session_manager.create_session(wallet_proxy, client_ip)
            
            # Store in legacy dict
            authenticated_wallets[session_id] = wallet_proxy
            
            logger.info(f"Wallet connected via signature: {wallet_address_str} (session: {session_id[:8]}...)")
            
            return WalletConnectResponse(
                success=True,
                session_id=session_id,
                message="Wallet connected and verified",
                wallet_address=wallet_address_str,
            )
            
        except Exception as e:
            logger.error(f"Wallet connection error: {e}")
            import traceback
            traceback.print_exc()
            return WalletConnectResponse(
                success=False,
                message=f"Connection failed: {str(e)}"
            )
    
    @app.post("/auth/verify/{session_id}")
    async def verify_session(session_id: str):
        """Verify if a session is still valid."""
        # Check session manager first
        session_data = session_manager.get_session(session_id)
        
        if not session_data:
            # Fallback to legacy dict
            if session_id not in authenticated_wallets:
                raise HTTPException(status_code=401, detail="Invalid or expired session")
            wallet = authenticated_wallets[session_id]
        else:
            wallet = session_data["wallet"]
        
        # Verify token access if enabled
        connector = get_wallet_connector()
        if connector:
            has_access, message = await connector.verify_access(wallet)
            if not has_access:
                # Remove invalid session
                session_manager.delete_session(session_id)
                if session_id in authenticated_wallets:
                    del authenticated_wallets[session_id]
                raise HTTPException(status_code=403, detail=message)
        
        return {
            "valid": True,
            "wallet_address": str(wallet.pubkey),
            "session_age": int(time.time() - session_data["created_at"]) if session_data else None,
        }
    
    # Serve dashboard static files
    import os
    web_dir = Path(__file__).parent.parent.parent / "web"
    if web_dir.exists():
        app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")
        
        @app.get("/dashboard")
        async def serve_dashboard():
            """Serve the main dashboard page."""
            dashboard_path = web_dir / "dashboard.html"
            if dashboard_path.exists():
                return FileResponse(str(dashboard_path))
            raise HTTPException(status_code=404, detail="Dashboard not found")
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        # Cleanup expired sessions
        session_manager.cleanup_expired_sessions()
        
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "active_sessions": session_manager.get_active_sessions_count(),
            "rate_limiter_enabled": rate_limiter is not None,
            "api_key_auth_enabled": api_key_auth is not None and api_key_auth.valid_api_keys is not None,
        }
    
    @app.get("/")
    async def root():
        """API root endpoint - redirects to dashboard."""
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/dashboard")
    
    @app.get("/api")
    async def api_info():
        """API information endpoint."""
        return {
            "message": "Trading Bot API",
            "version": "1.0.0",
            "endpoints": {
                "start_bot": "/api/bot/start",
                "stop_bot": "/api/bot/stop/{bot_id}",
                "bot_status": "/api/bot/status/{bot_id}",
                "list_bots": "/api/bot/list",
                "mev_start": "/api/mev/start",
                "mev_stop": "/api/mev/stop/{mev_id}",
                "mev_opportunities": "/api/mev/opportunities/{mev_id}",
                "market_making_start": "/api/market_making/start",
                "market_making_stop": "/api/market_making/stop/{mm_id}",
                "market_making_stats": "/api/market_making/stats/{mm_id}",
                "arbitrage_start": "/api/arbitrage/start",
                "arbitrage_stop": "/api/arbitrage/stop/{arb_id}",
                "arbitrage_opportunities": "/api/arbitrage/opportunities/{arb_id}",
                "arbitrage_stats": "/api/arbitrage/stats/{arb_id}",
                "auth_connect": "/auth/connect",
                "auth_verify": "/auth/verify/{session_id}",
                "health": "/health",
                "websocket": "/ws/{bot_id}",
                "docs": "/docs",
                "dashboard": "/dashboard",
                "config": "/api/config",
                "wallet_balance": "/api/wallet/balance"
            }
        }
    
    @app.get("/api/config")
    async def get_config():
        """Get current configuration (RPC/WSS endpoints from environment)."""
        return {
            "rpc_endpoint": os.getenv("SOLANA_NODE_RPC_ENDPOINT", ""),
            "wss_endpoint": os.getenv("SOLANA_NODE_WSS_ENDPOINT", ""),
        }
    
    @app.get("/api/wallet/balance")
    async def get_wallet_balance(session_id: Optional[str] = None):
        """Get wallet balance for the connected wallet."""
        # Get wallet from session
        wallet = get_wallet_from_session(session_id)
        
        if not wallet:
            raise HTTPException(
                status_code=401,
                detail="No wallet connected. Please connect your wallet first."
            )
        
        try:
            # Get pubkey - handle both Wallet objects and WalletProxy objects
            if hasattr(wallet, 'pubkey'):
                pubkey = wallet.pubkey
            elif hasattr(wallet, 'pubkey_str'):
                pubkey = Pubkey.from_string(wallet.pubkey_str)
            else:
                raise HTTPException(
                    status_code=500,
                    detail="Invalid wallet object"
                )
            
            # Get balance using SolanaClient
            rpc_endpoint = os.getenv("SOLANA_NODE_RPC_ENDPOINT")
            if not rpc_endpoint:
                raise HTTPException(
                    status_code=500,
                    detail="RPC endpoint not configured. Set SOLANA_NODE_RPC_ENDPOINT in .env"
                )
            
            client = SolanaClient(rpc_endpoint=rpc_endpoint)
            balance = await client.get_balance(pubkey)
            balance_sol = balance / 1_000_000_000  # Convert lamports to SOL
            
            return {
                "balance": balance_sol,
                "balance_lamports": balance,
                "wallet_address": str(pubkey)
            }
        except Exception as e:
            logger.error(f"Error getting wallet balance: {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get wallet balance: {str(e)}"
            )


    @app.get("/api/strategies")
    async def get_strategies_state():
        """Return available strategies and their current enablement state."""
        return {
            "strategies": strategy_definitions,
            "global_enabled": [slug for slug, enabled in strategy_state.items() if enabled],
            "bot_strategies": {bot: list(strats) for bot, strats in bot_strategy_state.items()},
        }

    @app.post("/api/strategies/toggle")
    async def toggle_strategy(request: StrategyToggleRequest):
        """Enable or disable a strategy globally or for a specific bot."""
        slug = request.strategy_slug
        if slug not in strategy_lookup:
            raise HTTPException(status_code=404, detail=f"Unknown strategy: {slug}")

        if request.bot_id:
            if request.bot_id not in active_bots:
                raise HTTPException(status_code=404, detail="Bot not found")
            target_set = bot_strategy_state.setdefault(request.bot_id, set())
            if request.enabled:
                target_set.add(slug)
            else:
                target_set.discard(slug)

            bot_status[request.bot_id]["strategies"] = list(target_set)
            trader = active_bots[request.bot_id]
            if hasattr(trader, "set_enabled_strategies"):
                trader.set_enabled_strategies(list(target_set))
        else:
            strategy_state[slug] = request.enabled

        return {
            "strategies": strategy_definitions,
            "global_enabled": [key for key, enabled in strategy_state.items() if enabled],
            "bot_strategies": {bot: list(strats) for bot, strats in bot_strategy_state.items()},
        }


    @app.post("/api/bot/start", response_model=BotResponse)
    async def start_bot(config: BotConfig, background_tasks: BackgroundTasks, request: Request):
        """Start a new bot instance."""
        bot_id = str(uuid.uuid4())
        
        try:
            # Get private key - either from config or from session
            private_key = config.private_key
            
            # If no private key provided, try to get from session
            if not private_key:
                session_id = config.session_id
                if not session_id:
                    # Try to get from request cookies/headers
                    session_id = request.cookies.get("session_id") or request.headers.get("X-Session-ID")
                
                if session_id:
                    wallet = get_wallet_from_session(session_id)
                    if wallet:
                        # Get private key from wallet object
                        # Note: This only works if the wallet was created with a private key
                        # Web3 wallets don't export private keys, so this will only work
                        # if the user manually entered a private key during wallet creation
                        private_key = wallet.private_key if hasattr(wallet, 'private_key') else None
            
            # Validate that we have a private key
            if not private_key:
                raise HTTPException(
                    status_code=400,
                    detail="Private key is required for automated trading. Please enter your private key in the 'Automated Mode' section, or use a wallet that supports private key export."
                )
            
            # Validate platform
            try:
                platform = Platform(config.platform)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid platform: {config.platform}. Must be 'pump_fun' or 'lets_bonk'"
                )
            
            initial_strategies = config.strategies or [
                slug for slug, enabled in strategy_state.items() if enabled
            ]

            # Create trader instance
            trader = UniversalTrader(
                rpc_endpoint=config.rpc_endpoint,
                wss_endpoint=config.wss_endpoint,
                private_key=private_key,
                platform=platform,
                buy_amount=config.buy_amount,
                buy_slippage=config.buy_slippage,
                sell_slippage=config.sell_slippage,
                exit_strategy=config.exit_strategy,
                listener_type=config.listener_type,
                extreme_fast_mode=config.extreme_fast_mode,
                take_profit_percentage=config.take_profit_percentage,
                stop_loss_percentage=config.stop_loss_percentage,
                max_hold_time=config.max_hold_time,
                enabled_strategies=initial_strategies,
            )
            
            # Store bot instance
            active_bots[bot_id] = trader
            bot_status[bot_id] = {
                "bot_id": bot_id,
                "running": True,
                "platform": config.platform,
                "positions": {},
                "trade_history": [],
                "wallet_balance": 0.0,
                "error": None,
                "strategies": list(initial_strategies),
            }
            bot_strategy_state[bot_id] = set(initial_strategies)
            
            # Start bot in background
            background_tasks.add_task(run_bot, bot_id, trader)
            
            logger.info(f"Bot {bot_id} started successfully")
            
            return BotResponse(
                bot_id=bot_id,
                status="started",
                message=f"Bot {bot_id} started successfully"
            )
        except Exception as e:
            logger.exception(f"Failed to start bot: {e}")
            raise HTTPException(status_code=400, detail=str(e))


    @app.post("/api/bot/stop/{bot_id}", response_model=BotResponse)
    async def stop_bot(bot_id: str):
        """Stop a running bot instance."""
        if bot_id not in active_bots:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        try:
            trader = active_bots[bot_id]
            # Stop the trader (you may need to implement a stop method)
            # For now, just mark as stopped
            bot_status[bot_id]["running"] = False
            del active_bots[bot_id]
            bot_strategy_state.pop(bot_id, None)
            
            logger.info(f"Bot {bot_id} stopped")
            
            return BotResponse(
                bot_id=bot_id,
                status="stopped",
                message=f"Bot {bot_id} stopped successfully"
            )
        except Exception as e:
            logger.exception(f"Failed to stop bot: {e}")
            raise HTTPException(status_code=400, detail=str(e))


    @app.get("/api/bot/status/{bot_id}", response_model=BotStatus)
    async def get_bot_status(bot_id: str):
        """Get status of a bot instance."""
        if bot_id not in bot_status:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        return BotStatus(**bot_status[bot_id])


    @app.get("/api/bot/list")
    async def list_bots():
        """List all active bot instances."""
        return {
            "bots": [
                {
                    "bot_id": bot_id,
                    "status": status
                }
                for bot_id, status in bot_status.items()
            ],
            "count": len(bot_status)
        }


    @app.websocket("/ws/{bot_id}")
    async def websocket_endpoint(websocket: WebSocket, bot_id: str):
        """WebSocket endpoint for real-time bot updates."""
        await manager.connect(websocket, bot_id)
        try:
            while True:
                # Send bot status updates
                if bot_id in bot_status:
                    await manager.broadcast(bot_id, bot_status[bot_id])
                await asyncio.sleep(1)  # Update every second
        except WebSocketDisconnect:
            manager.disconnect(websocket, bot_id)
        except Exception as e:
            logger.exception(f"WebSocket error: {e}")
            manager.disconnect(websocket, bot_id)


    async def run_bot(bot_id: str, trader: UniversalTrader):
        """Run bot in background task with position/trade tracking."""
        
        def update_positions():
            """Update bot_status with current positions."""
            if bot_id not in bot_status:
                return
            
            positions_dict = {}
            for mint, position in trader.active_positions.items():
                # Get current price - will be updated by price monitor
                # For now, use entry_price as placeholder (will be updated periodically)
                current_price = position.entry_price  # Will be updated by periodic task
                
                try:
                    pnl_data = position.get_pnl(current_price)
                    pnl = pnl_data["unrealized_pnl_sol"]
                    pnl_percent = pnl_data["price_change_pct"] / 100
                except (ValueError, KeyError):
                    pnl = 0
                    pnl_percent = 0
                
                positions_dict[mint] = {
                    "symbol": position.symbol,
                    "mint": mint,
                    "entry_price": position.entry_price,
                    "quantity": position.quantity,
                    "current_price": current_price,
                    "entry_time": position.entry_time.isoformat() if hasattr(position.entry_time, 'isoformat') else str(position.entry_time),
                    "pnl": pnl,
                    "pnl_percent": pnl_percent,
                    "status": "active" if position.is_active else "closed",
                    "take_profit_price": position.take_profit_price,
                    "stop_loss_price": position.stop_loss_price,
                }
            
            bot_status[bot_id]["positions"] = positions_dict
            bot_status[bot_id]["last_update"] = time.time()
            
            # Broadcast via WebSocket (non-blocking)
            try:
                asyncio.create_task(manager.broadcast(bot_id, {
                    "type": "positions_update",
                    "positions": positions_dict
                }))
            except Exception as e:
                logger.debug(f"Failed to broadcast positions update: {e}")
        
        def update_trades():
            """Update bot_status with trade history."""
            if bot_id not in bot_status:
                return
            
            bot_status[bot_id]["trade_history"] = trader.trade_history.copy()
            bot_status[bot_id]["last_update"] = time.time()
            
            # Broadcast via WebSocket (non-blocking)
            try:
                asyncio.create_task(manager.broadcast(bot_id, {
                    "type": "trades_update",
                    "trades": trader.trade_history[-10:] if trader.trade_history else []  # Last 10 trades
                }))
            except Exception as e:
                logger.debug(f"Failed to broadcast trades update: {e}")
        
        async def update_position_prices():
            """Periodically update current prices for active positions."""
            while bot_id in active_bots and bot_status.get(bot_id, {}).get("running", False):
                try:
                    if bot_id not in bot_status:
                        break
                    
                    # Update prices for active positions
                    for mint, position in trader.active_positions.items():
                        if not position.is_active:
                            continue
                        
                        try:
                            # Get pool address for price monitoring
                            from interfaces.core import TokenInfo
                            # We need token_info to get pool address, but we only have mint
                            # For now, skip price updates in this task - they'll be updated
                            # by the position monitoring loop in UniversalTrader
                            pass
                        except Exception as e:
                            logger.debug(f"Failed to update price for {mint}: {e}")
                    
                    await asyncio.sleep(10)  # Update prices every 10 seconds
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.warning(f"Error in position price update: {e}")
                    await asyncio.sleep(10)
        
        async def periodic_update():
            """Periodic status update task."""
            while bot_id in active_bots and bot_status.get(bot_id, {}).get("running", False):
                try:
                    if bot_id not in bot_status:
                        break
                    
                    # Update positions and trades
                    update_positions()
                    update_trades()
                    
                    # Update wallet balance
                    try:
                        balance = await trader.solana_client.get_balance(trader.wallet.pubkey)
                        bot_status[bot_id]["wallet_balance"] = balance / 1_000_000_000  # Convert lamports to SOL
                    except Exception as e:
                        logger.debug(f"Failed to update balance: {e}")
                    
                    await asyncio.sleep(5)  # Update every 5 seconds
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.warning(f"Error in periodic update: {e}")
                    await asyncio.sleep(5)
        
        # Set up callbacks
        trader.on_position_opened = lambda pos: update_positions()
        trader.on_position_closed = lambda pos: update_positions()
        trader.on_trade_executed = lambda trade: update_trades()
        
        # Start periodic updates
        update_task = None
        price_update_task = None
        
        try:
            # Start periodic update task
            update_task = asyncio.create_task(periodic_update())
            price_update_task = asyncio.create_task(update_position_prices())
            
            # Start the trader
            await trader.start()
        except Exception as e:
            logger.exception(f"Bot {bot_id} error: {e}")
            if bot_id in bot_status:
                bot_status[bot_id]["running"] = False
                bot_status[bot_id]["error"] = str(e)
                # Notify WebSocket connections
                try:
                    await manager.broadcast(bot_id, {
                        "type": "error",
                        "error": str(e)
                    })
                except Exception as broadcast_error:
                    logger.debug(f"Failed to broadcast error: {broadcast_error}")
        finally:
            # Cancel update tasks
            if update_task:
                update_task.cancel()
                try:
                    await update_task
                except asyncio.CancelledError:
                    pass
            
            if price_update_task:
                price_update_task.cancel()
                try:
                    await price_update_task
                except asyncio.CancelledError:
                    pass


    # ==================== MEV Endpoints ====================
    
    @app.post("/api/mev/start")
    async def start_mev(config: MEVConfig, background_tasks: BackgroundTasks):
        """Start MEV monitoring and execution."""
        mev_id = str(uuid.uuid4())
        
        try:
            from core.client import SolanaClient
            from core.wallet import Wallet
            from mev.mempool_monitor import MempoolMonitor
            from mev.sandwich_attacker import SandwichAttacker
            from mev.front_runner import FrontRunner
            
            client = SolanaClient(config.rpc_endpoint)
            wallet = Wallet(config.private_key)
            
            # Initialize mempool monitor
            monitor = MempoolMonitor(
                client=client,
                min_profit_threshold=config.min_profit_threshold,
                min_transaction_size=config.min_transaction_size,
            )
            
            mev_data = {
                "mev_id": mev_id,
                "monitor": monitor,
                "attacker": None,
                "front_runner": None,
                "running": True,
            }
            
            # Initialize sandwich attacker if enabled
            if config.enable_sandwich:
                attacker = SandwichAttacker(
                    client=client,
                    wallet=wallet,
                    use_jito_bundler=config.use_jito_bundler,
                    min_profit_threshold=config.min_profit_threshold,
                    max_slippage=config.sandwich_max_slippage,
                )
                mev_data["attacker"] = attacker
                monitor.add_opportunity_callback(
                    lambda opp: asyncio.create_task(attacker.execute_sandwich(opp))
                    if opp.opportunity_type == "sandwich" else None
                )
            
            # Initialize front runner if enabled
            if config.enable_front_run:
                front_runner = FrontRunner(
                    client=client,
                    wallet=wallet,
                    min_profit_threshold=config.min_profit_threshold,
                    priority_fee_multiplier=config.frontrun_priority_multiplier,
                )
                mev_data["front_runner"] = front_runner
                monitor.add_opportunity_callback(
                    lambda opp: asyncio.create_task(front_runner.execute_front_run(opp))
                    if opp.opportunity_type == "front_run" else None
                )
            
            active_mev[mev_id] = mev_data
            
            # Start monitoring in background
            background_tasks.add_task(run_mev, mev_id, monitor)
            
            logger.info(f"MEV {mev_id} started successfully")
            
            return {
                "mev_id": mev_id,
                "status": "started",
                "message": f"MEV {mev_id} started successfully"
            }
        except Exception as e:
            logger.exception(f"Failed to start MEV: {e}")
            raise HTTPException(status_code=400, detail=str(e))
    
    
    @app.post("/api/mev/stop/{mev_id}")
    async def stop_mev(mev_id: str):
        """Stop MEV monitoring."""
        if mev_id not in active_mev:
            raise HTTPException(status_code=404, detail="MEV instance not found")
        
        try:
            mev_data = active_mev[mev_id]
            mev_data["running"] = False
            if mev_data["monitor"]:
                await mev_data["monitor"].stop_monitoring()
            del active_mev[mev_id]
            
            logger.info(f"MEV {mev_id} stopped")
            
            return {
                "mev_id": mev_id,
                "status": "stopped",
                "message": f"MEV {mev_id} stopped successfully"
            }
        except Exception as e:
            logger.exception(f"Failed to stop MEV: {e}")
            raise HTTPException(status_code=400, detail=str(e))
    
    
    @app.get("/api/mev/opportunities/{mev_id}")
    async def get_mev_opportunities(mev_id: str):
        """Get detected MEV opportunities."""
        if mev_id not in active_mev:
            raise HTTPException(status_code=404, detail="MEV instance not found")
        
        mev_data = active_mev[mev_id]
        monitor = mev_data["monitor"]
        
        return {
            "mev_id": mev_id,
            "opportunities": [
                {
                    "type": opp.opportunity_type,
                    "estimated_profit": opp.estimated_profit,
                    "confidence": opp.confidence,
                    "risk_score": opp.risk_score,
                }
                for opp in monitor.detected_opportunities
            ],
            "count": len(monitor.detected_opportunities)
        }
    
    
    @app.get("/api/mev/stats/{mev_id}")
    async def get_mev_stats(mev_id: str):
        """Get MEV statistics."""
        if mev_id not in active_mev:
            raise HTTPException(status_code=404, detail="MEV instance not found")
        
        mev_data = active_mev[mev_id]
        stats = {}
        
        if mev_data["attacker"]:
            stats["sandwich"] = mev_data["attacker"].get_stats()
        
        if mev_data["front_runner"]:
            stats["front_run"] = mev_data["front_runner"].get_stats()
        
        return {
            "mev_id": mev_id,
            "running": mev_data["running"],
            "stats": stats
        }
    
    
    async def run_mev(mev_id: str, monitor: Any):
        """Run MEV monitoring in background."""
        try:
            await monitor.start_monitoring()
        except Exception as e:
            logger.exception(f"MEV {mev_id} error: {e}")
            if mev_id in active_mev:
                active_mev[mev_id]["running"] = False


    # ==================== Market Making Endpoints ====================
    
    @app.post("/api/market_making/start")
    async def start_market_making(config: MarketMakingConfig, background_tasks: BackgroundTasks):
        """Start market making."""
        mm_id = str(uuid.uuid4())
        
        try:
            from core.client import SolanaClient
            from core.wallet import Wallet
            from market_making.market_maker import MarketMaker, MarketMakingConfig as MMConfig
            from interfaces.core import Platform
            from solders.pubkey import Pubkey
            
            client = SolanaClient(config.rpc_endpoint)
            wallet = Wallet(config.private_key)
            token_mint = Pubkey.from_string(config.token_mint)
            platform = Platform(config.platform)
            
            mm_config = MMConfig(
                token_mint=token_mint,
                platform=platform,
                target_sol_ratio=config.target_sol_ratio,
                spread_percentage=config.spread_percentage,
                max_trade_size_sol=config.max_trade_size_sol,
                rebalance_interval_seconds=config.rebalance_interval_seconds,
            )
            
            market_maker = MarketMaker(client, wallet, mm_config)
            active_market_makers[mm_id] = market_maker
            
            # Start in background
            background_tasks.add_task(run_market_making, mm_id, market_maker)
            
            logger.info(f"Market making {mm_id} started successfully")
            
            return {
                "mm_id": mm_id,
                "status": "started",
                "message": f"Market making {mm_id} started successfully"
            }
        except Exception as e:
            logger.exception(f"Failed to start market making: {e}")
            raise HTTPException(status_code=400, detail=str(e))
    
    
    @app.post("/api/market_making/stop/{mm_id}")
    async def stop_market_making(mm_id: str):
        """Stop market making."""
        if mm_id not in active_market_makers:
            raise HTTPException(status_code=404, detail="Market making instance not found")
        
        try:
            market_maker = active_market_makers[mm_id]
            await market_maker.stop()
            del active_market_makers[mm_id]
            
            logger.info(f"Market making {mm_id} stopped")
            
            return {
                "mm_id": mm_id,
                "status": "stopped",
                "message": f"Market making {mm_id} stopped successfully"
            }
        except Exception as e:
            logger.exception(f"Failed to stop market making: {e}")
            raise HTTPException(status_code=400, detail=str(e))
    
    
    @app.get("/api/market_making/stats/{mm_id}")
    async def get_market_making_stats(mm_id: str):
        """Get market making statistics."""
        if mm_id not in active_market_makers:
            raise HTTPException(status_code=404, detail="Market making instance not found")
        
        market_maker = active_market_makers[mm_id]
        stats = market_maker.get_stats()
        
        return {
            "mm_id": mm_id,
            "is_active": market_maker.is_active,
            "stats": stats
        }
    
    
    async def run_market_making(mm_id: str, market_maker: Any):
        """Run market making in background."""
        try:
            await market_maker.start()
        except Exception as e:
            logger.exception(f"Market making {mm_id} error: {e}")


    # ==================== Arbitrage Endpoints ====================
    
    @app.post("/api/arbitrage/start")
    async def start_arbitrage(config: ArbitrageConfig, background_tasks: BackgroundTasks):
        """Start arbitrage engine."""
        arb_id = str(uuid.uuid4())
        
        try:
            from core.client import SolanaClient
            from core.wallet import Wallet
            from arbitrage.arbitrage_engine import ArbitrageEngine, ArbitrageConfig as ArbConfig
            from interfaces.core import Platform
            from solders.pubkey import Pubkey
            
            client = SolanaClient(config.rpc_endpoint)
            wallet = Wallet(config.private_key)
            
            arb_config = ArbConfig(
                token_mint=Pubkey.from_string(config.token_mint) if config.token_mint else None,
                platforms=[Platform.PUMP_FUN, Platform.LETS_BONK],
                min_profit_percentage=config.min_profit_percentage,
                min_profit_sol=config.min_profit_sol,
                max_trade_size_sol=config.max_trade_size_sol,
                max_concurrent_trades=config.max_concurrent_trades,
            )
            
            arbitrage_engine = ArbitrageEngine(client, wallet, arb_config)
            active_arbitrage[arb_id] = arbitrage_engine
            
            # Start in background
            background_tasks.add_task(run_arbitrage, arb_id, arbitrage_engine)
            
            logger.info(f"Arbitrage {arb_id} started successfully")
            
            return {
                "arb_id": arb_id,
                "status": "started",
                "message": f"Arbitrage {arb_id} started successfully"
            }
        except Exception as e:
            logger.exception(f"Failed to start arbitrage: {e}")
            raise HTTPException(status_code=400, detail=str(e))
    
    
    @app.post("/api/arbitrage/stop/{arb_id}")
    async def stop_arbitrage(arb_id: str):
        """Stop arbitrage engine."""
        if arb_id not in active_arbitrage:
            raise HTTPException(status_code=404, detail="Arbitrage instance not found")
        
        try:
            arbitrage_engine = active_arbitrage[arb_id]
            await arbitrage_engine.stop()
            del active_arbitrage[arb_id]
            
            logger.info(f"Arbitrage {arb_id} stopped")
            
            return {
                "arb_id": arb_id,
                "status": "stopped",
                "message": f"Arbitrage {arb_id} stopped successfully"
            }
        except Exception as e:
            logger.exception(f"Failed to stop arbitrage: {e}")
            raise HTTPException(status_code=400, detail=str(e))
    
    
    @app.get("/api/arbitrage/opportunities/{arb_id}")
    async def get_arbitrage_opportunities(arb_id: str):
        """Get detected arbitrage opportunities."""
        if arb_id not in active_arbitrage:
            raise HTTPException(status_code=404, detail="Arbitrage instance not found")
        
        arbitrage_engine = active_arbitrage[arb_id]
        price_monitor = arbitrage_engine.price_monitor
        
        # Get opportunities from price monitor
        opportunities = []
        for token_mint in price_monitor.monitored_tokens:
            price_diff = price_monitor.find_price_difference(token_mint, 0.01)
            if price_diff:
                buy_platform, sell_platform, profit_percentage = price_diff
                opportunities.append({
                    "token_mint": str(token_mint),
                    "buy_platform": buy_platform.value,
                    "sell_platform": sell_platform.value,
                    "profit_percentage": profit_percentage,
                })
        
        return {
            "arb_id": arb_id,
            "opportunities": opportunities,
            "count": len(opportunities)
        }
    
    
    @app.get("/api/arbitrage/stats/{arb_id}")
    async def get_arbitrage_stats(arb_id: str):
        """Get arbitrage statistics."""
        if arb_id not in active_arbitrage:
            raise HTTPException(status_code=404, detail="Arbitrage instance not found")
        
        arbitrage_engine = active_arbitrage[arb_id]
        stats = arbitrage_engine.get_stats()
        
        return {
            "arb_id": arb_id,
            "is_active": arbitrage_engine.is_active,
            "stats": stats
        }
    
    
    async def run_arbitrage(arb_id: str, arbitrage_engine: Any):
        """Run arbitrage in background."""
        try:
            await arbitrage_engine.start()
        except Exception as e:
            logger.exception(f"Arbitrage {arb_id} error: {e}")


    if __name__ == "__main__":
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
else:
    # Fallback if FastAPI not available
    app = None
    logger = None

