import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.mask import mask
import glob
import os
from pathlib import Path
from datetime import datetime, timedelta
import re
import numpy as np

# Get script directory and set up relative paths
SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR / ".." / ".." / ".."  # Goes up to .

# Define paths relative to script location
RAW_DIR = BASE_DIR / "data" / "raw" / "prism"
REFERENCE_FILE = BASE_DIR / "data" / "LandSurface_Temperature_2022_500m.tif"
OUTPUT_DIR = BASE_DIR / "data" / "validate_data" / "intermediate" / "prism"

def test_temperature_conversion():
    """Test the Celsius to Fahrenheit conversion"""
    print("Testing temperature conversion:")
    test_celsius = [0, 25, 30, 35, 40]  # Common summer temperatures in Celsius
    
    for c in test_celsius:
        f = (c * 9.0 / 5.0) + 32.0
        print(f"  {c}°C = {f}°F")
    print()

def process_prism_temperature_data(
    raw_data_dir,
    reference_file,
    output_dir,
    temp_type="tmax",
    start_date=None,
    end_date=None
):
    """
    Process PRISM temperature data to match reference raster specifications
    
    Parameters:
    -----------
    raw_data_dir : Path
        Directory containing raw PRISM data
    reference_file : Path
        Path to reference raster file (LandSurface_Temperature_2022_500m.tif)
    output_dir : Path
        Output directory for processed files
    temp_type : str
        Temperature type to process ('tmax', 'tmin', 'tmean')
    start_date : str
        Start date in YYYYMMDD format (None = process all)
    end_date : str
        End date in YYYYMMDD format (None = process all)
    """
    
    print(f"Starting PRISM {temp_type} data processing...")
    if start_date and end_date:
        print(f"Date range: {start_date} to {end_date}")
    else:
        print("Processing all available dates")
    print(f"Converting from Celsius (input) to Fahrenheit (output)")
    print(f"Output resolution: 500m to match reference raster")
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Read reference raster properties
    with rasterio.open(reference_file) as ref:
        ref_bounds = ref.bounds
        ref_crs = ref.crs
        ref_transform = ref.transform
        ref_width = ref.width
        ref_height = ref.height
        ref_nodata = ref.nodata
        
        print(f"\nReference raster properties:")
        print(f"  CRS: {ref_crs}")
        print(f"  Bounds: {ref_bounds}")
        print(f"  Dimensions: {ref_width} x {ref_height}")
        print(f"  Pixel size: {ref_transform[0]:.2f}, {ref_transform[4]:.2f}")
        print(f"  No data value: {ref_nodata}")
    
    # Find all PRISM files matching the pattern
    pattern = f"{temp_type}_prism_*_800m.tif"
    prism_files = list(raw_data_dir.glob(pattern))
    
    print(f"\nFound {len(prism_files)} {temp_type} files in directory")
    
    # Filter files by date range if specified
    filtered_files = []
    date_pattern = r'(\d{8})'  # Extract 8-digit date
    
    for file_path in prism_files:
        filename = file_path.name
        date_match = re.search(date_pattern, filename)
        
        if date_match:
            file_date = date_match.group(1)
            if start_date and end_date:
                if start_date <= file_date <= end_date:
                    filtered_files.append(file_path)
            else:
                filtered_files.append(file_path)
    
    # Sort files by date
    filtered_files.sort(key=lambda x: re.search(date_pattern, x.name).group(1))
    
    if start_date and end_date:
        print(f"Files in date range {start_date} to {end_date}: {len(filtered_files)}")
    else:
        print(f"Processing all {len(filtered_files)} files")
    
    if not filtered_files:
        print("No files found to process!")
        return
    
    # Process each file
    processed_count = 0
    failed_count = 0
    
    for i, prism_file in enumerate(filtered_files, 1):
        try:
            # Extract date from filename
            filename = prism_file.name
            date_match = re.search(date_pattern, filename)
            file_date = date_match.group(1)
            
            # Create output filename
            output_filename = f"{temp_type}_hennepin_{file_date}_500m.tif"
            output_path = output_dir / output_filename
            
            # Skip if already processed
            if output_path.exists():
                print(f"[{i:3d}/{len(filtered_files)}] Skipping {file_date} (already exists)")
                continue
            
            print(f"[{i:3d}/{len(filtered_files)}] Processing {file_date}...")
            
            # Process the file
            success = process_single_prism_file(
                prism_file, 
                output_path, 
                ref_bounds, 
                ref_crs, 
                ref_transform, 
                ref_width, 
                ref_height, 
                ref_nodata
            )
            
            if success:
                processed_count += 1
                print(f"    ✓ Saved: {output_filename}")
            else:
                failed_count += 1
                print(f"    ✗ Failed: {output_filename}")
                
        except Exception as e:
            failed_count += 1
            print(f"[{i:3d}/{len(filtered_files)}] Error processing {filename}: {str(e)}")
    
    # Summary
    print(f"\n{'='*60}")
    print(f"PROCESSING SUMMARY for {temp_type}")
    print(f"{'='*60}")
    print(f"Total files found: {len(filtered_files)}")
    print(f"Successfully processed: {processed_count}")
    print(f"Failed: {failed_count}")
    print(f"Temperature units: Fahrenheit (converted from Celsius)")
    print(f"Output directory: {output_dir}")
    
    return processed_count, failed_count

def celsius_to_fahrenheit(celsius_data, nodata_value):
    """
    Convert Celsius to Fahrenheit while preserving nodata values
    Formula: F = (C * 9/5) + 32
    """
    import numpy as np
    
    # Create mask for valid data (not nodata)
    if nodata_value is not None:
        valid_mask = celsius_data != nodata_value
    else:
        valid_mask = ~np.isnan(celsius_data)
    
    # Initialize output with same shape
    fahrenheit_data = celsius_data.copy()
    
    # Convert only valid data points
    fahrenheit_data[valid_mask] = (celsius_data[valid_mask] * 9.0 / 5.0) + 32.0
    
    return fahrenheit_data

def process_single_prism_file(input_file, output_file, target_bounds, target_crs, 
                            target_transform, target_width, target_height, target_nodata):
    """
    Process a single PRISM file to match target specifications and convert Celsius to Fahrenheit
    """
    
    try:
        with rasterio.open(input_file) as src:
            # Check if reprojection is needed
            if src.crs != target_crs:
                # Reproject and resample
                data = src.read(
                    out_shape=(src.count, target_height, target_width),
                    resampling=Resampling.bilinear
                )
                
                # Create empty array for reprojected data
                reprojected_data = data.copy()
                
                # Reproject each band
                for band_idx in range(src.count):
                    reproject(
                        source=rasterio.band(src, band_idx + 1),
                        destination=reprojected_data[band_idx],
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=target_transform,
                        dst_crs=target_crs,
                        resampling=Resampling.bilinear,
                        dst_nodata=target_nodata
                    )
                
                # Convert from Celsius to Fahrenheit
                print("    Converting Celsius to Fahrenheit...")
                for band_idx in range(reprojected_data.shape[0]):
                    reprojected_data[band_idx] = celsius_to_fahrenheit(
                        reprojected_data[band_idx], target_nodata
                    )
                
                # Update profile
                profile = src.profile.copy()
                profile.update({
                    'crs': target_crs,
                    'transform': target_transform,
                    'width': target_width,
                    'height': target_height,
                    'dtype': 'float64',  # Match reference data type
                    'nodata': target_nodata
                })
                
                # Write output
                with rasterio.open(output_file, 'w', **profile) as dst:
                    dst.write(reprojected_data)
                    
            else:
                # Same CRS - just resample and clip
                data = src.read(
                    out_shape=(src.count, target_height, target_width),
                    resampling=Resampling.bilinear
                )
                
                # Convert from Celsius to Fahrenheit
                print("    Converting Celsius to Fahrenheit...")
                for band_idx in range(data.shape[0]):
                    data[band_idx] = celsius_to_fahrenheit(data[band_idx], target_nodata)
                
                profile = src.profile.copy()
                profile.update({
                    'transform': target_transform,
                    'width': target_width,
                    'height': target_height,
                    'dtype': 'float64',
                    'nodata': target_nodata
                })
                
                with rasterio.open(output_file, 'w', **profile) as dst:
                    dst.write(data)
        
        return True
        
    except Exception as e:
        print(f"    Error in process_single_prism_file: {str(e)}")
        return False

def list_available_prism_files(raw_data_dir, temp_type="tmax"):
    """
    List available PRISM files and their date ranges
    """
    
    pattern = f"{temp_type}_prism_*_800m.tif"
    prism_files = list(raw_data_dir.glob(pattern))
    
    if not prism_files:
        print(f"No {temp_type} files found in {raw_data_dir}")
        return
    
    # Extract dates
    dates = []
    date_pattern = r'(\d{8})'
    
    for file_path in prism_files:
        filename = file_path.name
        date_match = re.search(date_pattern, filename)
        if date_match:
            dates.append(date_match.group(1))
    
    dates.sort()
    
    print(f"Found {len(prism_files)} {temp_type} files")
    print(f"Date range: {dates[0]} to {dates[-1]}")
    print(f"First file: {dates[0]}")
    print(f"Last file: {dates[-1]}")
    
    # Show sample of files
    print(f"\nSample files:")
    for i, date in enumerate(dates[:5]):
        print(f"  {temp_type}_prism_{date}_800m.tif")
    if len(dates) > 5:
        print(f"  ... and {len(dates) - 5} more files")
    
    return dates

def verify_output_files(output_dir, reference_file, temp_type="tmax"):
    """
    Verify that output files match reference specifications
    """
    
    # Get reference specs
    with rasterio.open(reference_file) as ref:
        ref_crs = ref.crs
        ref_bounds = ref.bounds
        ref_width = ref.width
        ref_height = ref.height
        ref_transform = ref.transform
    
    # Find processed files
    processed_files = list(output_dir.glob(f"{temp_type}_hennepin_*_500m.tif"))
    
    if not processed_files:
        print(f"No processed {temp_type} files found!")
        return
    
    print(f"Verifying {len(processed_files)} processed {temp_type} files...")
    
    issues_found = 0
    
    for file_path in processed_files[:5]:  # Check first 5 files
        filename = file_path.name
        
        try:
            with rasterio.open(file_path) as src:
                # Check specifications
                if src.crs != ref_crs:
                    print(f"❌ {filename}: CRS mismatch ({src.crs} vs {ref_crs})")
                    issues_found += 1
                elif src.bounds != ref_bounds:
                    print(f"❌ {filename}: Bounds mismatch")
                    issues_found += 1
                elif (src.width, src.height) != (ref_width, ref_height):
                    print(f"❌ {filename}: Dimensions mismatch ({src.width}x{src.height} vs {ref_width}x{ref_height})")
                    issues_found += 1
                else:
                    # Check temperature values are reasonable (should be in Fahrenheit)
                    data = src.read(1)
                    valid_data = data[data != src.nodata]
                    if len(valid_data) > 0:
                        temp_min, temp_max = valid_data.min(), valid_data.max()
                        print(f"✓ {filename}: OK (temp range: {temp_min:.1f}°F to {temp_max:.1f}°F)")
                        
                        # Verify temperatures are in reasonable Fahrenheit range
                        if temp_min < 0 or temp_max > 150:
                            print(f"    ⚠️ Warning: Temperature range seems unusual for Fahrenheit")
                    else:
                        print(f"⚠️ {filename}: No valid data")
                        issues_found += 1
                        
        except Exception as e:
            print(f"❌ {filename}: Error reading file - {str(e)}")
            issues_found += 1
    
    if issues_found == 0:
        print("\n✅ All verified files match reference specifications!")
    else:
        print(f"\n⚠️ Found {issues_found} issues in verification")

if __name__ == "__main__":
    print("PRISM Temperature Data Processing Script")
    print("=" * 50)
    print(f"Script location: {SCRIPT_DIR}")
    print(f"Raw data directory: {RAW_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Reference file: {REFERENCE_FILE}")
    print()
    
    # Test temperature conversion
    test_temperature_conversion()
    
    # Process all three temperature types
    temp_types = ["tmax", "tmin", "tmean"]
    
    for temp_type in temp_types:
        print(f"\n{'='*70}")
        print(f"PROCESSING {temp_type.upper()} DATA")
        print(f"{'='*70}")
        
        # Step 1: List available files
        print(f"\n1. Checking available PRISM {temp_type} files...")
        available_dates = list_available_prism_files(RAW_DIR, temp_type)
        
        if not available_dates:
            print(f"No PRISM {temp_type} files found. Skipping...")
            continue
        
        # Step 2: Process all files (no date filtering)
        print(f"\n2. Processing all {temp_type} files...")
        print("   Converting from Celsius to Fahrenheit...")
        processed, failed = process_prism_temperature_data(
            raw_data_dir=RAW_DIR,
            reference_file=REFERENCE_FILE,
            output_dir=OUTPUT_DIR,
            temp_type=temp_type,
            start_date=None,  # Process all dates
            end_date=None
        )
        
        # Step 3: Verify output
        if processed > 0:
            print(f"\n3. Verifying processed {temp_type} files...")
            verify_output_files(OUTPUT_DIR, REFERENCE_FILE, temp_type)
    
    print(f"\n{'='*70}")
    print("🎉 ALL PROCESSING COMPLETE!")
    print(f"{'='*70}")
    print(f"Processed files saved to: {OUTPUT_DIR}")
    print(f"Temperature data converted from Celsius to Fahrenheit")
    print(f"Ready for use with your heat event model!")