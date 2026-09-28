#!/usr/bin/env python3
"""
Debug script to understand the HeatEvent.gdf structure
"""

import os
import sys
import numpy as np

# Add the code path
sys.path.append(r'~\hennepin\code\HeatRisk_ABM_Model')

from src import HeatEvent

def debug_heat_event():
    """Debug a single HeatEvent to understand the structure"""
    print("=== DEBUGGING HEAT EVENT STRUCTURE ===")
    
    # Set working directory
    code_dir = r"~\hennepin\code\HeatRisk_ABM_Model"
    if os.path.exists(code_dir):
        os.chdir(code_dir)
        print(f"Working directory: {os.getcwd()}")
    
    # Configuration
    temp_raster = r"~\hennepin\output\oneoff\parcel_temperatures_20240831.tif"
    fallback_temp = 100
    
    try:
        print("\n1. Creating HeatEvent instance...")
        heat_event = HeatEvent(fallback_temp)
        
        print("\n2. Running simulation...")
        heat_event.run_simulation(temp_raster)
        
        print("\n3. Processing results...")
        heat_event.process_results()
        
        print("\n4. Examining GDF structure...")
        gdf = heat_event.gdf
        
        print(f"   Shape: {gdf.shape}")
        print(f"   Columns: {list(gdf.columns)}")
        print(f"   Index type: {type(gdf.index)}")
        print(f"   CRS: {gdf.crs}")
        
        print("\n5. Sample data:")
        print(gdf.head()[['pid', 'decision', 'proba']].to_string())
        
        print("\n6. Decision distribution:")
        decision_counts = gdf['decision'].value_counts()
        print(decision_counts)
        
        print("\n7. Checking for cooling center info...")
        if 'cooling_center' in gdf.columns:
            print("   ✓ cooling_center column exists")
            cc_counts = gdf['cooling_center'].value_counts()
            print(f"   Top cooling centers: {cc_counts.head()}")
        else:
            print("   ✗ cooling_center column MISSING")
            print("   Available columns with 'cool' in name:")
            cool_cols = [col for col in gdf.columns if 'cool' in col.lower()]
            print(f"   {cool_cols}")
            
            # Check what values are in decision column besides 'stay'
            unique_decisions = gdf['decision'].unique()
            print(f"   Unique decisions: {unique_decisions}")
            
            # Check if decisions that aren't 'stay' contain cooling center names
            non_stay = gdf[gdf['decision'] != 'stay']['decision'].unique()
            print(f"   Non-stay decisions: {non_stay}")
        
        print("\n8. Memory usage:")
        memory_mb = gdf.memory_usage(deep=True).sum() / (1024*1024)
        print(f"   GDF memory usage: {memory_mb:.1f} MB")
        
        return gdf
        
    except Exception as e:
        print(f"\n❌ Error during debug: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    np.random.seed(42)  # For reproducible results
    gdf = debug_heat_event()
    
    if gdf is not None:
        print("\n=== DEBUG COMPLETED SUCCESSFULLY ===")
        print("You can now examine the 'gdf' variable to understand the structure")
    else:
        print("\n=== DEBUG FAILED ===")
        print("Check the error messages above")