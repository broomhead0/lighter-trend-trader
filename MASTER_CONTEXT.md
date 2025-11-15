# Master Context Document - Lighter Trend Trader

**Last Updated:** 2025-11-14
**Purpose:** This document contains all critical context needed to understand and work with this project when context is lost.

---

## Project Overview

**Repository:** `lighter-trend-trader`
**Purpose:** Dual-strategy trading bot for SOL on Lighter.xyz exchange
**Deployment:** Railway (auto-deploys from GitHub)
**Language:** Python 3.11
**Trading Mode:** Currently DRY RUN (simulation only)

### Key Infrastructure
- **WebSocket Price Feed:** Real-time price updates from `wss://mainnet.zklighter.elliot.ai/stream`
- **Trading Client:** Uses Lighter.xyz API for order execution
- **State Store:** Tracks current market prices and positions
- **Logging:** Stdout for Railway, local files for development

---

## Two Trading Strategies

### 1. RSI + BB Strategy (Trend Following)
**File:** `modules/mean_reversion_trader.py`
**Type:** Trend Following (trades WITH the trend)
**Status:** Active, trading

**Entry Conditions:**
- **Long:** RSI > 60 (bullish momentum) + Price near/above BB middle + EMA fast > EMA slow
- **Short:** RSI < 40 (bearish momentum) + Price near/below BB middle + EMA fast < EMA slow
- Volume must be above average
- Volatility between 2-25 bps

**Exit Conditions:**
- Take profit: 8 bps
- Stop loss: 4 bps
- Time stop: 3 minutes max hold
- Trend reversal: RSI crosses opposite direction (long exits if RSI < 50)

**Key Parameters:**
- `rsi_bullish_threshold: 50.0` (RSI > 50 + 10 = 60 for longs)
- `rsi_bearish_threshold: 50.0` (RSI < 50 - 10 = 40 for shorts)
- `rsi_momentum_strength: 10.0` (RSI must be 10 points from 50)
- `bb_position_threshold: 0.3` (Price within 30% of BB middle)
- `trend_confirmation_bps: 2.0` (Min EMA divergence for trend)
- `candle_interval_seconds: 15` (15-second candles)

**Performance Notes:**
- Originally mean reversion (fading extremes) - struggled in trending markets
- Converted to trend following to trade WITH momentum
- Works best in trending markets

---

### 2. Renko + AO Strategy (Divergence/Mean Reversion)
**File:** `modules/renko_ao_trader.py`
**Type:** Counter-Trend (trades AGAINST the trend on divergences)
**Status:** Active, monitoring (no trades yet)

**Entry Conditions:**
- **Bullish Divergence:** Price makes lower low, AO makes higher low → Long
- **Bearish Divergence:** Price makes higher high, AO makes lower high → Short
- Divergence strength must be ≥ 0.3 (0.0 to 1.0 scale)
- Enhanced signal if divergence occurs near Bollinger Bands (within 20% of edge)

**Exit Conditions:**
- Take profit: 10 bps
- Stop loss: 5 bps
- Time stop: 5 minutes max hold
- AO reversal: Exit if AO trend reverses

**Key Parameters:**
- `renko_atr_period: 14` (ATR period for brick sizing)
- `renko_atr_multiplier: 1.0` (Brick size = ATR × multiplier)
- `renko_lookback: 20` (Bricks to look back for divergence)
- `ao_fast_period: 5` (Fast SMA for AO)
- `ao_slow_period: 34` (Slow SMA for AO)
- `min_divergence_strength: 0.3` (Minimum divergence strength to trade)
- `bb_enhancement_threshold: 0.2` (Within 20% of BB edge for enhancement)

**Technical Details:**
- **Renko Bricks:** ATR-based sizing (adapts to volatility)
- **Brick Formation:** New brick when price moves ≥ 1 ATR
- **ATR Calculation:** Uses price changes (mid prices from WebSocket)
- **Divergence Detection:** Compares price extremes with AO trends

**Performance Notes:**
- Needs 34+ bricks before indicators compute
- Divergences detected but often too weak (< 0.3 threshold)
- Waiting for stronger divergence setups

---

## Configuration System

**Config File:** `config.yaml.example` (template)
**Environment Variables:** Railway uses env vars (see `railway.env.example`)

### Key Config Sections:
1. **API:** Trading credentials (MUST use different account than market maker bot)
2. **WS:** WebSocket URL and auth token
3. **mean_reversion:** RSI + BB strategy settings
4. **renko_ao:** Renko + AO strategy settings

### Important Environment Variables:
- `MEAN_REVERSION_ENABLED=true`
- `MEAN_REVERSION_DRY_RUN=true` (set to false for live trading)
- `RENKO_AO_ENABLED=true`
- `RENKO_AO_DRY_RUN=true`
- `MEAN_REVERSION_CANDLE_INTERVAL_SECONDS=15`
- `API_KEY_PRIVATE_KEY` (0x...)
- `ACCOUNT_INDEX` (MUST be different from 366110 - market maker bot)

---

## Critical Design Decisions

### 1. Account Separation
**⚠️ CRITICAL:** The bot MUST use a different `account_index` than the market maker bot (366110). Using the same account causes order conflicts.

**Safety Check:** `main.py` warns if account_index == 366110

### 2. Candle Building
- **Primary:** REST API for historical candles (often returns 404)
- **Fallback:** Build candles from WebSocket price updates
- **Candle Interval:** Configurable (default 15s for RSI + BB)

### 3. Renko Brick Sizing
- **ATR-Based:** Brick size = ATR(14) × multiplier (default 1.0)
- **Dynamic:** Adapts to current volatility
- **Fallback:** 0.1% of price if ATR not available yet

### 4. Logging Strategy
- **Railway:** Logs to stdout only (no local files)
- **Local:** Logs to both stdout and `logs/bot_*.log`
- **Detection:** Checks for `RAILWAY_ENVIRONMENT` or `RAILWAY_PROJECT_ID`

### 5. Parallel Execution
- Both strategies run simultaneously in `main.py`
- Shared WebSocket price feed
- Independent position management
- Log prefixes: `[mean_reversion]` and `[renko_ao]`

---

## Deployment

### Railway Setup
- **Auto-Deploy:** From GitHub main branch
- **Dockerfile:** Python 3.11-slim base
- **Start Command:** `python main.py`
- **Logs:** `railway logs` or Railway dashboard

### Local Development
```bash
# Setup
pip install -r requirements.txt

# Run
python main.py

# Check status
./check_status.sh

# Analyze logs
python analyze_logs.py [log_file]
```

---

## File Structure

```
lighter-trend-trader/
├── main.py                          # Entry point, runs both strategies
├── modules/
│   ├── mean_reversion_trader.py     # RSI + BB (trend following)
│   ├── renko_ao_trader.py           # Renko + AO (divergence)
│   └── ws_price_feed.py             # WebSocket price feed
├── core/
│   ├── state_store.py               # Price/position tracking
│   └── trading_client.py            # Order execution
├── config.yaml.example              # Config template
├── railway.env.example              # Railway env vars template
├── Dockerfile                       # Railway deployment
├── railway.json                     # Railway config
├── analyze_logs.py                  # Log analysis script
├── check_status.sh                  # Status check script
└── MASTER_CONTEXT.md                # This file
```

---

## Current Status & Known Issues

### RSI + BB Strategy
- ✅ Active and trading
- ✅ Trend following logic working
- ⚠️ Recent performance: Mixed (some wins, some losses)
- 📊 Recent trades: 5 trades, 1 win, 4 losses, -0.18% net

### Renko + AO Strategy
- ✅ Running and computing indicators
- ✅ Bricks forming correctly (200+ collected)
- ⚠️ No trades yet - divergences too weak (< 0.3 threshold)
- 📊 Max divergence strength seen: 0.16 (needs 0.3)

### Known Issues
1. **REST API 404s:** Candle fetching often fails, but fallback (WebSocket) works
2. **Volume Data:** Not available from WebSocket, volume filter skipped if volume = 0
3. **Divergence Strength:** Renko strategy needs stronger divergences or lower threshold

---

## Important Code Patterns

### Strategy Initialization
```python
# Both strategies follow same pattern
trader = StrategyTrader(
    config=cfg,
    state=state,
    trading_client=trading_client,
    alert_manager=None,
    telemetry=None,
)
```

### Entry Signal Generation
- Check filters (volatility, volume, trend)
- Compute indicators
- Generate signal with strength (0.0 to 1.0)
- Create signal with risk management (stop loss, take profit)

### Position Management
- Track current position in `_current_position` dict
- Check exits first, then entries
- Dry-run mode simulates without trading client

---

## Performance Tracking

### Metrics to Monitor
- **RSI + BB:** Trades, win rate, PnL, RSI levels, BB position
- **Renko + AO:** Bricks formed, divergences detected, AO values, BB position

### Log Analysis
```bash
# Check recent trades
railway logs | grep "entering\|exiting"

# Check PnL
railway logs | grep "simulated PnL"

# Check indicators
railway logs | grep "indicators computed\|indicators:"
```

---

## Future Optimization Areas

1. **Renko Divergence Threshold:** Consider lowering `min_divergence_strength` from 0.3 to 0.2
2. **RSI + BB Parameters:** May need tuning based on market conditions
3. **Risk Management:** Consider dynamic position sizing based on volatility
4. **Exit Optimization:** Trailing stops or partial profit taking

---

## Quick Reference Commands

```bash
# Check Railway logs
railway logs --tail 500

# Check specific strategy
railway logs | grep "\[mean_reversion\]"  # or "\[renko_ao\]"

# Export logs for analysis
railway logs > logs.txt
python analyze_logs.py logs.txt

# Check deployment status
railway status

# View environment variables
railway variables
```

---

## Contact & Notes

- **User Preference:** "Don't ask permission, just go for it" - user trusts decisions
- **Testing:** Always start with `dry_run: true`
- **Account Safety:** Always warn if using same account as market maker bot
- **Strategy Philosophy:**
  - RSI + BB = Trend following (ride momentum)
  - Renko + AO = Counter-trend (fade divergences)

---

**Remember:** When context is lost, read this file first to understand the project structure, strategies, and current state.

