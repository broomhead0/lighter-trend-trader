# Railway Deployment Guide

Deploy your Lighter Trend Trader to Railway for cloud hosting with automatic logging.

## Quick Deploy

### 1. Connect to Railway

1. Go to https://railway.app
2. Sign in with GitHub
3. Click "New Project"
4. Select "Deploy from GitHub repo"
5. Choose `lighter-trend-trader` repository

### 2. Configure Environment Variables

In Railway → Variables, add these (see `railway.env.example` for full list):

**Required:**
```
LOG_LEVEL=INFO
LIGHTER_CONFIG=/app/config.yaml
MEAN_REVERSION_ENABLED=true
MEAN_REVERSION_DRY_RUN=true
MEAN_REVERSION_MARKET=market:2
```

**For Live Trading (when ready):**
```
API_BASE_URL=https://mainnet.zklighter.elliot.ai
API_KEY_PRIVATE_KEY=0x<your_different_api_key>
ACCOUNT_INDEX=<different_account_index>
API_KEY_INDEX=<different_api_key_index>
MEAN_REVERSION_DRY_RUN=false
```

⚠️ **IMPORTANT:** Use a DIFFERENT account than your market maker bot! See `ACCOUNT_SETUP.md`.

### 3. Deploy

Railway will:
- Auto-detect the Dockerfile
- Build the container
- Deploy automatically
- Show logs in real-time

### 4. Monitor

- **Logs**: View in Railway dashboard → Logs tab
- **Status**: Check Railway dashboard for service health
- **Restarts**: Railway auto-restarts on failure

## Logging

In Railway, logs automatically go to:
- **Railway Dashboard** → Logs tab (real-time)
- **Railway CLI**: `railway logs` (if installed)

No local log files needed - everything streams to Railway's logging system.

## Environment Variables Reference

See `railway.env.example` for all available variables. Key ones:

- `MEAN_REVERSION_ENABLED=true` - Enable the trader
- `MEAN_REVERSION_DRY_RUN=true` - Safe testing mode
- `LOG_LEVEL=INFO` - Logging verbosity
- `API_KEY_PRIVATE_KEY` - Your API key (different from market maker!)
- `ACCOUNT_INDEX` - Your account (different from market maker!)

## Updating

Railway auto-deploys on git push to main branch. To update:

```bash
git push origin main
```

Railway will rebuild and redeploy automatically.

## Troubleshooting

### Bot won't start
- Check Railway logs for errors
- Verify `MEAN_REVERSION_ENABLED=true`
- Check environment variables are set

### No logs
- Logs go to Railway dashboard, not local files
- Check Railway → Logs tab
- Verify `LOG_LEVEL=INFO` is set

### API errors
- Verify `API_BASE_URL` is correct
- Check API credentials are set (if live trading)
- Review logs for specific error messages

## Benefits of Railway

✅ **Automatic logging** - No local log files to manage
✅ **Auto-restart** - Bot restarts if it crashes
✅ **Easy updates** - Push to GitHub, auto-deploys
✅ **Monitoring** - Built-in health checks
✅ **Free tier** - Good for testing

## Next Steps

1. Deploy to Railway (follow steps above)
2. Monitor logs in Railway dashboard
3. Test in dry-run mode
4. When ready, enable live trading with separate account

