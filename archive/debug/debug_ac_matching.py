#!/usr/bin/env python3
"""
Debug script to investigate AC data matching issues
"""

import pandas as pd
import pickle
from pathlib import Path
import os

def debug_ac_matching():
    """Debug why external AC data isn't matching with parcels"""
    
    print("=== AC DATA MATCHING DEBUG SCRIPT ===\n")
    
    # Set working directory
    code_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(code_dir)
    print(f"Working directory: {os.getcwd()}\n")
    
    # 1. Load external AC data
    print("1. Loading external AC data...")
    ac_path = "../../data/raw/Parcel_AC/hennepin_parcel_ac_avail.csv"
    
    try:
        # Read with REM_ACCT_NUM as string
        ac_df = pd.read_csv(ac_path, dtype={'REM_ACCT_NUM': str})
        print(f"   ✓ Loaded {len(ac_df)} AC records")
        
        # Show sample AC data
        print("\n   Sample AC data (first 5 rows):")
        print("   REM_ACCT_NUM values:")
        for i, val in enumerate(ac_df['REM_ACCT_NUM'].head()):
            print(f"   [{i}] '{val}' (type: {type(val).__name__}, length: {len(str(val))})")
        
        # Check for unique REM_ACCT_NUM formats
        print("\n   AC ID format analysis:")
        ac_ids = ac_df['REM_ACCT_NUM'].astype(str)
        print(f"   - Total unique IDs: {ac_ids.nunique()}")
        print(f"   - Min length: {ac_ids.str.len().min()}")
        print(f"   - Max length: {ac_ids.str.len().max()}")
        print(f"   - Most common lengths: {ac_ids.str.len().value_counts().head()}")
        
        # Check if any have leading zeros
        leading_zero_count = ac_ids.str.startswith('0').sum()
        print(f"   - IDs with leading zeros: {leading_zero_count}")
        
    except Exception as e:
        print(f"   ❌ Error loading AC data: {e}")
        return
    
    # 2. Load preprocessed parcel data
    print("\n2. Loading preprocessed parcel data...")
    parcels_file = Path("../../data/preprocessed_data/parcels_prepared.pkl")
    
    try:
        with open(parcels_file, 'rb') as f:
            parcels_data = pickle.load(f)
        
        gdf = parcels_data['gdf']
        print(f"   ✓ Loaded {len(gdf)} parcels")
        
        # Show sample parcel PIDs
        print("\n   Sample parcel PIDs (first 5):")
        for i, val in enumerate(gdf['pid'].head()):
            print(f"   [{i}] '{val}' (type: {type(val).__name__}, length: {len(str(val))})")
        
        # Check PID formats
        print("\n   Parcel PID format analysis:")
        pids = gdf['pid'].astype(str)
        print(f"   - Total unique PIDs: {pids.nunique()}")
        print(f"   - Min length: {pids.str.len().min()}")
        print(f"   - Max length: {pids.str.len().max()}")
        print(f"   - Most common lengths: {pids.str.len().value_counts().head()}")
        
        # Check if any have leading zeros
        leading_zero_count = pids.str.startswith('0').sum()
        print(f"   - PIDs with leading zeros: {leading_zero_count}")
        
    except Exception as e:
        print(f"   ❌ Error loading parcel data: {e}")
        return
    
    # 3. Test different matching strategies
    print("\n3. Testing matching strategies...")
    
    # Convert both to string for matching
    ac_ids_str = set(ac_df['REM_ACCT_NUM'].astype(str))
    pids_str = set(gdf['pid'].astype(str))
    
    # Strategy 1: Direct string match
    print("\n   Strategy 1: Direct string match")
    matches_direct = pids_str.intersection(ac_ids_str)
    print(f"   - Matches found: {len(matches_direct)}")
    if len(matches_direct) > 0:
        print(f"   - Sample matches: {list(matches_direct)[:5]}")
    
    # Strategy 2: Strip whitespace
    print("\n   Strategy 2: Strip whitespace")
    ac_ids_stripped = set(ac_df['REM_ACCT_NUM'].astype(str).str.strip())
    pids_stripped = set(gdf['pid'].astype(str).str.strip())
    matches_stripped = pids_stripped.intersection(ac_ids_stripped)
    print(f"   - Matches found: {len(matches_stripped)}")
    if len(matches_stripped) > 0:
        print(f"   - Sample matches: {list(matches_stripped)[:5]}")
    
    # Strategy 3: Remove leading zeros
    print("\n   Strategy 3: Remove leading zeros")
    ac_ids_no_zeros = set(ac_df['REM_ACCT_NUM'].astype(str).str.lstrip('0'))
    pids_no_zeros = set(gdf['pid'].astype(str).str.lstrip('0'))
    matches_no_zeros = pids_no_zeros.intersection(ac_ids_no_zeros)
    print(f"   - Matches found: {len(matches_no_zeros)}")
    if len(matches_no_zeros) > 0:
        print(f"   - Sample matches: {list(matches_no_zeros)[:5]}")
    
    # Strategy 4: Convert to integer (if possible)
    print("\n   Strategy 4: Convert to integer")
    try:
        # Try converting to int
        ac_ids_int = set()
        for val in ac_df['REM_ACCT_NUM']:
            try:
                ac_ids_int.add(int(val))
            except:
                pass
        
        pids_int = set()
        for val in gdf['pid']:
            try:
                pids_int.add(int(val))
            except:
                pass
        
        matches_int = pids_int.intersection(ac_ids_int)
        print(f"   - AC IDs convertible to int: {len(ac_ids_int)}")
        print(f"   - PIDs convertible to int: {len(pids_int)}")
        print(f"   - Matches found: {len(matches_int)}")
        if len(matches_int) > 0:
            print(f"   - Sample matches: {list(matches_int)[:5]}")
    except Exception as e:
        print(f"   - Error with integer conversion: {e}")
    
    # 4. Check for systematic differences
    print("\n4. Checking for systematic differences...")
    
    # Sample some values that don't match
    print("\n   Non-matching samples:")
    non_matching_pids = list(pids_str - ac_ids_str)[:5]
    non_matching_ac = list(ac_ids_str - pids_str)[:5]
    
    print(f"   PIDs not in AC data:")
    for pid in non_matching_pids:
        print(f"   - '{pid}'")
    
    print(f"\n   AC IDs not in parcel data:")
    for ac_id in non_matching_ac:
        print(f"   - '{ac_id}'")
    
    # 5. Check if there's a column name issue
    print("\n5. Checking all column names...")
    print(f"   AC data columns: {list(ac_df.columns)}")
    print(f"   Parcel data columns: {list(gdf.columns)[:10]}...")  # First 10 columns
    
    # Look for any column that might contain matching IDs
    print("\n6. Searching for potential ID columns in parcel data...")
    for col in gdf.columns:
        if col != 'geometry' and gdf[col].dtype in ['object', 'int64', 'float64']:
            try:
                # Check if this column has any matches with AC data
                col_values = set(gdf[col].astype(str).dropna())
                matches = col_values.intersection(ac_ids_str)
                if len(matches) > 0:
                    print(f"   ✓ Column '{col}' has {len(matches)} matches with AC data!")
                    print(f"     Sample matches: {list(matches)[:3]}")
            except:
                pass
    
    # 7. Final summary
    print("\n=== SUMMARY ===")
    print(f"External AC records: {len(ac_df)}")
    print(f"Parcel records: {len(gdf)}")
    print(f"Best matching strategy: ", end="")
    
    best_matches = max(len(matches_direct), len(matches_stripped), 
                      len(matches_no_zeros), len(matches_int) if 'matches_int' in locals() else 0)
    
    if best_matches == 0:
        print("NO MATCHES FOUND")
        print("\nPossible issues:")
        print("- The PID column in parcels doesn't match REM_ACCT_NUM format")
        print("- There might be a different column that should be used for matching")
        print("- The data might be from different sources/systems")
    else:
        if best_matches == len(matches_direct):
            print(f"Direct string match ({len(matches_direct)} matches)")
        elif best_matches == len(matches_stripped):
            print(f"Strip whitespace ({len(matches_stripped)} matches)")
        elif best_matches == len(matches_no_zeros):
            print(f"Remove leading zeros ({len(matches_no_zeros)} matches)")
        elif 'matches_int' in locals() and best_matches == len(matches_int):
            print(f"Integer conversion ({len(matches_int)} matches)")
    
    print("\n=== END DEBUG ===")


if __name__ == "__main__":
    debug_ac_matching()