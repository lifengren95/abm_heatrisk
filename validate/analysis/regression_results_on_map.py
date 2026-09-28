#!/usr/bin/env python3
"""
Visualize Heat Tag Regression Coefficients and Significance on Map
Shows cooling centers with symbols sized by coefficient magnitude and colored by direction
Border style indicates significance level

Author: Project contributors
Date: 2025
"""
import os

import os
import sys

# Fix PROJ database conflicts BEFORE importing geopandas
os.environ['PROJ_LIB'] = ''  # Clear conflicting PROJ_LIB
os.environ.pop('PROJ_LIB', None)  # Remove it completely
os.environ['PROJ_NETWORK'] = 'OFF'  # Disable network downloads
os.environ['PYPROJ_GLOBAL_CONTEXT'] = 'ON'  # Use global context

import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap, Normalize, TwoSlopeNorm
from matplotlib.cm import ScalarMappable
import numpy as np
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Try to set up pyproj properly
try:
    import pyproj
    # Try to find the correct PROJ data directory
    conda_env = os.environ.get('CONDA_PREFIX')
    if conda_env:
        proj_lib_candidates = [
            os.path.join(conda_env, 'Library', 'share', 'proj'),
            os.path.join(conda_env, 'share', 'proj'),
            os.path.join(conda_env, 'lib', 'proj')
        ]
        for candidate in proj_lib_candidates:
            if os.path.exists(candidate):
                os.environ['PROJ_LIB'] = candidate
                pyproj.datadir.set_data_dir(candidate)
                break
except:
    pass

# Configuration
PATHS = {
    'regression_results': r'~\hennepin\output\validate\analysis\reg_byID_HEATTAG_1miles.csv',
    'cooling_centers': r'~\hennepin\data\validate_data\analysis\clean_cooling_centers_covar.csv',
    'county_parcels': r'~\hennepin\data\raw\Data\County_Parcels\County_Parcels.shp',
    'output_dir': r'~\hennepin\output\validate\analysis'
}

# Map configuration
MAP_CONFIG = {
    'figure_size': (16, 10),
    'dpi': 300,
    'background_color': '#f0f0f0',
    'parcels_color': '#e8e8e8',
    'parcels_edge_color': '#cccccc',
    'parcels_edge_width': 0.3,
    'symbol_min_size': 30,
    'symbol_max_size': 500,
    'font_size_title': 14,
    'font_size_label': 7,
    'font_size_legend': 9,
    'font_size_stats': 8
}

# Significance levels for border styling
SIG_STYLES = {
    '***': {'linewidth': 2.5, 'linestyle': '-', 'label': 'p < 0.01'},
    '**': {'linewidth': 2.0, 'linestyle': '-', 'label': 'p < 0.05'},
    '*': {'linewidth': 1.5, 'linestyle': '--', 'label': 'p < 0.10'},
    '': {'linewidth': 0.8, 'linestyle': ':', 'label': 'Not significant'}
}

# Outcome display names
OUTCOME_NAMES = {
    'lib_visits': 'Library Visits',
    'cellphone_visits': 'Cellphone Visits',
    'ed_encounters': 'ED Encounters'
}


def load_and_merge_data():
    """Load regression results and cooling center locations, then merge"""
    print("\nLoading data...")
    
    # Load regression results
    reg_df = pd.read_csv(PATHS['regression_results'])
    print(f"✓ Loaded regression results: {len(reg_df)} rows")
    
    # Load cooling center locations
    centers_df = pd.read_csv(PATHS['cooling_centers'])
    print(f"✓ Loaded cooling centers: {len(centers_df)} centers")
    
    # Check for required columns
    required_cols = ['id', 'latitude', 'longitude']
    missing_cols = [col for col in required_cols if col not in centers_df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in cooling centers data: {missing_cols}")
    
    # Merge data on 'id'
    merged_df = reg_df.merge(
        centers_df[['id', 'name', 'latitude', 'longitude', 'address', 'type']],
        on='id',
        how='left',
        suffixes=('_reg', '_center')
    )
    
    # Use name from regression results preferentially
    merged_df['name'] = merged_df['name_reg'].fillna(merged_df['name_center'])
    merged_df = merged_df.drop(['name_reg', 'name_center'], axis=1)
    
    # Check for unmatched centers
    unmatched = merged_df[merged_df['latitude'].isna()]
    if len(unmatched) > 0:
        print(f"⚠️  Warning: {len(unmatched)} regression results without location data")
        unique_unmatched = unmatched[['id', 'name']].drop_duplicates()
        for _, row in unique_unmatched.head(5).iterrows():
            print(f"   - ID {row['id']}: {row['name']}")
    
    # Filter to centers with location data
    merged_df = merged_df.dropna(subset=['latitude', 'longitude'])
    print(f"✓ Successfully matched {len(merged_df)} regression results with locations")
    
    return merged_df


def load_parcels():
    """Load county parcels shapefile for background"""
    try:
        parcels_gdf = gpd.read_file(PATHS['county_parcels'])
        print(f"✓ Loaded county parcels: {len(parcels_gdf)} features")
        
        # Try to project to local coordinate system with multiple fallback options
        try:
            # First attempt: EPSG code
            parcels_gdf = parcels_gdf.to_crs('EPSG:26915')
        except:
            try:
                # Second attempt: PROJ string
                parcels_gdf = parcels_gdf.to_crs('+proj=utm +zone=15 +ellps=GRS80 +datum=NAD83 +units=m +no_defs')
            except:
                # Final attempt: Keep original CRS
                print("⚠️  Could not project parcels, using original CRS")
        
        return parcels_gdf
    except Exception as e:
        print(f"⚠️  Could not load parcels: {e}")
        return None


def safe_create_geodataframe(df, lon_col='longitude', lat_col='latitude'):
    """Safely create a GeoDataFrame handling CRS issues"""
    from shapely.geometry import Point
    
    # Create geometry column
    geometry = [Point(xy) for xy in zip(df[lon_col], df[lat_col])]
    
    # Try different approaches to create GeoDataFrame with CRS
    try:
        # Attempt 1: Standard EPSG code
        gdf = gpd.GeoDataFrame(df, geometry=geometry, crs='EPSG:4326')
    except:
        try:
            # Attempt 2: PROJ string
            gdf = gpd.GeoDataFrame(df, geometry=geometry)
            gdf.crs = '+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs'
        except:
            # Attempt 3: No CRS
            print("⚠️  Creating GeoDataFrame without CRS due to PROJ issues")
            gdf = gpd.GeoDataFrame(df, geometry=geometry)
    
    return gdf


def safe_project_gdf(gdf, target_crs):
    """Safely project a GeoDataFrame handling CRS issues"""
    if gdf.crs is None:
        print("⚠️  GeoDataFrame has no CRS, skipping projection")
        return gdf
    
    try:
        # Try EPSG code
        return gdf.to_crs(target_crs)
    except:
        try:
            # Try PROJ string for UTM Zone 15N
            return gdf.to_crs('+proj=utm +zone=15 +ellps=GRS80 +datum=NAD83 +units=m +no_defs')
        except:
            print(f"⚠️  Could not project to {target_crs}, keeping original CRS")
            return gdf


def create_coefficient_map(data_df, outcome, parcels_gdf, output_path):
    """Create a map showing regression coefficients for a specific outcome"""
    
    # Filter data for this outcome
    outcome_df = data_df[data_df['outcome'] == outcome].copy()
    
    if len(outcome_df) == 0:
        print(f"⚠️  No data for outcome: {outcome}")
        return
    
    print(f"\nCreating map for {OUTCOME_NAMES[outcome]}...")
    print(f"  - Centers with data: {len(outcome_df)}")
    
    # Create GeoDataFrame safely
    gdf = safe_create_geodataframe(outcome_df)
    
    # Try to project to match parcels if available
    if parcels_gdf is not None and parcels_gdf.crs is not None:
        gdf = safe_project_gdf(gdf, 'EPSG:26915')
    
    # Create figure
    fig, ax = plt.subplots(1, 1, figsize=MAP_CONFIG['figure_size'])
    ax.set_facecolor(MAP_CONFIG['background_color'])
    
    # Plot parcels background if available
    if parcels_gdf is not None:
        try:
            parcels_gdf.boundary.plot(
                ax=ax,
                color=MAP_CONFIG['parcels_edge_color'],
                linewidth=MAP_CONFIG['parcels_edge_width'],
                alpha=0.3
            )
        except Exception as e:
            print(f"⚠️  Could not plot parcels: {e}")
    
    # Calculate symbol sizes based on absolute coefficient value
    abs_coef = gdf['coef_heat'].abs()
    non_zero_coef = abs_coef[abs_coef > 0]
    
    if len(non_zero_coef) > 0:
        # Use percentile-based sizing
        size_min = np.percentile(non_zero_coef, 10)
        size_max = np.percentile(non_zero_coef, 90)
        
        # Normalize and scale to symbol sizes
        def get_symbol_size(coef_abs):
            if coef_abs == 0 or pd.isna(coef_abs):
                return MAP_CONFIG['symbol_min_size']
            # Clip to range
            clipped = np.clip(coef_abs, size_min, size_max)
            # Normalize to 0-1
            if size_max > size_min:
                normalized = (clipped - size_min) / (size_max - size_min)
            else:
                normalized = 0.5
            # Scale to symbol size range
            return MAP_CONFIG['symbol_min_size'] + normalized * (MAP_CONFIG['symbol_max_size'] - MAP_CONFIG['symbol_min_size'])
        
        gdf['symbol_size'] = abs_coef.apply(get_symbol_size)
    else:
        gdf['symbol_size'] = MAP_CONFIG['symbol_min_size']
    
    # Create diverging colormap (blue for negative, red for positive)
    cmap = plt.cm.RdBu_r  # Red for positive, Blue for negative
    
    # Find range for normalization (symmetric around 0)
    coef_vals = gdf['coef_heat'].dropna()
    if len(coef_vals) > 0:
        max_abs = max(abs(coef_vals.min()), abs(coef_vals.max()))
        norm = TwoSlopeNorm(vmin=-max_abs, vcenter=0, vmax=max_abs)
    else:
        norm = TwoSlopeNorm(vmin=-1, vcenter=0, vmax=1)
    
    # Plot points
    for idx, row in gdf.iterrows():
        # Get coordinates (handle both projected and unprojected)
        try:
            x_coord = row.geometry.x
            y_coord = row.geometry.y
        except:
            # Fallback to original lat/lon if geometry fails
            x_coord = row['longitude']
            y_coord = row['latitude']
        
        if pd.isna(row['coef_heat']):
            color = 'gray'
            alpha = 0.5
        else:
            color = cmap(norm(row['coef_heat']))
            alpha = 0.8
        
        # Get border style based on significance
        sig_level = row['sig'] if pd.notna(row['sig']) else ''
        edge_style = SIG_STYLES.get(sig_level, SIG_STYLES[''])
        
        # Plot the point
        scatter = ax.scatter(
            x_coord,
            y_coord,
            s=row['symbol_size'],
            c=[color],
            edgecolor='black',
            linewidth=edge_style['linewidth'],
            alpha=alpha,
            zorder=5
        )
        
        # matplotlib doesn't support linestyle in scatter, so we'll skip that for now
        
        # Add labels for highly significant or large effects
        if (row['sig'] in ['***', '**'] and abs(row['coef_heat']) > np.percentile(abs_coef[abs_coef > 0], 75) if len(non_zero_coef) > 0 else False) or \
           (pd.notna(row['coef_heat']) and abs(row['coef_heat']) > np.percentile(abs_coef[abs_coef > 0], 90) if len(non_zero_coef) > 0 else False):
            # Shorten name for label
            label_name = row['name'].split()[0] if pd.notna(row['name']) else f"ID{row['id']}"
            ax.annotate(
                f"{label_name}\n({row['coef_heat']:.2f}{row['sig']})",
                xy=(x_coord, y_coord),
                xytext=(5, 5),
                textcoords='offset points',
                fontsize=MAP_CONFIG['font_size_label'],
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7)
            )
    
    # Set map extent with padding
    if hasattr(gdf, 'total_bounds'):
        bounds = gdf.total_bounds
    else:
        # Calculate bounds manually from coordinates
        x_coords = [row.geometry.x if hasattr(row.geometry, 'x') else row['longitude'] for _, row in gdf.iterrows()]
        y_coords = [row.geometry.y if hasattr(row.geometry, 'y') else row['latitude'] for _, row in gdf.iterrows()]
        bounds = [min(x_coords), min(y_coords), max(x_coords), max(y_coords)]
    
    x_pad = (bounds[2] - bounds[0]) * 0.1
    y_pad = (bounds[3] - bounds[1]) * 0.1
    ax.set_xlim(bounds[0] - x_pad, bounds[2] + x_pad)
    ax.set_ylim(bounds[1] - y_pad, bounds[3] + y_pad)
    
    # Remove axes
    ax.set_aspect('equal')
    ax.axis('off')
    
    # Add title
    title = f'Heat Day Effect on {OUTCOME_NAMES[outcome]}\n1-Mile Buffer Analysis'
    ax.set_title(title, fontsize=MAP_CONFIG['font_size_title'], pad=20, weight='bold')
    
    # Create legends
    # 1. Size legend (coefficient magnitude)
    if len(non_zero_coef) > 0:
        size_values = [np.percentile(non_zero_coef, p) for p in [25, 50, 75]]
    else:
        size_values = [0.1, 0.5, 1.0]
    
    size_handles = []
    for val in size_values:
        size = get_symbol_size(val) if len(non_zero_coef) > 0 else MAP_CONFIG['symbol_min_size'] + val * 100
        handle = plt.scatter([], [], s=size, c='gray', 
                           edgecolor='black', linewidth=1, alpha=0.6)
        size_handles.append(handle)
    
    size_labels = [f'|β| = {val:.2f}' for val in size_values]
    size_legend = ax.legend(
        size_handles, size_labels,
        title='Coefficient Magnitude',
        loc='upper left',
        bbox_to_anchor=(0.02, 0.98),
        frameon=True,
        fancybox=True,
        fontsize=MAP_CONFIG['font_size_legend']
    )
    
    # 2. Significance legend
    ax.add_artist(size_legend)  # Keep size legend
    sig_handles = []
    sig_labels = []
    for sig_key in ['***', '**', '*', '']:
        style = SIG_STYLES[sig_key]
        handle = plt.Line2D([0], [0], color='black', 
                          linewidth=style['linewidth'],
                          linestyle=style['linestyle'])
        sig_handles.append(handle)
        sig_labels.append(style['label'])
    
    sig_legend = ax.legend(
        sig_handles, sig_labels,
        title='Significance Level',
        loc='upper left',
        bbox_to_anchor=(0.02, 0.80),
        frameon=True,
        fancybox=True,
        fontsize=MAP_CONFIG['font_size_legend']
    )
    
    # 3. Color legend (colorbar)
    ax.add_artist(sig_legend)
    sm = ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label('Heat Day Coefficient\n(Positive = More visits on heat days)', 
                   fontsize=MAP_CONFIG['font_size_legend'])
    cbar.ax.tick_params(labelsize=MAP_CONFIG['font_size_legend']-2)
    
    # Add summary statistics
    valid_coef = gdf['coef_heat'].dropna()
    sig_coef = gdf[gdf['sig'].isin(['*', '**', '***'])]['coef_heat']
    
    stats_text = f'n = {len(gdf)} centers\n'
    if len(valid_coef) > 0:
        stats_text += f'Mean β = {valid_coef.mean():.3f}\n'
        stats_text += f'Median β = {valid_coef.median():.3f}\n'
        stats_text += f'Significant: {len(sig_coef)}/{len(valid_coef)} ({100*len(sig_coef)/len(valid_coef):.0f}%)'
    
    ax.text(0.98, 0.02, stats_text, transform=ax.transAxes,
           fontsize=MAP_CONFIG['font_size_stats'],
           verticalalignment='bottom', horizontalalignment='right',
           bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.8))
    
    # Save map
    plt.tight_layout()
    plt.savefig(output_path, dpi=MAP_CONFIG['dpi'], bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    print(f"✓ Map saved to: {output_path}")
    
    plt.close()


def create_summary_statistics(data_df, output_dir):
    """Create summary statistics table for all outcomes"""
    
    summary_rows = []
    
    for outcome in ['lib_visits', 'cellphone_visits', 'ed_encounters']:
        outcome_df = data_df[data_df['outcome'] == outcome]
        valid_coef = outcome_df['coef_heat'].dropna()
        
        if len(valid_coef) == 0:
            continue
            
        # Count significance levels
        sig_counts = outcome_df['sig'].value_counts()
        
        summary_rows.append({
            'Outcome': OUTCOME_NAMES[outcome],
            'N_centers': len(outcome_df),
            'N_valid': len(valid_coef),
            'Mean_coef': valid_coef.mean(),
            'Median_coef': valid_coef.median(),
            'Std_coef': valid_coef.std(),
            'Min_coef': valid_coef.min(),
            'Max_coef': valid_coef.max(),
            'N_positive': (valid_coef > 0).sum(),
            'N_negative': (valid_coef < 0).sum(),
            'N_sig_01': sig_counts.get('***', 0),
            'N_sig_05': sig_counts.get('**', 0),
            'N_sig_10': sig_counts.get('*', 0),
            'Mean_R2': outcome_df['r2'].mean()
        })
    
    summary_df = pd.DataFrame(summary_rows)
    
    # Save summary
    summary_path = Path(output_dir) / 'heat_tag_regression_summary.csv'
    summary_df.to_csv(summary_path, index=False)
    print(f"\n✓ Summary statistics saved to: {summary_path}")
    
    # Print summary
    print("\n" + "="*60)
    print("SUMMARY STATISTICS")
    print("="*60)
    for _, row in summary_df.iterrows():
        print(f"\n{row['Outcome']}:")
        print(f"  Centers analyzed: {row['N_valid']:.0f}/{row['N_centers']:.0f}")
        print(f"  Mean coefficient: {row['Mean_coef']:.3f} (SD: {row['Std_coef']:.3f})")
        print(f"  Range: [{row['Min_coef']:.3f}, {row['Max_coef']:.3f}]")
        print(f"  Direction: {row['N_positive']:.0f} positive, {row['N_negative']:.0f} negative")
        print(f"  Significant: {row['N_sig_01']:.0f} (p<0.01), {row['N_sig_05']:.0f} (p<0.05), {row['N_sig_10']:.0f} (p<0.10)")
        print(f"  Mean R²: {row['Mean_R2']:.3f}")


def main():
    """Main execution function"""
    print("🗺️  CREATING HEAT TAG REGRESSION COEFFICIENT MAPS")
    print("="*60)
    
    try:
        # Create output directory if needed
        output_dir = Path(PATHS['output_dir'])
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load and merge data
        merged_df = load_and_merge_data()
        
        # Load parcels for background
        parcels_gdf = load_parcels()
        
        # Generate timestamp for output files
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create maps for each outcome
        for outcome in ['lib_visits', 'cellphone_visits', 'ed_encounters']:
            output_filename = f"heat_tag_coef_map_{outcome}_{timestamp}.png"
            output_path = output_dir / output_filename
            create_coefficient_map(merged_df, outcome, parcels_gdf, output_path)
        
        # Create summary statistics
        create_summary_statistics(merged_df, output_dir)
        
        # Save merged data for reference
        merged_output = output_dir / f'heat_tag_regression_merged_{timestamp}.csv'
        merged_df.to_csv(merged_output, index=False)
        print(f"\n✓ Merged data saved to: {merged_output}")
        
        print("\n✅ All maps created successfully!")
        print(f"📊 Output saved to: {output_dir}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())