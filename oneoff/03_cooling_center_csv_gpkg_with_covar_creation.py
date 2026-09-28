#!/usr/bin/env python3
"""
Merge cooling center CSV with parcel GPKG data
Keep ALL original GPKG data and ADD cooling center information from CSV
"""
import os

import pandas as pd
import geopandas as gpd
import os
import warnings
warnings.filterwarnings('ignore')

def merge_cooling_center_data():
    """Main function to merge cooling center CSV with parcel GPKG data"""
    
    # Define file paths
    csv_path = r"~\hennepin\data\validate_data\intermediate\cooling_center.csv"
    gpkg_path = r"~\hennepin\data\raw\from_database\cooling_center_parcels_246.gpkg"
    output_dir = r"~\hennepin\data\validate_data\intermediate"
    
    # Output file paths
    output_csv = os.path.join(output_dir, "cooling_center_with_buildyr.csv")
    output_gpkg = os.path.join(output_dir, "cooling_center_with_buildyr.gpkg")
    
    print("="*60)
    print("COOLING CENTER BUILD YEAR MERGER")
    print("="*60)
    
    # Step 1: Load the CSV data
    print("\n1. Loading cooling center CSV...")
    df_csv = pd.read_csv(csv_path)
    print(f"   ✓ Loaded {len(df_csv)} cooling centers from CSV")
    print(f"   ✓ CSV columns: {list(df_csv.columns)}")
    
    # Step 2: Load the GPKG data WITH geometry preserved
    print("\n2. Loading parcel GPKG data with geometry...")
    try:
        # Use engine='pyogrio' or 'fiona' to handle better
        import fiona
        import shapely.wkt
        from shapely.geometry import shape
        
        # Read the GPKG maintaining geometry
        with fiona.open(gpkg_path, 'r') as src:
            # Get CRS
            crs = src.crs
            
            # Read all features
            features = []
            geometries = []
            
            for feat in src:
                # Extract properties and geometry separately
                properties = feat['properties']
                geom = shape(feat['geometry'])
                
                features.append(properties)
                geometries.append(geom)
            
            # Create DataFrame from properties
            gdf_parcels = pd.DataFrame(features)
            
            # Create GeoDataFrame with geometries
            gdf_parcels = gpd.GeoDataFrame(gdf_parcels, geometry=geometries, crs=crs)
            
        print(f"   ✓ Loaded {len(gdf_parcels)} parcels from GPKG with geometry")
        print(f"   ✓ Original GPKG has {len(gdf_parcels.columns)} columns")
        print(f"   ✓ CRS: {gdf_parcels.crs}")
        
    except Exception as e:
        print(f"   Trying alternative method: {e}")
        # Fallback to regular geopandas
        gdf_parcels = gpd.read_file(gpkg_path)
        print(f"   ✓ Loaded {len(gdf_parcels)} parcels using geopandas")
    
    # Step 3: Extract BUILD_YR for CSV update
    print("\n3. Extracting BUILD_YR for CSV update...")
    
    # Check for BUILD_YR column
    if 'BUILD_YR' in gdf_parcels.columns:
        print(f"   ✓ Found BUILD_YR column")
        
        # Create mapping for CSV
        gdf_parcels['cooling_center_id'] = pd.to_numeric(gdf_parcels['cooling_center_id'], errors='coerce')
        df_csv['id'] = pd.to_numeric(df_csv['id'], errors='coerce')
        
        build_yr_mapping = gdf_parcels.set_index('cooling_center_id')['BUILD_YR'].to_dict()
        
        # Add build_yr to CSV
        df_csv['build_yr'] = df_csv['id'].map(build_yr_mapping)
        
        matched = df_csv['build_yr'].notna().sum()
        print(f"   ✓ Matched {matched}/{len(df_csv)} cooling centers with building years")
    else:
        print("   ⚠ No BUILD_YR column found")
        df_csv['build_yr'] = None
    
    # Step 4: Save updated CSV
    print("\n4. Saving updated CSV...")
    df_csv.to_csv(output_csv, index=False)
    print(f"   ✓ Saved CSV to: {output_csv}")
    
    # Step 5: Merge CSV data INTO GPKG (keeping all GPKG columns + adding CSV columns)
    print("\n5. Merging CSV data into GPKG...")
    
    # Prepare CSV columns for merge (exclude 'geometry' text column and 'id')
    csv_columns_to_add = [col for col in df_csv.columns 
                          if col not in ['geometry', 'id', 'build_yr']]  # build_yr already in GPKG
    
    print(f"   ✓ Adding {len(csv_columns_to_add)} columns from CSV to GPKG")
    
    # Merge: GPKG (left) + CSV data (right)
    gdf_merged = gdf_parcels.merge(
        df_csv[['id'] + csv_columns_to_add],
        left_on='cooling_center_id',
        right_on='id',
        how='left',
        suffixes=('', '_from_csv')  # Add suffix to duplicate columns
    )
    
    # Drop the redundant 'id' column from CSV
    if 'id' in gdf_merged.columns:
        gdf_merged = gdf_merged.drop(columns=['id'])
    
    print(f"   ✓ Merged GPKG now has {len(gdf_merged.columns)} columns (was {len(gdf_parcels.columns)})")
    print(f"   ✓ Added columns: {csv_columns_to_add[:5]}..." if len(csv_columns_to_add) > 5 else f"   ✓ Added columns: {csv_columns_to_add}")
    
    # Step 6: Save merged GPKG
    print("\n6. Saving merged GPKG...")
    
    # Ensure we have a valid GeoDataFrame
    if not isinstance(gdf_merged, gpd.GeoDataFrame):
        print("   ⚠ Converting to GeoDataFrame...")
        gdf_merged = gpd.GeoDataFrame(gdf_merged)
    
    # Save with specific layer name
    try:
        gdf_merged.to_file(output_gpkg, layer='cooling_center_parcels', driver="GPKG")
        print(f"   ✓ Saved GPKG to: {output_gpkg}")
    except Exception as e:
        print(f"   ⚠ Error saving GPKG: {e}")
        
        # Try saving without problematic columns
        print("   Trying to save with column name fixes...")
        
        # Fix column names (remove special characters)
        gdf_merged.columns = [col.replace(' ', '_').replace('/', '_').replace('\\', '_') 
                              for col in gdf_merged.columns]
        
        try:
            gdf_merged.to_file(output_gpkg, layer='cooling_center_parcels', driver="GPKG")
            print(f"   ✓ Saved GPKG with fixed column names")
        except:
            # Last resort: save as shapefile
            shp_path = output_gpkg.replace('.gpkg', '.shp')
            gdf_merged.to_file(shp_path)
            print(f"   ✓ Saved as shapefile instead: {shp_path}")
    
    # Step 7: Verification
    print("\n7. VERIFICATION SUMMARY")
    print("="*60)
    
    # Verify CSV
    df_check = pd.read_csv(output_csv)
    print(f"✓ CSV Output:")
    print(f"  - Records: {len(df_check)}")
    print(f"  - Columns: {len(df_check.columns)}")
    print(f"  - Cooling centers with build_yr: {df_check['build_yr'].notna().sum()}/{len(df_check)}")
    
    # Verify GPKG
    print(f"\n✓ GPKG Output:")
    print(f"  - Records: {len(gdf_merged)}")
    print(f"  - Total columns: {len(gdf_merged.columns)}")
    print(f"  - Original GPKG columns preserved: {len([c for c in gdf_parcels.columns if c in gdf_merged.columns])}/{len(gdf_parcels.columns)}")
    print(f"  - New columns from CSV: {len([c for c in csv_columns_to_add if c in gdf_merged.columns or c+'_from_csv' in gdf_merged.columns])}")
    print(f"  - Has geometry: {gdf_merged.geometry.notna().all()}")
    
    # Show sample
    print("\n8. SAMPLE OF MERGED DATA:")
    print("-"*60)
    
    # Show a few key columns to verify merge
    sample_cols = ['cooling_center_id', 'BUILD_YR', 'name', 'type', 'address']
    available_cols = [col for col in sample_cols if col in gdf_merged.columns]
    
    if available_cols:
        print(gdf_merged[available_cols].head(3).to_string(index=False))
    
    print("\n✅ MERGE COMPLETE!")
    
    return df_check, gdf_merged

if __name__ == "__main__":
    try:
        # Set environment variables to suppress warnings
        os.environ['PROJ_LIB'] = ''
        os.environ['GDAL_DATA'] = ''
        
        # Create output directory if needed
        output_dir = r"~\hennepin\data\validate_data\intermediate"
        os.makedirs(output_dir, exist_ok=True)
        
        # Run the merge
        csv_result, gpkg_result = merge_cooling_center_data()
        
        print("\n🎉 Script completed successfully!")
        print("\nOutputs:")
        print(f"1. CSV with build_yr: cooling_center_with_buildyr.csv")
        print(f"2. GPKG with all data: cooling_center_with_buildyr.gpkg")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()