# RPC Failover System - Integration Guide

## Overview

The RPC Failover System provides automatic failover, health monitoring, and load balancing across multiple Solana RPC providers.

## Quick Start

### 1. Update Configuration

Add multiple RPC providers to your config:

```yaml
# bots/your-bot.yaml
rpc_endpoints:
  - "https://api.mainnet-beta.solana.com"  # Public fallback
  - "https://mainnet.helius-rpc.com/?api-key=YOUR_KEY"  # Helius
  - "https://your-quicknode-endpoint.solana-mainnet.quiknode.pro/YOUR_KEY"  # QuickNode
  - "https://your-triton-endpoint"  # Triton

# Optional: Failover settings
rpc_failover:
  health_check_interval: 30.0  # seconds
  max_consecutive_failures: 3
  min_success_rate: 0.8
  max_latency_ms: 2000.0
```

### 2. Update Code to Use Failover Manager

**Before (single RPC):**
```python
from core.client import SolanaClient

client = SolanaClient(rpc_endpoint)
```

**After (multi-provider failover):**
```python
from infrastructure.rpc_failover import RPCFailoverManager

# Initialize with multiple providers
failover_manager = RPCFailoverManager(
    providers=[
        "https://api.mainnet-beta.solana.com",
        "https://mainnet.helius-rpc.com/?api-key=YOUR_KEY",
        "https://your-quicknode-endpoint.solana-mainnet.quiknode.pro/YOUR_KEY",
    ]
)

# Start health monitoring
await failover_manager.start()

# Use like normal client
client = await failover_manager.get_client()
blockhash = await failover_manager.get_latest_blockhash()
```

### 3. Integration with Existing SolanaClient

**Option A: Replace SolanaClient entirely**

Modify `src/core/client.py` to use `RPCFailoverManager` internally:

```python
from infrastructure.rpc_failover import RPCFailoverManager

class SolanaClient:
    def __init__(self, rpc_endpoints: list[str] | str):
        if isinstance(rpc_endpoints, str):
            rpc_endpoints = [rpc_endpoints]
        
        self.failover_manager = RPCFailoverManager(providers=rpc_endpoints)
        # ... rest of initialization
```

**Option B: Wrapper Pattern (Recommended for gradual migration)**

Create a wrapper that maintains compatibility:

```python
class SolanaClientWithFailover:
    """Wrapper that maintains SolanaClient interface but uses failover."""
    
    def __init__(self, rpc_endpoints: list[str] | str):
        if isinstance(rpc_endpoints, str):
            rpc_endpoints = [rpc_endpoints]
        
        self.failover_manager = RPCFailoverManager(providers=rpc_endpoints)
        self._legacy_endpoint = rpc_endpoints[0]  # For compatibility
    
    @property
    def rpc_endpoint(self) -> str:
        """Maintain compatibility with existing code."""
        return self._legacy_endpoint
    
    async def get_client(self) -> AsyncClient:
        """Get client from failover manager."""
        return await self.failover_manager.get_client()
    
    # Delegate all other methods to failover_manager
    async def get_latest_blockhash(self) -> Hash:
        return await self.failover_manager.get_latest_blockhash()
    
    # ... etc
```

## Features

### Automatic Failover
- Automatically switches to healthy provider on failure
- Retries with different providers
- Exponential backoff between retries

### Health Monitoring
- Tracks latency for each provider
- Monitors success rate
- Detects consecutive failures
- Calculates quality scores

### Load Balancing
- Selects best provider based on:
  - Success rate
  - Latency
  - Recent failures
  - Overall health score

### State Consistency
- Shared blockhash cache across providers
- Automatic blockhash updates
- Consistent state checking

## Health Monitoring

### Check Provider Health

```python
# Get health summary
health = failover_manager.get_health_summary()

for endpoint, metrics in health.items():
    print(f"{endpoint}:")
    print(f"  Status: {metrics['status']}")
    print(f"  Latency: {metrics['latency_ms']:.0f}ms")
    print(f"  Success Rate: {metrics['success_rate']:.2%}")
    print(f"  Score: {metrics['score']:.2f}")
```

### Provider Status

- **HEALTHY**: Provider is working well
- **DEGRADED**: Some failures but still usable
- **UNHEALTHY**: Multiple consecutive failures
- **UNKNOWN**: Not yet checked

## Configuration Options

### Health Check Interval
```python
failover_manager = RPCFailoverManager(
    providers=[...],
    health_check_interval=30.0,  # Check every 30 seconds
)
```

### Failure Thresholds
```python
failover_manager = RPCFailoverManager(
    providers=[...],
    max_consecutive_failures=3,  # Mark unhealthy after 3 failures
    min_success_rate=0.8,  # Require 80% success rate
    max_latency_ms=2000.0,  # Max 2 second latency
)
```

## Best Practices

1. **Always include a public fallback**
   ```python
   providers = [
       "https://api.mainnet-beta.solana.com",  # Free fallback
       "https://your-paid-endpoint.com",  # Primary
   ]
   ```

2. **Use different provider types**
   - Public RPC (free, slower)
   - Paid RPC (faster, more reliable)
   - WebSocket RPC (for real-time)

3. **Monitor health regularly**
   ```python
   # In your monitoring loop
   health = failover_manager.get_health_summary()
   # Log or alert on unhealthy providers
   ```

4. **Start failover manager early**
   ```python
   # In your bot initialization
   await failover_manager.start()
   # ... rest of setup
   ```

5. **Clean shutdown**
   ```python
   # On exit
   await failover_manager.stop()
   ```

## Troubleshooting

### All Providers Failing

If all providers are marked unhealthy:
- Check network connectivity
- Verify API keys are valid
- Check provider status pages
- System will use best available provider anyway

### High Latency

If latency is high:
- Add more providers
- Use premium RPC providers
- Adjust `max_latency_ms` threshold
- Check network conditions

### Provider Not Switching

If provider doesn't switch:
- Check health check interval (may be too long)
- Verify failure thresholds aren't too strict
- Check logs for health check errors

## Example: Full Integration

```python
import asyncio
from infrastructure.rpc_failover import RPCFailoverManager

async def main():
    # Initialize with multiple providers
    failover = RPCFailoverManager(
        providers=[
            "https://api.mainnet-beta.solana.com",
            "https://mainnet.helius-rpc.com/?api-key=YOUR_KEY",
        ],
        health_check_interval=30.0,
    )
    
    # Start monitoring
    await failover.start()
    
    try:
        # Use normally
        client = await failover.get_client()
        blockhash = await failover.get_latest_blockhash()
        
        # Check health
        health = failover.get_health_summary()
        print("Provider Health:", health)
        
        # Your trading logic here...
        
    finally:
        await failover.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

## Next Steps

1. ✅ RPC Failover System (DONE)
2. ⏭️ Manual Override Console
3. ⏭️ Enhanced Threat Detection
4. ⏭️ Mayhem Mode Exploitation


