#!/usr/bin/env python3
"""
Test the staggered absolute strategy on Databento VIX options data.

This script runs on the server side after user uploads vix_options_databento.csv.zip

Usage:
    python test_databento_data.py [path_to_zip]
"""

import sys
import zipfile
import pandas as pd
import numpy as np
from datetime import datetime

# =============================================================================
# DATA LOADING
# =============================================================================

def load_data(file_path):
    """Load VIX options data from CSV or ZIP"""
    print(f"Loading data from {file_path}...")

    if file_path.endswith('.zip'):
        with zipfile.ZipFile(file_path, 'r') as zf:
            csv_name = [n for n in zf.namelist() if n.endswith('.csv')][0]
            with zf.open(csv_name) as f:
                df = pd.read_csv(f)
    else:
        df = pd.read_csv(file_path)

    # Convert date columns
    for col in ['quote_date', 'expiration']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])

    # Calculate DTE
    if 'quote_date' in df.columns and 'expiration' in df.columns:
        df['dte'] = (df['expiration'] - df['quote_date']).dt.days

    print(f"Loaded {len(df):,} rows")
    print(f"Columns: {df.columns.tolist()}")
    print(f"Date range: {df['quote_date'].min()} to {df['quote_date'].max()}")

    return df


# =============================================================================
# STRATEGY FUNCTIONS
# =============================================================================

def get_settlement_vix(df, expiration):
    """Get VIX at expiration"""
    d = df[df['quote_date'] == expiration]
    if len(d) > 0:
        return d['underlying_bid_eod'].iloc[0]
    prior = df[df['quote_date'] < expiration]['quote_date'].max()
    if not pd.isna(prior):
        d = df[df['quote_date'] == prior]
        return d['underlying_bid_eod'].iloc[0] if len(d) > 0 else None
    return None


def find_spread(df_day, short_strike, long_strike, dte_min, dte_max):
    """Find a specific spread if available"""
    calls = df_day[(df_day['option_type'] == 'C') &
                   (df_day['dte'] >= dte_min) &
                   (df_day['dte'] <= dte_max)]

    short = calls[calls['strike'] == short_strike]
    long = calls[calls['strike'] == long_strike]

    if len(short) == 0 or len(long) == 0:
        return None

    common_exp = set(short['expiration']) & set(long['expiration'])
    if not common_exp:
        return None

    exp = min(common_exp)
    s = short[short['expiration'] == exp].iloc[0]
    l = long[long['expiration'] == exp].iloc[0]

    credit = s['bid_eod'] - l['ask_eod']
    if credit <= 0:
        return None

    return {
        'expiration': exp,
        'short_strike': short_strike,
        'long_strike': long_strike,
        'credit': credit,
        'spread_width': long_strike - short_strike,
        'dte': s['dte']
    }


def run_staggered_absolute(df, short_strike=35, long_strike=45, dte_min=60, dte_max=100,
                           target_positions=3, starting_capital=40000, entry_interval_days=28):
    """
    Staggered expiration strategy with absolute strikes.

    Parameters:
    -----------
    short_strike : float = 35
    long_strike : float = 45
    dte_min : int = 60
    dte_max : int = 100
    target_positions : int = 3
    starting_capital : float = 40000
    entry_interval_days : int = 28

    Returns:
    --------
    trades : DataFrame
    final_capital : float
    open_positions : list
    """
    trading_dates = sorted(df['quote_date'].unique())

    capital = starting_capital
    open_positions = []
    closed_trades = []
    last_entry = None

    for date in trading_dates:
        df_day = df[df['quote_date'] == date]
        if len(df_day) == 0:
            continue

        vix = df_day['underlying_bid_eod'].iloc[0]

        # CHECK FOR EXPIRATIONS
        positions_to_close = []
        for i, pos in enumerate(open_positions):
            if date >= pos['expiration']:
                vix_exp = get_settlement_vix(df, pos['expiration'])
                if vix_exp:
                    short_intr = max(0, vix_exp - pos['short_strike'])
                    long_intr = max(0, vix_exp - pos['long_strike'])
                    settlement = min(short_intr - long_intr, pos['spread_width'])
                    pnl_per = (pos['credit'] - settlement) * 100
                    total_pnl = pnl_per * pos['contracts']

                    capital += total_pnl

                    closed_trades.append({
                        **pos,
                        'exit_date': pos['expiration'],
                        'vix_exp': vix_exp,
                        'pnl_per': pnl_per,
                        'total_pnl': total_pnl,
                        'capital_after': capital,
                        'win': pnl_per > 0
                    })
                positions_to_close.append(i)

        for i in sorted(positions_to_close, reverse=True):
            open_positions.pop(i)

        # CHECK FOR NEW ENTRY
        should_enter = (last_entry is None or
                        (date - last_entry).days >= entry_interval_days)

        if should_enter and len(open_positions) < target_positions:
            spread = find_spread(df_day, short_strike, long_strike, dte_min, dte_max)

            if spread:
                capital_per_position = capital / target_positions
                max_loss_per = (spread['spread_width'] - spread['credit']) * 100
                affordable = int(capital_per_position / max_loss_per)
                num_contracts = max(1, affordable)

                open_positions.append({
                    'entry_date': date,
                    'expiration': spread['expiration'],
                    'short_strike': spread['short_strike'],
                    'long_strike': spread['long_strike'],
                    'credit': spread['credit'],
                    'spread_width': spread['spread_width'],
                    'max_loss_per': max_loss_per,
                    'contracts': num_contracts,
                    'vix_entry': vix,
                    'capital_at_entry': capital,
                    'dte_at_entry': spread['dte']
                })
                last_entry = date

    return pd.DataFrame(closed_trades), capital, open_positions


# =============================================================================
# ANALYSIS
# =============================================================================

def analyze_results(trades, starting_capital=40000):
    """Analyze and print strategy results"""
    if len(trades) == 0:
        print("No trades to analyze")
        return

    final_capital = trades['capital_after'].iloc[-1]
    total_pnl = final_capital - starting_capital
    years = (trades['exit_date'].max() - trades['entry_date'].min()).days / 365.25

    wins = trades['win'].sum()
    losses = len(trades) - wins
    win_rate = 100 * wins / len(trades)

    cagr = (final_capital / starting_capital) ** (1/years) - 1 if years > 0 else 0

    peak = trades['capital_after'].iloc[0]
    max_dd = 0
    for cap in trades['capital_after']:
        peak = max(peak, cap)
        dd = (peak - cap) / peak
        max_dd = max(max_dd, dd)

    print(f"""
================================================================================
STAGGERED ABSOLUTE STRATEGY RESULTS
35/45 Call Spread | 60-100 DTE | 3 Overlapping Positions | Hold to Expiry
================================================================================

DATA PERIOD: {trades['entry_date'].min().strftime('%Y-%m-%d')} to {trades['exit_date'].max().strftime('%Y-%m-%d')} ({years:.1f} years)

PERFORMANCE:
  Starting Capital:  ${starting_capital:,.0f}
  Final Capital:     ${final_capital:,.0f}
  Total P&L:         ${total_pnl:,.0f}
  Total Return:      {(final_capital/starting_capital - 1)*100:.1f}%
  CAGR:              {cagr*100:.1f}%

TRADES:
  Total Trades:      {len(trades)}
  Wins:              {wins} ({win_rate:.1f}%)
  Losses:            {losses}

RISK:
  Max Single Loss:   ${trades['total_pnl'].min():,.0f}
  Max Single Win:    ${trades['total_pnl'].max():,.0f}
  Max Drawdown:      {max_dd*100:.1f}%
""")

    # Yearly breakdown
    trades = trades.copy()
    trades['year'] = trades['entry_date'].dt.year

    print("YEARLY BREAKDOWN")
    print("="*70)
    print(f"{'Year':<8} {'Trades':>8} {'Wins':>8} {'Losses':>8} {'P&L':>15} {'End Capital':>15}")
    print("-"*70)

    for year in sorted(trades['year'].unique()):
        yr = trades[trades['year'] == year]
        yr_wins = yr['win'].sum()
        yr_losses = len(yr) - yr_wins
        yr_pnl = yr['total_pnl'].sum()
        yr_end = yr['capital_after'].iloc[-1]
        sign = '+' if yr_pnl >= 0 else ''
        print(f"{year:<8} {len(yr):>8} {yr_wins:>8} {yr_losses:>8} {sign}${yr_pnl:>14,.0f} ${yr_end:>14,.0f}")

    # Show losing trades
    losers = trades[~trades['win']]
    if len(losers) > 0:
        print(f"\nLOSING TRADES ({len(losers)})")
        print("-"*80)
        for _, row in losers.iterrows():
            print(f"  {row['entry_date'].strftime('%Y-%m-%d')} -> {row['exit_date'].strftime('%Y-%m-%d')}: "
                  f"VIX {row['vix_entry']:.1f} -> {row['vix_exp']:.1f}, "
                  f"{row['contracts']} contracts, ${row['total_pnl']:,.0f}")
    else:
        print("\n*** NO LOSING TRADES IN THIS PERIOD! ***")

    return {
        'final_capital': final_capital,
        'cagr': cagr,
        'win_rate': win_rate,
        'max_drawdown': max_dd,
        'trades': len(trades),
        'losses': losses
    }


def check_data_quality(df):
    """Check if the data has the required columns and format"""
    print("\n" + "="*60)
    print("DATA QUALITY CHECK")
    print("="*60)

    required_cols = ['quote_date', 'expiration', 'strike', 'option_type',
                     'bid_eod', 'ask_eod', 'underlying_bid_eod']

    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        print(f"\n*** MISSING COLUMNS: {missing} ***")
        print("Available columns:", df.columns.tolist())
        return False

    print(f"\n✓ All required columns present")

    # Check data ranges
    print(f"\nData summary:")
    print(f"  Dates: {df['quote_date'].min()} to {df['quote_date'].max()}")
    print(f"  Strikes: {df['strike'].min()} to {df['strike'].max()}")
    print(f"  VIX range: {df['underlying_bid_eod'].min():.1f} to {df['underlying_bid_eod'].max():.1f}")
    print(f"  Option types: {df['option_type'].unique()}")

    # Check for 35 and 45 strikes
    has_35 = 35 in df['strike'].values
    has_45 = 45 in df['strike'].values
    print(f"  Has strike 35: {has_35}")
    print(f"  Has strike 45: {has_45}")

    if not has_35 or not has_45:
        print("\n*** WARNING: Missing 35 or 45 strikes - strategy may not execute ***")

    return True


# =============================================================================
# MAIN
# =============================================================================

def main():
    # Get file path from command line or use default
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        # Try to find the zip file
        import os
        for f in ['vix_options_databento.csv.zip', 'vix_options_databento.csv',
                  'analysis/vix_options_databento.csv.zip']:
            if os.path.exists(f):
                file_path = f
                break
        else:
            print("Usage: python test_databento_data.py <path_to_data>")
            print("Expected: vix_options_databento.csv.zip")
            return

    # Load data
    df = load_data(file_path)

    # Check data quality
    if not check_data_quality(df):
        print("\nData quality check failed. Please verify the data format.")
        return

    # Run strategy
    print("\n" + "="*60)
    print("RUNNING STAGGERED ABSOLUTE STRATEGY")
    print("="*60)

    trades, final_capital, remaining = run_staggered_absolute(
        df,
        short_strike=35,
        long_strike=45,
        dte_min=60,
        dte_max=100,
        target_positions=3,
        starting_capital=40000
    )

    if len(trades) > 0:
        results = analyze_results(trades, starting_capital=40000)

        if len(remaining) > 0:
            print(f"\nNote: {len(remaining)} positions still open at end of data")

    else:
        print("\nNo trades executed. Check if data contains 35/45 strikes at 60-100 DTE.")


if __name__ == "__main__":
    main()
