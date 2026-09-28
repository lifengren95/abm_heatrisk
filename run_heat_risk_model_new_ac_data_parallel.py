#!/usr/bin/env python3
"""
Modified chunk-parallel heat risk model with external parcel-level AC data support
Processes multiple temperature rasters for different dates with custom AC data
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

# ============= NEW CONFIGURATION FOR AC DATA =============
USE_EXTERNAL_AC_DATA = True  # Set to False to use original database AC logic
AC_DATA_PATH = "../../data/raw/Parcel_AC/hennepin_parcel_ac_avail.csv"  # Relative path
# ========================================================


def load_external_ac_data(ac_data_path):
    """
    Load external AC data and create lookup dictionary
    Returns: dict {parcel_id: ac_status} where ac_status is 0 or 1
    """
    print(f"\nLoading external AC data from: {ac_data_path}")
    start_time = time.time()
    
    try:
        # Read CSV with REM_ACCT_NUM as string to preserve leading zeros
        ac_df = pd.read_csv(ac_data_path, dtype={'REM_ACCT_NUM': str})
        
        # Create AC lookup dictionary
        ac_lookup = {}
        
        # Count statistics
        yes_count = 0
        no_count = 0
        empty_count = 0
        
        for idx, row in ac_df.iterrows():
            parcel_id = str(row['REM_ACCT_NUM']).strip()
            ac_type = str(row.get('AC_TYPE', '')).strip().upper()
            
            if ac_type == 'YES':
                ac_lookup[parcel_id] = 1
                yes_count += 1
            elif ac_type == 'NO':
                ac_lookup[parcel_id] = 0
                no_count += 1
            else:  # Empty or other values - will use database fallback
                empty_count += 1
        
        load_time = time.time() - start_time
        
        print(f"✓ Loaded AC data in {load_time:.2f} seconds")
        print(f"  - Total parcels in AC file: {len(ac_df):,}")
        print(f"  - Parcels with AC='Yes': {yes_count:,} ({yes_count/len(ac_df)*100:.1f}%)")
        print(f"  - Parcels with AC='No': {no_count:,} ({no_count/len(ac_df)*100:.1f}%)")
        print(f"  - Parcels with empty/unknown AC: {empty_count:,} ({empty_count/len(ac_df)*100:.1f}%)")
        print(f"  - Valid AC entries in lookup: {len(ac_lookup):,}")
        
        return ac_lookup
        
    except Exception as e:
        print(f"❌ Error loading AC data: {str(e)}")
        print("   Falling back to database AC values for all parcels")
        return {}


# No longer using global variable - will pass AC lookup to workers


def extract_temperatures_from_raster(gdf, temp_raster_path):
    """Extract temperatures from raster for each parcel"""
    print(f"Extracting temperatures from: {temp_raster_path}")
    
    with rasterio.open(temp_raster_path) as src:
        # Get parcel centroids
        centroids = [(geom.centroid.x, geom.centroid.y) for geom in gdf.geometry]
        
        # Sample temperatures at centroid locations using rasterio's sample generator
        temps = list(src.sample(centroids))
        
        # Extract values, use 100 as fallback for nodata
        temperature_values = []
        for temp in temps:
            if temp[0] is not None and not np.isnan(temp[0]):
                temperature_values.append(float(temp[0]))
            else:
                temperature_values.append(100.0)  # Fallback temperature
        
        # Add to GeoDataFrame
        gdf['temperature'] = temperature_values
        
    temp_min = gdf['temperature'].min()
    temp_max = gdf['temperature'].max()
    temp_mean = gdf['temperature'].mean()
    
    print(f"Temperature stats - Min: {temp_min:.1f}°F, Max: {temp_max:.1f}°F, Mean: {temp_mean:.1f}°F")
    
    return gdf


def get_temperature_raster_path(date_str, temp_dir):
    """Construct temperature raster path for a given date"""
    # Expected pattern: tmax_hennepin_YYYYMMDD_500m.tif
    filename = f"tmax_hennepin_{date_str}_500m.tif"
    filepath = Path(temp_dir) / filename
    
    if not filepath.exists():
        raise FileNotFoundError(f"Temperature raster not found: {filepath}")
    
    return str(filepath)


def process_parcel_chunk(args):
    """
    Process a chunk of parcels - returns results as numpy arrays
    Modified to use external AC data when available
    """
    chunk_id, chunk_indices, chunk_data, run_id, total_chunks, use_external_ac, ac_lookup, ac_stats = args
    
    start_time = time.time()
    
    try:
        # Pre-allocate result arrays
        chunk_size = len(chunk_data)
        indices = np.zeros(chunk_size, dtype=np.int32)
        decisions = np.full(chunk_size, 'stay', dtype='U50')
        probabilities = np.zeros(chunk_size, dtype=np.float32)
        
        # Create heat event instance
        heat_event = HeatEvent(100)  # Default temperature
        heat_event.parcels = []
        
        # Track AC source statistics for this chunk
        external_ac_used = 0
        database_ac_used = 0
        
        # Process each row
        for i, (idx, row) in enumerate(chunk_data.iterrows()):
            # Store the original index
            indices[i] = chunk_indices[i]
            
            # Determine AC value
            original_ac = row.get('AC', 0)
            final_ac = original_ac  # Default to database value
            ac_source = 'database'
            
            if use_external_ac and ac_lookup:
                # Convert pid to string for matching
                pid_str = str(row['pid']).strip()
                
                # Check if we have external AC data for this parcel
                if pid_str in ac_lookup:
                    final_ac = ac_lookup[pid_str]
                    ac_source = 'external'
                    external_ac_used += 1
                else:
                    database_ac_used += 1
            else:
                database_ac_used += 1
            
            # Create parcel with potentially modified AC value
            attrs = {
                'geometry': row['geometry'],
                'medianhhi': row.get('medianhhi'),
                'ageunder18': row.get('ageunder18'),
                'age18_39': row.get('age18_39'),
                'age40_64': row.get('age40_64'),
                'age65up': row.get('age65up'),
                'pubtransit': row.get('pubtransit'),
                'povertyn': row.get('povertyn'),
                'poptotal': row.get('poptotal'),
                'popinhh': row.get('popinhh'),
                'avghhsize': row.get('avghhsize'),
                'AC': final_ac,  # Use the determined AC value
                'AC_source': ac_source,  # Track the source for debugging
                'temperature': row.get('temperature', 100),
                'block_group_id': row.get('block_group_id'),
                'household_income': row.get('household_income'),
                'total_pop': row.get('total_pop'),
                'pop_under_5': row.get('pop_under_5'),
                'pop_5_17': row.get('pop_5_17'),
                'pop_18_34': row.get('pop_18_34'),
                'pop_35_64': row.get('pop_35_64'),
                'pop_over_65': row.get('pop_over_65'),
                'ac_proba': row.get('ac_proba')
            }
            
            parcel = Parcel(
                parcel_id=row['pid'],
                nearest_cooling_centers=row.get('cooling_centers', []),
                cooling_distance=row.get('cooling_distance', 1000),
                attributes=attrs
            )
            heat_event.parcels.append(parcel)
        
        # Generate synthetic population
        heat_event.assign_synthetic_population()
        
        # Make decisions and store results directly
        for i, parcel in enumerate(heat_event.parcels):
            parcel.make_decision()
            decisions[i] = getattr(parcel, 'decision', 'stay')
            probabilities[i] = getattr(parcel, 'proba', 0.0)
        
        elapsed = time.time() - start_time
        print(f"[Run {run_id}] Chunk {chunk_id}/{total_chunks} completed in {elapsed:.1f}s "
              f"(External AC: {external_ac_used}, Database AC: {database_ac_used})")
        
        # Return arrays with indices for direct placement AND AC statistics
        return indices, decisions, probabilities, external_ac_used, database_ac_used
        
    except Exception as e:
        print(f"[Run {run_id}] Chunk {chunk_id} failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None, None, 0, 0


class ChunkParallelHeatModel:
    def __init__(self, config):
        """Initialize chunk-parallel model"""
        self.config = config
        self.start_time = time.time()
        self.parcels_data = None
        self.results_wide = None
        self.current_date = None
        self.ac_stats_total = {'external': 0, 'database': 0}  # Track AC source usage
        self.external_ac_lookup = None  # Store AC lookup here
        # Create trial folder with timestamp
        self.trial_folder = f"trial_{time.strftime('%Y%m%d_%H%M%S')}"
        
    def load_preprocessed_parcels(self):
        """Load preprocessed parcel data"""
        parcels_file = Path("../../data/preprocessed_data/parcels_prepared.pkl")
        
        if not parcels_file.exists():
            raise FileNotFoundError(
                f"Preprocessed parcels file not found: {parcels_file}\n"
                "Please run '01_extract_parcels_oneoff.py' first!"
            )
        
        print("Loading preprocessed parcel data...")
        start_time = time.time()
        
        with open(parcels_file, 'rb') as f:
            self.parcels_data = pickle.load(f)
        
        load_time = time.time() - start_time
        gdf = self.parcels_data['gdf']
        
        print(f"✓ Loaded {len(gdf)} parcels in {load_time:.3f} seconds")
        print(f"✓ Memory usage: {gdf.memory_usage(deep=True).sum() / (1024*1024):.1f} MB")
        
        return gdf
    
    def run_all_simulations_for_date(self, gdf_with_temps, date_str):
        """Run all simulations for a specific date with temperature data"""
        num_runs = self.config['num_runs']
        num_chunks = self.config.get('max_workers', cpu_count())
        
        print(f"\n=== CHUNK-PARALLEL SIMULATION FOR DATE: {date_str} ===")
        print(f"Configuration:")
        print(f"  - Number of runs: {num_runs}")
        print(f"  - Chunks per run: {num_chunks}")
        print(f"  - System cores: {cpu_count()}")
        print(f"  - Using external AC data: {USE_EXTERNAL_AC_DATA}")
        
        # Use the GDF with temperatures
        num_parcels = len(gdf_with_temps)
        
        # PRE-ALLOCATE EVERYTHING
        print(f"\nPre-allocating all results...")
        init_start = time.time()
        
        # Create base DataFrame with just PIDs and geometry
        self.results_wide = pd.DataFrame({
            'pid': gdf_with_temps['pid'].values,
            'geometry': gdf_with_temps['geometry'].values,
            'temperature': gdf_with_temps['temperature'].values,  # Add temperature
            'date': date_str
        }, index=range(num_parcels))
        
        # Pre-allocate numpy arrays for ALL runs
        all_decisions = np.full((num_parcels, num_runs), 'stay', dtype='U50')
        all_probabilities = np.zeros((num_parcels, num_runs), dtype=np.float32)
        
        init_time = time.time() - init_start
        print(f"Pre-allocation completed in {init_time:.2f}s")
        
        # Prepare chunks with their indices
        chunk_size = num_parcels // num_chunks
        remainder = num_parcels % num_chunks
        
        chunks_with_indices = []
        start_idx = 0
        
        for i in range(num_chunks):
            current_chunk_size = chunk_size + (1 if i < remainder else 0)
            end_idx = start_idx + current_chunk_size
            
            chunk_df = gdf_with_temps.iloc[start_idx:end_idx].copy()
            chunk_indices = np.arange(start_idx, end_idx)
            chunks_with_indices.append((i + 1, chunk_indices, chunk_df, num_chunks))
            
            start_idx = end_idx
        
        print(f"Created {num_chunks} chunks of ~{chunk_size:,} parcels each")
        
        # Run simulations
        all_stats = []
        
        # Reset AC statistics for this date
        self.ac_stats_total = {'external': 0, 'database': 0}
        
        for run_idx in range(num_runs):
            run_id = run_idx + 1
            run_start = time.time()
            
            print(f"\n=== Starting Run {run_id} for {date_str} ===")
            
            # AC statistics for this run
            ac_stats_run = {'external': 0, 'database': 0}
            
            # Process chunks in parallel
            stayed_count = 0
            with ProcessPoolExecutor(max_workers=num_chunks) as executor:
                # Add run_id and AC config to chunk args
                # Pass the actual AC lookup dictionary instead of ac_stats
                chunk_args = [(c[0], c[1], c[2], run_id, c[3], USE_EXTERNAL_AC_DATA, 
                              self.external_ac_lookup, None) for c in chunks_with_indices]
                
                # Submit all chunks
                futures = [executor.submit(process_parcel_chunk, args) for args in chunk_args]
                
                # Collect results and directly store in pre-allocated arrays
                for future in as_completed(futures):
                    indices, decisions, probabilities, ext_ac, db_ac = future.result()
                    
                    if indices is not None:
                        # Direct numpy assignment - no DataFrame operations!
                        all_decisions[indices, run_idx] = decisions
                        all_probabilities[indices, run_idx] = probabilities
                        stayed_count += np.sum(decisions == 'stay')
                        
                        # Update AC statistics from returned values
                        ac_stats_run['external'] += ext_ac
                        ac_stats_run['database'] += db_ac
            
            # Update total AC statistics
            self.ac_stats_total['external'] += ac_stats_run['external']
            self.ac_stats_total['database'] += ac_stats_run['database']
            
            # Calculate stats
            moved_count = num_parcels - stayed_count
            stats = {
                'date': date_str,
                'run': run_id,
                'total_parcels': num_parcels,
                'stayed_home': stayed_count,
                'moved': moved_count,
                'stayed_home_pct': (stayed_count / num_parcels) * 100,
                'moved_pct': (moved_count / num_parcels) * 100,
                'ac_external_used': ac_stats_run['external'],
                'ac_database_used': ac_stats_run['database']
            }
            all_stats.append(stats)
            
            run_time = time.time() - run_start
            print(f"Run {run_id} completed in {run_time:.1f}s - {stats['moved_pct']:.1f}% moved")
            
            # Progress
            elapsed = time.time() - self.start_time
            avg_time = elapsed / run_id
            remaining = avg_time * (num_runs - run_id)
            print(f"Progress: {run_id}/{num_runs} | Total elapsed: {elapsed:.1f}s | ETA: {remaining:.1f}s")
        
        # Print AC usage summary
        total_ac_assignments = self.ac_stats_total['external'] + self.ac_stats_total['database']
        if total_ac_assignments > 0:
            print(f"\nAC Data Source Summary for {date_str}:")
            print(f"  - External AC data used: {self.ac_stats_total['external']:,} "
                  f"({self.ac_stats_total['external']/total_ac_assignments*100:.1f}%)")
            print(f"  - Database AC data used: {self.ac_stats_total['database']:,} "
                  f"({self.ac_stats_total['database']/total_ac_assignments*100:.1f}%)")
        
        # Calculate ensemble statistics
        print("\nCalculating ensemble statistics...")
        self.results_wide['proba_mean'] = all_probabilities.mean(axis=1)
        self.results_wide['proba_std'] = all_probabilities.std(axis=1)
        self.results_wide['decision_majority'] = np.where(
            (all_decisions == 'stay').sum(axis=1) > num_runs / 2, 'stay', 'move'
        )
        self.results_wide['decision_stability'] = np.maximum(
            (all_decisions == 'stay').sum(axis=1),
            (all_decisions != 'stay').sum(axis=1)
        ) / num_runs
        
        # Store decisions for cooling center calculation
        self._all_decisions = all_decisions
        
        # Convert to GeoDataFrame
        self.results_wide = gpd.GeoDataFrame(self.results_wide, geometry='geometry', crs=gdf_with_temps.crs)
        self.summary_stats = pd.DataFrame(all_stats)
        
        return num_runs, []
    
    def calculate_ensemble_results(self):
        """Calculate ensemble statistics from wide format results"""
        print("\nFinalizing ensemble results...")
        
        # Calculate cooling centers for moved parcels
        self.results_wide['cooling_center'] = 'None'
        
        moved_mask = self.results_wide['decision_majority'] == 'move'
        moved_indices = self.results_wide.index[moved_mask]
        
        if len(moved_indices) > 0:
            print(f"Processing cooling centers for {len(moved_indices)} moved parcels...")
            
            for idx in tqdm(moved_indices, desc="Processing cooling centers"):
                row_decisions = self._all_decisions[idx]
                non_stay_decisions = row_decisions[row_decisions != 'stay']
                
                if len(non_stay_decisions) > 0:
                    unique, counts = np.unique(non_stay_decisions, return_counts=True)
                    most_common_idx = np.argmax(counts)
                    self.results_wide.loc[idx, 'cooling_center'] = unique[most_common_idx]
        
        # Summary statistics
        total_parcels = len(self.results_wide)
        stayed_home = (self.results_wide['decision_majority'] == 'stay').sum()
        moved = total_parcels - stayed_home
        
        ensemble_stats = {
            'date': self.current_date,
            'total_parcels': total_parcels,
            'stayed_home': stayed_home,
            'moved': moved,
            'stayed_home_pct': (stayed_home / total_parcels) * 100,
            'moved_pct': (moved / total_parcels) * 100,
            'avg_probability': self.results_wide['proba_mean'].mean(),
            'avg_stability': self.results_wide['decision_stability'].mean(),
            'avg_temperature': self.results_wide['temperature'].mean(),
            'ac_data_source': 'mixed' if USE_EXTERNAL_AC_DATA else 'database_only',
            'ac_external_pct': (self.ac_stats_total['external'] / 
                               (self.ac_stats_total['external'] + self.ac_stats_total['database']) * 100)
                               if (self.ac_stats_total['external'] + self.ac_stats_total['database']) > 0 else 0
        }
        
        return ensemble_stats
    
    def save_results(self, date_str):
        """Save ensemble results only"""
        print(f"\nSaving ensemble results for {date_str}...")
        
        # Create organized output directory structure
        base_output_dir = Path(f"../../output/results/{self.trial_folder}")
        date_output_dir = base_output_dir / date_str
        date_output_dir.mkdir(exist_ok=True, parents=True)
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        # Save ensemble shapefile for GIS visualization
        ensemble_cols = [
            'pid', 'geometry', 'temperature', 'proba_mean', 'proba_std', 
            'decision_majority', 'decision_stability', 'cooling_center'
        ]
        
        ensemble_gdf = self.results_wide[ensemble_cols].copy()
        
        # Rename for shapefile column limits
        ensemble_gdf = ensemble_gdf.rename(columns={
            'proba_mean': 'proba',
            'proba_std': 'proba_std',
            'decision_majority': 'decision',
            'decision_stability': 'stability',
            'temperature': 'temp',
            'cooling_center': 'cool_centr'
        })
        
        shapefile_path = date_output_dir / f"ensemble_{date_str}.shp"
        ensemble_gdf.to_file(shapefile_path, driver='ESRI Shapefile')
        print(f"✓ Ensemble shapefile saved: {shapefile_path}")
        
        # Save summary CSV (without geometry)
        summary_df = self.results_wide.drop('geometry', axis=1)
        summary_file = date_output_dir / f"ensemble_summary_{date_str}.csv"
        summary_df.to_csv(summary_file, index=False)
        print(f"✓ Summary CSV saved: {summary_file}")
        
        # Save run statistics
        stats_file = date_output_dir / f"run_statistics_{date_str}.csv"
        self.summary_stats.to_csv(stats_file, index=False)
        print(f"✓ Run statistics saved: {stats_file}")
        
        # Save metadata with AC information
        metadata_file = date_output_dir / f"metadata_{date_str}.json"
        metadata = {
            'date': date_str,
            'timestamp': timestamp,
            'num_parcels': len(self.results_wide),
            'num_runs': self.config['num_runs'],
            'ac_data_config': {
                'use_external_ac': USE_EXTERNAL_AC_DATA,
                'external_ac_file': AC_DATA_PATH if USE_EXTERNAL_AC_DATA else None,
                'ac_assignments': {
                    'external': self.ac_stats_total['external'],
                    'database': self.ac_stats_total['database'],
                    'external_percentage': (self.ac_stats_total['external'] / 
                                          (self.ac_stats_total['external'] + self.ac_stats_total['database']) * 100)
                                          if (self.ac_stats_total['external'] + self.ac_stats_total['database']) > 0 else 0
                }
            },
            'avg_temperature': float(self.results_wide['temperature'].mean()),
            'temperature_range': {
                'min': float(self.results_wide['temperature'].min()),
                'max': float(self.results_wide['temperature'].max())
            },
            'movement_stats': {
                'moved_pct': float((self.results_wide['decision_majority'] == 'move').sum() / len(self.results_wide) * 100),
                'stayed_pct': float((self.results_wide['decision_majority'] == 'stay').sum() / len(self.results_wide) * 100),
                'avg_probability': float(self.results_wide['proba_mean'].mean()),
                'avg_stability': float(self.results_wide['decision_stability'].mean())
            }
        }
        
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"✓ Metadata saved: {metadata_file}")
        
        return ensemble_gdf, summary_file, shapefile_path
    
    def run_analysis_for_dates(self, dates_list, temp_dir):
        """Run analysis for multiple dates"""
        all_results = []
        all_ensemble_stats = []
        
        # Load external AC data once if configured
        if USE_EXTERNAL_AC_DATA:
            ac_file_path = Path(AC_DATA_PATH)
            if ac_file_path.exists():
                self.external_ac_lookup = load_external_ac_data(ac_file_path)
            else:
                print(f"❌ AC data file not found: {ac_file_path}")
                print("   Using database AC values for all parcels")
                self.external_ac_lookup = {}
        
        # Load base parcel data once
        base_gdf = self.load_preprocessed_parcels()
        
        for date_str in dates_list:
            try:
                print(f"\n{'='*60}")
                print(f"Processing date: {date_str}")
                print(f"{'='*60}")
                
                self.current_date = date_str
                
                # Get temperature raster path
                temp_raster_path = get_temperature_raster_path(date_str, temp_dir)
                
                # Extract temperatures for this date
                gdf_with_temps = base_gdf.copy()
                gdf_with_temps = extract_temperatures_from_raster(gdf_with_temps, temp_raster_path)
                
                # Run simulations for this date
                completed_count, failed_runs = self.run_all_simulations_for_date(gdf_with_temps, date_str)
                
                # Calculate ensemble results
                ensemble_stats = self.calculate_ensemble_results()
                all_ensemble_stats.append(ensemble_stats)
                
                # Save results for this date
                ensemble_gdf, summary_file, shapefile_path = self.save_results(date_str)
                
                all_results.append({
                    'date': date_str,
                    'ensemble_gdf': ensemble_gdf,
                    'ensemble_stats': ensemble_stats,
                    'output_files': {
                        'summary_file': summary_file,
                        'shapefile': shapefile_path
                    }
                })
                
                print(f"\n✓ Completed processing for {date_str}")
                print(f"  - Moved to cooling centers: {ensemble_stats['moved_pct']:.2f}%")
                print(f"  - Average temperature: {ensemble_stats['avg_temperature']:.1f}°F")
                if USE_EXTERNAL_AC_DATA:
                    print(f"  - External AC data used: {ensemble_stats['ac_external_pct']:.1f}%")
                
                # Clear memory after each date
                del gdf_with_temps
                gc.collect()
                
            except Exception as e:
                print(f"\n❌ Failed to process {date_str}: {str(e)}")
                import traceback
                traceback.print_exc()
                continue
        
        # Save combined summary
        if all_ensemble_stats:
            trial_dir = Path(f"../../output/results/{self.trial_folder}")
            combined_stats_df = pd.DataFrame(all_ensemble_stats)
            combined_stats_file = trial_dir / f"combined_summary_all_dates.csv"
            combined_stats_df.to_csv(combined_stats_file, index=False)
            print(f"\n✓ Combined summary saved: {combined_stats_file}")
            
            # Create main README
            readme_file = trial_dir / "README.txt"
            with open(readme_file, 'w') as f:
                f.write(f"Heat Risk Model Results - {self.trial_folder}\n")
                f.write("="*60 + "\n\n")
                f.write(f"Analysis completed: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Number of runs per date: {self.config['num_runs']}\n")
                f.write(f"Dates processed: {len(all_results)}\n")
                f.write(f"AC Data Configuration:\n")
                f.write(f"  - Using external AC data: {USE_EXTERNAL_AC_DATA}\n")
                if USE_EXTERNAL_AC_DATA:
                    f.write(f"  - External AC file: {AC_DATA_PATH}\n")
                    if self.external_ac_lookup:
                        f.write(f"  - Parcels with external AC data: {len(self.external_ac_lookup):,}\n")
                f.write("\nSummary by date:\n")
                f.write("-"*60 + "\n")
                for result in all_results:
                    stats = result['ensemble_stats']
                    f.write(f"\n{result['date']}:\n")
                    f.write(f"  Average Temperature: {stats['avg_temperature']:.1f}°F\n")
                    f.write(f"  Moved to cooling centers: {stats['moved_pct']:.2f}%\n")
                    f.write(f"  Stayed home: {stats['stayed_home_pct']:.2f}%\n")
                    f.write(f"  Decision stability: {stats['avg_stability']:.3f}\n")
                    if USE_EXTERNAL_AC_DATA:
                        f.write(f"  External AC data used: {stats['ac_external_pct']:.1f}%\n")
                
                f.write("\n" + "="*60 + "\n")
                f.write("File descriptions:\n")
                f.write("- ensemble_YYYYMMDD.shp: GIS visualization file\n")
                f.write("- ensemble_summary_YYYYMMDD.csv: Detailed results per parcel\n")
                f.write("- run_statistics_YYYYMMDD.csv: Statistics for each model run\n")
                f.write("- metadata_YYYYMMDD.json: Run configuration and summary\n")
        
        return all_results


def main():
    """Main execution function"""
    
    # Configuration
    config = {
        'num_runs': 5,  # Number of simulations to run per date
        'max_workers': 15,  # Number of chunks/workers per simulation
        'temp_dir': "../../data/validate_data/intermediate/prism",  # Temperature raster directory
        'dates': []  # Will be filled by date range below
    }
    
    # Generate date range
    start_date = datetime(2021, 7, 1)
    end_date = datetime(2021, 7, 31)
    date_range = []
    current_date = start_date
    while current_date <= end_date:
        date_range.append(current_date.strftime('%Y%m%d'))
        current_date += timedelta(days=1)
    config['dates'] = date_range
    
    print(f"🚀 CHUNK-PARALLEL HEAT RISK MODEL WITH EXTERNAL AC DATA")
    print(f"Configuration:")
    print(f"  - Number of runs per date: {config['num_runs']}")
    print(f"  - Parallel workers: {config['max_workers']}")
    print(f"  - Dates to process: {len(config['dates'])}")
    print(f"  - Date range: {config['dates'][0]} to {config['dates'][-1]}")
    print(f"  - External AC data: {'ENABLED' if USE_EXTERNAL_AC_DATA else 'DISABLED'}")
    if USE_EXTERNAL_AC_DATA:
        print(f"  - AC data file: {AC_DATA_PATH}")
    
    # Set working directory
    code_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(code_dir)
    print(f"Working directory: {os.getcwd()}")
    
    # Set random seed
    np.random.seed(42)
    
    # Run analysis
    model = ChunkParallelHeatModel(config)
    print(f"\nOutput will be saved to: ../../output/results/{model.trial_folder}/")
    
    all_results = model.run_analysis_for_dates(config['dates'], config['temp_dir'])
    
    # Print final summary
    print("\n" + "="*60)
    print("FINAL SUMMARY - ALL DATES")
    print("="*60)
    
    if all_results:
        for result in all_results:
            stats = result['ensemble_stats']
            print(f"\nDate: {result['date']}")
            print(f"  - Average Temperature: {stats['avg_temperature']:.1f}°F")
            print(f"  - Stayed home: {stats['stayed_home_pct']:.2f}%")
            print(f"  - Moved to cooling centers: {stats['moved_pct']:.2f}%")
            print(f"  - Average probability: {stats['avg_probability']:.3f}")
            print(f"  - Decision stability: {stats['avg_stability']:.3f}")
            if USE_EXTERNAL_AC_DATA:
                print(f"  - External AC data coverage: {stats['ac_external_pct']:.1f}%")
        
        print(f"\n📁 All results saved in: ../../output/results/{model.trial_folder}/")
    
    return all_results


if __name__ == "__main__":
    freeze_support()
    
    start_time = time.time()
    all_results = main()
    total_time = time.time() - start_time
    
    print(f"\n⏱️ Total execution time: {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
    print(f"⏱️ Processed {len(all_results)} dates successfully")
    print("\n✅ Script completed successfully!")