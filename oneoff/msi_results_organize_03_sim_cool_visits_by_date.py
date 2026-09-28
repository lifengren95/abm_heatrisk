import os
import pandas as pd
from pathlib import Path
import glob
from datetime import datetime

def process_cooling_center_visits():
    """
    Process all ensemble summary CSV files to aggregate cooling center visits
    """
    
    # Define paths
    base_path = r"~\hennepin\output\results\geometric_model_1000runs"
    output_file = os.path.join(base_path, "sim_cooling_visits_geometric_abm.csv")
    
    # Years to process
    years = ['2020', '2021', '2023', '2024']
    
    # Initialize list to store all results
    all_results = []
    
    # Counter for progress tracking
    total_files_processed = 0
    files_with_errors = []
    
    print(f"Starting processing of cooling center visits...")
    print(f"Base path: {base_path}")
    print(f"Output will be saved to: {output_file}\n")
    
    # Process each year
    for year in years:
        year_path = os.path.join(base_path, year)
        
        if not os.path.exists(year_path):
            print(f"Warning: Year folder {year_path} does not exist. Skipping...")
            continue
            
        print(f"Processing year {year}...")
        
        # Get all date folders in the year
        date_folders = [d for d in os.listdir(year_path) 
                       if os.path.isdir(os.path.join(year_path, d))]
        date_folders.sort()  # Sort for consistent processing
        
        print(f"  Found {len(date_folders)} date folders in {year}")
        
        # Process each date folder
        for date_folder in date_folders:
            date_path = os.path.join(year_path, date_folder)
            csv_file = os.path.join(date_path, f"ensemble_summary_{date_folder}.csv")
            
            if not os.path.exists(csv_file):
                print(f"  Warning: CSV file not found: {csv_file}")
                files_with_errors.append(csv_file)
                continue
            
            try:
                # Read the CSV file
                df = pd.read_csv(csv_file)
                
                # Check if cooling_center column exists
                if 'cooling_center' not in df.columns:
                    print(f"  Warning: 'cooling_center' column not found in {csv_file}")
                    files_with_errors.append(csv_file)
                    continue
                
                # Convert cooling_center column to string, handling NaN values
                df['cooling_center'] = df['cooling_center'].astype(str)
                
                # Filter out rows where cooling_center is "None", "nan", or empty
                df_filtered = df[
                    (df['cooling_center'] != 'None') &
                    (df['cooling_center'] != 'nan') &
                    (df['cooling_center'].str.strip() != '')
                ]
                
                # Count visits to each cooling center
                if len(df_filtered) > 0:
                    visit_counts = df_filtered['cooling_center'].value_counts().reset_index()
                    visit_counts.columns = ['name', 'simulate_parcel_visits']
                    visit_counts['date'] = date_folder
                    
                    # Reorder columns
                    visit_counts = visit_counts[['name', 'date', 'simulate_parcel_visits']]
                    
                    # Add to results
                    all_results.append(visit_counts)
                
                total_files_processed += 1
                
                # Progress update every 50 files
                if total_files_processed % 50 == 0:
                    print(f"  Processed {total_files_processed} files...")
                    
            except Exception as e:
                print(f"  Error processing {csv_file}: {str(e)}")
                files_with_errors.append(csv_file)
                continue
    
    # Combine all results
    if all_results:
        final_df = pd.concat(all_results, ignore_index=True)
        
        # Sort by date and name for better organization
        final_df = final_df.sort_values(['date', 'name']).reset_index(drop=True)
        
        # Save to CSV
        final_df.to_csv(output_file, index=False)
        
        print(f"\n" + "="*60)
        print(f"Processing complete!")
        print(f"Total files processed: {total_files_processed}")
        print(f"Files with errors: {len(files_with_errors)}")
        print(f"Total unique cooling centers found: {final_df['name'].nunique()}")
        print(f"Total records in output: {len(final_df)}")
        print(f"Date range: {final_df['date'].min()} to {final_df['date'].max()}")
        print(f"\nOutput saved to: {output_file}")
        
        # Display sample of results
        print(f"\nSample of results (first 10 rows):")
        print(final_df.head(10).to_string())
        
        # Summary statistics
        print(f"\nSummary by year:")
        final_df['year'] = final_df['date'].astype(str).str[:4]
        year_summary = final_df.groupby('year').agg({
            'date': 'nunique',
            'name': 'nunique',
            'simulate_parcel_visits': 'sum'
        }).rename(columns={
            'date': 'unique_dates',
            'name': 'unique_centers',
            'simulate_parcel_visits': 'total_visits'
        })
        print(year_summary.to_string())
        
    else:
        print(f"\nNo data was processed. Please check the input folders and file structure.")
    
    # Report files with errors if any
    if files_with_errors:
        print(f"\nFiles that couldn't be processed ({len(files_with_errors)}):")
        for f in files_with_errors[:10]:  # Show first 10
            print(f"  - {f}")
        if len(files_with_errors) > 10:
            print(f"  ... and {len(files_with_errors) - 10} more")
    
    return final_df if all_results else None


def verify_folder_structure():
    """
    Verify the folder structure before processing
    """
    base_path = r"~\hennepin\output\results\geometric_model_1000runs"
    
    print("Verifying folder structure...")
    
    if not os.path.exists(base_path):
        print(f"ERROR: Base path does not exist: {base_path}")
        return False
    
    years = ['2020', '2021', '2023', '2024']
    total_date_folders = 0
    
    for year in years:
        year_path = os.path.join(base_path, year)
        if os.path.exists(year_path):
            date_folders = [d for d in os.listdir(year_path) 
                          if os.path.isdir(os.path.join(year_path, d))]
            print(f"  Year {year}: {len(date_folders)} date folders")
            total_date_folders += len(date_folders)
        else:
            print(f"  Year {year}: Folder not found")
    
    print(f"Total date folders found: {total_date_folders}")
    return total_date_folders > 0


if __name__ == "__main__":
    # Verify folder structure first
    if verify_folder_structure():
        print("\n" + "="*60)
        # Process the data
        result_df = process_cooling_center_visits()
        
        if result_df is not None:
            print("\nProcessing completed successfully!")
        else:
            print("\nProcessing failed. Please check the error messages above.")
    else:
        print("\nFolder structure verification failed. Please check your paths.")