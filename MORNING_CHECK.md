# Morning Status Check Guide

## Quick Status Check

Run this when you wake up:
```bash
cd /Users/nico/cursour_lighter_bot/lighter-trend-trader
./check_status.sh
```

Or manually:
```bash
railway logs --tail 500 | grep -E "(entering|exiting|indicators computed|signal)"
```

## What to Look For

### ✅ Good Signs:
- `indicators computed` - Bot has enough data and is computing indicators
- `entering position` - Signals are being generated and trades executed
- `exiting position` - Trades are closing (check PnL in logs)
- `DRY RUN: would place` - Simulated trades (safe testing)

### ⚠️ Issues:
- `collecting candles: X/21` - Still waiting for data (should be done by morning)
- `failed to fetch candles: 404` - API issue (expected, WS candles work)
- `no trading client` - Only an issue if not in dry-run mode

## Expected Timeline

With 15-second candles:
- **21 candles needed** = ~5.25 minutes
- Bot should be fully operational within 10 minutes of startup
- By morning, should have hours of trading data

## Key Metrics to Check

1. **Signal Generation**: Look for `entering position` logs
2. **Trade Frequency**: Count entries/exits
3. **PnL**: Check `simulated PnL` in exit logs (dry-run mode)
4. **Indicators**: Look for `indicators computed` with RSI/BB values

## If Bot Needs Restart

```bash
cd /Users/nico/cursour_lighter_bot/lighter-trend-trader
railway redeploy
```

## Current Configuration

- **Timeframe**: 15 seconds (fastest iteration)
- **Mode**: Dry-run (safe testing)
- **Market**: SOL (market:2)
- **Strategy**: Mean reversion (Bollinger Bands + RSI)

## Next Steps After Review

1. Review signal quality - are entries making sense?
2. Check win rate from PnL logs
3. Adjust parameters if needed (RSI thresholds, volatility filters)
4. Consider going live if performance looks good

