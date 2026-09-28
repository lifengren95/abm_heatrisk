#!/usr/bin/env python3
"""
Create Graduated Symbol Map of Relative Error from Cellphone Heat vs Non-Heat Validation
Shows cooling centers with symbols sized/colored by relative error for July 2020 cellphone data

Usage: python visualize_validate_2020_cellphone.py

Author: Project contributors
Date: 2025
"""
import os

import os
import sys

# Try to fix PROJ database conflicts
os.environ['PROJ_LIB'] = ''  # Clear any conflicting PROJ_LIB settings

import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.cm import ScalarMappable
import numpy as np
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


# Configuration - All paths relative to script location
PATHS = {
    'cooling_centers': '../../data/validate_data/intermediate/cooling_center.csv',
    'validation_results': '../../output/validate/geometric_model_5runs/cellphone_validate/cellphone_2020_July/cellphone_heat_nonheat_validation_2020July_20250722_043044.csv',
    'county_parcels': '../../data/raw/Data/County_Parcels/County_Parcels.shp',
    'output_dir': '../../output/validate/geometric_model_5runs/cellphone_validate/cellphone_2020_July/maps/'
}

# Map configuration
MAP_CONFIG = {
    'figure_size': (14, 10),
    'dpi': 300,
    'background_color': '#f0f0f0',
    'parcels_color': '#e8e8e8',
    'parcels_edge_color': '#cccccc',
    'parcels_edge_width': 0.5,
    'symbol_min_size': 50,
    'symbol_max_size': 500,
    'symbol_edge_color': 'black',
    'symbol_edge_width': 1,
    'font_size_title': 16,
    'font_size_label': 8,
    'font_size_legend': 10
}


def setup_paths():
    """Set up working directory and convert relative paths to absolute"""
    # Set working directory to script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    print(f"Working directory: {os.getcwd()}")
    
    # Convert relative paths to absolute
    abs_paths = {}
    for key, rel_path in PATHS.items():
        abs_path = Path(rel_path).resolve()
        abs_paths[key] = abs_path
        
        # Check if input files exist
        if key != 'output_dir' and not abs_path.exists():
            print(f"⚠️  Warning: {key} not found at {abs_path}")
    
    # Create output directory if needed
    abs_paths['output_dir'].mkdir(parents=True, exist_ok=True)
    
    return abs_paths


def load_data(paths):
    """Load all required data"""
    print("\nLoading data...")
    
    # Load validation results
    validation_df = pd.read_csv(paths['validation_results'])
    # Filter out the "Overall" row - it's not a physical location
    validation_df = validation_df[validation_df['cooling_option'] != 'Overall'].copy()
    print(f"✓ Loaded validation results: {len(validation_df)} cooling centers")
    
    # Load cooling center locations
    centers_df = pd.read_csv(paths['cooling_centers'])
    print(f"✓ Loaded all cooling center locations: {len(centers_df)} centers")
    
    # Load county parcels for background (optional)
    parcels_gdf = None
    try:
        parcels_gdf = gpd.read_file(paths['county_parcels'])
        print(f"✓ Loaded county parcels: {len(parcels_gdf)} features")
    except Exception as e:
        print(f"⚠️  Could not load parcels shapefile: {e}")
        print("   Proceeding without background parcels...")
    
    return validation_df, centers_df, parcels_gdf


def join_validation_with_locations(validation_df, centers_df):
    """Join validation results with cooling center locations"""
    print("\nJoining validation results with locations...")
    
    # Merge on cooling center name
    merged_df = validation_df.merge(
        centers_df[['name', 'latitude', 'longitude', 'address', 'type']],
        left_on='cooling_option',
        right_on='name',
        how='left'
    )
    
    # Check for unmatched centers
    unmatched = merged_df[merged_df['latitude'].isna()]
    if len(unmatched) > 0:
        print(f"⚠️  Warning: {len(unmatched)} centers without location data:")
        # Show first 10 unmatched
        for i, center in enumerate(unmatched['cooling_option'].values[:10]):
            print(f"   - {center}")
        if len(unmatched) > 10:
            print(f"   ... and {len(unmatched) - 10} more")
    
    # Filter to centers with location data
    merged_df = merged_df.dropna(subset=['latitude', 'longitude'])
    
    # Convert to GeoDataFrame with workaround for PROJ issues
    geometry = gpd.points_from_xy(merged_df.longitude, merged_df.latitude)
    
    # Try different approaches to set CRS due to PROJ database conflicts
    try:
        # First attempt: Create without CRS, then set it
        merged_gdf = gpd.GeoDataFrame(merged_df, geometry=geometry)
        merged_gdf.crs = 'EPSG:4326'
    except Exception as e1:
        try:
            # Second attempt: Use PROJ string instead of EPSG code
            merged_gdf = gpd.GeoDataFrame(merged_df, geometry=geometry)
            merged_gdf.crs = '+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs'
        except Exception as e2:
            # Final attempt: Create without CRS (will set later if needed)
            print(f"⚠️  Warning: Could not set CRS due to PROJ conflicts. Proceeding without CRS.")
            merged_gdf = gpd.GeoDataFrame(merged_df, geometry=geometry)
    
    print(f"✓ Successfully matched {len(merged_gdf)} centers with locations")
    
    return merged_gdf


def categorize_relative_error(relative_error):
    """Categorize relative error into bins for symbol sizing"""
    # Handle NaN and infinite values
    if pd.isna(relative_error) or np.isinf(relative_error):
        return 'No Data'
    
    # Convert to percentage
    error_pct = abs(relative_error * 100)
    
    # Define bins
    if error_pct < 50:
        return '0-50%'
    elif error_pct < 100:
        return '50-100%'
    elif error_pct < 200:
        return '100-200%'
    elif error_pct < 500:
        return '200-500%'
    else:
        return '>500%'


def get_symbol_size(category):
    """Get symbol size based on error category"""
    size_map = {
        'No Data': MAP_CONFIG['symbol_min_size'],
        '0-50%': MAP_CONFIG['symbol_min_size'] + 50,
        '50-100%': MAP_CONFIG['symbol_min_size'] + 100,
        '100-200%': MAP_CONFIG['symbol_min_size'] + 200,
        '200-500%': MAP_CONFIG['symbol_min_size'] + 300,
        '>500%': MAP_CONFIG['symbol_max_size']
    }
    return size_map.get(category, MAP_CONFIG['symbol_min_size'])


def create_diverging_colormap():
    """Create a diverging colormap for relative error"""
    # Blue (negative) -> White (zero) -> Red (positive)
    colors = ['#2166ac', '#4393c3', '#92c5de', '#d1e5f0', 
              '#f7f7f7', 
              '#fddbc7', '#f4a582', '#d6604d', '#b2182b']
    n_bins = 100
    cmap_name = 'relative_error'
    return LinearSegmentedColormap.from_list(cmap_name, colors, N=n_bins)


def create_map(merged_gdf, parcels_gdf, output_path):
    """Create the graduated symbol map"""
    print("\nCreating map...")
    
    # Create figure and axis
    fig, ax = plt.subplots(1, 1, figsize=MAP_CONFIG['figure_size'])
    ax.set_facecolor(MAP_CONFIG['background_color'])
    
    # Plot county parcels as background if available
    parcels_plotted = False
    if parcels_gdf is not None:
        try:
            # Try to project to local coordinate system for better display
            parcels_gdf_projected = parcels_gdf.to_crs('EPSG:26915')  # UTM Zone 15N for Minnesota
            parcels_gdf_projected.boundary.plot(
                ax=ax,
                color=MAP_CONFIG['parcels_edge_color'],
                linewidth=MAP_CONFIG['parcels_edge_width'],
                alpha=0.3
            )
            parcels_plotted = True
        except Exception as e:
            print(f"⚠️  Warning: Could not project parcels. Trying original CRS. Error: {e}")
            try:
                parcels_gdf.boundary.plot(
                    ax=ax,
                    color=MAP_CONFIG['parcels_edge_color'],
                    linewidth=MAP_CONFIG['parcels_edge_width'],
                    alpha=0.3
                )
                parcels_plotted = True
            except Exception as e2:
                print(f"⚠️  Warning: Could not plot parcels. Continuing without background. Error: {e2}")
    
    # Try to project points to same CRS if parcels were projected
    points_projected = False
    if parcels_plotted:
        try:
            merged_gdf = merged_gdf.to_crs('EPSG:26915')
            points_projected = True
        except Exception as e:
            print(f"⚠️  Warning: Could not project points to UTM. Using lat/lon. Error: {e}")
    
    # If projection failed or no parcels, ensure we have valid geometry
    if not points_projected:
        if 'longitude' in merged_gdf.columns and 'latitude' in merged_gdf.columns:
            # Recreate geometry from lat/lon if needed
            merged_gdf['geometry'] = gpd.points_from_xy(merged_gdf.longitude, merged_gdf.latitude)
    
    # Add error categories and sizes
    merged_gdf['error_category'] = merged_gdf['relative_error'].apply(categorize_relative_error)
    merged_gdf['symbol_size'] = merged_gdf['error_category'].apply(get_symbol_size)
    
    # Prepare colormap
    cmap = create_diverging_colormap()
    
    # Handle NaN and infinite values for coloring
    color_values = merged_gdf['relative_error'].copy()
    color_values = color_values.replace([np.inf, -np.inf], np.nan)
    
    # Set color normalization (-2 to 2 for -200% to 200%)
    vmin, vmax = -2, 2
    norm = Normalize(vmin=vmin, vmax=vmax)
    
    # Plot points with graduated symbols
    for idx, row in merged_gdf.iterrows():
        if pd.isna(row['relative_error']) or np.isinf(row['relative_error']):
            color = 'gray'
            alpha = 0.5
        else:
            # Clip values to range for coloring
            clipped_value = np.clip(row['relative_error'], vmin, vmax)
            color = cmap(norm(clipped_value))
            alpha = 0.8
        
        ax.scatter(
            row.geometry.x,
            row.geometry.y,
            s=row['symbol_size'],
            c=[color],
            edgecolor=MAP_CONFIG['symbol_edge_color'],
            linewidth=MAP_CONFIG['symbol_edge_width'],
            alpha=alpha,
            zorder=5
        )
        
        # Add labels for centers with extreme errors (>500% or <-500%)
        if abs(row['relative_error']) > 5 or pd.isna(row['relative_error']):
            # Shorten long names for better display
            label = row['cooling_option']
            if len(label) > 20:
                label = label[:17] + '...'
            
            ax.annotate(
                label,
                xy=(row.geometry.x, row.geometry.y),
                xytext=(5, 5),
                textcoords='offset points',
                fontsize=MAP_CONFIG['font_size_label'],
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7)
            )
    
    # Set map extent with padding
    bounds = merged_gdf.total_bounds
    x_pad = (bounds[2] - bounds[0]) * 0.1
    y_pad = (bounds[3] - bounds[1]) * 0.1
    ax.set_xlim(bounds[0] - x_pad, bounds[2] + x_pad)
    ax.set_ylim(bounds[1] - y_pad, bounds[3] + y_pad)
    
    # Remove axes
    ax.set_aspect('equal')
    ax.axis('off')
    
    # Add title
    title = 'Cellphone Data Heat Response Validation (July 2020)\nRelative Error: Simulated vs Real Heat/Non-Heat Ratio'
    ax.set_title(title, fontsize=MAP_CONFIG['font_size_title'], pad=20, weight='bold')
    
    # Create legend
    # Size legend
    size_categories = ['0-50%', '50-100%', '100-200%', '200-500%', '>500%']
    size_handles = []
    for cat in size_categories:
        size = get_symbol_size(cat)
        handle = plt.scatter([], [], s=size, c='gray', 
                           edgecolor='black', linewidth=1, alpha=0.6)
        size_handles.append(handle)
    
    size_legend = ax.legend(
        size_handles, size_categories,
        title='Absolute Error',
        loc='upper left',
        bbox_to_anchor=(0.02, 0.98),
        frameon=True,
        fancybox=True,
        fontsize=MAP_CONFIG['font_size_legend']
    )
    
    # Color legend (colorbar)
    sm = ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label('Relative Error\n(Negative = Underestimate)', 
                   fontsize=MAP_CONFIG['font_size_legend'])
    cbar.ax.tick_params(labelsize=MAP_CONFIG['font_size_legend']-2)
    
    # Format colorbar ticks as percentages
    cbar_ticks = cbar.get_ticks()
    cbar.set_ticklabels([f'{int(t*100)}%' for t in cbar_ticks])
    
    # Add legend for gray points
    ax.add_artist(size_legend)  # Re-add size legend
    gray_handle = plt.scatter([], [], s=100, c='gray', 
                            edgecolor='black', linewidth=1, alpha=0.5)
    ax.legend([gray_handle], ['No Data/Infinite'], 
             loc='upper left', bbox_to_anchor=(0.02, 0.75),
             frameon=True, fancybox=True, fontsize=MAP_CONFIG['font_size_legend'])
    
    # Add summary statistics
    valid_errors = merged_gdf['relative_error'].replace([np.inf, -np.inf], np.nan).dropna()
    if len(valid_errors) > 0:
        stats_text = (f'n = {len(merged_gdf)} centers\n'
                     f'Mean Error: {valid_errors.mean():.1%}\n'
                     f'Median Error: {valid_errors.median():.1%}')
        ax.text(0.98, 0.02, stats_text, transform=ax.transAxes,
               fontsize=MAP_CONFIG['font_size_legend']-1,
               verticalalignment='bottom', horizontalalignment='right',
               bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.8))
    
    # Add data source note
    ax.text(0.02, 0.02, 'Data: Cellphone visitation data (July 2020)', transform=ax.transAxes,
           fontsize=MAP_CONFIG['font_size_legend']-2,
           verticalalignment='bottom', horizontalalignment='left',
           style='italic', alpha=0.7)
    
    # Save map
    plt.tight_layout()
    plt.savefig(output_path, dpi=MAP_CONFIG['dpi'], bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    print(f"✓ Map saved to: {output_path}")
    
    # Close figure to free memory
    plt.close()
    
    return merged_gdf


def save_supplementary_data(merged_gdf, output_dir):
    """Save GeoJSON of the mapped data for future use"""
    geojson_path = output_dir / 'cellphone_cooling_centers_relative_error_2020.geojson'
    
    # Select relevant columns
    export_cols = ['cooling_option', 'type', 'address', 
                   'real_heat_nonheat_ratio', 'sim_heat_nonheat_ratio',
                   'relative_error', 'mae_ratio', 'error_category', 'geometry']
    
    # Check which columns exist
    existing_cols = [col for col in export_cols if col in merged_gdf.columns]
    export_gdf = merged_gdf[existing_cols].copy()
    
    # Try to convert to WGS84 for GeoJSON
    try:
        export_gdf = export_gdf.to_crs('EPSG:4326')
    except Exception as e:
        print(f"⚠️  Warning: Could not convert to WGS84 for GeoJSON. Error: {e}")
        # If we can't convert, check if we have lat/lon columns
        if 'longitude' in merged_gdf.columns and 'latitude' in merged_gdf.columns:
            # Recreate geometry from lat/lon
            export_gdf['geometry'] = gpd.points_from_xy(
                merged_gdf.longitude, 
                merged_gdf.latitude
            )
    
    # Save as GeoJSON
    try:
        export_gdf.to_file(geojson_path, driver='GeoJSON')
        print(f"✓ Saved GeoJSON to: {geojson_path}")
    except Exception as e:
        print(f"⚠️  Warning: Could not save GeoJSON. Error: {e}")
        # Try saving as CSV instead
        csv_path = output_dir / 'cellphone_cooling_centers_relative_error_2020.csv'
        export_df = export_gdf.drop('geometry', axis=1)
        if 'longitude' in merged_gdf.columns and 'latitude' in merged_gdf.columns:
            export_df['longitude'] = merged_gdf['longitude']
            export_df['latitude'] = merged_gdf['latitude']
        export_df.to_csv(csv_path, index=False)
        print(f"✓ Saved data as CSV instead: {csv_path}")


def main():
    """Main execution function"""
    print("🗺️  CREATING CELLPHONE DATA RELATIVE ERROR MAP")
    print("="*60)
    
    try:
        # Set up paths
        paths = setup_paths()
        
        # Load data
        validation_df, centers_df, parcels_gdf = load_data(paths)
        
        # Join validation results with locations
        merged_gdf = join_validation_with_locations(validation_df, centers_df)
        
        # Generate output filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"cellphone_relative_error_map_heat_nonheat_2020_{timestamp}.png"
        output_path = paths['output_dir'] / output_filename
        
        # Create map
        final_gdf = create_map(merged_gdf, parcels_gdf, output_path)
        
        # Save supplementary data
        save_supplementary_data(final_gdf, paths['output_dir'])
        
        print("\n✅ Map creation complete!")
        print(f"📊 Output saved to: {paths['output_dir']}")
        
        # Print summary of extreme values
        print("\n📈 Extreme Values Summary:")
        sorted_gdf = merged_gdf.sort_values('relative_error', ascending=False)
        
        # Filter out infinite values for display
        finite_gdf = sorted_gdf[~np.isinf(sorted_gdf['relative_error'])]
        
        print("\nTop 5 Overestimations (positive error):")
        for idx, row in finite_gdf.head(5).iterrows():
            print(f"  {row['cooling_option']}: {row['relative_error']:.1%}")
            
        print("\nTop 5 Underestimations (negative error):")
        for idx, row in finite_gdf.tail(5).iterrows():
            print(f"  {row['cooling_option']}: {row['relative_error']:.1%}")
        
        # Count infinite values
        inf_count = np.isinf(merged_gdf['relative_error']).sum()
        if inf_count > 0:
            print(f"\n⚠️  Note: {inf_count} centers have infinite relative error values")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())