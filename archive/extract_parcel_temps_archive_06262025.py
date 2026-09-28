#!/usr/bin/env python3
"""
Simple script to extract parcel-level temperatures from raster TIF
Input: Temperature raster TIF
Output: Parcel-level temperature data as TIF
"""

import sys
import os
sys.path.append(r'~\hennepin\code\hennepin_heat_abm')

from src.event import HeatEvent
import geopandas as gpd
import rasterio
from rasterio.features import rasterize
import numpy as np

# Paths
input_tif = r"~\hennepin\data\validate_data\intermediate\prism\test\tmax_hennepin_20240831_500m.tif"
output_dir = r"~\hennepin\output\oneoff"
output_tif = os.path.join(output_dir, "parcel_temperatures_20240831_testoldscript.tif")

# Create output directory
os.makedirs(output_dir, exist_ok=True)

# Create HeatEvent instance
heat_event = HeatEvent(temperature=75)  # fallback temperature

# Load parcel data
print("Loading parcel data...")
heat_event.load_data()

# Extract temperatures from raster
print("Extracting temperatures...")
heat_event.join_temps_to_parcels(temp_raster=input_tif, temperature=75)

# Create GeoDataFrame with temperature data
print("Creating output data...")
data = []
for parcel in heat_event.parcels:
    data.append({
        'pid': parcel.id,
        'temperature': parcel.attributes['temperature'],
        'geometry': parcel.attributes['geometry']
    })

gdf = gpd.GeoDataFrame(data).set_crs(epsg=26915)

# Read input raster to get template properties
with rasterio.open(input_tif) as src:
    template_profile = src.profile.copy()
    template_transform = src.transform
    template_shape = src.shape

# Rasterize parcels with temperature values
print("Rasterizing to TIF...")
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

with rasterio.open(output_tif, 'w', **template_profile) as dst:
    dst.write(rasterized, 1)

print(f"Output saved to: {output_tif}")
print(f"Processed {len(gdf)} parcels")
print(f"Temperature range: {gdf.temperature.min():.2f} - {gdf.temperature.max():.2f}°F")