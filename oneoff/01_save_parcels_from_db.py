#!/usr/bin/env python3
"""
UPDATED parcel extraction script that includes all necessary fields for Parcel constructor.
This version extracts cooling_distance and other missing fields needed for parallel processing.
"""

import os
import sys
import pandas as pd
import geopandas as gpd
import numpy as np
import pickle
import time
from pathlib import Path

# Add the code path
sys.path.append(r'~\hennepin\code\HeatRisk_ABM_Model')

def extract_parcels_data_updated():
    """Extract parcel data with all necessary fields for Parcel constructor"""
    print("=== EXTRACTING PARCEL DATA (UPDATED VERSION) ===")
    
    # Set working directory
    code_dir = r"~\hennepin\code\HeatRisk_ABM_Model"
    if os.path.exists(code_dir):
        os.chdir(code_dir)
        print(f"Working directory: {os.getcwd()}")
    
    # Output configuration
    output_dir = Path("./preprocessed_data")
    output_dir.mkdir(exist_ok=True)
    
    # Files to create
    parcels_file = output_dir / "parcels_prepared.pkl"
    metadata_file = output_dir / "parcels_metadata.json"
    
    try:
        print("\n1. Loading parcel data from database...")
        start_time = time.time()
        
        # Import and use existing HeatEvent to get the data
        from src import HeatEvent
        
        # Create temporary HeatEvent just to load data
        heat_event = HeatEvent(temperature=75)  # Temperature doesn't matter for data loading
        heat_event.load_data()
        
        print(f"   ✓ Loaded {len(heat_event.parcels)} parcels")
        
        print("\n2. Converting to efficient format with ALL required fields...")
        
        # Extract parcel data into a structured format
        parcel_data = []
        for parcel in heat_event.parcels:
            # Get all attribute values with proper handling of missing data
            attrs = parcel.attributes
            
            parcel_data.append({
                # Required fields for Parcel constructor
                'pid': parcel.id,
                'geometry': attrs.get('geometry'),
                'cooling_centers': parcel.nearest_cooling_centers,  # This is the required field
                'cooling_distance': parcel.cooling_distance,        # This too
                
                # Demographic data
                'block_group_id': attrs.get('block_group_id'),
                'household_income': attrs.get('household_income'),
                'total_pop': attrs.get('total_pop'),
                'pop_under_5': attrs.get('pop_under_5'),
                'pop_5_17': attrs.get('pop_5_17'),
                'pop_18_34': attrs.get('pop_18_34'),
                'pop_35_64': attrs.get('pop_35_64'),
                'pop_over_65': attrs.get('pop_over_65'),
                'ac_proba': attrs.get('ac_proba'),
                
                # All original attributes for perfect reconstruction
                'medianhhi': attrs.get('medianhhi'),
                'ageunder18': attrs.get('ageunder18'),
                'age18_39': attrs.get('age18_39'),
                'age40_64': attrs.get('age40_64'),
                'age65up': attrs.get('age65up'),
                'pubtransit': attrs.get('pubtransit'),
                'povertyn': attrs.get('povertyn'),
                'poptotal': attrs.get('poptotal'),
                'popinhh': attrs.get('popinhh'),
                'avghhsize': attrs.get('avghhsize'),
                'AC': attrs.get('AC')  # This is the binary AC ownership flag
            })
        
        # Create GeoDataFrame
        gdf = gpd.GeoDataFrame(parcel_data)
        
        print(f"   ✓ Created GeoDataFrame with shape: {gdf.shape}")
        print(f"   ✓ Columns: {list(gdf.columns)}")
        print(f"   ✓ CRS: {gdf.crs}")
        
        # Check for required fields
        required_fields = ['pid', 'geometry', 'cooling_centers', 'cooling_distance']
        missing_fields = [field for field in required_fields if field not in gdf.columns or gdf[field].isnull().all()]
        
        if missing_fields:
            print(f"   ⚠ Warning: Some required fields missing or empty: {missing_fields}")
        else:
            print(f"   ✅ All required fields present and populated")
        
        print("\n3. Adding temperature extraction capability...")
        
        # Also store the temperature raster path for later use
        temp_raster = r"~\hennepin\output\oneoff\parcel_temperatures_20240831.tif"
        
        # Extract temperatures once and store them
        if os.path.exists(temp_raster):
            print(f"   ✓ Extracting temperatures from: {temp_raster}")
            heat_event.join_temps_to_parcels(temp_raster=temp_raster, temperature=100)
            
            # Add temperatures to our GDF
            temperatures = []
            for parcel in heat_event.parcels:
                temperatures.append(parcel.attributes.get('temperature', 100))
            
            gdf['temperature'] = temperatures
            print(f"   ✓ Temperature range: {min(temperatures):.1f} - {max(temperatures):.1f}°F")
        else:
            print(f"   ⚠ Temperature raster not found: {temp_raster}")
            gdf['temperature'] = 100  # Default fallback
        
        print("\n4. Data quality checks...")
        
        # Check cooling centers
        if 'cooling_centers' in gdf.columns:
            non_empty_centers = gdf['cooling_centers'].apply(lambda x: len(x) if isinstance(x, list) else 0)
            print(f"   ✓ Parcels with cooling centers: {(non_empty_centers > 0).sum()}/{len(gdf)}")
            if (non_empty_centers > 0).sum() > 0:
                print(f"   ✓ Average cooling centers per parcel: {non_empty_centers[non_empty_centers > 0].mean():.1f}")
        
        # Check cooling distance
        if 'cooling_distance' in gdf.columns:
            valid_distances = gdf['cooling_distance'].dropna()
            if len(valid_distances) > 0:
                print(f"   ✓ Distance range: {valid_distances.min():.0f} - {valid_distances.max():.0f}m")
                print(f"   ✓ Average distance: {valid_distances.mean():.0f}m")
        
        # Check AC data
        if 'AC' in gdf.columns:
            ac_counts = gdf['AC'].value_counts().sort_index()
            print(f"   ✓ AC ownership distribution: {dict(ac_counts)}")
        
        print("\n5. Saving preprocessed data...")
        
        # Save as pickle for fast loading
        with open(parcels_file, 'wb') as f:
            pickle.dump({
                'gdf': gdf,
                'temp_raster_path': temp_raster,
                'total_parcels': len(gdf),
                'creation_time': time.time(),
                'crs': str(gdf.crs),
                'version': 'updated_v2'  # Mark this as the updated version
            }, f)
        
        # Save metadata as JSON for reference
        metadata = {
            'total_parcels': len(gdf),
            'columns': list(gdf.columns),
            'crs': str(gdf.crs),
            'temperature_range': [float(gdf['temperature'].min()), float(gdf['temperature'].max())],
            'cooling_centers_stats': {
                'parcels_with_centers': int((gdf['cooling_centers'].apply(lambda x: len(x) if isinstance(x, list) else 0) > 0).sum()),
                'total_parcels': len(gdf)
            },
            'cooling_distance_stats': {
                'min': float(gdf['cooling_distance'].min()) if 'cooling_distance' in gdf.columns else None,
                'max': float(gdf['cooling_distance'].max()) if 'cooling_distance' in gdf.columns else None,
                'mean': float(gdf['cooling_distance'].mean()) if 'cooling_distance' in gdf.columns else None
            },
            'file_size_mb': parcels_file.stat().st_size / (1024*1024) if parcels_file.exists() else 0,
            'creation_time': time.strftime('%Y-%m-%d %H:%M:%S'),
            'version': 'updated_v2'
        }
        
        import json
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        load_time = time.time() - start_time
        
        print(f"   ✓ Saved to: {parcels_file}")
        print(f"   ✓ File size: {parcels_file.stat().st_size / (1024*1024):.1f} MB")
        print(f"   ✓ Metadata saved to: {metadata_file}")
        
        print(f"\n=== EXTRACTION COMPLETE (UPDATED VERSION) ===")
        print(f"Processing time: {load_time:.2f} seconds")
        print(f"Ready for parallel processing!")
        
        return parcels_file, metadata
        
    except Exception as e:
        print(f"\n❌ Error during extraction: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None

def test_load_speed():
    """Test how fast we can load the preprocessed data"""
    print("\n=== TESTING LOAD SPEED ===")
    
    parcels_file = Path("./preprocessed_data/parcels_prepared.pkl")
    
    if not parcels_file.exists():
        print("❌ Preprocessed file not found. Run extraction first.")
        return
    
    start_time = time.time()
    
    with open(parcels_file, 'rb') as f:
        data = pickle.load(f)
    
    load_time = time.time() - start_time
    
    gdf = data['gdf']
    version = data.get('version', 'original')
    
    print(f"✓ Loaded {len(gdf)} parcels in {load_time:.3f} seconds")
    print(f"✓ Version: {version}")
    print(f"✓ Columns: {list(gdf.columns)}")
    print(f"✓ Memory usage: {gdf.memory_usage(deep=True).sum() / (1024*1024):.1f} MB")
    
    # Check for required fields
    required_fields = ['pid', 'geometry', 'cooling_centers', 'cooling_distance']
    missing_fields = [field for field in required_fields if field not in gdf.columns]
    
    if missing_fields:
        print(f"❌ Missing required fields: {missing_fields}")
        print("   This file needs to be regenerated with the updated extraction")
    else:
        print(f"✅ All required fields present")
        
        # Show sample data
        print(f"\nSample data:")
        sample_cols = ['pid', 'cooling_centers', 'cooling_distance', 'temperature', 'AC']
        available_cols = [col for col in sample_cols if col in gdf.columns]
        if available_cols:
            print(gdf[available_cols].head(3))
    
    return data

if __name__ == "__main__":
    # Extract parcels data
    parcels_file, metadata = extract_parcels_data_updated()
    
    if parcels_file:
        # Test loading speed
        data = test_load_speed()
        
        if data:
            print(f"\n🎉 SUCCESS! Updated extraction complete.")
            print(f"📁 Use this file in parallel processing: {parcels_file}")
            print(f"💡 This version includes all required fields for Parcel constructor")
    else:
        print("\n❌ FAILED! Check error messages above.")