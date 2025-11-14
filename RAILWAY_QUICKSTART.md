# Railway Quick Start

Deploy your trend trader to Railway in 5 minutes!

## Steps

### 1. Connect Repository

1. Go to https://railway.app
2. Sign in with GitHub
3. Click **"New Project"**
4. Select **"Deploy from GitHub repo"**
5. Choose `lighter-trend-trader`

### 2. Set Environment Variables

In Railway → **Variables** tab, add:

```
MEAN_REVERSION_ENABLED=true
MEAN_REVERSION_DRY_RUN=true
MEAN_REVERSION_MARKET=market:2
LOG_LEVEL=INFO
```

That's it for testing! Railway will:
- ✅ Auto-detect Dockerfile
- ✅ Build and deploy
- ✅ Stream logs to dashboard
- ✅ Auto-restart on failure

### 3. View Logs

- Go to Railway dashboard
- Click on your service
- Open **"Logs"** tab
- See real-time bot activity!

### 4. For Live Trading (Later)

When ready, add these variables:

```
API_BASE_URL=https://mainnet.zklighter.elliot.ai
API_KEY_PRIVATE_KEY=0x<your_different_api_key>
ACCOUNT_INDEX=<different_account_index>
API_KEY_INDEX=<different_api_key_index>
MEAN_REVERSION_DRY_RUN=false
```

⚠️ **Remember:** Use a DIFFERENT account than your market maker bot!

## Benefits

✅ **No local logs** - Everything in Railway dashboard  
✅ **Auto-restart** - Bot restarts if it crashes  
✅ **Easy updates** - Push to GitHub, auto-deploys  
✅ **Free tier** - Good for testing  
✅ **Monitoring** - Built-in health checks  

## That's It!

Your bot is now running in the cloud. Check Railway logs to see it in action!

