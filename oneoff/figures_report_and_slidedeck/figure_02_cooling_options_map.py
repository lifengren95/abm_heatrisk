#!/usr/bin/env python3
"""
Cooling Centers Map Visualization
Shows cooling center locations overlaid on parcel boundaries
"""
import os

import os
import sys

# Fix PROJ database conflicts - MUST be before importing geopandas
os.environ['PROJ_LIB'] = ''  # Clear any conflicting PROJ_LIB settings
os.environ['GDAL_DATA'] = ''

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch
from matplotlib_scalebar.scalebar import ScaleBar
import pickle
from pathlib import Path
import warnings
import time

warnings.filterwarnings('ignore')

# Set matplotlib parameters for Nature publication style
plt.rcParams['font.family'] = 'Arial'
plt.rcParams['font.size'] = 10
plt.rcParams['axes.labelsize'] = 10
plt.rcParams['axes.titlesize'] = 12
plt.rcParams['xtick.labelsize'] = 9
plt.rcParams['ytick.labelsize'] = 9
plt.rcParams['legend.fontsize'] = 9
plt.rcParams['figure.titlesize'] = 12


class CoolingCenterMapper:
    def __init__(self):
        """Initialize paths and settings"""
        # Data paths
        self.parcels_path = r"~\hennepin\data\preprocessed_data\parcels_prepared.pkl"
        self.cooling_centers_path = r"~\hennepin\data\validate_data\intermediate\cooling_center_with_buildyr.gpkg"
        # Fallback path for CSV if GPKG fails
        self.cooling_centers_csv_path = r"~\hennepin\data\validate_data\intermediate\cooling_center.csv"
        
        # Output path
        self.output_dir = Path(r"~\hennepin\output\figures\summary_stats")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Nature publication settings
        self.figure_dpi = 300
        self.figure_size = (12, 14)  # Larger for better visibility
        
        # Colors
        self.parcel_color = '#E8E8E8'  # Light grey for parcels
        self.cooling_center_color = '#2166AC'  # Blue for cooling centers
        self.cooling_center_edge = '#053061'  # Dark blue edge
        
        print("="*60)
        print("COOLING CENTERS MAP VISUALIZATION")
        print("="*60)
        print(f"Output directory: {self.output_dir}")
    
    def load_parcel_data(self):
        """Load preprocessed parcel data"""
        print("\n1. Loading parcel data...")
        start_time = time.time()
        
        if not Path(self.parcels_path).exists():
            raise FileNotFoundError(f"Parcel data not found: {self.parcels_path}")
        
        with open(self.parcels_path, 'rb') as f:
            data = pickle.load(f)
        
        gdf_parcels = data['gdf']
        load_time = time.time() - start_time
        
        print(f"   ✓ Loaded {len(gdf_parcels)} parcels in {load_time:.2f} seconds")
        print(f"   ✓ CRS: {gdf_parcels.crs}")
        
        # Ensure we have geometry
        if 'geometry' not in gdf_parcels.columns:
            raise ValueError("No geometry column found in parcel data")
        
        return gdf_parcels
    
    def load_cooling_centers_from_csv(self):
        """Fallback: Load cooling centers from CSV and create geometry"""
        print("\n   Attempting to load cooling centers from CSV fallback...")
        
        if not Path(self.cooling_centers_csv_path).exists():
            raise FileNotFoundError(f"CSV fallback not found: {self.cooling_centers_csv_path}")
        
        # Load CSV
        df = pd.read_csv(self.cooling_centers_csv_path)
        print(f"   ✓ Loaded {len(df)} cooling centers from CSV")
        
        # Check for coordinate columns
        if 'latitude' in df.columns and 'longitude' in df.columns:
            # Create geometry from lat/lon
            geometry = gpd.points_from_xy(df.longitude, df.latitude)
            gdf_cooling = gpd.GeoDataFrame(df, geometry=geometry)
            
            # Try to set CRS to WGS84
            try:
                gdf_cooling.crs = 'EPSG:4326'
                print("   ✓ Created GeoDataFrame with WGS84 CRS")
            except:
                print("   ⚠ Created GeoDataFrame without CRS")
                
        elif 'utm_x' in df.columns and 'utm_y' in df.columns:
            # Create geometry from UTM coordinates
            geometry = gpd.points_from_xy(df.utm_x, df.utm_y)
            gdf_cooling = gpd.GeoDataFrame(df, geometry=geometry)
            
            # Try to set CRS to UTM 15N
            try:
                gdf_cooling.crs = 'EPSG:26915'
                print("   ✓ Created GeoDataFrame with UTM 15N CRS")
            except:
                print("   ⚠ Created GeoDataFrame without CRS")
        else:
            raise ValueError("No coordinate columns found in CSV (need latitude/longitude or utm_x/utm_y)")
        
        return gdf_cooling
    
    def load_cooling_centers(self):
        """Load cooling centers from GeoPackage"""
        print("\n2. Loading cooling centers...")
        start_time = time.time()
        
        if not Path(self.cooling_centers_path).exists():
            print(f"   ⚠ GeoPackage not found, trying CSV fallback...")
            gdf_cooling = self.load_cooling_centers_from_csv()
        else:
            # Try different approaches to load the data due to PROJ issues
            gdf_cooling = None
            
            # First attempt: Load without specifying CRS handling
            try:
                gdf_cooling = gpd.read_file(self.cooling_centers_path, layer='cooling_center_parcels')
                print(f"   ✓ Loaded with default CRS handling")
            except Exception as e1:
                print(f"   ⚠ GPKG loading failed: {str(e1)[:100]}")
                
                # Try CSV fallback
                try:
                    gdf_cooling = self.load_cooling_centers_from_csv()
                    print(f"   ✓ Loaded from CSV fallback")
                except Exception as e2:
                    print(f"   ❌ CSV fallback also failed: {str(e2)[:100]}")
                    
                    # Second attempt: Load data and set CRS manually using fiona
                    try:
                        import fiona
                        with fiona.open(self.cooling_centers_path, layer='cooling_center_parcels') as src:
                            # Read features
                            features = [feature for feature in src]
                            
                            # Create DataFrame from features
                            df = pd.DataFrame([f['properties'] for f in features])
                            
                            # Create geometries
                            from shapely.geometry import shape
                            geometries = [shape(f['geometry']) for f in features]
                            
                            # Create GeoDataFrame without CRS initially
                            gdf_cooling = gpd.GeoDataFrame(df, geometry=geometries)
                            
                            # Try to set CRS using different methods
                            try:
                                # Try PROJ string for UTM Zone 15N
                                gdf_cooling.crs = '+proj=utm +zone=15 +datum=NAD83 +units=m +no_defs'
                                print(f"   ✓ Loaded with manual CRS (UTM 15N)")
                            except:
                                # If that fails, proceed without CRS
                                print(f"   ⚠ Proceeding without CRS")
                                
                        print(f"   ✓ Loaded using fiona")
                    except Exception as e3:
                        print(f"   ❌ All loading methods failed")
                        raise RuntimeError("Failed to load cooling centers data from any source")
        
        if gdf_cooling is None:
            raise RuntimeError("Failed to load cooling centers data")
            
        load_time = time.time() - start_time
        
        print(f"   ✓ Loaded {len(gdf_cooling)} cooling centers in {load_time:.2f} seconds")
        
        # Try to print CRS info safely
        try:
            print(f"   ✓ CRS: {gdf_cooling.crs}")
        except:
            print(f"   ✓ CRS: Not set or unavailable")
        
        # Print some information about the cooling centers
        if 'name' in gdf_cooling.columns:
            sample_names = gdf_cooling['name'].dropna().head(3).values
            if len(sample_names) > 0:
                print(f"   ✓ Sample cooling centers: {', '.join(sample_names)}")
        
        # Check for important columns
        important_cols = ['name', 'address', 'type', 'status', 'BUILD_YR']
        available_cols = [col for col in important_cols if col in gdf_cooling.columns]
        if available_cols:
            print(f"   ✓ Available metadata: {', '.join(available_cols)}")
        
        # Filter for active/open cooling centers if status column exists
        if 'status' in gdf_cooling.columns:
            active_centers = gdf_cooling[gdf_cooling['status'].notna()]
            if len(active_centers) < len(gdf_cooling):
                print(f"   ✓ Active cooling centers: {len(active_centers)}/{len(gdf_cooling)}")
                gdf_cooling = active_centers
        
        return gdf_cooling
    
    def align_crs(self, gdf_parcels, gdf_cooling):
        """Ensure both GeoDataFrames have compatible coordinate systems"""
        print("\n3. Aligning coordinate reference systems...")
        
        # Check if either dataset has no CRS
        parcels_has_crs = gdf_parcels.crs is not None
        cooling_has_crs = gdf_cooling.crs is not None
        
        if not parcels_has_crs and not cooling_has_crs:
            print("   ⚠ Neither dataset has CRS defined. Proceeding with raw coordinates.")
            return gdf_parcels, gdf_cooling
            
        if parcels_has_crs and not cooling_has_crs:
            print("   ⚠ Cooling centers have no CRS. Attempting to set same as parcels...")
            try:
                gdf_cooling.crs = gdf_parcels.crs
                print(f"   ✓ Set cooling centers CRS to match parcels")
            except:
                print("   ⚠ Could not set CRS. Proceeding anyway.")
            return gdf_parcels, gdf_cooling
            
        if not parcels_has_crs and cooling_has_crs:
            print("   ⚠ Parcels have no CRS. Attempting to set same as cooling centers...")
            try:
                gdf_parcels.crs = gdf_cooling.crs
                print(f"   ✓ Set parcels CRS to match cooling centers")
            except:
                print("   ⚠ Could not set CRS. Proceeding anyway.")
            return gdf_parcels, gdf_cooling
        
        # Both have CRS - try to align them
        try:
            if gdf_parcels.crs != gdf_cooling.crs:
                print(f"   Converting cooling centers to match parcels CRS...")
                gdf_cooling = gdf_cooling.to_crs(gdf_parcels.crs)
                print("   ✓ CRS aligned")
            else:
                print("   ✓ CRS already aligned")
        except Exception as e:
            print(f"   ⚠ Warning: Could not align CRS. Error: {str(e)[:100]}")
            print("   Proceeding with mismatched CRS - map may show distortion")
        
        return gdf_parcels, gdf_cooling
    
    def add_north_arrow(self, ax, x=0.95, y=0.95):
        """Add a north arrow to the map"""
        arrow = FancyArrowPatch(
            (x, y-0.02), (x, y+0.02),
            transform=ax.transAxes,
            arrowstyle='-|>',
            mutation_scale=20,
            lw=2,
            color='black'
        )
        ax.add_patch(arrow)
        ax.text(x, y+0.03, 'N', transform=ax.transAxes, 
                ha='center', fontsize=12, fontweight='bold')
    
    def create_cooling_centers_map(self, gdf_parcels, gdf_cooling):
        """Create a comprehensive map showing cooling centers and parcels"""
        print("\n4. Creating cooling centers map...")
        
        fig, ax = plt.subplots(figsize=self.figure_size, dpi=self.figure_dpi)
        
        # Plot parcels as background
        print("   Plotting parcel boundaries...")
        gdf_parcels.plot(
            ax=ax,
            color=self.parcel_color,
            edgecolor='white',
            linewidth=0.05,
            alpha=0.6
        )
        
        # Check if we have type information
        if 'type' in gdf_cooling.columns:
            # Plot cooling centers by type with different colors
            print("   Plotting cooling centers by type...")
            
            # Define colors for different types
            type_colors = {
                'Library': '#1B9E77',      # Teal
                'Recreation Center': '#D95F02',  # Orange
                'Community Center': '#7570B3',   # Purple
                'Park': '#66A61E',          # Green
                'School': '#E7298A',        # Pink
                'Other': '#666666'          # Grey
            }
            
            # Plot each type separately
            legend_elements = []
            for center_type, color in type_colors.items():
                subset = gdf_cooling[gdf_cooling['type'] == center_type]
                if len(subset) > 0:
                    subset.plot(
                        ax=ax,
                        color=color,
                        edgecolor='black',
                        linewidth=1,
                        alpha=0.8,
                        markersize=150
                    )
                    legend_elements.append(
                        mpatches.Patch(color=color, 
                                      label=f'{center_type} (n={len(subset)})',
                                      edgecolor='black')
                    )
            
            # Plot any remaining types
            known_types = list(type_colors.keys())
            other_types = gdf_cooling[~gdf_cooling['type'].isin(known_types)]
            if len(other_types) > 0:
                other_types.plot(
                    ax=ax,
                    color=type_colors['Other'],
                    edgecolor='black',
                    linewidth=1,
                    alpha=0.8,
                    markersize=150
                )
                legend_elements.append(
                    mpatches.Patch(color=type_colors['Other'], 
                                  label=f'Other (n={len(other_types)})',
                                  edgecolor='black')
                )
        else:
            # Plot all cooling centers with same color
            gdf_cooling.plot(
                ax=ax,
                color=self.cooling_center_color,
                edgecolor=self.cooling_center_edge,
                linewidth=1.5,
                alpha=0.9,
                markersize=150
            )
            legend_elements = [
                mpatches.Patch(color=self.cooling_center_color, 
                              label=f'Cooling Centers (n={len(gdf_cooling)})',
                              edgecolor=self.cooling_center_edge)
            ]
        
        # Add parcel legend element at the beginning
        legend_elements.insert(0, 
            mpatches.Patch(color=self.parcel_color, label='Parcels', alpha=0.6)
        )
        
        # Add title
        ax.set_title('Cooling Center Distribution by Type in Hennepin County', 
                    fontsize=14, fontweight='bold', pad=20)
        
        # Remove axes
        ax.set_axis_off()
        
        # Add legend
        legend = ax.legend(
            handles=legend_elements,
            loc='lower left',
            frameon=True,
            fancybox=True,
            shadow=True,
            fontsize=9,
            ncol=1
        )
        legend.get_frame().set_alpha(0.9)
        
        # Add scale bar
        scalebar = ScaleBar(
            1, 'm', 
            length_fraction=0.15, 
            location='lower right',
            box_alpha=0.8, 
            pad=0.5, 
            sep=2,
            font_properties={'size': 9}
        )
        ax.add_artist(scalebar)
        
        # Add north arrow
        self.add_north_arrow(ax)
        
        # Calculate and display statistics
        stats_lines = []
        stats_lines.append(f"Total Cooling Centers: {len(gdf_cooling)}")
        
        # Add average distance statistics if available in parcels
        if 'cooling_distance' in gdf_parcels.columns:
            avg_distance_m = gdf_parcels['cooling_distance'].mean()
            avg_distance_miles = avg_distance_m * 0.000621371
            stats_lines.append(f"Avg. Distance to Center: {avg_distance_miles:.2f} miles")
        
        # Add coverage statistics
        if 'cooling_distance' in gdf_parcels.columns:
            within_1_mile = (gdf_parcels['cooling_distance'] <= 1609.34).sum()  # 1 mile in meters
            coverage_pct = (within_1_mile / len(gdf_parcels)) * 100
            stats_lines.append(f"Parcels within 1 mile: {coverage_pct:.1f}%")
        
        stats_text = '\n'.join(stats_lines)
        
        ax.text(0.02, 0.98, stats_text,
               transform=ax.transAxes, 
               fontsize=9,
               verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='white', alpha=0.9))
        
        # Add data source
        ax.text(0.98, 0.02, 'Data: Hennepin County', 
               transform=ax.transAxes, fontsize=7,
               ha='right', style='italic', alpha=0.7)
        
        # Adjust layout
        plt.tight_layout()
        
        # Save figure
        output_path = self.output_dir / "cooling_centers_map.png"
        plt.savefig(output_path, dpi=self.figure_dpi, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        plt.close()
        
        print(f"   ✓ Map saved: {output_path}")
        
        return output_path
    
    def generate_summary_statistics(self, gdf_parcels, gdf_cooling):
        """Generate summary statistics about cooling centers"""
        print("\n5. Generating summary statistics...")
        
        stats = {}
        
        # Basic counts
        stats['total_parcels'] = len(gdf_parcels)
        stats['total_cooling_centers'] = len(gdf_cooling)
        
        # Type distribution
        if 'type' in gdf_cooling.columns:
            type_dist = gdf_cooling['type'].value_counts().to_dict()
            stats['cooling_center_types'] = type_dist
        
        # Build year statistics
        if 'BUILD_YR' in gdf_cooling.columns:
            build_years = pd.to_numeric(gdf_cooling['BUILD_YR'], errors='coerce')
            valid_years = build_years[build_years > 0]
            if len(valid_years) > 0:
                stats['avg_build_year'] = valid_years.mean()
                stats['oldest_build_year'] = valid_years.min()
                stats['newest_build_year'] = valid_years.max()
        
        # Distance statistics from parcels
        if 'cooling_distance' in gdf_parcels.columns:
            distances_m = gdf_parcels['cooling_distance']
            distances_miles = distances_m * 0.000621371
            
            stats['avg_distance_miles'] = distances_miles.mean()
            stats['median_distance_miles'] = distances_miles.median()
            stats['max_distance_miles'] = distances_miles.max()
            
            # Coverage statistics
            stats['parcels_within_0.5_miles'] = (distances_m <= 804.67).sum()
            stats['parcels_within_1_mile'] = (distances_m <= 1609.34).sum()
            stats['parcels_within_2_miles'] = (distances_m <= 3218.69).sum()
            
            stats['pct_within_0.5_miles'] = (stats['parcels_within_0.5_miles'] / len(gdf_parcels)) * 100
            stats['pct_within_1_mile'] = (stats['parcels_within_1_mile'] / len(gdf_parcels)) * 100
            stats['pct_within_2_miles'] = (stats['parcels_within_2_miles'] / len(gdf_parcels)) * 100
        
        # Print statistics
        print("\n   Cooling Center Statistics:")
        print("   " + "="*50)
        print(f"   Total Parcels: {stats['total_parcels']:,}")
        print(f"   Total Cooling Centers: {stats['total_cooling_centers']}")
        
        if 'cooling_center_types' in stats:
            print("\n   Cooling Center Types:")
            for ctype, count in stats['cooling_center_types'].items():
                print(f"     - {ctype}: {count}")
        
        if 'avg_build_year' in stats:
            print(f"\n   Building Years:")
            print(f"     - Average: {stats['avg_build_year']:.0f}")
            print(f"     - Oldest: {stats['oldest_build_year']:.0f}")
            print(f"     - Newest: {stats['newest_build_year']:.0f}")
        
        if 'avg_distance_miles' in stats:
            print(f"\n   Distance to Nearest Center:")
            print(f"     - Average: {stats['avg_distance_miles']:.2f} miles")
            print(f"     - Median: {stats['median_distance_miles']:.2f} miles")
            print(f"     - Maximum: {stats['max_distance_miles']:.2f} miles")
            
            print(f"\n   Coverage:")
            print(f"     - Within 0.5 miles: {stats['pct_within_0.5_miles']:.1f}% ({stats['parcels_within_0.5_miles']:,} parcels)")
            print(f"     - Within 1 mile: {stats['pct_within_1_mile']:.1f}% ({stats['parcels_within_1_mile']:,} parcels)")
            print(f"     - Within 2 miles: {stats['pct_within_2_miles']:.1f}% ({stats['parcels_within_2_miles']:,} parcels)")
        
        return stats
    
    def run(self):
        """Main execution"""
        start_time = time.time()
        
        try:
            # Load data
            gdf_parcels = self.load_parcel_data()
            gdf_cooling = self.load_cooling_centers()
            
            # Align CRS
            gdf_parcels, gdf_cooling = self.align_crs(gdf_parcels, gdf_cooling)
            
            # Create the comprehensive map
            output_map = self.create_cooling_centers_map(gdf_parcels, gdf_cooling)
            
            # Generate statistics
            stats = self.generate_summary_statistics(gdf_parcels, gdf_cooling)
            
            # Final summary
            elapsed_time = time.time() - start_time
            print("\n" + "="*60)
            print("PROCESSING COMPLETE")
            print("="*60)
            print(f"Total execution time: {elapsed_time:.2f} seconds")
            print(f"\nMap saved to: {self.output_dir}/cooling_centers_map.png")
            
            return gdf_parcels, gdf_cooling, stats
            
        except Exception as e:
            print(f"\n❌ Error during processing: {str(e)}")
            import traceback
            traceback.print_exc()
            return None, None, None


def main():
    """Main entry point"""
    print("Starting Cooling Centers Map Visualization...")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Create and run mapper
    mapper = CoolingCenterMapper()
    gdf_parcels, gdf_cooling, stats = mapper.run()
    
    if gdf_parcels is not None and gdf_cooling is not None:
        print("\n✅ Script completed successfully!")
        print("Maps have been saved to the output directory.")
    else:
        print("\n❌ Script failed. Please check the error messages above.")
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())