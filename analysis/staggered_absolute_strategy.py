# staggered_absolute_strategy.py - VIX Options Strategy with Absolute Strikes
#
# WINNING STRATEGY: 35/45 Call Spread, 60-100 DTE, 3 Overlapping Positions
#
# Key findings vs baseline (relative VIX+10/+20 strikes):
#   - CAGR: 12.4% vs 4.7%
#   - Win rate: 98.0% vs 96.5%
#   - Losing trades: 3 vs 5
#   - Final capital (12 yrs): $162,816 vs $69,450 (starting $40k)
#   - Max drawdown: 51.4% vs 21.4% (tail risk is higher)
#
# The absolute 35 strike is breached less often than VIX+10 during spikes,
# resulting in 39% more profit per position.

import pandas as pd
import numpy as np
from datetime import timedelta

def load_options_data(file_path):
    """Load and prepare VIX options data"""
    df = pd.read_csv(file_path,
                     usecols=['quote_date', 'expiration', 'strike', 'option_type',
                              'bid_eod', 'ask_eod', 'underlying_bid_eod'])
    df['quote_date'] = pd.to_datetime(df['quote_date'])
    df['expiration'] = pd.to_datetime(df['expiration'])
    df['dte'] = (df['expiration'] - df['quote_date']).dt.days
    return df

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

    # Find common expiration
    common_exp = set(short['expiration']) & set(long['expiration'])
    if not common_exp:
        return None

    exp = min(common_exp)  # Take nearest expiration
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
    df : DataFrame
        VIX options data
    short_strike : float
        Fixed short call strike (default 35)
    long_strike : float
        Fixed long call strike (default 45)
    dte_min : int
        Minimum days to expiration at entry (default 60)
    dte_max : int
        Maximum days to expiration at entry (default 100)
    target_positions : int
        Number of overlapping positions to maintain (default 3)
    starting_capital : float
        Initial capital (default $40,000)
    entry_interval_days : int
        Days between entries (default 28 = monthly)

    Returns:
    --------
    trades : DataFrame
        All closed trades with P&L
    final_capital : float
        Ending capital
    open_positions : list
        Any positions still open
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


def analyze_results(trades, starting_capital=40000):
    """Analyze strategy results"""
    if len(trades) == 0:
        print("No trades to analyze")
        return

    final_capital = trades['capital_after'].iloc[-1]
    total_pnl = final_capital - starting_capital
    years = (trades['exit_date'].max() - trades['entry_date'].min()).days / 365.25

    wins = trades['win'].sum()
    losses = len(trades) - wins
    win_rate = 100 * wins / len(trades)

    # Calculate CAGR
    cagr = (final_capital / starting_capital) ** (1/years) - 1

    # Calculate max drawdown
    peak = trades['capital_after'].iloc[0]
    max_dd = 0
    for cap in trades['capital_after']:
        peak = max(peak, cap)
        dd = (peak - cap) / peak
        max_dd = max(max_dd, dd)

    print(f"""
STRATEGY RESULTS
================
Starting Capital:  ${starting_capital:,.0f}
Final Capital:     ${final_capital:,.0f}
Total P&L:         ${total_pnl:,.0f}
Total Return:      {(final_capital/starting_capital - 1)*100:.1f}%
CAGR:              {cagr*100:.1f}%

Trades:            {len(trades)}
Wins:              {wins} ({win_rate:.1f}%)
Losses:            {losses}

Max Single Loss:   ${trades['total_pnl'].min():,.0f}
Max Single Win:    ${trades['total_pnl'].max():,.0f}
Max Drawdown:      {max_dd*100:.1f}%
""")

    # Yearly breakdown
    trades['year'] = trades['entry_date'].dt.year
    print("YEARLY BREAKDOWN")
    print("="*60)
    print(f"{'Year':<8} {'Trades':>8} {'Wins':>8} {'P&L':>15} {'End Capital':>15}")
    print("-"*60)

    for year in sorted(trades['year'].unique()):
        yr = trades[trades['year'] == year]
        yr_wins = yr['win'].sum()
        yr_pnl = yr['total_pnl'].sum()
        yr_end = yr['capital_after'].iloc[-1]
        print(f"{year:<8} {len(yr):>8} {yr_wins:>8} ${yr_pnl:>14,.0f} ${yr_end:>14,.0f}")

    # Show losing trades
    losers = trades[~trades['win']]
    if len(losers) > 0:
        print(f"\nLOSING TRADES ({len(losers)})")
        print("-"*60)
        for _, row in losers.iterrows():
            print(f"  {row['entry_date'].strftime('%Y-%m-%d')} -> {row['exit_date'].strftime('%Y-%m-%d')}: "
                  f"VIX {row['vix_entry']:.1f} -> {row['vix_exp']:.1f}, "
                  f"{row['contracts']} contracts, ${row['total_pnl']:,.0f}")


if __name__ == "__main__":
    import sys

    file_path = sys.argv[1] if len(sys.argv) > 1 else "raw vix option data 2010 to Aug 2022.csv"

    print(f"Loading data from {file_path}...")
    df = load_options_data(file_path)
    print(f"Loaded {len(df):,} rows")

    print("\nRunning staggered absolute strategy (35/45 spread, 60-100 DTE, 3 positions)...")
    trades, final_capital, remaining = run_staggered_absolute(
        df,
        short_strike=35,
        long_strike=45,
        dte_min=60,
        dte_max=100,
        target_positions=3,
        starting_capital=40000
    )

    analyze_results(trades, starting_capital=40000)

    if len(remaining) > 0:
        print(f"\nNote: {len(remaining)} positions still open at end of data")
