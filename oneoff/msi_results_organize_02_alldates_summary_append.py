#!/usr/bin/env python3
"""
Combine MSI job outputs into year-level and overall summaries for heat risk model results.
Reads 368 individual job CSVs and creates consolidated summaries.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime
import glob
import os
from tqdm import tqdm

def find_trial_folders(msi_base_dir):
    """Find all trial folders for jobs 0-367"""
    trial_folders = []
    missing_jobs = []
    
    for job_num in range(368):
        # Pattern to match: trial_*_prod_job{job_num}
        pattern = str(Path(msi_base_dir) / f"trial_*_prod_job{job_num}")
        matches = glob.glob(pattern)
        
        if matches:
            # Should only be one match per job number
            trial_folders.append(matches[0])
        else:
            missing_jobs.append(job_num)
            print(f"⚠️ Warning: No folder found for job {job_num}")
    
    print(f"✓ Found {len(trial_folders)} job folders out of 368")
    if missing_jobs:
        print(f"  Missing jobs: {missing_jobs}")
    
    return trial_folders

def read_all_summaries(trial_folders):
    """Read all combined_summary_all_dates.csv files from trial folders"""
    all_data = []
    failed_reads = []
    
    print("\nReading CSV files from all job folders...")
    for folder in tqdm(trial_folders, desc="Reading CSVs"):
        csv_path = Path(folder) / "combined_summary_all_dates.csv"
        
        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path)
                # Add source folder for debugging if needed
                df['source_folder'] = Path(folder).name
                all_data.append(df)
            except Exception as e:
                print(f"\n❌ Error reading {csv_path}: {e}")
                failed_reads.append(folder)
        else:
            print(f"\n⚠️ CSV not found: {csv_path}")
            failed_reads.append(folder)
    
    if failed_reads:
        print(f"\n⚠️ Failed to read {len(failed_reads)} files")
    
    # Concatenate all dataframes
    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        print(f"\n✓ Successfully combined {len(combined_df)} date records")
        return combined_df
    else:
        raise ValueError("No data could be read from any job folders!")

def parse_dates(df):
    """Add year column and sort by date"""
    # Convert date column to string if it isn't already
    df['date'] = df['date'].astype(str)
    
    # Extract year from YYYYMMDD format
    df['year'] = df['date'].str[:4].astype(int)
    
    # Sort by date
    df = df.sort_values('date').reset_index(drop=True)
    
    return df

def create_readme_content(df, title, num_runs=1000):
    """Generate README content similar to the original format"""
    content = []
    content.append(f"{title}")
    content.append("=" * 60)
    content.append(f"\nAnalysis completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    content.append(f"Number of runs per date: {num_runs}")
    content.append(f"Dates processed: {len(df)}")
    content.append("AC Data Configuration:")
    content.append("  - Using external AC data: True")
    content.append("  - External AC file: ../../data/raw/Parcel_AC/hennepin_parcel_ac_avail.csv")
    content.append("  - Parcels with external AC data: 346,704")
    
    # Add summary statistics
    content.append("\nOverall Statistics:")
    content.append("-" * 60)
    content.append(f"Temperature range: {df['avg_temperature'].min():.1f}°F - {df['avg_temperature'].max():.1f}°F")
    content.append(f"Average temperature: {df['avg_temperature'].mean():.1f}°F")
    content.append(f"Average movement rate: {df['moved_pct'].mean():.2f}%")
    content.append(f"Movement rate range: {df['moved_pct'].min():.2f}% - {df['moved_pct'].max():.2f}%")
    
    # Group by year if multiple years present
    if 'year' in df.columns and df['year'].nunique() > 1:
        content.append("\nSummary by Year:")
        content.append("-" * 60)
        for year in sorted(df['year'].unique()):
            year_data = df[df['year'] == year]
            content.append(f"\n{year}: {len(year_data)} dates")
            content.append(f"  Average Temperature: {year_data['avg_temperature'].mean():.1f}°F")
            content.append(f"  Average Movement: {year_data['moved_pct'].mean():.2f}%")
            content.append(f"  Temperature Range: {year_data['avg_temperature'].min():.1f}°F - {year_data['avg_temperature'].max():.1f}°F")
    
    content.append("\nSummary by date:")
    content.append("-" * 60)
    
    for _, row in df.iterrows():
        date_str = str(row['date'])
        # Format date as YYYYMMDD for display
        content.append(f"\n{date_str}:")
        content.append(f"  Average Temperature: {row['avg_temperature']:.1f}°F")
        content.append(f"  Moved to cooling centers: {row['moved_pct']:.2f}%")
        content.append(f"  Stayed home: {row['stayed_home_pct']:.2f}%")
        content.append(f"  Decision stability: {row['avg_stability']:.3f}")
        content.append(f"  External AC data used: {row['ac_external_pct']:.1f}%")
    
    content.append("\n" + "=" * 60)
    content.append("File descriptions:")
    content.append("- ensemble_YYYYMMDD.shp: GIS visualization file")
    content.append("- ensemble_summary_YYYYMMDD.csv: Detailed results per parcel")
    content.append("- run_statistics_YYYYMMDD.csv: Statistics for each model run")
    content.append("- metadata_YYYYMMDD.json: Run configuration and summary")
    
    return "\n".join(content)

def save_year_summaries(df, output_base_dir):
    """Save summaries for each year"""
    years = sorted(df['year'].unique())
    
    print(f"\nSaving year-level summaries for years: {years}")
    
    for year in years:
        year_df = df[df['year'] == year].copy()
        year_df = year_df.sort_values('date').reset_index(drop=True)
        
        # Create year directory
        year_dir = Path(output_base_dir) / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)
        
        # Save CSV (without the source_folder column if present)
        if 'source_folder' in year_df.columns:
            year_df = year_df.drop('source_folder', axis=1)
        
        csv_path = year_dir / "combined_summary_all_dates.csv"
        year_df.to_csv(csv_path, index=False)
        print(f"  ✓ Saved {year} CSV: {csv_path} ({len(year_df)} dates)")
        
        # Save README
        readme_content = create_readme_content(
            year_df, 
            f"Heat Risk Model Results - {year} (1000 runs per date)"
        )
        readme_path = year_dir / "README.txt"
        with open(readme_path, 'w') as f:
            f.write(readme_content)
        print(f"  ✓ Saved {year} README: {readme_path}")

def save_overall_summary(df, output_base_dir):
    """Save overall summary across all years"""
    print("\nSaving overall summary...")
    
    # Remove source_folder column if present
    if 'source_folder' in df.columns:
        df = df.drop('source_folder', axis=1)
    
    # Save all years CSV
    csv_path = Path(output_base_dir) / "combined_summary_all_years.csv"
    df.to_csv(csv_path, index=False)
    print(f"  ✓ Saved overall CSV: {csv_path} ({len(df)} dates)")
    
    # Save all years README
    readme_content = create_readme_content(
        df,
        "Heat Risk Model Results - All Years (1000 runs per date)"
    )
    readme_path = Path(output_base_dir) / "README_all_years.txt"
    with open(readme_path, 'w') as f:
        f.write(readme_content)
    print(f"  ✓ Saved overall README: {readme_path}")

def print_summary_statistics(df):
    """Print summary statistics for verification"""
    print("\n" + "=" * 60)
    print("SUMMARY STATISTICS")
    print("=" * 60)
    
    # Overall stats
    print(f"\nTotal dates processed: {len(df)}")
    print(f"Years covered: {sorted(df['year'].unique())}")
    
    # By year breakdown
    print("\nDates per year:")
    for year in sorted(df['year'].unique()):
        count = len(df[df['year'] == year])
        print(f"  {year}: {count} dates")
    
    # Temperature statistics
    print(f"\nTemperature Statistics:")
    print(f"  Overall mean: {df['avg_temperature'].mean():.1f}°F")
    print(f"  Overall min: {df['avg_temperature'].min():.1f}°F")
    print(f"  Overall max: {df['avg_temperature'].max():.1f}°F")
    
    # Movement statistics
    print(f"\nMovement Statistics:")
    print(f"  Average moved %: {df['moved_pct'].mean():.2f}%")
    print(f"  Min moved %: {df['moved_pct'].min():.2f}%")
    print(f"  Max moved %: {df['moved_pct'].max():.2f}%")
    
    # Check for any missing or unusual data
    if df.isnull().any().any():
        print("\n⚠️ Warning: Some null values detected in the data")
        print(df.isnull().sum())

def main():
    """Main execution function"""
    
    # Configuration
    MSI_BASE_DIR = r"~\hennepin\output\msi_runs_07262025"
    OUTPUT_BASE_DIR = r"~\hennepin\output\results\geometric_model_1000runs"
    
    print("🚀 COMBINING MSI HEAT RISK MODEL RESULTS")
    print(f"MSI source directory: {MSI_BASE_DIR}")
    print(f"Output directory: {OUTPUT_BASE_DIR}")
    
    try:
        # Step 1: Find all trial folders
        trial_folders = find_trial_folders(MSI_BASE_DIR)
        
        if len(trial_folders) < 368:
            response = input(f"\n⚠️ Only found {len(trial_folders)} folders out of 368. Continue? (y/n): ")
            if response.lower() != 'y':
                print("Exiting...")
                return
        
        # Step 2: Read all CSV files
        combined_df = read_all_summaries(trial_folders)
        
        # Step 3: Parse dates and add year column
        combined_df = parse_dates(combined_df)
        
        # Step 4: Print summary statistics
        print_summary_statistics(combined_df)
        
        # Step 5: Save year-level summaries
        save_year_summaries(combined_df, OUTPUT_BASE_DIR)
        
        # Step 6: Save overall summary
        save_overall_summary(combined_df, OUTPUT_BASE_DIR)
        
        print("\n✅ All summaries created successfully!")
        print(f"📁 Results saved in: {OUTPUT_BASE_DIR}")
        
        # Final verification
        print(f"\nCreated files:")
        for year in sorted(combined_df['year'].unique()):
            print(f"  - {year}/combined_summary_all_dates.csv")
            print(f"  - {year}/README.txt")
        print(f"  - combined_summary_all_years.csv")
        print(f"  - README_all_years.txt")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()