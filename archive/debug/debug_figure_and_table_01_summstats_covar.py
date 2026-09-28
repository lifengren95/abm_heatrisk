#!/usr/bin/env python3
"""
Debug script to investigate why age variables are missing
"""

import numpy as np
import pandas as pd
import geopandas as gpd
import pickle
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')


def investigate_age_columns():
    """Investigate the age-related columns in the parcel data"""
    
    print("="*60)
    print("INVESTIGATING AGE DATA ISSUE")
    print("="*60)
    
    # Load parcel data
    parcels_path = r"~\hennepin\data\preprocessed_data\parcels_prepared.pkl"
    
    print(f"\n1. Loading data from: {parcels_path}")
    with open(parcels_path, 'rb') as f:
        data = pickle.load(f)
    
    gdf = data['gdf']
    print(f"   Loaded {len(gdf)} parcels")
    
    # Check all columns
    print(f"\n2. All columns in the dataset:")
    for i, col in enumerate(gdf.columns, 1):
        print(f"   {i:3d}. {col}")
    
    # Check for age-related columns
    print(f"\n3. Looking for age-related columns:")
    age_columns_expected = ['pop_under_5', 'pop_5_17', 'pop_18_34', 'pop_35_64', 'pop_over_65', 'total_pop']
    age_columns_alt1 = ['ageunder18', 'age18_39', 'age40_64', 'age65up', 'poptotal']
    age_columns_alt2 = ['ageunder5', 'age5_17', 'age18_34', 'age35_64', 'age65up', 'poptotal']
    
    print("\n   Expected columns:")
    for col in age_columns_expected:
        exists = col in gdf.columns
        print(f"     {col}: {'✓ EXISTS' if exists else '✗ MISSING'}")
        if exists:
            non_null = gdf[col].notna().sum()
            print(f"       - Non-null values: {non_null}/{len(gdf)}")
            if non_null > 0:
                print(f"       - Sample values: {gdf[col].dropna().head(3).values}")
    
    print("\n   Alternative column names (set 1):")
    for col in age_columns_alt1:
        exists = col in gdf.columns
        print(f"     {col}: {'✓ EXISTS' if exists else '✗ MISSING'}")
        if exists:
            non_null = gdf[col].notna().sum()
            print(f"       - Non-null values: {non_null}/{len(gdf)}")
            if non_null > 0:
                print(f"       - Sample values: {gdf[col].dropna().head(3).values}")
    
    # Check data types
    print(f"\n4. Data types of existing age columns:")
    for col in gdf.columns:
        if any(age_word in col.lower() for age_word in ['age', 'pop', 'under', 'over', '18', '65', 'total']):
            print(f"   {col}: {gdf[col].dtype}")
            # Show statistics
            if gdf[col].dtype in ['float64', 'int64', 'float32', 'int32']:
                print(f"     - Min: {gdf[col].min()}")
                print(f"     - Max: {gdf[col].max()}")
                print(f"     - Mean: {gdf[col].mean():.2f}")
                print(f"     - Non-zero count: {(gdf[col] > 0).sum()}")
    
    # Sample a few rows to see actual data
    print(f"\n5. Sample data for first 3 parcels:")
    sample_cols = []
    for col in gdf.columns:
        if any(word in col.lower() for word in ['age', 'pop', 'under', 'over', 'total', 'elderly']):
            sample_cols.append(col)
    
    if sample_cols:
        print(f"   Columns found: {sample_cols}")
        print(gdf[sample_cols].head(3))
    else:
        print("   No age-related columns found!")
    
    # Check if block_group_id has data (might need to aggregate from census)
    if 'block_group_id' in gdf.columns:
        print(f"\n6. Block group data check:")
        non_null_bg = gdf['block_group_id'].notna().sum()
        print(f"   Block groups with data: {non_null_bg}/{len(gdf)}")
        if non_null_bg > 0:
            print(f"   Sample block group IDs: {gdf['block_group_id'].dropna().head(3).values}")
    
    # Try to find the actual age data pattern
    print(f"\n7. Searching for any numeric columns that might be age data:")
    numeric_cols = gdf.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        unique_vals = gdf[col].nunique()
        if unique_vals > 1 and unique_vals < 1000:  # Reasonable range for demographic data
            sample = gdf[col].dropna().head(5).values
            if len(sample) > 0 and np.all(sample >= 0):  # Non-negative values
                print(f"   {col}: unique values={unique_vals}, sample={sample}")
    
    return gdf


def test_fixed_age_calculation(gdf):
    """Test calculation with correct column names"""
    print(f"\n8. Testing age calculations with available columns:")
    
    # Find which columns actually exist
    actual_age_cols = []
    mapping = {}
    
    # Check for the alternative column names from the extraction script
    if 'ageunder18' in gdf.columns:
        print("   Found alternative column naming pattern!")
        mapping = {
            'pop_under_18': 'ageunder18',
            'pop_18_39': 'age18_39',
            'pop_40_64': 'age40_64',
            'pop_65up': 'age65up',
            'total_pop': 'poptotal'
        }
    elif 'pop_under_5' in gdf.columns:
        print("   Found expected column naming pattern!")
        mapping = {
            'pop_under_5': 'pop_under_5',
            'pop_5_17': 'pop_5_17',
            'pop_18_34': 'pop_18_34',
            'pop_35_64': 'pop_35_64',
            'pop_over_65': 'pop_over_65',
            'total_pop': 'total_pop'
        }
    else:
        print("   ✗ No recognized age column pattern found!")
        return
    
    # Calculate elderly percentage with available columns
    if 'age65up' in gdf.columns and 'poptotal' in gdf.columns:
        print("\n   Calculating elderly percentage using age65up/poptotal:")
        gdf['elderly_pct_calc'] = np.where(
            gdf['poptotal'] > 0,
            (gdf['age65up'] / gdf['poptotal']) * 100,
            np.nan
        )
        valid = gdf['elderly_pct_calc'].notna().sum()
        print(f"   ✓ Valid elderly % calculated: {valid}/{len(gdf)} parcels")
        if valid > 0:
            print(f"   Stats: Mean={gdf['elderly_pct_calc'].mean():.1f}%, Median={gdf['elderly_pct_calc'].median():.1f}%")
    
    # Calculate median age approximation
    if 'ageunder18' in gdf.columns and 'age18_39' in gdf.columns and 'age40_64' in gdf.columns and 'age65up' in gdf.columns:
        print("\n   Calculating median age approximation:")
        
        def calc_median_age_approx(row):
            try:
                # Use midpoints for broader age groups
                midpoints = {
                    'ageunder18': 9,    # 0-18
                    'age18_39': 28.5,   # 18-39
                    'age40_64': 52,     # 40-64
                    'age65up': 75       # 65+
                }
                
                total_pop = 0
                weighted_sum = 0
                
                for col, midpoint in midpoints.items():
                    pop = row.get(col, 0)
                    if pd.notna(pop) and pop > 0:
                        weighted_sum += pop * midpoint
                        total_pop += pop
                
                if total_pop > 0:
                    return weighted_sum / total_pop
                else:
                    return np.nan
            except:
                return np.nan
        
        gdf['median_age_calc'] = gdf.apply(calc_median_age_approx, axis=1)
        valid = gdf['median_age_calc'].notna().sum()
        print(f"   ✓ Valid median age calculated: {valid}/{len(gdf)} parcels")
        if valid > 0:
            print(f"   Stats: Mean={gdf['median_age_calc'].mean():.1f} years, Median={gdf['median_age_calc'].median():.1f} years")
    
    return gdf


if __name__ == "__main__":
    # Investigate the issue
    gdf = investigate_age_columns()
    
    # Test fixes
    gdf = test_fixed_age_calculation(gdf)
    
    print("\n" + "="*60)
    print("DIAGNOSIS COMPLETE")
    print("="*60)
    print("\nRecommendation: Update the main script to use the correct column names found above.")