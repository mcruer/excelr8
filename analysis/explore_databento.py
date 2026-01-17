#!/usr/bin/env python3
"""
Explore what VIX data is available on Databento.

Run this first to discover the correct dataset and schema,
then we can fetch and backtest.

Usage:
    pip install databento
    python explore_databento.py
"""

import os
import databento as db

API_KEY = os.environ.get("DATABENTO_API_KEY", "db-x5MB8c3vCxjin5s8CeARFrWAEBenb")

def main():
    print("="*80)
    print("DATABENTO DATA EXPLORATION")
    print("="*80)

    client = db.Historical(API_KEY)

    # 1. List all datasets
    print("\n1. AVAILABLE DATASETS")
    print("-"*40)
    try:
        datasets = client.metadata.list_datasets()
        for ds in sorted(datasets):
            # Highlight potentially relevant ones
            if any(x in ds.upper() for x in ['CBOE', 'OPT', 'VIX', 'OPRA']):
                print(f"  *** {ds} ***")
            else:
                print(f"      {ds}")
    except Exception as e:
        print(f"Error: {e}")
        return

    # 2. For each relevant dataset, check schemas
    print("\n2. CHECKING SCHEMAS FOR OPTIONS DATASETS")
    print("-"*40)

    options_datasets = [ds for ds in datasets
                        if any(x in ds.upper() for x in ['CBOE', 'OPRA', 'OPT'])]

    for ds in options_datasets[:5]:  # Check first 5
        try:
            schemas = client.metadata.list_schemas(dataset=ds)
            print(f"\n{ds}:")
            for schema in schemas:
                print(f"    {schema}")
        except Exception as e:
            print(f"\n{ds}: Error - {e}")

    # 3. Try to find VIX symbols
    print("\n3. SEARCHING FOR VIX SYMBOLS")
    print("-"*40)

    for ds in options_datasets[:3]:
        try:
            # Try different VIX symbol patterns
            for pattern in ["VIX*", "VX*", "$VIX*"]:
                try:
                    symbols = client.metadata.list_symbols(
                        dataset=ds,
                        symbol=pattern
                    )
                    if symbols:
                        print(f"\n{ds} - Pattern '{pattern}':")
                        for sym in symbols[:10]:
                            print(f"    {sym}")
                        if len(symbols) > 10:
                            print(f"    ... and {len(symbols)-10} more")
                except:
                    pass
        except Exception as e:
            print(f"{ds}: Error - {e}")

    # 4. Check cost estimate for a small data pull
    print("\n4. COST ESTIMATE FOR VIX OPTIONS (if found)")
    print("-"*40)

    try:
        # Try to get cost for OPRA VIX options
        cost = client.metadata.get_cost(
            dataset="OPRA.PILLAR",
            symbols=["VIX*"],
            schema="trades",
            start="2024-01-01",
            end="2024-01-31",
        )
        print(f"OPRA.PILLAR VIX* for Jan 2024: ${cost:.2f}")
    except Exception as e:
        print(f"Could not estimate cost: {e}")

    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)
    print("""
1. Look for a dataset containing VIX options (CBOE or OPRA)
2. Find the correct symbol format (e.g., 'VIX 240119C00035000')
3. Choose schema: 'ohlcv-1d' for daily or 'tbbo' for bid/ask
4. Update fetch_and_test_databento.py with correct parameters
5. Run the fetch and backtest

If VIX OPTIONS aren't available, you could:
- Use VIX futures (VX) as a proxy
- Contact Databento support for guidance
""")


if __name__ == "__main__":
    main()
