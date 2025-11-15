# Automated Optimization Feedback Loop

## Overview

This system automatically monitors strategy performance and iterates on parameters until profitability is achieved.

## How It Works

1. **Monitor**: Script analyzes Railway logs for PnL data
2. **Analyze**: Calculates win rate, R:R ratio, and break-even requirements
3. **Optimize**: Suggests parameter tweaks based on performance gaps
4. **Iterate**: Repeats until strategies are profitable

## Sample Size Requirements

- **Minimum for significance**: 30-50 trades per strategy
- **With current frequency**: ~15-20 trades/hour
- **Time per iteration**: ~2-3 hours
- **Early exit**: Can detect clear failures after ~15 trades

## Profitability Criteria

A strategy is considered profitable when:
- Total PnL > 0.1% AND Win Rate > 50%, OR
- Total PnL > 0.2%

## Usage

### Manual Check
```bash
python3 scripts/auto_optimize.py
```

### Automated Monitoring (cron)
Add to crontab to run every 2 hours:
```bash
0 */2 * * * cd /path/to/lighter-trend-trader && python3 scripts/auto_optimize.py >> optimization.log 2>&1
```

### Continuous Loop (background)
```bash
# Run optimization check every 2 hours
while true; do
  python3 scripts/auto_optimize.py
  sleep 7200  # 2 hours
done
```

## Current Optimization Targets

### RSI+BB Strategy
- **Current Gap**: Need +4.4% win rate (from 50% to 54.4%)
- **Current R:R**: 0.85:1 (target: >1.0)
- **Latest Tweaks**: Stop loss 4.5 bps, Take profit 5.0 bps (R:R = 1.11:1)

### Renko+AO Strategy
- **Current Gap**: Need +12.4% win rate (from 23.5% to 35.9%)
- **Current R:R**: 1.79:1 (good!)
- **Latest Tweaks**: Divergence threshold 0.05 (more selective), Stop loss 7.0 bps

## Next Steps

1. Let bot run for 2-3 hours to gather ~30-50 trades
2. Run `auto_optimize.py` to check status
3. If not profitable, review recommendations and iterate
4. Repeat until profitable
5. Report back when both strategies are profitable

## Notes

- The script will automatically detect when strategies are profitable
- Recommendations are strategy-specific based on current performance
- All changes are logged to git for tracking

