# Master Context Document - Lighter Trend Trader

**Last Updated:** 2025-11-18 (Renko optimizations implemented, brick persistence working, database persistence fixed, entry filters relaxed for data collection)
**Purpose:** This document contains all critical context needed to understand and work with this project when context is lost.

---

## Project Overview

**Repository:** `lighter-trend-trader`
**Purpose:** Dual-strategy trading bot for SOL on Lighter.xyz exchange
**Deployment:** Railway (auto-deploys from GitHub)
**Language:** Python 3.11
**Trading Mode:** LIVE TRADING (ultra-selective, quality over quantity - 1-3 trades/day target)
**Account:** `281474976639501` (Account #2, separate from market maker bot at 366110)
**API Key Index:** `16`

### Key Infrastructure
- **WebSocket Price Feed:** Real-time price updates from `wss://mainnet.zklighter.elliot.ai/stream`
- **Trading Client:** Uses Lighter.xyz API for order execution
- **State Store:** Tracks current market prices and positions
- **Logging:** Stdout for Railway, local files for development

---

## Three Trading Strategies

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
- Take profit: 4.5 bps (increased from 3.0 for better R:R)
- Stop loss: 9.0 bps (widened from 6.0 to reduce premature stops)
- Time stop: 8 minutes max hold (increased from 5 to reduce time stops)
- Trend reversal: RSI crosses opposite direction (long exits if RSI < 50)

**Key Parameters:**
- `rsi_bullish_threshold: 50.0` (RSI > 50 + 15 = 65 for longs)
- `rsi_bearish_threshold: 50.0` (RSI < 50 - 15 = 35 for shorts)
- `rsi_momentum_strength: 15.0` (RSI must be 15 points from 50 - increased from 10.0 for better win rate)
- `bb_position_threshold: 0.3` (Price within 30% of BB middle)
- `trend_confirmation_bps: 2.0` (Min EMA divergence for trend)
- `candle_interval_seconds: 15` (15-second candles)

**Adaptive Trading Features (NEW):**
- **Volatility-Based Adjustments:**
  - High volatility (>8 bps): Widen stops by 20%, widen TP by 10%
  - Low volatility (<2 bps): Tighten stops by 10%, reduce position size by 30%
  - Optimal volatility (3-6 bps): Full size and normal stops
- **Losing Streak Protection:**
  - Pause trading for 5 minutes after 3 consecutive losses
  - Reduce position size by 20% after 2+ losses
  - Skip trades in low volatility conditions during losing streaks
- **Dynamic Position Sizing:**
  - Low volatility: 30% size reduction
  - After losing streak: 20% size reduction
  - Optimal conditions: Full size

**Performance Notes:**
- Originally mean reversion (fading extremes) - struggled in trending markets
- Converted to trend following to trade WITH momentum
- Works best in trending markets

---

### 2. Renko + AO Strategy (Divergence/Mean Reversion)
**File:** `modules/renko_ao_trader.py`
**Type:** Counter-Trend (trades AGAINST the trend on divergences)
**Status:** Active, trading (filters relaxed for data collection)

**Entry Conditions (Relaxed for Data Collection - 2025-11-18):**
- **Bullish Divergence:** Price makes lower low, AO makes higher low → Long
- **Bearish Divergence:** Price makes higher high, AO makes lower high → Short
- Divergence strength must be ≥ 0.05 (relaxed from 0.08 for data collection)
- AO strength must be ≥ 0.10 (relaxed from 0.15 for data collection)
- BB enhancement is OPTIONAL (not required) - tracked for analytics
- ATR range: 2-12 bps (relaxed from 3-8 bps)
- At least 3 bricks since divergence (relaxed from 4)

**Key Parameters (Optimized - 2025-11-18):**
- `renko_atr_multiplier: 1.3` (30% larger bricks for stronger signals, up from 1.0)
- `renko_lookback: 30` (increased from 20 for better pattern detection)
- `min_divergence_strength: 0.05` (relaxed from 0.08 for data collection)
- `min_ao_strength: 0.10` (relaxed from 0.15 for data collection)
- `bb_enhancement_threshold: 0.4` (relaxed from 0.3, now optional)
- `min_bricks_since_divergence: 3` (relaxed from 4 for faster entries)
- `optimal_atr_min_bps: 2.0` (relaxed from 3.0)
- `optimal_atr_max_bps: 12.0` (relaxed from 8.0)

**Exit Conditions:**
- Take profit: 12.0 bps (increased from 10.0 for better R:R)
- Stop loss: 8.0 bps (widened from 5.0 to reduce premature stops)
- Time stop: 8 minutes max hold (increased from 5 to reduce time stops)
- AO reversal: Exit if AO trend reverses

**Adaptive Trading Features (NEW):**
- **Losing Streak Protection:**
  - Pause trading for 5 minutes after 3 consecutive losses
  - Reset losing streak counter on win

**Key Parameters:**
- `renko_atr_period: 14` (ATR period for brick sizing)
- `renko_atr_multiplier: 1.0` (Brick size = ATR × multiplier)
- `renko_lookback: 20` (Bricks to look back for divergence)
- `ao_fast_period: 5` (Fast SMA for AO)
- `ao_slow_period: 34` (Slow SMA for AO)
- `min_divergence_strength: 0.05` (Lowered from 0.3 to generate more signals)
- `bb_enhancement_threshold: 0.3` (Relaxed from 0.2 to 0.3 for more signals)

**Technical Details:**
- **Renko Bricks:** ATR-based sizing (adapts to volatility)
- **Brick Formation:** New brick when price moves ≥ 1 ATR
- **ATR Calculation:** Uses price changes (mid prices from WebSocket)
- **Divergence Detection:** Compares price extremes with AO trends

**Performance Notes:**
- Needs 34+ bricks before indicators compute
- Divergences detected but often too weak (< 0.3 threshold)
- Waiting for stronger divergence setups

### 3. Breakout + Momentum Strategy (NEW)
**File:** `modules/breakout_trader.py`
**Type:** Breakout + Momentum (catches explosive moves)
**Status:** Implemented, ready for testing
**Account:** `281474976639273` (Account #2, separate from other strategies)
**API Key Index:** `17`

**Entry Conditions:**
- **Long:** Price breaks above recent high (30-candle lookback) + RSI >60 + MACD bullish + ATR expanding + EMA 20 > EMA 50
- **Short:** Price breaks below recent low (30-candle lookback) + RSI <40 + MACD bearish + ATR expanding + EMA 20 < EMA 50
- Volatility 3-15 bps (sweet spot)
- Candle must close above/below breakout level (confirmation)

**Exit Conditions:**
- Take profit: 2.5x ATR from entry
- Trailing stop: After 1x ATR profit, trail by 0.5x ATR
- Breakout failure: Price closes back below/above breakout level (immediate exit)
- Stop loss: 1.5x ATR below/above breakout level
- Time stop: 60 minutes max hold
- No movement: Exit if no progress after 30 minutes

**Key Parameters:**
- `candle_interval_seconds: 900` (15 minutes - good for breakouts)
- `breakout_lookback: 30` (30 candles to find recent high/low)
- `rsi_bullish_threshold: 60.0` (RSI >60 for longs)
- `rsi_bearish_threshold: 40.0` (RSI <40 for shorts)
- `atr_min_bps: 3.0` (Minimum volatility)
- `atr_max_bps: 15.0` (Maximum volatility)
- `take_profit_atr_multiplier: 2.5` (2.5x ATR TP)
- `stop_loss_atr_multiplier: 1.5` (1.5x ATR SL)

**Expected Performance:**
- Trade frequency: 2-5 trades/day
- Win rate target: 55-65%
- R:R target: 2:1-3:1
- PnL target: +0.3-0.8% per day

**Candle Persistence (NEW - 2025-11-17):**
- **Problem Solved**: Previously took 12.5 hours to collect 50 candles after each deploy
- **Solution**: Candles saved to database, automatically recovered on startup
- **Result**: Breakout strategy ready to trade immediately after deploys
- **Implementation**: `CandleTracker` module saves/loads candles from database
- **Status**: ✅ Implemented and active

---

## Configuration System

**Config File:** `config.yaml.example` (template)
**Environment Variables:** Railway uses env vars (see `railway.env.example`)

### Key Config Sections:
1. **API:** Trading credentials (MUST use different account than market maker bot)
2. **WS:** WebSocket URL and auth token
3. **mean_reversion:** RSI + BB strategy settings
4. **renko_ao:** Renko + AO strategy settings
5. **breakout:** Breakout + Momentum strategy settings

### Important Environment Variables:
- `MEAN_REVERSION_ENABLED=true`
- `MEAN_REVERSION_DRY_RUN=false` (LIVE TRADING - tiny sizes)
- `RENKO_AO_ENABLED=true`
- `RENKO_AO_DRY_RUN=false` (live trading)
- `BREAKOUT_ENABLED=true` (enabled)
- `BREAKOUT_DRY_RUN=false` (live trading with small sizes)
- `MEAN_REVERSION_CANDLE_INTERVAL_SECONDS=15`
- `API_KEY_PRIVATE_KEY` (0x...)
- `ACCOUNT_INDEX=281474976639501` (Account #4, separate from market maker bot at 366110)
- `API_KEY_INDEX=16`
- `API_BASE_URL=https://mainnet.zklighter.elliot.ai`
- `PNL_DB_PATH=/tmp/pnl_trades.db` (Persistent trade database)

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
- RSI+BB Strategy: Account `281474976639501` (Account #4), API Key Index `16`
- Renko+AO Strategy: Account `281474976639377` (Account #3), API Key Index `17`
- Breakout Strategy: Account `281474976639273` (Account #2), API Key Index `17`
- All accounts are under the same wallet (`0xE7C753eD56B4258b1a700D9A1732D5bCff179A11`)

**Persistent Storage:**
- **Database**: `/data/pnl_trades.db` (persists across deployments via Railway volume)
- **Railway Volume**: `lighter-trend-trader-volume` mounted at `/data` (500MB)
- **Environment Variable**: `PNL_DB_PATH=/data/pnl_trades.db` (set in Railway)
- **Backups**: `/data/backups/` (hourly, keeps last 10)
- **Backup Config**: Enabled by default (`pnl_backup.enabled: true`)
- **Query Tool**: `scripts/query_pnl.py` for analysis (see Performance Tracking section)
- **⚠️ CRITICAL FIX (2025-11-18):** Previously used `/tmp` which is NOT persistent on Railway. Now uses `/data` volume for true persistence.

**Continuity Across Deploys (CRITICAL - 2025-11-18):**
- **Positions**: Automatically recovered from database on startup (all strategies)
  - RSI+BB, Renko+AO, Breakout all recover positions on startup
  - Bot resumes managing positions immediately after deploy
- **Candles**: Automatically recovered from database on startup (breakout strategy)
  - Previously: 12.5 hours to collect 50 candles after each deploy
  - Now: Candles loaded instantly, ready to trade immediately
  - Saved on creation/update, loaded on startup
  - ✅ VERIFIED: Tested and confirmed working (4 candles recovered on deploy)
- **Renko Bricks & Price History**: Automatically recovered from database on startup (renko_ao strategy)
  - Previously: Lost on deploy, need to rebuild 20-30 bricks (takes hours)
  - Now: Bricks and price history loaded instantly, ready to trade immediately
  - Saved on brick creation, price history saved every 100 prices
  - ✅ VERIFIED: Tested and confirmed working (800 price points recovered on deploy)
- **Trades**: All trades saved to database for historical analysis
  - Every closed position automatically recorded
  - Persists across deploys for PnL analysis
- **Trade Context**: (To be implemented) Enhanced analytics for all strategies
  - Entry conditions, market context, MFE/MAE, exit quality
  - Enables pattern analysis and optimization
- **No Data Loss**: Everything persists across deploys - bot picks up exactly where it left off
- **Principle**: From now on, all new features must have continuity - nothing should reset on deploy

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
- ✅ Adaptive trading features active (volatility-based adjustments, losing streak pauses)
- 📊 Recent performance: 4 trades, 3W/1L, -0.01% net (75% win rate)
- 📊 Average win: +0.0133%, Average loss: -0.0500%

### Renko + AO Strategy
- ✅ Running and computing indicators
- ✅ Bricks forming correctly with ATR-based sizing (1.3x multiplier)
- ✅ Brick and price history persistence working (recovered on deploy)
- ✅ Adaptive trading features active (losing streak pauses)
- ✅ Entry filters relaxed for data collection (2025-11-18)
  - Divergence: 0.08 → 0.05 (37% more lenient)
  - AO strength: 0.15 → 0.10 (33% more lenient)
  - BB enhancement: Now OPTIONAL (was required)
  - ATR range: 3-8bps → 2-12bps (wider)
  - Bricks since divergence: 4 → 3 (faster entries)
- 📊 Recent performance: 2 trades, 2W/0L, +0.06% net (100% win rate)
- 📊 Average win: +0.0300%

### Known Issues
1. **REST API 404s:** Candle fetching often fails, but fallback (WebSocket) works
2. **Volume Data:** Not available from WebSocket, volume filter skipped if volume = 0

### Recent Changes (2025-11-18)

**1. Renko Strategy Optimizations:**
- Brick size: 1.0 → 1.3 (30% larger for stronger signals)
- Lookback: 20 → 30 bricks (better pattern detection)
- Divergence threshold: 0.08 → 0.05 (relaxed for data collection)
- Confirmation: 4 → 3 bricks (faster entries)

**2. Renko Persistence (Implemented & Verified):**
- Renko bricks saved to database on creation
- Price history saved every 100 prices
- Both recovered on startup (verified working)
- No more data loss on deploy

**3. Database Persistence Fix (Critical):**
- **Problem:** Database was using `/tmp` which is NOT persistent on Railway
- **Solution:** Created Railway volume at `/data`, set `PNL_DB_PATH=/data/pnl_trades.db`
- **Result:** All data (trades, positions, candles, bricks) now persists across deploys
- **Verification:** Tested and confirmed - candles and price history recovered successfully

**4. Entry Filters Relaxed for Data Collection:**
- Goal: Gather more trade data to analyze what works
- Changes: All filters relaxed (see Renko + AO Strategy section above)
- Expected: 2-3x more trades for data analysis
- Future: Will tighten filters based on data analysis results

### Recent Optimizations (2025-11-15)
1. **Parameter Tweaks Based on PnL Analysis:**
   - RSI momentum strength: 10.0 → 15.0 (tighter entries, better win rate)
   - RSI+BB take profit: 3.0 → 4.5 bps (better R:R)
   - RSI+BB stop loss: 6.0 → 9.0 bps (reduce premature stops)
   - Renko+AO take profit: 10.0 → 12.0 bps (better R:R)
   - Renko+AO stop loss: 5.0 → 8.0 bps (reduce premature stops)
   - Max hold time: 5 → 8 minutes (both strategies, reduce time stops)

2. **Adaptive Trading Features Added:**
   - Volatility-based stop loss/take profit adjustments
   - Volatility-based position sizing (reduce size in low vol)
   - Losing streak detection and automatic pause (5 min after 3 losses)
   - Dynamic position sizing based on market conditions
   - Enhanced entry filters (skip low vol trades during losing streaks)

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

### Database System (SQLite)

**Architecture:**
- **Single Database File**: `pnl_trades.db` (one file, three tables)
- **Storage**: SQLite with WAL mode (Write-Ahead Logging for better concurrency)
- **Location**: Auto-detects persistent path (`/data`, `/persist`, `/tmp`, or local)
- **Railway**: Uses `/tmp/pnl_trades.db` (set via `PNL_DB_PATH` env var)
- **Performance**: <10ms queries, <1ms writes, handles 100k+ trades efficiently

**Three Tables in One Database:**

1. **`trades`** - Completed trade records
   - Stores: strategy, side, entry/exit prices, PnL %, size, timestamps, exit reason, market
   - Purpose: Historical PnL analysis, performance tracking
   - Auto-recorded: Every closed position automatically saved

2. **`positions`** - Open position state
   - Stores: strategy, market, side, entry_price, size, stop_loss, take_profit, entry_time, scaled_entries
   - Purpose: Recover positions after deploys (all strategies)
   - Auto-recovered: Loaded on startup, bot resumes managing positions

3. **`candles`** - OHLCV candle data
   - Stores: strategy, market, open_time, open, high, low, close, volume
   - Purpose: Recover candle history after deploys (breakout strategy)
   - Auto-recovered: Loaded on startup, no more 12.5-hour wait after deploys

**How It Works:**
- **WAL Mode**: Changes written to log first, then committed (allows concurrent reads)
- **Transactions**: Each write is atomic (all-or-nothing, rollback on failure)
- **Indexes**: Fast lookups on strategy, market, timestamps
- **Persistence**: Data written to disk immediately, survives container restarts

**ELI5 Explanation:**
- Database = One filing cabinet (`pnl_trades.db`)
- Three drawers = Three tables (trades, positions, candles)
- Memory = Your desk (cleared on restart)
- Database = Filing cabinet (permanent, survives restarts)
- On deploy: Bot opens filing cabinet, reads what it saved, continues where it left off

**Persistent Storage:**
- **Database Path**: `/tmp/pnl_trades.db` (Railway) - persists across deployments
- **Backups**: Automatic hourly backups to `/tmp/backups/` (keeps last 10)
- **Backup Config**: Enabled by default in `config.yaml` (`pnl_backup.enabled: true`)
- **Backup Interval**: 3600 seconds (1 hour)
- **Backup Methods Supported**: Local, S3, Webhook (see `PERSISTENT_STORAGE.md`)

**See `DATABASE_EXPLANATION.md` for full technical details and ELI5 explanation.**

**Query PnL Statistics:**
```bash
# All-time stats
python scripts/query_pnl.py

# By strategy
python scripts/query_pnl.py --strategy mean_reversion
python scripts/query_pnl.py --strategy renko_ao
python scripts/query_pnl.py --strategy breakout

# Time-based filtering
python scripts/query_pnl.py --since 24h  # Last 24 hours
python scripts/query_pnl.py --since 7d   # Last 7 days
python scripts/query_pnl.py --since 30d  # Last 30 days

# Recent trades
python scripts/query_pnl.py --recent 50

# Export to CSV/JSON
python scripts/query_pnl.py --export csv --output trades.csv
python scripts/query_pnl.py --export json --output trades.json
```

**Returns:**
- Total trades, wins, losses, win rate
- Total PnL (%), Total PnL (USD)
- Average PnL, average win, average loss
- R:R ratio (risk/reward)
- Best/worst trades
- Breakdown by strategy and exit reason
- Recent trade history with timestamps

**Database Schema:**
- `id`: Auto-increment primary key
- `strategy`: mean_reversion, renko_ao, or breakout
- `side`: long or short
- `entry_price`, `exit_price`: Prices
- `size`: Position size in SOL
- `pnl_pct`: Profit/loss percentage
- `pnl_usd`: Approximate USD value
- `entry_time`, `exit_time`: Unix timestamps
- `exit_reason`: take_profit, stop_loss, time_stop, etc.
- `market`: market:2 (SOL)
- `created_at`: Record creation timestamp

**Indexes:** Fast queries on strategy, exit_time, market, pnl_pct

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

## Performance Metrics (Current)

**Overall Performance (Last 6 Trades):**
- Total Trades: 6
- Win Rate: 83.3% (5W/1L)
- Total PnL: +0.05%
- Average PnL per Trade: +0.0083%
- Risk/Reward Ratio: 0.40:1 (needs improvement - wins are small)

**By Strategy:**
- **RSI + BB:** 4 trades, 75% win rate, -0.01% net (small sample)
- **Renko + AO:** 2 trades, 100% win rate, +0.06% net

**By Exit Reason:**
- Time stop: 3 trades, 100% win rate, +0.06% total
- AO reversal: 1 trade, 100% win rate, +0.02%
- Trend reversal: 1 trade, 100% win rate, +0.02%
- Stop loss: 1 trade, 0% win rate, -0.05%

**Key Observations:**
- High win rate but small average wins (0.02% vs 0.05% average loss)
- Risk/Reward ratio needs improvement (currently 0.40:1, target >1.0)
- Time stops are working well (100% win rate)
- Stop losses are the main source of losses

## Future Optimization Areas

1. **Risk/Reward Improvement:** Consider wider take profits or tighter stop losses to improve R:R
2. **Entry Quality:** Further tighten entry conditions to improve average win size
3. **Exit Optimization:** Trailing stops or partial profit taking
4. **Market Condition Detection:** Better detection of trending vs choppy markets

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
  - Defaults: `min=0.1`, `max=0.1` SOL (meets Lighter minimum notional requirement ~$14)
  - Adaptive sizing: Reduces by 30% in low vol, 20% after losing streak
- **Base Scale**: 1000 (1 SOL = 1000 base units) - configured in code, can override via `BASE_SCALE` env var
- **PnL Tracking**: Database-backed (`/data/pnl_trades.db`) for high-volume scalability
- **Persistent Storage**: Railway volume at `/data` (preferred), fallback to `/persist` or `/tmp` (with warning)
- **Backups**: Automatic hourly backups to `/data/backups/` (keeps last 10)
- **Railway Volume**: `lighter-trend-trader-volume` (500MB) mounted at `/data`
- **Query Tool**: `scripts/query_pnl.py` for analysis (see Performance Tracking section)

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

## Deep Dive Optimization (2025-11-16)

### Goal
**Quality over quantity**: Even 1 trade/day is acceptable if highly profitable. Ultra-selective approach targeting >70% win rate.

### Current Status
- **Overall Performance**: 33.3% win rate, -0.28% PnL (needs improvement)
- **RSI+BB**: 40% WR, R:R 1.18:1, -0.21% PnL
- **Renko+AO**: 25% WR, R:R 2.10:1, -0.07% PnL

### Optimization Strategy
1. **Ultra-Selective Entry Filters** (implemented)
   - RSI+BB: RSI >70 (long) or <30 (short), BB 0.2-0.3 or 0.7-0.8, Vol 3-8 bps, EMA divergence >5 bps
   - Renko+AO: Divergence >0.1, BB <0.2 or >0.8, AO >0.15 or <-0.15, ATR 3-8 bps

2. **Enhanced Logging** (implemented)
   - Comprehensive entry/exit condition logging
   - MFE/MAE tracking
   - Market context capture

3. **Exit Optimization** (implemented)
   - Wider stops (10 bps) for high-probability setups
   - Trailing stops for winners
   - Optimized time stops

4. **Data Collection** (ongoing)
   - Collecting comprehensive trade data
   - Pattern analysis to identify best setups
   - Iterative refinement

### Expected Outcomes
- **Trade Frequency**: 1-3 trades/day (down from 10+)
- **Win Rate Target**: >70% (up from 33%)
- **R:R Target**: >2:1 (maintain current)
- **PnL Target**: >0.5% per day

See `DEEP_DIVE_PLAN.md` for full details.

---

---

## Self-Learning Infrastructure (2025-11-17) - **FUTURE TODO**

### Status: 📋 **Planned, Not Yet Implemented**

### Goal
Build a system that **keeps learning until we achieve profitability** through automated data collection, performance analysis, and parameter optimization.

### Current Infrastructure ✅ (Already Built)
1. **Deploy Continuity**: Positions, candles, bricks persist across deploys
2. **Data Storage**: Trades, trade context, positions in database
3. **Performance Tracking**: PnL tracker with query tools

### Planned Infrastructure (To Be Implemented)

**Phase 1: Essential (High Priority)**
1. **Parameter History Tracking** - Track all parameter changes and link to performance
2. **Performance Monitoring** - Automated checks, alerts on degradation, trend tracking

**Phase 2: Helpful (Medium Priority)**
3. **Automated Analysis** - Daily insights, setup performance, recommendations
4. **Experiment Tracking** - A/B testing, compare configurations

**Phase 3: Advanced (Future)**
5. **Backtesting** - Test changes on historical data
6. **Automated Optimization** - Self-tuning parameters

### Key Principles
- Keep it simple: Start with essentials, add complexity only if needed
- Data-driven: All decisions based on data
- Iterative: Small changes, measure results, iterate
- Automated: Reduce manual work

### Scheduling Strategy
- **No cron jobs needed initially** - Can be built into main trading loop
- Performance monitoring runs automatically every 6 hours
- Parameter tracking happens automatically on deploy
- See `SCHEDULING_STRATEGY.md` for details

**See `SELF_LEARNING_INFRASTRUCTURE.md` for complete design.**

---

## Recent Analysis & Planning Documents

### 1. Renko Strategy Optimization (`RENKO_OPTIMIZATION_ANALYSIS.md`)
- Analysis of all parameter change recommendations
- Pros/cons of each change
- Data persistence requirements
- Recommended implementation: All parameter changes (brick size 1.3, lookback 30, threshold 0.08, confirmation 4)

### 2. Unified Analytics Design (`UNIFIED_ANALYTICS_DESIGN.md`)
- Enhanced analytics for ALL strategies (RSI+BB, Renko+AO, Breakout)
- Database schema for `trade_context` table
- Strategy-specific entry data tracking
- Common metrics: MFE/MAE, market context, exit quality
- Enables cross-strategy comparison and pattern analysis

### 3. Self-Learning Infrastructure (`SELF_LEARNING_INFRASTRUCTURE.md`)
- Infrastructure needed for automated learning
- Parameter versioning and history
- Performance monitoring and alerts
- Automated analysis and insights
- Experiment tracking for A/B testing

---

**Remember:** When context is lost, read this file first to understand the project structure, strategies, and current state.

