#!/usr/bin/env python3
"""
Script to extract parcel-level temperatures from PRISM raster TIFs
Processes multiple files and converts temperatures from Celsius to Fahrenheit
Input: Temperature raster TIFs
Output: Parcel-level temperature data as TIF
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

# Add correct path for imports - matching the working script
script_dir = Path(__file__).parent
sys.path.append(str(script_dir / ".." / ".." / "HeatRisk_ABM_Model"))

from src.event import HeatEvent
import geopandas as gpd
import rasterio
from rasterio.features import rasterize
import numpy as np

# Define paths relative to script location
BASE_DIR = script_dir / ".." / ".." / ".."  # .
INPUT_DIR = BASE_DIR / "data" / "raw" / "prism"
OUTPUT_DIR = BASE_DIR / "data" / "validate_data" / "intermediate" / "prism"

# Create output directory
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Temperature conversion
def celsius_to_fahrenheit(celsius):
    """Convert Celsius to Fahrenheit"""
    return celsius * 9/5 + 32

# Generate date list for processing
def generate_dates():
    """Generate all dates from May 1 to Sept 30 for years 2020, 2023, 2024"""
    dates = []
    years = [2020, 2023, 2024]
    
    for year in years:
        start_date = datetime(year, 5, 1)
        end_date = datetime(year, 9, 30)
        
        current_date = start_date
        while current_date <= end_date:
            dates.append(current_date.strftime("%Y%m%d"))
            current_date += timedelta(days=1)
    
    return dates

# Main processing
def main():
    # Get list of dates to process
    dates = generate_dates()
    print(f"Processing {len(dates)} potential dates...")
    
    processed_count = 0
    failed_count = 0
    
    # Process each date
    for date_str in dates:
        input_filename = f"tmax_prism_{date_str}_800m.tif"
        input_path = INPUT_DIR / input_filename
        
        # Check if file exists
        if not input_path.exists():
            continue
            
        output_filename = f"tmax_hennepin_prism_{date_str}_800m.tif"
        output_path = OUTPUT_DIR / output_filename
        
        print(f"\nProcessing {input_filename}...")
        
        try:
            # Create HeatEvent instance for each file to ensure clean data
            heat_event = HeatEvent(temperature=75)  # fallback temperature
            
            # Load parcel data
            heat_event.load_data()
            
            # Extract temperatures from raster
            heat_event.join_temps_to_parcels(temp_raster=str(input_path), temperature=75)
            
            # Create GeoDataFrame with temperature data
            data = []
            for parcel in heat_event.parcels:
                # Convert temperature from Celsius to Fahrenheit
                temp_celsius = parcel.attributes['temperature']
                temp_fahrenheit = celsius_to_fahrenheit(temp_celsius)
                
                data.append({
                    'pid': parcel.id,
                    'temperature': temp_fahrenheit,
                    'geometry': parcel.attributes['geometry']
                })
            
            gdf = gpd.GeoDataFrame(data).set_crs(epsg=26915)
            
            # Read input raster to get template properties
            with rasterio.open(input_path) as src:
                template_profile = src.profile.copy()
                template_transform = src.transform
                template_shape = src.shape
            
            # Rasterize parcels with temperature values
            shapes = [(geom, temp) for geom, temp in zip(gdf.geometry, gdf.temperature)]
            rasterized = rasterize(
                shapes,
                out_shape=template_shape,
                transform=template_transform,
                fill=0,
                dtype=rasterio.float32
            )
            
            # Save as TIF
            template_profile.update({
                'dtype': rasterio.float32,
                'count': 1,
                'compress': 'lzw'
            })
            
            with rasterio.open(output_path, 'w', **template_profile) as dst:
                dst.write(rasterized, 1)
            
            # Print statistics
            print(f"  Output saved to: {output_filename}")
            print(f"  Processed {len(gdf)} parcels")
            print(f"  Temperature range: {gdf.temperature.min():.2f} - {gdf.temperature.max():.2f}°F")
            
            processed_count += 1
            
        except Exception as e:
            print(f"  ERROR processing {input_filename}: {str(e)}")
            failed_count += 1
    
    # Final summary
    print(f"\nProcessing complete!")
    print(f"Successfully processed: {processed_count} files")
    print(f"Failed: {failed_count} files")
    print(f"Output directory: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()