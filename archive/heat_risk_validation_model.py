"""
Hennepin County Heat Risk ABM Model - Validation Study
Author: Project contributors
Date: 2025-06-26

This script runs the heat risk model at two temperature levels and tracks
visitation to validated cooling centers (validate_tag == 1).
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
import seaborn as sns

# Progress tracking
from tqdm import tqdm

# Database
import psycopg2
from sqlalchemy import create_engine

# Model imports
sys.path.append('./src')
from src import Parcel, HeatEvent


class ValidationModelRunner:
    """Model runner for validation study with cooling center visitation tracking"""
    
    def __init__(self, config_path="config/config_validation.yaml"):
        """Initialize the validation model runner"""
        self.config = self.load_config(config_path)
        self.setup_environment()
        self.all_gdfs = []
        self.all_results = []
        self.cooling_center_visits = []
        self.validated_centers = None
        
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
        if self.config['processing']['suppress_warnings']:
            warnings.filterwarnings('ignore')
        
        seed = self.config['model']['random_seed']
        np.random.seed(seed)
        random.seed(seed)
        
        code_dir = self.config['paths']['code_dir']
        os.chdir(code_dir)
        print(f"Current working directory: {os.getcwd()}")
        
        self.create_directories()
        self.setup_database_config()
        
        print("✓ Environment setup complete")
    
    def create_directories(self):
        """Create all required directories"""
        paths = self.config['paths']
        
        directories_to_create = [
            paths['output_dir'],
            paths['validation_output_dir'],
            os.path.join('.', paths['results_dir']),
            os.path.join('.', paths['figures_dir'])
        ]
        
        for directory in directories_to_create:
            os.makedirs(directory, exist_ok=True)
            print(f"Created directory: {directory}")
    
    def setup_database_config(self):
        """Set up database configuration"""
        db_config = self.config['database']
        password = os.environ["PGPASSWORD"]  # Using the password from your original config
        
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
    
    def load_validated_cooling_centers(self):
        """Load cooling centers with validate_tag information from database for tracking only
        Note: The simulation itself still uses ALL cooling centers for decision-making"""
        try:
            from src.utils import fetch_data
            
            # Load all cooling centers to verify total count
            query_all = "SELECT COUNT(*) as total_centers FROM cooling_centers;"
            total_centers = fetch_data(query_all)
            
            if total_centers is not None:
                total_count = total_centers.iloc[0]['total_centers']
                print(f"✓ Total cooling centers in database: {total_count}")
            
            # Load only validated centers for tracking visits
            query_validated = """
            SELECT name, id, validate_tag, 
                   ST_X(geom) as x, ST_Y(geom) as y,
                   geom
            FROM cooling_centers
            WHERE validate_tag = 1;
            """
            
            self.validated_centers = fetch_data(query_validated)
            if self.validated_centers is not None:
                print(f"✓ Loaded {len(self.validated_centers)} validated cooling centers for visit tracking")
                print("⚠ Note: Simulation will still use ALL cooling centers for parcel decision-making")
                return True
            else:
                print("✗ Failed to load validated cooling centers")
                return False
                
        except Exception as e:
            print(f"✗ Error loading validated cooling centers: {e}")
            return False
    
    def verify_simulation_uses_all_centers(self, gdf):
        """Verify that the simulation is using all cooling centers, not just validated ones"""
        try:
            # Get unique cooling centers that parcels decided to visit
            moved_parcels = gdf[gdf['decision'] != 'stay']
            
            if len(moved_parcels) > 0:
                unique_centers_visited = moved_parcels['decision'].unique()
                total_centers_visited = len(unique_centers_visited)
                
                # Count how many are validated vs non-validated
                validated_center_names = self.validated_centers['name'].tolist() if self.validated_centers is not None else []
                
                validated_visited = sum(1 for center in unique_centers_visited if center in validated_center_names)
                non_validated_visited = total_centers_visited - validated_visited
                
                print(f"✓ Simulation verification:")
                print(f"  - Total centers visited by parcels: {total_centers_visited}")
                print(f"  - Validated centers visited: {validated_visited}")
                print(f"  - Non-validated centers visited: {non_validated_visited}")
                
                if non_validated_visited > 0:
                    print(f"  ✅ CONFIRMED: Simulation is using ALL cooling centers (not just validated ones)")
                else:
                    print(f"  ⚠ WARNING: Only validated centers were visited - this may indicate an issue")
                    
                return True
            else:
                print("✓ No parcels moved to cooling centers in this simulation")
                return True
                
        except Exception as e:
            print(f"✗ Error verifying simulation: {e}")
            return False

    def count_cooling_center_visits(self, gdf, temperature):
        """Count visits to validated cooling centers"""
        visit_counts = {}
        
        # Count visits to each cooling center
        moved_parcels = gdf[gdf['decision'] != 'stay']
        
        if len(moved_parcels) > 0:
            visit_counts_all = moved_parcels['decision'].value_counts()
            
            # Filter only validated cooling centers
            if self.validated_centers is not None:
                validated_center_names = self.validated_centers['name'].tolist()
                
                for center_name in validated_center_names:
                    visit_counts[center_name] = visit_counts_all.get(center_name, 0)
        
        # Create summary records
        visit_records = []
        if self.validated_centers is not None:
            for _, center in self.validated_centers.iterrows():
                center_name = center['name']
                visits = visit_counts.get(center_name, 0)
                
                visit_records.append({
                    'cooling_center': center_name,
                    'validate_tag': 1,  # All these centers have validate_tag == 1
                    'visitation_simulated': visits,
                    'sim_temp_level': temperature
                })
        
        return visit_records
    
    def run_validation_simulation(self, temperature):
        """Run simulation at a specific temperature level"""
        num_runs = self.config['model']['num_runs']
        
        print(f"Running validation simulation at {temperature}°F...")
        
        all_visit_records = []
        
        if self.config['processing']['show_progress']:
            pbar = tqdm(range(num_runs), desc=f"Runs at {temperature}°F")
        else:
            pbar = range(num_runs)
        
        for run in pbar:
            # Create a new model instance for each run
            heat_event = HeatEvent(temperature)
            
            # Run the simulation with static temperature
            heat_event.run_simulation(temperature=temperature)
            heat_event.process_results()
            
            # Verify simulation uses all centers (only check first run)
            if run == 0:
                self.verify_simulation_uses_all_centers(heat_event.gdf)
            
            # Count visits to validated cooling centers
            visit_records = self.count_cooling_center_visits(heat_event.gdf, temperature)
            all_visit_records.extend(visit_records)
            
            # Store the results
            self.all_gdfs.append(heat_event.gdf.copy())
            
            # Collect summary statistics
            run_results = self.calculate_run_statistics(heat_event.gdf, run + 1, temperature)
            self.all_results.append(run_results)
        
        return all_visit_records
    
    def calculate_run_statistics(self, gdf, run_number, temperature):
        """Calculate statistics for a single run"""
        run_results = {
            'run': run_number,
            'temperature': temperature,
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
    
    def aggregate_visit_data(self, all_visit_records):
        """Aggregate visit data across all runs"""
        visit_df = pd.DataFrame(all_visit_records)
        
        if len(visit_df) > 0:
            # Calculate average visits per cooling center per temperature
            aggregated = visit_df.groupby(['cooling_center', 'sim_temp_level']).agg({
                'visitation_simulated': 'mean',
                'validate_tag': 'first'
            }).reset_index()
            
            # Round to nearest integer
            aggregated['visitation_simulated'] = aggregated['visitation_simulated'].round().astype(int)
        else:
            aggregated = pd.DataFrame(columns=['cooling_center', 'validate_tag', 'visitation_simulated', 'sim_temp_level'])
        
        return aggregated
    
    def save_visit_summary(self, visit_summary):
        """Save cooling center visit summary to CSV"""
        try:
            output_path = os.path.join(
                self.config['paths']['validation_output_dir'],
                self.config['output']['cooling_center_visits']
            )
            
            visit_summary.to_csv(output_path, index=False)
            print(f"✓ Cooling center visit summary saved to: {output_path}")
            
            # Also save to results directory as backup
            backup_path = os.path.join(
                self.config['paths']['results_dir'],
                self.config['output']['cooling_center_visits']
            )
            visit_summary.to_csv(backup_path, index=False)
            
        except Exception as e:
            print(f"✗ Error saving visit summary: {e}")
    
    def print_visit_summary(self, visit_summary):
        """Print summary of cooling center visits"""
        print("\n" + "="*60)
        print("COOLING CENTER VALIDATION VISIT SUMMARY")
        print("="*60)
        
        if len(visit_summary) > 0:
            for temp in visit_summary['sim_temp_level'].unique():
                temp_data = visit_summary[visit_summary['sim_temp_level'] == temp]
                total_visits = temp_data['visitation_simulated'].sum()
                
                print(f"\nTemperature: {temp}°F")
                print(f"Total visits to validated cooling centers: {total_visits}")
                print(f"Number of validated centers with visits: {len(temp_data[temp_data['visitation_simulated'] > 0])}")
                
                if total_visits > 0:
                    print("\nTop 10 visited validated cooling centers:")
                    top_centers = temp_data.nlargest(10, 'visitation_simulated')
                    for _, row in top_centers.iterrows():
                        if row['visitation_simulated'] > 0:
                            print(f"  {row['cooling_center']}: {row['visitation_simulated']} visits")
        else:
            print("No visits recorded to validated cooling centers")
    
    def run_complete_validation_study(self):
        """Run the complete validation study"""
        start_time = time.time()
        
        print("=== Hennepin County Heat Risk Validation Study ===")
        print("Starting validation analysis with cooling center tracking...")
        
        # Load validated cooling centers
        if not self.load_validated_cooling_centers():
            print("Cannot proceed without validated cooling center data")
            return None
        
        all_visit_records = []
        temperatures = self.config['input_data']['static_temperatures']
        
        # Run simulations at both temperature levels
        for temperature in temperatures:
            visit_records = self.run_validation_simulation(temperature)
            all_visit_records.extend(visit_records)
        
        # Aggregate visit data
        visit_summary = self.aggregate_visit_data(all_visit_records)
        
        # Save results
        if self.config['validation']['save_visit_summary']:
            self.save_visit_summary(visit_summary)
        
        # Print summary
        self.print_visit_summary(visit_summary)
        
        # Print overall statistics
        self.print_overall_statistics()
        
        # Final summary
        elapsed_time = time.time() - start_time
        print(f"\n=== Validation Study Complete ===")
        print(f"Total runtime: {elapsed_time:.1f} seconds")
        print(f"Results saved to: {self.config['paths']['validation_output_dir']}")
        
        return visit_summary
    
    def print_overall_statistics(self):
        """Print overall statistics from all runs"""
        if self.all_results:
            results_df = pd.DataFrame(self.all_results)
            
            print("\n" + "="*60)
            print("OVERALL SIMULATION STATISTICS")
            print("="*60)
            
            for temp in results_df['temperature'].unique():
                temp_results = results_df[results_df['temperature'] == temp]
                avg_moved = temp_results['moved_pct'].mean()
                std_moved = temp_results['moved_pct'].std()
                
                print(f"\nTemperature {temp}°F:")
                print(f"  Average % moved to cooling centers: {avg_moved:.2f}% (±{std_moved:.2f}%)")
                print(f"  Number of simulation runs: {len(temp_results)}")


def main():
    """Main function to run the validation study"""
    config_path = "config/config_validation.yaml"
    
    if not os.path.exists(config_path):
        print(f"Configuration file not found: {config_path}")
        print("Please create the validation configuration file first.")
        sys.exit(1)
    
    try:
        model_runner = ValidationModelRunner(config_path)
        visit_summary = model_runner.run_complete_validation_study()
        
        print("\n🎯 Validation study completed successfully!")
        print(f"📊 Visit summary contains {len(visit_summary)} records")
        
    except KeyboardInterrupt:
        print("\nValidation study interrupted by user")
    except Exception as e:
        print(f"Error running validation study: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()