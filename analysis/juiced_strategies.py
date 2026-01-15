# juiced_strategies.py - Enhanced VIX Call Spread Strategy Variations
# Tests all "juiced" variations and compares them

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

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


# =============================================================================
# BASELINE: Strategy 7 - Monthly Call Spreads (25% return)
# =============================================================================
def baseline_call_spreads(df, short_offset=10, long_offset=20, dte_min=25, dte_max=45):
    """Original 25% strategy - sell call spread monthly"""
    trading_dates = sorted(df['quote_date'].unique())
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
                        results.append({
                            'entry_date': date, 'expiration': short_call['expiration'],
                            'short_strike': short_call['strike'], 'long_strike': long_call['strike'],
                            'credit': credit, 'max_loss': spread_width - credit,
                            'vix_entry': vix, 'contracts': 1
                        })
                        last_exp = short_call['expiration']

    # Calculate P&L
    for pos in results:
        vix_exp = get_settlement_vix(df, pos['expiration'])
        if vix_exp:
            short_intr = max(0, vix_exp - pos['short_strike'])
            long_intr = max(0, vix_exp - pos['long_strike'])
            settlement = short_intr - long_intr
            pos['pnl'] = (pos['credit'] - settlement) * 100 * pos['contracts']
            pos['vix_exp'] = vix_exp
            pos['capital_at_risk'] = pos['max_loss'] * 100 * pos['contracts']

    return pd.DataFrame([r for r in results if 'pnl' in r])


# =============================================================================
# JUICE #1: VIX-Scaled Position Sizing
# =============================================================================
def juice1_vix_scaled(df, short_offset=10, long_offset=20, dte_min=25, dte_max=45):
    """Scale position size based on VIX level: 1x normal, 2x elevated, 3x spike"""
    trading_dates = sorted(df['quote_date'].unique())
    results = []
    last_exp = None

    for date in trading_dates:
        df_day = df[df['quote_date'] == date]
        vix = df_day['underlying_bid_eod'].iloc[0]

        # VIX-based sizing
        if vix >= 30:
            contracts = 3
        elif vix >= 22:
            contracts = 2
        else:
            contracts = 1

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
                        results.append({
                            'entry_date': date, 'expiration': short_call['expiration'],
                            'short_strike': short_call['strike'], 'long_strike': long_call['strike'],
                            'credit': credit, 'max_loss': spread_width - credit,
                            'vix_entry': vix, 'contracts': contracts
                        })
                        last_exp = short_call['expiration']

    for pos in results:
        vix_exp = get_settlement_vix(df, pos['expiration'])
        if vix_exp:
            short_intr = max(0, vix_exp - pos['short_strike'])
            long_intr = max(0, vix_exp - pos['long_strike'])
            settlement = short_intr - long_intr
            pos['pnl'] = (pos['credit'] - settlement) * 100 * pos['contracts']
            pos['vix_exp'] = vix_exp
            pos['capital_at_risk'] = pos['max_loss'] * 100 * pos['contracts']

    return pd.DataFrame([r for r in results if 'pnl' in r])


# =============================================================================
# JUICE #2: Tighter Spreads When VIX High
# =============================================================================
def juice2_tight_when_high(df, dte_min=25, dte_max=45):
    """Use +5/+15 when VIX > 25, else +10/+20"""
    trading_dates = sorted(df['quote_date'].unique())
    results = []
    last_exp = None

    for date in trading_dates:
        df_day = df[df['quote_date'] == date]
        vix = df_day['underlying_bid_eod'].iloc[0]

        # Tighter spread when VIX elevated
        if vix >= 25:
            short_offset, long_offset = 5, 15
        else:
            short_offset, long_offset = 10, 20

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
                        results.append({
                            'entry_date': date, 'expiration': short_call['expiration'],
                            'short_strike': short_call['strike'], 'long_strike': long_call['strike'],
                            'credit': credit, 'max_loss': spread_width - credit,
                            'vix_entry': vix, 'contracts': 1
                        })
                        last_exp = short_call['expiration']

    for pos in results:
        vix_exp = get_settlement_vix(df, pos['expiration'])
        if vix_exp:
            short_intr = max(0, vix_exp - pos['short_strike'])
            long_intr = max(0, vix_exp - pos['long_strike'])
            settlement = short_intr - long_intr
            pos['pnl'] = (pos['credit'] - settlement) * 100 * pos['contracts']
            pos['vix_exp'] = vix_exp
            pos['capital_at_risk'] = pos['max_loss'] * 100 * pos['contracts']

    return pd.DataFrame([r for r in results if 'pnl' in r])


# =============================================================================
# JUICE #3: Twice-Monthly Entries
# =============================================================================
def juice3_twice_monthly(df, short_offset=10, long_offset=20):
    """Two entries per month - around 1st and 15th"""
    trading_dates = sorted(df['quote_date'].unique())
    results = []
    last_exp_1 = None  # Track first monthly position
    last_exp_2 = None  # Track second monthly position

    for date in trading_dates:
        df_day = df[df['quote_date'] == date]
        vix = df_day['underlying_bid_eod'].iloc[0]
        day_of_month = date.day

        # Entry 1: Days 1-10, use 45-60 DTE
        can_enter_1 = (last_exp_1 is None or date > last_exp_1) and (1 <= day_of_month <= 10)
        # Entry 2: Days 15-25, use 25-45 DTE
        can_enter_2 = (last_exp_2 is None or date > last_exp_2) and (15 <= day_of_month <= 25)

        for entry_type, can_enter, dte_range in [
            (1, can_enter_1, (40, 60)),
            (2, can_enter_2, (25, 45))
        ]:
            if can_enter:
                short_strike = round((vix + short_offset) / 2.5) * 2.5
                long_strike = round((vix + long_offset) / 2.5) * 2.5

                short_call = find_option(df_day, 'C', short_strike, dte_range[0], dte_range[1])
                long_call = find_option(df_day, 'C', long_strike, dte_range[0], dte_range[1])

                if short_call is not None and long_call is not None:
                    if short_call['expiration'] == long_call['expiration']:
                        credit = short_call['bid_eod'] - long_call['ask_eod']
                        spread_width = long_call['strike'] - short_call['strike']

                        if credit > 0.10 and spread_width > 0:
                            results.append({
                                'entry_date': date, 'expiration': short_call['expiration'],
                                'short_strike': short_call['strike'], 'long_strike': long_call['strike'],
                                'credit': credit, 'max_loss': spread_width - credit,
                                'vix_entry': vix, 'contracts': 1, 'entry_type': entry_type
                            })
                            if entry_type == 1:
                                last_exp_1 = short_call['expiration']
                            else:
                                last_exp_2 = short_call['expiration']

    for pos in results:
        vix_exp = get_settlement_vix(df, pos['expiration'])
        if vix_exp:
            short_intr = max(0, vix_exp - pos['short_strike'])
            long_intr = max(0, vix_exp - pos['long_strike'])
            settlement = short_intr - long_intr
            pos['pnl'] = (pos['credit'] - settlement) * 100 * pos['contracts']
            pos['vix_exp'] = vix_exp
            pos['capital_at_risk'] = pos['max_loss'] * 100 * pos['contracts']

    return pd.DataFrame([r for r in results if 'pnl' in r])


# =============================================================================
# JUICE #4: Post-Spike Bonus Entries
# =============================================================================
def juice4_post_spike(df, vix_threshold=30, short_offset=15, long_offset=25, dte_min=25, dte_max=45):
    """Extra entries when VIX was recently above threshold"""
    trading_dates = sorted(df['quote_date'].unique())
    results = []
    last_exp = None

    # Track when VIX was above threshold
    vix_history = {}
    for date in trading_dates:
        df_day = df[df['quote_date'] == date]
        vix = df_day['underlying_bid_eod'].iloc[0]
        vix_history[date] = vix

    for date in trading_dates:
        df_day = df[df['quote_date'] == date]
        vix = df_day['underlying_bid_eod'].iloc[0]

        # Check if VIX was above threshold in last 10 days
        lookback = [d for d in trading_dates if d < date and d >= date - timedelta(days=10)]
        was_spiked = any(vix_history.get(d, 0) >= vix_threshold for d in lookback)

        if was_spiked and vix < vix_threshold and (last_exp is None or date > last_exp):
            short_strike = round((vix + short_offset) / 2.5) * 2.5
            long_strike = round((vix + long_offset) / 2.5) * 2.5

            short_call = find_option(df_day, 'C', short_strike, dte_min, dte_max)
            long_call = find_option(df_day, 'C', long_strike, dte_min, dte_max)

            if short_call is not None and long_call is not None:
                if short_call['expiration'] == long_call['expiration']:
                    credit = short_call['bid_eod'] - long_call['ask_eod']
                    spread_width = long_call['strike'] - short_call['strike']

                    if credit > 0.20 and spread_width > 0:
                        results.append({
                            'entry_date': date, 'expiration': short_call['expiration'],
                            'short_strike': short_call['strike'], 'long_strike': long_call['strike'],
                            'credit': credit, 'max_loss': spread_width - credit,
                            'vix_entry': vix, 'contracts': 1
                        })
                        last_exp = short_call['expiration']

    for pos in results:
        vix_exp = get_settlement_vix(df, pos['expiration'])
        if vix_exp:
            short_intr = max(0, vix_exp - pos['short_strike'])
            long_intr = max(0, vix_exp - pos['long_strike'])
            settlement = short_intr - long_intr
            pos['pnl'] = (pos['credit'] - settlement) * 100 * pos['contracts']
            pos['vix_exp'] = vix_exp
            pos['capital_at_risk'] = pos['max_loss'] * 100 * pos['contracts']

    return pd.DataFrame([r for r in results if 'pnl' in r])


# =============================================================================
# JUICE #5: Long Puts After Spikes (Hedge + Stack)
# =============================================================================
def juice5_long_puts(df, vix_threshold=30, dte_min=60, dte_max=90):
    """Buy puts when VIX > threshold, bet on mean reversion"""
    trading_dates = sorted(df['quote_date'].unique())
    results = []
    last_exp = None

    for date in trading_dates:
        df_day = df[df['quote_date'] == date]
        vix = df_day['underlying_bid_eod'].iloc[0]

        if vix > vix_threshold and (last_exp is None or date > last_exp):
            # Buy ATM put
            target_strike = round(vix / 2.5) * 2.5
            put = find_option(df_day, 'P', target_strike, dte_min, dte_max)

            if put is not None:
                cost = put['ask_eod']
                if cost > 0:
                    results.append({
                        'entry_date': date, 'expiration': put['expiration'],
                        'strike': put['strike'], 'cost': cost,
                        'vix_entry': vix, 'contracts': 1
                    })
                    last_exp = put['expiration']

    for pos in results:
        vix_exp = get_settlement_vix(df, pos['expiration'])
        if vix_exp:
            intrinsic = max(0, pos['strike'] - vix_exp)
            pos['pnl'] = (intrinsic - pos['cost']) * 100 * pos['contracts']
            pos['vix_exp'] = vix_exp
            pos['capital_at_risk'] = pos['cost'] * 100 * pos['contracts']

    return pd.DataFrame([r for r in results if 'pnl' in r])


# =============================================================================
# JUICE #6: Wider Spreads (+10/+25)
# =============================================================================
def juice6_wider_spread(df, short_offset=10, long_offset=25, dte_min=25, dte_max=45):
    """Wider spread for higher credit but higher max loss"""
    trading_dates = sorted(df['quote_date'].unique())
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
                        results.append({
                            'entry_date': date, 'expiration': short_call['expiration'],
                            'short_strike': short_call['strike'], 'long_strike': long_call['strike'],
                            'credit': credit, 'max_loss': spread_width - credit,
                            'vix_entry': vix, 'contracts': 1
                        })
                        last_exp = short_call['expiration']

    for pos in results:
        vix_exp = get_settlement_vix(df, pos['expiration'])
        if vix_exp:
            short_intr = max(0, vix_exp - pos['short_strike'])
            long_intr = max(0, vix_exp - pos['long_strike'])
            settlement = short_intr - long_intr
            pos['pnl'] = (pos['credit'] - settlement) * 100 * pos['contracts']
            pos['vix_exp'] = vix_exp
            pos['capital_at_risk'] = pos['max_loss'] * 100 * pos['contracts']

    return pd.DataFrame([r for r in results if 'pnl' in r])


# =============================================================================
# BUNDLE: Combined 1 + 4 + 5 Strategy
# =============================================================================
def bundle_combined(df):
    """
    Combined strategy:
    - Base: VIX-scaled monthly call spreads (Juice 1)
    - Bonus: Post-spike entries (Juice 4)
    - Hedge: Long puts after spikes (Juice 5)
    """
    # Get results from each component
    base_results = juice1_vix_scaled(df)
    base_results['strategy_component'] = 'base_scaled'

    post_spike_results = juice4_post_spike(df)
    post_spike_results['strategy_component'] = 'post_spike'

    long_put_results = juice5_long_puts(df)
    long_put_results['strategy_component'] = 'long_puts'

    # Combine all results
    combined = pd.concat([base_results, post_spike_results, long_put_results], ignore_index=True)
    return combined


# =============================================================================
# OPTIMIZED BUNDLE: Best performing combinations
# =============================================================================
def bundle_optimized(df):
    """
    Optimized bundle using strategies that ACTUALLY improve returns:
    - Base: Twice-monthly entries (Juice 3) - best single strategy
    - Bonus: Post-spike entries (Juice 4) - 100% win rate
    No VIX-scaling (drags down risk-adjusted returns)
    """
    base_results = juice3_twice_monthly(df)
    base_results['strategy_component'] = 'twice_monthly'

    post_spike_results = juice4_post_spike(df)
    post_spike_results['strategy_component'] = 'post_spike'

    combined = pd.concat([base_results, post_spike_results], ignore_index=True)
    return combined


def bundle_twice_monthly_tight(df):
    """
    Twice-monthly entries with tight spreads when VIX high
    """
    trading_dates = sorted(df['quote_date'].unique())
    results = []
    last_exp_1 = None
    last_exp_2 = None

    for date in trading_dates:
        df_day = df[df['quote_date'] == date]
        vix = df_day['underlying_bid_eod'].iloc[0]
        day_of_month = date.day

        # Dynamic spread based on VIX
        if vix >= 25:
            short_offset, long_offset = 5, 15
        else:
            short_offset, long_offset = 10, 20

        can_enter_1 = (last_exp_1 is None or date > last_exp_1) and (1 <= day_of_month <= 10)
        can_enter_2 = (last_exp_2 is None or date > last_exp_2) and (15 <= day_of_month <= 25)

        for entry_type, can_enter, dte_range in [
            (1, can_enter_1, (40, 60)),
            (2, can_enter_2, (25, 45))
        ]:
            if can_enter:
                short_strike = round((vix + short_offset) / 2.5) * 2.5
                long_strike = round((vix + long_offset) / 2.5) * 2.5

                short_call = find_option(df_day, 'C', short_strike, dte_range[0], dte_range[1])
                long_call = find_option(df_day, 'C', long_strike, dte_range[0], dte_range[1])

                if short_call is not None and long_call is not None:
                    if short_call['expiration'] == long_call['expiration']:
                        credit = short_call['bid_eod'] - long_call['ask_eod']
                        spread_width = long_call['strike'] - short_call['strike']

                        if credit > 0.10 and spread_width > 0:
                            results.append({
                                'entry_date': date, 'expiration': short_call['expiration'],
                                'short_strike': short_call['strike'], 'long_strike': long_call['strike'],
                                'credit': credit, 'max_loss': spread_width - credit,
                                'vix_entry': vix, 'contracts': 1, 'entry_type': entry_type
                            })
                            if entry_type == 1:
                                last_exp_1 = short_call['expiration']
                            else:
                                last_exp_2 = short_call['expiration']

    for pos in results:
        vix_exp = get_settlement_vix(df, pos['expiration'])
        if vix_exp:
            short_intr = max(0, vix_exp - pos['short_strike'])
            long_intr = max(0, vix_exp - pos['long_strike'])
            settlement = short_intr - long_intr
            pos['pnl'] = (pos['credit'] - settlement) * 100 * pos['contracts']
            pos['vix_exp'] = vix_exp
            pos['capital_at_risk'] = pos['max_loss'] * 100 * pos['contracts']

    return pd.DataFrame([r for r in results if 'pnl' in r])


# =============================================================================
# Analysis and Reporting
# =============================================================================
def analyze_strategy(results_df, name, years=12.5):
    """Calculate key metrics for a strategy"""
    if len(results_df) == 0:
        return None

    total_pnl = results_df['pnl'].sum()
    num_trades = len(results_df)
    wins = (results_df['pnl'] > 0).sum()
    losses = (results_df['pnl'] <= 0).sum()
    win_rate = 100 * wins / num_trades if num_trades > 0 else 0

    avg_win = results_df[results_df['pnl'] > 0]['pnl'].mean() if wins > 0 else 0
    avg_loss = results_df[results_df['pnl'] <= 0]['pnl'].mean() if losses > 0 else 0
    max_loss_trade = results_df['pnl'].min()
    max_win_trade = results_df['pnl'].max()

    # Capital calculation
    if 'capital_at_risk' in results_df.columns:
        max_capital = results_df['capital_at_risk'].max()
    else:
        max_capital = 1000  # Default

    annual_return = (total_pnl / max_capital / years) * 100 if max_capital > 0 else 0

    return {
        'name': name,
        'trades': num_trades,
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'max_loss_trade': max_loss_trade,
        'max_win_trade': max_win_trade,
        'max_capital': max_capital,
        'annual_return': annual_return
    }


def run_all_strategies(df):
    """Run all strategies and generate comparison report"""

    # Calculate years in dataset
    dates = df['quote_date'].unique()
    years = (max(dates) - min(dates)).days / 365.25

    print(f"\n{'='*80}")
    print(f"VIX OPTIONS STRATEGY COMPARISON")
    print(f"Data period: {min(dates).strftime('%Y-%m-%d')} to {max(dates).strftime('%Y-%m-%d')} ({years:.1f} years)")
    print(f"{'='*80}\n")

    strategies = {}

    # Run all strategies
    print("Running strategies...")

    print("  [0] Baseline: Monthly Call Spreads (+10/+20)")
    strategies['0_Baseline'] = baseline_call_spreads(df)

    print("  [1] Juice 1: VIX-Scaled Sizing")
    strategies['1_VIX_Scaled'] = juice1_vix_scaled(df)

    print("  [2] Juice 2: Tight Spreads When VIX High")
    strategies['2_Tight_High'] = juice2_tight_when_high(df)

    print("  [3] Juice 3: Twice-Monthly Entries")
    strategies['3_Twice_Monthly'] = juice3_twice_monthly(df)

    print("  [4] Juice 4: Post-Spike Bonus")
    strategies['4_Post_Spike'] = juice4_post_spike(df)

    print("  [5] Juice 5: Long Puts After Spikes")
    strategies['5_Long_Puts'] = juice5_long_puts(df)

    print("  [6] Juice 6: Wider Spread (+10/+25)")
    strategies['6_Wider'] = juice6_wider_spread(df)

    print("  [B] BUNDLE: Combined (1 + 4 + 5)")
    strategies['B_BUNDLE'] = bundle_combined(df)

    print("  [O] OPTIMIZED: Twice-Monthly + Post-Spike")
    strategies['O_OPTIMIZED'] = bundle_optimized(df)

    print("  [X] BEST: Twice-Monthly + Tight When High")
    strategies['X_BEST'] = bundle_twice_monthly_tight(df)

    # Analyze all strategies
    print("\n")
    print("="*100)
    print("INDIVIDUAL STRATEGY RESULTS")
    print("="*100)
    print(f"\n{'Strategy':<30} {'Trades':>7} {'Win%':>7} {'Total P&L':>12} {'Max Cap':>10} {'Ann.Ret':>10}")
    print("-"*100)

    results_summary = []
    for key, res_df in strategies.items():
        stats = analyze_strategy(res_df, key, years)
        if stats:
            results_summary.append(stats)
            print(f"{stats['name']:<30} {stats['trades']:>7} {stats['win_rate']:>6.1f}% ${stats['total_pnl']:>10,.0f} ${stats['max_capital']:>9,.0f} {stats['annual_return']:>9.1f}%")

    # Detailed breakdown
    print("\n")
    print("="*100)
    print("DETAILED STATISTICS")
    print("="*100)
    print(f"\n{'Strategy':<30} {'Avg Win':>10} {'Avg Loss':>10} {'Max Loss':>10} {'Max Win':>10}")
    print("-"*100)

    for stats in results_summary:
        print(f"{stats['name']:<30} ${stats['avg_win']:>9,.0f} ${stats['avg_loss']:>9,.0f} ${stats['max_loss_trade']:>9,.0f} ${stats['max_win_trade']:>9,.0f}")

    # Bundle breakdown
    print("\n")
    print("="*100)
    print("BUNDLE BREAKDOWN (1 + 4 + 5)")
    print("="*100)

    bundle = strategies['B_BUNDLE']
    if len(bundle) > 0:
        for component in bundle['strategy_component'].unique():
            comp_df = bundle[bundle['strategy_component'] == component]
            comp_pnl = comp_df['pnl'].sum()
            comp_trades = len(comp_df)
            comp_wins = (comp_df['pnl'] > 0).sum()
            comp_win_rate = 100 * comp_wins / comp_trades if comp_trades > 0 else 0
            print(f"  {component:<25}: {comp_trades:>4} trades, {comp_win_rate:>5.1f}% win rate, ${comp_pnl:>10,.0f} P&L")

        total_bundle_pnl = bundle['pnl'].sum()
        total_bundle_trades = len(bundle)
        max_cap = bundle['capital_at_risk'].max() if 'capital_at_risk' in bundle.columns else 3000
        bundle_annual = (total_bundle_pnl / max_cap / years) * 100
        print(f"\n  BUNDLE TOTAL: {total_bundle_trades} trades, ${total_bundle_pnl:,.0f} P&L")
        print(f"  Max capital at risk: ${max_cap:,.0f}")
        print(f"  Annualized return: {bundle_annual:.1f}%")

    # Comparison vs baseline
    print("\n")
    print("="*100)
    print("COMPARISON VS BASELINE (25% strategy)")
    print("="*100)

    baseline_stats = next((s for s in results_summary if s['name'] == '0_Baseline'), None)
    if baseline_stats:
        baseline_ret = baseline_stats['annual_return']
        print(f"\nBaseline annual return: {baseline_ret:.1f}%\n")
        print(f"{'Strategy':<30} {'Ann.Ret':>10} {'vs Baseline':>15} {'Risk-Adj':>15}")
        print("-"*70)

        for stats in results_summary:
            diff = stats['annual_return'] - baseline_ret
            risk_ratio = stats['annual_return'] / (stats['max_capital'] / baseline_stats['max_capital']) if stats['max_capital'] > 0 else 0
            sign = '+' if diff >= 0 else ''
            print(f"{stats['name']:<30} {stats['annual_return']:>9.1f}% {sign}{diff:>14.1f}% {risk_ratio:>14.1f}%")

    return strategies, results_summary


if __name__ == "__main__":
    import sys

    # Default path - adjust as needed
    file_path = sys.argv[1] if len(sys.argv) > 1 else "raw vix option data 2010 to Aug 2022.csv"

    print(f"Loading data from {file_path}...")
    df = load_options_data(file_path)
    print(f"Loaded {len(df):,} rows")

    strategies, summary = run_all_strategies(df)
