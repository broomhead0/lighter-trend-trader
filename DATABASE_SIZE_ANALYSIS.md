# Database Size Analysis

## Current Situation

- **Railway Volume**: 67MB / 500MB used
- **Database File**: ~1.9 MB (`/data/pnl_trades.db`)
- **Gap**: ~65 MB unaccounted for

## What's Taking Space

### Database File (1.9 MB)

1. **Trades** (~200 bytes each)
   - ✅ **KEEP ALL** - Essential for PnL analysis, win rate, R:R ratios
   - Needed for strategy optimization feedback loop

2. **Candles** (~100 bytes each)
   - ✅ **KEEP RECENT** - Last 500-1000 per strategy
   - Used for indicator calculations (RSI, BB, EMA, MACD)
   - Can delete candles >30 days old or >1000 per strategy

3. **Renko Bricks** (~120 bytes each)
   - ✅ **AUTO-LIMITED** - Code keeps max 200 bricks per strategy
   - Oldest bricks automatically removed as new ones added
   - No cleanup needed

4. **Price History** (~50 bytes each)
   - ⚠️ **LIMITED IN CODE** - Code keeps last 1000 per strategy
   - Used for ATR and AO calculations
   - Code deletes all old data when saving (line 214 in renko_tracker.py)
   - **Potential issue**: If code wasn't running, old data may accumulate

5. **Positions** (~100 bytes each)
   - ✅ **MINIMAL** - Only open positions (usually 0-3)
   - No cleanup needed

### Unaccounted Space (~65 MB)

The 65MB gap is likely:

1. **WAL File** (Write-Ahead Log)
   - SQLite WAL mode creates a `-wal` file
   - Can grow large if not checkpointed regularly
   - **Solution**: Run `PRAGMA wal_checkpoint(TRUNCATE)` periodically

2. **Backup Files**
   - If backup is enabled, files in `/data/backups/`
   - **Solution**: Keep only last 10 backups (configurable)

3. **SQLite Overhead**
   - Indexes, free space in pages
   - **Solution**: Run `VACUUM` to reclaim space

4. **Other Files on Volume**
   - Check if other services/files are using the volume

## Recommendations

### Essential (Keep)

- ✅ **All trades** - Critical for PnL analysis
- ✅ **Recent candles** - Last 500-1000 per strategy
- ✅ **Recent bricks** - Last 200 per strategy (auto-limited)
- ✅ **Open positions** - Minimal size

### Can Be Reduced

- ⚠️ **Price history** - Only need last 1000 per strategy (code already limits)
- ⚠️ **Old candles** - Delete >30 days or >1000 per strategy
- ⚠️ **WAL file** - Checkpoint regularly to reduce size

### Cleanup Actions

1. **Run cleanup script**: `python scripts/cleanup_old_data.py`
   - Cleans old price history (>1000 per strategy)
   - Cleans old candles (>1000 per strategy or >30 days)
   - Vacuums database
   - Checkpoints WAL file

2. **Monitor WAL size**: Check `-wal` file size periodically

3. **Limit backups**: Keep only last 10 backup files

4. **Regular maintenance**: Run cleanup monthly or when volume >100MB

## For Strategy Optimization

**What you need:**
- All trades (for PnL analysis)
- Recent candles (for indicators)
- Recent bricks (for Renko indicators)
- Recent price history (for ATR/AO)

**What you DON'T need:**
- Old candles (>30 days)
- Old price history (>1000 per strategy)
- Large WAL files (checkpoint regularly)

## Implementation

The code already limits:
- ✅ Renko bricks: Max 200 per strategy (auto-removes oldest)
- ✅ Price history: Max 1000 per strategy (deletes old on save)

What needs cleanup:
- ⚠️ Old candles (no automatic limit)
- ⚠️ WAL file (needs periodic checkpoint)

## Next Steps

1. Run `scripts/check_db_usage.py` to see detailed breakdown
2. Run `scripts/cleanup_old_data.py` to clean old data
3. Monitor volume usage monthly
4. Consider adding automatic cleanup for old candles

