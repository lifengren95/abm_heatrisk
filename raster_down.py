import rasterio
from rasterio.enums import Resampling
import numpy as np

def downsample_raster(input_tif, output_tif, scale_factor=2):
    with rasterio.open(input_tif) as src:
        new_height = src.height // scale_factor
        new_width = src.width // scale_factor

        # Calculate new transform
        transform = src.transform * src.transform.scale(
            src.width / new_width,
            src.height / new_height
        )

        data = src.read(
            out_shape=(src.count, new_height, new_width),
            resampling=Resampling.average  # use average instead of bilinear for clean downsample
        )

        profile = src.profile
        profile.update({
            'height': new_height,
            'width': new_width,
            'transform': transform
        })

        with rasterio.open(output_tif, 'w', **profile) as dst:
            dst.write(data)

# Example usage
for scale in [2, 10, 25, 50, 100]:
    res = scale*10
    input_tif = './data/LandSurface_Temperature_2022.tif'
    output_tif = f'./data/LandSurface_Temperature_2022_{res}m.tif'
    
    downsample_raster(input_tif, output_tif, scale_factor=scale)  # Adjust scale_factor as needed
