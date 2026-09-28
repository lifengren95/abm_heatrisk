#!/usr/bin/env python3
"""
Heat Risk Model Validation Visualization
Creates visual analysis of validation results including scatter plots, maps, and time series

Usage: python run_validation_visualization.py [--download-county]

Options:
    --download-county: Download Hennepin County boundary from Census TIGER data

Author: Project contributors
Date: 2025
"""

import os
import sys
import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime
import warnings
import argparse
import pickle
warnings.filterwarnings('ignore')

# Set style
try:
    plt.style.use('seaborn-v0_8-darkgrid')
except:
    try:
        plt.style.use('seaborn-darkgrid')
    except:
        plt.style.use('default')
        plt.rcParams['axes.grid'] = True
        plt.rcParams['grid.alpha'] = 0.3

sns.set_palette("husl")


class ValidationVisualizer:
    def __init__(self):
        """Initialize visualizer"""
        # Set working directory to script location
        self.code_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(self.code_dir)
        print(f"Working directory: {os.getcwd()}")
        
        # Paths
        self.base_path = Path("../..")
        self.output_validate_path = self.base_path / "output/validate"
        self.data_path = self.base_path / "data/validate_data/intermediate"
        
        # Create visualization output directory
        self.vis_output_path = self.output_validate_path / "visualizations"
        self.vis_output_path.mkdir(parents=True, exist_ok=True)
        
        # Hennepin County boundary path - adjust if needed
        self.county_boundary_path = self.base_path / "data/raw/hennepin_county_boundary/hennepin_county.shp"
        
        # Alternative: Use parcels data to derive boundary
        self.parcels_pickle_path = self.base_path / "data/preprocessed_data/parcels_prepared.pkl"
        self.parcels_metadata_path = self.base_path / "data/preprocessed_data/parcels_metadata.json"
        
        print(f"Visualizations will be saved to: {self.vis_output_path}")
        
    def load_data(self):
        """Load validation results and cooling center locations"""
        print("\nLoading validation data...")
        
        # Find most recent validation files
        validation_files = list(self.output_validate_path.glob("validation_comparison_*.csv"))
        stats_files = list(self.output_validate_path.glob("validation_statistics_*.csv"))
        
        if not validation_files or not stats_files:
            raise FileNotFoundError("No validation results found. Run validation study first.")
            
        # Use most recent files
        validation_files.sort()
        stats_files.sort()
        
        self.validation_file = validation_files[-1]
        self.stats_file = stats_files[-1]
        
        print(f"Using validation file: {self.validation_file.name}")
        print(f"Using statistics file: {self.stats_file.name}")
        
        # Load data
        self.validation_df = pd.read_csv(self.validation_file)
        self.validation_df['date'] = pd.to_datetime(self.validation_df['date'])
        
        self.stats_df = pd.read_csv(self.stats_file)
        
        # Load cooling center locations
        cooling_centers_file = self.data_path / "cooling_center.csv"
        self.cooling_centers = pd.read_csv(cooling_centers_file)
        
        # Convert to GeoDataFrame
        self.cooling_centers_gdf = gpd.GeoDataFrame(
            self.cooling_centers,
            geometry=gpd.points_from_xy(
                self.cooling_centers.longitude, 
                self.cooling_centers.latitude
            ),
            crs='EPSG:4326'
        )
        
        # Filter to validated centers only
        self.validated_centers_gdf = self.cooling_centers_gdf[
            self.cooling_centers_gdf['validate_tag'] == 1
        ].copy()
        
        # Load county boundary if available
        self.county_boundary = None
        if self.county_boundary_path.exists():
            try:
                self.county_boundary = gpd.read_file(self.county_boundary_path)
                # Ensure it's in the same CRS as cooling centers (WGS84 initially)
                if self.county_boundary.crs != 'EPSG:4326':
                    self.county_boundary = self.county_boundary.to_crs('EPSG:4326')
                print(f"✓ Loaded Hennepin County boundary from shapefile")
            except Exception as e:
                print(f"⚠ Could not load county boundary: {e}")
                self.county_boundary = None
        
        # If no county boundary shapefile, try to create from parcels
        if self.county_boundary is None and self.parcels_pickle_path.exists():
            print(f"  Attempting to create boundary from parcels data...")
            try:
                import pickle
                
                # Load parcels data
                with open(self.parcels_pickle_path, 'rb') as f:
                    parcels_data = pickle.load(f)
                
                # Extract GeoDataFrame
                if isinstance(parcels_data, dict) and 'gdf' in parcels_data:
                    parcels_gdf = parcels_data['gdf']
                elif isinstance(parcels_data, gpd.GeoDataFrame):
                    parcels_gdf = parcels_data
                else:
                    raise ValueError("Unexpected parcels data format")
                
                # Check and set CRS if missing
                if parcels_gdf.crs is None:
                    print(f"  Setting CRS to EPSG:26915 (UTM Zone 15N) for parcels")
                    parcels_gdf.set_crs('EPSG:26915', inplace=True)
                
                # Create boundary from parcels
                # Method 1: Convex hull (simpler boundary)
                # county_boundary_geom = parcels_gdf.unary_union.convex_hull
                
                # Method 2: Actual boundary (more accurate but may have holes)
                print(f"  Creating boundary from {len(parcels_gdf):,} parcels (this may take a moment)...")
                county_boundary_geom = parcels_gdf.unary_union.convex_hull  # Using convex hull for speed
                
                # Create GeoDataFrame with the boundary
                self.county_boundary = gpd.GeoDataFrame(
                    [{'name': 'Hennepin County', 'geometry': county_boundary_geom}],
                    crs=parcels_gdf.crs
                )
                
                # Convert to WGS84 to match cooling centers
                if self.county_boundary.crs != 'EPSG:4326':
                    self.county_boundary = self.county_boundary.to_crs('EPSG:4326')
                
                print(f"✓ Created Hennepin County boundary from parcels data")
                print(f"  (Derived from {len(parcels_gdf):,} parcels)")
                
            except Exception as e:
                print(f"⚠ Could not create boundary from parcels: {e}")
                if 'crs' in str(e).lower() or 'transform' in str(e).lower():
                    print("  This appears to be a CRS issue. The parcels may need a coordinate system defined.")
                print("  Maps will show cooling centers without county context")
        elif self.county_boundary is None:
            print(f"⚠ County boundary file not found at: {self.county_boundary_path}")
            print(f"⚠ Parcels data not found at: {self.parcels_pickle_path}")
            print("  Maps will show cooling centers without county context")
        
        print(f"✓ Loaded {len(self.validation_df)} days of validation data")
        print(f"✓ Loaded {len(self.stats_df)} cooling center statistics")
        print(f"✓ Loaded {len(self.validated_centers_gdf)} validated center locations")
        
    def download_county_boundary(self):
        """Download Hennepin County boundary from Census TIGER data"""
        print("\nDownloading Hennepin County boundary...")
        
        try:
            # Create directory if needed
            county_dir = self.county_boundary_path.parent
            county_dir.mkdir(parents=True, exist_ok=True)
            
            # Download Minnesota counties from Census TIGER
            url = "https://www2.census.gov/geo/tiger/TIGER2023/COUNTY/tl_2023_us_county.zip"
            counties = gpd.read_file(url)
            
            # Filter to Hennepin County, MN (FIPS: 27053)
            hennepin = counties[(counties['STATEFP'] == '27') & (counties['COUNTYFP'] == '053')]
            
            if len(hennepin) == 0:
                print("❌ Could not find Hennepin County in Census data")
                return False
                
            # Save to file
            hennepin.to_file(self.county_boundary_path)
            print(f"✓ Downloaded and saved Hennepin County boundary to: {self.county_boundary_path}")
            return True
            
        except Exception as e:
            print(f"❌ Error downloading county boundary: {e}")
            print("  You can manually download county boundaries from:")
            print("  https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html")
            print("\n  Alternatively, the script will use parcels data to create a boundary if available")
            return False
        
    def create_r2_scatter_plot(self):
        """Create R² scatter plot for all centers"""
        print("\nCreating R² scatter plot...")
        
        fig, ax = plt.subplots(figsize=(12, 10))
        
        # Prepare data for scatter plot
        all_real_ratios = []
        all_sim_ratios = []
        center_data = []
        
        # Get ratio columns for each center
        for _, row in self.stats_df.iterrows():
            center_name = row['cooling_center']
            
            # Find corresponding columns in validation data
            real_ratio_col = f"{center_name}_visits_ratio"
            sim_ratio_col = f"{center_name}_sim_visit_ratio"
            
            if real_ratio_col in self.validation_df.columns and sim_ratio_col in self.validation_df.columns:
                real_ratios = self.validation_df[real_ratio_col].values
                sim_ratios = self.validation_df[sim_ratio_col].values
                
                # Add to overall data
                all_real_ratios.extend(real_ratios)
                all_sim_ratios.extend(sim_ratios)
                
                # Store center-specific data
                center_data.append({
                    'name': center_name,
                    'real_ratios': real_ratios,
                    'sim_ratios': sim_ratios,
                    'correlation': row['correlation']
                })
        
        # Convert to numpy arrays
        all_real_ratios = np.array(all_real_ratios)
        all_sim_ratios = np.array(all_sim_ratios)
        
        # Remove any NaN values
        mask = ~(np.isnan(all_real_ratios) | np.isnan(all_sim_ratios))
        all_real_ratios = all_real_ratios[mask]
        all_sim_ratios = all_sim_ratios[mask]
        
        # Calculate overall R²
        overall_corr = np.corrcoef(all_real_ratios, all_sim_ratios)[0, 1]
        overall_r2 = overall_corr ** 2
        
        # Create scatter plot with different colors for each center
        colors = plt.cm.tab20(np.linspace(0, 1, len(center_data)))
        
        for i, center in enumerate(center_data):
            ax.scatter(center['real_ratios'], center['sim_ratios'], 
                      alpha=0.6, s=30, color=colors[i], 
                      label=f"{center['name'][:20]}... (r={center['correlation']:.2f})")
        
        # Add overall trend line
        z = np.polyfit(all_real_ratios, all_sim_ratios, 1)
        p = np.poly1d(z)
        x_trend = np.linspace(all_real_ratios.min(), all_real_ratios.max(), 100)
        ax.plot(x_trend, p(x_trend), "r--", linewidth=2, 
                label=f'Overall trend (R² = {overall_r2:.3f})')
        
        # Add 1:1 line
        max_val = max(all_real_ratios.max(), all_sim_ratios.max())
        ax.plot([0, max_val], [0, max_val], 'k-', alpha=0.5, 
                linewidth=1, label='1:1 line')
        
        # Labels and title
        ax.set_xlabel('Real Visitation Ratio', fontsize=12)
        ax.set_ylabel('Simulated Visitation Ratio', fontsize=12)
        ax.set_title(f'Validation Scatter Plot: Real vs Simulated Visitation Ratios\nOverall R² = {overall_r2:.3f}', 
                     fontsize=14, fontweight='bold')
        
        # Add text box with summary statistics
        textstr = f'n = {len(all_real_ratios)} observations\n'
        textstr += f'Overall correlation = {overall_corr:.3f}\n'
        textstr += f'Overall R² = {overall_r2:.3f}'
        
        props = dict(boxstyle='round', facecolor='wheat', alpha=0.8)
        ax.text(0.05, 0.95, textstr, transform=ax.transAxes, fontsize=10,
                verticalalignment='top', bbox=props)
        
        # Legend (show only if few centers, otherwise too crowded)
        if len(center_data) <= 10:
            ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
        
        plt.tight_layout()
        
        # Save
        output_file = self.vis_output_path / f"r2_scatter_plot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"✓ Saved R² scatter plot to: {output_file}")
        plt.close()
        
    def create_correlation_map(self):
        """Create map showing correlation by cooling center"""
        print("\nCreating correlation map...")
        
        # Merge data
        merged_gdf = self.merge_stats_with_locations()
        
        # Create figure
        fig, ax = plt.subplots(figsize=(14, 10))
        
        # Plot county boundary if available
        if self.county_boundary is not None:
            self.county_boundary.plot(ax=ax, color='none', edgecolor='black', linewidth=2)
            # Set the extent to county bounds
            bounds = self.county_boundary.total_bounds
            ax.set_xlim(bounds[0] - 0.05, bounds[2] + 0.05)
            ax.set_ylim(bounds[1] - 0.05, bounds[3] + 0.05)
        
        # Create color map (use diverging centered at 0, or sequential from -1 to 1)
        vmin = -1
        vmax = 1
        
        # Plot cooling centers colored by correlation
        scatter = ax.scatter(
            merged_gdf.geometry.x,
            merged_gdf.geometry.y,
            c=merged_gdf['correlation'],
            cmap='RdYlGn',  # Red for low correlation, Green for high
            s=300,  # Larger dots
            alpha=0.9,
            edgecolors='black',
            linewidth=2,
            vmin=vmin,
            vmax=vmax,
            zorder=5  # Ensure dots are on top
        )
        
        # Add colorbar
        cbar = plt.colorbar(scatter, ax=ax, shrink=0.8)
        cbar.set_label('Correlation (r)', fontsize=12)
        
        # Add labels for best and worst correlations
        # Best correlations
        best_corr = merged_gdf.nlargest(3, 'correlation')
        for _, row in best_corr.iterrows():
            ax.annotate(
                f"{row['name'][:15]}\n(r={row['correlation']:.2f})",
                xy=(row.geometry.x, row.geometry.y),
                xytext=(10, 10),
                textcoords='offset points',
                fontsize=9,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='green', alpha=0.8),
                color='white',
                arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0', color='green')
            )
        
        # Worst correlations
        worst_corr = merged_gdf.nsmallest(3, 'correlation')
        for _, row in worst_corr.iterrows():
            ax.annotate(
                f"{row['name'][:15]}\n(r={row['correlation']:.2f})",
                xy=(row.geometry.x, row.geometry.y),
                xytext=(10, -20),
                textcoords='offset points',
                fontsize=9,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='red', alpha=0.8),
                color='white',
                arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0', color='red')
            )
        
        # Set labels and title
        ax.set_xlabel('Longitude', fontsize=12)
        ax.set_ylabel('Latitude', fontsize=12)
        ax.set_title('Correlation by Cooling Center\n' +
                     'Green = High correlation (good match), Red = Low correlation (poor match)', 
                     fontsize=14, fontweight='bold')
        
        # Add county boundary note if available
        if self.county_boundary is not None:
            ax.text(0.02, 0.02, 'Hennepin County Boundary', 
                    transform=ax.transAxes, fontsize=10,
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        # Grid and aspect
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal')
        
        # Add reference lines in colorbar
        cbar.ax.axhline(y=0, color='black', linewidth=1)
        cbar.ax.axhline(y=0.7, color='black', linewidth=0.5, linestyle='--', alpha=0.5)
        cbar.ax.axhline(y=-0.7, color='black', linewidth=0.5, linestyle='--', alpha=0.5)
        
        plt.tight_layout()
        
        # Save
        output_file = self.vis_output_path / f"correlation_map_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"✓ Saved correlation map to: {output_file}")
        plt.close()
        
    def merge_stats_with_locations(self):
        """Merge statistics with cooling center locations"""
        # Create a mapping from stats to center names
        self.stats_df['center_name_lower'] = self.stats_df['cooling_center'].str.replace('_', ' ').str.lower()
        self.validated_centers_gdf['name_lower'] = self.validated_centers_gdf['name'].str.lower()
        
        # Try to match with more flexible rules
        merged_list = []
        
        for _, stat_row in self.stats_df.iterrows():
            stat_name = stat_row['center_name_lower']
            
            # Try exact match first
            matches = self.validated_centers_gdf[self.validated_centers_gdf['name_lower'] == stat_name]
            
            # If no exact match, try partial matching
            if len(matches) == 0:
                for _, center_row in self.validated_centers_gdf.iterrows():
                    center_name = center_row['name_lower']
                    # Check if one name contains the other
                    if stat_name in center_name or center_name in stat_name:
                        matches = self.validated_centers_gdf[self.validated_centers_gdf['name_lower'] == center_name]
                        break
                        
                    # Special handling for common variations
                    stat_words = set(stat_name.split())
                    center_words = set(center_name.split())
                    # If significant overlap in words
                    if len(stat_words.intersection(center_words)) >= 2:
                        matches = self.validated_centers_gdf[self.validated_centers_gdf['name_lower'] == center_name]
                        break
            
            if len(matches) > 0:
                # Combine the statistics with the location
                merged_row = matches.iloc[0].to_dict()
                # Add all statistics columns
                for col in stat_row.index:
                    if col not in merged_row:
                        merged_row[col] = stat_row[col]
                merged_list.append(merged_row)
        
        # Create merged GeoDataFrame
        if merged_list:
            # Convert list of dicts to DataFrame first
            merged_df = pd.DataFrame(merged_list)
            # Extract geometry column
            geometry = merged_df['geometry']
            # Create GeoDataFrame
            merged = gpd.GeoDataFrame(merged_df, geometry=geometry, crs=self.validated_centers_gdf.crs)
        else:
            print("⚠ Warning: No matches found between statistics and center locations")
            # Return empty GeoDataFrame with expected columns
            merged = gpd.GeoDataFrame(columns=list(self.stats_df.columns) + ['geometry'], 
                                     crs=self.validated_centers_gdf.crs)
        
        print(f"✓ Merged {len(merged)} centers with statistics (out of {len(self.stats_df)} in stats)")
        
        if len(merged) < len(self.stats_df):
            unmatched = set(self.stats_df['cooling_center']) - set(merged['cooling_center'])
            print(f"⚠ Unmatched centers from statistics: {unmatched}")
        
        return merged
        
    def create_mae_map(self):
        """Create map showing MAE as percentage"""
        print("\nCreating MAE percentage map...")
        
        # Merge data
        merged_gdf = self.merge_stats_with_locations()
        
        # Convert MAE ratio to percentage
        merged_gdf['mae_percentage'] = merged_gdf['mae_ratio'] * 100
        
        # Create figure
        fig, ax = plt.subplots(figsize=(14, 10))
        
        # Plot county boundary if available
        if self.county_boundary is not None:
            self.county_boundary.plot(ax=ax, color='none', edgecolor='black', linewidth=2)
            # Set the extent to county bounds
            bounds = self.county_boundary.total_bounds
            ax.set_xlim(bounds[0] - 0.05, bounds[2] + 0.05)
            ax.set_ylim(bounds[1] - 0.05, bounds[3] + 0.05)
        
        # Create color map
        vmin = merged_gdf['mae_percentage'].min()
        vmax = merged_gdf['mae_percentage'].max()
        
        # Plot cooling centers colored by MAE
        scatter = ax.scatter(
            merged_gdf.geometry.x,
            merged_gdf.geometry.y,
            c=merged_gdf['mae_percentage'],
            cmap='YlOrRd',
            s=300,  # Larger dots
            alpha=0.9,
            edgecolors='black',
            linewidth=2,
            vmin=vmin,
            vmax=vmax,
            zorder=5  # Ensure dots are on top
        )
        
        # Add colorbar
        cbar = plt.colorbar(scatter, ax=ax, shrink=0.8)
        cbar.set_label('MAE (% difference)', fontsize=12)
        
        # Add labels for high-error centers
        high_error = merged_gdf.nlargest(5, 'mae_percentage')
        for _, row in high_error.iterrows():
            ax.annotate(
                row['name'][:20],
                xy=(row.geometry.x, row.geometry.y),
                xytext=(10, 10),
                textcoords='offset points',
                fontsize=9,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.8),
                arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0')
            )
        
        # Set labels and title
        ax.set_xlabel('Longitude', fontsize=12)
        ax.set_ylabel('Latitude', fontsize=12)
        ax.set_title('Mean Absolute Error (MAE) by Cooling Center\n' + 
                     'Dot color shows percentage difference between real and simulated visitation ratios', 
                     fontsize=14, fontweight='bold')
        
        # Add county boundary note if available
        if self.county_boundary is not None:
            ax.text(0.02, 0.02, 'Hennepin County Boundary', 
                    transform=ax.transAxes, fontsize=10,
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        # Grid and aspect
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal')
        
        plt.tight_layout()
        
        # Save
        output_file = self.vis_output_path / f"mae_map_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"✓ Saved MAE map to: {output_file}")
        plt.close()
        
    def create_rmse_map(self):
        """Create map showing RMSE as percentage"""
        print("\nCreating RMSE percentage map...")
        
        # Merge data
        merged_gdf = self.merge_stats_with_locations()
        
        # Convert RMSE ratio to percentage
        merged_gdf['rmse_percentage'] = merged_gdf['rmse_ratio'] * 100
        
        # Create figure
        fig, ax = plt.subplots(figsize=(14, 10))
        
        # Plot county boundary if available
        if self.county_boundary is not None:
            self.county_boundary.plot(ax=ax, color='none', edgecolor='black', linewidth=2)
            # Set the extent to county bounds
            bounds = self.county_boundary.total_bounds
            ax.set_xlim(bounds[0] - 0.05, bounds[2] + 0.05)
            ax.set_ylim(bounds[1] - 0.05, bounds[3] + 0.05)
        
        # Create color map
        vmin = merged_gdf['rmse_percentage'].min()
        vmax = merged_gdf['rmse_percentage'].max()
        
        # Plot cooling centers colored by RMSE
        scatter = ax.scatter(
            merged_gdf.geometry.x,
            merged_gdf.geometry.y,
            c=merged_gdf['rmse_percentage'],
            cmap='plasma',
            s=300,  # Larger dots
            alpha=0.9,
            edgecolors='black',
            linewidth=2,
            vmin=vmin,
            vmax=vmax,
            zorder=5  # Ensure dots are on top
        )
        
        # Add colorbar
        cbar = plt.colorbar(scatter, ax=ax, shrink=0.8)
        cbar.set_label('RMSE (% difference)', fontsize=12)
        
        # Add labels for high-error centers
        high_error = merged_gdf.nlargest(5, 'rmse_percentage')
        for _, row in high_error.iterrows():
            ax.annotate(
                row['name'][:20],
                xy=(row.geometry.x, row.geometry.y),
                xytext=(10, 10),
                textcoords='offset points',
                fontsize=9,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.8),
                arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0')
            )
        
        # Set labels and title
        ax.set_xlabel('Longitude', fontsize=12)
        ax.set_ylabel('Latitude', fontsize=12)
        ax.set_title('Root Mean Square Error (RMSE) by Cooling Center\n' + 
                     'Dot color shows percentage difference between real and simulated visitation ratios', 
                     fontsize=14, fontweight='bold')
        
        # Add county boundary note if available
        if self.county_boundary is not None:
            ax.text(0.02, 0.02, 'Hennepin County Boundary', 
                    transform=ax.transAxes, fontsize=10,
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        # Grid and aspect
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal')
        
        plt.tight_layout()
        
        # Save
        output_file = self.vis_output_path / f"rmse_map_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"✓ Saved RMSE map to: {output_file}")
        plt.close()
        
    def create_bias_map(self):
        """Create map showing over/under estimation"""
        print("\nCreating bias (over/under estimation) map...")
        
        # Merge data
        merged_gdf = self.merge_stats_with_locations()
        
        # Convert relative error to percentage
        merged_gdf['bias_percentage'] = merged_gdf['relative_error'] * 100
        
        # Create figure
        fig, ax = plt.subplots(figsize=(14, 10))
        
        # Plot county boundary if available
        if self.county_boundary is not None:
            self.county_boundary.plot(ax=ax, color='none', edgecolor='black', linewidth=2)
            # Set the extent to county bounds
            bounds = self.county_boundary.total_bounds
            ax.set_xlim(bounds[0] - 0.05, bounds[2] + 0.05)
            ax.set_ylim(bounds[1] - 0.05, bounds[3] + 0.05)
        
        # Create diverging color map centered at 0
        vmax = max(abs(merged_gdf['bias_percentage'].min()), 
                   abs(merged_gdf['bias_percentage'].max()))
        vmin = -vmax
        
        # Plot cooling centers colored by bias
        scatter = ax.scatter(
            merged_gdf.geometry.x,
            merged_gdf.geometry.y,
            c=merged_gdf['bias_percentage'],
            cmap='RdBu_r',  # Red for overestimation, Blue for underestimation
            s=300,  # Larger dots
            alpha=0.9,
            edgecolors='black',
            linewidth=2,
            vmin=vmin,
            vmax=vmax,
            zorder=5  # Ensure dots are on top
        )
        
        # Add colorbar
        cbar = plt.colorbar(scatter, ax=ax, shrink=0.8)
        cbar.set_label('Bias (% over/underestimation)', fontsize=12)
        
        # Add labels for extreme bias
        # Most overestimated
        overest = merged_gdf.nlargest(3, 'bias_percentage')
        for _, row in overest.iterrows():
            ax.annotate(
                f"{row['name'][:15]}\n(+{row['bias_percentage']:.0f}%)",
                xy=(row.geometry.x, row.geometry.y),
                xytext=(10, 10),
                textcoords='offset points',
                fontsize=9,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='red', alpha=0.8),
                color='white',
                arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0', color='red')
            )
        
        # Most underestimated
        underest = merged_gdf.nsmallest(3, 'bias_percentage')
        for _, row in underest.iterrows():
            ax.annotate(
                f"{row['name'][:15]}\n({row['bias_percentage']:.0f}%)",
                xy=(row.geometry.x, row.geometry.y),
                xytext=(10, -20),
                textcoords='offset points',
                fontsize=9,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='blue', alpha=0.8),
                color='white',
                arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0', color='blue')
            )
        
        # Set labels and title
        ax.set_xlabel('Longitude', fontsize=12)
        ax.set_ylabel('Latitude', fontsize=12)
        ax.set_title('Model Bias by Cooling Center\n' +
                     'Red dots = Overestimation, Blue dots = Underestimation', 
                     fontsize=14, fontweight='bold')
        
        # Add county boundary note if available
        if self.county_boundary is not None:
            ax.text(0.02, 0.02, 'Hennepin County Boundary', 
                    transform=ax.transAxes, fontsize=10,
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        # Grid and aspect
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal')
        
        # Add a horizontal line at 0 in the colorbar
        cbar.ax.axhline(y=0, color='black', linewidth=1)
        
        plt.tight_layout()
        
        # Save
        output_file = self.vis_output_path / f"bias_map_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"✓ Saved bias map to: {output_file}")
        plt.close()
        
    def create_time_series_comparison(self):
        """Create time series plot of total visitation ratios"""
        print("\nCreating time series comparison...")
        
        fig, ax = plt.subplots(figsize=(14, 8))
        
        # Calculate total ratios for each date
        dates = self.validation_df['date']
        
        # Get all ratio columns
        real_ratio_cols = [col for col in self.validation_df.columns 
                          if col.endswith('_visits_ratio') and not col.endswith('_sim_visit_ratio')]
        sim_ratio_cols = [col for col in self.validation_df.columns 
                         if col.endswith('_sim_visit_ratio')]
        
        # Sum ratios for each date
        total_real_ratios = self.validation_df[real_ratio_cols].sum(axis=1)
        total_sim_ratios = self.validation_df[sim_ratio_cols].sum(axis=1)
        
        # Create plot
        ax.plot(dates, total_real_ratios, 'o-', color='blue', linewidth=2, 
                markersize=6, label='Real Total', alpha=0.8)
        ax.plot(dates, total_sim_ratios, 's-', color='red', linewidth=2, 
                markersize=6, label='Simulated Total', alpha=0.8)
        
        # Add shaded area between lines
        ax.fill_between(dates, total_real_ratios, total_sim_ratios, 
                       alpha=0.2, color='gray')
        
        # Calculate and display correlation
        correlation = total_real_ratios.corr(total_sim_ratios)
        
        # Add trend lines
        z_real = np.polyfit(range(len(dates)), total_real_ratios, 1)
        p_real = np.poly1d(z_real)
        ax.plot(dates, p_real(range(len(dates))), '--', color='blue', alpha=0.5)
        
        z_sim = np.polyfit(range(len(dates)), total_sim_ratios, 1)
        p_sim = np.poly1d(z_sim)
        ax.plot(dates, p_sim(range(len(dates))), '--', color='red', alpha=0.5)
        
        # Labels and title
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Total Visitation Ratio (sum across all centers)', fontsize=12)
        ax.set_title(f'Daily Total Visitation Ratios: Real vs Simulated\nCorrelation = {correlation:.3f}', 
                     fontsize=14, fontweight='bold')
        
        # Rotate x-axis labels
        plt.xticks(rotation=45, ha='right')
        
        # Add legend
        ax.legend(loc='upper left', fontsize=10)
        
        # Add grid
        ax.grid(True, alpha=0.3)
        
        # Add statistics box
        avg_real = total_real_ratios.mean()
        avg_sim = total_sim_ratios.mean()
        ratio = avg_sim / avg_real
        
        textstr = f'Average Real: {avg_real:.4f}\n'
        textstr += f'Average Sim: {avg_sim:.4f}\n'
        textstr += f'Sim/Real Ratio: {ratio:.2f}\n'
        textstr += f'Correlation: {correlation:.3f}'
        
        props = dict(boxstyle='round', facecolor='wheat', alpha=0.8)
        ax.text(0.02, 0.98, textstr, transform=ax.transAxes, fontsize=10,
                verticalalignment='top', bbox=props)
        
        plt.tight_layout()
        
        # Save
        output_file = self.vis_output_path / f"time_series_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"✓ Saved time series plot to: {output_file}")
        plt.close()
        
    def create_summary_dashboard(self):
        """Create a summary dashboard with key metrics"""
        print("\nCreating summary dashboard...")
        
        fig = plt.figure(figsize=(16, 12))
        
        # Create grid
        gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
        
        # 1. Overall metrics (top left)
        ax1 = fig.add_subplot(gs[0, 0])
        ax1.axis('off')
        
        # Calculate overall metrics
        overall_corr = self.stats_df['correlation'].mean()
        overall_mae = self.stats_df['mae_ratio'].mean() * 100
        overall_rmse = self.stats_df['rmse_ratio'].mean() * 100
        overall_bias = self.stats_df['relative_error'].mean() * 100
        
        metrics_text = f"OVERALL VALIDATION METRICS\n\n"
        metrics_text += f"Average Correlation: {overall_corr:.3f}\n"
        metrics_text += f"Average MAE: {overall_mae:.2f}%\n"
        metrics_text += f"Average RMSE: {overall_rmse:.2f}%\n"
        metrics_text += f"Average Bias: {overall_bias:+.1f}%\n"
        metrics_text += f"Number of Centers: {len(self.stats_df)}"
        
        ax1.text(0.1, 0.9, metrics_text, transform=ax1.transAxes, 
                fontsize=12, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))
        
        # 2. Correlation distribution (top middle)
        ax2 = fig.add_subplot(gs[0, 1])
        ax2.hist(self.stats_df['correlation'], bins=20, alpha=0.7, color='green', edgecolor='black')
        ax2.set_xlabel('Correlation')
        ax2.set_ylabel('Number of Centers')
        ax2.set_title('Distribution of Correlations')
        ax2.axvline(overall_corr, color='red', linestyle='--', label=f'Mean={overall_corr:.3f}')
        ax2.legend()
        
        # 3. MAE distribution (top right)
        ax3 = fig.add_subplot(gs[0, 2])
        mae_pct = self.stats_df['mae_ratio'] * 100
        ax3.hist(mae_pct, bins=20, alpha=0.7, color='orange', edgecolor='black')
        ax3.set_xlabel('MAE (%)')
        ax3.set_ylabel('Number of Centers')
        ax3.set_title('Distribution of Mean Absolute Errors')
        ax3.axvline(overall_mae, color='red', linestyle='--', label=f'Mean={overall_mae:.2f}%')
        ax3.legend()
        
        # 4. Best performing centers (middle left)
        ax4 = fig.add_subplot(gs[1, 0])
        best_centers = self.stats_df.nlargest(10, 'correlation')[['cooling_center', 'correlation']]
        y_pos = np.arange(len(best_centers))
        ax4.barh(y_pos, best_centers['correlation'], alpha=0.7, color='darkgreen')
        ax4.set_yticks(y_pos)
        ax4.set_yticklabels([name[:20] for name in best_centers['cooling_center']], fontsize=8)
        ax4.set_xlabel('Correlation')
        ax4.set_title('Top 10 Centers by Correlation')
        ax4.set_xlim(0, 1)
        
        # 5. Worst performing centers (middle middle)
        ax5 = fig.add_subplot(gs[1, 1])
        worst_centers = self.stats_df.nsmallest(10, 'correlation')[['cooling_center', 'correlation']]
        y_pos = np.arange(len(worst_centers))
        ax5.barh(y_pos, worst_centers['correlation'], alpha=0.7, color='darkred')
        ax5.set_yticks(y_pos)
        ax5.set_yticklabels([name[:20] for name in worst_centers['cooling_center']], fontsize=8)
        ax5.set_xlabel('Correlation')
        ax5.set_title('Bottom 10 Centers by Correlation')
        ax5.set_xlim(-1, 1)
        
        # 6. Bias distribution (middle right)
        ax6 = fig.add_subplot(gs[1, 2])
        bias_pct = self.stats_df['relative_error'] * 100
        ax6.hist(bias_pct, bins=20, alpha=0.7, color='purple', edgecolor='black')
        ax6.set_xlabel('Relative Error (%)')
        ax6.set_ylabel('Number of Centers')
        ax6.set_title('Distribution of Bias')
        ax6.axvline(0, color='black', linestyle='-', alpha=0.5)
        ax6.axvline(overall_bias, color='red', linestyle='--', label=f'Mean={overall_bias:+.1f}%')
        ax6.legend()
        
        # 7-9. Mini scatter plots for different correlation ranges (bottom row)
        # Low correlation
        ax7 = fig.add_subplot(gs[2, 0])
        low_corr = self.stats_df[self.stats_df['correlation'] < 0.3]
        if len(low_corr) > 0:
            ax7.scatter(low_corr['mean_real_ratio'], low_corr['mean_sim_ratio'], 
                       alpha=0.6, color='red')
            ax7.set_xlabel('Mean Real Ratio')
            ax7.set_ylabel('Mean Sim Ratio')
            ax7.set_title(f'Low Correlation Centers (r < 0.3)\nn = {len(low_corr)}')
            
            # Add 1:1 line
            max_val = max(low_corr['mean_real_ratio'].max(), low_corr['mean_sim_ratio'].max())
            ax7.plot([0, max_val], [0, max_val], 'k--', alpha=0.5)
        
        # Medium correlation
        ax8 = fig.add_subplot(gs[2, 1])
        med_corr = self.stats_df[(self.stats_df['correlation'] >= 0.3) & 
                                 (self.stats_df['correlation'] < 0.7)]
        if len(med_corr) > 0:
            ax8.scatter(med_corr['mean_real_ratio'], med_corr['mean_sim_ratio'], 
                       alpha=0.6, color='orange')
            ax8.set_xlabel('Mean Real Ratio')
            ax8.set_ylabel('Mean Sim Ratio')
            ax8.set_title(f'Medium Correlation Centers (0.3 ≤ r < 0.7)\nn = {len(med_corr)}')
            
            # Add 1:1 line
            max_val = max(med_corr['mean_real_ratio'].max(), med_corr['mean_sim_ratio'].max())
            ax8.plot([0, max_val], [0, max_val], 'k--', alpha=0.5)
        
        # High correlation
        ax9 = fig.add_subplot(gs[2, 2])
        high_corr = self.stats_df[self.stats_df['correlation'] >= 0.7]
        if len(high_corr) > 0:
            ax9.scatter(high_corr['mean_real_ratio'], high_corr['mean_sim_ratio'], 
                       alpha=0.6, color='green')
            ax9.set_xlabel('Mean Real Ratio')
            ax9.set_ylabel('Mean Sim Ratio')
            ax9.set_title(f'High Correlation Centers (r ≥ 0.7)\nn = {len(high_corr)}')
            
            # Add 1:1 line
            max_val = max(high_corr['mean_real_ratio'].max(), high_corr['mean_sim_ratio'].max())
            ax9.plot([0, max_val], [0, max_val], 'k--', alpha=0.5)
        
        # Overall title
        fig.suptitle('Heat Risk Model Validation Summary Dashboard', 
                     fontsize=16, fontweight='bold')
        
        # Adjust layout to prevent overlap
        plt.subplots_adjust(top=0.95)
        
        plt.tight_layout()
        
        # Save
        output_file = self.vis_output_path / f"summary_dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"✓ Saved summary dashboard to: {output_file}")
        plt.close()
        
    def run_all_visualizations(self):
        """Run all visualization methods"""
        print("\n" + "="*60)
        print("CREATING ALL VISUALIZATIONS")
        print("="*60)
        
        # Load data
        self.load_data()
        
        # Create all visualizations
        self.create_r2_scatter_plot()
        self.create_correlation_map()  # New correlation map
        self.create_mae_map()
        self.create_rmse_map()
        self.create_bias_map()
        self.create_time_series_comparison()
        self.create_summary_dashboard()
        
        print("\n" + "="*60)
        print("✅ ALL VISUALIZATIONS COMPLETE!")
        print(f"📊 Files saved to: {self.vis_output_path}")
        print("="*60)


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description='Create visualizations for heat risk model validation results'
    )
    parser.add_argument(
        '--download-county',
        action='store_true',
        help='Download Hennepin County boundary from Census data'
    )
    args = parser.parse_args()
    
    print("🎨 HEAT RISK MODEL VALIDATION VISUALIZATION")
    print("="*60)
    
    try:
        # Create visualizer
        visualizer = ValidationVisualizer()
        
        # Download county boundary if requested
        if args.download_county:
            visualizer.download_county_boundary()
            return 0
        
        # Run all visualizations
        visualizer.run_all_visualizations()
        
        print("\n✅ Visualization complete!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    return 0


if __name__ == "__main__":
    sys.exit(main())