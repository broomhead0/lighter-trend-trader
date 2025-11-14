# Log Analysis Guide

## Bot is Running! 📊

The bot is now running in the background and logging everything to `logs/bot_*.log`.

## Quick Commands

### Check Status
```bash
./check_status.sh
```

### View Live Logs
```bash
tail -f logs/bot_*.log
```

### Analyze Logs (After a Few Hours)
```bash
python analyze_logs.py
```

## What the Analysis Script Shows

After running `python analyze_logs.py`, you'll see:

1. **Price Updates** - How many price updates received, price range
2. **Candle Fetches** - How many candles fetched, average per fetch
3. **Signals Generated** - Entry signals that were triggered
4. **Entries** - Actual position entries (long/short breakdown)
5. **Exits** - Position exits by reason (take_profit, stop_loss, time_stop, etc.)
6. **Errors** - Any errors or exceptions

## Key Metrics to Look For

### ✅ Good Signs
- Regular price updates (every 5 seconds)
- Successful candle fetches (every minute)
- No errors
- Signals generated when conditions are met

### ⚠️ Things to Watch
- API errors (404, timeout, etc.) - may need endpoint fix
- No signals for days - normal if market conditions don't align
- Frequent errors - indicates a problem

## After a Few Hours

Run the analysis:
```bash
python analyze_logs.py
```

This will show you:
- How the bot performed
- What signals were generated
- Any issues that occurred
- Whether the strategy is working as expected

## Next Steps After Analysis

1. **If signals look good** - Continue monitoring, consider live trading
2. **If no signals** - This is normal! Strategy is selective by design
3. **If errors** - Check API connectivity, fix issues
4. **If signals seem wrong** - Review strategy parameters in config.yaml

