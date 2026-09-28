#!/usr/bin/env python3
"""
Final optimized chunk-parallel heat risk model
Eliminates delays between runs by pre-allocating everything
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

# Model imports
import sys
from src import Parcel, HeatEvent

# Suppress warnings
warnings.filterwarnings('ignore')


def process_parcel_chunk(args):
    """
    Process a chunk of parcels - returns results as numpy arrays
    """
    chunk_id, chunk_indices, chunk_data, run_id, total_chunks = args
    
    start_time = time.time()
    
    try:
        # Pre-allocate result arrays
        chunk_size = len(chunk_data)
        indices = np.zeros(chunk_size, dtype=np.int32)
        decisions = np.full(chunk_size, 'stay', dtype='U50')
        probabilities = np.zeros(chunk_size, dtype=np.float32)
        
        # Create heat event instance
        heat_event = HeatEvent(100)
        heat_event.parcels = []
        
        # Process each row
        for i, (idx, row) in enumerate(chunk_data.iterrows()):
            # Store the original index
            indices[i] = chunk_indices[i]
            
            # Create parcel
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
                'AC': row.get('AC'),
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
        print(f"[Run {run_id}] Chunk {chunk_id}/{total_chunks} completed in {elapsed:.1f}s")
        
        # Return arrays with indices for direct placement
        return indices, decisions, probabilities
        
    except Exception as e:
        print(f"[Run {run_id}] Chunk {chunk_id} failed: {str(e)}")
        return None, None, None


class ChunkParallelHeatModel:
    def __init__(self, config):
        """Initialize chunk-parallel model"""
        self.config = config
        self.start_time = time.time()
        self.parcels_data = None
        self.results_wide = None
        
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
    
    def run_all_simulations(self):
        """Run all simulations with pre-allocated arrays for zero-copy storage"""
        num_runs = self.config['num_runs']
        num_chunks = self.config.get('max_workers', cpu_count())
        
        print(f"\n=== CHUNK-PARALLEL SIMULATION (ZERO-COPY VERSION) ===")
        print(f"Configuration:")
        print(f"  - Number of runs: {num_runs}")
        print(f"  - Chunks per run: {num_chunks}")
        print(f"  - System cores: {cpu_count()}")
        
        # Load data
        gdf = self.parcels_data['gdf']
        num_parcels = len(gdf)
        
        # PRE-ALLOCATE EVERYTHING
        print(f"\nPre-allocating all results...")
        init_start = time.time()
        
        # Create base DataFrame with just PIDs and geometry
        self.results_wide = pd.DataFrame({
            'pid': gdf['pid'].values,
            'geometry': gdf['geometry'].values
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
            
            chunk_df = gdf.iloc[start_idx:end_idx].copy()
            chunk_indices = np.arange(start_idx, end_idx)
            chunks_with_indices.append((i + 1, chunk_indices, chunk_df, num_chunks))
            
            start_idx = end_idx
        
        print(f"Created {num_chunks} chunks of ~{chunk_size:,} parcels each")
        
        # Run simulations
        all_stats = []
        
        for run_idx in range(num_runs):
            run_id = run_idx + 1
            run_start = time.time()
            
            print(f"\n=== Starting Run {run_id} ===")
            
            # Process chunks in parallel
            stayed_count = 0
            with ProcessPoolExecutor(max_workers=num_chunks) as executor:
                # Add run_id to chunk args
                chunk_args = [(c[0], c[1], c[2], run_id, c[3]) for c in chunks_with_indices]
                
                # Submit all chunks
                futures = [executor.submit(process_parcel_chunk, args) for args in chunk_args]
                
                # Collect results and directly store in pre-allocated arrays
                for future in as_completed(futures):
                    indices, decisions, probabilities = future.result()
                    
                    if indices is not None:
                        # Direct numpy assignment - no DataFrame operations!
                        all_decisions[indices, run_idx] = decisions
                        all_probabilities[indices, run_idx] = probabilities
                        stayed_count += np.sum(decisions == 'stay')
            
            # Calculate stats
            moved_count = num_parcels - stayed_count
            stats = {
                'run': run_id,
                'total_parcels': num_parcels,
                'stayed_home': stayed_count,
                'moved': moved_count,
                'stayed_home_pct': (stayed_count / num_parcels) * 100,
                'moved_pct': (moved_count / num_parcels) * 100
            }
            all_stats.append(stats)
            
            run_time = time.time() - run_start
            print(f"Run {run_id} completed in {run_time:.1f}s - {stats['moved_pct']:.1f}% moved")
            
            # Progress
            elapsed = time.time() - self.start_time
            avg_time = elapsed / run_id
            remaining = avg_time * (num_runs - run_id)
            print(f"Progress: {run_id}/{num_runs} | Total elapsed: {elapsed:.1f}s | ETA: {remaining:.1f}s")
        
        # Add arrays to DataFrame as columns
        print("\nFinalizing results...")
        for run_idx in range(num_runs):
            run_id = run_idx + 1
            self.results_wide[f'decision_run_{run_id}'] = all_decisions[:, run_idx]
            self.results_wide[f'proba_run_{run_id}'] = all_probabilities[:, run_idx]
        
        # Convert to GeoDataFrame
        self.results_wide = gpd.GeoDataFrame(self.results_wide, geometry='geometry', crs=gdf.crs)
        self.summary_stats = pd.DataFrame(all_stats)
        
        return num_runs, []
    
    def calculate_ensemble_results(self):
        """Calculate ensemble statistics from wide format results"""
        print("\nCalculating ensemble results...")
        
        num_runs = self.config['num_runs']
        
        # Get decision and probability columns
        decision_cols = [f'decision_run_{i}' for i in range(1, num_runs + 1)]
        proba_cols = [f'proba_run_{i}' for i in range(1, num_runs + 1)]
        
        # Calculate average probabilities
        self.results_wide['proba_mean'] = self.results_wide[proba_cols].mean(axis=1)
        self.results_wide['proba_std'] = self.results_wide[proba_cols].std(axis=1)
        
        # Calculate majority vote decisions
        print("Calculating majority vote decisions...")
        decisions_data = self.results_wide[decision_cols]
        
        # Count votes
        stay_votes = (decisions_data == 'stay').sum(axis=1)
        move_votes = len(decision_cols) - stay_votes
        
        # Majority decision
        self.results_wide['decision_majority'] = np.where(
            move_votes > stay_votes, 'move', 'stay'
        )
        
        # For move decisions, find the most common cooling center
        self.results_wide['cooling_center_majority'] = 'None'
        
        # Vectorized approach for finding most common cooling center
        moved_mask = self.results_wide['decision_majority'] == 'move'
        moved_indices = self.results_wide.index[moved_mask]
        
        if len(moved_indices) > 0:
            print(f"Processing cooling centers for {len(moved_indices)} moved parcels...")
            
            for idx in tqdm(moved_indices, desc="Processing cooling centers"):
                row_decisions = decisions_data.loc[idx]
                non_stay_decisions = row_decisions[row_decisions != 'stay']
                
                if len(non_stay_decisions) > 0:
                    most_common = non_stay_decisions.mode()
                    if len(most_common) > 0:
                        self.results_wide.loc[idx, 'cooling_center_majority'] = most_common.iloc[0]
        
        # Calculate decision stability
        self.results_wide['decision_stability'] = np.maximum(stay_votes, move_votes) / len(decision_cols)
        
        # Summary statistics
        total_parcels = len(self.results_wide)
        stayed_home = (self.results_wide['decision_majority'] == 'stay').sum()
        moved = total_parcels - stayed_home
        
        ensemble_stats = {
            'total_parcels': total_parcels,
            'stayed_home': stayed_home,
            'moved': moved,
            'stayed_home_pct': (stayed_home / total_parcels) * 100,
            'moved_pct': (moved / total_parcels) * 100,
            'avg_probability': self.results_wide['proba_mean'].mean(),
            'avg_stability': self.results_wide['decision_stability'].mean()
        }
        
        return ensemble_stats
    
    def save_results(self):
        """Save results in multiple formats"""
        print("\nSaving results...")
        
        output_dir = Path("../../output/results")
        output_dir.mkdir(exist_ok=True)
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        # Save wide format results
        wide_file = output_dir / f"results_wide_chunked_{timestamp}.pkl"
        with open(wide_file, 'wb') as f:
            pickle.dump({
                'results_wide': self.results_wide,
                'summary_stats': self.summary_stats,
                'config': self.config,
                'timestamp': timestamp
            }, f)
        print(f"✓ Wide format results saved: {wide_file}")
        
        # Save ensemble results
        ensemble_cols = [
            'pid', 'geometry', 'proba_mean', 'proba_std', 
            'decision_majority', 'cooling_center_majority', 'decision_stability'
        ]
        ensemble_gdf = self.results_wide[ensemble_cols].copy()
        
        # Rename for clarity
        ensemble_gdf = ensemble_gdf.rename(columns={
            'proba_mean': 'proba',
            'decision_majority': 'decision',
            'cooling_center_majority': 'cooling_center',
            'decision_stability': 'stability'
        })
        
        # Save as shapefile
        shapefile_path = output_dir / f"ensemble_results_chunked_{timestamp}.shp"
        ensemble_gdf.to_file(shapefile_path, driver='ESRI Shapefile')
        print(f"✓ Ensemble shapefile saved: {shapefile_path}")
        
        # Save summary statistics
        stats_file = output_dir / f"summary_stats_chunked_{timestamp}.csv"
        self.summary_stats.to_csv(stats_file, index=False)
        print(f"✓ Summary statistics saved: {stats_file}")
        
        return ensemble_gdf, wide_file, shapefile_path
    
    def run_complete_analysis(self):
        """Run the complete chunk-parallelized analysis"""
        try:
            print("=== CHUNK-PARALLEL HEAT RISK MODEL ===")
            
            # Load preprocessed data
            gdf = self.load_preprocessed_parcels()
            
            # Run all simulations with chunk parallelization
            completed_count, failed_runs = self.run_all_simulations()
            
            # Calculate ensemble results
            ensemble_stats = self.calculate_ensemble_results()
            
            # Save results
            ensemble_gdf, wide_file, shapefile_path = self.save_results()
            
            # Print summary
            elapsed_time = time.time() - self.start_time
            
            print("\n=== ANALYSIS COMPLETE ===")
            print(f"Runtime: {elapsed_time:.1f} seconds ({elapsed_time/60:.1f} minutes)")
            print(f"Average time per simulation: {elapsed_time/completed_count:.2f} seconds")
            
            # Compare to sequential baseline
            sequential_estimate = 60 * completed_count
            speedup = sequential_estimate / elapsed_time
            print(f"Estimated speedup vs sequential: {speedup:.1f}x")
            
            print(f"\nEnsemble Results:")
            print(f"  Stayed home: {ensemble_stats['stayed_home_pct']:.2f}%")
            print(f"  Moved to cooling centers: {ensemble_stats['moved_pct']:.2f}%")
            print(f"  Average probability: {ensemble_stats['avg_probability']:.3f}")
            print(f"  Average decision stability: {ensemble_stats['avg_stability']:.3f}")
            
            print(f"\nOutput files:")
            print(f"  📄 Wide format (detailed): {wide_file}")
            print(f"  🗺️  Ensemble shapefile: {shapefile_path}")
            
            return ensemble_gdf, self.results_wide, ensemble_stats
            
        except Exception as e:
            print(f"\n❌ Analysis failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return None, None, None


def main():
    """Main execution function"""
    
    # Configuration
    config = {
        'num_runs': 10,  # Number of simulations to run
        'max_workers': 15,  # Number of chunks/workers per simulation (use 15 to match your test)
    }
    
    print(f"🚀 CHUNK-PARALLEL HEAT RISK MODEL (FINAL VERSION)")
    print(f"Configuration: {config}")
    print(f"Expected performance:")
    print(f"  - Each simulation divided into {config['max_workers']} chunks")
    print(f"  - Each worker processes ~{399605//config['max_workers']:,} parcels")
    print(f"  - Zero-copy result storage")
    
    # Set working directory
    code_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(code_dir)
    print(f"Working directory: {os.getcwd()}")
    
    # Set random seed
    np.random.seed(42)
    
    # Run analysis
    model = ChunkParallelHeatModel(config)
    ensemble_gdf, results_wide, ensemble_stats = model.run_complete_analysis()
    
    if ensemble_gdf is not None:
        print(f"\n🎉 SUCCESS! Chunk-parallel execution completed.")
        print(f"📊 Results shape: {ensemble_gdf.shape}")
        
        # Show sample results
        print(f"\nSample results:")
        print(ensemble_gdf[['pid', 'proba', 'decision', 'stability']].head())
        
    return ensemble_gdf, results_wide, ensemble_stats


if __name__ == "__main__":
    freeze_support()
    
    start_time = time.time()
    ensemble_gdf, results_wide, ensemble_stats = main()
    total_time = time.time() - start_time
    
    print(f"\n⏱️ Total execution time: {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
    print("\n✅ Script completed successfully!")