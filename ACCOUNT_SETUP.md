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

#### Option 1: Sub-Account (Recommended) ✅
**Best Option:** Create a sub-account tied to your existing Ethereum wallet.

According to [Lighter.xyz documentation](https://docs.lighter.xyz/perpetual-futures/sub-accounts-and-api-keys):
- Sub-accounts are separate accounts with their own `account_index`
- Orders and positions are isolated between sub-accounts
- Each sub-account can have its own API keys
- You don't need a different wallet!

```yaml
api:
  account_index: <SUB_ACCOUNT_INDEX>  # Different from 366110
  key: "<SUB_ACCOUNT_API_KEY>"
```

**How to create:**
1. Go to Lighter.xyz → Account Settings → Sub-Accounts
2. Create a new sub-account
3. Generate API key for the sub-account
4. Use the sub-account's `account_index` and API key

#### Option 2: Different Main Account (Alternative)
Use a completely different Lighter.xyz main account (requires different wallet):
```yaml
api:
  account_index: <DIFFERENT_ACCOUNT_NUMBER>
  key: "<DIFFERENT_API_KEY>"
```

#### Option 3: Same Account, Different API Key ⚠️ NOT RECOMMENDED
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

#### Option 4: Dry-Run Only (Safest for Testing)
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

