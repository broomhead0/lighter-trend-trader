#!/usr/bin/env python3
"""
Deep dive analysis for strategy optimization.

This script analyzes all trade data to identify:
1. What conditions lead to profitable trades
2. What conditions lead to losses
3. Optimal entry/exit parameters
4. Market regime filters
5. Time-based patterns

Goal: Find the highest-probability setups, even if they're rare.
"""

import sys
import re
import subprocess
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import json

def fetch_logs(tail_lines: int = 20000) -> List[str]:
    """Fetch logs from Railway."""
    try:
        result = subprocess.run(
            ["railway", "logs", "--tail", str(tail_lines)],
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.stdout.splitlines()
    except Exception as e:
        print(f"Error fetching logs: {e}")
        return []

def parse_trade_data(logs: List[str]) -> List[Dict]:
    """
    Parse comprehensive trade data including:
    - Entry conditions (RSI, BB position, volatility, EMA, etc.)
    - Exit conditions (reason, price, time in trade)
    - PnL outcome
    - Market conditions
    """
    trades = []
    current_trade = None
    
    for line in logs:
        # Entry signal
        entry_match = re.search(
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*\[(mean_reversion|renko_ao)\].*entering (\w+) position: price=([\d.]+) size=([\d.]+) reason=(.+)',
            line
        )
        if entry_match:
            if current_trade:
                trades.append(current_trade)  # Save previous trade
            current_trade = {
                'timestamp': entry_match.group(1),
                'strategy': entry_match.group(2),
                'side': entry_match.group(3),
                'entry_price': float(entry_match.group(4)),
                'size': float(entry_match.group(5)),
                'entry_reason': entry_match.group(6),
                'entry_indicators': {},
                'exit_indicators': {},
            }
            continue
        
        # Indicators at entry (RSI+BB)
        if current_trade and current_trade['strategy'] == 'mean_reversion':
            rsi_match = re.search(r'RSI=([\d.]+)', line)
            bb_match = re.search(r'BB_pos=([\d.]+)', line)
            vol_match = re.search(r'vol_bps=([\d.]+)', line)
            ema_match = re.search(r'EMA_fast=([\d.]+).*EMA_slow=([\d.]+)', line)
            
            if rsi_match:
                current_trade['entry_indicators']['rsi'] = float(rsi_match.group(1))
            if bb_match:
                current_trade['entry_indicators']['bb_position'] = float(bb_match.group(1))
            if vol_match:
                current_trade['entry_indicators']['volatility_bps'] = float(vol_match.group(1))
            if ema_match:
                current_trade['entry_indicators']['ema_fast'] = float(ema_match.group(1))
                current_trade['entry_indicators']['ema_slow'] = float(ema_match.group(2))
        
        # Indicators at entry (Renko+AO)
        if current_trade and current_trade['strategy'] == 'renko_ao':
            ao_match = re.search(r'AO=([\d.+-]+)', line)
            div_match = re.search(r'divergence=(\w+)', line)
            strength_match = re.search(r'strength=([\d.]+)', line)
            bb_match = re.search(r'BB_pos=([\d.]+)', line)
            
            if ao_match:
                current_trade['entry_indicators']['ao'] = float(ao_match.group(1))
            if div_match:
                current_trade['entry_indicators']['divergence_type'] = div_match.group(1)
            if strength_match:
                current_trade['entry_indicators']['divergence_strength'] = float(strength_match.group(1))
            if bb_match:
                current_trade['entry_indicators']['bb_position'] = float(bb_match.group(1))
        
        # Exit
        exit_match = re.search(
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*\[(mean_reversion|renko_ao)\].*exiting position: side=(\w+) entry=([\d.]+) reason=(\w+)',
            line
        )
        if exit_match and current_trade:
            current_trade['exit_timestamp'] = exit_match.group(1)
            current_trade['exit_reason'] = exit_match.group(5)
            continue
        
        # PnL
        pnl_match = re.search(
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*\[(mean_reversion|renko_ao)\].*LIVE PnL: ([\d.+-]+)% \(entry=([\d.]+), exit=([\d.]+)',
            line
        )
        if pnl_match and current_trade:
            current_trade['pnl_pct'] = float(pnl_match.group(3))
            current_trade['exit_price'] = float(pnl_match.group(5))
            
            # Calculate time in trade
            try:
                entry_time = datetime.strptime(current_trade['timestamp'], '%Y-%m-%d %H:%M:%S')
                exit_time = datetime.strptime(current_trade.get('exit_timestamp', pnl_match.group(1)), '%Y-%m-%d %H:%M:%S')
                current_trade['time_in_trade_seconds'] = (exit_time - entry_time).total_seconds()
            except:
                current_trade['time_in_trade_seconds'] = None
            
            trades.append(current_trade)
            current_trade = None
    
    return trades

def analyze_by_condition(trades: List[Dict], strategy: str) -> Dict:
    """Analyze trades grouped by entry conditions."""
    strategy_trades = [t for t in trades if t['strategy'] == strategy]
    
    if not strategy_trades:
        return {}
    
    analysis = {
        'total_trades': len(strategy_trades),
        'wins': [t for t in strategy_trades if t.get('pnl_pct', 0) > 0],
        'losses': [t for t in strategy_trades if t.get('pnl_pct', 0) <= 0],
        'by_condition': defaultdict(list),
    }
    
    # Group by key conditions
    for trade in strategy_trades:
        if strategy == 'mean_reversion':
            # Group by RSI range, BB position, volatility
            rsi = trade['entry_indicators'].get('rsi', 50)
            bb_pos = trade['entry_indicators'].get('bb_position', 0.5)
            vol = trade['entry_indicators'].get('volatility_bps', 0)
            
            # RSI buckets
            if rsi > 70:
                rsi_bucket = 'RSI>70'
            elif rsi > 60:
                rsi_bucket = 'RSI 60-70'
            elif rsi > 50:
                rsi_bucket = 'RSI 50-60'
            elif rsi > 40:
                rsi_bucket = 'RSI 40-50'
            elif rsi > 30:
                rsi_bucket = 'RSI 30-40'
            else:
                rsi_bucket = 'RSI<30'
            
            # BB position buckets
            if bb_pos > 0.8:
                bb_bucket = 'BB>80%'
            elif bb_pos > 0.6:
                bb_bucket = 'BB 60-80%'
            elif bb_pos > 0.4:
                bb_bucket = 'BB 40-60%'
            elif bb_pos > 0.2:
                bb_bucket = 'BB 20-40%'
            else:
                bb_bucket = 'BB<20%'
            
            # Volatility buckets
            if vol > 10:
                vol_bucket = 'Vol>10bps'
            elif vol > 5:
                vol_bucket = 'Vol 5-10bps'
            elif vol > 2:
                vol_bucket = 'Vol 2-5bps'
            else:
                vol_bucket = 'Vol<2bps'
            
            condition_key = f"{rsi_bucket} | {bb_bucket} | {vol_bucket}"
            analysis['by_condition'][condition_key].append(trade)
        
        elif strategy == 'renko_ao':
            # Group by divergence strength, BB position, AO value
            div_strength = trade['entry_indicators'].get('divergence_strength', 0)
            bb_pos = trade['entry_indicators'].get('bb_position', 0.5)
            ao = trade['entry_indicators'].get('ao', 0)
            
            # Divergence strength buckets
            if div_strength > 0.1:
                div_bucket = 'Div>0.1'
            elif div_strength > 0.05:
                div_bucket = 'Div 0.05-0.1'
            else:
                div_bucket = 'Div<0.05'
            
            # BB position buckets (same as above)
            if bb_pos > 0.8:
                bb_bucket = 'BB>80%'
            elif bb_pos > 0.6:
                bb_bucket = 'BB 60-80%'
            elif bb_pos > 0.4:
                bb_bucket = 'BB 40-60%'
            elif bb_pos > 0.2:
                bb_bucket = 'BB 20-40%'
            else:
                bb_bucket = 'BB<20%'
            
            # AO buckets
            if ao > 0.1:
                ao_bucket = 'AO>0.1'
            elif ao > 0:
                ao_bucket = 'AO 0-0.1'
            elif ao > -0.1:
                ao_bucket = 'AO -0.1-0'
            else:
                ao_bucket = 'AO<-0.1'
            
            condition_key = f"{div_bucket} | {bb_bucket} | {ao_bucket}"
            analysis['by_condition'][condition_key].append(trade)
    
    return analysis

def print_analysis(trades: List[Dict]):
    """Print comprehensive analysis."""
    print("=" * 80)
    print("DEEP DIVE STRATEGY ANALYSIS")
    print("=" * 80)
    print()
    
    # Overall stats
    total = len(trades)
    wins = [t for t in trades if t.get('pnl_pct', 0) > 0]
    losses = [t for t in trades if t.get('pnl_pct', 0) <= 0]
    total_pnl = sum(t.get('pnl_pct', 0) for t in trades)
    
    print(f"Total Trades: {total}")
    print(f"Wins: {len(wins)} ({len(wins)/total*100:.1f}%)")
    print(f"Losses: {len(losses)} ({len(losses)/total*100:.1f}%)")
    print(f"Total PnL: {total_pnl:+.4f}%")
    print()
    
    # Analyze by strategy
    for strategy in ['mean_reversion', 'renko_ao']:
        analysis = analyze_by_condition(trades, strategy)
        if not analysis:
            continue
        
        print("=" * 80)
        print(f"{strategy.upper()} STRATEGY")
        print("=" * 80)
        print()
        
        # Overall stats
        strat_trades = [t for t in trades if t['strategy'] == strategy]
        strat_wins = [t for t in strat_trades if t.get('pnl_pct', 0) > 0]
        strat_losses = [t for t in strat_trades if t.get('pnl_pct', 0) <= 0]
        strat_pnl = sum(t.get('pnl_pct', 0) for t in strat_trades)
        
        print(f"Total: {len(strat_trades)} trades, {len(strat_wins)}W/{len(strat_losses)}L, {strat_pnl:+.4f}% PnL")
        print()
        
        # Best conditions
        print("TOP CONDITIONS BY WIN RATE:")
        print("-" * 80)
        
        condition_stats = []
        for condition, condition_trades in analysis['by_condition'].items():
            condition_wins = [t for t in condition_trades if t.get('pnl_pct', 0) > 0]
            condition_pnl = sum(t.get('pnl_pct', 0) for t in condition_trades)
            win_rate = len(condition_wins) / len(condition_trades) * 100 if condition_trades else 0
            
            condition_stats.append({
                'condition': condition,
                'trades': len(condition_trades),
                'wins': len(condition_wins),
                'win_rate': win_rate,
                'pnl': condition_pnl,
                'avg_pnl': condition_pnl / len(condition_trades) if condition_trades else 0,
            })
        
        # Sort by win rate (descending)
        condition_stats.sort(key=lambda x: x['win_rate'], reverse=True)
        
        for stat in condition_stats[:10]:  # Top 10
            if stat['trades'] >= 2:  # At least 2 trades for significance
                print(f"{stat['condition']}")
                print(f"  Trades: {stat['trades']}, Win Rate: {stat['win_rate']:.1f}%, PnL: {stat['pnl']:+.4f}%, Avg: {stat['avg_pnl']:+.4f}%")
                print()
        
        # Worst conditions
        print("WORST CONDITIONS (AVOID):")
        print("-" * 80)
        for stat in condition_stats[-5:]:  # Bottom 5
            if stat['trades'] >= 2:
                print(f"{stat['condition']}")
                print(f"  Trades: {stat['trades']}, Win Rate: {stat['win_rate']:.1f}%, PnL: {stat['pnl']:+.4f}%")
                print()
        
        print()

def main():
    print("Fetching logs...")
    logs = fetch_logs(20000)
    
    print("Parsing trade data...")
    trades = parse_trade_data(logs)
    
    if not trades:
        print("No trades found in logs")
        return
    
    print(f"Found {len(trades)} trades")
    print()
    
    print_analysis(trades)
    
    # Export to JSON for further analysis
    with open('trade_analysis.json', 'w') as f:
        json.dump(trades, f, indent=2, default=str)
    print("Trade data exported to trade_analysis.json")

if __name__ == "__main__":
    main()

