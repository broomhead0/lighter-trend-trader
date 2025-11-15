# Master Context Document - Lighter Trend Trader

**Last Updated:** 2025-11-15
**Purpose:** This document contains all critical context needed to understand and work with this project when context is lost.

---

## Project Overview

**Repository:** `lighter-trend-trader`
**Purpose:** Dual-strategy trading bot for SOL on Lighter.xyz exchange
**Deployment:** Railway (auto-deploys from GitHub)
**Language:** Python 3.11
**Trading Mode:** LIVE TRADING (tiny sizes: 0.001-0.005 SOL)
**Account:** `281474976639501` (Account #2, separate from market maker bot at 366110)
**API Key Index:** `16`

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
- `MEAN_REVERSION_DRY_RUN=false` (LIVE TRADING - tiny sizes)
- `RENKO_AO_ENABLED=true`
- `RENKO_AO_DRY_RUN=true` (still in dry-run)
- `MEAN_REVERSION_CANDLE_INTERVAL_SECONDS=15`
- `API_KEY_PRIVATE_KEY` (0x...)
- `ACCOUNT_INDEX=281474976639501` (Account #2, separate from market maker bot at 366110)
- `API_KEY_INDEX=16`
- `API_BASE_URL=https://mainnet.zklighter.elliot.ai`

---

## API Key Setup Process

### How to Set Up API Keys (Fresh Start)

**Script**: `scripts/setup_api_key.py`

This script automates the entire API key setup process based on the official lighter-python example:
- Finds your account(s) using `ETH_PRIVATE_KEY` via `accounts_by_l1_address`
- Generates a new API key using `lighter.create_api_key()`
- Registers it on-chain using `change_api_key()` with wallet signature
- Verifies the API key is working

**Usage**:
```bash
python scripts/setup_api_key.py \
    --eth-private-key 0x<your_wallet_private_key> \
    --api-key-index 16 \
    --account-index 281474976639501  # Optional: will use first account if not provided
```

**What You Need**:
- `ETH_PRIVATE_KEY`: Your Ethereum wallet private key (0x...)
- `API_KEY_INDEX`: Which API key index to create (2-254, we use 16)
- `ACCOUNT_INDEX`: Optional - script will find it if not provided

**Current Configuration**:
- **Account Index**: `281474976639501` (Account #2, separate from market maker bot at 366110)
- **API Key Index**: `16`
- **API Key Private Key**: Generated and registered (stored in Railway)
- **Base URL**: `https://mainnet.zklighter.elliot.ai`

**Important Notes**:
- Account `366110` is the market maker bot account (Account #1)
- Account `281474976639501` is the trend trading account (Account #2)
- The script automatically finds all accounts and lets you choose
- API keys must be registered on-chain via `change_api_key()` transaction
- The wallet private key is required to sign the registration transaction
- API keys are 40 bytes (not standard 32-byte Ethereum keys)

### Testing API Keys

**Script**: `scripts/test_order.py`

Tests that the API key can place and cancel orders:
```bash
python scripts/test_order.py \
    --account-index 281474976639501 \
    --api-key-index 16 \
    --api-key-private-key 0x<your_api_key_private_key>
```

This places a small post-only test order (5% below market, won't fill) and then cancels it.

### Railway Environment Variables

Required variables for live trading:
```
ACCOUNT_INDEX=281474976639501
API_KEY_INDEX=16
API_KEY_PRIVATE_KEY=0x<generated_key>
API_BASE_URL=https://mainnet.zklighter.elliot.ai
```

Set via Railway CLI:
```bash
railway variables --set "ACCOUNT_INDEX=281474976639501" \
                  --set "API_KEY_INDEX=16" \
                  --set "API_KEY_PRIVATE_KEY=0x<key>" \
                  --set "API_BASE_URL=https://mainnet.zklighter.elliot.ai"
```

**Key Resources**:
- API Docs: https://apidocs.lighter.xyz/docs/get-started-for-programmers-1
- Official Example: https://github.com/elliottech/lighter-python/blob/main/examples/system_setup.py
- Official Get Info Example: https://github.com/elliottech/lighter-python/blob/main/examples/get_info.py

---

## Critical Design Decisions

### 1. Account Separation
**⚠️ CRITICAL:** The bot MUST use a different `account_index` than the market maker bot (366110). Using the same account causes order conflicts.

**Current Setup:**
- Market Maker Bot: Account `366110` (Account #1)
- Trend Trading Bot: Account `281474976639501` (Account #2)
- Both accounts are under the same wallet (`0xE7C753eD56B4258b1a700D9A1732D5bCff179A11`)

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

### 6. Strategy Independence & Net Position Reality
**Important:** In perpetual futures, positions NET OUT on the exchange. Strategies track positions internally, but the exchange sees only the NET position.

**How it works:**
- Each strategy maintains its own `_current_position` dict (internal tracking)
- They share the same `trading_client` and same account
- **Positions net out on the exchange:**
  - If RSI+BB goes LONG 0.002 SOL and Renko+AO goes SHORT 0.001 SOL
  - Exchange sees: **NET +0.001 SOL (long)**
  - Not two separate positions - they combine into one net position

**Example scenario:**
- RSI+BB sees bullish momentum → enters LONG 0.002 SOL
- Renko+AO sees bearish divergence → enters SHORT 0.001 SOL
- **Exchange reality:** Account has NET +0.001 SOL (long)
- **Internal tracking:** RSI+BB thinks it's long 0.002, Renko+AO thinks it's short 0.001
- **Risk:** If RSI+BB exits (sells 0.002), it will close the entire net position, affecting Renko+AO's perceived position

**Current Implementation:**
- Strategies track positions internally (`_current_position` dict)
- They don't check actual account position before entering
- **Potential issue:** One strategy's exit could affect the other's perceived position

**Future Improvement Needed:**
- Check actual account position before entering trades
- Consider net position when deciding entry/exit
- Or: Use separate accounts for each strategy (true isolation)

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
├── scripts/
│   ├── setup_api_key.py             # API key setup script
│   ├── test_order.py                # Test order placement script
│   ├── get_pnl.py                   # Query positions/PnL from API (placeholder)
│   └── query_pnl.py                 # Query PnL statistics from database
├── modules/
│   └── pnl_tracker.py               # Database-backed PnL tracker (high volume)
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
3. **Divergence Strength:** Renko strategy needs stronger divergences or lower threshold (lowered to 0.05)

### API Key Status
- ✅ API key generated and registered for account `281474976639501`
- ✅ API key index `16` is active and verified
- ✅ Test order placed and canceled successfully
- ✅ Railway variables configured
- ✅ Bot ready for live trading

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

### PnL Tracker (Database-Backed for High Volume)

**For 100k+ trades, we use a database-backed PnL tracker:**
- **Storage**: SQLite with WAL mode (can handle millions of trades)
- **Location**: `pnl_trades.db` (or set `PNL_DB_PATH` env var)
- **Performance**: <10ms queries, <1ms writes
- **Features**: Per-strategy tracking, time-based filtering, fast aggregation

**Automatic Recording:**
- Every closed position is automatically recorded to the database
- Tracks: strategy, side, entry/exit prices, PnL %, size, timestamps, exit reason
- No performance impact (async, non-blocking)

**Query PnL Statistics:**
```bash
# All-time stats
python scripts/query_pnl.py

# By strategy
python scripts/query_pnl.py --strategy mean_reversion
python scripts/query_pnl.py --strategy renko_ao

# Last 24 hours
python scripts/query_pnl.py --since-hours 24

# Recent trades
python scripts/query_pnl.py --recent 50
```

**Returns:**
- Total trades, wins, losses, win rate
- Total PnL (%), Total PnL (USD)
- Average PnL, average win, average loss
- Best/worst trades
- Recent trade history

### Metrics to Monitor
- **RSI + BB:** Trades, win rate, PnL, RSI levels, BB position
- **Renko + AO:** Bricks formed, divergences detected, AO values, BB position

### Log Analysis
```bash
# Check recent trades
railway logs | grep "entering\|exiting"

# Check live PnL
railway logs | grep "LIVE PnL"

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

# Set Railway variables
railway variables --set "KEY=VALUE" --set "KEY2=VALUE2"

# Setup new API key
python scripts/setup_api_key.py --eth-private-key 0x<key> --api-key-index 16

# Test API key
python scripts/test_order.py --account-index 281474976639501 --api-key-index 16 --api-key-private-key 0x<key>
```

## Quick Reference

- **Repository**: `lighter-trend-trader`
- **Deployment**: Railway (auto-deploy from GitHub)
- **Account**: `281474976639501` (Account #2, separate from market maker bot at 366110)
- **API Key Index**: `16`
- **Strategies**: RSI + BB (trend following), Renko + AO (divergence)
- **Market**: SOL (market:2)
- **Timeframe**: 15 seconds (configurable)
- **Trading Mode**: LIVE (tiny sizes: 0.001-0.002 SOL for $100 account)
- **Lighter Minimum**: 0.001 SOL per order (enforced in code)
- **Position Size Source**: Code defaults (single source of truth in `__init__` methods)
  - Defaults: `min=0.001`, `max=0.002` (can override via config.yaml, env vars removed)
- **Base Scale**: 1000 (1 SOL = 1000 base units) - configured in code, can override via `BASE_SCALE` env var
- **PnL Tracking**: Database-backed (`pnl_trades.db`) for high-volume scalability

---

## Contact & Notes

- **User Preference:** "Don't ask permission, just go for it" - user trusts decisions
- **Testing:** Always start with `dry_run: true`
- **Account Safety:** Always warn if using same account as market maker bot
- **Strategy Philosophy:**
  - RSI + BB = Trend following (ride momentum)
  - Renko + AO = Counter-trend (fade divergences)
- **Strategy Independence:**
  - Strategies can have opposing signals (one long, one short) - this is normal
  - Each manages its own positions independently
  - No conflicts - they can both trade simultaneously

---

**Remember:** When context is lost, read this file first to understand the project structure, strategies, and current state.

