"""
API Security Module
Handles authentication, rate limiting, and security middleware.
"""

import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable, Any
from functools import wraps

try:
    from fastapi import HTTPException, Request, status
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import Response
    import hashlib
    import hmac
    
    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False


class RateLimiter:
    """Rate limiting implementation using token bucket algorithm."""
    
    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        burst_size: int = 10,
    ):
        """Initialize rate limiter.
        
        Args:
            requests_per_minute: Max requests per minute
            requests_per_hour: Max requests per hour
            burst_size: Max burst requests allowed
        """
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_size = burst_size
        
        # Track requests: {identifier: [(timestamp, endpoint), ...]}
        self.request_history: Dict[str, list] = defaultdict(list)
        self.burst_tokens: Dict[str, int] = defaultdict(lambda: burst_size)
        self.last_refill: Dict[str, float] = defaultdict(time.time)
    
    def _refill_tokens(self, identifier: str):
        """Refill burst tokens over time."""
        now = time.time()
        last_refill = self.last_refill[identifier]
        elapsed = now - last_refill
        
        # Refill 1 token per second
        if elapsed >= 1.0:
            tokens_to_add = int(elapsed)
            self.burst_tokens[identifier] = min(
                self.burst_size,
                self.burst_tokens[identifier] + tokens_to_add
            )
            self.last_refill[identifier] = now
    
    def _cleanup_old_requests(self, identifier: str):
        """Remove old request records."""
        now = time.time()
        cutoff = now - 3600  # Keep last hour
        
        self.request_history[identifier] = [
            (ts, endpoint) for ts, endpoint in self.request_history[identifier]
            if ts > cutoff
        ]
    
    def is_allowed(
        self,
        identifier: str,
        endpoint: str = "default",
    ) -> tuple[bool, Optional[str]]:
        """Check if request is allowed.
        
        Args:
            identifier: Unique identifier (IP, session_id, etc.)
            endpoint: Endpoint being accessed
            
        Returns:
            Tuple of (allowed: bool, error_message: Optional[str])
        """
        now = time.time()
        
        # Refill burst tokens
        self._refill_tokens(identifier)
        
        # Check burst limit
        if self.burst_tokens[identifier] <= 0:
            return False, "Rate limit exceeded (burst). Please wait a moment."
        
        # Cleanup old requests
        self._cleanup_old_requests(identifier)
        
        # Count requests in last minute
        minute_cutoff = now - 60
        minute_requests = [
            ts for ts, ep in self.request_history[identifier]
            if ts > minute_cutoff
        ]
        
        if len(minute_requests) >= self.requests_per_minute:
            return False, f"Rate limit exceeded. Max {self.requests_per_minute} requests per minute."
        
        # Count requests in last hour
        hour_cutoff = now - 3600
        hour_requests = [
            ts for ts, ep in self.request_history[identifier]
            if ts > hour_cutoff
        ]
        
        if len(hour_requests) >= self.requests_per_hour:
            return False, f"Rate limit exceeded. Max {self.requests_per_hour} requests per hour."
        
        # Record request
        self.request_history[identifier].append((now, endpoint))
        self.burst_tokens[identifier] -= 1
        
        return True, None


class APIKeyAuth:
    """API Key authentication handler."""
    
    def __init__(self, valid_api_keys: Optional[list[str]] = None):
        """Initialize API key authentication.
        
        Args:
            valid_api_keys: List of valid API keys (or None to disable)
        """
        self.valid_api_keys = set(valid_api_keys) if valid_api_keys else None
        self.security = HTTPBearer(auto_error=False)
    
    def verify_api_key(self, api_key: Optional[str]) -> bool:
        """Verify API key.
        
        Args:
            api_key: API key to verify
            
        Returns:
            True if valid, False otherwise
        """
        if self.valid_api_keys is None:
            return True  # API key auth disabled
        
        if not api_key:
            return False
        
        return api_key in self.valid_api_keys
    
    async def get_api_key(self, request: Request) -> Optional[str]:
        """Extract API key from request.
        
        Checks:
        1. Authorization header: Bearer <key>
        2. X-API-Key header
        3. api_key query parameter
        
        Args:
            request: FastAPI request
            
        Returns:
            API key if found, None otherwise
        """
        # Check Authorization header
        credentials: Optional[HTTPAuthorizationCredentials] = await self.security(request)
        if credentials:
            return credentials.credentials
        
        # Check X-API-Key header
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return api_key
        
        # Check query parameter
        api_key = request.query_params.get("api_key")
        if api_key:
            return api_key
        
        return None


class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware for API."""
    
    def __init__(
        self,
        app,
        rate_limiter: Optional[RateLimiter] = None,
        api_key_auth: Optional[APIKeyAuth] = None,
        require_auth: bool = False,
    ):
        """Initialize security middleware.
        
        Args:
            app: FastAPI app
            rate_limiter: Rate limiter instance
            api_key_auth: API key authenticator
            require_auth: Whether to require authentication for all endpoints
        """
        super().__init__(app)
        self.rate_limiter = rate_limiter
        self.api_key_auth = api_key_auth
        self.require_auth = require_auth
    
    def _get_client_identifier(self, request: Request) -> str:
        """Get client identifier for rate limiting.
        
        Args:
            request: FastAPI request
            
        Returns:
            Client identifier (IP address or session ID)
        """
        # Try to get session ID from headers
        session_id = request.headers.get("X-Session-ID")
        if session_id:
            return f"session:{session_id}"
        
        # Fallback to IP address
        client_ip = request.client.host if request.client else "unknown"
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take first IP if multiple
            client_ip = forwarded_for.split(",")[0].strip()
        
        return f"ip:{client_ip}"
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through security middleware."""
        # Skip security for docs and health endpoints
        path = request.url.path
        if path in ["/docs", "/redoc", "/openapi.json", "/health", "/"]:
            return await call_next(request)
        
        # Get client identifier
        identifier = self._get_client_identifier(request)
        
        # Rate limiting
        if self.rate_limiter:
            endpoint = path
            allowed, error_msg = self.rate_limiter.is_allowed(identifier, endpoint)
            if not allowed:
                return Response(
                    content=f'{{"error": "{error_msg}"}}',
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    media_type="application/json",
                    headers={
                        "Retry-After": "60",
                        "X-RateLimit-Limit": str(self.rate_limiter.requests_per_minute),
                    },
                )
        
        # API Key authentication (if enabled)
        if self.require_auth and self.api_key_auth:
            api_key = await self.api_key_auth.get_api_key(request)
            if not self.api_key_auth.verify_api_key(api_key):
                return Response(
                    content='{"error": "Authentication required. Provide API key in Authorization header, X-API-Key header, or api_key query parameter."}',
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    media_type="application/json",
                )
        
        # Add security headers
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # CORS headers (if not already set)
        if "Access-Control-Allow-Origin" not in response.headers:
            # Will be set by CORS middleware, but add fallback
            pass
        
        return response


class SessionManager:
    """Enhanced session management with expiration and validation."""
    
    def __init__(
        self,
        session_timeout: int = 3600,  # 1 hour
        max_sessions_per_ip: int = 5,
    ):
        """Initialize session manager.
        
        Args:
            session_timeout: Session timeout in seconds
            max_sessions_per_ip: Max sessions per IP address
        """
        self.session_timeout = session_timeout
        self.max_sessions_per_ip = max_sessions_per_ip
        
        # {session_id: {"wallet": Wallet, "created_at": timestamp, "last_access": timestamp, "ip": str}}
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.ip_sessions: Dict[str, list[str]] = defaultdict(list)
    
    def create_session(
        self,
        wallet: Any,
        ip_address: str,
        session_id: Optional[str] = None,
    ) -> str:
        """Create a new session.
        
        Args:
            wallet: Wallet instance
            ip_address: Client IP address
            session_id: Optional custom session ID
            
        Returns:
            Session ID
        """
        # Cleanup old sessions for this IP
        self._cleanup_ip_sessions(ip_address)
        
        # Check max sessions per IP
        if len(self.ip_sessions[ip_address]) >= self.max_sessions_per_ip:
            # Remove oldest session
            oldest_session = self.ip_sessions[ip_address][0]
            self.delete_session(oldest_session)
        
        # Generate session ID if not provided
        if not session_id:
            import uuid
            session_id = str(uuid.uuid4())
        
        now = time.time()
        self.sessions[session_id] = {
            "wallet": wallet,
            "created_at": now,
            "last_access": now,
            "ip_address": ip_address,
        }
        
        self.ip_sessions[ip_address].append(session_id)
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session data if valid, None otherwise
        """
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        now = time.time()
        
        # Check timeout
        if now - session["last_access"] > self.session_timeout:
            self.delete_session(session_id)
            return None
        
        # Update last access
        session["last_access"] = now
        
        return session
    
    def delete_session(self, session_id: str):
        """Delete a session.
        
        Args:
            session_id: Session ID to delete
        """
        if session_id in self.sessions:
            ip_address = self.sessions[session_id]["ip_address"]
            if session_id in self.ip_sessions[ip_address]:
                self.ip_sessions[ip_address].remove(session_id)
            del self.sessions[session_id]
    
    def _cleanup_ip_sessions(self, ip_address: str):
        """Cleanup expired sessions for an IP.
        
        Args:
            ip_address: IP address
        """
        now = time.time()
        sessions_to_remove = []
        
        for session_id in self.ip_sessions[ip_address]:
            if session_id in self.sessions:
                session = self.sessions[session_id]
                if now - session["last_access"] > self.session_timeout:
                    sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            self.delete_session(session_id)
    
    def cleanup_expired_sessions(self):
        """Cleanup all expired sessions."""
        now = time.time()
        sessions_to_remove = []
        
        for session_id, session in self.sessions.items():
            if now - session["last_access"] > self.session_timeout:
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            self.delete_session(session_id)
    
    def get_active_sessions_count(self) -> int:
        """Get count of active sessions."""
        return len(self.sessions)


def require_session(func: Callable) -> Callable:
    """Decorator to require valid session for endpoint.
    
    Usage:
        @app.post("/api/endpoint")
        @require_session
        async def my_endpoint(request: Request, session_id: str):
            ...
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Extract session_id from kwargs or request
        session_id = kwargs.get("session_id")
        if not session_id:
            # Try to get from request
            for arg in args:
                if hasattr(arg, "query_params"):
                    session_id = arg.query_params.get("session_id")
                    break
        
        if not session_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session ID required"
            )
        
        # Session validation will be done in the endpoint
        return await func(*args, **kwargs)
    
    return wrapper

