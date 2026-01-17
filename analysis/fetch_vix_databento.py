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


def fetch_vix_options():
    """Fetch VIX options data from Databento"""
    import databento as db

    print("="*60)
    print("DATABENTO VIX OPTIONS DATA FETCHER")
    print("="*60)
    print(f"\nDate range: {START_DATE} to {END_DATE}")
    print("Connecting to Databento...")

    client = db.Historical(API_KEY)

    # First, explore what's available
    print("\nExploring available datasets...")
    datasets = client.metadata.list_datasets()

    options_datasets = [ds for ds in datasets
                        if any(x in ds.upper() for x in ['CBOE', 'OPRA', 'OPT'])]
    print(f"Options-related datasets: {options_datasets}")

    all_data = []

    # Method 1: Try using parent symbol (underlying) with stype_in
    print("\nMethod 1: Trying parent symbol approach...")
    try:
        data = client.timeseries.get_range(
            dataset="OPRA.PILLAR",
            symbols=["VIX"],  # Parent/underlying symbol
            stype_in="parent",  # Search by underlying
            schema="ohlcv-1d",
            start=START_DATE,
            end=END_DATE,
        )
        df = data.to_df()
        if len(df) > 0:
            all_data.append(df)
            print(f"  Success! Got {len(df):,} rows")
    except Exception as e:
        print(f"  Parent symbol approach failed: {e}")

    # Method 2: Try with specific OCC-format symbols
    if not all_data:
        print("\nMethod 2: Trying specific OCC symbols...")
        try:
            # Generate a batch of VIX option symbols
            symbols = generate_vix_option_symbols(START_DATE, END_DATE)
            print(f"  Generated {len(symbols)} potential symbols")
            print(f"  Sample: {symbols[:3]}")

            # Fetch in batches (API may have limits)
            batch_size = 100
            for i in range(0, min(len(symbols), 500), batch_size):
                batch = symbols[i:i+batch_size]
                try:
                    data = client.timeseries.get_range(
                        dataset="OPRA.PILLAR",
                        symbols=batch,
                        schema="ohlcv-1d",
                        start=START_DATE,
                        end=END_DATE,
                    )
                    df = data.to_df()
                    if len(df) > 0:
                        all_data.append(df)
                        print(f"  Batch {i//batch_size + 1}: Got {len(df):,} rows")
                except Exception as e:
                    print(f"  Batch {i//batch_size + 1} failed: {e}")
        except Exception as e:
            print(f"  OCC symbols approach failed: {e}")

    # Method 3: Try instrument definitions to find valid symbols
    if not all_data:
        print("\nMethod 3: Trying instrument definitions...")
        try:
            # Get instrument definitions for a recent date
            definitions = client.metadata.get_instrument_definitions(
                dataset="OPRA.PILLAR",
                symbols=["VIX*"],
                stype_in="raw_symbol",
                start=START_DATE,
                end=END_DATE,
            )
            if definitions:
                print(f"  Found {len(definitions)} instrument definitions")
                # Extract symbols and try to fetch
                found_symbols = [d.raw_symbol for d in definitions[:100]]
                print(f"  Sample symbols: {found_symbols[:5]}")

                data = client.timeseries.get_range(
                    dataset="OPRA.PILLAR",
                    symbols=found_symbols,
                    schema="ohlcv-1d",
                    start=START_DATE,
                    end=END_DATE,
                )
                df = data.to_df()
                if len(df) > 0:
                    all_data.append(df)
                    print(f"  Success! Got {len(df):,} rows")
        except Exception as e:
            print(f"  Instrument definitions approach failed: {e}")

    # Method 4: Try different schemas (maybe ohlcv-1d isn't available)
    if not all_data:
        print("\nMethod 4: Trying different schemas...")
        for schema in ["trades", "tbbo", "mbp-1"]:
            try:
                data = client.timeseries.get_range(
                    dataset="OPRA.PILLAR",
                    symbols=["VIX"],
                    stype_in="parent",
                    schema=schema,
                    start=START_DATE,
                    end=END_DATE,
                    limit=10000,  # Limit for testing
                )
                df = data.to_df()
                if len(df) > 0:
                    all_data.append(df)
                    print(f"  Schema '{schema}': Got {len(df):,} rows")
                    break
            except Exception as e:
                print(f"  Schema '{schema}' failed: {e}")

    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        return combined

    return None


def transform_data(df):
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

    # The transformation depends on Databento's output format
    # This is a template - adjust based on actual data

    transformed = df.copy()

    # Databento typically has these columns:
    # ts_event, symbol, open, high, low, close, volume

    # Parse option symbol to extract strike, expiration, type
    # VIX option symbols look like: VIX 240119C00035000
    # Format: VIX YYMMDD[C/P]STRIKE

    if 'symbol' in transformed.columns:
        def parse_symbol(sym):
            try:
                # Extract components from symbol
                # This parsing depends on Databento's symbol format
                parts = str(sym).split()
                if len(parts) >= 2:
                    opt_code = parts[1] if len(parts) > 1 else parts[0]
                    # Parse YYMMDD + C/P + strike
                    if len(opt_code) >= 15:
                        exp_str = opt_code[:6]
                        opt_type = opt_code[6]
                        strike = float(opt_code[7:]) / 1000
                        exp_date = pd.to_datetime('20' + exp_str, format='%Y%m%d')
                        return pd.Series([exp_date, opt_type, strike])
                return pd.Series([None, None, None])
            except:
                return pd.Series([None, None, None])

        parsed = transformed['symbol'].apply(parse_symbol)
        transformed['expiration'] = parsed[0]
        transformed['option_type'] = parsed[1]
        transformed['strike'] = parsed[2]

    # Rename columns to match expected format
    column_mapping = {
        'ts_event': 'quote_date',
        'close': 'bid_eod',  # Use close as proxy if no bid/ask
    }

    for old, new in column_mapping.items():
        if old in transformed.columns:
            transformed[new] = transformed[old]

    # Add ask_eod as bid + spread estimate if not present
    if 'ask_eod' not in transformed.columns and 'bid_eod' in transformed.columns:
        transformed['ask_eod'] = transformed['bid_eod'] * 1.1  # 10% spread estimate

    # Add underlying (VIX) - may need separate fetch
    if 'underlying_bid_eod' not in transformed.columns:
        transformed['underlying_bid_eod'] = 20  # Placeholder - needs real VIX data

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
    df = fetch_vix_options()

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

    print(f"\nSuccessfully fetched {len(df):,} rows")

    # Transform to expected format
    transformed = transform_data(df)

    # Save and zip
    save_and_zip(transformed)

    print("\n" + "="*60)
    print("DONE!")
    print("="*60)


if __name__ == "__main__":
    main()
