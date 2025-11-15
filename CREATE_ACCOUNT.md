# Creating a New Lighter Account for Trend Trading

## Overview

To separate your trend trading strategies from your automated points bot, you need a **different account** on Lighter.xyz. This guide shows you how to create one.

## Why Separate Accounts?

- ✅ **No Order Conflicts:** Each bot manages its own orders independently
- ✅ **Clear Position Tracking:** Separate inventory and PnL tracking
- ✅ **Risk Isolation:** Problems in one bot don't affect the other
- ✅ **Better Monitoring:** Track performance separately

## Method 1: Through Lighter.xyz UI (Recommended)

### Step 1: Access Lighter.xyz
1. Go to **https://lighter.xyz** (or mainnet.zklighter.elliot.ai)
2. Connect your wallet (same wallet as your main account is fine)

### Step 2: Create/Register New Account
1. Navigate to **Account Settings** or **Profile**
2. Look for **"Create New Account"** or **"Register Account"** option
3. If using the same wallet, you may need to:
   - Create a new account index
   - Or use a different API key with a different `api_key_index`

### Step 3: Get Account Index
1. After creation, note your **account_index** (a number like `366110`)
2. This will be different from your market maker bot's account

### Step 4: Generate API Key
1. Go to **API Settings** or **API Keys** section
2. Click **"Create New API Key"**
3. Set permissions (trading enabled)
4. Copy the **private key** (starts with `0x...`)
5. Note the **api_key_index** (usually 0, 1, 2, etc.)

### Step 5: Update Config
Add to Railway environment variables:
```bash
ACCOUNT_INDEX=<new_account_index>
API_KEY_PRIVATE_KEY=0x<new_api_key_private_key>
API_KEY_INDEX=<api_key_index>
```

## Method 2: Using Script (If Available)

If account creation is supported via API:

```bash
cd lighter-trend-trader
python scripts/create_lighter_account.py \
    --base-url https://mainnet.zklighter.elliot.ai \
    --private-key 0x<your_wallet_private_key> \
    --api-key-index 0
```

**Note:** This may require the account to already exist or be created through the UI first.

## Method 3: Same Account, Different API Key

If you can't create a new account, use the **same account** but a **different API key**:

### Step 1: Create New API Key
1. Go to Lighter.xyz → API Settings
2. Create a **new API key** (different from market maker bot)
3. Note the `api_key_index` (e.g., if market maker uses index 0, use index 1)

### Step 2: Update Config
```bash
# Same account, different API key
ACCOUNT_INDEX=366110  # Same as market maker
API_KEY_INDEX=1       # Different from market maker (which uses 0)
API_KEY_PRIVATE_KEY=0x<new_api_key_private_key>
```

**⚠️ Warning:** This is less ideal than separate accounts, but works if account creation isn't available.

## Verification

After setting up, verify the account is different:

1. **Check Logs:** The bot will warn if using account 366110:
   ```
   ⚠️  WARNING: Using same account_index (366110) as market maker bot!
   ```

2. **Test Order:** Place a tiny test order and verify it appears in the correct account

3. **Dashboard Check:** Check Lighter.xyz dashboard to confirm orders are in the right account

## Current Setup

- **Market Maker Bot:** `account_index: 366110`, `api_key_index: 0` (or null)
- **Trend Trading Bot:** Should use **different** `account_index` OR **different** `api_key_index`

## Troubleshooting

### "Account not found" error
- Account may need to be created through UI first
- Try placing a small order through the UI to activate the account

### "API key invalid" error
- Verify the private key is correct (starts with `0x`)
- Check `api_key_index` matches the key you created
- Ensure API key has trading permissions

### "Account already exists"
- Good! The account is already created
- Just use the existing `account_index`

## Next Steps

1. ✅ Create new account (or new API key)
2. ✅ Get `account_index` and `api_key_index`
3. ✅ Generate API key private key
4. ✅ Update Railway environment variables
5. ✅ Deploy and test with tiny sizes (0.001-0.005 SOL)
6. ✅ Monitor logs to verify account separation

## Support

If you encounter issues:
- Check Lighter.xyz documentation
- Contact Lighter support
- Review `ACCOUNT_SETUP.md` for more details

