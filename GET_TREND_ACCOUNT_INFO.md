# Getting "Trend" Account Information

## Quick Guide

To configure the trend trading bot with your new "trend" sub-account, you need:

1. **Account Index** (`account_index`) - The unique number for your "trend" account
2. **API Key Private Key** - A private key for API access
3. **API Key Index** - Usually 0 for the first API key

## Method 1: From Lighter.xyz Dashboard (Easiest)

### Step 1: Find Account Index
1. Go to **https://lighter.xyz** (or mainnet.zklighter.elliot.ai)
2. Navigate to your **"trend"** sub-account
3. Go to **Account Settings** or **Account Info**
4. Look for **Account Index** or **Account ID** (a number like `366110`)
5. **Copy this number** - this is your `account_index`

### Step 2: Generate API Key
1. Still in the "trend" account, go to **API Settings** or **API Keys**
2. Click **"Create New API Key"** or **"Generate API Key"**
3. Set permissions (enable trading)
4. **Copy the private key** (starts with `0x...`)
5. Note the **API Key Index** (usually 0 for the first key)

### Step 3: Verify
You should now have:
- ✅ `account_index`: A number (different from 366110)
- ✅ `API_KEY_PRIVATE_KEY`: A hex string starting with `0x`
- ✅ `API_KEY_INDEX`: Usually 0

## Method 2: Using Script (If You Have Account Index)

If you already know the account_index, you can verify it with the script:

```bash
cd lighter-trend-trader
python scripts/get_account_info.py \
    --base-url https://mainnet.zklighter.elliot.ai \
    --api-key-private-key 0x<your_api_key_private_key> \
    --account-index <account_index> \
    --api-key-index 0
```

## What I Need From You

To configure the bot, please provide:

1. **Account Index** - What's the account_index for your "trend" account?
   - You can find this in the Lighter.xyz dashboard
   - It should be a number (different from 366110)

2. **API Key Private Key** - Have you generated an API key for the "trend" account?
   - If yes, what's the private key? (starts with `0x...`)
   - If no, I can guide you through generating one

3. **API Key Index** - What index is the API key?
   - Usually 0 for the first API key

## Next Steps

Once you provide this information, I'll:
1. ✅ Update Railway environment variables
2. ✅ Verify the account is different from 366110
3. ✅ Test the connection
4. ✅ Configure the bot to use the new account

## Quick Check

**Important:** Make sure the account_index is **different from 366110** (your market maker bot's account).

If it's the same, we need to create a proper sub-account instead.

