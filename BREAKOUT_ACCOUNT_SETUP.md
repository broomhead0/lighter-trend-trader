# Breakout Strategy Account Setup

## Step-by-Step Process (Based on Previous Experience)

### Step 1: Create Sub-Account in Lighter.xyz Dashboard
1. Go to Lighter.xyz → Account Settings → Sub-Accounts
2. Create a new sub-account (name it "breakout" or similar)
3. **Note the account index** (you'll need this)

### Step 2: Generate API Key
1. In the new sub-account, go to API Keys section
2. Generate a new API key
3. **Save the following:**
   - Account Index (e.g., `281474976639501`)
   - API Key Index (e.g., `17`)
   - API Key Public Key (starts with `0x...`)
   - API Key Private Key (starts with `0x...`)

### Step 3: Provide Info to Bot
Once you have the account created, provide:
- Account Index
- API Key Index
- API Key Private Key
- Your ETH Wallet Private Key (same one we used before: `0x9b5039dfe996508b3c04bafe42758914b0f173ba4e3353cbd6cdb059c7778745`)

### Step 4: API Key Registration
The bot will:
1. Use your ETH wallet private key to sign the "Change Pub Key" transaction
2. Register the API key on-chain
3. Test with a small order to verify it works

### Step 5: Configure Railway
Set environment variables:
- `BREAKOUT_ACCOUNT_INDEX=<account_index>`
- `BREAKOUT_API_KEY_INDEX=<api_key_index>`
- `BREAKOUT_API_KEY_PRIVATE_KEY=<api_key_private_key>`

## What We Learned from Previous Setup

### What Worked:
✅ Using ETH wallet private key to get account info
✅ Using `system_setup.py` script to register API keys
✅ Testing with small orders before going live
✅ Separate accounts prevent conflicts

### What to Avoid:
❌ Don't push sensitive keys to GitHub
❌ Don't use same account as other bots
❌ Don't skip the test order step

## Current Account Setup

- **Market Maker Bot**: Account `366110`
- **RSI+BB Strategy**: Account `281474976639501` (API Key Index 16)
- **Renko+AO Strategy**: Separate account (renko_ao)
- **Breakout Strategy**: **NEW** - Need to create

## Next Steps

1. **You**: Create sub-account in Lighter.xyz dashboard
2. **You**: Provide account index, API key index, and API key private key
3. **Me**: Set up API key registration and test
4. **Me**: Build breakout strategy
5. **Me**: Integrate into main.py
6. **Both**: Test in dry-run, then go live

