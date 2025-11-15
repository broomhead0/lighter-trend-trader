# Account Separation Plan: RSI+BB vs Renko+AO

## Overview
Separate the two strategies into different Lighter.xyz sub-accounts to avoid position conflicts, especially with Renko+AO's new scaling feature.

## Current Setup
- **Account**: `281474976639501` (shared by both strategies)
- **API Key Index**: `16`
- **Wallet**: `0xE7C753eD56B4258b1a700D9A1732D5bCff179A11`

## Target Setup
- **RSI+BB Strategy**: Keep on current account `281474976639501` (or move to new account)
- **Renko+AO Strategy**: New sub-account (e.g., `281474976639502` or similar)

## Step-by-Step Plan

### Step 1: Create New Sub-Account for Renko+AO
1. Go to Lighter.xyz UI: https://app.lighter.xyz
2. Create a new sub-account (e.g., name it "renko-ao" or "divergence")
3. Note the `account_index` (you'll need this)

### Step 2: Generate API Key for New Account
Use the existing `scripts/setup_api_key.py` script:

```bash
python scripts/setup_api_key.py \
    --eth-private-key 0x<your_wallet_private_key> \
    --api-key-index 17 \
    --account-index <new_account_index>
```

**Note**: Use a different `api_key_index` (e.g., 17) to avoid conflicts.

### Step 3: Update Code to Support Per-Strategy Accounts

#### 3.1 Update `main.py` to Support Per-Strategy Trading Clients
- Create separate `TradingClient` instances for each strategy
- Each strategy gets its own account configuration
- Strategies remain independent

#### 3.2 Update Configuration Structure
- Add per-strategy account config in `config.yaml.example`
- Support environment variables:
  - `MEAN_REVERSION_ACCOUNT_INDEX` (optional, falls back to `ACCOUNT_INDEX`)
  - `MEAN_REVERSION_API_KEY_INDEX` (optional, falls back to `API_KEY_INDEX`)
  - `MEAN_REVERSION_API_KEY_PRIVATE_KEY` (optional, falls back to `API_KEY_PRIVATE_KEY`)
  - `RENKO_AO_ACCOUNT_INDEX` (optional, falls back to `ACCOUNT_INDEX`)
  - `RENKO_AO_API_KEY_INDEX` (optional, falls back to `API_KEY_INDEX`)
  - `RENKO_AO_API_KEY_PRIVATE_KEY` (optional, falls back to `API_KEY_PRIVATE_KEY`)

#### 3.3 Backward Compatibility
- If per-strategy config not provided, both strategies use the same account (current behavior)
- This allows gradual migration

### Step 4: Update Railway Environment Variables

#### For RSI+BB (keep on current account):
```
ACCOUNT_INDEX=281474976639501
API_KEY_INDEX=16
API_KEY_PRIVATE_KEY=<existing_key>
```

#### For Renko+AO (new account):
```
RENKO_AO_ACCOUNT_INDEX=<new_account_index>
RENKO_AO_API_KEY_INDEX=17
RENKO_AO_API_KEY_PRIVATE_KEY=<new_key>
```

### Step 5: Test Setup
1. Test RSI+BB with existing account (should work as before)
2. Test Renko+AO with new account (verify API key works)
3. Verify both strategies can run simultaneously without conflicts

## Benefits After Separation
✅ **True Isolation**: Each strategy has its own account
✅ **No Position Conflicts**: Positions don't offset each other
✅ **Independent Tracking**: Each strategy sees real positions
✅ **Scaling Works**: Renko+AO can scale without affecting RSI+BB
✅ **Cleaner PnL**: Per-account, per-strategy tracking
✅ **Easier Debugging**: Can see actual positions per strategy

## Migration Path
1. **Phase 1**: Update code to support per-strategy accounts (backward compatible)
2. **Phase 2**: Create new account and API key for Renko+AO
3. **Phase 3**: Update Railway env vars
4. **Phase 4**: Deploy and verify both strategies work independently

## Files to Modify
1. `main.py` - Support per-strategy TradingClient instances
2. `config.yaml.example` - Add per-strategy account config
3. `railway.env.example` - Add per-strategy env vars
4. `MASTER_CONTEXT.md` - Update with new account structure

## Rollback Plan
If issues arise, we can:
- Remove per-strategy env vars
- Both strategies will fall back to shared account (current behavior)
- No code changes needed for rollback

