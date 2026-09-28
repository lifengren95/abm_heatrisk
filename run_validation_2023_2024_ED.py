#!/usr/bin/env python3
"""
Heat Risk Model Validation Study - Emergency Department & Simulation Movement
Validates both:
1. Actual ED encounters during heat vs non-heat days
2. Simulated movement decisions during heat vs non-heat days

Usage: python run_validation_ed_heat_vs_nonheat.py

Author: Project contributors
Date: 2025
"""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import json
import warnings
warnings.filterwarnings('ignore')


class EmergencyDeptHeatValidation:
    def __init__(self, validation_config):
        """Initialize ED and simulation validation study"""
        # Store validation configuration
        self.validation_config = validation_config
        self.heat_dates_2023 = [pd.to_datetime(d) for d in validation_config['heat_dates_2023']]
        self.heat_dates_2024 = [pd.to_datetime(d) for d in validation_config['heat_dates_2024']]
        self.data_files = validation_config['data_files']
        self.simulation_paths = validation_config['simulation_paths']
        
        # Create output directory
        self.output_path = Path(r"~\hennepin\output\validate\ed_validate")
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        print(f"ED & Simulation Heat Validation Study")
        print(f"2023 heat dates: {[d.strftime('%Y-%m-%d') for d in self.heat_dates_2023]}")
        print(f"2024 heat dates: {[d.strftime('%Y-%m-%d') for d in self.heat_dates_2024]}")
        
    def load_ed_data(self, filepath, column_name='ed_encounters'):
        """Load and parse ED data CSV file"""
        print(f"\nLoading data from: {filepath}")
        
        df = pd.read_csv(filepath)
        df['date'] = pd.to_datetime(df['date'])
        
        # Rename column if needed
        if 'heat_ed_encounters' in df.columns:
            column_name = 'heat_ed_encounters'
        
        print(f"✓ Loaded {len(df)} days of {column_name} data")
        print(f"  Date range: {df['date'].min().strftime('%Y-%m-%d')} to {df['date'].max().strftime('%Y-%m-%d')}")
        
        return df, column_name
        
    def calculate_lag_dates(self, base_dates, lag_days):
        """Generate lagged heat date sets"""
        return [date + timedelta(days=lag_days) for date in base_dates]
        
    def calculate_heat_vs_nonheat_avg(self, df, heat_dates, value_column):
        """Calculate average values for heat vs non-heat dates"""
        # Create heat mask
        heat_mask = df['date'].isin(heat_dates)
        
        # Calculate averages
        heat_avg = df.loc[heat_mask, value_column].mean() if heat_mask.sum() > 0 else np.nan
        nonheat_avg = df.loc[~heat_mask, value_column].mean() if (~heat_mask).sum() > 0 else np.nan
        
        # Count days
        n_heat = heat_mask.sum()
        n_nonheat = (~heat_mask).sum()
        
        return heat_avg, nonheat_avg, n_heat, n_nonheat
        
    def calculate_relative_increase(self, heat_avg, nonheat_avg):
        """Calculate relative increase ratio"""
        if pd.isna(nonheat_avg) or nonheat_avg == 0:
            return np.nan
        return (heat_avg - nonheat_avg) / nonheat_avg
        
    def get_available_ensemble_dates(self, year):
        """Get list of dates with ensemble results for a given year"""
        print(f"\nFinding ensemble results for {year}...")
        
        base_path = Path(self.simulation_paths[str(year)])
        available_dates = []
        
        if not base_path.exists():
            print(f"⚠ Warning: Simulation path not found: {base_path}")
            return available_dates
            
        # Check each subdirectory
        for date_dir in base_path.iterdir():
            if date_dir.is_dir() and date_dir.name.isdigit() and len(date_dir.name) == 8:
                # Check for ensemble CSV file
                ensemble_csv = date_dir / f"ensemble_summary_{date_dir.name}.csv"
                if ensemble_csv.exists():
                    date = pd.to_datetime(date_dir.name, format='%Y%m%d')
                    available_dates.append(date)
                    
        available_dates.sort()
        print(f"✓ Found ensemble results for {len(available_dates)} dates in {year}")
        
        return available_dates
        
    def count_moves_from_ensemble(self, year, date):
        """Count parcels that moved from ensemble CSV"""
        date_str = date.strftime('%Y%m%d')
        base_path = Path(self.simulation_paths[str(year)])
        
        # Read ensemble CSV file
        ensemble_csv = base_path / date_str / f"ensemble_summary_{date_str}.csv"
        
        if not ensemble_csv.exists():
            return None
            
        try:
            ensemble_df = pd.read_csv(ensemble_csv)
            
            # Count parcels that decided to move
            total_parcels = len(ensemble_df)
            moved_parcels = (ensemble_df['decision_majority'] == 'move').sum()
            
            return moved_parcels, total_parcels
            
        except Exception as e:
            print(f"⚠ Warning: Could not read ensemble CSV for {date_str}: {e}")
            return None
            
    def process_simulation_data(self, year):
        """Process simulation results for heat vs non-heat analysis"""
        print(f"\n{'='*60}")
        print(f"Processing simulation data for {year}")
        print(f"{'='*60}")
        
        # Get available dates
        available_dates = self.get_available_ensemble_dates(year)
        if not available_dates:
            print(f"⚠ No ensemble data found for {year}")
            return None
            
        # Get appropriate heat dates
        base_heat_dates = self.heat_dates_2023 if year == 2023 else self.heat_dates_2024
        
        results = {'year': year}
        
        # Process each lag scenario
        for lag_days, lag_name in [(0, 'nolag'), (1, 'lag1'), (2, 'lag2')]:
            print(f"\nProcessing {lag_name}...")
            
            # Calculate lagged heat dates
            heat_dates = self.calculate_lag_dates(base_heat_dates, lag_days)
            
            # Separate available dates into heat and non-heat
            heat_mask = pd.Series([d in heat_dates for d in available_dates])
            heat_dates_available = [d for d, is_heat in zip(available_dates, heat_mask) if is_heat]
            nonheat_dates_available = [d for d, is_heat in zip(available_dates, heat_mask) if not is_heat]
            
            print(f"  Heat dates available: {len(heat_dates_available)}")
            if heat_dates_available:
                print(f"    {[d.strftime('%Y-%m-%d') for d in heat_dates_available]}")
            print(f"  Non-heat dates available: {len(nonheat_dates_available)}")
            
            # Calculate moves for heat dates
            heat_moves = []
            heat_totals = []
            for date in heat_dates_available:
                result = self.count_moves_from_ensemble(year, date)
                if result:
                    moved, total = result
                    heat_moves.append(moved)
                    heat_totals.append(total)
                    
            # Calculate moves for non-heat dates
            nonheat_moves = []
            nonheat_totals = []
            for date in nonheat_dates_available:
                result = self.count_moves_from_ensemble(year, date)
                if result:
                    moved, total = result
                    nonheat_moves.append(moved)
                    nonheat_totals.append(total)
                    
            # Calculate averages
            heat_avg = np.mean(heat_moves) if heat_moves else np.nan
            nonheat_avg = np.mean(nonheat_moves) if nonheat_moves else np.nan
            
            # Store results
            results[f'sim_overall_move_heat_{lag_name}'] = heat_avg
            results[f'sim_overall_move_nonheat_{lag_name}'] = nonheat_avg
            
            # Calculate relative increase
            relative_increase = self.calculate_relative_increase(heat_avg, nonheat_avg)
            results[f'relative_increase_move_heat_{lag_name}'] = relative_increase
            
            # Report
            print(f"  Average moves on heat days: {heat_avg:.1f}" if not pd.isna(heat_avg) else "  Average moves on heat days: N/A")
            print(f"  Average moves on non-heat days: {nonheat_avg:.1f}" if not pd.isna(nonheat_avg) else "  Average moves on non-heat days: N/A")
            print(f"  Relative increase: {relative_increase:.1%}" if not pd.isna(relative_increase) else "  Relative increase: N/A")
            
        return results
        
    def process_ed_dataset(self, filepath, year, dataset_name):
        """Process one ED dataset with all lag scenarios"""
        # Load data
        df, column_name = self.load_ed_data(filepath)
        
        # Get appropriate heat dates for the year
        base_heat_dates = self.heat_dates_2023 if year == 2023 else self.heat_dates_2024
        
        # Results dictionary
        results = {'year': year}
        
        # Determine prefix based on dataset
        if 'heat_ed' in dataset_name:
            prefix = 'heat_ed_encounters'
        else:
            prefix = 'ed_encounters'
        
        print(f"\nProcessing {dataset_name} for year {year}...")
        
        # Process each lag scenario
        for lag_days, lag_name in [(0, 'nolag'), (1, 'onedaylag'), (2, 'twodaylag')]:
            # Calculate lagged dates
            heat_dates = self.calculate_lag_dates(base_heat_dates, lag_days)
            
            # Filter out dates that might be outside data range
            valid_heat_dates = [d for d in heat_dates if d in df['date'].values]
            
            if len(valid_heat_dates) == 0:
                print(f"  ⚠ Warning: No valid heat dates for {lag_name} (dates outside data range)")
                heat_avg, nonheat_avg = np.nan, np.nan
                n_heat, n_nonheat = 0, 0
            else:
                # Calculate averages
                heat_avg, nonheat_avg, n_heat, n_nonheat = self.calculate_heat_vs_nonheat_avg(
                    df, valid_heat_dates, column_name
                )
                
                print(f"  {lag_name}: {n_heat} heat days, {n_nonheat} non-heat days")
                print(f"    Heat dates: {[d.strftime('%Y-%m-%d') for d in valid_heat_dates]}")
            
            # Store results
            results[f'{prefix}_heat_{lag_name}'] = heat_avg
            results[f'{prefix}_nonheat_{lag_name}'] = nonheat_avg
            
            # Calculate relative increase
            relative_increase = self.calculate_relative_increase(heat_avg, nonheat_avg)
            results[f'relative_{prefix}_increase_heat_{lag_name}'] = relative_increase
            
            # Report
            print(f"    Average on heat days: {heat_avg:.1f}")
            print(f"    Average on non-heat days: {nonheat_avg:.1f}")
            print(f"    Relative increase: {relative_increase:.1%}" if not pd.isna(relative_increase) else "    Relative increase: N/A")
        
        return results
        
    def run_validation(self):
        """Run the complete validation analysis"""
        print("\n" + "="*60)
        print("STARTING VALIDATION ANALYSIS")
        print("="*60)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Part 1: Process simulation data
        print("\n" + "="*60)
        print("PART 1: SIMULATION VALIDATION")
        print("="*60)
        
        sim_results = []
        
        # Process 2023 simulation data
        results_2023 = self.process_simulation_data(2023)
        if results_2023:
            sim_results.append((2023, results_2023))
            
        # Process 2024 simulation data
        results_2024 = self.process_simulation_data(2024)
        if results_2024:
            sim_results.append((2024, results_2024))
            
        # Save simulation results
        self.save_simulation_results(sim_results, timestamp)
        
        # Part 2: Process ED encounter data
        print("\n" + "="*60)
        print("PART 2: ED ENCOUNTER VALIDATION")
        print("="*60)
        
        ed_results = []
        
        # Process each ED dataset
        if 'ed_2023' in self.data_files:
            results = self.process_ed_dataset(
                self.data_files['ed_2023'],
                year=2023,
                dataset_name='ed_encounters_2023'
            )
            ed_results.append(('ed_encounters_2023', results))
        
        if 'ed_2024' in self.data_files:
            results = self.process_ed_dataset(
                self.data_files['ed_2024'],
                year=2024,
                dataset_name='ed_encounters_2024'
            )
            ed_results.append(('ed_encounters_2024', results))
        
        if 'heat_ed_2023' in self.data_files:
            results = self.process_ed_dataset(
                self.data_files['heat_ed_2023'],
                year=2023,
                dataset_name='heat_ed_encounters_2023'
            )
            ed_results.append(('heat_ed_encounters_2023', results))
        
        # Save ED results
        self.save_ed_results(ed_results, timestamp)
        
        # Create combined report
        self.create_summary_report(sim_results, ed_results, timestamp)
        
        return sim_results, ed_results
        
    def save_simulation_results(self, sim_results, timestamp):
        """Save simulation validation results"""
        print("\n" + "="*60)
        print("Saving Simulation Results")
        print("="*60)
        
        for year, results in sim_results:
            # Create DataFrame with one row
            df = pd.DataFrame([results])
            
            # Define column order
            col_order = [
                'year',
                'sim_overall_move_heat_nolag', 'sim_overall_move_nonheat_nolag', 'relative_increase_move_heat_nolag',
                'sim_overall_move_heat_lag1', 'sim_overall_move_nonheat_lag1', 'relative_increase_move_heat_lag1',
                'sim_overall_move_heat_lag2', 'sim_overall_move_nonheat_lag2', 'relative_increase_move_heat_lag2'
            ]
            
            # Reorder columns
            df = df[col_order]
            
            # Save to CSV
            output_file = self.output_path / f"simulation_heat_validation_{year}_{timestamp}.csv"
            df.to_csv(output_file, index=False, float_format='%.6f')
            print(f"✓ Saved {year} simulation results to: {output_file}")
            
            # Display results
            print(f"\n{year} Simulation Results:")
            print(df.to_string(index=False))
            
    def save_ed_results(self, ed_results, timestamp):
        """Save ED encounter validation results"""
        print("\n" + "="*60)
        print("Saving ED Encounter Results")
        print("="*60)
        
        for dataset_name, results in ed_results:
            # Create DataFrame with one row
            df = pd.DataFrame([results])
            
            # Define column order based on dataset type
            if 'heat_ed' in dataset_name:
                col_order = [
                    'year',
                    'heat_ed_encounters_heat_nolag', 'heat_ed_encounters_nonheat_nolag',
                    'heat_ed_encounters_heat_onedaylag', 'heat_ed_encounters_nonheat_onedaylag',
                    'heat_ed_encounters_heat_twodaylag', 'heat_ed_encounters_nonheat_twodaylag',
                    'relative_heat_ed_encounters_increase_heat_nolag',
                    'relative_heat_ed_encounters_increase_heat_onedaylag',
                    'relative_heat_ed_encounters_increase_heat_twodaylag'
                ]
            else:
                col_order = [
                    'year',
                    'ed_encounters_heat_nolag', 'ed_encounters_nonheat_nolag',
                    'ed_encounters_heat_onedaylag', 'ed_encounters_nonheat_onedaylag',
                    'ed_encounters_heat_twodaylag', 'ed_encounters_nonheat_twodaylag',
                    'relative_ed_encounters_increase_heat_nolag',
                    'relative_ed_encounters_increase_heat_onedaylag',
                    'relative_ed_encounters_increase_heat_twodaylag'
                ]
            
            # Reorder columns
            df = df[col_order]
            
            # Save to CSV
            output_file = self.output_path / f"{dataset_name}_validation_{timestamp}.csv"
            df.to_csv(output_file, index=False, float_format='%.6f')
            print(f"✓ Saved {dataset_name} results to: {output_file}")
            
            # Display results
            print(f"\n{dataset_name} Results:")
            print(df.to_string(index=False))
            
    def create_summary_report(self, sim_results, ed_results, timestamp):
        """Create a combined summary report"""
        report_file = self.output_path / f"validation_report_{timestamp}.txt"
        
        with open(report_file, 'w') as f:
            f.write("HEAT VALIDATION REPORT - SIMULATION & ED ENCOUNTERS\n")
            f.write("="*60 + "\n")
            f.write(f"Generated: {datetime.now()}\n")
            f.write(f"2023 Heat Dates: {', '.join([d.strftime('%Y-%m-%d') for d in self.heat_dates_2023])}\n")
            f.write(f"2024 Heat Dates: {', '.join([d.strftime('%Y-%m-%d') for d in self.heat_dates_2024])}\n\n")
            
            # Simulation results
            f.write("SIMULATION RESULTS (Movement to Cooling Centers)\n")
            f.write("="*60 + "\n")
            
            for year, results in sim_results:
                f.write(f"\n{year} Simulation:\n")
                f.write("-"*40 + "\n")
                
                for lag_name, lag_label in [('nolag', 'No Lag'), ('lag1', '1-Day Lag'), ('lag2', '2-Day Lag')]:
                    f.write(f"\n{lag_label}:\n")
                    heat_avg = results.get(f'sim_overall_move_heat_{lag_name}', np.nan)
                    nonheat_avg = results.get(f'sim_overall_move_nonheat_{lag_name}', np.nan)
                    rel_inc = results.get(f'relative_increase_move_heat_{lag_name}', np.nan)
                    
                    f.write(f"  Heat avg: {heat_avg:.1f} parcels/day\n" if not pd.isna(heat_avg) else "  Heat avg: N/A\n")
                    f.write(f"  Non-heat avg: {nonheat_avg:.1f} parcels/day\n" if not pd.isna(nonheat_avg) else "  Non-heat avg: N/A\n")
                    f.write(f"  Relative increase: {rel_inc:.1%}\n" if not pd.isna(rel_inc) else "  Relative increase: N/A\n")
            
            # ED results
            f.write("\n\nED ENCOUNTER RESULTS\n")
            f.write("="*60 + "\n")
            
            for dataset_name, results in ed_results:
                f.write(f"\n{dataset_name.upper()}\n")
                f.write("-"*40 + "\n")
                
                # Determine prefix
                prefix = 'heat_ed_encounters' if 'heat_ed' in dataset_name else 'ed_encounters'
                
                # No lag results
                f.write(f"No Lag:\n")
                f.write(f"  Heat avg: {results.get(f'{prefix}_heat_nolag', 'N/A'):.1f}\n")
                f.write(f"  Non-heat avg: {results.get(f'{prefix}_nonheat_nolag', 'N/A'):.1f}\n")
                rel_inc = results.get(f'relative_{prefix}_increase_heat_nolag', np.nan)
                f.write(f"  Relative increase: {rel_inc:.1%}\n" if not pd.isna(rel_inc) else "  Relative increase: N/A\n")
                
                # 1-day lag results
                f.write(f"\n1-Day Lag:\n")
                f.write(f"  Heat avg: {results.get(f'{prefix}_heat_onedaylag', 'N/A'):.1f}\n")
                f.write(f"  Non-heat avg: {results.get(f'{prefix}_nonheat_onedaylag', 'N/A'):.1f}\n")
                rel_inc = results.get(f'relative_{prefix}_increase_heat_onedaylag', np.nan)
                f.write(f"  Relative increase: {rel_inc:.1%}\n" if not pd.isna(rel_inc) else "  Relative increase: N/A\n")
                
                # 2-day lag results
                f.write(f"\n2-Day Lag:\n")
                f.write(f"  Heat avg: {results.get(f'{prefix}_heat_twodaylag', 'N/A'):.1f}\n")
                f.write(f"  Non-heat avg: {results.get(f'{prefix}_nonheat_twodaylag', 'N/A'):.1f}\n")
                rel_inc = results.get(f'relative_{prefix}_increase_heat_twodaylag', np.nan)
                f.write(f"  Relative increase: {rel_inc:.1%}\n" if not pd.isna(rel_inc) else "  Relative increase: N/A\n")
        
        print(f"\n✓ Saved summary report to: {report_file}")


def main():
    """Main execution function"""
    # Configuration for validation
    validation_config = {
        'heat_dates_2023': ['2023-08-22', '2023-08-23'],  # Aug 22-23, 2023
        'heat_dates_2024': ['2024-08-26', '2024-08-27'],  # Aug 26-27, 2024
        'data_files': {
            'ed_2023': r'~\hennepin\data\validate_data\raw\ED\ed_encounters_2023_0501_0930.csv',
            'ed_2024': r'~\hennepin\data\validate_data\raw\ED\ed_encounters_2024_0501_0930.csv',
            'heat_ed_2023': r'~\hennepin\data\validate_data\raw\ED\heat_ed_encounters_2023_0501_0930.csv'
        },
        'simulation_paths': {
            '2023': r'~\hennepin\output\results\2023',
            '2024': r'~\hennepin\output\results\2024'
        }
    }
    
    print("🏥 HEAT VALIDATION STUDY - SIMULATION & ED ENCOUNTERS")
    print("="*60)
    
    try:
        # Initialize validator
        validator = EmergencyDeptHeatValidation(validation_config)
        
        # Run validation
        sim_results, ed_results = validator.run_validation()
        
        print("\n✅ Heat validation complete!")
        print(f"📊 Results saved to: {validator.output_path}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    return 0


if __name__ == "__main__":
    sys.exit(main())