#!/usr/bin/env python3
"""
run_model_results_visualization_dates.py - Multi-date visualization for Heat Risk ABM Model

This script creates visualizations for heat risk model results across multiple dates.
It reads the output from run_parallel.py and generates 4 visualization types per date:
1. Probability distribution histogram
2. Spatial probability map  
3. Cooling center catchment areas
4. Decision stability map

Input: Results from run_parallel.py trial folder
Output: Visualizations saved to ../../output/visualization/trial_*/date/

Usage:
    VS Code: Just click run - uses config settings in main()
    
    To modify behavior, edit the config dictionary in main():
    - dates: [] for all dates, or ['20240601', '20240602'] for specific dates
    - trial_folder: None for most recent, or 'trial_20240601_120000' for specific
    - show_plots: True to display plots interactively
    - save_formats: ['png', 'pdf', 'svg'] for multiple formats
    
    Command line: python run_model_results_visualization_dates.py [trial] [--dates 20240601 20240602]
    
Author: Project contributors
Date: 2024
"""

import os
import sys
import time
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
import seaborn as sns
import colorsys
import random
from pathlib import Path
from datetime import datetime, timedelta
import warnings
import argparse
import json
from tqdm import tqdm

# Suppress warnings
warnings.filterwarnings('ignore')

class HeatRiskVisualizer:
    """Visualizer for heat risk model results across multiple dates"""
    
    def __init__(self, trial_folder, config=None):
        """
        Initialize visualizer
        
        Args:
            trial_folder: Name of trial folder (e.g., 'trial_20240601_120000')
            config: Optional configuration dictionary
        """
        self.trial_folder = trial_folder
        self.config = self._get_default_config()
        if config:
            self.config.update(config)
        
        # Set up paths
        self.input_base_path = Path("../../output/results") / trial_folder
        self.output_base_path = Path("../../output/visualization") / trial_folder
        
        # Validate input path
        if not self.input_base_path.exists():
            raise ValueError(f"Input trial folder not found: {self.input_base_path}")
        
        # Create output directory
        self.output_base_path.mkdir(parents=True, exist_ok=True)
    
    def _get_default_config(self):
        """Get default configuration"""
        return {
            'figure_size_small': (10, 6),
            'figure_size_large': (15, 10),
            'dpi': 300,
            'colormap_probability': 'viridis',
            'colormap_stability': 'RdYlGn',
            'histogram_color': 'skyblue',
            'histogram_edge_color': 'black',
            'alpha': 0.9,
            'save_formats': ['png'],
            'show_plots': False
        }
    
    def get_available_dates(self):
        """Get list of available dates from trial folder"""
        dates = []
        for item in self.input_base_path.iterdir():
            if item.is_dir() and item.name.isdigit() and len(item.name) == 8:
                dates.append(item.name)
        return sorted(dates)
    
    def load_ensemble_data(self, date_str):
        """Load ensemble data for a specific date"""
        date_path = self.input_base_path / date_str
        
        # Load shapefile
        shp_path = date_path / f"ensemble_{date_str}.shp"
        if not shp_path.exists():
            print(f"Warning: Shapefile not found for {date_str}")
            return None
        
        gdf = gpd.read_file(shp_path)
        
        # Rename columns back from shapefile abbreviations
        column_mapping = {
            'proba': 'proba',
            'proba_std': 'proba_std',
            'decision': 'decision',
            'stability': 'stability',
            'temp': 'temperature',
            'cool_centr': 'cooling_center'
        }
        
        for old_col, new_col in column_mapping.items():
            if old_col in gdf.columns and old_col != new_col:
                gdf = gdf.rename(columns={old_col: new_col})
        
        # Load metadata if available
        metadata_path = date_path / f"metadata_{date_str}.json"
        metadata = None
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
        
        return gdf, metadata
    
    def create_probability_histogram(self, gdf, date_str, metadata=None):
        """Create probability distribution histogram"""
        plt.figure(figsize=self.config['figure_size_small'])
        
        # Create histogram with KDE
        sns.histplot(gdf['proba'], kde=True, bins=20, 
                    color=self.config['histogram_color'],
                    edgecolor=self.config['histogram_edge_color'],
                    alpha=0.7)
        
        # Add title with metadata if available
        title = f'Distribution of Movement Probability - {date_str}'
        if metadata and 'num_runs' in metadata:
            title += f' (Ensemble of {metadata["num_runs"]} runs)'
        plt.title(title, fontsize=16)
        
        plt.xlabel('Probability of Moving to Cooling Center', fontsize=14)
        plt.ylabel('Frequency', fontsize=14)
        
        # Add statistics text
        avg_prob = gdf['proba'].mean()
        std_prob = gdf['proba'].std()
        plt.text(0.7, 0.9, f'Mean: {avg_prob:.3f}\nStd: {std_prob:.3f}',
                transform=plt.gca().transAxes,
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        plt.tight_layout()
        
        # Save figure
        self._save_figure(date_str, 'probability_histogram')
        
    def create_spatial_probability_map(self, gdf, date_str):
        """Create spatial probability map"""
        plt.figure(figsize=self.config['figure_size_large'])
        
        # Plot with probability coloring
        gdf.plot(column='proba', 
                cmap=self.config['colormap_probability'],
                legend=True,
                legend_kwds={'label': 'Probability of Moving to Cooling Center'},
                ax=plt.gca(),
                edgecolor=None,
                alpha=self.config['alpha'])
        
        plt.title(f'Spatial Distribution of Movement Probability - {date_str}', fontsize=16)
        plt.axis('equal')
        plt.axis('off')
        plt.tight_layout()
        
        # Save figure
        self._save_figure(date_str, 'spatial_probability_map')
    
    def create_cooling_center_catchments(self, gdf, date_str):
        """Create cooling center catchment area visualization"""
        # Separate stay and move parcels
        stay_parcels = gdf[gdf['decision'] == 'stay'].copy()
        moved_parcels = gdf[gdf['decision'] == 'move'].copy()
        
        # Get unique cooling centers
        unique_centers = moved_parcels['cooling_center'].unique()
        unique_centers = [c for c in unique_centers if c != 'None' and pd.notna(c)]
        
        if len(unique_centers) == 0:
            print(f"No cooling center movements found for {date_str}")
            return
        
        # Generate colors
        colors = self._generate_distinct_colors(len(unique_centers))
        center_to_color = {center: colors[i] for i, center in enumerate(unique_centers)}
        
        # Create figure
        plt.figure(figsize=self.config['figure_size_large'])
        
        # Plot stay parcels in gray
        if len(stay_parcels) > 0:
            stay_parcels.plot(color='lightgray', ax=plt.gca(),
                             edgecolor=None, alpha=0.5)
        
        # Plot each cooling center's catchment area
        for center in unique_centers:
            center_parcels = moved_parcels[moved_parcels['cooling_center'] == center]
            if len(center_parcels) > 0:
                color = center_to_color[center]
                center_parcels.plot(color=color, ax=plt.gca(),
                                   edgecolor=None, alpha=0.7)
        
        plt.title(f'Cooling Center Catchment Areas - {date_str}\n(Gray = Stay Home)', 
                 fontsize=16)
        plt.axis('equal')
        plt.axis('off')
        plt.tight_layout()
        
        # Save figure
        self._save_figure(date_str, 'cooling_center_catchments')
        
        # Print statistics
        self._print_cooling_center_stats(stay_parcels, moved_parcels, unique_centers, date_str)
    
    def create_decision_stability_map(self, gdf, date_str):
        """Create decision stability map"""
        plt.figure(figsize=self.config['figure_size_large'])
        
        # Plot with stability coloring
        gdf.plot(column='stability',
                cmap=self.config['colormap_stability'],
                legend=True,
                legend_kwds={'label': 'Decision Stability Across Runs'},
                ax=plt.gca(),
                edgecolor=None,
                alpha=self.config['alpha'])
        
        plt.title(f'Decision Stability Map - {date_str}', fontsize=16)
        plt.axis('equal')
        plt.axis('off')
        plt.tight_layout()
        
        # Save figure
        self._save_figure(date_str, 'decision_stability_map')
    
    def _generate_distinct_colors(self, n):
        """Generate n distinct colors using HSV color space"""
        np.random.seed(42)
        random.seed(42)
        
        hsv_colors = []
        for i in range(n):
            h = i / n
            s = 0.7 + 0.3 * random.random()
            v = 0.8 + 0.2 * random.random()
            hsv_colors.append((h, s, v))
        
        rgb_colors = [colorsys.hsv_to_rgb(*color) for color in hsv_colors]
        return rgb_colors
    
    def _save_figure(self, date_str, figure_name):
        """Save figure to appropriate directory"""
        # Create date directory
        date_output_path = self.output_base_path / date_str
        date_output_path.mkdir(exist_ok=True)
        
        # Save in each format
        for fmt in self.config['save_formats']:
            output_file = date_output_path / f"{figure_name}.{fmt}"
            plt.savefig(output_file, dpi=self.config['dpi'], bbox_inches='tight')
        
        # Show or close
        if self.config['show_plots']:
            plt.show()
        else:
            plt.close()
    
    def _print_cooling_center_stats(self, stay_parcels, moved_parcels, unique_centers, date_str):
        """Print cooling center statistics"""
        print(f"     Stats: {len(stay_parcels):,} stay home, {len(moved_parcels):,} move to {len(unique_centers)} centers")
    
    def create_summary_report(self, all_dates_processed):
        """Create a summary report across all dates"""
        report_path = self.output_base_path / "visualization_summary.txt"
        
        with open(report_path, 'w') as f:
            f.write("Heat Risk Model Visualization Summary\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Trial: {self.trial_folder}\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Dates processed: {len(all_dates_processed)}\n\n")
            
            f.write("Dates visualized:\n")
            for date in sorted(all_dates_processed):
                f.write(f"  - {date}\n")
            
            f.write("\nVisualization types created:\n")
            f.write("  - Probability distribution histogram\n")
            f.write("  - Spatial probability map\n")
            f.write("  - Cooling center catchment areas\n")
            f.write("  - Decision stability map\n")
            
            f.write(f"\nOutput location: {self.output_base_path}\n")
        
        print(f"\nSummary report saved: {report_path}")
    
    def process_all_dates(self, dates=None):
        """Process visualizations for all dates"""
        if dates is None:
            dates = self.get_available_dates()
        
        if not dates:
            print("No dates found to process!")
            return
        
        print(f"\n📊 Processing visualizations for {len(dates)} dates: {', '.join(dates)}")
        print(f"📁 Output directory: {self.output_base_path}")
        
        processed_dates = []
        
        for date_str in tqdm(dates, desc="Creating visualizations"):
            print(f"\n📅 Processing {date_str}...")
            
            # Load data
            result = self.load_ensemble_data(date_str)
            if result is None:
                print(f"  ⚠️  Skipping {date_str} - no data found")
                continue
            
            gdf, metadata = result
            
            # Create visualizations
            try:
                print(f"  📈 Creating probability histogram...")
                self.create_probability_histogram(gdf, date_str, metadata)
                
                print(f"  🗺️  Creating spatial probability map...")
                self.create_spatial_probability_map(gdf, date_str)
                
                print(f"  🏢 Creating cooling center catchments...")
                self.create_cooling_center_catchments(gdf, date_str)
                
                print(f"  🎯 Creating decision stability map...")
                self.create_decision_stability_map(gdf, date_str)
                
                processed_dates.append(date_str)
                print(f"  ✅ Completed visualizations for {date_str}")
                
            except Exception as e:
                print(f"  ❌ Error processing {date_str}: {str(e)}")
                import traceback
                traceback.print_exc()
        
        # Create summary report
        if processed_dates:
            self.create_summary_report(processed_dates)
        
        return processed_dates


def find_most_recent_trial():
    """Find the most recent trial folder"""
    results_path = Path("../../output/results")
    
    if not results_path.exists():
        return None
    
    # Find all trial folders
    trial_folders = []
    for item in results_path.iterdir():
        if item.is_dir() and item.name.startswith('trial_'):
            # Extract timestamp from folder name (trial_YYYYMMDD_HHMMSS)
            try:
                timestamp_str = item.name.replace('trial_', '')
                # Parse the timestamp to allow sorting
                trial_folders.append((item.name, timestamp_str))
            except:
                continue
    
    if not trial_folders:
        return None
    
    # Sort by timestamp and get the most recent
    trial_folders.sort(key=lambda x: x[1], reverse=True)
    return trial_folders[0][0]


def main():
    """Main execution function"""
    
    # ========== CONFIGURATION - MODIFY HERE! ==========
    # Examples:
    #   Process all dates from most recent trial:
    #     'dates': []
    #   Process specific dates only:
    #     'dates': ['20240601', '20240602', '20240603']
    #   Use specific trial folder:
    #     'trial_folder': 'trial_20240601_120000'
    
    config = {
        'trial_folder': None,  # None = use most recent trial
        'dates': [],  # Empty = process all dates, or specify like ['20240601', '20240602']
        'show_plots': False,  # Set to True to display plots interactively
        'save_formats': ['png'],  # Output formats: ['png', 'pdf', 'svg']
        'figure_size_small': (10, 6),
        'figure_size_large': (15, 10),
        'dpi': 300,
        'colormap_probability': 'viridis',
        'colormap_stability': 'RdYlGn',
        'histogram_color': 'skyblue',
        'histogram_edge_color': 'black',
        'alpha': 0.9
    }
    
    # Optional: Generate date range programmatically (like run_parallel.py)
    # from datetime import datetime, timedelta
    # start_date = datetime(2024, 6, 1)
    # end_date = datetime(2024, 6, 5)
    # date_range = []
    # current_date = start_date
    # while current_date <= end_date:
    #     date_range.append(current_date.strftime('%Y%m%d'))
    #     current_date += timedelta(days=1)
    # config['dates'] = date_range
    # ================================================
    
    # Optional: Override config with command line arguments if provided
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(
            description='Create visualizations for heat risk model results'
        )
        parser.add_argument(
            'trial_folder',
            type=str,
            nargs='?',
            help='Name of trial folder (e.g., trial_20240601_120000)'
        )
        parser.add_argument(
            '--dates',
            type=str,
            nargs='+',
            help='Specific dates to process (e.g., 20240601 20240602)'
        )
        parser.add_argument(
            '--show',
            action='store_true',
            help='Show plots interactively'
        )
        parser.add_argument(
            '--formats',
            type=str,
            nargs='+',
            help='Output formats (png, pdf, svg)'
        )
        
        args = parser.parse_args()
        
        # Override config with command line args
        if args.trial_folder:
            config['trial_folder'] = args.trial_folder
        if args.dates:
            config['dates'] = args.dates
        if args.show:
            config['show_plots'] = True
        if args.formats:
            config['save_formats'] = args.formats
    
    # If no trial folder specified, find the most recent
    if config['trial_folder'] is None:
        print("No trial folder specified. Finding most recent trial...")
        config['trial_folder'] = find_most_recent_trial()
        
        if config['trial_folder'] is None:
            print("❌ No trial folders found in ../../output/results/")
            print("   Please run the model first or specify a trial folder.")
            return 1
        
        print(f"✓ Using most recent trial: {config['trial_folder']}")
    
    # Run visualization
    print(f"\n{'='*60}")
    print(f"🎨 Heat Risk Model Visualization Tool")
    print(f"{'='*60}")
    print(f"📂 Trial folder: {config['trial_folder']}")
    if config['dates']:
        print(f"📅 Specific dates: {', '.join(config['dates'])}")
    else:
        print(f"📅 Processing: All available dates")
    print(f"💾 Output formats: {', '.join(config['save_formats'])}")
    print(f"👁️  Show plots: {config['show_plots']}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        # Initialize visualizer
        visualizer = HeatRiskVisualizer(config['trial_folder'], config)
        
        # Process dates (None means all dates if dates list is empty)
        dates_to_process = config['dates'] if config['dates'] else None
        processed_dates = visualizer.process_all_dates(dates_to_process)
        
        if not processed_dates:
            print(f"\n⚠️  No dates were successfully processed")
            return 1
        
        # Summary
        elapsed_time = time.time() - start_time
        print(f"\n{'='*60}")
        print(f"✅ Visualization complete!")
        print(f"{'='*60}")
        print(f"📊 Processed {len(processed_dates)} dates in {elapsed_time:.1f} seconds")
        print(f"📁 Output saved to: {visualizer.output_base_path}")
        print(f"📄 Formats: {', '.join(config['save_formats'])}")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    # Check if running without arguments (e.g., from VS Code)
    if len(sys.argv) == 1:
        print("🎨 Running visualization with configuration from main() function")
        print("   To modify settings, edit the config dictionary in the script")
        print("   For command line options, run: python run_model_results_visualization_dates.py -h\n")
    
    sys.exit(main())