#!/usr/bin/env python3
"""
Cooling Center Cluster Visualization
Creates maps showing cooling centers as small colored dots (by cluster assignment)
overlaid on grey parcel polygons - similar to the heat risk visualization style
"""

import os
import sys
import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import pickle
import json
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Set style
plt.style.use('default')
plt.rcParams['axes.grid'] = False
plt.rcParams['figure.facecolor'] = 'white'
plt.rcParams['axes.facecolor'] = 'white'

class CoolingCenterClusterVisualizer:
    def __init__(self):
        """Initialize the visualizer with data paths"""
        
        # Data paths
        self.cooling_center_path = Path(r"~\hennepin\data\validate_data\intermediate\cooling_center_with_buildyr_clustered.gpkg")
        self.parcels_pickle_path = Path(r"~\hennepin\data\preprocessed_data\parcels_prepared.pkl")
        self.parcels_metadata_path = Path(r"~\hennepin\data\preprocessed_data\parcels_metadata.json")
        
        # Output directory
        self.output_dir = Path(r"~\hennepin\output\figures")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Color schemes for clusters - using distinct colors like in the reference
        self.colors_4 = {
            1: '#17becf',   # Cyan
            2: '#ff7f0e',   # Orange  
            3: '#d62728',   # Red
            4: '#2ca02c'    # Green
        }
        
        self.colors_8 = {
            1: '#17becf',   # Cyan
            2: '#ff7f0e',   # Orange
            3: '#d62728',   # Red
            4: '#2ca02c',   # Green
            5: '#9467bd',   # Purple
            6: '#8c564b',   # Brown
            7: '#e377c2',   # Pink
            8: '#7f7f7f'    # Gray
        }
        
        print("Cooling Center Cluster Visualizer initialized")
        print(f"Output directory: {self.output_dir}")
    
    def load_cooling_centers(self):
        """Load cooling center data with cluster assignments"""
        print("\nLoading cooling center data...")
        
        try:
            # Load the geopackage file
            self.cooling_centers_gdf = gpd.read_file(self.cooling_center_path)
            print(f"✓ Loaded {len(self.cooling_centers_gdf)} cooling centers")
            
            # Check for required columns
            required_cols = ['cluster4_tag', 'cluster8_tag', 'geometry']
            missing_cols = [col for col in required_cols if col not in self.cooling_centers_gdf.columns]
            
            if missing_cols:
                print(f"⚠ Warning: Missing columns: {missing_cols}")
                print(f"Available columns: {list(self.cooling_centers_gdf.columns)}")
            else:
                print(f"✓ All required columns present")
                
            # Print cluster statistics
            if 'cluster4_tag' in self.cooling_centers_gdf.columns:
                print(f"\n4-cluster distribution:")
                print(self.cooling_centers_gdf['cluster4_tag'].value_counts().sort_index())
                
            if 'cluster8_tag' in self.cooling_centers_gdf.columns:
                print(f"\n8-cluster distribution:")
                print(self.cooling_centers_gdf['cluster8_tag'].value_counts().sort_index())
                
            return True
            
        except Exception as e:
            print(f"❌ Error loading cooling centers: {e}")
            return False
    
    def load_parcels(self):
        """Load parcel polygon data for grey background"""
        print("\nLoading parcel data...")
        
        try:
            # First try to load pickle file
            if self.parcels_pickle_path.exists():
                with open(self.parcels_pickle_path, 'rb') as f:
                    parcels_data = pickle.load(f)
                
                if isinstance(parcels_data, dict) and 'gdf' in parcels_data:
                    self.parcels_gdf = parcels_data['gdf']
                else:
                    self.parcels_gdf = parcels_data
                    
                print(f"✓ Loaded {len(self.parcels_gdf)} parcels from pickle")
                
                # Ensure it's a GeoDataFrame
                if not isinstance(self.parcels_gdf, gpd.GeoDataFrame):
                    print("Converting to GeoDataFrame...")
                    self.parcels_gdf = gpd.GeoDataFrame(self.parcels_gdf)
                    
            else:
                print(f"⚠ Parcel pickle file not found at {self.parcels_pickle_path}")
                print("Parcels will not be shown in the visualization")
                self.parcels_gdf = None
                return False
                
            # Load metadata if available
            if self.parcels_metadata_path.exists():
                with open(self.parcels_metadata_path, 'r') as f:
                    metadata = json.load(f)
                print(f"✓ Loaded parcel metadata")
                print(f"  CRS: {metadata.get('crs', 'Unknown')}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error loading parcels: {e}")
            self.parcels_gdf = None
            return False
    
    def align_crs(self):
        """Ensure all data uses the same CRS"""
        print("\nAligning coordinate reference systems...")
        
        # Use parcels CRS as the base if available, otherwise use cooling centers
        if self.parcels_gdf is not None and self.parcels_gdf.crs is not None:
            base_crs = self.parcels_gdf.crs
        else:
            base_crs = self.cooling_centers_gdf.crs
            
        print(f"Base CRS: {base_crs}")
        
        # Align cooling centers
        if self.cooling_centers_gdf.crs != base_crs:
            print(f"Converting cooling centers from {self.cooling_centers_gdf.crs} to {base_crs}")
            self.cooling_centers_gdf = self.cooling_centers_gdf.to_crs(base_crs)
            
        print("✓ CRS aligned")
    
    def create_cluster_map(self, n_clusters=4, save=True, show=True):
        """
        Create a map showing cooling centers as small colored dots on grey parcels
        Matches the style of the heat risk visualization
        
        Args:
            n_clusters: 4 or 8 for the number of clusters to visualize
            save: Whether to save the figure
            show: Whether to display the figure
        """
        
        # Validate cluster number
        if n_clusters not in [4, 8]:
            print(f"⚠ Invalid cluster number: {n_clusters}. Must be 4 or 8.")
            return
        
        cluster_col = f'cluster{n_clusters}_tag'
        color_map = self.colors_4 if n_clusters == 4 else self.colors_8
        
        # Check if cluster column exists
        if cluster_col not in self.cooling_centers_gdf.columns:
            print(f"⚠ Column '{cluster_col}' not found in cooling centers data")
            return
        
        print(f"\nCreating {n_clusters}-cluster map...")
        
        # Create figure and axis
        fig, ax = plt.subplots(figsize=(15, 10))
        
        # Set white background
        ax.set_facecolor('white')
        fig.patch.set_facecolor('white')
        
        # Plot all parcels as light grey polygons for background
        if self.parcels_gdf is not None:
            print("  Adding parcel polygons as grey background...")
            self.parcels_gdf.plot(ax=ax, 
                                  color='lightgray',      # Light grey like the reference
                                  edgecolor=None,         # No edges for cleaner look
                                  alpha=0.5,              # Semi-transparent
                                  zorder=1)
        
        # Plot cooling centers as small colored dots
        print(f"  Adding cooling center dots...")
        
        # Get valid cooling centers (non-null cluster values)
        valid_centers = self.cooling_centers_gdf.dropna(subset=[cluster_col])
        
        # Plot each cluster separately
        unique_clusters = sorted(valid_centers[cluster_col].unique())
        
        for cluster in unique_clusters:
            cluster_data = valid_centers[valid_centers[cluster_col] == cluster]
            
            if len(cluster_data) > 0:
                # Get color for this cluster
                color = color_map.get(cluster, '#333333')  # Default to dark grey if not found
                
                # Plot as small dots by using the CENTROID of the geometry
                cluster_data.geometry.centroid.plot(ax=ax,
                                     color=color,
                                     markersize=30,      # Small dots like the reference
                                     marker='o',
                                     edgecolor='black',  # Black edge for visibility
                                     linewidth=0.5,
                                     alpha=0.9,
                                     zorder=5,           # On top of parcels
                                     label=f'Cluster {cluster}')
        
        # Create legend
        legend_elements = []
        
        # Add parcels to legend
        if self.parcels_gdf is not None:
            legend_elements.append(
                Patch(facecolor='lightgray', edgecolor='none', 
                      label=f'Parcels ({len(self.parcels_gdf):,})', alpha=0.5)
            )
        
        # Add cluster dots to legend
        for cluster in unique_clusters:
            count = (valid_centers[cluster_col] == cluster).sum()
            color = color_map.get(cluster, '#333333')
            legend_elements.append(
                Line2D([0], [0], marker='o', color='w',
                       markerfacecolor=color,
                       markersize=8, 
                       markeredgecolor='black',
                       markeredgewidth=0.5,
                       label=f'Cluster {cluster} (n={count})')
            )
        
        # Position legend - upper left like in the reference
        ax.legend(handles=legend_elements,
                  loc='upper left',
                  bbox_to_anchor=(1.02, 1),
                  title='Legend',
                  fontsize=8,
                  title_fontsize=10,
                  frameon=True,
                  fancybox=False,
                  shadow=False,
                  framealpha=0.95)
        
        # Set title
        ax.set_title(f'Cooling Centers - {n_clusters} Cluster Classification\n'
                     f'Total Centers: {len(valid_centers)}',
                     fontsize=16, fontweight='bold', pad=20)
        
        # Remove axes for cleaner look
        ax.set_axis_off()
        
        # Set equal aspect ratio
        ax.set_aspect('equal')
        
        # Tight layout
        plt.tight_layout()
        
        # Save figure
        if save:
            output_file = self.output_dir / f'cooling_centers_{n_clusters}_clusters_dots.png'
            plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
            print(f"✓ Map saved to: {output_file}")
        
        # Show figure
        if show:
            plt.show()
        else:
            plt.close()
            
        return fig, ax
    
    def create_side_by_side_comparison(self, save=True, show=True):
        """Create a side-by-side comparison of 4 and 8 cluster maps"""
        
        print("\nCreating side-by-side cluster comparison...")
        
        # Create figure with two subplots
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(24, 10))
        
        # Set white background
        fig.patch.set_facecolor('white')
        ax1.set_facecolor('white')
        ax2.set_facecolor('white')
        
        # Helper function to plot on a specific axis
        def plot_clusters(ax, n_clusters):
            cluster_col = f'cluster{n_clusters}_tag'
            color_map = self.colors_4 if n_clusters == 4 else self.colors_8
            
            # Plot grey parcels
            if self.parcels_gdf is not None:
                self.parcels_gdf.plot(ax=ax, 
                                      color='lightgray',
                                      edgecolor=None,
                                      alpha=0.5,
                                      zorder=1)
            
            # Get valid centers
            valid_centers = self.cooling_centers_gdf.dropna(subset=[cluster_col])
            unique_clusters = sorted(valid_centers[cluster_col].unique())
            
            # Plot cooling center dots
            for cluster in unique_clusters:
                cluster_data = valid_centers[valid_centers[cluster_col] == cluster]
                if len(cluster_data) > 0:
                    color = color_map.get(cluster, '#333333')
                    # Plot as dots by using the CENTROID of the geometry
                    cluster_data.geometry.centroid.plot(ax=ax,
                                         color=color,
                                         markersize=25,  # Slightly smaller for comparison view
                                         marker='o',
                                         edgecolor='black',
                                         linewidth=0.5,
                                         alpha=0.9,
                                         zorder=5)
            
            # Set title
            ax.set_title(f'{n_clusters}-Cluster Classification',
                         fontsize=14, fontweight='bold')
            ax.set_axis_off()
            ax.set_aspect('equal')
            
            return unique_clusters
        
        # Plot 4 clusters
        clusters4 = plot_clusters(ax1, 4)
        
        # Plot 8 clusters
        clusters8 = plot_clusters(ax2, 8)
        
        # Add main title
        fig.suptitle('Cooling Center Cluster Comparison\n4 vs 8 Cluster Classifications',
                     fontsize=18, fontweight='bold', y=1.02)
        
        # Adjust layout
        plt.tight_layout()
        
        # Save figure
        if save:
            output_file = self.output_dir / 'cooling_centers_cluster_comparison_dots.png'
            plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
            print(f"✓ Comparison map saved to: {output_file}")
        
        # Show figure
        if show:
            plt.show()
        else:
            plt.close()
            
        return fig, (ax1, ax2)
    
    def create_zoomed_cluster_map(self, n_clusters=4, zoom_center='density', zoom_level=0.3, save=True, show=True):
        """
        Create a zoomed-in version focusing on areas with high cooling center density
        
        Args:
            n_clusters: 4 or 8 for the number of clusters
            zoom_center: 'downtown', 'density', or 'geometric' for zoom focus
            zoom_level: Fraction of extent to show (0.3 = 30% of area)
            save: Whether to save the figure
            show: Whether to display the figure
        """
        
        cluster_col = f'cluster{n_clusters}_tag'
        color_map = self.colors_4 if n_clusters == 4 else self.colors_8
        
        print(f"\nCreating zoomed {n_clusters}-cluster map (focus: {zoom_center})...")
        
        # Create figure and axis
        fig, ax = plt.subplots(figsize=(12, 12))
        
        # Set white background
        ax.set_facecolor('white')
        fig.patch.set_facecolor('white')
        
        # Calculate zoom bounds based on cooling center density
        valid_centers = self.cooling_centers_gdf.dropna(subset=[cluster_col])
        
        if zoom_center == 'density':
            # Find the densest area of cooling centers
            center_points = valid_centers.geometry.centroid
            x_coords = center_points.x
            y_coords = center_points.y
            
            # Use median as center for robustness against outliers
            center_x = x_coords.median()
            center_y = y_coords.median()
        elif zoom_center == 'downtown':
            # Use geometric center shifted slightly south (typically downtown)
            bounds = valid_centers.total_bounds
            center_x = (bounds[0] + bounds[2]) / 2
            center_y = (bounds[1] + bounds[3]) / 2 - (bounds[3] - bounds[1]) * 0.1
        else:  # geometric center
            bounds = valid_centers.total_bounds
            center_x = (bounds[0] + bounds[2]) / 2
            center_y = (bounds[1] + bounds[3]) / 2
        
        # Calculate zoom window
        bounds = valid_centers.total_bounds
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        
        zoom_width = width * zoom_level
        zoom_height = height * zoom_level
        
        zoom_bounds = [
            center_x - zoom_width / 2,
            center_y - zoom_height / 2,
            center_x + zoom_width / 2,
            center_y + zoom_height / 2
        ]
        
        # Plot parcels
        if self.parcels_gdf is not None:
            print("  Adding parcel polygons (zoomed area)...")
            self.parcels_gdf.plot(ax=ax, 
                                  color='lightgray',
                                  edgecolor=None,
                                  alpha=0.5,
                                  zorder=1)
        
        # Plot cooling centers with larger dots for zoom
        unique_clusters = sorted(valid_centers[cluster_col].unique())
        
        for cluster in unique_clusters:
            cluster_data = valid_centers[valid_centers[cluster_col] == cluster]
            
            if len(cluster_data) > 0:
                color = color_map.get(cluster, '#333333')
                # Plot as dots by using the CENTROID of the geometry
                cluster_data.geometry.centroid.plot(ax=ax,
                                     color=color,
                                     markersize=60,      # Larger dots for zoomed view
                                     marker='o',
                                     edgecolor='black',
                                     linewidth=0.8,
                                     alpha=0.9,
                                     zorder=5)
        
        # Set zoom limits
        ax.set_xlim(zoom_bounds[0], zoom_bounds[2])
        ax.set_ylim(zoom_bounds[1], zoom_bounds[3])
        
        # Title
        ax.set_title(f'Cooling Centers - {n_clusters} Cluster Classification (Zoomed View)\n'
                     f'Focus: {zoom_center.capitalize()} Area',
                     fontsize=16, fontweight='bold', pad=20)
        
        ax.set_axis_off()
        ax.set_aspect('equal')
        plt.tight_layout()
        
        # Save
        if save:
            output_file = self.output_dir / f'cooling_centers_{n_clusters}_clusters_zoomed_{zoom_center}.png'
            plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
            print(f"✓ Zoomed map saved to: {output_file}")
        
        if show:
            plt.show()
        else:
            plt.close()
        
        return fig, ax
    
    def print_summary_statistics(self):
        """Print summary statistics about the clusters"""
        
        print("\n" + "="*60)
        print("CLUSTER SUMMARY STATISTICS")
        print("="*60)
        
        if not hasattr(self, 'cooling_centers_gdf'):
             print("Cooling center data not loaded. Cannot print statistics.")
             return

        # Total cooling centers
        print(f"\nTotal cooling centers: {len(self.cooling_centers_gdf)}")
        
        # Total parcels
        if self.parcels_gdf is not None:
            print(f"Total parcels: {len(self.parcels_gdf):,}")
        
        # 4-cluster statistics
        if 'cluster4_tag' in self.cooling_centers_gdf.columns:
            print(f"\n4-CLUSTER DISTRIBUTION:")
            print("-"*30)
            valid_4 = self.cooling_centers_gdf.dropna(subset=['cluster4_tag'])
            if len(valid_4) > 0:
                cluster4_counts = valid_4['cluster4_tag'].value_counts().sort_index()
                for cluster, count in cluster4_counts.items():
                    percentage = (count / len(valid_4)) * 100
                    print(f"  Cluster {int(cluster)}: {count:3d} centers ({percentage:5.1f}%)")
            else:
                print("  No data with 4-cluster tags.")

        # 8-cluster statistics
        if 'cluster8_tag' in self.cooling_centers_gdf.columns:
            print(f"\n8-CLUSTER DISTRIBUTION:")
            print("-"*30)
            valid_8 = self.cooling_centers_gdf.dropna(subset=['cluster8_tag'])
            if len(valid_8) > 0:
                cluster8_counts = valid_8['cluster8_tag'].value_counts().sort_index()
                for cluster, count in cluster8_counts.items():
                    percentage = (count / len(valid_8)) * 100
                    print(f"  Cluster {int(cluster)}: {count:3d} centers ({percentage:5.1f}%)")
            else:
                 print("  No data with 8-cluster tags.")

        # Spatial extent
        bounds = self.cooling_centers_gdf.total_bounds
        print(f"\nSPATIAL EXTENT:")
        print("-"*30)
        print(f"  Min X: {bounds[0]:,.0f}")
        print(f"  Min Y: {bounds[1]:,.0f}")
        print(f"  Max X: {bounds[2]:,.0f}")
        print(f"  Max Y: {bounds[3]:,.0f}")
        
        print("\n" + "="*60)


def main():
    """Main execution function"""
    
    print("="*60)
    print("COOLING CENTER CLUSTER VISUALIZATION")
    print("Using Heat Risk Model visualization style")
    print("="*60)
    
    # Initialize visualizer
    viz = CoolingCenterClusterVisualizer()
    
    # Load data
    if not viz.load_cooling_centers():
        print("❌ Failed to load cooling centers. Exiting.")
        return
    
    # Load parcels (optional - will continue even if fails)
    viz.load_parcels()
    
    # Align CRS
    viz.align_crs()
    
    # Print summary statistics
    viz.print_summary_statistics()
    
    # Create individual cluster maps
    print("\n" + "="*60)
    print("GENERATING VISUALIZATIONS")
    print("="*60)
    
    # Full extent maps with small dots
    print("\n[1/5] Creating 4-cluster map with dots...")
    viz.create_cluster_map(n_clusters=4, save=True, show=False)
    
    print("\n[2/5] Creating 8-cluster map with dots...")
    viz.create_cluster_map(n_clusters=8, save=True, show=False)
    
    # Comparison
    print("\n[3/5] Creating side-by-side comparison...")
    viz.create_side_by_side_comparison(save=True, show=False)
    
    # Zoomed views for better detail
    print("\n[4/5] Creating zoomed 4-cluster map (density focus)...")
    viz.create_zoomed_cluster_map(n_clusters=4, zoom_center='density', zoom_level=0.3, save=True, show=False)
    
    print("\n[5/5] Creating zoomed 8-cluster map (downtown focus)...")
    viz.create_zoomed_cluster_map(n_clusters=8, zoom_center='downtown', zoom_level=0.3, save=True, show=False)
    
    print("\n" + "="*60)
    print("✅ VISUALIZATION COMPLETE!")
    print(f"Output saved to: {viz.output_dir}")
    print("="*60)


if __name__ == "__main__":
    main()