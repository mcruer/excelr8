#!/usr/bin/env python3
"""
Fetch VIX options data from Databento and save to CSV (zipped).

Usage:
    pip install databento pandas
    python fetch_vix_databento.py

Output:
    vix_options_databento.csv.zip - Upload this to the repo
"""

import os
import zipfile
import pandas as pd
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# =============================================================================
# CONFIGURATION
# =============================================================================

API_KEY = open(r"C:\Users\McRuersG\OneDrive - Government of Ontario\Desktop\Temp\All Plain Interface.txt").read().strip()

# 3 years of data
END_DATE = datetime.now().strftime("%Y-%m-%d")
START_DATE = (datetime.now() - timedelta(days=3*365)).strftime("%Y-%m-%d")

OUTPUT_CSV = "vix_options_databento.csv"
OUTPUT_ZIP = "vix_options_databento.csv.zip"

# =============================================================================
# FETCH DATA
# =============================================================================

def generate_vix_option_symbols(start_date, end_date):
    """
    Generate OCC-format VIX option symbols for common strikes.
    OCC format: VIX   YYMMDDCSSSSSSSS (6-char root, date, C/P, 8-digit strike*1000)
    """
    symbols = []

    # Parse dates
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    # Generate monthly expirations (3rd Wednesday typically, but we'll approximate)
    current = start
    while current <= end + relativedelta(months=6):  # Include some future expirations
        # VIX options expire on Wednesday, roughly mid-month
        # Use 15th as approximation, adjust to nearest Wednesday
        exp_date = current.replace(day=15)

        # Format as YYMMDD
        exp_str = exp_date.strftime("%y%m%d")

        # Common VIX strikes: 15, 20, 25, 30, 35, 40, 45, 50
        for strike in [15, 20, 25, 30, 35, 40, 45, 50]:
            # Strike is multiplied by 1000 and zero-padded to 8 digits
            strike_str = f"{strike * 1000:08d}"

            # Generate call and put symbols
            # OCC format: ROOT(6) + YYMMDD + C/P + STRIKE(8)
            for opt_type in ['C', 'P']:
                symbol = f"VIX   {exp_str}{opt_type}{strike_str}"
                symbols.append(symbol)

        current += relativedelta(months=1)

    return symbols


def fetch_vix_spot(client):
    """Fetch VIX spot/index data for underlying prices"""
    print("\nFetching VIX spot data...")
    try:
        # Try CBOE dataset for VIX index
        data = client.timeseries.get_range(
            dataset="CBOE.STREAMING",
            symbols=["VIX"],
            schema="ohlcv-1d",
            start=START_DATE,
            end=END_DATE,
        )
        df = data.to_df()
        if len(df) > 0:
            print(f"  Got {len(df):,} VIX spot rows")
            return df
    except Exception as e:
        print(f"  CBOE.STREAMING failed: {e}")

    # Alternative: try different dataset
    try:
        data = client.timeseries.get_range(
            dataset="DBEQ.BASIC",
            symbols=["VIX"],
            schema="ohlcv-1d",
            start=START_DATE,
            end=END_DATE,
        )
        df = data.to_df()
        if len(df) > 0:
            print(f"  Got {len(df):,} VIX spot rows from DBEQ")
            return df
    except Exception as e:
        print(f"  DBEQ.BASIC failed: {e}")

    print("  Could not fetch VIX spot - will use placeholder")
    return None


def fetch_vix_options():
    """Fetch VIX options data from Databento using VIX.OPT parent symbol"""
    import databento as db

    print("="*60)
    print("DATABENTO VIX OPTIONS DATA FETCHER")
    print("="*60)
    print(f"\nDate range: {START_DATE} to {END_DATE}")
    print("Connecting to Databento...")

    client = db.Historical(API_KEY)

    # Use correct parent symbol format: VIX.OPT for VIX options
    # Per error message: expected format '[ROOT].SPOT', '[ROOT].FUT', or '[ROOT].OPT'
    print("\nFetching VIX options using 'VIX.OPT' parent symbol...")
    try:
        data = client.timeseries.get_range(
            dataset="OPRA.PILLAR",
            symbols=["VIX.OPT"],  # Correct format for options
            stype_in="parent",
            schema="ohlcv-1d",
            start=START_DATE,
            end=END_DATE,
        )
        df = data.to_df()
        if len(df) > 0:
            print(f"  Success! Got {len(df):,} rows")

            # Also try to get VIX spot for underlying prices
            vix_spot = fetch_vix_spot(client)

            return df, vix_spot
        else:
            print("  No data returned")
    except Exception as e:
        print(f"  Failed: {e}")

    return None, None


def transform_data(df, vix_spot=None):
    """
    Transform Databento data to match the expected format:
    - quote_date: date of the quote
    - expiration: option expiration date
    - strike: strike price
    - option_type: 'C' or 'P'
    - bid_eod: end of day bid
    - ask_eod: end of day ask
    - underlying_bid_eod: VIX level
    """
    print("\nTransforming data to expected format...")
    print(f"Original columns: {df.columns.tolist()}")
    print(f"Original shape: {df.shape}")
    print(f"\nSample data:")
    print(df.head())

    transformed = df.copy()

    # Reset index to get ts_event as a column
    if transformed.index.name == 'ts_event' or 'ts_event' not in transformed.columns:
        transformed = transformed.reset_index()

    # Parse option symbol to extract strike, expiration, type
    # VIX option symbols look like: VIX   240119C00035000
    # Format: ROOT(6) + YYMMDD + C/P + STRIKE(8)

    if 'symbol' in transformed.columns:
        def parse_symbol(sym):
            try:
                sym = str(sym).strip()
                # Find the date/type/strike portion after root
                # Look for 6 digits followed by C or P
                import re
                match = re.search(r'(\d{6})([CP])(\d{8})', sym)
                if match:
                    exp_str = match.group(1)
                    opt_type = match.group(2)
                    strike = float(match.group(3)) / 1000
                    exp_date = pd.to_datetime('20' + exp_str, format='%Y%m%d')
                    return pd.Series([exp_date, opt_type, strike])
                return pd.Series([None, None, None])
            except:
                return pd.Series([None, None, None])

        parsed = transformed['symbol'].apply(parse_symbol)
        transformed['expiration'] = parsed[0]
        transformed['option_type'] = parsed[1]
        transformed['strike'] = parsed[2]

    # Extract quote_date from ts_event
    if 'ts_event' in transformed.columns:
        transformed['quote_date'] = pd.to_datetime(transformed['ts_event']).dt.date
        transformed['quote_date'] = pd.to_datetime(transformed['quote_date'])

    # Use close as mid-price estimate, then derive bid/ask
    # Typical VIX option spread is ~$0.10-0.30 depending on liquidity
    if 'close' in transformed.columns:
        transformed['mid_price'] = transformed['close']
        # Estimate 5% bid-ask spread (conservative for VIX options)
        transformed['bid_eod'] = transformed['mid_price'] * 0.975
        transformed['ask_eod'] = transformed['mid_price'] * 1.025

    # Merge VIX spot data for underlying prices
    if vix_spot is not None and len(vix_spot) > 0:
        print("\nMerging VIX spot data...")
        vix_spot = vix_spot.reset_index()
        if 'ts_event' in vix_spot.columns:
            vix_spot['quote_date'] = pd.to_datetime(vix_spot['ts_event']).dt.date
            vix_spot['quote_date'] = pd.to_datetime(vix_spot['quote_date'])
        vix_spot = vix_spot[['quote_date', 'close']].rename(columns={'close': 'underlying_bid_eod'})
        vix_spot = vix_spot.drop_duplicates('quote_date')
        transformed = transformed.merge(vix_spot, on='quote_date', how='left')
        print(f"  Matched {transformed['underlying_bid_eod'].notna().sum()} rows with VIX spot")
    else:
        # No VIX spot data - leave as NaN (test script will need to handle)
        transformed['underlying_bid_eod'] = None
        print("  No VIX spot data - underlying_bid_eod will be None")

    # Drop rows where we couldn't parse the option
    before = len(transformed)
    transformed = transformed.dropna(subset=['expiration', 'strike', 'option_type'])
    after = len(transformed)
    if before != after:
        print(f"  Dropped {before - after} rows with unparseable symbols")

    print(f"\nTransformed columns: {transformed.columns.tolist()}")
    print(f"Transformed shape: {transformed.shape}")

    return transformed


def save_and_zip(df):
    """Save to CSV and zip it"""
    print(f"\nSaving to {OUTPUT_CSV}...")
    df.to_csv(OUTPUT_CSV, index=False)

    print(f"Zipping to {OUTPUT_ZIP}...")
    with zipfile.ZipFile(OUTPUT_ZIP, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(OUTPUT_CSV)

    # Get file sizes
    csv_size = os.path.getsize(OUTPUT_CSV) / (1024*1024)
    zip_size = os.path.getsize(OUTPUT_ZIP) / (1024*1024)

    print(f"\nFiles created:")
    print(f"  {OUTPUT_CSV}: {csv_size:.1f} MB")
    print(f"  {OUTPUT_ZIP}: {zip_size:.1f} MB")

    # Clean up CSV (keep only zip)
    os.remove(OUTPUT_CSV)
    print(f"\nRemoved {OUTPUT_CSV}, kept {OUTPUT_ZIP}")
    print(f"\n>>> Upload {OUTPUT_ZIP} to the repo <<<")


def main():
    df, vix_spot = fetch_vix_options()

    if df is None or len(df) == 0:
        print("\n" + "="*60)
        print("FAILED TO FETCH DATA")
        print("="*60)
        print("""
Could not fetch VIX options data from Databento.

Please check:
1. API key is valid
2. You have credits available
3. The correct dataset/schema for VIX options

You may need to:
- Contact Databento support for the correct dataset
- Use their web interface to download manually
- Try different symbol patterns
""")
        return

    print(f"\nSuccessfully fetched {len(df):,} option rows")
    if vix_spot is not None:
        print(f"Also fetched {len(vix_spot):,} VIX spot rows")

    # Transform to expected format
    transformed = transform_data(df, vix_spot)

    # Save and zip
    save_and_zip(transformed)

    print("\n" + "="*60)
    print("DONE!")
    print("="*60)


if __name__ == "__main__":
    main()
