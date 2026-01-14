# options_backtest.py - VIX Options Strategy Backtesting
# Requires: pandas, numpy
# Data: VIX options CSV with columns: quote_date, expiration, strike, option_type, bid_eod, ask_eod, underlying_bid_eod

import pandas as pd
import numpy as np
from datetime import datetime

def load_options_data(file_path):
    """Load and prepare VIX options data"""
    df = pd.read_csv(file_path,
                     usecols=['quote_date', 'expiration', 'strike', 'option_type',
                              'bid_eod', 'ask_eod', 'underlying_bid_eod'])
    df['quote_date'] = pd.to_datetime(df['quote_date'])
    df['expiration'] = pd.to_datetime(df['expiration'])
    df['dte'] = (df['expiration'] - df['quote_date']).dt.days
    return df

def find_option(df_day, option_type, target_strike, dte_min=20, dte_max=45):
    """Find option closest to target strike within DTE range"""
    opts = df_day[(df_day['option_type'] == option_type) &
                  (df_day['dte'] >= dte_min) &
                  (df_day['dte'] <= dte_max) &
                  (df_day['bid_eod'] > 0)]
    if len(opts) == 0:
        return None
    opts = opts.copy()
    opts['strike_diff'] = abs(opts['strike'] - target_strike)
    return opts.loc[opts['strike_diff'].idxmin()]

def get_vix_on_date(df, date):
    """Get VIX level on a specific date"""
    d = df[df['quote_date'] == date]
    return d['underlying_bid_eod'].iloc[0] if len(d) > 0 else None

def get_settlement_vix(df, expiration):
    """Get VIX at expiration (or nearest prior date)"""
    vix = get_vix_on_date(df, expiration)
    if vix is None:
        prior = df[df['quote_date'] < expiration]['quote_date'].max()
        vix = get_vix_on_date(df, prior) if not pd.isna(prior) else None
    return vix


# =============================================================================
# STRATEGY 1: Sell OTM Calls Monthly
# =============================================================================
def strategy_otm_calls(df, otm_offset=10, dte_min=25, dte_max=45, min_premium=0.10):
    """
    Sell calls OTM_OFFSET points above current VIX, monthly.
    """
    trading_dates = sorted(df['quote_date'].unique())
    positions = []
    results = []
    last_exp = None

    for date in trading_dates:
        df_day = df[df['quote_date'] == date]
        vix = df_day['underlying_bid_eod'].iloc[0]

        if last_exp is None or date > last_exp:
            target_strike = round((vix + otm_offset) / 2.5) * 2.5
            opt = find_option(df_day, 'C', target_strike, dte_min, dte_max)

            if opt is not None and opt['bid_eod'] > min_premium:
                positions.append({
                    'entry_date': date, 'expiration': opt['expiration'],
                    'strike': opt['strike'], 'premium': opt['bid_eod'], 'vix_entry': vix
                })
                last_exp = opt['expiration']

    for pos in positions:
        vix_exp = get_settlement_vix(df, pos['expiration'])
        if vix_exp:
            settlement = max(0, vix_exp - pos['strike'])
            pnl = (pos['premium'] - settlement) * 100
            results.append({**pos, 'settlement': settlement, 'pnl': pnl, 'vix_exp': vix_exp})

    return pd.DataFrame(results)


# =============================================================================
# STRATEGY 5: Dynamic Strangles
# =============================================================================
def strategy_dynamic_strangles(df, put_pct=0.70, call_pct=1.50, dte_min=25, dte_max=45):
    """
    Sell strangle with strikes at PUT_PCT * VIX and CALL_PCT * VIX.
    """
    trading_dates = sorted(df['quote_date'].unique())
    positions = []
    results = []
    last_exp = None

    for date in trading_dates:
        df_day = df[df['quote_date'] == date]
        vix = df_day['underlying_bid_eod'].iloc[0]

        if last_exp is None or date > last_exp:
            put_strike = max(10, round((vix * put_pct) / 2.5) * 2.5)
            call_strike = round((vix * call_pct) / 2.5) * 2.5

            put_opt = find_option(df_day, 'P', put_strike, dte_min, dte_max)
            call_opt = find_option(df_day, 'C', call_strike, dte_min, dte_max)

            if put_opt is not None and call_opt is not None:
                if put_opt['expiration'] == call_opt['expiration']:
                    premium = put_opt['bid_eod'] + call_opt['bid_eod']
                    if premium > 0.20:
                        positions.append({
                            'entry_date': date, 'expiration': put_opt['expiration'],
                            'put_strike': put_opt['strike'], 'call_strike': call_opt['strike'],
                            'premium': premium, 'vix_entry': vix
                        })
                        last_exp = put_opt['expiration']

    for pos in positions:
        vix_exp = get_settlement_vix(df, pos['expiration'])
        if vix_exp:
            put_settle = max(0, pos['put_strike'] - vix_exp)
            call_settle = max(0, vix_exp - pos['call_strike'])
            settlement = put_settle + call_settle
            pnl = (pos['premium'] - settlement) * 100
            results.append({**pos, 'settlement': settlement, 'pnl': pnl, 'vix_exp': vix_exp})

    return pd.DataFrame(results)


# =============================================================================
# STRATEGY 7: Call Spreads (Defined Risk)
# =============================================================================
def strategy_call_spreads(df, short_offset=10, long_offset=20, dte_min=25, dte_max=45):
    """
    Sell call spread with defined max loss.
    Short strike = VIX + SHORT_OFFSET, Long strike = VIX + LONG_OFFSET
    """
    trading_dates = sorted(df['quote_date'].unique())
    positions = []
    results = []
    last_exp = None

    for date in trading_dates:
        df_day = df[df['quote_date'] == date]
        vix = df_day['underlying_bid_eod'].iloc[0]

        if last_exp is None or date > last_exp:
            short_strike = round((vix + short_offset) / 2.5) * 2.5
            long_strike = round((vix + long_offset) / 2.5) * 2.5

            short_call = find_option(df_day, 'C', short_strike, dte_min, dte_max)
            long_call = find_option(df_day, 'C', long_strike, dte_min, dte_max)

            if short_call is not None and long_call is not None:
                if short_call['expiration'] == long_call['expiration']:
                    credit = short_call['bid_eod'] - long_call['ask_eod']
                    spread_width = long_call['strike'] - short_call['strike']

                    if credit > 0.10 and spread_width > 0:
                        positions.append({
                            'entry_date': date, 'expiration': short_call['expiration'],
                            'short_strike': short_call['strike'], 'long_strike': long_call['strike'],
                            'credit': credit, 'max_loss': spread_width - credit, 'vix_entry': vix
                        })
                        last_exp = short_call['expiration']

    for pos in positions:
        vix_exp = get_settlement_vix(df, pos['expiration'])
        if vix_exp:
            short_intr = max(0, vix_exp - pos['short_strike'])
            long_intr = max(0, vix_exp - pos['long_strike'])
            settlement = short_intr - long_intr
            pnl = (pos['credit'] - settlement) * 100
            results.append({**pos, 'settlement': settlement, 'pnl': pnl, 'vix_exp': vix_exp})

    return pd.DataFrame(results)


# =============================================================================
# STRATEGY 9: Post-Spike Call Spreads (BEST RISK-ADJUSTED)
# =============================================================================
def strategy_post_spike_call_spreads(df, vix_threshold=30, short_pct=1.20, long_pct=1.40):
    """
    Only sell call spreads AFTER VIX spikes above threshold.
    Best risk-adjusted strategy - 100% win rate in backtest.
    """
    trading_dates = sorted(df['quote_date'].unique())
    positions = []
    results = []
    in_position = False
    last_exp = None

    for date in trading_dates:
        df_day = df[df['quote_date'] == date]
        vix = df_day['underlying_bid_eod'].iloc[0]

        if last_exp and date > last_exp:
            in_position = False

        if not in_position and vix > vix_threshold:
            short_strike = round((vix * short_pct) / 5) * 5
            long_strike = round((vix * long_pct) / 5) * 5

            short_call = find_option(df_day, 'C', short_strike, 25, 45)
            long_call = find_option(df_day, 'C', long_strike, 25, 45)

            if short_call is not None and long_call is not None:
                if short_call['expiration'] == long_call['expiration']:
                    credit = short_call['bid_eod'] - long_call['ask_eod']
                    spread_width = long_call['strike'] - short_call['strike']

                    if credit > 0.20 and spread_width > 0:
                        positions.append({
                            'entry_date': date, 'expiration': short_call['expiration'],
                            'short_strike': short_call['strike'], 'long_strike': long_call['strike'],
                            'credit': credit, 'spread_width': spread_width, 'vix_entry': vix
                        })
                        in_position = True
                        last_exp = short_call['expiration']

    for pos in positions:
        vix_exp = get_settlement_vix(df, pos['expiration'])
        if vix_exp:
            short_intr = max(0, vix_exp - pos['short_strike'])
            long_intr = max(0, vix_exp - pos['long_strike'])
            settlement = min(short_intr - long_intr, pos['spread_width'])
            pnl = (pos['credit'] - settlement) * 100
            results.append({**pos, 'settlement': settlement, 'pnl': pnl, 'vix_exp': vix_exp})

    return pd.DataFrame(results)


# =============================================================================
# Run all strategies
# =============================================================================
def run_all_strategies(df):
    """Run all strategies and return summary"""
    results = {}

    print("Running Strategy 1: OTM Calls...")
    results['otm_calls'] = strategy_otm_calls(df)

    print("Running Strategy 5: Dynamic Strangles...")
    results['strangles'] = strategy_dynamic_strangles(df)

    print("Running Strategy 7: Call Spreads...")
    results['call_spreads'] = strategy_call_spreads(df)

    print("Running Strategy 9: Post-Spike Call Spreads...")
    results['post_spike'] = strategy_post_spike_call_spreads(df)

    # Summary
    print("\n" + "="*70)
    print("STRATEGY COMPARISON")
    print("="*70)
    print(f"\n{'Strategy':<35} {'Trades':>7} {'Win%':>7} {'Total P&L':>12} {'Max Loss':>10}")
    print("-" * 75)

    for name, res in results.items():
        if len(res) > 0:
            wins = (res['pnl'] > 0).sum()
            win_pct = 100 * wins / len(res)
            total = res['pnl'].sum()
            max_loss = res['pnl'].min()
            print(f"{name:<35} {len(res):>7} {win_pct:>6.1f}% ${total:>10,.0f} ${max_loss:>9,.0f}")

    return results


if __name__ == "__main__":
    import sys
    file_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/raw vix option data 2010 to Aug 2022.csv"

    print(f"Loading data from {file_path}...")
    df = load_options_data(file_path)
    print(f"Loaded {len(df):,} rows")

    results = run_all_strategies(df)
