# Testing Guide

## Testing Strategy

**⚠️ ALWAYS test in dry-run mode before live trading!**

## Step 1: Dry-Run Testing (Recommended First)

### Setup

1. **Create config file:**
   ```bash
   cp config.yaml.example config.yaml
   ```

2. **Edit `config.yaml`:**
   ```yaml
   mean_reversion:
     enabled: true
     dry_run: true  # ← CRITICAL: Keep this true for testing
     market: market:2
   ```

3. **Run the bot:**
   ```bash
   export PYTHONPATH=.
   python main.py
   ```

### What to Watch For

- ✅ Bot starts without errors
- ✅ Price feed fetches current prices (check logs for price updates)
- ✅ Candles are fetched successfully
- ✅ Indicators are computed (RSI, Bollinger Bands, etc.)
- ✅ Entry signals are generated (when conditions are met)
- ✅ Exit signals work correctly
- ✅ No crashes or errors

### Expected Log Output

```
[INFO] Starting Lighter Trend Trader...
[INFO] Trading client initialized
[INFO] Mean reversion trader initialized
[INFO] Price feed initialized
[price_feed] market:2 price: 153.45
[mean_reversion] fetched 100 candles
[mean_reversion] DRY RUN: would place bid order  # When signal triggers
```

## Step 2: Monitor Signal Generation

Watch for entry signals in the logs. The bot will log:
- When it checks for signals
- When entry conditions are met
- What signals it would execute (in dry-run)

### Test Scenarios

1. **No signals** - Normal when market conditions don't meet criteria
2. **Long signal** - Price near lower BB + RSI < 30
3. **Short signal** - Price near upper BB + RSI > 70
4. **Exit signals** - Take profit, stop loss, time stop

## Step 3: Paper Trading (Optional)

If you want to test with real market data but fake orders:

1. Keep `dry_run: true`
2. Monitor what trades it would make
3. Track hypothetical PnL manually
4. Verify signals make sense

## Step 4: Live Trading (Only After Thorough Testing)

### Prerequisites

- ✅ Dry-run tested for at least 24-48 hours
- ✅ Signals look reasonable
- ✅ No crashes or errors
- ✅ You understand the strategy
- ✅ You have risk management in place

### Enable Live Trading

1. **Update config:**
   ```yaml
   mean_reversion:
     enabled: true
     dry_run: false  # ← Enable live trading
   ```

2. **Start with small position sizes:**
   ```yaml
   mean_reversion:
     max_position_size: 0.01  # Start very small
     min_position_size: 0.005
   ```

3. **Monitor closely:**
   - Watch logs in real-time
   - Check for unexpected behavior
   - Verify orders are placed correctly
   - Monitor PnL

## Common Issues & Solutions

### Issue: "No price updates"
**Solution:** Check API base_url is correct, verify network connection

### Issue: "Failed to fetch candles"
**Solution:** Verify market ID is correct (market:2 for SOL), check API endpoint

### Issue: "No signals generated"
**Solution:** This is normal - signals only trigger when all conditions are met. Check:
- Volatility is in range (4-25 bps)
- Price is near Bollinger Bands
- RSI is oversold/overbought
- Volume is above average

### Issue: "Trading client errors"
**Solution:** Verify API credentials are correct in config.yaml

## Performance Monitoring

### Key Metrics to Track

1. **Signal Generation Rate** - How often signals are generated
2. **Win Rate** - % of profitable trades
3. **Average Profit/Loss** - Per trade PnL
4. **Max Drawdown** - Largest losing streak
5. **Sharpe Ratio** - Risk-adjusted returns

### Log Analysis

Grep for key events:
```bash
# Entry signals
grep "entering.*position" logs/*.log

# Exit signals
grep "exiting position" logs/*.log

# Errors
grep "ERROR" logs/*.log
```

## Risk Management Checklist

Before going live:

- [ ] Position sizes are appropriate for your capital
- [ ] Stop loss is set (6 bps default)
- [ ] Take profit is reasonable (3 bps default)
- [ ] Max hold time prevents stuck positions (5 min default)
- [ ] Volatility filters prevent trading in extreme conditions
- [ ] You have a plan to stop the bot if needed
- [ ] You understand the strategy and its limitations

## Recommended Testing Timeline

1. **Day 1-2:** Dry-run testing, verify basic functionality
2. **Day 3-5:** Monitor signal generation, verify logic
3. **Day 6-7:** If signals look good, consider small live test
4. **Week 2+:** Gradually increase position sizes if profitable

## Emergency Stop

If something goes wrong:

1. **Stop the bot:** `Ctrl+C` or `kill <pid>`
2. **Check open positions:** Log into Lighter.xyz dashboard
3. **Manually close positions** if needed
4. **Review logs** to understand what happened

## Next Steps After Testing

Once you're confident:

1. ✅ Optimize parameters based on results
2. ✅ Add telemetry/monitoring (optional)
3. ✅ Set up alerts (optional)
4. ✅ Consider adding more sophisticated risk management
5. ✅ Document your specific configuration

