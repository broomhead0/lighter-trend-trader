# Self-Learning Infrastructure for Trading Bot

## Goal
Build a system that **keeps learning until we achieve profitability** through:
- Automated data collection
- Performance analysis
- Parameter optimization
- Feedback loops

---

## Current Infrastructure (✅ Already Built)

### 1. Deploy Continuity
- **Positions**: Recovered from database on startup
- **Candles**: Persisted for breakout strategy
- **Renko Bricks**: (To be implemented) Persisted for Renko strategy
- **Why**: Don't lose state on deploys, can iterate without resetting

### 2. Data Storage
- **Trades**: All trades stored in `trades` table
- **Trade Context**: Enhanced analytics in `trade_context` table (to be implemented)
- **Positions**: Current positions in `positions` table
- **Why**: Historical data for analysis and learning

### 3. Performance Tracking
- **PnL Tracker**: Database-backed, handles 100k+ trades
- **Query Tools**: `scripts/query_pnl.py` for analysis
- **Why**: Track what's working, what's not

---

## Additional Infrastructure Needed

### 1. Parameter Versioning & History ⚠️ **IMPORTANT**

**Problem**: When we change parameters, we lose track of what worked.

**Solution**: Track parameter changes over time.

**Implementation:**
```sql
CREATE TABLE parameter_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy TEXT NOT NULL,
    parameter_name TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_at REAL NOT NULL,
    reason TEXT,  -- Why we changed it
    performance_before REAL,  -- PnL before change
    performance_after REAL,  -- PnL after change (updated later)
    created_at REAL NOT NULL
);
```

**Why**:
- Know what parameter values worked best
- Can revert if performance drops
- Track optimization journey

**Usage**:
- Log every parameter change
- After X trades, update `performance_after`
- Query: "What RSI threshold gave best results?"

---

### 2. Performance Monitoring & Alerts ⚠️ **IMPORTANT**

**Problem**: Need to know when performance degrades.

**Solution**: Automated performance checks and alerts.

**Implementation:**
- **Scheduled Analysis**: Run `scripts/analyze_performance.py` every hour/day
- **Performance Metrics**: Win rate, avg PnL, Sharpe ratio, drawdown
- **Thresholds**: Alert if win rate drops below X%, or PnL goes negative
- **Trend Detection**: Is performance improving or degrading?

**Why**:
- Catch problems early
- Know when to adjust parameters
- Track progress toward profitability

**Simple Version**:
```python
# scripts/monitor_performance.py
# Runs periodically, checks:
# - Win rate last 24h vs last 7d
# - PnL trend (improving/degrading)
# - Any strategy underperforming
# - Logs warnings if thresholds breached
```

---

### 3. Automated Analysis & Insights ⚠️ **NICE TO HAVE**

**Problem**: Need to extract insights from data automatically.

**Solution**: Scheduled analysis scripts that generate insights.

**Implementation:**
- **Daily Analysis**: `scripts/daily_insights.py`
  - Best performing setups
  - Worst performing setups
  - Parameter recommendations
  - Market condition analysis

**Why**:
- Automatically surface what's working
- Suggest optimizations
- Reduce manual analysis time

**Example Output**:
```
Daily Insights (2025-11-17):
- RSI+BB: Win rate 60% (↑ from 55%)
- Renko+AO: No trades (divergence threshold too high?)
- Breakout: 2 trades, +0.15% net
- Recommendation: Lower Renko divergence threshold to 0.08
```

---

### 4. Experiment Tracking ⚠️ **NICE TO HAVE**

**Problem**: When testing changes, need to compare results.

**Solution**: Track "experiments" (parameter changes) and their outcomes.

**Implementation:**
```sql
CREATE TABLE experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,  -- "renko_brick_size_1.3"
    strategy TEXT NOT NULL,
    parameters_json TEXT,  -- JSON of all parameters
    start_time REAL NOT NULL,
    end_time REAL,  -- NULL if active
    trades_count INTEGER,
    win_rate REAL,
    avg_pnl_pct REAL,
    total_pnl_pct REAL,
    status TEXT,  -- "active", "completed", "stopped"
    notes TEXT
);
```

**Why**:
- A/B test parameter changes
- Compare different configurations
- Make data-driven decisions

**Usage**:
- Start experiment when changing parameters
- End experiment after N trades or X days
- Compare experiments to find best config

---

### 5. Backtesting Capability ⚠️ **FUTURE**

**Problem**: Want to test changes before deploying live.

**Solution**: Replay historical data with different parameters.

**Implementation** (Future):
- Store historical price data
- Replay with different parameters
- Compare results

**Why**:
- Test changes safely
- Validate optimizations
- Reduce risk

**Note**: This is more complex, can add later if needed.

---

### 6. Automated Parameter Optimization ⚠️ **FUTURE**

**Problem**: Want system to optimize itself.

**Solution**: Automated parameter tuning based on performance.

**Implementation** (Future):
- Grid search or genetic algorithm
- Test parameter combinations
- Select best performing

**Why**:
- Fully automated optimization
- Find optimal parameters
- Continuous improvement

**Note**: This is advanced, start with manual optimization first.

---

## Recommended Implementation Order

### Phase 1: Essential (Do First)
1. ✅ **Parameter History Tracking**
   - Track all parameter changes
   - Link to performance outcomes
   - Enable rollback if needed

2. ✅ **Performance Monitoring**
   - Daily/weekly performance checks
   - Alert on degradation
   - Track trends

### Phase 2: Helpful (Do Next)
3. ✅ **Automated Analysis**
   - Daily insights generation
   - Setup performance analysis
   - Recommendations

4. ✅ **Experiment Tracking**
   - Track parameter experiments
   - Compare configurations
   - A/B testing capability

### Phase 3: Advanced (Future)
5. ⚠️ **Backtesting** (if needed)
6. ⚠️ **Automated Optimization** (if needed)

---

## Simple Feedback Loop Design

### Current State:
1. Collect data ✅ (trades, context)
2. Analyze data ⚠️ (manual queries)
3. Optimize parameters ⚠️ (manual changes)
4. Deploy changes ✅ (GitHub → Railway)

### With Infrastructure:
1. Collect data ✅ (trades, context)
2. **Automated analysis** ✅ (scheduled scripts)
3. **Performance monitoring** ✅ (alerts on degradation)
4. **Parameter tracking** ✅ (know what worked)
5. **Experiment tracking** ✅ (compare changes)
6. Optimize parameters ✅ (data-driven)
7. Deploy changes ✅ (GitHub → Railway)
8. **Monitor results** ✅ (automated tracking)

---

## Key Principles

1. **Keep It Simple**: Start with essentials, add complexity only if needed
2. **Data-Driven**: All decisions based on data, not intuition
3. **Iterative**: Small changes, measure results, iterate
4. **Automated**: Reduce manual work, automate analysis
5. **Track Everything**: Can't optimize what you don't measure

---

## What We Have vs What We Need

| Feature | Status | Priority |
|---------|--------|----------|
| Deploy Continuity | ✅ Done | Critical |
| Data Storage | ✅ Done | Critical |
| Performance Tracking | ✅ Done | Critical |
| Trade Context Analytics | 🚧 In Progress | High |
| Parameter History | ❌ Missing | **High** |
| Performance Monitoring | ❌ Missing | **High** |
| Automated Analysis | ❌ Missing | Medium |
| Experiment Tracking | ❌ Missing | Medium |
| Backtesting | ❌ Missing | Low |
| Auto-Optimization | ❌ Missing | Low |

---

## Next Steps

1. **Complete Trade Context** (already planned)
2. **Add Parameter History** (track all changes)
3. **Add Performance Monitoring** (automated checks)
4. **Add Automated Analysis** (daily insights)
5. **Add Experiment Tracking** (A/B testing)

This gives us a complete self-learning system without over-engineering.

