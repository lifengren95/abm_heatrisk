#!/usr/bin/env python3
"""
TEST Heat Risk Model - Simplified for quick testing
Processes only 4 test dates with 10 runs each
"""

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
    """Test main function - processes 4 dates with reduced runs"""
    
    # TEST CONFIGURATION - 4 dates only
    test_dates = [
        '20230701',  # July 1, 2023
        '20230715',  # July 15, 2023
        '20240701',  # July 1, 2024
        '20240715'   # July 15, 2024
    ]
    
    # Test configuration
    config = {
        'num_runs': 10,     # Test: only 10 runs
        'max_workers': 8,   # Test: fewer workers
        'temp_dir': "../../data/validate_data/intermediate/prism",
        'dates': test_dates
    }
    
    # Print configuration
    print("="*80)
    print("HEAT RISK MODEL - TEST RUN")
    print("="*80)
    print(f"Test dates: {', '.join(test_dates)}")
    print(f"Number of runs per date: {config['num_runs']}")
    print(f"Parallel workers: {config['max_workers']}")
    print(f"Available CPU cores: {cpu_count()}")
    print(f"External AC data: {'ENABLED' if USE_EXTERNAL_AC_DATA else 'DISABLED'}")
    print("="*80)
    
    # Set working directory
    code_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(code_dir)
    print(f"Working directory: {os.getcwd()}")
    
    # Set random seed
    np.random.seed(42)
    
    # Run analysis
    model = ChunkParallelHeatModel(config)
    model.trial_folder = f"trial_{time.strftime('%Y%m%d_%H%M%S')}_test"
    
    print(f"\nOutput directory: ../../output/results/{model.trial_folder}/")
    
    # Check temperature files
    print("\nChecking temperature raster files...")
    available_dates = []
    for date_str in config['dates']:
        try:
            temp_path = get_temperature_raster_path(date_str, config['temp_dir'])
            print(f"  ✓ Found: {os.path.basename(temp_path)}")
            available_dates.append(date_str)
        except FileNotFoundError:
            print(f"  ❌ Missing: tmax_hennepin_{date_str}_500m.tif")
    
    if not available_dates:
        print("\n❌ ERROR: No temperature files found for test dates!")
        return []
    
    config['dates'] = available_dates
    print(f"\nProcessing {len(available_dates)} available test dates...")
    
    # Run the analysis
    all_results = model.run_analysis_for_dates(config['dates'], config['temp_dir'])
    
    # Print summary
    print("\n" + "="*80)
    print("TEST RUN COMPLETED")
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
    
    print(f"\n🚀 Starting Heat Risk Model Test Run at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    start_time = time.time()
    
    try:
        all_results = main()
        total_time = time.time() - start_time
        
        print(f"\n⏱️ Total execution time: {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
        print(f"⏱️ Processed {len(all_results)} dates successfully")
        print("\n✅ Test completed successfully!")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user (Ctrl+C)")
        print("Shutting down gracefully...")
        
    except Exception as e:
        print(f"\n❌ Error occurred: {str(e)}")
        import traceback
        traceback.print_exc()