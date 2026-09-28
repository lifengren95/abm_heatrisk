#!/usr/bin/env python3
"""
Heat Risk Model Validation Study - Heat vs Non-Heat Comparison
Compares the relative increase in cooling center visits during heat events vs normal days

Usage: python run_validation_heat_vs_nonheat.py [--trial TRIAL_FOLDER]

Author: Project contributors
Date: 2025
"""

import os
import sys
import argparse
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


class CoolingCenterHeatValidation:
    def __init__(self, trial_folder=None, validation_config=None):
        """Initialize validation study with heat vs non-heat approach"""
        # Set working directory to script location
        self.code_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(self.code_dir)
        print(f"Working directory: {os.getcwd()}")
        
        # Store validation configuration
        self.validation_config = validation_config
        self.validation_year = validation_config['validation_year']
        self.heat_dates = [pd.to_datetime(d) for d in validation_config['heat_dates']]
        self.validation_datasource = validation_config['validation_datasource']
        
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
        
        # Create validation output directory for this trial
        self.trial_validate_path = self.output_validate_path / self.trial_folder
        self.trial_validate_path.mkdir(parents=True, exist_ok=True)
        
        print(f"Using trial folder: {self.trial_folder}")
        print(f"Validation year: {self.validation_year}")
        print(f"Number of heat dates: {len(self.heat_dates)}")
        
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
        """Load real cooling center visit data"""
        print("\nLoading validation data...")
        
        # Load real visits data using configured datasource
        self.real_visits_file = self.data_path / self.validation_datasource
        
        if not self.real_visits_file.exists():
            raise FileNotFoundError(f"Validation data not found: {self.real_visits_file}")
            
        self.real_visits_df = pd.read_csv(self.real_visits_file)
        self.real_visits_df['date'] = pd.to_datetime(self.real_visits_df['date'])
        
        # Filter to validation year only
        self.real_visits_df = self.real_visits_df[
            self.real_visits_df['date'].dt.year == int(self.validation_year)
        ]
        
        print(f"✓ Loaded real visits data: {len(self.real_visits_df)} days in {self.validation_year}")
        
        # Load cooling center definitions
        cooling_centers_file = self.data_path / "cooling_center.csv"
        if not cooling_centers_file.exists():
            raise FileNotFoundError(f"Cooling centers file not found: {cooling_centers_file}")
            
        self.cooling_centers = pd.read_csv(cooling_centers_file)
        
        # Filter to validated centers only
        self.cooling_centers = self.cooling_centers[self.cooling_centers['validate_tag'] == 1].copy()
        print(f"✓ Loaded {len(self.cooling_centers)} validated cooling centers")
        
    def get_available_dates(self):
        """Get list of dates with ensemble results"""
        print("\nFinding available ensemble results...")
        
        available_dates = []
        
        # Check each subdirectory in trial folder
        for date_dir in self.trial_path.iterdir():
            if date_dir.is_dir() and date_dir.name.isdigit() and len(date_dir.name) == 8:
                # Check for ensemble CSV file
                ensemble_csv = date_dir / f"ensemble_summary_{date_dir.name}.csv"
                if ensemble_csv.exists():
                    # Convert to datetime and check if in validation year
                    date = pd.to_datetime(date_dir.name, format='%Y%m%d')
                    if date.year == int(self.validation_year):
                        available_dates.append(date)
                        
        available_dates.sort()
        print(f"✓ Found ensemble results for {len(available_dates)} dates in {self.validation_year}")
        
        return available_dates
        
    def create_name_mapping(self):
        """Create mapping between cooling center names and column names"""
        print("\nCreating name mapping...")
        
        # Get column names that end with '_visits'
        visit_columns = [col for col in self.real_visits_df.columns if col.endswith('_visits')]
        
        # Create mapping
        self.center_to_column = {}
        
        for center_name in self.cooling_centers['name']:
            # Clean center name
            center_clean = center_name.lower().strip()
            
            # Find best matching column
            best_match = None
            best_score = 0
            
            for col in visit_columns:
                col_clean = col.replace('_visits', '').replace('_', ' ').lower()
                
                # Check for matches
                if col_clean in center_clean or center_clean in col_clean:
                    best_match = col
                    best_score = 1.0
                    break
                    
                # Special cases for swim centers
                if 'swim' in col and 'regional park' in center_clean:
                    if 'elm creek' in col and 'elm creek' in center_clean:
                        best_match = col
                        break
                    elif 'minnetonka' in col and 'minnetonka' in center_clean:
                        best_match = col
                        break
                        
                # Calculate similarity score for partial matches
                center_words = set(center_clean.split())
                col_words = set(col_clean.split())
                common_words = center_words.intersection(col_words)
                if len(common_words) > 0:
                    score = len(common_words) / max(len(center_words), len(col_words))
                    if score > best_score:
                        best_score = score
                        best_match = col
                        
            if best_match and best_score > 0.5:
                self.center_to_column[center_name] = best_match
                
        print(f"✓ Created mapping for {len(self.center_to_column)} centers")
        
        # Print unmapped centers for debugging
        mapped_centers = set(self.center_to_column.keys())
        all_validated_centers = set(self.cooling_centers['name'])
        unmapped = all_validated_centers - mapped_centers
        
        if unmapped:
            print(f"⚠ Warning: {len(unmapped)} validated centers not mapped to columns:")
            for center in list(unmapped)[:5]:
                print(f"  - {center}")
                
        # Store visit columns for overall calculations
        self.visit_columns = visit_columns
                
    def count_visits_from_ensemble(self, date):
        """Count visits to validated centers from ensemble CSV"""
        date_str = date.strftime('%Y%m%d')
        
        # Read ensemble CSV file
        ensemble_csv = self.trial_path / date_str / f"ensemble_summary_{date_str}.csv"
        
        if not ensemble_csv.exists():
            print(f"⚠ Warning: Ensemble CSV not found for {date_str}")
            return None
            
        # Read CSV
        try:
            ensemble_df = pd.read_csv(ensemble_csv)
        except Exception as e:
            print(f"⚠ Warning: Could not read ensemble CSV for {date_str}: {e}")
            return None
            
        # Get parcels that moved to cooling centers
        moved_parcels = ensemble_df[ensemble_df['decision_majority'] == 'move'].copy()
        
        # Count visits per cooling center
        visit_counts = {}
        
        for center_name in self.cooling_centers['name']:
            # Count how many parcels went to this center
            visits = (moved_parcels['cooling_center'] == center_name).sum()
            visit_counts[center_name] = visits
            
        # Also get total parcel count for ratio calculation
        total_parcels = len(ensemble_df)
        
        return visit_counts, total_parcels
        
    def separate_heat_nonheat_dates(self):
        """Separate dates into heat and non-heat categories"""
        print("\nSeparating heat and non-heat dates...")
        
        # Get all available dates from ensemble results
        self.available_dates = self.get_available_dates()
        
        # Separate into heat and non-heat
        heat_dates_set = set(self.heat_dates)
        
        self.available_heat_dates = [d for d in self.available_dates if d in heat_dates_set]
        self.available_nonheat_dates = [d for d in self.available_dates if d not in heat_dates_set]
        
        print(f"✓ Available heat dates with ensemble data: {len(self.available_heat_dates)}")
        print(f"✓ Available non-heat dates with ensemble data: {len(self.available_nonheat_dates)}")
        
        # Print heat dates for verification
        if self.available_heat_dates:
            print("\nAvailable heat dates with ensemble data:")
            for d in sorted(self.available_heat_dates):
                print(f"  - {d.strftime('%Y-%m-%d')}")
        else:
            print("\n⚠ Warning: No heat dates found in ensemble results!")
            
        # Check if all configured heat dates have data
        missing_heat_dates = set(self.heat_dates) - set(self.available_heat_dates)
        if missing_heat_dates:
            print("\n⚠ Warning: Some heat dates missing from ensemble results:")
            for d in sorted(missing_heat_dates):
                print(f"  - {d.strftime('%Y-%m-%d')}")
                
    def calculate_overall_statistics(self):
        """Calculate overall heat vs non-heat statistics across all centers"""
        print("\nCalculating overall system heat response...")
        
        # === REAL DATA - Overall ===
        # Get heat and non-heat masks
        heat_mask = self.real_visits_df['date'].isin(self.heat_dates)
        nonheat_mask = ~heat_mask & (self.real_visits_df['date'].dt.year == int(self.validation_year))
        
        # Sum all visits across all centers for each day
        real_heat_daily_totals = self.real_visits_df.loc[heat_mask, self.visit_columns].sum(axis=1)
        real_nonheat_daily_totals = self.real_visits_df.loc[nonheat_mask, self.visit_columns].sum(axis=1)
        
        # Calculate averages
        real_heat_total_avg = real_heat_daily_totals.mean() if len(real_heat_daily_totals) > 0 else 0
        real_nonheat_total_avg = real_nonheat_daily_totals.mean() if len(real_nonheat_daily_totals) > 0 else 0
        
        # Calculate overall ratio
        if real_nonheat_total_avg > 0:
            real_overall_ratio = (real_heat_total_avg - real_nonheat_total_avg) / real_nonheat_total_avg
        else:
            real_overall_ratio = 0
            
        # === SIMULATED DATA - Overall ===
        sim_heat_totals = []
        sim_nonheat_totals = []
        
        # Process heat dates
        for date in self.available_heat_dates:
            result = self.count_visits_from_ensemble(date)
            if result:
                visit_counts, _ = result
                daily_total = sum(visit_counts.values())
                sim_heat_totals.append(daily_total)
        
        # Process non-heat dates
        for date in self.available_nonheat_dates:
            result = self.count_visits_from_ensemble(date)
            if result:
                visit_counts, _ = result
                daily_total = sum(visit_counts.values())
                sim_nonheat_totals.append(daily_total)
        
        # Calculate averages
        sim_heat_avg = np.mean(sim_heat_totals) if sim_heat_totals else 0
        sim_nonheat_avg = np.mean(sim_nonheat_totals) if sim_nonheat_totals else 0
        
        # Calculate overall ratio
        if sim_nonheat_avg > 0:
            sim_overall_ratio = (sim_heat_avg - sim_nonheat_avg) / sim_nonheat_avg
        else:
            sim_overall_ratio = 0
            
        # Store overall statistics
        self.overall_stats = {
            'cooling_option': 'Overall',
            'year': self.validation_year,
            'real_heat_visits': real_heat_total_avg,
            'real_nonheat_visits': real_nonheat_total_avg,
            'sim_heat_visits': sim_heat_avg,
            'sim_nonheat_visits': sim_nonheat_avg,
            'real_heat_nonheat_ratio': real_overall_ratio,
            'sim_heat_nonheat_ratio': sim_overall_ratio,
            'mae_ratio': abs(real_overall_ratio - sim_overall_ratio),
            'relative_error': (sim_overall_ratio - real_overall_ratio) / real_overall_ratio if real_overall_ratio != 0 else np.nan,
            'n_heat_days': len(self.available_heat_dates),
            'n_nonheat_days': len(self.available_nonheat_dates)
        }
        
        print(f"Real data: {real_overall_ratio:.1%} increase during heat events")
        print(f"Simulated: {sim_overall_ratio:.1%} increase during heat events")
        
        return self.overall_stats
        
    def calculate_heat_nonheat_ratios(self):
        """Calculate heat vs non-heat ratios for each cooling center"""
        print("\nCalculating heat vs non-heat ratios...")
        
        # First separate dates
        self.separate_heat_nonheat_dates()
        
        # Check if we have data for both heat and non-heat periods
        if len(self.available_heat_dates) == 0:
            raise ValueError("No heat dates found in ensemble results!")
        if len(self.available_nonheat_dates) == 0:
            raise ValueError("No non-heat dates found in ensemble results!")
        
        # Calculate overall statistics first
        overall_stats = self.calculate_overall_statistics()
        
        # Start timing
        import time
        start_time = time.time()
        
        # Initialize results with overall statistics
        results_data = [overall_stats]
        
        # Process each cooling center
        print("\nCalculating individual center heat responses...")
        total_centers = len(self.cooling_centers)
        
        for idx, center_row in self.cooling_centers.iterrows():
            center_name = center_row['name']
            col_name = self.center_to_column.get(center_name)
            
            # Show progress
            print(f"\r  Processing center {idx+1}/{total_centers}: {center_name[:30]}...", end='', flush=True)
            
            if col_name:
                # === REAL DATA CALCULATIONS ===
                # Heat visits
                heat_mask = self.real_visits_df['date'].isin(self.heat_dates)
                heat_visits_series = self.real_visits_df.loc[heat_mask, col_name]
                real_heat_visits_avg = heat_visits_series.mean() if len(heat_visits_series) > 0 else 0
                
                # Non-heat visits
                nonheat_mask = ~heat_mask & (self.real_visits_df['date'].dt.year == int(self.validation_year))
                nonheat_visits_series = self.real_visits_df.loc[nonheat_mask, col_name]
                real_nonheat_visits_avg = nonheat_visits_series.mean() if len(nonheat_visits_series) > 0 else 0
                
                # Real heat vs non-heat ratio
                if real_nonheat_visits_avg > 0:
                    real_heat_nonheat_ratio = (real_heat_visits_avg - real_nonheat_visits_avg) / real_nonheat_visits_avg
                else:
                    real_heat_nonheat_ratio = 0
                    
                # === SIMULATED DATA CALCULATIONS ===
                sim_heat_visits = []
                sim_nonheat_visits = []
                
                # Collect visits from heat dates
                for date in self.available_heat_dates:
                    result = self.count_visits_from_ensemble(date)
                    if result:
                        visit_counts, total_parcels = result
                        sim_heat_visits.append(visit_counts.get(center_name, 0))
                        
                # Collect visits from non-heat dates
                for date in self.available_nonheat_dates:
                    result = self.count_visits_from_ensemble(date)
                    if result:
                        visit_counts, total_parcels = result
                        sim_nonheat_visits.append(visit_counts.get(center_name, 0))
                        
                # Calculate averages
                sim_heat_visits_avg = np.mean(sim_heat_visits) if sim_heat_visits else 0
                sim_nonheat_visits_avg = np.mean(sim_nonheat_visits) if sim_nonheat_visits else 0
                
                # Simulated heat vs non-heat ratio
                if sim_nonheat_visits_avg > 0:
                    sim_heat_nonheat_ratio = (sim_heat_visits_avg - sim_nonheat_visits_avg) / sim_nonheat_visits_avg
                else:
                    sim_heat_nonheat_ratio = 0
                    
                # Store results
                result_row = {
                    'cooling_option': center_name,
                    'year': self.validation_year,
                    'real_heat_visits': real_heat_visits_avg,
                    'real_nonheat_visits': real_nonheat_visits_avg,
                    'sim_heat_visits': sim_heat_visits_avg,
                    'sim_nonheat_visits': sim_nonheat_visits_avg,
                    'real_heat_nonheat_ratio': real_heat_nonheat_ratio,
                    'sim_heat_nonheat_ratio': sim_heat_nonheat_ratio,
                    'mae_ratio': abs(real_heat_nonheat_ratio - sim_heat_nonheat_ratio),
                    'relative_error': (sim_heat_nonheat_ratio - real_heat_nonheat_ratio) / real_heat_nonheat_ratio if real_heat_nonheat_ratio != 0 else np.nan,
                    'n_heat_days': len(sim_heat_visits),
                    'n_nonheat_days': len(sim_nonheat_visits)
                }
                
                results_data.append(result_row)
                
        # Clear the progress line
        print("\r" + " " * 80 + "\r", end='', flush=True)
        
        # Create dataframe
        self.validation_results = pd.DataFrame(results_data)
        
        # Report timing
        elapsed_time = time.time() - start_time
        print(f"✓ Calculated ratios for {len(self.validation_results)-1} centers (plus overall)")
        print(f"  Processing time: {elapsed_time:.1f} seconds ({elapsed_time/60:.1f} minutes)")
        
        return self.validation_results
        
    def calculate_summary_statistics(self):
        """Calculate summary statistics from validation results"""
        print("\nCalculating summary statistics...")
        
        # Filter to individual centers only (exclude overall)
        center_stats = self.validation_results[self.validation_results['cooling_option'] != 'Overall'].copy()
        
        # Calculate correlation
        valid_mask = ~(center_stats['real_heat_nonheat_ratio'].isna() | 
                      center_stats['sim_heat_nonheat_ratio'].isna())
        
        if valid_mask.sum() > 1:
            overall_correlation = center_stats.loc[valid_mask, 'real_heat_nonheat_ratio'].corr(
                center_stats.loc[valid_mask, 'sim_heat_nonheat_ratio']
            )
        else:
            overall_correlation = np.nan
            
        # Print summary
        print("\nHeat vs Non-Heat Validation Summary:")
        print(f"Overall correlation: {overall_correlation:.3f}")
        print(f"Average MAE (ratio): {center_stats['mae_ratio'].mean():.3f}")
        
        # Filter out invalid relative errors for the mean
        valid_rel_errors = center_stats['relative_error'].dropna()
        if len(valid_rel_errors) > 0:
            print(f"Average relative error: {valid_rel_errors.mean():.1%}")
        
        # Show average heat response
        avg_real_increase = center_stats['real_heat_nonheat_ratio'].mean()
        avg_sim_increase = center_stats['sim_heat_nonheat_ratio'].mean()
        print(f"\nAverage heat response (centers):")
        print(f"Real data: {avg_real_increase:.1%} increase during heat events")
        print(f"Simulated: {avg_sim_increase:.1%} increase during heat events")
        
        # Store correlation for report
        self.overall_correlation = overall_correlation
        
        return center_stats
        
    def save_results(self):
        """Save validation results"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save comprehensive CSV to trial validation folder
        output_csv = self.trial_validate_path / f"heat_nonheat_validation_{self.validation_year}_{timestamp}.csv"
        
        # Add correlation as a column for all rows
        self.validation_results['correlation'] = self.overall_correlation
        
        # Reorder columns for clarity
        column_order = [
            'cooling_option', 'year', 
            'real_heat_visits', 'real_nonheat_visits',
            'sim_heat_visits', 'sim_nonheat_visits',
            'real_heat_nonheat_ratio', 'sim_heat_nonheat_ratio',
            'mae_ratio', 'relative_error', 'correlation',
            'n_heat_days', 'n_nonheat_days'
        ]
        
        # Save CSV
        self.validation_results[column_order].to_csv(output_csv, index=False, float_format='%.6f')
        print(f"\n✓ Saved validation results to: {output_csv}")
        
        # Create summary report
        report_file = self.trial_validate_path / f"heat_nonheat_report_{self.validation_year}_{timestamp}.txt"
        
        # Get overall stats row
        overall_row = self.validation_results[self.validation_results['cooling_option'] == 'Overall'].iloc[0]
        
        # Filter out invalid relative errors for the mean
        center_stats = self.validation_results[self.validation_results['cooling_option'] != 'Overall']
        valid_rel_errors = center_stats['relative_error'].dropna()
        avg_rel_error = valid_rel_errors.mean() if len(valid_rel_errors) > 0 else np.nan
        
        with open(report_file, 'w') as f:
            f.write(f"HEAT VS NON-HEAT VALIDATION REPORT\n")
            f.write(f"{'='*60}\n")
            f.write(f"Generated: {datetime.now()}\n")
            f.write(f"Trial folder: {self.trial_folder}\n")
            f.write(f"Validation year: {self.validation_year}\n")
            f.write(f"Validation datasource: {self.validation_datasource}\n\n")
            
            f.write(f"HEAT EVENT DEFINITION:\n")
            f.write(f"Configured heat dates ({len(self.heat_dates)} days):\n")
            for d in sorted(self.heat_dates):
                f.write(f"  - {d.strftime('%Y-%m-%d')}\n")
            f.write(f"\nAvailable heat dates with ensemble data ({len(self.available_heat_dates)} days):\n")
            for d in sorted(self.available_heat_dates):
                f.write(f"  - {d.strftime('%Y-%m-%d')}\n")
            f.write(f"\nNon-heat dates with ensemble data: {len(self.available_nonheat_dates)} days\n\n")
            
            f.write(f"OVERALL SYSTEM HEAT RESPONSE:\n")
            f.write(f"- Total average visits on heat days (real): {overall_row['real_heat_visits']:.1f} visits/day\n")
            f.write(f"- Total average visits on non-heat days (real): {overall_row['real_nonheat_visits']:.1f} visits/day\n")
            f.write(f"- Real overall heat response: {overall_row['real_heat_nonheat_ratio']:.1%} increase\n")
            f.write(f"- Total average visits on heat days (sim): {overall_row['sim_heat_visits']:.1f} visits/day\n")
            f.write(f"- Total average visits on non-heat days (sim): {overall_row['sim_nonheat_visits']:.1f} visits/day\n")
            f.write(f"- Simulated overall heat response: {overall_row['sim_heat_nonheat_ratio']:.1%} increase\n")
            f.write(f"- Difference: {(overall_row['sim_heat_nonheat_ratio'] - overall_row['real_heat_nonheat_ratio']):.1%}\n\n")
            
            f.write(f"INDIVIDUAL CENTER METRICS:\n")
            f.write(f"- Correlation between real and sim ratios: {self.overall_correlation:.3f}\n")
            f.write(f"- Average MAE (ratio): {center_stats['mae_ratio'].mean():.3f}\n")
            if not np.isnan(avg_rel_error):
                f.write(f"- Average relative error: {avg_rel_error:.1%}\n\n")
            else:
                f.write(f"- Average relative error: N/A\n\n")
            
            f.write(f"TOP 5 BEST MATCHING HEAT RESPONSES:\n")
            best = center_stats.nsmallest(5, 'mae_ratio')
            for _, row in best.iterrows():
                f.write(f"- {row['cooling_option']}: ")
                f.write(f"Real={row['real_heat_nonheat_ratio']:.1%}, ")
                f.write(f"Sim={row['sim_heat_nonheat_ratio']:.1%}, ")
                f.write(f"MAE={row['mae_ratio']:.3f}\n")
                
            f.write(f"\nTOP 5 LARGEST HEAT RESPONSE ERRORS:\n")
            worst = center_stats.nlargest(5, 'mae_ratio')
            for _, row in worst.iterrows():
                f.write(f"- {row['cooling_option']}: ")
                f.write(f"Real={row['real_heat_nonheat_ratio']:.1%}, ")
                f.write(f"Sim={row['sim_heat_nonheat_ratio']:.1%}, ")
                f.write(f"MAE={row['mae_ratio']:.3f}\n")
                
        print(f"✓ Saved validation report to: {report_file}")
        
        # Also save a summary of results to the main validate folder
        summary_file = self.output_validate_path / f"heat_nonheat_summary_{self.validation_year}_{self.trial_folder}.csv"
        summary_data = {
            'trial': self.trial_folder,
            'year': self.validation_year,
            'heat_dates': ', '.join([d.strftime('%Y-%m-%d') for d in self.available_heat_dates]),
            'n_heat_days': len(self.available_heat_dates),
            'n_nonheat_days': len(self.available_nonheat_dates),
            'overall_real_ratio': overall_row['real_heat_nonheat_ratio'],
            'overall_sim_ratio': overall_row['sim_heat_nonheat_ratio'],
            'overall_mae': overall_row['mae_ratio'],
            'center_correlation': self.overall_correlation,
            'center_avg_mae': center_stats['mae_ratio'].mean(),
            'center_avg_rel_error': avg_rel_error
        }
        
        pd.DataFrame([summary_data]).to_csv(summary_file, index=False)
        print(f"✓ Saved summary to: {summary_file}")
        
        return output_csv


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description='Run heat vs non-heat validation study for cooling center visits'
    )
    parser.add_argument(
        '--trial', 
        type=str, 
        help='Specific trial folder to use (default: most recent)'
    )
    
    args = parser.parse_args()
    
    # Configuration for validation
    validation_config = {
        'validation_year': '2024',
        'validation_datasource': 'validate_cooling_summer_2024.csv',
        'heat_dates': ['20240826', '20240827'],  # Aug 26, 27, 2024
        # non_heat_dates will be automatically determined
    }
    
    print("🌡️  HEAT VS NON-HEAT VALIDATION STUDY")
    print("="*60)
    print(f"Validation configuration:")
    print(f"  Year: {validation_config['validation_year']}")
    print(f"  Data source: {validation_config['validation_datasource']}")
    print(f"  Heat dates: {', '.join(validation_config['heat_dates'])}")
    print("="*60)
    
    try:
        # Initialize validator
        validator = CoolingCenterHeatValidation(
            trial_folder=args.trial,
            validation_config=validation_config
        )
        
        # Load data
        validator.load_validation_data()
        
        # Create name mapping
        validator.create_name_mapping()
        
        # Calculate heat vs non-heat ratios
        validator.calculate_heat_nonheat_ratios()
        
        # Calculate statistics
        validator.calculate_summary_statistics()
        
        # Save results
        output_file = validator.save_results()
        
        print("\n✅ Heat vs non-heat validation complete!")
        print(f"📊 Results saved to trial validation folder: {validator.trial_validate_path}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    return 0


if __name__ == "__main__":
    sys.exit(main())