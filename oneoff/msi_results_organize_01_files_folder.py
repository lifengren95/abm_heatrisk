import os
import shutil
import re

# Source and destination paths
source_base = r"~\hennepin\output\msi_runs_07262025"
dest_base = r"~\hennepin\output\results\geometric_model_1000runs"

# Define year folders
year_folders = ['2020', '2021', '2023', '2024']

# Create destination year folders if they don't exist
for year in year_folders:
    year_path = os.path.join(dest_base, year)
    os.makedirs(year_path, exist_ok=True)

# Pattern to match date folders (8 digits starting with year)
date_pattern = re.compile(r'^(\d{4})(\d{4})$')

# Counter for tracking
copied_count = 0
error_count = 0

# Iterate through all trial folders
for trial_folder in os.listdir(source_base):
    trial_path = os.path.join(source_base, trial_folder)
    
    # Skip if not a directory
    if not os.path.isdir(trial_path):
        continue
    
    print(f"\nProcessing trial folder: {trial_folder}")
    
    # Look for date folders inside each trial folder
    for item in os.listdir(trial_path):
        item_path = os.path.join(trial_path, item)
        
        # Check if it's a directory and matches date pattern
        if os.path.isdir(item_path):
            match = date_pattern.match(item)
            if match:
                year = match.group(1)
                
                # Only process if year is in our list
                if year in year_folders:
                    dest_year_folder = os.path.join(dest_base, year)
                    dest_path = os.path.join(dest_year_folder, item)
                    
                    try:
                        # Check if destination already exists
                        if os.path.exists(dest_path):
                            print(f"  Warning: {item} already exists in {year} folder. Skipping...")
                            continue
                        
                        # Copy the folder
                        shutil.copytree(item_path, dest_path)
                        print(f"  Copied: {item} -> {year} folder")
                        copied_count += 1
                        
                    except Exception as e:
                        print(f"  Error copying {item}: {str(e)}")
                        error_count += 1
                else:
                    print(f"  Skipping {item} - year {year} not in target years")

print(f"\n{'='*50}")
print(f"Summary:")
print(f"  Total folders copied: {copied_count}")
print(f"  Errors encountered: {error_count}")
print(f"{'='*50}")