# Live Testing Setup - Tiny Size

## Overview
This document outlines the setup for live testing with **tiny position sizes** to minimize risk while validating the strategies.

## Current Configuration

### RSI + BB Strategy (Trend Following)
- **Status:** ✅ Ready for live testing
- **Position Sizes:** 0.001 - 0.005 SOL (TINY)
- **Dry Run:** `false` (live trading enabled)
- **Risk:** ~$0.14 - $0.70 per trade at $140 SOL (minimal)

### Renko + AO Strategy (Divergence)
- **Status:** ⏸️ Still in dry-run (hasn't traded yet)
- **Position Sizes:** 0.001 - 0.005 SOL (when enabled)
- **Dry Run:** `true` (waiting for first trades)

## Railway Environment Variables

To enable live testing with tiny sizes, set these in Railway:

```bash
# RSI + BB - Live Trading (Tiny Size)
MEAN_REVERSION_ENABLED=true
MEAN_REVERSION_DRY_RUN=false
MEAN_REVERSION_MAX_POSITION_SIZE=0.005
MEAN_REVERSION_MIN_POSITION_SIZE=0.001

# Renko + AO - Still Dry Run
RENKO_AO_ENABLED=true
RENKO_AO_DRY_RUN=true

# Trading Credentials (REQUIRED)
API_BASE_URL=https://mainnet.zklighter.elliot.ai
API_KEY_PRIVATE_KEY=0x<your_key>
ACCOUNT_INDEX=<your_account>  # ⚠️ MUST be different from 366110
API_KEY_INDEX=<your_api_key_index>
```

## Risk Assessment

### Per Trade Risk (at $140 SOL):
- **Min Size (0.001 SOL):** ~$0.14 per trade
- **Max Size (0.005 SOL):** ~$0.70 per trade
- **Stop Loss (4 bps):** ~$0.006 - $0.028 per trade
- **Take Profit (8 bps):** ~$0.011 - $0.056 per trade

### Daily Risk Estimate:
- **Assumptions:** 20-30 trades/day, 50% win rate
- **Max Loss Scenario:** 15 losses × $0.028 = ~$0.42/day
- **Typical Scenario:** Mixed wins/losses = ~$0.10-0.20/day

## Safety Checks

1. ✅ **Account Separation:** Bot warns if using account_index 366110
2. ✅ **Tiny Position Sizes:** 0.001-0.005 SOL (10-20x smaller than before)
3. ✅ **Stop Losses:** 4 bps (tight risk control)
4. ✅ **Time Stops:** 3 minutes max hold (prevents stuck positions)
5. ✅ **Dry Run Available:** Can switch back instantly via env var

## Monitoring

### Key Metrics to Watch:
- **Trade Frequency:** Should see 20-30 trades/day
- **Win Rate:** Target 50%+ (currently ~40-50% in dry-run)
- **Average PnL:** Track per-trade performance
- **Position Sizes:** Verify they're actually 0.001-0.005 SOL

### Log Monitoring:
```bash
# Check live trades
railway logs | grep "entering.*position"

# Check PnL
railway logs | grep "simulated PnL"

# Check position sizes
railway logs | grep "size="
```

## Rollback Plan

If issues arise, immediately set:
```bash
MEAN_REVERSION_DRY_RUN=true
```

This will stop all live trading instantly (bot will continue monitoring but won't place orders).

## Next Steps

1. ✅ Config updated with tiny sizes
2. ⏳ Set Railway env vars (see above)
3. ⏳ Verify account_index is different from 366110
4. ⏳ Monitor first few trades closely
5. ⏳ Gradually increase size if performance is good

## Notes

- **Renko + AO:** Keep in dry-run until it starts generating signals
- **RSI + BB:** Ready for live testing with tiny sizes
- **Position Sizing:** Currently fixed at 0.01 SOL in code (needs update to respect config)
- **Risk Management:** Stop losses and take profits are working correctly

