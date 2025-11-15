# Setup Guide: Separate Accounts for RSI+BB and Renko+AO

## Quick Start

This guide walks you through setting up separate Lighter.xyz sub-accounts for each strategy to avoid position conflicts.

## Step 1: Create New Sub-Account for Renko+AO

1. Go to https://app.lighter.xyz
2. Navigate to your account settings
3. Create a new sub-account (e.g., name it "renko-ao" or "divergence")
4. **Note the `account_index`** - you'll need this in Step 2

## Step 2: Generate API Key for New Account

Use the existing setup script:

```bash
python scripts/setup_api_key.py \
    --eth-private-key 0x<your_wallet_private_key> \
    --api-key-index 17 \
    --account-index <new_account_index>
```

**Important:**
- Use a different `api_key_index` (e.g., 17) to avoid conflicts with RSI+BB (which uses 16)
- The script will output the API key private key - **save this!**

## Step 3: Update Railway Environment Variables

Add these to your Railway project:

### For Renko+AO (new account):
```
RENKO_AO_ACCOUNT_INDEX=<new_account_index>
RENKO_AO_API_KEY_INDEX=17
RENKO_AO_API_KEY_PRIVATE_KEY=0x<new_api_key_private_key>
```

### For RSI+BB (keep existing or set explicitly):
```
MEAN_REVERSION_ACCOUNT_INDEX=281474976639501
MEAN_REVERSION_API_KEY_INDEX=16
MEAN_REVERSION_API_KEY_PRIVATE_KEY=0x<existing_api_key_private_key>
```

**Note:** If you don't set the per-strategy variables, both strategies will use the shared account (backward compatible).

## Step 4: Verify Setup

1. Deploy to Railway (auto-deploys from GitHub)
2. Check logs for initialization messages:
   - Should see: `RSI + BB trader initialized with dedicated account <account_index>`
   - Should see: `Renko + AO trader initialized with dedicated account <account_index>`
3. Both strategies should now run independently

## Step 5: Test (Optional)

You can test the API key for the new account:

```bash
python scripts/test_order.py \
    --account-index <new_account_index> \
    --api-key-index 17 \
    --api-key-private-key 0x<new_api_key_private_key>
```

## Benefits After Separation

✅ **True Isolation**: Each strategy has its own account  
✅ **No Position Conflicts**: Positions don't offset each other  
✅ **Independent Tracking**: Each strategy sees real positions  
✅ **Scaling Works**: Renko+AO can scale without affecting RSI+BB  
✅ **Cleaner PnL**: Per-account, per-strategy tracking  
✅ **Easier Debugging**: Can see actual positions per strategy  

## Troubleshooting

### "API key not found" error
- Make sure you ran `setup_api_key.py` and the transaction completed
- Wait 10-15 seconds after setup for the transaction to propagate
- Verify the API key index matches what you set in Railway

### Both strategies still using same account
- Check that you set the per-strategy environment variables in Railway
- Verify the variable names are correct (case-sensitive)
- Check logs for which account each strategy is using

### Rollback
If you need to rollback:
- Remove the per-strategy environment variables from Railway
- Both strategies will automatically fall back to the shared account
- No code changes needed

## Current Account Structure

After setup, you'll have:
- **RSI+BB**: Account `281474976639501`, API Key Index `16`
- **Renko+AO**: Account `<new_account_index>`, API Key Index `17`
- Both under the same wallet: `0xE7C753eD56B4258b1a700D9A1732D5bCff179A11`

