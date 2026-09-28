#!/usr/bin/env python3
"""
Heat Risk Model Validation Study
Compares simulated cooling center visits from ensemble results against real visitation data

Usage: python run_validation_study.py [--trial TRIAL_FOLDER]

Author: Project contributors
Date: 2025
"""

import os
import sys
import argparse
import pandas as pd
import geopandas as gpd
import numpy as np
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Constants
HENNEPIN_POPULATION_2020 = 1281565  # From census data


class CoolingCenterValidation:
    def __init__(self, trial_folder=None):
        """Initialize validation study"""
        # Set working directory to script location
        self.code_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(self.code_dir)
        print(f"Working directory: {os.getcwd()}")
        
        # Paths using relative paths
        self.base_path = Path("../..")
        self.output_results_path = self.base_path / "output/results"
        self.output_validate_path = self.base_path / "output/validate"
        self.data_path = self.base_path / "data/validate_data/intermediate"
        
        # Create output directory if needed
        self.output_validate_path.mkdir(parents=True, exist_ok=True)
        
        # Find or set trial folder
        self.trial_folder = self._get_trial_folder(trial_folder)
        self.trial_path = self.output_results_path / self.trial_folder
        
        print(f"Using trial folder: {self.trial_folder}")
        
    def _get_trial_folder(self, specified_trial=None):
        """Get trial folder - either specified or most recent"""
        if specified_trial:
            return specified_trial
            
        # Find most recent trial folder
        print("Finding most recent trial folder...")
        
        if not self.output_results_path.exists():
            raise FileNotFoundError(f"Results directory not found: {self.output_results_path}")
            
        # Get all trial folders
        trial_folders = [d for d in self.output_results_path.iterdir() 
                        if d.is_dir() and d.name.startswith("trial_")]
        
        if not trial_folders:
            raise ValueError("No trial folders found in results directory")
            
        # Sort by timestamp in folder name
        trial_folders.sort(key=lambda x: x.name.split("_")[1])
        most_recent = trial_folders[-1].name
        
        print(f"Found {len(trial_folders)} trial folders")
        print(f"Most recent: {most_recent}")
        
        return most_recent
        
    def load_validation_data(self):
        """Load real visitation data"""
        print("\nLoading validation data...")
        
        # Load real visits
        real_visits_file = self.data_path / "validate_cooling_summer_2024.csv"
        self.real_visits_df = pd.read_csv(real_visits_file)
        self.real_visits_df['date'] = pd.to_datetime(self.real_visits_df['date'])
        
        # Load cooling centers
        cooling_centers_file = self.data_path / "cooling_center.csv"
        self.cooling_centers_df = pd.read_csv(cooling_centers_file)
        
        # Get validated centers only
        self.validated_centers = self.cooling_centers_df[
            self.cooling_centers_df['validate_tag'] == 1
        ].copy()
        
        print(f"✓ Loaded {len(self.real_visits_df)} days of real visitation data")
        print(f"✓ Found {len(self.validated_centers)} validated cooling centers")
        
        return True
        
    def create_name_mapping(self):
        """Create mapping between CSV columns and cooling center names"""
        print("\nCreating name mapping...")
        
        self.column_to_center = {}
        self.center_to_column = {}
        
        # Get visit columns (exclude 'date')
        visit_columns = [col for col in self.real_visits_df.columns if col != 'date']
        
        # Create mappings for each validated center
        for _, center in self.validated_centers.iterrows():
            center_name = center['name']
            
            # Try to find matching column
            for col in visit_columns:
                # Create comparable names
                col_clean = col.replace('_visits', '').replace('_', ' ').lower()
                center_clean = center_name.lower()
                
                # Check for matches
                if col_clean in center_clean or center_clean in col_clean:
                    self.column_to_center[col] = center_name
                    self.center_to_column[center_name] = col
                    break
                    
                # Special cases
                if 'swim' in col and 'regional park' in center_clean.lower():
                    if 'elm creek' in col and 'elm creek' in center_clean:
                        self.column_to_center[col] = center_name
                        self.center_to_column[center_name] = col
                        break
                    elif 'minnetonka' in col and 'minnetonka' in center_clean:
                        self.column_to_center[col] = center_name
                        self.center_to_column[center_name] = col
                        break
                        
        print(f"✓ Mapped {len(self.column_to_center)} columns to cooling centers")
        
        # Print unmapped centers for debugging
        mapped_centers = set(self.center_to_column.keys())
        all_validated_centers = set(self.validated_centers['name'])
        unmapped = all_validated_centers - mapped_centers
        
        if unmapped:
            print(f"⚠ Warning: {len(unmapped)} validated centers not mapped to columns:")
            for center in list(unmapped)[:5]:
                print(f"  - {center}")
                
        return self.column_to_center
        
    def get_available_dates(self):
        """Get list of dates with ensemble results"""
        print("\nFinding available ensemble results...")
        
        available_dates = []
        
        # Check each subdirectory in trial folder
        for date_dir in self.trial_path.iterdir():
            if date_dir.is_dir() and date_dir.name.isdigit():
                # Check for ensemble DBF file
                ensemble_dbf = date_dir / f"ensemble_{date_dir.name}.dbf"
                if ensemble_dbf.exists():
                    available_dates.append(date_dir.name)
                    
        available_dates.sort()
        print(f"✓ Found ensemble results for {len(available_dates)} dates")
        
        return available_dates
        
    def count_visits_from_ensemble(self, date_str):
        """Count visits to validated centers from ensemble DBF"""
        # Read ensemble shapefile
        ensemble_path = self.trial_path / date_str / f"ensemble_{date_str}.shp"
        
        if not ensemble_path.exists():
            print(f"⚠ Warning: Ensemble file not found for {date_str}")
            return None
            
        # Read the shapefile
        ensemble_gdf = gpd.read_file(ensemble_path)
        
        # Get parcels that moved to cooling centers
        moved_parcels = ensemble_gdf[ensemble_gdf['decision'] == 'move'].copy()
        
        # Count visits per cooling center
        visit_counts = {}
        
        for center_name in self.validated_centers['name']:
            # Count how many parcels went to this center
            visits = (moved_parcels['cool_centr'] == center_name).sum()
            visit_counts[center_name] = visits
            
        # Also get total parcel count for ratio calculation
        total_parcels = len(ensemble_gdf)
        
        return visit_counts, total_parcels
        
    def process_all_dates(self):
        """Process all available dates and create validation dataset"""
        print("\nProcessing ensemble results...")
        
        available_dates = self.get_available_dates()
        
        # Convert date strings to datetime for matching
        available_datetimes = [pd.to_datetime(d, format='%Y%m%d') for d in available_dates]
        
        # Filter real visits to matching dates
        real_visits_filtered = self.real_visits_df[
            self.real_visits_df['date'].isin(available_datetimes)
        ].copy()
        
        print(f"✓ Matched {len(real_visits_filtered)} dates between real and simulated data")
        
        # Initialize results dataframe
        results_data = []
        
        # Process each date
        for idx, row in real_visits_filtered.iterrows():
            date = row['date']
            date_str = date.strftime('%Y%m%d')
            
            print(f"  Processing {date_str}...", end='')
            
            # Get simulated visits
            sim_results = self.count_visits_from_ensemble(date_str)
            
            if sim_results is None:
                print(" skipped (no ensemble data)")
                continue
                
            visit_counts, total_parcels = sim_results
            
            # Create row for this date
            result_row = {'date': date}
            
            # Add data for each validated center
            for center_name in self.validated_centers['name']:
                # Get column name for this center
                col_name = self.center_to_column.get(center_name)
                
                if col_name:
                    # Real visits
                    real_visits = row.get(col_name, 0)
                    if pd.isna(real_visits):
                        real_visits = 0
                        
                    # Simulated visits
                    sim_visits = visit_counts.get(center_name, 0)
                    
                    # Calculate ratios
                    real_ratio = real_visits / HENNEPIN_POPULATION_2020
                    sim_ratio = sim_visits / total_parcels if total_parcels > 0 else 0
                    
                    # Add to result row
                    base_name = col_name.replace('_visits', '')
                    result_row[f"{base_name}_visits"] = real_visits
                    result_row[f"{base_name}_visits_ratio"] = real_ratio
                    result_row[f"{base_name}_sim_visits"] = sim_visits
                    result_row[f"{base_name}_sim_visit_ratio"] = sim_ratio
                    
            results_data.append(result_row)
            print(" done")
            
        # Create final dataframe
        self.validation_results = pd.DataFrame(results_data)
        
        # Sort columns: date first, then grouped by center
        date_col = ['date']
        other_cols = sorted([col for col in self.validation_results.columns if col != 'date'])
        self.validation_results = self.validation_results[date_col + other_cols]
        
        print(f"\n✓ Created validation dataset with {len(self.validation_results)} dates")
        
        return self.validation_results
        
    def calculate_summary_statistics(self):
        """Calculate summary statistics for validation"""
        print("\nCalculating summary statistics...")
        
        # Get all visit columns
        visit_cols = [col for col in self.validation_results.columns 
                     if col.endswith('_visits') and not col.endswith('_sim_visits')]
        
        stats = []
        
        for base_col in visit_cols:
            base_name = base_col.replace('_visits', '')
            
            # Use ratio columns for comparison
            real_ratio_col = f"{base_name}_visits_ratio"
            sim_ratio_col = f"{base_name}_sim_visit_ratio"
            
            # Also get raw counts for reference
            real_visits_col = f"{base_name}_visits"
            sim_visits_col = f"{base_name}_sim_visits"
            
            if all(col in self.validation_results for col in [real_ratio_col, sim_ratio_col, real_visits_col, sim_visits_col]):
                real_ratios = self.validation_results[real_ratio_col]
                sim_ratios = self.validation_results[sim_ratio_col]
                real_visits = self.validation_results[real_visits_col]
                sim_visits = self.validation_results[sim_visits_col]
                
                # Filter out zeros for correlation (using ratios)
                mask = (real_ratios > 0) | (sim_ratios > 0)
                
                stat_row = {
                    'cooling_center': base_name,
                    'mean_real_visits': real_visits.mean(),
                    'mean_sim_visits': sim_visits.mean(),
                    'mean_real_ratio': real_ratios.mean(),
                    'mean_sim_ratio': sim_ratios.mean(),
                    'correlation': real_ratios[mask].corr(sim_ratios[mask]) if mask.sum() > 1 else np.nan,
                    'mae_ratio': np.abs(real_ratios - sim_ratios).mean(),
                    'rmse_ratio': np.sqrt(((real_ratios - sim_ratios) ** 2).mean()),
                    'relative_error': (sim_ratios.mean() - real_ratios.mean()) / real_ratios.mean() if real_ratios.mean() > 0 else np.nan,
                    'n_days': len(real_ratios)
                }
                
                stats.append(stat_row)
                
        self.summary_stats = pd.DataFrame(stats)
        
        # Print summary
        print("\nValidation Summary:")
        print(f"Overall correlation (using ratios): {self.summary_stats['correlation'].mean():.3f}")
        print(f"Average MAE (ratio): {self.summary_stats['mae_ratio'].mean():.6f}")
        print(f"Average RMSE (ratio): {self.summary_stats['rmse_ratio'].mean():.6f}")
        print(f"Average relative error: {self.summary_stats['relative_error'].mean():.1%}")
        
        # Also show scale difference
        total_real_visits = self.summary_stats['mean_real_visits'].sum()
        total_sim_visits = self.summary_stats['mean_sim_visits'].sum()
        print(f"\nScale comparison:")
        print(f"Total mean real visits per day: {total_real_visits:.0f}")
        print(f"Total mean simulated visits per day: {total_sim_visits:.0f}")
        print(f"Scaling factor: {total_real_visits/total_sim_visits:.2f}x")
        
        return self.summary_stats
        
    def save_results(self):
        """Save validation results"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save main validation data
        validation_file = self.output_validate_path / f"validation_comparison_{timestamp}.csv"
        self.validation_results.to_csv(validation_file, index=False)
        print(f"\n✓ Saved validation results to: {validation_file}")
        
        # Save summary statistics
        stats_file = self.output_validate_path / f"validation_statistics_{timestamp}.csv"
        self.summary_stats.to_csv(stats_file, index=False)
        print(f"✓ Saved summary statistics to: {stats_file}")
        
        # Create summary report
        report_file = self.output_validate_path / f"validation_report_{timestamp}.txt"
        
        with open(report_file, 'w') as f:
            f.write(f"HEAT RISK MODEL VALIDATION REPORT\n")
            f.write(f"{'='*60}\n")
            f.write(f"Generated: {datetime.now()}\n")
            f.write(f"Trial folder: {self.trial_folder}\n")
            f.write(f"Dates analyzed: {len(self.validation_results)}\n\n")
            
            f.write(f"OVERALL METRICS:\n")
            f.write(f"- Average correlation (ratios): {self.summary_stats['correlation'].mean():.3f}\n")
            f.write(f"- Average MAE (ratio): {self.summary_stats['mae_ratio'].mean():.6f}\n")
            f.write(f"- Average RMSE (ratio): {self.summary_stats['rmse_ratio'].mean():.6f}\n")
            f.write(f"- Average relative error: {self.summary_stats['relative_error'].mean():.1%}\n")
            f.write(f"- Total mean real visits/day: {self.summary_stats['mean_real_visits'].sum():.0f}\n")
            f.write(f"- Total mean sim visits/day: {self.summary_stats['mean_sim_visits'].sum():.0f}\n\n")
            
            f.write(f"TOP 5 BEST CORRELATIONS:\n")
            best = self.summary_stats.nlargest(5, 'correlation')
            for _, row in best.iterrows():
                f.write(f"- {row['cooling_center']}: r={row['correlation']:.3f}\n")
                
            f.write(f"\nTOP 5 LARGEST ERRORS (MAE ratio):\n")
            worst = self.summary_stats.nlargest(5, 'mae_ratio')
            for _, row in worst.iterrows():
                f.write(f"- {row['cooling_center']}: MAE={row['mae_ratio']:.6f}\n")
                
            f.write(f"\nMOST OVERESTIMATED (relative error):\n")
            overest = self.summary_stats.nlargest(5, 'relative_error')
            for _, row in overest.iterrows():
                f.write(f"- {row['cooling_center']}: {row['relative_error']:.1%} higher than real\n")
                
            f.write(f"\nMOST UNDERESTIMATED (relative error):\n")
            underest = self.summary_stats.nsmallest(5, 'relative_error')
            for _, row in underest.iterrows():
                f.write(f"- {row['cooling_center']}: {row['relative_error']:.1%} lower than real\n")
                
        print(f"✓ Saved validation report to: {report_file}")
        
        return validation_file


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description='Run validation study comparing simulated vs real cooling center visits'
    )
    parser.add_argument(
        '--trial', 
        type=str, 
        help='Specific trial folder to use (default: most recent)'
    )
    
    args = parser.parse_args()
    
    print("🌡️  HEAT RISK MODEL VALIDATION STUDY")
    print("="*60)
    
    try:
        # Initialize validator
        validator = CoolingCenterValidation(trial_folder=args.trial)
        
        # Load data
        validator.load_validation_data()
        
        # Create name mapping
        validator.create_name_mapping()
        
        # Process all dates
        validation_results = validator.process_all_dates()
        
        if len(validation_results) == 0:
            print("\n❌ No matching dates found between real and simulated data")
            return
            
        # Calculate statistics
        validator.calculate_summary_statistics()
        
        # Save results
        output_file = validator.save_results()
        
        print("\n✅ Validation study complete!")
        print(f"📊 Results saved to: {validator.output_validate_path}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    return 0


if __name__ == "__main__":
    sys.exit(main())