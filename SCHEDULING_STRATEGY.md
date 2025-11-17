# Scheduling Strategy for Self-Learning Infrastructure

## The Problem

You're right - I can't run things automatically without prompts. So we need to decide:
1. **What needs to run automatically?**
2. **How do we schedule it?**
3. **What can run in the main loop vs separate jobs?**

---

## What Needs Scheduling?

### 1. Parameter History Tracking ✅ **NO SCHEDULING NEEDED**
- **When**: Automatically on parameter change (during deploy)
- **How**: Built into parameter change logic
- **Why**: Happens when we change config and deploy

### 2. Performance Monitoring ⚠️ **NEEDS SCHEDULING**
- **When**: Every 1-6 hours (check recent performance)
- **What**: Compare last 24h vs last 7d, detect degradation
- **Action**: Log warnings/alerts if thresholds breached

### 3. Automated Analysis ⚠️ **NEEDS SCHEDULING**
- **When**: Daily (once per day)
- **What**: Generate insights, recommendations
- **Action**: Log insights, could email/Discord (future)

### 4. Experiment Tracking ✅ **MOSTLY AUTOMATIC**
- **When**: On experiment start/end (manual or automatic)
- **How**: Built into parameter change logic
- **Why**: Happens when we start/stop experiments

---

## Solution Options

### Option 1: Built into Main Loop (Simplest) ✅ **RECOMMENDED**

**How it works:**
- Add monitoring/analysis to the main trading loop
- Run checks every X hours (e.g., every 6 hours)
- No external dependencies, no cron setup needed

**Pros:**
- ✅ Simple - no Railway cron setup
- ✅ Works immediately
- ✅ No additional infrastructure
- ✅ Runs automatically with bot

**Cons:**
- ⚠️ Less precise timing (runs when bot is running)
- ⚠️ If bot crashes, checks don't run
- ⚠️ Tied to main process

**Implementation:**
```python
# In main.py or strategy loop
last_performance_check = 0
PERFORMANCE_CHECK_INTERVAL = 6 * 3600  # 6 hours

while running:
    # ... trading logic ...
    
    # Performance monitoring (every 6 hours)
    if time.time() - last_performance_check > PERFORMANCE_CHECK_INTERVAL:
        await check_performance()
        last_performance_check = time.time()
```

---

### Option 2: Railway Cron Jobs (More Precise)

**How it works:**
- Railway supports cron jobs via `railway.json` or separate services
- Create separate lightweight script for monitoring
- Schedule runs (e.g., daily at 2am)

**Pros:**
- ✅ Precise timing (runs exactly when scheduled)
- ✅ Independent of main bot (runs even if bot crashes)
- ✅ Can run more frequently without impacting trading

**Cons:**
- ⚠️ More setup required
- ⚠️ Need to configure Railway cron
- ⚠️ Separate process to manage

**Implementation:**
```json
// railway.json
{
  "cron": [
    {
      "command": "python scripts/monitor_performance.py",
      "schedule": "0 */6 * * *"  // Every 6 hours
    },
    {
      "command": "python scripts/daily_analysis.py",
      "schedule": "0 2 * * *"  // Daily at 2am
    }
  ]
}
```

---

### Option 3: Hybrid Approach ✅ **BEST BALANCE**

**How it works:**
- **Performance Monitoring**: Built into main loop (every 6 hours)
- **Daily Analysis**: Railway cron job (once per day)
- **Parameter Tracking**: Automatic on deploy

**Why:**
- Performance monitoring needs to be frequent and tied to bot health
- Daily analysis can be separate and more comprehensive
- Parameter tracking happens naturally on deploy

---

## Recommended Implementation

### Phase 1: Built into Main Loop (Start Here)

**Add to main.py:**
```python
# Performance monitoring (runs every 6 hours in main loop)
async def monitor_performance():
    """Check performance and log warnings."""
    # Compare last 24h vs last 7d
    # Log warnings if degradation detected
    # Update parameter history performance metrics
    pass

# In main loop
last_check = 0
while True:
    # ... existing trading logic ...
    
    # Performance check every 6 hours
    if time.time() - last_check > 6 * 3600:
        await monitor_performance()
        last_check = time.time()
```

**Pros:**
- ✅ No setup required
- ✅ Works immediately
- ✅ Simple to implement

### Phase 2: Add Railway Cron (If Needed)

**If we want more precise timing or separate processes:**
- Add `railway.json` with cron jobs
- Create `scripts/monitor_performance.py`
- Create `scripts/daily_analysis.py`
- Schedule runs

**When to add:**
- If we want daily comprehensive analysis
- If we want alerts/notifications
- If we want more sophisticated reporting

---

## What We'll Implement

### Immediate (Phase 1):
1. ✅ **Performance Monitoring** - Built into main loop, runs every 6 hours
2. ✅ **Parameter History** - Automatic on parameter change (no scheduling)
3. ✅ **Basic Alerts** - Log warnings when performance degrades

### Later (Phase 2, if needed):
4. ⚠️ **Daily Analysis** - Railway cron job for comprehensive daily insights
5. ⚠️ **Notifications** - Email/Discord alerts (future)

---

## Answer to Your Question

**Do you need to set up cron jobs?**

**Short answer: No, not initially.**

We can build performance monitoring into the main trading loop. It will:
- Run automatically when the bot is running
- Check performance every 6 hours
- Log warnings if issues detected
- No Railway cron setup needed

**If you want more precise timing later**, we can add Railway cron jobs, but it's not required to start.

**The key insight:** Most of the self-learning infrastructure can run automatically:
- Parameter tracking: Automatic on deploy ✅
- Performance monitoring: Built into main loop ✅
- Daily analysis: Can be built into loop OR cron (your choice)

---

## Implementation Plan

1. **Add performance monitoring to main loop** (no cron needed)
2. **Add parameter history tracking** (automatic on changes)
3. **Test and iterate**
4. **Add Railway cron later if needed** (optional)

This way, everything works automatically without you needing to set up anything!

