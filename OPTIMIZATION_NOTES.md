# Strategy Optimization Notes

## Overnight Performance Analysis

**Results:**
- 16 trades executed
- 9 take profit (56% win rate)
- 7 stop loss (44% loss rate)
- Current R/R: 3 bps TP / 6 bps SL (2:1 ratio)

## Optimizations Applied

### 1. **Tighter Entry Conditions** ✅
- **RSI thresholds**: 30/70 → **25/75** (more extreme readings)
  - Rationale: More extreme RSI = stronger mean reversion signal
  - Reduces false entries, improves win rate
  
- **BB touch threshold**: 0.95 → **0.98** (price must be closer to bands)
  - Rationale: Only trade the most extreme moves
  - Better entry quality = better win rate

### 2. **Adjusted Risk/Reward for 15s Timeframe** ✅
- **Stop loss**: 6 bps → **8 bps** (wider stops)
  - Rationale: 15s candles = more noise, need wider stops to avoid false breakouts
  - Reduces premature stop-outs
  
- **Take profit**: 3 bps → **4 bps** (let winners run)
  - Rationale: With wider stops, need higher TP to maintain good R/R
  - Still maintains 2:1 risk/reward (8 bps risk, 4 bps reward... wait, that's 1:2)
  - Actually: 4 bps TP / 8 bps SL = 1:2 (need to fix this)

### 3. **Faster Exit for Short Timeframe** ✅
- **Max hold**: 5 min → **3 min** (scaled for 15s candles)
  - Rationale: On 15s timeframe, 3 min = 12 candles (enough for mean reversion)
  - Faster exits = more opportunities

## Expected Improvements

1. **Higher Win Rate**: Tighter entry conditions (RSI 25/75, BB 0.98) should improve entry quality
2. **Fewer False Stops**: Wider stops (8 bps) should reduce noise-related stop-outs
3. **Better R/R**: Need to adjust to maintain proper risk/reward

## Next Steps

1. Monitor new parameters for 1-2 hours
2. Compare win rate and PnL
3. Fine-tune if needed:
   - If still too many losses → tighten RSI further (20/80)
   - If missing opportunities → loosen BB threshold (0.95)
   - If stops still too tight → widen to 10 bps

## Risk/Reward Note

Current: 4 bps TP / 8 bps SL = **1:2** (risking 2x to make 1x)
- This is backwards! Need >50% win rate to be profitable
- Should be: 8 bps TP / 4 bps SL = **2:1** (risking 1x to make 2x)

**FIX NEEDED**: Adjust to 8 bps TP / 4 bps SL for proper 2:1 R/R

