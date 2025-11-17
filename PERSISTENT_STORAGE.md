# Persistent Trade Data Storage

## Problem

Railway containers are **ephemeral** - each deployment creates a new container, and the database is lost on redeploy. We need persistent storage for trade history.

## Solutions

### Option 1: Railway Persistent Volumes (Recommended)

Railway supports persistent volumes that survive deployments.

**Setup:**
1. In Railway dashboard → Your Service → Settings → Volumes
2. Create a new volume (e.g., `pnl-data`)
3. Mount it at `/data` in your service

**Configuration:**
```yaml
# config.yaml
pnl_backup:
  enabled: false  # Not needed if using Railway volume
```

**Environment Variable:**
```
PNL_DB_PATH=/data/pnl_trades.db
```

**Pros:**
- ✅ Simple setup
- ✅ No external dependencies
- ✅ Automatic persistence
- ✅ Fast access

**Cons:**
- ⚠️ Railway-specific (not portable)
- ⚠️ Limited to Railway platform

---

### Option 2: External Database (PostgreSQL)

Use a managed PostgreSQL database (Railway, Supabase, Neon, etc.).

**Setup:**
1. Create PostgreSQL database in Railway (or external provider)
2. Get connection string
3. Update code to use PostgreSQL instead of SQLite

**Configuration:**
```yaml
# config.yaml
pnl_database:
  type: postgresql
  url: ${DATABASE_URL}  # From Railway or external provider
```

**Pros:**
- ✅ Industry standard
- ✅ Scalable
- ✅ Multiple services can access
- ✅ Built-in backups

**Cons:**
- ⚠️ Requires database setup
- ⚠️ Additional cost
- ⚠️ Network latency

---

### Option 3: Backup to External Storage (S3, etc.)

Periodically backup SQLite database to external storage.

**Setup:**
1. Configure S3/MinIO credentials
2. Enable backup in config

**Configuration:**
```yaml
# config.yaml
pnl_backup:
  enabled: true
  interval_seconds: 3600  # Backup every hour
  s3:
    bucket: your-bucket-name
    key_prefix: pnl_backups/
    endpoint_url: https://s3.amazonaws.com  # Or MinIO URL
    # Credentials from env vars: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
```

**Or local backup:**
```yaml
pnl_backup:
  enabled: true
  interval_seconds: 3600
  local_path: /data/backups  # Persistent volume path
  max_backups: 10  # Keep last 10 backups
```

**Pros:**
- ✅ Works with any storage
- ✅ Versioned backups
- ✅ Can restore from any point

**Cons:**
- ⚠️ Requires backup service setup
- ⚠️ Not real-time (periodic only)

---

### Option 4: Webhook/API Export

Export trades to external service in real-time.

**Configuration:**
```yaml
# config.yaml
pnl_backup:
  enabled: true
  webhook_url: https://your-api.com/trades
```

**Pros:**
- ✅ Real-time export
- ✅ Can use any backend
- ✅ No storage management

**Cons:**
- ⚠️ Requires external service
- ⚠️ Network dependency
- ⚠️ Potential data loss if service down

---

## Recommended Setup

**For Railway deployment:**

1. **Use Railway Persistent Volume** (Option 1)
   - Simplest and most reliable
   - No external dependencies
   - Automatic persistence

2. **Add periodic backup** (Option 3 - local backup)
   - Backup to same volume
   - Keep last 10 backups
   - Safety net if database corrupts

**Implementation:**
```yaml
# config.yaml
pnl_backup:
  enabled: true
  interval_seconds: 3600  # Hourly backups
  local_path: /data/backups
  max_backups: 10
```

**Environment Variable:**
```
PNL_DB_PATH=/data/pnl_trades.db
```

---

## Querying Trade Data

Use the query script:

```bash
# Overall stats
python scripts/query_pnl.py

# By strategy
python scripts/query_pnl.py --strategy mean_reversion

# Last 24 hours
python scripts/query_pnl.py --since 24h

# Export to CSV
python scripts/query_pnl.py --export csv --output trades.csv

# Recent trades
python scripts/query_pnl.py --recent 20
```

---

## Migration from Old Database

If you have an old database file:

```bash
# Copy to persistent volume
cp pnl_trades.db /data/pnl_trades.db

# Or restore from backup
cp /data/backups/pnl_trades_20241117_120000.db /data/pnl_trades.db
```

---

## Monitoring

Check database size:
```bash
ls -lh /data/pnl_trades.db
```

Check backup status:
```bash
ls -lh /data/backups/
```

View recent trades:
```bash
python scripts/query_pnl.py --recent 10
```

