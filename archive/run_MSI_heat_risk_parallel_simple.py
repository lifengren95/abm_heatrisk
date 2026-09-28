#!/usr/bin/env python3
"""
PRODUCTION Heat Risk Model - Simplified for direct execution
No argument parsing - all configuration hardcoded for production runs
"""
import os

import numpy as np
import pandas as pd
import geopandas as gpd
import os
import time
import pickle
import warnings
from multiprocessing import cpu_count, freeze_support
from concurrent.futures import ProcessPoolExecutor, as_completed
import gc
from pathlib import Path
from tqdm import tqdm
import psutil
import rasterio
from datetime import datetime, timedelta
import json

# Model imports
import sys
from src import Parcel, HeatEvent

# Suppress warnings
warnings.filterwarnings('ignore')

# ============= CONFIGURATION =============
USE_EXTERNAL_AC_DATA = True
AC_DATA_PATH = "../../data/raw/Parcel_AC/hennepin_parcel_ac_avail.csv"

# Import all the necessary functions from your main script
from run_MSI_heat_risk_model_parallel import (
    load_external_ac_data,
    extract_temperatures_from_raster,
    get_temperature_raster_path,
    process_parcel_chunk,
    ChunkParallelHeatModel
)


def main():
    """Production main function - all configuration hardcoded"""
    
    # ============= HARDCODED PRODUCTION CONFIGURATION =============
    # Get array task ID from environment (for SLURM) or default to 0
    array_task_id = int(os.environ.get('SLURM_ARRAY_TASK_ID', 0))
    
    # Get date indices from environment or command line fallback
    start_idx = int(os.environ.get('START_DATE_IDX', array_task_id * 3))
    end_idx = int(os.environ.get('END_DATE_IDX', start_idx + 2))
    
    # Generate all production dates
    all_dates = []
    
    # 2020: July 1-31
    for day in range(1, 32):
        all_dates.append(f'202007{day:02d}')
    
    # 2021: July 1-31
    for day in range(1, 32):
        all_dates.append(f'202107{day:02d}')
    
    # 2023: May 1 - September 30
    for month in [5, 6, 7, 8, 9]:
        if month in [5, 7, 8]:  # 31-day months
            days = 31
        elif month == 6:  # June has 30 days
            days = 30
        else:  # September has 30 days
            days = 30
        for day in range(1, days + 1):
            all_dates.append(f'2023{month:02d}{day:02d}')
    
    # 2024: May 1 - September 30
    for month in [5, 6, 7, 8, 9]:
        if month in [5, 7, 8]:  # 31-day months
            days = 31
        elif month == 6:  # June has 30 days
            days = 30
        else:  # September has 30 days
            days = 30
        for day in range(1, days + 1):
            all_dates.append(f'2024{month:02d}{day:02d}')
    
    # Handle bounds
    if end_idx >= len(all_dates):
        end_idx = len(all_dates) - 1
    
    # Select dates for this run
    dates_to_process = all_dates[start_idx:end_idx+1]
    
    # Production configuration
    config = {
        'num_runs': 1000,  # Production: 1000 runs
        'max_workers': 60,  # Production: 60 workers
        'temp_dir': "../../data/validate_data/intermediate/prism",
        'dates': dates_to_process
    }
    
    # Print configuration
    print("="*80)
    print("HEAT RISK MODEL - PRODUCTION RUN")
    print("="*80)
    print(f"Array Task ID: {array_task_id}")
    print(f"Job ID: {os.environ.get('SLURM_JOB_ID', 'LOCAL')}")
    print(f"Node: {os.environ.get('SLURMD_NODENAME', 'LOCAL')}")
    print(f"Total dates available: {len(all_dates)}")
    print(f"Date indices: {start_idx} to {end_idx}")
    print(f"Dates to process: {dates_to_process}")
    print(f"Number of runs per date: {config['num_runs']}")
    print(f"Parallel workers: {config['max_workers']}")
    print(f"External AC data: {'ENABLED' if USE_EXTERNAL_AC_DATA else 'DISABLED'}")
    print("="*80)
    
    # Set working directory
    code_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(code_dir)
    print(f"Working directory: {os.getcwd()}")
    
    # Set random seed
    np.random.seed(42 + array_task_id)
    
    # Run analysis
    model = ChunkParallelHeatModel(config)
    model.trial_folder = f"trial_{time.strftime('%Y%m%d_%H%M%S')}_prod_job{array_task_id}"
    
    print(f"\nOutput directory: ../../output/results/{model.trial_folder}/")
    
    # Check temperature files
    print("\nChecking temperature raster files...")
    missing_dates = []
    for date_str in config['dates']:
        try:
            temp_path = get_temperature_raster_path(date_str, config['temp_dir'])
            print(f"  ✓ Found: {os.path.basename(temp_path)}")
        except FileNotFoundError:
            missing_dates.append(date_str)
            print(f"  ❌ Missing: tmax_hennepin_{date_str}_500m.tif")
    
    if missing_dates:
        print(f"\n⚠️ WARNING: Missing temperature files for: {', '.join(missing_dates)}")
        config['dates'] = [d for d in config['dates'] if d not in missing_dates]
    
    if not config['dates']:
        print("\n❌ ERROR: No valid temperature files found. Exiting.")
        return []
    
    # Run the analysis
    print(f"\nStarting analysis for {len(config['dates'])} dates...")
    all_results = model.run_analysis_for_dates(config['dates'], config['temp_dir'])
    
    # Print summary
    print("\n" + "="*80)
    print(f"PRODUCTION RUN COMPLETED - JOB {array_task_id}")
    print("="*80)
    
    if all_results:
        for result in all_results:
            stats = result['ensemble_stats']
            print(f"\nDate: {result['date']}")
            print(f"  - Average Temperature: {stats['avg_temperature']:.1f}°F")
            print(f"  - Moved to cooling centers: {stats['moved_pct']:.2f}%")
            print(f"  - Decision stability: {stats['avg_stability']:.3f}")
        
        print(f"\n📁 Results saved in: ../../output/results/{model.trial_folder}/")
    
    return all_results


if __name__ == "__main__":
    freeze_support()
    
    print(f"\n🚀 Starting Heat Risk Model Production Run at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    start_time = time.time()
    
    try:
        all_results = main()
        total_time = time.time() - start_time
        
        print(f"\n⏱️ Total execution time: {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
        print(f"⏱️ Processed {len(all_results)} dates successfully")
        print("\n✅ Script completed successfully!")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Script interrupted by user (Ctrl+C)")
        print("Shutting down gracefully...")
        
    except Exception as e:
        print(f"\n❌ Error occurred: {str(e)}")
        import traceback
        traceback.print_exc()