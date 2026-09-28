#!/usr/bin/env python3
"""
Heat Risk Model Validation Study - Cellphone Data Heat vs Non-Heat Comparison
Compares the relative increase in cooling center visits during heat events vs normal days
using cellphone visitation data for July 2020

Usage: python run_validation_cellphone_heat_vs_nonheat.py [--trial TRIAL_FOLDER]

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
import json
import warnings
warnings.filterwarnings('ignore')


class CellphoneDataHeatValidation:
    def __init__(self, trial_folder=None, validation_config=None):
        """Initialize validation study with heat vs non-heat approach for cellphone data"""
        # Store validation configuration
        self.validation_config = validation_config
        self.validation_year = validation_config['validation_year']
        self.validation_month = validation_config['validation_month']
        self.validation_datasource = validation_config['validation_datasource']
        self.data_path = Path(validation_config['data_path'])
        self.simulation_path = Path(validation_config['simulation_path'])
        self.manual_heat_dates = validation_config.get('manual_heat_dates', None)
        
        # Create output directory
        self.output_validate_path = Path(r"~\hennepin\output\validate\cellphone_validate")
        self.output_validate_path.mkdir(parents=True, exist_ok=True)
        
        # Find or set trial folder
        self.trial_folder = self._get_trial_folder(trial_folder)
        
        # Create validation output directory for this trial
        self.trial_validate_path = self.output_validate_path / self.trial_folder
        self.trial_validate_path.mkdir(parents=True, exist_ok=True)
        
        print(f"Cellphone Data Heat Validation Study")
        print(f"Using trial folder: {self.trial_folder}")
        print(f"Validation year: {self.validation_year}")
        print(f"Validation month: {self.validation_month}")
        if self.manual_heat_dates:
            print(f"Using manually specified heat dates: {', '.join(self.manual_heat_dates)}")
        
    def _get_trial_folder(self, specified_trial=None):
        """Get trial folder - either specified or use year-based naming"""
        if specified_trial:
            return specified_trial
        else:
            # For cellphone data, use year-based trial folder
            return f"cellphone_{self.validation_year}_{self.validation_month}"
            
    def load_cellphone_data(self):
        """Load and preprocess cellphone visitation data"""
        print("\nLoading cellphone data...")
        
        # Load cellphone data
        cellphone_file = self.data_path / self.validation_datasource
        
        if not cellphone_file.exists():
            raise FileNotFoundError(f"Cellphone data not found: {cellphone_file}")
            
        # Read CSV
        self.cellphone_df = pd.read_csv(cellphone_file)
        self.cellphone_df['Date'] = pd.to_datetime(self.cellphone_df['Date'])
        
        print(f"✓ Loaded cellphone data: {len(self.cellphone_df)} records")
        print(f"  Date range: {self.cellphone_df['Date'].min().strftime('%Y-%m-%d')} to {self.cellphone_df['Date'].max().strftime('%Y-%m-%d')}")
        
        # Pivot to create date x cooling center matrix
        self.real_visits_df = self.cellphone_df.pivot_table(
            index='Date',
            columns='name',
            values='Visitation',
            aggfunc='sum',
            fill_value=0
        ).reset_index()
        
        # Rename Date to date for consistency
        self.real_visits_df.rename(columns={'Date': 'date'}, inplace=True)
        
        # Get list of cooling centers
        self.cooling_centers = self.cellphone_df['name'].unique()
        print(f"✓ Found {len(self.cooling_centers)} cooling centers in cellphone data")
        
        # Store column names for visits
        self.visit_columns = [col for col in self.real_visits_df.columns if col != 'date']
        
    def determine_heat_dates(self):
        """Determine top 3 hottest dates based on average temperature or use manual dates"""
        # Use manual dates if provided
        if self.manual_heat_dates:
            print("\nUsing manually specified heat dates...")
            self.heat_dates = [pd.to_datetime(d) for d in self.manual_heat_dates]
            print(f"✓ Heat dates set to:")
            for date in self.heat_dates:
                print(f"  - {date.strftime('%Y-%m-%d')}")
            return
            
        print("\nDetermining heat dates based on temperature data...")
        
        # Load combined summary file with temperature data
        combined_summary_file = self.simulation_path / "combined_summary_all_dates.csv"
        
        if not combined_summary_file.exists():
            raise FileNotFoundError(f"Combined summary file not found: {combined_summary_file}")
            
        # Read temperature data
        temp_df = pd.read_csv(combined_summary_file)
        
        # Check for date column and parse it
        if 'date' in temp_df.columns:
            temp_df['date'] = pd.to_datetime(temp_df['date'])
        else:
            # Try to infer date from first column or index
            temp_df['date'] = pd.to_datetime(temp_df.iloc[:, 0])
        
        # Filter to July 2020 only
        july_mask = (temp_df['date'].dt.year == 2020) & (temp_df['date'].dt.month == 7)
        july_temps = temp_df[july_mask].copy()
        
        # Find temperature column - try different possible names
        temp_col = None
        for col in ['avg_temperature', 'average_temperature', 'mean_temperature', 'temperature']:
            if col in july_temps.columns:
                temp_col = col
                break
                
        if temp_col is None:
            # Print available columns for debugging
            print(f"Available columns: {july_temps.columns.tolist()}")
            raise ValueError("Could not find temperature column in combined summary file")
        
        # Sort by average temperature and get top 3
        top_3_temps = july_temps.nlargest(3, temp_col)
        
        # Extract heat dates
        self.heat_dates = sorted(top_3_temps['date'].tolist())
        
        print(f"✓ Identified top 3 heat dates based on temperature:")
        for date in self.heat_dates:
            temp = july_temps[july_temps['date'] == date][temp_col].values[0]
            print(f"  - {date.strftime('%Y-%m-%d')}: {temp:.1f}°F")
            
    def get_available_dates(self):
        """Get list of dates with ensemble results in July 2020"""
        print("\nFinding available ensemble results...")
        
        available_dates = []
        
        # Check each subdirectory in simulation folder
        if not self.simulation_path.exists():
            raise FileNotFoundError(f"Simulation path not found: {self.simulation_path}")
            
        for date_dir in self.simulation_path.iterdir():
            if date_dir.is_dir() and date_dir.name.isdigit() and len(date_dir.name) == 8:
                # Check for ensemble CSV file
                ensemble_csv = date_dir / f"ensemble_summary_{date_dir.name}.csv"
                if ensemble_csv.exists():
                    # Convert to datetime
                    date = pd.to_datetime(date_dir.name, format='%Y%m%d')
                    # Only include July 2020 dates
                    if date.year == 2020 and date.month == 7:
                        available_dates.append(date)
                        
        available_dates.sort()
        print(f"✓ Found ensemble results for {len(available_dates)} dates in July 2020")
        
        # Debug: show all available dates
        if len(available_dates) > 0:
            print("Available dates with ensemble data:")
            for i, date in enumerate(available_dates):
                if i < 10 or i >= len(available_dates) - 3:  # Show first 10 and last 3
                    print(f"  - {date.strftime('%Y-%m-%d')}")
                elif i == 10:
                    print(f"  ... ({len(available_dates) - 13} more dates) ...")
        
        return available_dates
        
    def count_visits_from_ensemble(self, date):
        """Count visits to cooling centers from ensemble CSV"""
        date_str = date.strftime('%Y%m%d')
        
        # Read ensemble CSV file
        ensemble_csv = self.simulation_path / date_str / f"ensemble_summary_{date_str}.csv"
        
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
        
        for center_name in self.cooling_centers:
            # Count how many parcels went to this center
            visits = (moved_parcels['cooling_center'] == center_name).sum()
            visit_counts[center_name] = visits
            
        # Also get total parcel count
        total_parcels = len(ensemble_df)
        
        return visit_counts, total_parcels
        
    def separate_heat_nonheat_dates(self):
        """Separate dates into heat and non-heat categories"""
        print("\nSeparating heat and non-heat dates...")
        
        # Get all available dates from ensemble results
        self.available_dates = self.get_available_dates()
        
        # Debug: print first few available dates
        print(f"Sample available dates: {[d.strftime('%Y-%m-%d') for d in self.available_dates[:5]]}")
        print(f"Heat dates to match: {[d.strftime('%Y-%m-%d') for d in self.heat_dates]}")
        
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
            # Additional debugging
            print("Checking date matching...")
            for heat_date in self.heat_dates:
                if heat_date in self.available_dates:
                    print(f"  ✓ {heat_date.strftime('%Y-%m-%d')} found in available dates")
                else:
                    print(f"  ✗ {heat_date.strftime('%Y-%m-%d')} NOT found in available dates")
            
    def calculate_overall_statistics(self):
        """Calculate overall heat vs non-heat statistics across all centers"""
        print("\nCalculating overall system heat response...")
        
        # === REAL DATA - Overall ===
        # Get heat and non-heat masks
        heat_mask = self.real_visits_df['date'].isin(self.heat_dates)
        nonheat_mask = ~heat_mask
        
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
            print("\n⚠ ERROR: No heat dates found in ensemble results!")
            print("Please check that the ensemble results exist for the specified heat dates:")
            for date in self.heat_dates:
                date_str = date.strftime('%Y%m%d')
                ensemble_path = self.simulation_path / date_str / f"ensemble_summary_{date_str}.csv"
                if ensemble_path.exists():
                    print(f"  ✓ {date.strftime('%Y-%m-%d')}: Ensemble file exists")
                else:
                    print(f"  ✗ {date.strftime('%Y-%m-%d')}: Ensemble file NOT FOUND at {ensemble_path}")
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
        
        for idx, center_name in enumerate(self.cooling_centers):
            # Show progress
            print(f"\r  Processing center {idx+1}/{total_centers}: {center_name[:30]}...", end='', flush=True)
            
            # Check if center exists in real data columns
            if center_name in self.real_visits_df.columns:
                # === REAL DATA CALCULATIONS ===
                # Heat visits
                heat_mask = self.real_visits_df['date'].isin(self.heat_dates)
                heat_visits_series = self.real_visits_df.loc[heat_mask, center_name]
                real_heat_visits_avg = heat_visits_series.mean() if len(heat_visits_series) > 0 else 0
                
                # Non-heat visits
                nonheat_mask = ~heat_mask
                nonheat_visits_series = self.real_visits_df.loc[nonheat_mask, center_name]
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
        output_csv = self.trial_validate_path / f"cellphone_heat_nonheat_validation_{self.validation_year}{self.validation_month}_{timestamp}.csv"
        
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
        report_file = self.trial_validate_path / f"cellphone_heat_nonheat_report_{self.validation_year}{self.validation_month}_{timestamp}.txt"
        
        # Get overall stats row
        overall_row = self.validation_results[self.validation_results['cooling_option'] == 'Overall'].iloc[0]
        
        # Filter out invalid relative errors for the mean
        center_stats = self.validation_results[self.validation_results['cooling_option'] != 'Overall']
        valid_rel_errors = center_stats['relative_error'].dropna()
        avg_rel_error = valid_rel_errors.mean() if len(valid_rel_errors) > 0 else np.nan
        
        with open(report_file, 'w') as f:
            f.write(f"CELLPHONE DATA HEAT VS NON-HEAT VALIDATION REPORT\n")
            f.write(f"{'='*60}\n")
            f.write(f"Generated: {datetime.now()}\n")
            f.write(f"Trial folder: {self.trial_folder}\n")
            f.write(f"Validation year: {self.validation_year}\n")
            f.write(f"Validation month: {self.validation_month}\n")
            f.write(f"Validation datasource: {self.validation_datasource}\n\n")
            
            f.write(f"HEAT EVENT DEFINITION:\n")
            if self.manual_heat_dates:
                f.write(f"Manually specified heat dates:\n")
            else:
                f.write(f"Top 3 heat dates based on temperature:\n")
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
        summary_file = self.output_validate_path / f"cellphone_summary_{self.validation_year}{self.validation_month}_{self.trial_folder}.csv"
        summary_data = {
            'trial': self.trial_folder,
            'year': self.validation_year,
            'month': self.validation_month,
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
        description='Run heat vs non-heat validation study for cellphone cooling center visits'
    )
    parser.add_argument(
        '--trial', 
        type=str, 
        help='Specific trial folder to use (default: cellphone_YYYY_Month)'
    )
    
    args = parser.parse_args()
    
    # Configuration for validation
    validation_config = {
        'validation_year': '2021',
        'validation_month': 'July',
        'validation_datasource': 'cooling_center_visitation_2021July.csv',
        'data_path': r'~\hennepin\data\validate_data\raw\cellphone_pid_data',
        'simulation_path': r'~\hennepin\output\results\2021',
        # Manually specify heat dates (format: YYYY-MM-DD)
        'manual_heat_dates': ['2020-07-03', '2020-07-09', '2020-07-25']
    }
    
    print("📱 CELLPHONE DATA HEAT VS NON-HEAT VALIDATION STUDY")
    print("="*60)
    print(f"Validation configuration:")
    print(f"  Year: {validation_config['validation_year']}")
    print(f"  Month: {validation_config['validation_month']}")
    print(f"  Data source: {validation_config['validation_datasource']}")
    if 'manual_heat_dates' in validation_config and validation_config['manual_heat_dates']:
        print(f"  Heat dates: {', '.join(validation_config['manual_heat_dates'])} (manually specified)")
    else:
        print(f"  Heat dates: Will be determined from top 3 hottest days (by temperature)")
    print("="*60)
    
    try:
        # Initialize validator
        validator = CellphoneDataHeatValidation(
            trial_folder=args.trial,
            validation_config=validation_config
        )
        
        # Load cellphone data
        validator.load_cellphone_data()
        
        # Determine heat dates from the data or use manual ones
        validator.determine_heat_dates()
        
        # Calculate heat vs non-heat ratios
        validator.calculate_heat_nonheat_ratios()
        
        # Calculate statistics
        validator.calculate_summary_statistics()
        
        # Save results
        output_file = validator.save_results()
        
        print("\n✅ Cellphone data heat vs non-heat validation complete!")
        print(f"📊 Results saved to trial validation folder: {validator.trial_validate_path}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    return 0


if __name__ == "__main__":
    sys.exit(main())