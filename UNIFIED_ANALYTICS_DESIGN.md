# Unified Analytics Design for All Strategies

## Overview

Extend enhanced analytics to **all three strategies** (RSI+BB, Renko+AO, Breakout) to enable:
- Cross-strategy performance comparison
- Pattern analysis across different approaches
- Data-driven optimization for all strategies
- Understanding "what works best" universally

---

## Strategy-Specific Entry Data

### RSI + BB Strategy (Trend Following)
**Entry Conditions:**
- `rsi_value` (float) - RSI at entry
- `bb_position` (float) - BB position 0.0-1.0
- `ema_fast` (float) - Fast EMA value
- `ema_slow` (float) - Slow EMA value
- `ema_trend_strength_bps` (float) - EMA divergence in bps
- `volatility_bps` (float) - Current volatility
- `volume_ratio` (float) - Volume vs average
- `recent_momentum` (string) - "up", "down", "mixed"
- `signal_strength` (float) - 0.0-1.0

### Renko + AO Strategy (Divergence)
**Entry Conditions:**
- `divergence_type` (string) - "bullish" or "bearish"
- `divergence_strength` (float) - 0.0-1.0
- `ao_value` (float) - Awesome Oscillator value
- `bb_position` (float) - BB position 0.0-1.0
- `atr_bps` (float) - ATR in basis points
- `brick_size` (float) - Renko brick size
- `bricks_since_divergence` (int) - Confirmation wait
- `volatility_bps` (float) - Current volatility
- `signal_strength` (float) - 0.0-1.0

### Breakout Strategy (Momentum)
**Entry Conditions:**
- `breakout_type` (string) - "long" or "short"
- `breakout_level` (float) - Price level broken
- `rsi_value` (float) - RSI at entry
- `macd_value` (float) - MACD line
- `macd_signal` (float) - MACD signal line
- `macd_histogram` (float) - MACD histogram
- `atr_expanding` (boolean) - ATR expansion flag
- `ema_fast` (float) - EMA 20 value
- `ema_slow` (float) - EMA 50 value
- `volatility_bps` (float) - Current volatility
- `signal_strength` (float) - 0.0-1.0

---

## Common Data (All Strategies)

### Market Context (All Strategies)
- `volatility_bps` (float) - Market volatility
- `price_trend` (string) - "up", "down", "sideways"
- `volatility_trend` (string) - "increasing", "decreasing", "stable"
- `entry_hour` (int) - 0-23
- `entry_day_of_week` (int) - 0-6 (Monday=0)

### Exit Quality Metrics (All Strategies)
- `mfe_pct` (float) - Maximum Favorable Excursion %
- `mae_pct` (float) - Maximum Adverse Excursion %
- `time_to_mfe_seconds` (float) - How long until best price
- `hold_time_seconds` (float) - Total time in trade
- `reached_tp` (boolean) - Did price reach TP?
- `reached_sl` (boolean) - Did price reach SL?
- `max_profit_pct` (float) - Highest profit reached
- `max_drawdown_pct` (float) - Largest drawdown

---

## Database Schema

### Table: `trade_context`

```sql
CREATE TABLE trade_context (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER NOT NULL,  -- Foreign key to trades table
    strategy TEXT NOT NULL,  -- "mean_reversion", "renko_ao", "breakout"
    
    -- Common: Market Context
    volatility_bps REAL,  -- Market volatility at entry
    price_trend TEXT,  -- "up", "down", "sideways"
    volatility_trend TEXT,  -- "increasing", "decreasing", "stable"
    entry_hour INTEGER,  -- 0-23
    entry_day_of_week INTEGER,  -- 0-6 (Monday=0)
    
    -- Common: Signal Quality
    signal_strength REAL,  -- 0.0-1.0
    
    -- RSI+BB Specific (nullable)
    rsi_value REAL,
    bb_position REAL,  -- 0.0-1.0
    ema_fast REAL,
    ema_slow REAL,
    ema_trend_strength_bps REAL,
    volume_ratio REAL,
    recent_momentum TEXT,  -- "up", "down", "mixed"
    
    -- Renko+AO Specific (nullable)
    divergence_type TEXT,  -- "bullish", "bearish"
    divergence_strength REAL,  -- 0.0-1.0
    ao_value REAL,
    brick_size REAL,
    bricks_since_divergence INTEGER,
    
    -- Breakout Specific (nullable)
    breakout_type TEXT,  -- "long", "short"
    breakout_level REAL,
    macd_value REAL,
    macd_signal REAL,
    macd_histogram REAL,
    atr_expanding BOOLEAN,
    
    -- Common: Exit Quality
    mfe_pct REAL,  -- Maximum favorable excursion %
    mae_pct REAL,  -- Maximum adverse excursion %
    time_to_mfe_seconds REAL,
    hold_time_seconds REAL,
    reached_tp BOOLEAN,
    reached_sl BOOLEAN,
    max_profit_pct REAL,
    max_drawdown_pct REAL,
    
    created_at REAL NOT NULL,
    FOREIGN KEY (trade_id) REFERENCES trades(id)
);

-- Indexes for fast queries
CREATE INDEX idx_trade_context_strategy ON trade_context(strategy);
CREATE INDEX idx_trade_context_trade_id ON trade_context(trade_id);
CREATE INDEX idx_trade_context_entry_hour ON trade_context(entry_hour);
CREATE INDEX idx_trade_context_divergence_type ON trade_context(divergence_type);
CREATE INDEX idx_trade_context_breakout_type ON trade_context(breakout_type);
```

---

## Data Collection Points

### On Entry (All Strategies)
1. **Capture entry conditions** - Store all strategy-specific indicators
2. **Capture market context** - Volatility, trends, time of day
3. **Initialize MFE/MAE tracking** - Start tracking best/worst prices

### During Trade (All Strategies)
1. **Update MFE/MAE** - Track highest profit and largest drawdown
2. **Track price vs TP/SL** - Record if price reaches targets
3. **Update time metrics** - Track time to MFE, total hold time

### On Exit (All Strategies)
1. **Finalize exit quality metrics** - Calculate final MFE/MAE
2. **Record exit context** - Why did we exit? (TP, SL, time, etc.)
3. **Save to database** - Write trade_context record

---

## Analysis Queries We Can Answer

### Cross-Strategy Questions
1. **Which strategy performs best in different market conditions?**
   - High volatility (>10 bps) → Which strategy wins?
   - Low volatility (<3 bps) → Which strategy wins?
   - Trending markets → Which strategy wins?
   - Ranging markets → Which strategy wins?

2. **Time-based performance**
   - Which hours are most profitable for each strategy?
   - Do certain strategies work better at specific times?

3. **Signal quality analysis**
   - Do stronger signals (higher signal_strength) perform better?
   - What's the optimal signal strength threshold?

### RSI+BB Specific
1. **What RSI ranges work best?** (RSI 60-70 vs 70-80)
2. **What BB positions work best?** (<0.3 vs 0.3-0.5)
3. **What EMA divergences work best?** (>5 bps vs >10 bps)
4. **Does recent momentum matter?** (up vs down vs mixed)

### Renko+AO Specific
1. **Which divergence types work best?** (bullish vs bearish)
2. **What divergence strengths work best?** (0.08-0.1 vs 0.15+)
3. **What BB positions work best?** (<0.2 vs >0.8)
4. **What AO values work best?** (strong vs moderate)
5. **How many bricks since divergence is optimal?** (3 vs 4 vs 5)

### Breakout Specific
1. **What breakout types work best?** (long vs short)
2. **What RSI ranges work best?** (>60 vs >70)
3. **Does ATR expansion matter?** (expanding vs not)
4. **What MACD conditions work best?** (strong vs moderate)

### Exit Quality Analysis (All Strategies)
1. **Are we exiting too early?** (MFE vs actual PnL)
2. **Are we exiting too late?** (MAE vs actual PnL)
3. **What's the optimal hold time?** (by strategy, by setup type)
4. **Should we trail stops more aggressively?** (time to MFE analysis)

---

## Implementation Plan

### Phase 1: Database Schema
1. ✅ Create `trade_context` table
2. ✅ Add indexes for fast queries
3. ✅ Migration script (if needed)

### Phase 2: Data Collection Module
1. ✅ Create `TradeContextTracker` class
2. ✅ Methods: `start_trade()`, `update_trade()`, `finish_trade()`
3. ✅ Integrate with existing `PnLTracker`

### Phase 3: Strategy Integration
1. ✅ RSI+BB: Capture entry conditions on `_enter_position`
2. ✅ Renko+AO: Capture entry conditions on `_enter_position`
3. ✅ Breakout: Capture entry conditions on `_enter_position`
4. ✅ All: Track MFE/MAE during position management
5. ✅ All: Record exit quality on `_exit_position`

### Phase 4: Analysis Tools
1. ✅ Create `scripts/analyze_trade_context.py`
2. ✅ Queries for cross-strategy comparison
3. ✅ Queries for pattern analysis
4. ✅ Queries for parameter optimization

---

## Example Analysis Queries

### Find Best Performing Setup Types
```sql
SELECT 
    strategy,
    divergence_type,
    AVG(pnl_pct) as avg_pnl,
    COUNT(*) as trade_count,
    SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate
FROM trades t
JOIN trade_context tc ON t.id = tc.trade_id
WHERE tc.divergence_type IS NOT NULL
GROUP BY strategy, divergence_type
ORDER BY avg_pnl DESC;
```

### Find Optimal Entry Hours
```sql
SELECT 
    strategy,
    entry_hour,
    AVG(pnl_pct) as avg_pnl,
    COUNT(*) as trade_count
FROM trade_context
GROUP BY strategy, entry_hour
ORDER BY avg_pnl DESC;
```

### MFE/MAE Analysis (Are We Exiting Too Early?)
```sql
SELECT 
    strategy,
    AVG(mfe_pct) as avg_mfe,
    AVG(pnl_pct) as avg_actual_pnl,
    AVG(mfe_pct - pnl_pct) as avg_left_on_table
FROM trades t
JOIN trade_context tc ON t.id = tc.trade_id
GROUP BY strategy;
```

---

## Benefits of Unified System

1. **Cross-Strategy Learning**: Understand what works across all strategies
2. **Parameter Optimization**: Data-driven decisions on thresholds
3. **Market Regime Detection**: Know which strategy works in which conditions
4. **Exit Strategy Refinement**: Optimize when to exit based on MFE/MAE
5. **Time-Based Optimization**: Know best trading hours
6. **Pattern Recognition**: Identify winning setups across strategies

---

## Next Steps

1. Design `TradeContextTracker` class
2. Implement database schema
3. Integrate with all three strategies
4. Build analysis tools
5. Start collecting data
6. Iterate based on insights

