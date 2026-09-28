"""
Hennepin County Heat Risk ABM Model - Consolidated Script
Author: Project contributors
Date: 2025-06-09

This script runs the complete heat risk agent-based model ensemble simulation.
"""
import os

import os
import sys
import time
import yaml
import random
import warnings
from pathlib import Path
from getpass import getpass

# Analysis
import numpy as np
import pandas as pd
import geopandas as gpd

# Visualization
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import seaborn as sns
import colorsys

# Progress tracking
from tqdm import tqdm

# Model imports
sys.path.append('./src')
from src import Parcel, HeatEvent


class HeatRiskModelRunner:
    """Main class for running the Heat Risk ABM Model"""
    
    def __init__(self, config_path="config/config.yaml"):
        """Initialize the model runner with configuration"""
        self.config = self.load_config(config_path)
        self.setup_environment()
        self.all_gdfs = []
        self.all_results = []
        
    def load_config(self, config_path):
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as file:
                config = yaml.safe_load(file)
            print(f"✓ Configuration loaded from {config_path}")
            return config
        except FileNotFoundError:
            print(f"✗ Configuration file not found: {config_path}")
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"✗ Error parsing YAML configuration: {e}")
            sys.exit(1)
    
    def setup_environment(self):
        """Set up directories and environment"""
        # Suppress warnings if configured
        if self.config['processing']['suppress_warnings']:
            warnings.filterwarnings('ignore')
        
        # Set random seed
        seed = self.config['model']['random_seed']
        np.random.seed(seed)
        random.seed(seed)
        
        # Change to code directory
        code_dir = self.config['paths']['code_dir']
        os.chdir(code_dir)
        print(f"Current working directory: {os.getcwd()}")
        
        # Create all necessary directories
        self.create_directories()
        
        # Set up database password
        self.setup_database_config()
        
        print("✓ Environment setup complete")
    
    def create_directories(self):
        """Create all required directories"""
        paths = self.config['paths']
        
        directories_to_create = [
            paths['output_dir'],
            os.path.join('.', paths['results_dir']),
            os.path.join('.', paths['figures_dir']),
            os.path.join(paths['output_dir'], 'results'),
            os.path.join(paths['output_dir'], 'figures')
        ]
        
        for directory in directories_to_create:
            os.makedirs(directory, exist_ok=True)
            print(f"Created directory: {directory}")
    
    def setup_database_config(self):
        """Set up database configuration with password"""
        # Update utils.py with database configuration
        db_config = self.config['database']
        
        # Get password (you might want to use environment variable or prompt)
        if 'PGPASSWORD' in os.environ:
            password = os.environ['PGPASSWORD']
        else:
            password = getpass("Enter PostgreSQL password: ")
        
        # Update the database configuration in utils.py
        self.update_database_config(db_config, password)
    
    def update_database_config(self, db_config, password):
        """Keep runtime credentials in memory; never write them to source files."""
        from src.utils import DB_CONFIG
        DB_CONFIG.update({
            "host": os.environ["PGHOST"],
            "database": os.environ["PGDATABASE"],
            "user": os.environ["PGUSER"],
            "password": password,
            "port": os.environ.get("PGPORT", "5432"),
        })
    
    def run_ensemble_simulation(self):
        """Run the ensemble simulation"""
        num_runs = self.config['model']['num_runs']
        temp_raster = self.config['input_data']['temp_raster']
        fallback_temp = self.config['model']['fallback_temperature']
        
        print(f"Running model ensemble with {num_runs} iterations...")
        
        # Progress bar setup
        if self.config['processing']['show_progress']:
            pbar = tqdm(range(num_runs), desc="Model Runs")
        else:
            pbar = range(num_runs)
        
        for run in pbar:
            # Create a new model instance for each run
            heat_event = HeatEvent(fallback_temp)
            
            # Run the simulation
            if self.config['input_data']['use_raster']:
                heat_event.run_simulation(temp_raster)
            else:
                static_temp = self.config['input_data']['static_temperature']
                heat_event.run_simulation(temperature=static_temp)
            
            heat_event.process_results()
            
            # Store the results
            self.all_gdfs.append(heat_event.gdf.copy())
            
            # Collect summary statistics
            run_results = self.calculate_run_statistics(heat_event.gdf, run + 1)
            self.all_results.append(run_results)
        
        print("✓ Ensemble simulation complete")
    
    def calculate_run_statistics(self, gdf, run_number):
        """Calculate statistics for a single run"""
        run_results = {
            'run': run_number,
            'total_parcels': len(gdf)
        }
        
        # Count decisions
        run_results['stayed_home'] = gdf['decision'].value_counts().get('stay', 0)
        run_results['moved_to_cooling_center'] = len(gdf) - run_results['stayed_home']
        
        # Calculate percentages
        total = run_results['total_parcels']
        run_results['stayed_home_pct'] = (run_results['stayed_home'] / total) * 100
        run_results['moved_pct'] = (run_results['moved_to_cooling_center'] / total) * 100
        
        return run_results
    
    def analyze_ensemble_results(self):
        """Analyze and print ensemble results"""
        results_df = pd.DataFrame(self.all_results)
        print("\nResults from individual runs:")
        print(results_df[['run', 'stayed_home_pct', 'moved_pct']].round(2))
        
        # Calculate ensemble averages
        avg_results = {
            'stayed_home_pct': results_df['stayed_home_pct'].mean(),
            'moved_pct': results_df['moved_pct'].mean(),
            'stayed_home_std': results_df['stayed_home_pct'].std(),
            'moved_std': results_df['moved_pct'].std()
        }
        
        print("\nEnsemble average results:")
        print(f"Stayed home: {avg_results['stayed_home_pct']:.2f}% (±{avg_results['stayed_home_std']:.2f}%)")
        print(f"Moved to cooling center: {avg_results['moved_pct']:.2f}% (±{avg_results['moved_std']:.2f}%)")
        
        return avg_results
    
    def create_ensemble_geodataframe(self):
        """Create ensemble GeoDataFrame with averaged results"""
        print("Creating ensemble GeoDataFrame...")
        
        # Base geometry from first run
        base_gdf = self.all_gdfs[0]
        ensemble_gdf = gpd.GeoDataFrame(
            geometry=base_gdf.geometry,
            index=base_gdf.index
        )
        ensemble_gdf['pid'] = base_gdf['pid']
        
        # Calculate average probabilities
        ensemble_gdf['proba'] = 0
        for gdf in self.all_gdfs:
            ensemble_gdf['proba'] += gdf['proba'] / len(self.all_gdfs)
        
        # Determine final decisions by majority voting
        ensemble_gdf = self.calculate_majority_decisions(ensemble_gdf)
        
        # Calculate decision stability
        ensemble_gdf = self.calculate_decision_stability(ensemble_gdf)
        
        return ensemble_gdf
    
    def calculate_majority_decisions(self, ensemble_gdf):
        """Calculate final decisions based on majority voting"""
        ensemble_gdf['decision'] = ''
        ensemble_gdf['cooling_center'] = ''
        
        decision_counts = {}
        cooling_center_counts = {}
        
        # Count decisions for each parcel across all runs
        for idx in ensemble_gdf.index:
            decision_counts[idx] = {'stay': 0, 'move': 0}
            cooling_center_counts[idx] = {}
            
            for gdf in self.all_gdfs:
                decision = gdf.loc[idx, 'decision']
                
                if decision == 'stay':
                    decision_counts[idx]['stay'] += 1
                else:
                    decision_counts[idx]['move'] += 1
                    if decision not in cooling_center_counts[idx]:
                        cooling_center_counts[idx][decision] = 0
                    cooling_center_counts[idx][decision] += 1
        
        # Set final decisions
        for idx in ensemble_gdf.index:
            if decision_counts[idx]['move'] > decision_counts[idx]['stay']:
                ensemble_gdf.loc[idx, 'decision'] = 'move'
                
                # Find most common cooling center
                if cooling_center_counts[idx]:
                    most_common_center = max(
                        cooling_center_counts[idx].items(),
                        key=lambda x: x[1]
                    )[0]
                    ensemble_gdf.loc[idx, 'cooling_center'] = most_common_center
                else:
                    ensemble_gdf.loc[idx, 'cooling_center'] = 'None'
            else:
                ensemble_gdf.loc[idx, 'decision'] = 'stay'
                ensemble_gdf.loc[idx, 'cooling_center'] = 'None'
        
        return ensemble_gdf
    
    def calculate_decision_stability(self, ensemble_gdf):
        """Calculate stability of decisions across runs"""
        stability = {}
        for idx in ensemble_gdf.index:
            decisions = [gdf.loc[idx, 'decision'] for gdf in self.all_gdfs]
            most_common = max(set(decisions), key=decisions.count)
            stability[idx] = decisions.count(most_common) / len(decisions)
        
        ensemble_gdf['stability'] = pd.Series(stability)
        return ensemble_gdf
    
    def save_results(self, ensemble_gdf):
        """Save ensemble results to shapefile"""
        output_file = os.path.join(
            self.config['paths']['output_dir'],
            'results',
            self.config['output']['ensemble_results']
        )
        
        try:
            ensemble_gdf.to_file(output_file, driver='ESRI Shapefile')
            print(f"✓ Ensemble results saved to: {output_file}")
        except Exception as e:
            # Fallback to local directory
            local_output_file = os.path.join(
                self.config['paths']['results_dir'],
                self.config['output']['ensemble_results']
            )
            ensemble_gdf.to_file(local_output_file, driver='ESRI Shapefile')
            print(f"✓ Ensemble results saved to: {local_output_file}")
            print(f"Note: Original path failed ({e})")
    
    def create_visualizations(self, ensemble_gdf):
        """Create all visualizations"""
        print("Creating visualizations...")
        
        vis_config = self.config['visualization']
        
        # 1. Probability distribution histogram
        self.plot_probability_distribution(ensemble_gdf, vis_config)
        
        # 2. Spatial probability map
        self.plot_spatial_probability_map(ensemble_gdf, vis_config)
        
        # 3. Cooling center catchment areas
        self.plot_cooling_center_catchments(ensemble_gdf, vis_config)
        
        # 4. Decision stability map
        self.plot_decision_stability(ensemble_gdf, vis_config)
        
        print("✓ All visualizations created")
    
    def plot_probability_distribution(self, ensemble_gdf, vis_config):
        """Create probability distribution histogram"""
        plt.figure(figsize=vis_config['figure_size_small'])
        sns.histplot(ensemble_gdf['proba'], kde=True, bins=20, color='skyblue',
                     edgecolor='black', alpha=0.7)
        plt.title('Distribution of Average Probability Values (Ensemble)', fontsize=16)
        plt.xlabel('Probability', fontsize=14)
        plt.ylabel('Frequency', fontsize=14)
        plt.tight_layout()
        
        output_path = os.path.join(
            self.config['paths']['figures_dir'],
            self.config['output']['probability_histogram']
        )
        plt.savefig(output_path, dpi=vis_config['dpi'], bbox_inches='tight')
        plt.show()
    
    def plot_spatial_probability_map(self, ensemble_gdf, vis_config):
        """Create spatial probability map"""
        plt.figure(figsize=vis_config['figure_size_large'])
        ensemble_gdf.plot(
            column='proba',
            cmap=vis_config['colormap'],
            legend=True,
            legend_kwds={'label': 'Probability of Moving to Cooling Center'},
            ax=plt.gca(),
            edgecolor=None,
            alpha=vis_config['alpha']
        )
        plt.title('Ensemble Results: Probability of Moving to Cooling Center', fontsize=16)
        plt.axis('equal')
        plt.tight_layout()
        
        output_path = os.path.join(
            self.config['paths']['figures_dir'],
            self.config['output']['spatial_map']
        )
        plt.savefig(output_path, dpi=vis_config['dpi'], bbox_inches='tight')
        plt.show()
    
    def plot_cooling_center_catchments(self, ensemble_gdf, vis_config):
        """Create cooling center catchment area visualization"""
        stay_parcels = ensemble_gdf[ensemble_gdf['decision'] == 'stay'].copy()
        moved_parcels = ensemble_gdf[ensemble_gdf['decision'] == 'move'].copy()
        
        unique_centers = moved_parcels['cooling_center'].unique()
        colors = self.generate_distinct_colors(len(unique_centers))
        center_to_color = {center: colors[i] for i, center in enumerate(unique_centers)}
        
        plt.figure(figsize=vis_config['figure_size_large'])
        
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
        
        plt.title('Cooling Center Catchment Areas (Gray areas represent parcels staying home)', fontsize=16)
        plt.axis('equal')
        plt.tight_layout()
        
        output_path = os.path.join(
            self.config['paths']['figures_dir'],
            self.config['output']['catchment_map']
        )
        plt.savefig(output_path, dpi=vis_config['dpi'], bbox_inches='tight')
        plt.show()
        
        # Print statistics
        center_counts = moved_parcels['cooling_center'].value_counts()
        print(f"Number of parcels staying home: {len(stay_parcels)}")
        print(f"Number of parcels moving to cooling centers: {len(moved_parcels)}")
        print(f"Number of unique cooling centers: {len(unique_centers)}")
        print(f"Top 10 cooling centers by usage:")
        print(center_counts.nlargest(10))
    
    def plot_decision_stability(self, ensemble_gdf, vis_config):
        """Create decision stability visualization"""
        plt.figure(figsize=vis_config['figure_size_large'])
        ensemble_gdf.plot(
            column='stability',
            cmap='RdYlGn',
            legend=True,
            legend_kwds={'label': 'Decision Stability Across Runs'},
            ax=plt.gca(),
            edgecolor=None,
            alpha=vis_config['alpha']
        )
        plt.title(f'Ensemble Results: Decision Stability Across {self.config["model"]["num_runs"]} Runs', fontsize=16)
        plt.axis('equal')
        plt.tight_layout()
        
        output_path = os.path.join(
            self.config['paths']['figures_dir'],
            self.config['output']['stability_map']
        )
        plt.savefig(output_path, dpi=vis_config['dpi'], bbox_inches='tight')
        plt.show()
    
    def generate_distinct_colors(self, n):
        """Generate distinct colors for visualization"""
        np.random.seed(self.config['model']['random_seed'])
        random.seed(self.config['model']['random_seed'])
        
        hsv_colors = []
        for i in range(n):
            h = i / n
            s = 0.7 + 0.3 * random.random()
            v = 0.8 + 0.2 * random.random()
            hsv_colors.append((h, s, v))
        
        rgb_colors = [colorsys.hsv_to_rgb(*color) for color in hsv_colors]
        return rgb_colors
    
    def run_complete_analysis(self):
        """Run the complete model analysis pipeline"""
        start_time = time.time()
        
        print("=== Hennepin County Heat Risk ABM Model ===")
        print("Starting complete ensemble analysis...")
        
        # Run ensemble simulation
        self.run_ensemble_simulation()
        
        # Analyze results
        avg_results = self.analyze_ensemble_results()
        
        # Create ensemble GeoDataFrame
        ensemble_gdf = self.create_ensemble_geodataframe()
        
        # Save results
        self.save_results(ensemble_gdf)
        
        # Create visualizations
        self.create_visualizations(ensemble_gdf)
        
        # Final summary
        elapsed_time = time.time() - start_time
        print(f"\n=== Analysis Complete ===")
        print(f"Total runtime: {elapsed_time:.1f} seconds")
        print(f"Results saved to: {self.config['paths']['output_dir']}")
        print(f"Visualizations saved to: {self.config['paths']['figures_dir']}")


def main():
    """Main function to run the heat risk model"""
    # Check if config file exists
    config_path = "config/config.yaml"
    if not os.path.exists(config_path):
        print(f"Configuration file not found: {config_path}")
        print("Please create the configuration file first.")
        sys.exit(1)
    
    # Create and run the model
    try:
        model_runner = HeatRiskModelRunner(config_path)
        model_runner.run_complete_analysis()
    except KeyboardInterrupt:
        print("\nAnalysis interrupted by user")
    except Exception as e:
        print(f"Error running analysis: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()