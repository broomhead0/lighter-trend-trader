# Renko Strategy Optimization Analysis

## Recommendation Analysis: Pros & Cons

### Option 1: Increase Brick Size (ATR Multiplier 1.0 → 1.3-1.5)

**Pros:**
- ✅ **Stronger signals**: Bigger bricks filter out more noise, producing cleaner divergence patterns
- ✅ **Better divergence detection**: Larger price movements = more significant divergences
- ✅ **Moves into optimal range**: Current avg brick size ~2.5 bps → would become ~3.25-3.75 bps (within 3-8 bps optimal)
- ✅ **Reduces false signals**: Less sensitive to minor price fluctuations
- ✅ **Better R:R potential**: Larger moves = better profit potential per trade

**Cons:**
- ⚠️ **Fewer signals**: Will generate fewer trading opportunities (but that's the goal - quality over quantity)
- ⚠️ **Slower brick formation**: Takes longer to form each brick, so divergence detection is slower
- ⚠️ **May miss quick reversals**: Smaller divergences might be filtered out

**Recommendation**: ✅ **DO THIS** - This is the most impactful change

---

### Option 2: Increase Lookback Period (20 → 25-30)

**Pros:**
- ✅ **Better pattern recognition**: More historical context = better divergence detection
- ✅ **Catches longer-term divergences**: Some divergences develop over more bricks
- ✅ **More reliable signals**: More data points = more confidence in patterns

**Cons:**
- ⚠️ **Slower divergence detection**: Takes longer to accumulate enough bricks (need 25-30 vs 20)
- ⚠️ **More memory usage**: Stores more bricks (but we already have maxlen=200, so fine)
- ⚠️ **May miss short-term divergences**: If divergence happens quickly, might miss it

**Recommendation**: ✅ **DO THIS** - But go to 30, not 25 (significant increase as you asked)

**Why 30?**
- Current lookback: 20 bricks
- If we increase brick size (Option 1), each brick represents more price movement
- 30 bricks with bigger bricks = similar time coverage but better pattern quality
- Divergences often develop over 15-25 bricks, so 30 gives good buffer

---

### Option 3: Lower Divergence Threshold (0.1 → 0.08)

**Pros:**
- ✅ **Catches more quality signals**: We're seeing strengths of 0.10, 0.17 - 0.08 would catch the 0.10 ones
- ✅ **Still selective**: 0.08 is still quite selective (not going to 0.05 or lower)
- ✅ **Better signal capture**: Won't miss borderline-strong divergences

**Cons:**
- ⚠️ **Slightly lower quality**: Some 0.08-0.10 divergences might be weaker
- ⚠️ **More trades**: Could increase trade frequency (but still very selective)

**Recommendation**: ✅ **DO THIS** - Small adjustment, good balance

---

### Option 4: Increase Confirmation Wait (3 → 4-5 bricks)

**Pros:**
- ✅ **Higher quality signals**: Longer confirmation = more reliable divergences
- ✅ **Reduces false signals**: Gives divergence more time to develop
- ✅ **Better entry timing**: Enters when divergence is more established

**Cons:**
- ⚠️ **Slower entries**: Takes longer to enter after divergence starts
- ⚠️ **May miss quick reversals**: If price reverts quickly, might miss the move
- ⚠️ **Fewer trades**: Even more selective (but we want quality)

**Recommendation**: ⚠️ **CONSIDER CAREFULLY** - Maybe 4, not 5

**Why 4?**
- 3 bricks might be too quick (current)
- 5 bricks might be too slow (could miss moves)
- 4 bricks is a good middle ground

---

## Combined Impact Analysis

### If We Do ALL Recommendations:

**Combined Effect:**
- Brick size: 1.0 → 1.3 (30% larger bricks)
- Lookback: 20 → 30 (50% more history)
- Threshold: 0.1 → 0.08 (20% more lenient)
- Confirmation: 3 → 4 bricks (33% longer wait)

**Expected Outcomes:**
- ✅ **Stronger signals**: Bigger bricks + longer lookback = better patterns
- ✅ **More quality trades**: Lower threshold + longer confirmation = balanced selectivity
- ✅ **Better win rate**: All changes favor quality over quantity
- ⚠️ **Slower startup**: Need 30 bricks instead of 20 (but with persistence, this is fine)
- ⚠️ **Fewer total trades**: But each trade should be higher quality

**Risk:**
- Might become TOO selective (but that's the goal - 1-3 trades/day is fine)
- Need to monitor if we're getting any trades at all

---

## Data Persistence Requirements

### Current State (Lost on Deploy):
1. **Renko Bricks** (`_renko_bricks: Deque[RenkoBrick]`, maxlen=200)
   - Currently: Lost on deploy, need to rebuild from scratch
   - Impact: Need 20-30 bricks to start trading (could take hours)

2. **Price History** (`_price_history: Deque[float]`, maxlen=1000)
   - Currently: Lost on deploy
   - Impact: Need 14+ prices for ATR calculation

3. **Divergence Tracking** (`_divergence_start_brick: Dict[str, int]`)
   - Currently: Lost on deploy
   - Impact: Minor - just resets divergence tracking

### What We Should Persist:

**1. Renko Bricks (CRITICAL)**
- Store: `RenkoBrick` objects (open_time, open, close, direction, high, low)
- Why: Takes longest to rebuild (20-30 bricks = hours of data)
- Similar to: How we persist candles for breakout strategy

**2. Price History (IMPORTANT)**
- Store: Last 1000 price points (or at least last 50 for ATR)
- Why: Needed for ATR calculation and AO calculation
- Similar to: Price history for indicators

**3. Current Brick Size (NICE TO HAVE)**
- Store: `_current_renko_brick_size`
- Why: Can resume immediately without recalculating ATR

**4. Divergence State (OPTIONAL)**
- Store: `_divergence_start_brick` dict
- Why: Minor - just helps track ongoing divergences

---

## Enhanced Analytics: What Data Should We Track?

### Current Trade Data (in `trades` table):
- Strategy, side, entry/exit prices, PnL, size, timestamps, exit reason

### Missing Critical Data for Refining Edge:

**1. Entry Condition Context (CRITICAL)**
- Divergence type (bullish/bearish)
- Divergence strength (0.0-1.0)
- AO value at entry
- BB position at entry (0.0-1.0)
- ATR at entry (in bps)
- Brick size at entry
- Number of bricks since divergence started
- Volatility at entry (in bps)

**2. Market Context at Entry**
- Recent price trend (up/down/sideways)
- Recent volatility trend (increasing/decreasing)
- Time of day (hour)
- Market regime (trending/ranging)

**3. Exit Quality Metrics**
- MFE (Maximum Favorable Excursion) - highest profit reached
- MAE (Maximum Adverse Excursion) - largest drawdown
- Time to MFE (how long until best price)
- Time to exit (total hold time)
- Did price reach TP before exit?
- Did price reach SL before exit?

**4. Pattern Analysis Data**
- Which divergence types work best? (bullish vs bearish)
- What divergence strengths are most profitable? (0.08-0.1 vs 0.15+)
- What BB positions work best? (<0.2 vs >0.8)
- What AO values work best? (strong vs moderate)
- What ATR ranges work best? (3-5 bps vs 6-8 bps)
- What time of day works best?

**5. Strategy Performance by Setup Type**
- Bullish divergence + lower BB → Win rate? Avg PnL?
- Bearish divergence + upper BB → Win rate? Avg PnL?
- Strong divergence (>0.15) → Win rate? Avg PnL?
- Moderate divergence (0.08-0.15) → Win rate? Avg PnL?

---

## Proposed Database Schema Enhancement

**NOTE: This has been expanded to cover ALL strategies (RSI+BB, Renko+AO, Breakout).**
**See `UNIFIED_ANALYTICS_DESIGN.md` for the complete unified design.**

### New Table: `trade_context` (Unified for All Strategies)

```sql
CREATE TABLE trade_context (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER NOT NULL,  -- Foreign key to trades table
    strategy TEXT NOT NULL,

    -- Entry conditions
    divergence_type TEXT,  -- "bullish" or "bearish"
    divergence_strength REAL,  -- 0.0 to 1.0
    ao_value REAL,  -- Awesome Oscillator value at entry
    bb_position REAL,  -- BB position 0.0-1.0
    atr_bps REAL,  -- ATR in basis points
    brick_size REAL,  -- Renko brick size
    bricks_since_divergence INTEGER,
    volatility_bps REAL,

    -- Market context
    price_trend TEXT,  -- "up", "down", "sideways"
    volatility_trend TEXT,  -- "increasing", "decreasing", "stable"
    entry_hour INTEGER,  -- 0-23

    -- Exit quality
    mfe_pct REAL,  -- Maximum favorable excursion %
    mae_pct REAL,  -- Maximum adverse excursion %
    time_to_mfe_seconds REAL,
    hold_time_seconds REAL,
    reached_tp BOOLEAN,  -- Did price reach TP?
    reached_sl BOOLEAN,  -- Did price reach SL?

    created_at REAL NOT NULL,
    FOREIGN KEY (trade_id) REFERENCES trades(id)
);
```

### Benefits:
- **Pattern Analysis**: "Which setups work best?"
- **Parameter Optimization**: "What divergence strength threshold is optimal?"
- **Time-based Analysis**: "Do trades at 3am perform worse?"
- **Context-aware Learning**: "Strong divergences in high volatility = better?"

---

## Implementation Priority

### Phase 1: Parameter Changes (Immediate)
1. ✅ Increase brick size: 1.0 → 1.3
2. ✅ Increase lookback: 20 → 30
3. ✅ Lower threshold: 0.1 → 0.08
4. ✅ Increase confirmation: 3 → 4 bricks

### Phase 2: Data Persistence (High Priority)
1. ✅ Persist Renko bricks (like candles for breakout)
2. ✅ Persist price history (for ATR/AO)
3. ⚠️ Persist current brick size (optional)

### Phase 3: Enhanced Analytics (Medium Priority)
1. ✅ Add `trade_context` table
2. ✅ Record entry conditions on trade
3. ✅ Record MFE/MAE during trade
4. ✅ Create analysis queries

---

## Questions to Answer with Analytics

1. **Which divergence types are most profitable?**
   - Bullish vs Bearish
   - Strong (>0.15) vs Moderate (0.08-0.15)

2. **What market conditions favor Renko strategy?**
   - Volatility ranges (3-5 bps vs 6-8 bps)
   - BB positions (<0.2 vs >0.8)
   - Time of day

3. **What entry timing works best?**
   - Bricks since divergence (3 vs 4 vs 5)
   - AO strength at entry

4. **What exit strategies work best?**
   - Should we trail stops more aggressively?
   - Should we take profit earlier?
   - What's the optimal hold time?

5. **How do parameters interact?**
   - Does brick size affect optimal divergence threshold?
   - Does lookback period affect win rate?

---

## Summary

**Recommendation: Do ALL parameter changes**
- They work synergistically (bigger bricks + longer lookback = better patterns)
- Still very selective (goal: 1-3 trades/day)
- Better quality signals

**Data Persistence: CRITICAL**
- Renko bricks must persist (takes hours to rebuild)
- Price history should persist (needed for indicators)

**Enhanced Analytics: HIGH VALUE**
- Will enable data-driven optimization
- Can answer "what works best?" questions
- Essential for refining edge over time

