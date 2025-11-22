# Manual Override Console - Integration Guide

## Overview

The Manual Override Console provides emergency controls, manual trading, and strategy management for the bot.

## Features

✅ **Emergency Stop** - Instant kill switch  
✅ **Pause/Resume** - Temporarily halt operations  
✅ **Manual Trading** - Execute buys/sells manually  
✅ **Position Management** - View and close positions  
✅ **Strategy Override** - Temporarily change strategy parameters  
✅ **Status Monitoring** - Real-time bot status  

---

## Quick Start

### 1. Automatic Integration

The override console is **automatically available** when you create a `UniversalTrader`:

```python
from trading.universal_trader import UniversalTrader

trader = UniversalTrader(
    rpc_endpoint="...",
    wss_endpoint="...",
    private_key="...",
    buy_amount=0.1,
    buy_slippage=0.1,
    sell_slippage=0.1,
)

# Override console is automatically available
override = trader.override_console

# Start the bot
await trader.start()
```

### 2. Basic Usage

```python
# Emergency stop
await override.emergency_stop()

# Pause bot
await override.pause()

# Resume bot
await override.resume()

# Reset emergency stop
await override.reset()

# Manual buy
result = await override.manual_buy(
    token_address="TokenMintAddress...",
    amount=0.1,  # Optional
    slippage=0.1,  # Optional
)

# Manual sell
result = await override.manual_sell(
    token_address="TokenMintAddress...",
    slippage=0.1,  # Optional
)

# Get status
status = await override.get_status()
print(f"Bot state: {status.bot_state}")
print(f"Active positions: {status.active_positions}")

# Get positions
positions = await override.get_positions()
for token, position in positions.items():
    print(f"{token}: {position.quantity} @ {position.entry_price}")
```

---

## Emergency Controls

### Emergency Stop

**Use when**: Something is wrong and you need to stop immediately.

```python
await override.emergency_stop()
```

**What it does**:
- Immediately stops all trading
- Cancels pending operations
- Prevents new operations
- Requires explicit `reset()` to resume

**Reset emergency stop**:
```python
await override.reset()
```

### Pause/Resume

**Use when**: You want to temporarily stop trading (can be resumed easily).

```python
# Pause
await override.pause()

# Resume
await override.resume()
```

---

## Manual Trading

### Manual Buy

Execute a buy order manually:

```python
result = await override.manual_buy(
    token_address="TokenMintAddress...",
    amount=0.1,  # SOL amount (optional, uses default if None)
    slippage=0.1,  # Slippage tolerance (optional)
    priority_fee=200000,  # Priority fee (optional)
)

if result.success:
    print(f"Bought {result.quantity} tokens at {result.price}")
else:
    print(f"Buy failed: {result.error}")
```

### Manual Sell

Execute a sell order manually:

```python
result = await override.manual_sell(
    token_address="TokenMintAddress...",
    slippage=0.1,  # Optional
    priority_fee=200000,  # Optional
)

if result.success:
    print(f"Sold at {result.price}")
```

### Close Position

Close a specific position:

```python
await override.close_position("TokenMintAddress...")
```

---

## Position Management

### Get All Positions

```python
positions = await override.get_positions()

for token_address, position in positions.items():
    print(f"Token: {token_address}")
    print(f"  Quantity: {position.quantity}")
    print(f"  Entry Price: {position.entry_price}")
    print(f"  Entry Time: {position.entry_time}")
    print(f"  Take Profit: {position.take_profit_price}")
    print(f"  Stop Loss: {position.stop_loss_price}")
```

### Get Single Position

```python
position = await override.get_position("TokenMintAddress...")

if position:
    print(f"Active position: {position.quantity} @ {position.entry_price}")
else:
    print("No active position for this token")
```

---

## Strategy Override

### Override Strategy Parameters

Temporarily change strategy parameters:

```python
await override.override_strategy({
    "buy_amount": 0.2,  # Increase buy amount
    "take_profit_percentage": 0.5,  # 50% take profit
    "stop_loss_percentage": 0.1,  # 10% stop loss
    "max_hold_time": 3600,  # 1 hour max hold
})
```

### Reset Strategy

Restore original strategy:

```python
await override.reset_strategy()
```

**Available Override Parameters**:
- `buy_amount`: Buy amount in SOL
- `buy_slippage`: Buy slippage tolerance
- `sell_slippage`: Sell slippage tolerance
- `take_profit_percentage`: Take profit percentage (0.5 = 50%)
- `stop_loss_percentage`: Stop loss percentage (0.2 = 20%)
- `max_hold_time`: Maximum hold time in seconds

---

## Status Monitoring

### Get Status

```python
status = await override.get_status()

print(f"Bot State: {status.bot_state}")
print(f"Emergency Stop: {status.is_emergency_stopped}")
print(f"Paused: {status.is_paused}")
print(f"Active Positions: {status.active_positions}")
print(f"Last Command: {status.last_command}")
print(f"Strategy Override: {status.override_active}")
```

### Check State

```python
# Quick checks
if override.is_running():
    print("Bot is running")

if override.is_paused():
    print("Bot is paused")

if override.is_emergency_stopped():
    print("Emergency stop is active")
```

### Check If Trading Is Allowed

```python
can_trade, reason = override.check_can_trade()

if can_trade:
    print("Trading is allowed")
else:
    print(f"Trading blocked: {reason}")
```

---

## Callbacks

### State Change Callback

```python
def on_state_change(new_state):
    print(f"Bot state changed to: {new_state}")

override.set_on_state_change(on_state_change)
```

### Emergency Stop Callback

```python
def on_emergency_stop():
    print("🚨 Emergency stop activated!")
    # Send alert, log, etc.

override.set_on_emergency_stop(on_emergency_stop)
```

### Trade Executed Callback

```python
def on_trade_executed(result):
    if result.success:
        print(f"Trade successful: {result.signature}")
    else:
        print(f"Trade failed: {result.error}")

override.set_on_trade_executed(on_trade_executed)
```

---

## Integration with GUI

The override console can be integrated with the GUI:

```python
# In GUI code
def on_emergency_stop_clicked():
    asyncio.create_task(trader.override_console.emergency_stop())

def on_pause_clicked():
    asyncio.create_task(trader.override_console.pause())

def on_resume_clicked():
    asyncio.create_task(trader.override_console.resume())

def on_manual_buy_clicked():
    token = token_entry.get()
    amount = float(amount_entry.get())
    asyncio.create_task(
        trader.override_console.manual_buy(token, amount)
    )
```

---

## Example: Complete Workflow

```python
import asyncio
from trading.universal_trader import UniversalTrader

async def main():
    # Create trader
    trader = UniversalTrader(
        rpc_endpoint="https://api.mainnet-beta.solana.com",
        wss_endpoint="wss://api.mainnet-beta.solana.com",
        private_key="your_private_key",
        buy_amount=0.1,
        buy_slippage=0.1,
        sell_slippage=0.1,
    )

    override = trader.override_console

    # Set up callbacks
    override.set_on_emergency_stop(lambda: print("🚨 EMERGENCY STOP!"))
    override.set_on_state_change(lambda state: print(f"State: {state}"))

    # Start bot
    await trader.start()

    # Bot runs automatically...

    # Later, manual control
    await asyncio.sleep(60)  # Wait 1 minute

    # Check status
    status = await override.get_status()
    print(f"Active positions: {status.active_positions}")

    # Manual buy
    result = await override.manual_buy(
        "TokenMintAddress...",
        amount=0.2
    )

    # Override strategy
    await override.override_strategy({
        "take_profit_percentage": 0.5,
    })

    # Wait more...
    await asyncio.sleep(60)

    # Close position
    await override.close_position("TokenMintAddress...")

    # Reset strategy
    await override.reset_strategy()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Safety Notes

1. **Emergency Stop** requires explicit `reset()` to resume
2. **Pause** can be resumed easily with `resume()`
3. **Manual trades** respect pause/emergency stop
4. **Strategy overrides** are temporary (use `reset_strategy()` to restore)
5. **Position tracking** is automatic for manual trades

---

## Troubleshooting

### Override Console Not Available

If `trader.override_console` is `None`:
- Check that `src/control/manual_override.py` exists
- Check import errors in logs
- Feature is optional, bot works without it

### Emergency Stop Won't Reset

Use `reset()` explicitly:
```python
await override.reset()
```

### Manual Trade Fails

Check:
- Bot is not paused/stopped
- Token address is valid
- Sufficient balance
- RPC connection is working

---

## Next Steps

- ✅ Manual Override Console (DONE)
- ⏭️ Enhanced Threat Detection
- ⏭️ GUI Integration
- ⏭️ API Endpoints

