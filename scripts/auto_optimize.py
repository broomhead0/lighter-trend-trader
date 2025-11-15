#!/usr/bin/env python3
"""
Automated optimization feedback loop for trading strategies.

This script:
1. Monitors performance from Railway logs
2. Analyzes win rate, R:R, and PnL
3. Determines if tweaks are working
4. Suggests next iteration or reports profitability

Sample size: ~30-50 trades per strategy for statistical significance
With ~15-20 trades/hour, that's ~2-3 hours per iteration
"""

import subprocess
import re
import sys
from collections import defaultdict
from typing import Dict, List, Tuple
from datetime import datetime, timedelta

# Minimum sample size for statistical significance
MIN_TRADES_PER_STRATEGY = 30
MIN_TRADES_FOR_EARLY_EXIT = 15  # Can exit early if clearly failing


def fetch_logs(tail_lines: int = 10000) -> List[str]:
    """Fetch logs from Railway."""
    try:
        result = subprocess.run(
            ["railway", "logs", "--tail", str(tail_lines)],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout.splitlines()
    except Exception as e:
        print(f"Error fetching logs: {e}")
        return []


def parse_trades(logs: List[str]) -> Dict[str, List[Dict]]:
    """Parse PnL data from logs."""
    trades = defaultdict(list)
    
    for line in logs:
        match = re.search(r'LIVE PnL: ([\d.+-]+)%', line)
        if match:
            strategy = 'mean_reversion' if 'mean_reversion' in line else 'renko_ao' if 'renko_ao' in line else 'unknown'
            if strategy != 'unknown':
                trades[strategy].append({
                    'pnl': float(match.group(1)),
                    'line': line
                })
    
    return trades


def analyze_strategy(trades: List[Dict], strategy_name: str) -> Dict:
    """Analyze a single strategy's performance."""
    if not trades:
        return None
    
    wins = [t for t in trades if t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] < 0]
    total_pnl = sum(t['pnl'] for t in trades)
    avg_pnl = total_pnl / len(trades)
    win_rate = len(wins) / len(trades) * 100
    
    avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 0
    avg_loss = abs(sum(t['pnl'] for t in losses) / len(losses)) if losses else 0
    rr_ratio = avg_win / avg_loss if avg_loss > 0 else 0
    
    # Calculate break-even win rate
    breakeven_wr = avg_loss / (avg_win + avg_loss) * 100 if (avg_win + avg_loss) > 0 else 0
    wr_gap = breakeven_wr - win_rate
    
    # Profitability threshold: >0.1% total PnL and >50% win rate OR >0.2% total PnL
    is_profitable = (total_pnl > 0.1 and win_rate > 50) or total_pnl > 0.2
    
    return {
        'strategy': strategy_name,
        'total_trades': len(trades),
        'win_rate': win_rate,
        'wins': len(wins),
        'losses': len(losses),
        'total_pnl': total_pnl,
        'avg_pnl': avg_pnl,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'rr_ratio': rr_ratio,
        'breakeven_wr': breakeven_wr,
        'wr_gap': wr_gap,
        'is_profitable': is_profitable
    }


def generate_recommendations(analysis: Dict) -> List[str]:
    """Generate optimization recommendations."""
    recs = []
    
    if analysis['total_trades'] < MIN_TRADES_PER_STRATEGY:
        recs.append(f"⚠️  Need {MIN_TRADES_PER_STRATEGY - analysis['total_trades']} more trades for statistical significance")
        return recs
    
    if analysis['is_profitable']:
        recs.append("✅ Strategy is PROFITABLE!")
        return recs
    
    # RSI+BB specific recommendations
    if analysis['strategy'] == 'mean_reversion':
        if analysis['rr_ratio'] < 1.0:
            recs.append(f"⚠️  R:R ratio {analysis['rr_ratio']:.2f}:1 is below 1.0")
            recs.append("   → Consider: Increase take profit OR tighten stop loss")
        if analysis['win_rate'] < analysis['breakeven_wr']:
            recs.append(f"⚠️  Win rate {analysis['win_rate']:.1f}% below break-even {analysis['breakeven_wr']:.1f}%")
            recs.append(f"   → Need +{analysis['wr_gap']:.1f}% win rate")
            if analysis['rr_ratio'] > 1.0:
                recs.append("   → Consider: Tighten entry filters to improve win rate")
            else:
                recs.append("   → Consider: Widen stop loss OR increase take profit")
    
    # Renko+AO specific recommendations
    elif analysis['strategy'] == 'renko_ao':
        if analysis['win_rate'] < analysis['breakeven_wr']:
            recs.append(f"⚠️  Win rate {analysis['win_rate']:.1f}% below break-even {analysis['breakeven_wr']:.1f}%")
            recs.append(f"   → Need +{analysis['wr_gap']:.1f}% win rate")
            if analysis['rr_ratio'] > 1.5:
                recs.append("   → R:R is good, focus on improving win rate")
                recs.append("   → Consider: Increase divergence threshold (more selective)")
                recs.append("   → Consider: Tighten stop loss to reduce losses")
            else:
                recs.append("   → Consider: Widen stop loss OR increase take profit")
    
    return recs


def main():
    """Main optimization loop."""
    print("=" * 70)
    print("Automated Strategy Optimization Monitor")
    print("=" * 70)
    print()
    
    # Fetch and parse logs
    print("Fetching logs from Railway...")
    logs = fetch_logs()
    trades = parse_trades(logs)
    
    if not trades:
        print("❌ No trades found in logs")
        print("   Bot may have just deployed. Waiting for trades...")
        return 1
    
    print(f"Found {sum(len(t) for t in trades.values())} total trades")
    print()
    
    # Analyze each strategy
    all_profitable = True
    for strategy_name in ['mean_reversion', 'renko_ao']:
        if strategy_name not in trades:
            continue
        
        analysis = analyze_strategy(trades[strategy_name], strategy_name)
        if not analysis:
            continue
        
        print(f"{analysis['strategy'].upper()}:")
        print(f"  Trades: {analysis['total_trades']} ({analysis['wins']}W/{analysis['losses']}L)")
        print(f"  Win Rate: {analysis['win_rate']:.1f}% (need {analysis['breakeven_wr']:.1f}% for break-even)")
        print(f"  Total PnL: {analysis['total_pnl']:+.4f}%")
        print(f"  Avg PnL: {analysis['avg_pnl']:+.4f}%")
        print(f"  R:R Ratio: {analysis['rr_ratio']:.2f}:1")
        print(f"  Avg Win: {analysis['avg_win']:+.4f}%, Avg Loss: {analysis['avg_loss']:+.4f}%")
        
        if analysis['is_profitable']:
            print("  ✅ PROFITABLE!")
        else:
            print("  ⚠️  Not yet profitable")
            all_profitable = False
        
        print()
        
        # Generate recommendations
        recs = generate_recommendations(analysis)
        if recs:
            print("  Recommendations:")
            for rec in recs:
                print(f"    {rec}")
            print()
    
    # Overall status
    total_trades = sum(len(t) for t in trades.values())
    total_pnl = sum(sum(t['pnl'] for t in trades[s]) for s in trades)
    
    print("=" * 70)
    print("OVERALL STATUS")
    print("=" * 70)
    print(f"Total Trades: {total_trades}")
    print(f"Total PnL: {total_pnl:+.4f}%")
    
    if total_trades == 0:
        print()
        print("⏳ No trades yet. Bot may have just deployed.")
        print("   Waiting for trades to accumulate...")
        return 1
    elif all_profitable and total_trades >= MIN_TRADES_PER_STRATEGY * 2:
        print()
        print("🎉 ALL STRATEGIES ARE PROFITABLE!")
        print("   Ready for production deployment.")
        return 0
    elif total_trades < MIN_TRADES_PER_STRATEGY * 2:
        print()
        print(f"⏳ Need more data: {MIN_TRADES_PER_STRATEGY * 2 - total_trades} more trades")
        print("   Continue monitoring...")
        return 1
    else:
        print()
        print("⚠️  Strategies need optimization")
        print("   Review recommendations above and iterate.")
        return 2


if __name__ == "__main__":
    sys.exit(main())

