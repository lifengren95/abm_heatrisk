import rasterio
from rasterio.mask import mask
import geopandas as gpd
import pandas as pd
import numpy as np
import glob
import os
from datetime import datetime
import re
from pathlib import Path

def extract_daily_county_average_temps(
    tmax_files_dir=r"~\hennepin\data\validate_data\intermediate\prism",
    county_shapefile=r"~\hennepin\data\raw\Data\County_Parcels\County_Parcels.shp",
    output_dir=r"~\hennepin\data\validate_data\intermediate\temp_input",
    start_date="20240601",
    end_date="20240831"
):
    """
    Extract daily average tmax temperatures for Hennepin County from processed PRISM data
    
    Parameters:
    -----------
    tmax_files_dir : str
        Directory containing processed tmax files (e.g., tmax_hennepin_YYYYMMDD_500m.tif)
    county_shapefile : str
        Path to Hennepin County boundary shapefile
    output_dir : str
        Output directory for temperature input files
    start_date : str
        Start date in YYYYMMDD format
    end_date : str  
        End date in YYYYMMDD format
    """
    
    print("Extracting Daily County Average Temperatures")
    print("=" * 60)
    print(f"Processing dates: {start_date} to {end_date}")
    print(f"TMAX files directory: {tmax_files_dir}")
    print(f"County boundary: {county_shapefile}")
    print(f"Output directory: {output_dir}")
    print()
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Read county boundary
    print("Loading county boundary...")
    try:
        county_gdf = gpd.read_file(county_shapefile)
        print(f"  County CRS: {county_gdf.crs}")
        print(f"  Number of features: {len(county_gdf)}")
        
        # If multiple features, create union to get overall county boundary
        if len(county_gdf) > 1:
            print("  Creating county union from multiple features...")
            county_boundary = county_gdf.unary_union
            county_gdf = gpd.GeoDataFrame([1], geometry=[county_boundary], crs=county_gdf.crs)
        
        county_geom = county_gdf.geometry.iloc[0]
        print(f"  County boundary loaded successfully")
        
    except Exception as e:
        print(f"❌ Error loading county boundary: {e}")
        return None
    
    # Find all processed tmax files
    print("\nFinding processed TMAX files...")
    tmax_pattern = "tmax_hennepin_*_500m*.tif"
    tmax_files = glob.glob(os.path.join(tmax_files_dir, tmax_pattern))
    
    print(f"Found {len(tmax_files)} potential tmax files")
    
    # Filter by date range and extract dates
    date_pattern = r'tmax_hennepin_(\d{8})_500m'
    filtered_files = []
    
    for file_path in tmax_files:
        filename = os.path.basename(file_path)
        date_match = re.search(date_pattern, filename)
        
        if date_match:
            file_date = date_match.group(1)
            if start_date <= file_date <= end_date:
                filtered_files.append((file_date, file_path))
    
    # Sort by date
    filtered_files.sort(key=lambda x: x[0])
    
    print(f"Files in date range: {len(filtered_files)}")
    if filtered_files:
        print(f"  First: {filtered_files[0][0]}")
        print(f"  Last: {filtered_files[-1][0]}")
    else:
        print("❌ No files found in date range!")
        return None
    
    # Process each file to extract county average
    print(f"\nExtracting county averages...")
    daily_temps = []
    failed_dates = []
    
    for i, (date_str, file_path) in enumerate(filtered_files, 1):
        try:
            print(f"[{i:3d}/{len(filtered_files)}] Processing {date_str}...")
            
            with rasterio.open(file_path) as src:
                # Check if CRS match
                if county_gdf.crs != src.crs:
                    print(f"    Reprojecting county boundary: {county_gdf.crs} → {src.crs}")
                    county_gdf_reproj = county_gdf.to_crs(src.crs)
                    county_geom_reproj = county_gdf_reproj.geometry.iloc[0]
                else:
                    county_geom_reproj = county_geom
                
                # Mask raster to county boundary
                masked_data, masked_transform = mask(src, [county_geom_reproj], crop=True, nodata=src.nodata)
                
                # Extract valid temperature values
                temp_data = masked_data[0]  # First (and only) band
                
                if src.nodata is not None:
                    valid_temps = temp_data[temp_data != src.nodata]
                else:
                    valid_temps = temp_data[~np.isnan(temp_data)]
                
                if len(valid_temps) > 0:
                    county_avg_temp = float(np.mean(valid_temps))
                    county_min_temp = float(np.min(valid_temps))
                    county_max_temp = float(np.max(valid_temps))
                    valid_pixel_count = len(valid_temps)
                    
                    daily_temps.append({
                        'date': date_str,
                        'date_formatted': f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}",
                        'avg_temp_f': county_avg_temp,
                        'min_temp_f': county_min_temp,
                        'max_temp_f': county_max_temp,
                        'valid_pixels': valid_pixel_count
                    })
                    
                    print(f"    ✓ Avg: {county_avg_temp:.1f}°F, Range: {county_min_temp:.1f}-{county_max_temp:.1f}°F, Pixels: {valid_pixel_count:,}")
                    
                else:
                    print(f"    ❌ No valid temperature data for {date_str}")
                    failed_dates.append(date_str)
                    
        except Exception as e:
            print(f"    ❌ Error processing {date_str}: {str(e)}")
            failed_dates.append(date_str)
    
    # Create results DataFrame
    if daily_temps:
        df = pd.DataFrame(daily_temps)
        
        # Summary statistics
        print(f"\n{'='*60}")
        print(f"EXTRACTION SUMMARY")
        print(f"{'='*60}")
        print(f"Successfully processed: {len(daily_temps)} days")
        print(f"Failed: {len(failed_dates)} days")
        print(f"Temperature range: {df['avg_temp_f'].min():.1f}°F to {df['avg_temp_f'].max():.1f}°F")
        print(f"Average temperature: {df['avg_temp_f'].mean():.1f}°F")
        print(f"Standard deviation: {df['avg_temp_f'].std():.1f}°F")
        
        if failed_dates:
            print(f"Failed dates: {', '.join(failed_dates[:10])}")
            if len(failed_dates) > 10:
                print(f"... and {len(failed_dates) - 10} more")
        
        # Save outputs for model input
        save_temperature_input_files(df, output_dir)
        
        return df
    else:
        print("❌ No temperature data extracted!")
        return None

def save_temperature_input_files(df, output_dir):
    """
    Save temperature data in different formats for easy model input
    """
    
    print(f"\nSaving temperature input files to: {output_dir}")
    
    # 1. Full CSV with all details
    csv_path = os.path.join(output_dir, "hennepin_daily_tmax_2024.csv")
    df.to_csv(csv_path, index=False)
    print(f"  ✓ Full data: hennepin_daily_tmax_2024.csv")
    
    # 2. Simple temperature list (for easy model input)
    temp_list_path = os.path.join(output_dir, "temperature_list.txt")
    with open(temp_list_path, 'w') as f:
        f.write("# Daily average TMAX for Hennepin County (June 1 - August 31, 2024)\n")
        f.write("# Format: YYYY-MM-DD, Temperature (°F)\n")
        for _, row in df.iterrows():
            f.write(f"{row['date_formatted']}, {row['avg_temp_f']:.1f}\n")
    print(f"  ✓ Temperature list: temperature_list.txt")
    
    # 3. Python list format (ready to copy-paste into model)
    py_list_path = os.path.join(output_dir, "temperature_values.py")
    with open(py_list_path, 'w') as f:
        f.write("# Hennepin County daily average TMAX temperatures\n")
        f.write("# June 1 - August 31, 2024\n")
        f.write("# Generated from PRISM data\n\n")
        
        # List of temperatures only
        temps = df['avg_temp_f'].round(1).tolist()
        f.write("daily_temperatures = [\n")
        for i, temp in enumerate(temps):
            date = df.iloc[i]['date_formatted']
            f.write(f"    {temp:5.1f},  # {date}\n")
        f.write("]\n\n")
        
        # List with dates
        f.write("daily_temperature_data = [\n")
        for _, row in df.iterrows():
            f.write(f"    ('{row['date_formatted']}', {row['avg_temp_f']:5.1f}),\n")
        f.write("]\n\n")
        
        # Summary stats
        f.write(f"# Summary statistics:\n")
        f.write(f"# Number of days: {len(df)}\n")
        f.write(f"# Temperature range: {df['avg_temp_f'].min():.1f}°F to {df['avg_temp_f'].max():.1f}°F\n")
        f.write(f"# Average: {df['avg_temp_f'].mean():.1f}°F\n")
        f.write(f"# Standard deviation: {df['avg_temp_f'].std():.1f}°F\n")
        
    print(f"  ✓ Python format: temperature_values.py")
    
    # 4. JSON format
    import json
    json_path = os.path.join(output_dir, "temperature_data.json")
    json_data = {
        'metadata': {
            'source': 'PRISM tmax data',
            'region': 'Hennepin County, MN',
            'date_range': f"{df['date_formatted'].iloc[0]} to {df['date_formatted'].iloc[-1]}",
            'num_days': len(df),
            'avg_temperature': round(df['avg_temp_f'].mean(), 1),
            'temperature_range': [round(df['avg_temp_f'].min(), 1), round(df['avg_temp_f'].max(), 1)]
        },
        'daily_data': df.to_dict('records')
    }
    
    with open(json_path, 'w') as f:
        json.dump(json_data, f, indent=2)
    print(f"  ✓ JSON format: temperature_data.json")
    
    # 5. Create a simple example of how to use with the model
    example_path = os.path.join(output_dir, "model_usage_example.py")
    with open(example_path, 'w') as f:
        f.write("""# Example: How to use daily temperatures with your heat event model

from src.event import HeatEvent
import json

# Load temperature data
with open('temperature_data.json', 'r') as f:
    temp_data = json.load(f)

# Extract daily temperatures
daily_temps = [day['avg_temp_f'] for day in temp_data['daily_data']]
dates = [day['date_formatted'] for day in temp_data['daily_data']]

print(f"Running heat event model for {len(daily_temps)} days...")

# Run model for each day
results = []
for i, (date, temp) in enumerate(zip(dates, daily_temps)):
    print(f"Day {i+1}/{len(daily_temps)}: {date} at {temp:.1f}°F")
    
    # Create heat event with daily temperature
    heat_event = HeatEvent(temperature=temp)
    
    # Run simulation (can repeat M times for ensemble)
    heat_event.run_simulation()
    heat_event.process_results()
    
    # Store results
    results.append({
        'date': date,
        'temperature': temp,
        'gdf': heat_event.gdf  # Contains parcel-level results
    })

print(f"Completed {len(results)} daily simulations!")

# You can now analyze patterns across all days:
# - Which days had highest movement to cooling centers?
# - How does movement correlate with temperature?
# - Spatial patterns across the summer period
""")
    print(f"  ✓ Usage example: model_usage_example.py")

def preview_temperature_data(output_dir):
    """
    Preview the extracted temperature data
    """
    csv_path = os.path.join(output_dir, "hennepin_daily_tmax_2024.csv")
    
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        
        print(f"\n📊 TEMPERATURE DATA PREVIEW")
        print(f"{'='*60}")
        print(f"Period: {df['date_formatted'].iloc[0]} to {df['date_formatted'].iloc[-1]}")
        print(f"Number of days: {len(df)}")
        print()
        print("First 10 days:")
        print(df[['date_formatted', 'avg_temp_f', 'min_temp_f', 'max_temp_f']].head(10).to_string(index=False))
        print()
        print("Hottest days:")
        hot_days = df.nlargest(5, 'avg_temp_f')[['date_formatted', 'avg_temp_f']]
        print(hot_days.to_string(index=False))
        print()
        print("Coolest days:")
        cool_days = df.nsmallest(5, 'avg_temp_f')[['date_formatted', 'avg_temp_f']]
        print(cool_days.to_string(index=False))

if __name__ == "__main__":
    # Extract daily county average temperatures
    df = extract_daily_county_average_temps()
    
    if df is not None:
        # Preview the results
        preview_temperature_data(r"~\hennepin\data\validate_data\intermediate\temp_input")
        
        print(f"\n🎉 Temperature input data ready!")
        print(f"Files saved in: .\\data\\validate_data\\intermediate\\temp_input")
        print(f"Use 'temperature_values.py' for easy copy-paste into your model")