# Account Setup - IMPORTANT! ⚠️

## Critical: Use Separate Accounts

**The trend trader bot MUST use a different account than your market making bot to avoid order conflicts.**

### Why?

Both bots will:
- Place orders on the same market (SOL)
- Manage positions independently
- Use different strategies

If they share the same account:
- ❌ Orders can conflict
- ❌ Position tracking gets confused
- ❌ Risk management breaks
- ❌ Both bots may try to cancel each other's orders

### Solution Options

#### Option 1: Different Account (Recommended)
Use a completely different Lighter.xyz account:
```yaml
api:
  account_index: <DIFFERENT_ACCOUNT_NUMBER>
  key: "<DIFFERENT_API_KEY>"
```

#### Option 2: Same Account, Different API Key ⚠️ NOT RECOMMENDED
**Warning:** This does NOT prevent conflicts! Orders belong to the account, not the API key.

If you use the same account with different API keys:
- ❌ Both bots will see the same inventory/positions
- ❌ Both bots will see each other's orders
- ❌ One bot may cancel the other's orders
- ❌ Position tracking will conflict

**Only use this if:**
- You're absolutely certain the bots won't interfere
- You're manually coordinating their behavior
- You accept the risk of conflicts

```yaml
api:
  account_index: 366110  # Same account (NOT RECOMMENDED)
  api_key_index: 1  # Different API key (market maker uses 0 or null)
  key: "<DIFFERENT_API_KEY_PRIVATE_KEY>"
```

#### Option 3: Dry-Run Only (Safest for Testing)
Keep `dry_run: true` - no real orders, no conflicts:
```yaml
mean_reversion:
  dry_run: true  # No real trades, safe to test
```

### Current Market Maker Bot Account

Your market maker bot uses:
- `account_index: 366110`
- `api_key_index: null` (or 0)

**Do NOT use these same values in the trend trader!**

### Recommended Setup

1. **For Testing:** Keep `dry_run: true` (no account needed)
2. **For Live Trading:**
   - Create a new API key in Lighter.xyz dashboard
   - Use that API key's `api_key_index` and private key
   - Or use a completely different account

### Verification

The bot will warn you at startup if it detects you're using account 366110:
```
⚠️  WARNING: Using same account_index (366110) as market maker bot!
```

If you see this warning, **stop and fix your config** before enabling live trading.

