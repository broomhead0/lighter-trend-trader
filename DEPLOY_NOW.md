# Deploy to Railway - Step by Step

Since Railway CLI may not be available, here's the manual deployment process:

## Step 1: Go to Railway

1. Open https://railway.app in your browser
2. Sign in with your GitHub account (same one that owns the repo)

## Step 2: Create New Project

1. Click **"New Project"** button (top right)
2. Select **"Deploy from GitHub repo"**
3. If prompted, authorize Railway to access your GitHub
4. Find and select **`lighter-trend-trader`** repository
5. Click **"Deploy Now"**

## Step 3: Set Environment Variables

Once the project is created:

1. Click on your service (should be named `lighter-trend-trader`)
2. Go to **"Variables"** tab
3. Click **"New Variable"** and add these one by one:

```
MEAN_REVERSION_ENABLED=true
MEAN_REVERSION_DRY_RUN=true
MEAN_REVERSION_MARKET=market:2
LOG_LEVEL=INFO
```

4. Click **"Add"** after each variable

## Step 4: Wait for Deployment

- Railway will automatically:
  - Detect the Dockerfile
  - Build the container
  - Deploy the service
- Watch the build logs in the **"Deployments"** tab
- Should take 2-3 minutes

## Step 5: View Logs

1. Once deployed, go to **"Logs"** tab
2. You should see:
   ```
   [INFO] Starting Lighter Trend Trader...
   [INFO] Mean reversion trader initialized
   [INFO] Price feed initialized
   ```
3. Bot is now running!

## Step 6: Monitor

- **Logs tab**: Real-time bot activity
- **Metrics tab**: Resource usage
- **Settings tab**: Configuration

## That's It!

Your bot is now running in the cloud. Logs will stream to Railway dashboard automatically.

## For Live Trading (Later)

When ready, add these additional variables:

```
API_BASE_URL=https://mainnet.zklighter.elliot.ai
API_KEY_PRIVATE_KEY=0x<your_different_api_key>
ACCOUNT_INDEX=<different_account_index>
API_KEY_INDEX=<different_api_key_index>
MEAN_REVERSION_DRY_RUN=false
```

⚠️ **Remember:** Use a DIFFERENT account than your market maker bot (account 366110)!

## Troubleshooting

**Build fails?**
- Check Railway logs for error messages
- Verify Dockerfile is in repo (it is!)
- Check that requirements.txt exists

**Bot won't start?**
- Check logs for errors
- Verify `MEAN_REVERSION_ENABLED=true` is set
- Check environment variables are correct

**No logs?**
- Logs appear in Railway dashboard → Logs tab
- Make sure service is running (green status)
- Check LOG_LEVEL=INFO is set

