# Creating a New Lighter Account for Trend Trading

## Overview

To separate your trend trading strategies from your automated points bot, you need a **different account** on Lighter.xyz. This guide shows you how to create one.

## Why Separate Accounts?

- ✅ **No Order Conflicts:** Each bot manages its own orders independently
- ✅ **Clear Position Tracking:** Separate inventory and PnL tracking
- ✅ **Risk Isolation:** Problems in one bot don't affect the other
- ✅ **Better Monitoring:** Track performance separately

## Method 1: Create a Sub-Account (Recommended) ✅

**Good News:** According to [Lighter.xyz documentation](https://docs.lighter.xyz/perpetual-futures/sub-accounts-and-api-keys), you can create **sub-accounts** tied to your existing Ethereum wallet. **You don't need a different wallet!**

### What are Sub-Accounts?
- Sub-accounts are separate accounts tied to the same Ethereum wallet
- Each sub-account has its own `account_index` (different from main account)
- Each sub-account can have up to 256 API keys
- **Orders and positions are isolated** between sub-accounts
- They share the same account tier and cross balance for fees

### Step 1: Access Lighter.xyz
1. Go to **https://lighter.xyz** (or mainnet.zklighter.elliot.ai)
2. Connect your wallet (same wallet as your main account)

### Step 2: Create Sub-Account
1. Navigate to **Account Settings** or **Sub-Accounts** section
2. Look for **"Create Sub-Account"** or **"New Sub-Account"** option
3. Create the sub-account (it will be tied to your existing wallet)
4. Note the new `account_index` for the sub-account (different from 366110)

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

## Method 2: Different Wallet (Alternative)

If you prefer complete separation (different wallet, different account tier, separate fees):
1. Create a new Ethereum wallet
2. Connect it to Lighter.xyz
3. Register a new main account
4. Use that account's `account_index`

**Note:** Sub-accounts (Method 1) are usually sufficient and easier.

## Method 3: Using Script (If Available)

If account creation is supported via API:

```bash
cd lighter-trend-trader
python scripts/create_lighter_account.py \
    --base-url https://mainnet.zklighter.elliot.ai \
    --private-key 0x<your_wallet_private_key> \
    --api-key-index 0
```

**Note:** This may require the account to already exist or be created through the UI first.

## Method 4: Same Account, Different API Key ⚠️ NOT RECOMMENDED

**Important:** Using the same account with different API keys does NOT prevent conflicts!

### Why This Doesn't Work
- Orders belong to the **account**, not the API key
- Both bots will see the same inventory and positions
- Both bots will see each other's orders
- One bot may cancel the other's orders
- Position tracking will conflict

### When This Might Work
Only if:
- You're manually coordinating the bots
- You're certain they won't interfere
- You accept the risk of conflicts

### Step 1: Create New API Key
1. Go to Lighter.xyz → API Settings
2. Create a **new API key** (different from market maker bot)
3. Note the `api_key_index` (e.g., if market maker uses index 0, use index 1)

### Step 2: Update Config
```bash
# Same account, different API key (NOT RECOMMENDED)
ACCOUNT_INDEX=366110  # Same as market maker
API_KEY_INDEX=1       # Different from market maker (which uses 0)
API_KEY_PRIVATE_KEY=0x<new_api_key_private_key>
```

**⚠️ Strong Warning:** This is NOT recommended. Use a different account (Method 1) if at all possible.

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

