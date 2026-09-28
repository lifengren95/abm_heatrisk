#!/usr/bin/env python3
"""
Cooling Center Catchment Analysis
Counts parcels and calculates demographics within various distances from each cooling center
Using the cooling center GPKG parcels as the base geometry
"""
import os

import pandas as pd
import geopandas as gpd
import numpy as np
import pickle
from pathlib import Path
import time
import warnings
import os
warnings.filterwarnings('ignore')

# Set environment variables to avoid PROJ issues
os.environ['PROJ_LIB'] = ''
os.environ['GDAL_DATA'] = ''

def analyze_cooling_center_catchments():
    """Main function to analyze catchment areas around cooling centers"""
    
    print("="*70)
    print("COOLING CENTER CATCHMENT AREA ANALYSIS")
    print("="*70)
    
    # File paths
    parcels_pkl = r"~\hennepin\data\preprocessed_data\parcels_prepared.pkl"
    cooling_gpkg = r"~\hennepin\data\validate_data\intermediate\cooling_center_with_buildyr.gpkg"
    output_csv = r"~\hennepin\data\validate_data\intermediate\cooling_center_with_buildyr_catchment.csv"
    
    # Distance thresholds in miles and meters
    distances_miles = [0.5, 1, 2, 4, 6, 8, 10]
    distances_meters = [miles * 1609.34 for miles in distances_miles]
    
    print("\n1. Loading data...")
    
    # Load main parcels data
    print("   Loading parcels from pickle file...")
    start_time = time.time()
    
    with open(parcels_pkl, 'rb') as f:
        parcel_data = pickle.load(f)
    
    parcels_gdf = parcel_data['gdf']
    print(f"   ✓ Loaded {len(parcels_gdf):,} parcels in {time.time()-start_time:.2f} seconds")
    
    # Load cooling center parcels with CRS handling
    print("   Loading cooling center parcels from GPKG...")
    
    try:
        # Try to read normally first
        cooling_centers = gpd.read_file(cooling_gpkg)
    except Exception as e:
        print(f"   ⚠ Standard read failed: {str(e)[:100]}...")
        print("   Trying alternative method...")
        
        # Alternative: Read with fiona and reconstruct
        import fiona
        from shapely.geometry import shape
        
        with fiona.open(cooling_gpkg, 'r') as src:
            # Get the CRS if available
            crs_wkt = src.crs_wkt if hasattr(src, 'crs_wkt') else None
            
            # Read features
            features = []
            geometries = []
            
            for feat in src:
                # Extract properties and geometry
                properties = dict(feat['properties'])
                geom = shape(feat['geometry'])
                
                features.append(properties)
                geometries.append(geom)
            
            # Create DataFrame
            cooling_centers = pd.DataFrame(features)
            
            # Add geometry to create GeoDataFrame
            cooling_centers = gpd.GeoDataFrame(
                cooling_centers, 
                geometry=geometries
            )
            
            # Try to set CRS if we have it, otherwise assume EPSG:26915
            try:
                if crs_wkt:
                    cooling_centers.set_crs(crs_wkt, inplace=True)
                else:
                    cooling_centers.set_crs('EPSG:26915', inplace=True)
            except:
                # If CRS setting fails, just leave it as None for now
                pass
    
    print(f"   ✓ Loaded {len(cooling_centers)} cooling center parcels")
    
    # Ensure both datasets have CRS set (use EPSG:26915 as default for Minnesota)
    print("\n2. Aligning coordinate systems...")
    
    # Set CRS for parcels if missing
    if parcels_gdf.crs is None:
        try:
            parcels_gdf.set_crs('EPSG:26915', inplace=True)
            print("   Set parcels CRS to EPSG:26915")
        except:
            print("   Warning: Could not set parcels CRS, continuing anyway")
    
    # Set CRS for cooling centers if missing
    if cooling_centers.crs is None:
        try:
            cooling_centers.set_crs('EPSG:26915', inplace=True)
            print("   Set cooling centers CRS to EPSG:26915")
        except:
            print("   Warning: Could not set cooling centers CRS, continuing anyway")
    
    # If both have CRS and they're different, convert
    if cooling_centers.crs and parcels_gdf.crs and cooling_centers.crs != parcels_gdf.crs:
        try:
            cooling_centers = cooling_centers.to_crs(parcels_gdf.crs)
            print(f"   ✓ Converted cooling centers to {parcels_gdf.crs}")
        except:
            print("   Warning: Could not convert CRS, continuing with mismatched CRS")
    
    # Calculate parcel centroids for spatial operations
    print("\n3. Preparing spatial data...")
    if 'centroid' not in parcels_gdf.columns:
        parcels_gdf['centroid'] = parcels_gdf.geometry.centroid
    
    # Create spatial index for parcels (speeds up spatial operations)
    try:
        parcels_sindex = parcels_gdf.sindex
        print("   ✓ Created spatial index for parcels")
        use_spatial_index = True
    except:
        print("   ⚠ Could not create spatial index, will use slower method")
        use_spatial_index = False
    
    # Initialize result columns
    print("\n4. Analyzing catchment areas for each cooling center...")
    
    # Create column names for each distance and metric
    result_columns = {}
    for miles in distances_miles:
        miles_str = str(miles).replace('.', '_')
        result_columns[f'parcels_within_{miles_str}miles'] = []
        result_columns[f'median_income_{miles_str}miles'] = []
        result_columns[f'avg_ac_ownership_{miles_str}miles'] = []
        result_columns[f'total_population_{miles_str}miles'] = []
        result_columns[f'pct_elderly_{miles_str}miles'] = []
    
    # Process each cooling center
    total = len(cooling_centers)
    
    for idx, cooling_center in cooling_centers.iterrows():
        if (idx + 1) % 10 == 0 or idx == 0:
            print(f"   Processing cooling center {idx+1}/{total}...")
        
        # Get the cooling center geometry
        center_geom = cooling_center.geometry
        
        # Skip if geometry is invalid
        if center_geom is None or center_geom.is_empty:
            print(f"   ⚠ Skipping cooling center {idx+1} - invalid geometry")
            for miles in distances_miles:
                miles_str = str(miles).replace('.', '_')
                result_columns[f'parcels_within_{miles_str}miles'].append(0)
                result_columns[f'median_income_{miles_str}miles'].append(np.nan)
                result_columns[f'avg_ac_ownership_{miles_str}miles'].append(np.nan)
                result_columns[f'total_population_{miles_str}miles'].append(0)
                result_columns[f'pct_elderly_{miles_str}miles'].append(np.nan)
            continue
        
        # For each distance threshold
        for miles, meters in zip(distances_miles, distances_meters):
            miles_str = str(miles).replace('.', '_')
            
            # Create buffer around cooling center
            try:
                buffer = center_geom.buffer(meters)
            except Exception as e:
                print(f"   ⚠ Could not create buffer for center {idx+1}: {e}")
                result_columns[f'parcels_within_{miles_str}miles'].append(0)
                result_columns[f'median_income_{miles_str}miles'].append(np.nan)
                result_columns[f'avg_ac_ownership_{miles_str}miles'].append(np.nan)
                result_columns[f'total_population_{miles_str}miles'].append(0)
                result_columns[f'pct_elderly_{miles_str}miles'].append(np.nan)
                continue
            
            # Find parcels within buffer
            if use_spatial_index:
                # Use spatial index for efficiency
                possible_matches_index = list(parcels_sindex.intersection(buffer.bounds))
                possible_matches = parcels_gdf.iloc[possible_matches_index]
            else:
                # Fallback: check all parcels (slower)
                possible_matches = parcels_gdf
            
            # Precise check: which parcels actually intersect with buffer
            try:
                parcels_in_buffer = possible_matches[possible_matches.geometry.intersects(buffer)]
            except:
                # If intersection fails, use centroid instead
                parcels_in_buffer = possible_matches[possible_matches.centroid.intersects(buffer)]
            
            # Count parcels
            parcel_count = len(parcels_in_buffer)
            result_columns[f'parcels_within_{miles_str}miles'].append(parcel_count)
            
            # Calculate statistics if there are parcels in buffer
            if parcel_count > 0:
                # Median income
                if 'medianhhi' in parcels_in_buffer.columns:
                    median_income = parcels_in_buffer['medianhhi'].median()
                elif 'household_income' in parcels_in_buffer.columns:
                    median_income = parcels_in_buffer['household_income'].median()
                else:
                    median_income = np.nan
                result_columns[f'median_income_{miles_str}miles'].append(median_income)
                
                # Average AC ownership
                if 'AC' in parcels_in_buffer.columns:
                    avg_ac = parcels_in_buffer['AC'].mean()
                else:
                    avg_ac = np.nan
                result_columns[f'avg_ac_ownership_{miles_str}miles'].append(avg_ac)
                
                # Total population
                if 'poptotal' in parcels_in_buffer.columns:
                    total_pop = parcels_in_buffer['poptotal'].sum()
                elif 'total_pop' in parcels_in_buffer.columns:
                    total_pop = parcels_in_buffer['total_pop'].sum()
                else:
                    total_pop = np.nan
                result_columns[f'total_population_{miles_str}miles'].append(total_pop)
                
                # Percentage elderly (65+)
                if 'age65up' in parcels_in_buffer.columns and 'poptotal' in parcels_in_buffer.columns:
                    total_elderly = parcels_in_buffer['age65up'].sum()
                    total_population = parcels_in_buffer['poptotal'].sum()
                    if total_population > 0:
                        pct_elderly = (total_elderly / total_population) * 100
                    else:
                        pct_elderly = 0
                elif 'pop_over_65' in parcels_in_buffer.columns and 'total_pop' in parcels_in_buffer.columns:
                    total_elderly = parcels_in_buffer['pop_over_65'].sum()
                    total_population = parcels_in_buffer['total_pop'].sum()
                    if total_population > 0:
                        pct_elderly = (total_elderly / total_population) * 100
                    else:
                        pct_elderly = 0
                else:
                    pct_elderly = np.nan
                result_columns[f'pct_elderly_{miles_str}miles'].append(pct_elderly)
                
            else:
                # No parcels in buffer
                result_columns[f'median_income_{miles_str}miles'].append(np.nan)
                result_columns[f'avg_ac_ownership_{miles_str}miles'].append(np.nan)
                result_columns[f'total_population_{miles_str}miles'].append(0)
                result_columns[f'pct_elderly_{miles_str}miles'].append(np.nan)
    
    print("   ✓ Completed catchment analysis for all cooling centers")
    
    # Add results to cooling centers dataframe
    print("\n5. Adding results to cooling center data...")
    for col_name, values in result_columns.items():
        cooling_centers[col_name] = values
    
    # Save to CSV
    print("\n6. Saving results...")
    
    # Drop geometry column for CSV (keep all other columns)
    cooling_centers_csv = cooling_centers.drop(columns=['geometry'])
    cooling_centers_csv.to_csv(output_csv, index=False)
    print(f"   ✓ Saved to: {output_csv}")
    
    # Display summary statistics
    print("\n7. SUMMARY STATISTICS")
    print("="*70)
    
    for miles in distances_miles:
        miles_str = str(miles).replace('.', '_')
        col = f'parcels_within_{miles_str}miles'
        
        if col in cooling_centers.columns:
            print(f"\n   Within {miles} miles:")
            print(f"   - Average parcels: {cooling_centers[col].mean():.0f}")
            print(f"   - Min parcels: {cooling_centers[col].min():.0f}")
            print(f"   - Max parcels: {cooling_centers[col].max():.0f}")
            print(f"   - Centers with 0 parcels: {(cooling_centers[col] == 0).sum()}")
    
    # Show sample of results
    print("\n8. SAMPLE RESULTS (first 5 cooling centers):")
    print("-"*70)
    
    sample_cols = ['name', 'type', 'parcels_within_0_5miles', 'parcels_within_1miles', 
                   'median_income_1miles', 'avg_ac_ownership_1miles']
    available_cols = [col for col in sample_cols if col in cooling_centers.columns]
    
    if available_cols:
        print(cooling_centers[available_cols].head().to_string(index=False))
    
    # Data quality check
    print("\n9. DATA QUALITY CHECK")
    print("-"*70)
    
    # Check that larger distances have more parcels
    for i in range(len(distances_miles) - 1):
        miles1 = str(distances_miles[i]).replace('.', '_')
        miles2 = str(distances_miles[i+1]).replace('.', '_')
        col1 = f'parcels_within_{miles1}miles'
        col2 = f'parcels_within_{miles2}miles'
        
        if col1 in cooling_centers.columns and col2 in cooling_centers.columns:
            violations = (cooling_centers[col1] > cooling_centers[col2]).sum()
            if violations > 0:
                print(f"   ⚠ {violations} centers have more parcels at {distances_miles[i]} miles than {distances_miles[i+1]} miles")
            else:
                print(f"   ✓ Monotonic increase verified: {distances_miles[i]} → {distances_miles[i+1]} miles")
    
    print("\n✅ ANALYSIS COMPLETE!")
    print(f"📊 Results saved to: {output_csv}")
    print(f"📈 Added {len(result_columns)} new columns to cooling center data")
    
    return cooling_centers

if __name__ == "__main__":
    try:
        # Run the analysis
        results = analyze_cooling_center_catchments()
        
        print("\n🎉 Script completed successfully!")
        print("\nOutput file contains:")
        print("- Original cooling center data")
        print("- Building year from previous merge")
        print("- Parcel counts within 7 distance thresholds")
        print("- Demographics for each distance threshold:")
        print("  • Median household income")
        print("  • Average AC ownership rate")
        print("  • Total population")
        print("  • Percentage of elderly population")
        
    except FileNotFoundError as e:
        print(f"\n❌ Error: File not found - {e}")
        print("Please ensure all input files exist:")
        print("- Parcels pickle file")
        print("- Cooling center GPKG file")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()