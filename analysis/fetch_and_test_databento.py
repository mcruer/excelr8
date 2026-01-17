#!/usr/bin/env python3
"""
Fetch VIX options data from Databento and test the staggered absolute strategy.

Usage:
    pip install databento pandas numpy
    python fetch_and_test_databento.py

You'll need to set your Databento API key below or as an environment variable.
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# =============================================================================
# CONFIGURATION
# =============================================================================

# Set your API key here or use environment variable DATABENTO_API_KEY
API_KEY = os.environ.get("DATABENTO_API_KEY", "db-x5MB8c3vCxjin5s8CeARFrWAEBenb")

# Date range for data (3 years)
END_DATE = datetime.now().strftime("%Y-%m-%d")
START_DATE = (datetime.now() - timedelta(days=3*365)).strftime("%Y-%m-%d")

# Output file for cached data
OUTPUT_FILE = "vix_options_databento.csv"

# =============================================================================
# FETCH DATA FROM DATABENTO
# =============================================================================

def fetch_vix_options(api_key, start_date, end_date):
    """Fetch VIX options data from Databento"""
    import databento as db

    print(f"Connecting to Databento...")
    client = db.Historical(api_key)

    # VIX options are on CBOE - dataset is OPRA for US options
    # The symbol for VIX options is "VIX" with option suffixes
    # We need end-of-day data with bid/ask

    print(f"Fetching VIX options data from {start_date} to {end_date}...")
    print("This may take a few minutes and will use your Databento credits...")

    # Try OPRA dataset for options (includes CBOE)
    # Schema: Use 'ohlcv-1d' for daily data or 'tbbo' for best bid/offer
    try:
        # First, let's check available datasets
        datasets = client.metadata.list_datasets()
        print(f"\nAvailable datasets: {datasets[:10]}...")

        # Look for CBOE or options datasets
        opra_datasets = [d for d in datasets if 'OPRA' in d.upper() or 'CBOE' in d.upper()]
        print(f"Options-related datasets: {opra_datasets}")

        # For VIX options, we likely need OPRA.PILLAR or similar
        # Let's try to get the data
        data = client.timeseries.get_range(
            dataset="OPRA.PILLAR",  # OPRA is the options price reporting authority
            symbols=["VIX*.C*", "VIX*.P*"],  # All VIX calls and puts
            schema="ohlcv-1d",  # Daily OHLCV
            start=start_date,
            end=end_date,
        )

        df = data.to_df()
        print(f"Fetched {len(df):,} rows")
        return df

    except Exception as e:
        print(f"Error with OPRA.PILLAR: {e}")
        print("\nTrying alternative approach...")

        # Try listing available symbols for VIX
        try:
            # Check what's available
            publishers = client.metadata.list_publishers()
            print(f"Publishers: {publishers[:5]}...")

            # Try CBOE directly
            data = client.timeseries.get_range(
                dataset="CBOE.FUTURES",  # Try CBOE futures (VIX futures)
                symbols=["VX*"],
                schema="ohlcv-1d",
                start=start_date,
                end=end_date,
            )
            df = data.to_df()
            print(f"Fetched {len(df):,} rows from CBOE.FUTURES")
            return df

        except Exception as e2:
            print(f"Error with CBOE.FUTURES: {e2}")

            # Last resort - try to get any VIX-related data
            print("\nAttempting to list available datasets for reference...")
            try:
                for ds in datasets:
                    if 'VIX' in ds.upper() or 'CBOE' in ds.upper() or 'OPT' in ds.upper():
                        print(f"  Potentially relevant: {ds}")
            except:
                pass

            return None


def fetch_vix_spot(api_key, start_date, end_date):
    """Fetch VIX spot/index data as fallback"""
    import databento as db

    client = db.Historical(api_key)

    try:
        # Try to get VIX index data
        data = client.timeseries.get_range(
            dataset="CBOE.STREAMING",
            symbols=["VIX.XO"],  # VIX index
            schema="ohlcv-1d",
            start=start_date,
            end=end_date,
        )
        return data.to_df()
    except Exception as e:
        print(f"Could not fetch VIX spot: {e}")
        return None


# =============================================================================
# STRATEGY BACKTEST (same as staggered_absolute_strategy.py)
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

    cagr = (final_capital / starting_capital) ** (1/years) - 1 if years > 0 else 0

    peak = trades['capital_after'].iloc[0]
    max_dd = 0
    for cap in trades['capital_after']:
        peak = max(peak, cap)
        dd = (peak - cap) / peak
        max_dd = max(max_dd, dd)

    print(f"""
================================================================================
STAGGERED ABSOLUTE STRATEGY RESULTS (35/45 spread, 60-100 DTE, 3 positions)
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
        print("-"*70)
        for _, row in losers.iterrows():
            print(f"  {row['entry_date'].strftime('%Y-%m-%d')} -> {row['exit_date'].strftime('%Y-%m-%d')}: "
                  f"VIX {row['vix_entry']:.1f} -> {row['vix_exp']:.1f}, "
                  f"{row['contracts']} contracts, ${row['total_pnl']:,.0f}")
    else:
        print("\nNo losing trades in this period!")


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("="*80)
    print("VIX OPTIONS STRATEGY TESTER - DATABENTO")
    print("="*80)
    print(f"\nFetching data from {START_DATE} to {END_DATE}...")

    # Try to fetch data
    df = fetch_vix_options(API_KEY, START_DATE, END_DATE)

    if df is None or len(df) == 0:
        print("\n" + "="*80)
        print("COULD NOT FETCH OPTIONS DATA")
        print("="*80)
        print("""
Databento may not have VIX options in the expected format.

ALTERNATIVES:
1. Check Databento's documentation for the correct dataset/schema for CBOE VIX options
2. Use their web interface to browse available data
3. Contact Databento support for the correct symbols

The dataset you need is likely one of:
- OPRA.PILLAR (US options)
- CBOE.* (CBOE-specific data)

Symbols for VIX options typically look like:
- VIX 230118C00025000 (VIX Jan 18 2023 25 Call)
""")
        return

    # If we got data, process it
    print(f"\nLoaded {len(df):,} rows")
    print(f"Columns: {df.columns.tolist()}")
    print(f"\nSample data:")
    print(df.head())

    # Save to CSV for future use
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved data to {OUTPUT_FILE}")

    # Transform data to expected format if needed
    # (This depends on what Databento returns - may need adjustment)

    # Run backtest
    print("\n" + "="*80)
    print("RUNNING STRATEGY BACKTEST")
    print("="*80)

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
        analyze_results(trades, starting_capital=40000)
    else:
        print("No trades were executed. Check data format.")

    if len(remaining) > 0:
        print(f"\nNote: {len(remaining)} positions still open at end of data")


if __name__ == "__main__":
    main()
