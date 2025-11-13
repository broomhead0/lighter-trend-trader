# Quick Start Guide

## Get Running in 5 Minutes

### 1. Install Dependencies

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Create Config

```bash
cp config.yaml.example config.yaml
```

Edit `config.yaml` - at minimum set:
```yaml
mean_reversion:
  enabled: true
  dry_run: true  # Start with dry_run!
```

### 3. Run (Dry-Run Mode)

```bash
export PYTHONPATH=.
python main.py
```

You should see:
- Price feed updating prices
- Candle fetching
- Signal checking (may not generate signals immediately)

### 4. What to Expect

**Normal behavior:**
- Bot runs continuously
- Fetches candles every minute
- Updates prices every 5 seconds
- Checks for signals every 5 seconds
- **May not generate signals for hours** - this is normal! Signals only trigger when all conditions are met.

**When a signal triggers:**
- You'll see: `[mean_reversion] DRY RUN: would place bid/ask order`
- In dry-run mode, no real trades are executed
- Logs show what would happen

### 5. Monitor

Watch the logs for:
- ✅ Price updates: `[price_feed] market:2 price: XXX.XX`
- ✅ Candle fetches: `[mean_reversion] fetched X candles`
- ✅ Signal checks (no output = no signal, which is normal)
- ❌ Errors (should be none)

### 6. Next Steps

Once dry-run looks good:
1. Monitor for 24-48 hours
2. Verify signals make sense
3. Then consider `dry_run: false` with small positions

See [TESTING.md](TESTING.md) for detailed testing guide.

