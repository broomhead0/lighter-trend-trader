# Railway Persistent Volume Setup

## Quick Setup (5 minutes)

### Step 1: Create Volume in Railway

1. Go to Railway Dashboard → Your Service
2. Click **Settings** tab
3. Scroll to **Volumes** section
4. Click **+ New Volume**
5. Name it: `pnl-data`
6. Mount path: `/data`
7. Click **Create**

### Step 2: Set Environment Variable

The environment variable is already set:
```
PNL_DB_PATH=/data/pnl_trades.db
```

This tells the bot to store the database on the persistent volume.

### Step 3: Verify

After the next deployment, check logs:
```
[INFO] PnL tracker initialized: /data/pnl_trades.db
```

## What This Does

- ✅ Database persists across deployments
- ✅ Trade history survives redeploys
- ✅ Automatic backups every hour (to `/data/backups`)
- ✅ Last 10 backups kept automatically

## Querying Data

```bash
# From your local machine (if you have access)
python scripts/query_pnl.py --db-path /path/to/backup.db

# Or download database from Railway and query locally
```

## Backup Location

Backups are stored at: `/data/backups/pnl_trades_YYYYMMDD_HHMMSS.db`

The bot automatically:
- Creates backups every hour
- Keeps last 10 backups
- Removes older backups

## Troubleshooting

**Database not persisting?**
- Check volume is mounted: Railway → Settings → Volumes
- Verify `PNL_DB_PATH=/data/pnl_trades.db` is set
- Check logs for database path on startup

**Backups not working?**
- Check `pnl_backup.enabled=true` in config
- Verify `/data/backups` directory exists
- Check logs for backup errors

