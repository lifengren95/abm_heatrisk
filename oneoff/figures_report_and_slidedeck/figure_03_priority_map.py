#!/usr/bin/env python3
"""
Parcel Vulnerability Priority Mapping Script
Generates priority maps based on weighted combination of vulnerability factors:
- Economic vulnerability (low income)
- Demographic vulnerability (elderly population)
- Infrastructure vulnerability (AC availability)
- Geographic vulnerability (cooling distance)
"""

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.colors import ListedColormap, BoundaryNorm, Normalize
from matplotlib.colorbar import ColorbarBase
from matplotlib_scalebar.scalebar import ScaleBar
import seaborn as sns
import pickle
from pathlib import Path
import warnings
import time
from scipy import stats as scipy_stats
from scipy.stats import percentileofscore
import json
from sklearn.preprocessing import MinMaxScaler

warnings.filterwarnings('ignore')

# Set matplotlib parameters for Nature publication style
plt.rcParams['font.family'] = 'Arial'
plt.rcParams['font.size'] = 10
plt.rcParams['axes.labelsize'] = 10
plt.rcParams['axes.titlesize'] = 12
plt.rcParams['xtick.labelsize'] = 9
plt.rcParams['ytick.labelsize'] = 9
plt.rcParams['legend.fontsize'] = 9
plt.rcParams['figure.titlesize'] = 12


class VulnerabilityPriorityMapper:
    def __init__(self):
        """Initialize paths and settings"""
        # Data paths
        self.parcels_path = r"~\hennepin\data\preprocessed_data\parcels_prepared.pkl"
        self.ac_data_path = r"~\hennepin\data\raw\Parcel_AC\hennepin_parcel_ac_avail.csv"
        
        # Output paths
        self.output_dir = Path(r"~\hennepin\output")
        self.figures_dir = self.output_dir / "figures" / "priority_maps"
        self.stats_dir = self.output_dir / "statistics" / "priority_analysis"
        
        # Create directories if they don't exist
        self.figures_dir.mkdir(parents=True, exist_ok=True)
        self.stats_dir.mkdir(parents=True, exist_ok=True)
        
        # Nature publication settings
        self.figure_dpi = 300
        self.figure_size = (10, 12)
        self.font_size = 10
        self.title_size = 12
        
        # Define weight scenarios
        self.weight_scenarios = {
            'equal': {
                'name': 'Equal Weights',
                'income': 0.25,
                'elderly': 0.25,
                'ac': 0.25,
                'distance': 0.25
            },
            'ac_focused': {
                'name': 'AC-Focused',
                'income': 0.2,
                'elderly': 0.2,
                'ac': 0.4,
                'distance': 0.2
            },
            'elderly_focused': {
                'name': 'Elderly-Focused',
                'income': 0.2,
                'elderly': 0.4,
                'ac': 0.3,
                'distance': 0.1
            },
            'economic_focused': {
                'name': 'Economic-Focused',
                'income': 0.4,
                'elderly': 0.2,
                'ac': 0.3,
                'distance': 0.1
            },
            'comprehensive': {
                'name': 'Comprehensive (No Distance)',
                'income': 0.33,
                'elderly': 0.33,
                'ac': 0.34,
                'distance': 0.0
            }
        }
        
        # Priority level thresholds (percentiles)
        self.priority_levels = {
            'Critical': (95, 100),     # Top 5%
            'Very High': (85, 95),      # 85-95%
            'High': (70, 85),           # 70-85%
            'Medium': (50, 70),         # 50-70%
            'Low': (0, 50)              # Bottom 50%
        }
        
        # Color scheme for priority levels
        self.priority_colors = {
            'Critical': '#67000d',     # Dark red
            'Very High': '#a50f15',    # Red
            'High': '#ef3b2c',         # Light red
            'Medium': '#fc9272',       # Orange
            'Low': '#fee0d2',          # Light pink
            'No Data': '#CCCCCC'       # Grey
        }
        
        print("="*60)
        print("VULNERABILITY PRIORITY MAPPING SYSTEM")
        print("="*60)
        print(f"Output directories created:")
        print(f"  Figures: {self.figures_dir}")
        print(f"  Statistics: {self.stats_dir}")
        print(f"\nWeight scenarios defined: {', '.join(self.weight_scenarios.keys())}")
    
    def load_parcel_data(self):
        """Load preprocessed parcel data"""
        print("\n1. Loading parcel data...")
        start_time = time.time()
        
        if not Path(self.parcels_path).exists():
            raise FileNotFoundError(f"Parcel data not found: {self.parcels_path}")
        
        with open(self.parcels_path, 'rb') as f:
            data = pickle.load(f)
        
        gdf = data['gdf']
        load_time = time.time() - start_time
        
        print(f"   ✓ Loaded {len(gdf)} parcels in {load_time:.2f} seconds")
        print(f"   ✓ CRS: {gdf.crs}")
        
        return gdf
    
    def load_external_ac_data(self):
        """Load external AC data"""
        print("\n2. Loading external AC data...")
        ac_lookup = {}
        
        try:
            if not Path(self.ac_data_path).exists():
                print(f"   ⚠ AC data file not found: {self.ac_data_path}")
                return ac_lookup
            
            ac_df = pd.read_csv(self.ac_data_path, dtype={'REM_ACCT_NUM': str})
            
            for idx, row in ac_df.iterrows():
                parcel_id = str(row['REM_ACCT_NUM']).strip()
                ac_type = str(row.get('AC_TYPE', '')).strip().upper()
                
                if ac_type == 'YES':
                    ac_lookup[parcel_id] = 1
                elif ac_type == 'NO':
                    ac_lookup[parcel_id] = 0
            
            print(f"   ✓ Loaded AC data for {len(ac_lookup):,} parcels")
            return ac_lookup
            
        except Exception as e:
            print(f"   ❌ Error loading AC data: {str(e)}")
            return {}
    
    def calculate_median_age(self, row):
        """Calculate weighted median age estimate"""
        try:
            if 'ageunder18' in row.index:
                midpoints = {
                    'ageunder18': 9,
                    'age18_39': 28.5,
                    'age40_64': 52,
                    'age65up': 75
                }
            elif 'pop_under_5' in row.index:
                midpoints = {
                    'pop_under_5': 2.5,
                    'pop_5_17': 11,
                    'pop_18_34': 26,
                    'pop_35_64': 49.5,
                    'pop_over_65': 75
                }
            else:
                return np.nan
            
            total_pop = 0
            weighted_sum = 0
            
            for col, midpoint in midpoints.items():
                pop = row.get(col, 0)
                if pd.notna(pop) and pop > 0:
                    weighted_sum += pop * midpoint
                    total_pop += pop
            
            if total_pop > 0:
                return weighted_sum / total_pop
            else:
                return np.nan
        except:
            return np.nan
    
    def calculate_elderly_pct(self, row):
        """Calculate elderly percentage"""
        try:
            if 'age65up' in row.index:
                pop_over_65 = row.get('age65up', 0)
                total_pop = row.get('poptotal', 0)
            elif 'pop_over_65' in row.index:
                pop_over_65 = row.get('pop_over_65', 0)
                total_pop = row.get('total_pop', 0)
            else:
                return np.nan
            
            if pd.notna(pop_over_65) and pd.notna(total_pop) and total_pop > 0:
                return (pop_over_65 / total_pop) * 100
            else:
                return np.nan
        except:
            return np.nan
    
    def prepare_vulnerability_factors(self, gdf, ac_lookup):
        """Prepare and normalize vulnerability factors"""
        print("\n3. Preparing vulnerability factors...")
        
        # Calculate age variables
        print("   Calculating demographic variables...")
        gdf['elderly_pct'] = gdf.apply(self.calculate_elderly_pct, axis=1)
        
        # Process income (already in database)
        print("   Processing income data...")
        gdf['income'] = gdf['medianhhi']
        
        # Integrate AC data
        print("   Integrating AC data...")
        gdf['AC_final'] = gdf['AC'].copy()
        for idx, row in gdf.iterrows():
            pid_str = str(row['pid']).strip()
            if pid_str in ac_lookup:
                gdf.at[idx, 'AC_final'] = ac_lookup[pid_str]
        
        # Convert cooling distance to miles
        print("   Processing cooling distance...")
        gdf['cooling_distance_miles'] = gdf['cooling_distance'] * 0.000621371
        gdf.loc[gdf['cooling_distance_miles'] > 100, 'cooling_distance_miles'] = np.nan
        
        # Filter to residential parcels with population
        print("   Filtering to residential parcels...")
        initial_count = len(gdf)
        
        # Keep only residential parcels with population > 0
        if 'poptotal' in gdf.columns:
            gdf = gdf[(gdf['poptotal'] > 0) & (gdf['poptotal'].notna())]
        elif 'total_pop' in gdf.columns:
            gdf = gdf[(gdf['total_pop'] > 0) & (gdf['total_pop'].notna())]
        
        filtered_count = len(gdf)
        print(f"   ✓ Filtered from {initial_count:,} to {filtered_count:,} residential parcels")
        
        # Create normalized scores
        print("\n   Normalizing vulnerability factors...")
        
        # Income score (inverse - lower income = higher vulnerability)
        income_valid = gdf['income'].notna()
        if income_valid.sum() > 0:
            income_min = gdf.loc[income_valid, 'income'].quantile(0.01)
            income_max = gdf.loc[income_valid, 'income'].quantile(0.99)
            gdf['income_score'] = 1 - ((gdf['income'] - income_min) / (income_max - income_min))
            gdf['income_score'] = gdf['income_score'].clip(0, 1)
        else:
            gdf['income_score'] = np.nan
        
        # Elderly score (direct - higher elderly % = higher vulnerability)
        elderly_valid = gdf['elderly_pct'].notna()
        if elderly_valid.sum() > 0:
            elderly_min = 0  # Use 0 as minimum
            elderly_max = gdf.loc[elderly_valid, 'elderly_pct'].quantile(0.99)
            gdf['elderly_score'] = (gdf['elderly_pct'] - elderly_min) / (elderly_max - elderly_min)
            gdf['elderly_score'] = gdf['elderly_score'].clip(0, 1)
        else:
            gdf['elderly_score'] = np.nan
        
        # AC score (binary - no AC = 1, has AC = 0)
        gdf['ac_score'] = 1 - gdf['AC_final']  # Invert so no AC = higher vulnerability
        
        # Distance score (direct - farther = higher vulnerability)
        distance_valid = gdf['cooling_distance_miles'].notna()
        if distance_valid.sum() > 0:
            dist_min = gdf.loc[distance_valid, 'cooling_distance_miles'].quantile(0.01)
            dist_max = gdf.loc[distance_valid, 'cooling_distance_miles'].quantile(0.99)
            gdf['distance_score'] = (gdf['cooling_distance_miles'] - dist_min) / (dist_max - dist_min)
            gdf['distance_score'] = gdf['distance_score'].clip(0, 1)
        else:
            gdf['distance_score'] = np.nan
        
        # Print summary
        print("\n   Factor summary (normalized scores):")
        for factor in ['income_score', 'elderly_score', 'ac_score', 'distance_score']:
            valid = gdf[factor].notna().sum()
            if valid > 0:
                mean_val = gdf[factor].mean()
                median_val = gdf[factor].median()
                print(f"     {factor}: Valid={valid:,}, Mean={mean_val:.3f}, Median={median_val:.3f}")
        
        return gdf
    
    def calculate_priority_scores(self, gdf, scenario_key='equal'):
        """Calculate weighted priority scores for a given scenario"""
        print(f"\n4. Calculating priority scores ({scenario_key} scenario)...")
        
        weights = self.weight_scenarios[scenario_key]
        
        # Create a mask for valid data (all factors present)
        valid_mask = (
            gdf['income_score'].notna() & 
            gdf['elderly_score'].notna() & 
            gdf['ac_score'].notna() & 
            gdf['distance_score'].notna()
        )
        
        # Calculate weighted score
        gdf[f'priority_score_{scenario_key}'] = np.nan
        
        gdf.loc[valid_mask, f'priority_score_{scenario_key}'] = (
            weights['income'] * gdf.loc[valid_mask, 'income_score'] +
            weights['elderly'] * gdf.loc[valid_mask, 'elderly_score'] +
            weights['ac'] * gdf.loc[valid_mask, 'ac_score'] +
            weights['distance'] * gdf.loc[valid_mask, 'distance_score']
        )
        
        # Calculate percentiles for valid scores
        valid_scores = gdf.loc[valid_mask, f'priority_score_{scenario_key}']
        
        # Assign priority levels based on percentiles
        gdf[f'priority_level_{scenario_key}'] = 'No Data'
        
        for level, (low_pct, high_pct) in self.priority_levels.items():
            if len(valid_scores) > 0:
                low_threshold = np.percentile(valid_scores, low_pct)
                high_threshold = np.percentile(valid_scores, high_pct)
                
                mask = (
                    (gdf[f'priority_score_{scenario_key}'] >= low_threshold) & 
                    (gdf[f'priority_score_{scenario_key}'] < high_threshold)
                )
                
                # Handle the top category
                if level == 'Critical':
                    mask = gdf[f'priority_score_{scenario_key}'] >= low_threshold
                
                gdf.loc[mask, f'priority_level_{scenario_key}'] = level
        
        # Print summary
        print(f"   ✓ Scores calculated for {valid_mask.sum():,} parcels")
        print(f"   ✓ Missing data for {(~valid_mask).sum():,} parcels")
        
        # Distribution summary
        level_counts = gdf[f'priority_level_{scenario_key}'].value_counts()
        print("\n   Priority level distribution:")
        for level in ['Critical', 'Very High', 'High', 'Medium', 'Low', 'No Data']:
            if level in level_counts.index:
                count = level_counts[level]
                pct = (count / len(gdf)) * 100
                print(f"     {level}: {count:,} ({pct:.1f}%)")
        
        return gdf
    
    def add_north_arrow(self, ax, x=0.95, y=0.95):
        """Add a north arrow to the map"""
        arrow = FancyArrowPatch(
            (x, y-0.02), (x, y+0.02),
            transform=ax.transAxes,
            arrowstyle='-|>',
            mutation_scale=20,
            lw=2,
            color='black'
        )
        ax.add_patch(arrow)
        ax.text(x, y+0.03, 'N', transform=ax.transAxes, 
                ha='center', fontsize=12, fontweight='bold')
    
    def create_priority_map(self, gdf, scenario_key, output_name):
        """Create priority map for a given scenario"""
        print(f"   Creating priority map: {output_name}...")
        
        fig, ax = plt.subplots(figsize=self.figure_size, dpi=self.figure_dpi)
        
        score_col = f'priority_score_{scenario_key}'
        level_col = f'priority_level_{scenario_key}'
        
        # Plot each priority level
        for level in ['Low', 'Medium', 'High', 'Very High', 'Critical', 'No Data']:
            mask = gdf[level_col] == level
            if mask.sum() > 0:
                gdf[mask].plot(
                    ax=ax,
                    color=self.priority_colors[level],
                    edgecolor='none',
                    linewidth=0
                )
        
        # Add title
        scenario_name = self.weight_scenarios[scenario_key]['name']
        ax.set_title(f'Vulnerability Priority Map - {scenario_name}', 
                    fontsize=self.title_size, fontweight='bold', pad=20)
        
        # Remove axes
        ax.set_axis_off()
        
        # Create legend
        legend_elements = []
        level_counts = gdf[level_col].value_counts()
        
        for level in ['Critical', 'Very High', 'High', 'Medium', 'Low', 'No Data']:
            if level in level_counts.index:
                count = level_counts[level]
                pct = (count / len(gdf)) * 100
                legend_elements.append(
                    mpatches.Patch(color=self.priority_colors[level], 
                                 label=f'{level} ({pct:.1f}%)')
                )
        
        ax.legend(handles=legend_elements, loc='lower left', frameon=True, 
                 fancybox=True, shadow=True, fontsize=9, title='Priority Level')
        
        # Add scale bar
        scalebar = ScaleBar(1, 'm', length_fraction=0.15, location='lower right',
                           box_alpha=0.8, pad=0.5, sep=2, 
                           font_properties={'size': 9})
        ax.add_artist(scalebar)
        
        # Add north arrow
        self.add_north_arrow(ax)
        
        # Add weights text
        weights = self.weight_scenarios[scenario_key]
        weights_text = (
            f"Weights: Income={weights['income']:.2f}, "
            f"Elderly={weights['elderly']:.2f}, "
            f"AC={weights['ac']:.2f}, "
            f"Distance={weights['distance']:.2f}"
        )
        ax.text(0.02, 0.95, weights_text, transform=ax.transAxes, 
               fontsize=8, bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        # Add data source
        ax.text(0.98, 0.02, 'Data: Hennepin County Parcels', 
               transform=ax.transAxes, fontsize=7,
               ha='right', style='italic', alpha=0.7)
        
        # Tight layout
        plt.tight_layout()
        
        # Save figure
        output_path = self.figures_dir / output_name
        plt.savefig(output_path, dpi=self.figure_dpi, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        plt.close()
        
        print(f"   ✓ Saved: {output_path}")
    
    def create_component_contribution_map(self, gdf, scenario_key):
        """Create a map showing which component contributes most to each parcel's score"""
        print(f"   Creating component contribution map...")
        
        fig, ax = plt.subplots(figsize=self.figure_size, dpi=self.figure_dpi)
        
        weights = self.weight_scenarios[scenario_key]
        
        # Calculate weighted contributions
        gdf['contrib_income'] = weights['income'] * gdf['income_score']
        gdf['contrib_elderly'] = weights['elderly'] * gdf['elderly_score']
        gdf['contrib_ac'] = weights['ac'] * gdf['ac_score']
        gdf['contrib_distance'] = weights['distance'] * gdf['distance_score']
        
        # Find dominant factor for each parcel
        contrib_cols = ['contrib_income', 'contrib_elderly', 'contrib_ac', 'contrib_distance']
        gdf['dominant_factor'] = gdf[contrib_cols].idxmax(axis=1)
        gdf['dominant_factor'] = gdf['dominant_factor'].str.replace('contrib_', '')
        
        # Color scheme for factors
        factor_colors = {
            'income': '#e41a1c',      # Red
            'elderly': '#377eb8',     # Blue
            'ac': '#4daf4a',          # Green
            'distance': '#984ea3'     # Purple
        }
        
        # Plot each factor
        for factor, color in factor_colors.items():
            mask = gdf['dominant_factor'] == factor
            if mask.sum() > 0:
                gdf[mask].plot(ax=ax, color=color, edgecolor='none', linewidth=0)
        
        # Plot no data
        no_data_mask = gdf[f'priority_score_{scenario_key}'].isna()
        if no_data_mask.sum() > 0:
            gdf[no_data_mask].plot(ax=ax, color='#CCCCCC', edgecolor='none', linewidth=0)
        
        # Add title
        scenario_name = self.weight_scenarios[scenario_key]['name']
        ax.set_title(f'Dominant Vulnerability Factor - {scenario_name}', 
                    fontsize=self.title_size, fontweight='bold', pad=20)
        
        # Remove axes
        ax.set_axis_off()
        
        # Create legend
        legend_elements = []
        factor_counts = gdf['dominant_factor'].value_counts()
        
        for factor in ['income', 'elderly', 'ac', 'distance']:
            if factor in factor_counts.index:
                count = factor_counts[factor]
                pct = (count / len(gdf[~no_data_mask])) * 100
                legend_elements.append(
                    mpatches.Patch(color=factor_colors[factor], 
                                 label=f'{factor.capitalize()} ({pct:.1f}%)')
                )
        
        if no_data_mask.sum() > 0:
            legend_elements.append(
                mpatches.Patch(color='#CCCCCC', 
                             label=f'No Data ({no_data_mask.sum()/len(gdf)*100:.1f}%)')
            )
        
        ax.legend(handles=legend_elements, loc='lower left', frameon=True, 
                 fancybox=True, shadow=True, fontsize=9, title='Dominant Factor')
        
        # Add scale bar
        scalebar = ScaleBar(1, 'm', length_fraction=0.15, location='lower right',
                           box_alpha=0.8, pad=0.5, sep=2, 
                           font_properties={'size': 9})
        ax.add_artist(scalebar)
        
        # Add north arrow
        self.add_north_arrow(ax)
        
        # Tight layout
        plt.tight_layout()
        
        # Save figure
        output_path = self.figures_dir / f'component_contribution_{scenario_key}.png'
        plt.savefig(output_path, dpi=self.figure_dpi, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        plt.close()
        
        print(f"   ✓ Saved: {output_path}")
    
    def create_comparison_matrix(self, gdf):
        """Create a comparison matrix showing correlations between scenarios"""
        print("\n6. Creating scenario comparison matrix...")
        
        # Collect all priority scores
        score_cols = [f'priority_score_{key}' for key in self.weight_scenarios.keys()]
        score_data = gdf[score_cols].dropna()
        
        # Rename columns for better display
        rename_dict = {f'priority_score_{key}': self.weight_scenarios[key]['name'] 
                      for key in self.weight_scenarios.keys()}
        score_data = score_data.rename(columns=rename_dict)
        
        # Calculate correlation matrix
        corr_matrix = score_data.corr()
        
        # Create heatmap
        fig, ax = plt.subplots(figsize=(10, 8), dpi=self.figure_dpi)
        
        sns.heatmap(corr_matrix, annot=True, fmt='.3f', cmap='RdBu_r', 
                   center=0.5, vmin=0, vmax=1,
                   square=True, linewidths=0.5, cbar_kws={"shrink": 0.8})
        
        ax.set_title('Priority Score Correlation Between Scenarios', 
                    fontsize=self.title_size, fontweight='bold', pad=20)
        
        plt.tight_layout()
        
        # Save figure
        output_path = self.figures_dir / 'scenario_correlation_matrix.png'
        plt.savefig(output_path, dpi=self.figure_dpi, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        plt.close()
        
        print(f"   ✓ Correlation matrix saved: {output_path}")
        
        return corr_matrix
    
    def calculate_statistics(self, gdf):
        """Calculate comprehensive statistics for all scenarios"""
        print("\n7. Calculating comprehensive statistics...")
        
        all_stats = []
        
        for scenario_key in self.weight_scenarios.keys():
            score_col = f'priority_score_{scenario_key}'
            level_col = f'priority_level_{scenario_key}'
            
            valid_scores = gdf[score_col].dropna()
            
            stats = {
                'scenario': self.weight_scenarios[scenario_key]['name'],
                'scenario_key': scenario_key,
                'total_parcels': len(gdf),
                'valid_parcels': len(valid_scores),
                'missing_parcels': len(gdf) - len(valid_scores),
                'mean_score': valid_scores.mean(),
                'median_score': valid_scores.median(),
                'std_score': valid_scores.std(),
                'min_score': valid_scores.min(),
                'max_score': valid_scores.max(),
                'skewness': scipy_stats.skew(valid_scores),
                'kurtosis': scipy_stats.kurtosis(valid_scores)
            }
            
            # Add level counts
            level_counts = gdf[level_col].value_counts()
            for level in self.priority_levels.keys():
                stats[f'{level.lower()}_count'] = level_counts.get(level, 0)
                stats[f'{level.lower()}_pct'] = (level_counts.get(level, 0) / len(gdf)) * 100
            
            # Add population affected (if population data available)
            if 'poptotal' in gdf.columns:
                for level in self.priority_levels.keys():
                    mask = gdf[level_col] == level
                    pop_affected = gdf.loc[mask, 'poptotal'].sum()
                    stats[f'{level.lower()}_population'] = pop_affected
            
            all_stats.append(stats)
        
        stats_df = pd.DataFrame(all_stats)
        
        # Print summary
        print("\n   Summary across scenarios:")
        print("   " + "="*50)
        for _, row in stats_df.iterrows():
            print(f"\n   {row['scenario']}:")
            print(f"     Valid parcels: {row['valid_parcels']:,}")
            print(f"     Mean score: {row['mean_score']:.3f}")
            print(f"     Critical parcels: {row['critical_count']:,} ({row['critical_pct']:.1f}%)")
            if 'critical_population' in row:
                print(f"     Critical population: {row['critical_population']:,.0f}")
        
        return stats_df
    
    def export_priority_parcels(self, gdf, scenario_key='equal', top_n=1000):
        """Export top priority parcels for a scenario"""
        print(f"\n8. Exporting top {top_n} priority parcels...")
        
        score_col = f'priority_score_{scenario_key}'
        
        # Get top parcels
        valid_gdf = gdf[gdf[score_col].notna()].copy()
        top_parcels = valid_gdf.nlargest(top_n, score_col)
        
        # Select relevant columns for export
        export_cols = [
            'pid', 'address', 
            'poptotal' if 'poptotal' in gdf.columns else 'total_pop',
            'elderly_pct', 'medianhhi', 'AC_final', 'cooling_distance_miles',
            score_col, f'priority_level_{scenario_key}'
        ]
        
        # Filter to existing columns
        export_cols = [col for col in export_cols if col in top_parcels.columns]
        
        # Create export dataframe
        export_df = top_parcels[export_cols].copy()
        
        # Save to CSV
        output_path = self.stats_dir / f'top_{top_n}_priority_parcels_{scenario_key}.csv'
        export_df.to_csv(output_path, index=False)
        
        print(f"   ✓ Exported top {top_n} parcels: {output_path}")
        
        # Also save as GeoJSON for mapping
        geojson_path = self.stats_dir / f'top_{top_n}_priority_parcels_{scenario_key}.geojson'
        top_parcels.to_file(geojson_path, driver='GeoJSON')
        print(f"   ✓ Exported GeoJSON: {geojson_path}")
        
        return export_df
    
    def save_full_results(self, gdf, stats_df, corr_matrix):
        """Save all results and metadata"""
        print("\n9. Saving comprehensive results...")
        
        # Save full statistics
        stats_path = self.stats_dir / 'scenario_statistics.csv'
        stats_df.to_csv(stats_path, index=False)
        print(f"   ✓ Statistics saved: {stats_path}")
        
        # Save correlation matrix
        corr_path = self.stats_dir / 'scenario_correlations.csv'
        corr_matrix.to_csv(corr_path)
        print(f"   ✓ Correlations saved: {corr_path}")
        
        # Save metadata
        metadata = {
            'processing_date': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_parcels': len(gdf),
            'scenarios_processed': list(self.weight_scenarios.keys()),
            'weight_configurations': self.weight_scenarios,
            'priority_thresholds': self.priority_levels,
            'data_sources': {
                'parcels': self.parcels_path,
                'ac_data': self.ac_data_path
            },
            'outputs': {
                'figures': str(self.figures_dir),
                'statistics': str(self.stats_dir)
            }
        }
        
        metadata_path = self.stats_dir / 'processing_metadata.json'
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"   ✓ Metadata saved: {metadata_path}")
        
        # Save geodataframe with all scores (subset for file size)
        output_cols = ['pid', 'geometry'] + \
                     [f'priority_score_{key}' for key in self.weight_scenarios.keys()] + \
                     [f'priority_level_{key}' for key in self.weight_scenarios.keys()]
        
        gdf_export = gdf[output_cols].copy()
        
        # Save as shapefile
        shp_path = self.stats_dir / 'priority_scores_all_scenarios.shp'
        gdf_export.to_file(shp_path)
        print(f"   ✓ Shapefile saved: {shp_path}")
        
        print("\n   All results saved successfully!")
    
    def run(self):
        """Main execution"""
        start_time = time.time()
        
        try:
            # 1. Load data
            gdf = self.load_parcel_data()
            ac_lookup = self.load_external_ac_data()
            
            # 2. Prepare vulnerability factors
            gdf = self.prepare_vulnerability_factors(gdf, ac_lookup)
            
            # 3. Calculate priority scores for all scenarios
            for scenario_key in self.weight_scenarios.keys():
                gdf = self.calculate_priority_scores(gdf, scenario_key)
            
            # 4. Generate maps
            print("\n5. Generating priority maps...")
            for scenario_key in self.weight_scenarios.keys():
                # Main priority map
                self.create_priority_map(
                    gdf, scenario_key, 
                    f'priority_map_{scenario_key}.png'
                )
                
                # Component contribution map
                self.create_component_contribution_map(gdf, scenario_key)
            
            # 5. Create comparison matrix
            corr_matrix = self.create_comparison_matrix(gdf)
            
            # 6. Calculate statistics
            stats_df = self.calculate_statistics(gdf)
            
            # 7. Export top priority parcels for main scenario
            self.export_priority_parcels(gdf, 'equal', top_n=1000)
            self.export_priority_parcels(gdf, 'elderly_focused', top_n=500)
            
            # 8. Save all results
            self.save_full_results(gdf, stats_df, corr_matrix)
            
            # Final summary
            elapsed_time = time.time() - start_time
            print("\n" + "="*60)
            print("PROCESSING COMPLETE")
            print("="*60)
            print(f"Total execution time: {elapsed_time:.2f} seconds")
            print(f"Total parcels processed: {len(gdf):,}")
            print(f"Scenarios analyzed: {len(self.weight_scenarios)}")
            print(f"\nOutputs saved to:")
            print(f"  - Maps: {self.figures_dir}")
            print(f"  - Statistics: {self.stats_dir}")
            
            # Highlight critical findings
            for scenario_key in ['equal', 'elderly_focused']:
                scenario_name = self.weight_scenarios[scenario_key]['name']
                critical_count = (gdf[f'priority_level_{scenario_key}'] == 'Critical').sum()
                print(f"\n{scenario_name} scenario:")
                print(f"  Critical priority parcels: {critical_count:,}")
            
            return gdf, stats_df
            
        except Exception as e:
            print(f"\n❌ Error during processing: {str(e)}")
            import traceback
            traceback.print_exc()
            return None, None


def main():
    """Main entry point"""
    print("Starting Vulnerability Priority Mapping System...")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Create and run mapper
    mapper = VulnerabilityPriorityMapper()
    gdf, stats_df = mapper.run()
    
    if gdf is not None and stats_df is not None:
        print("\n✅ Script completed successfully!")
        print("All priority maps and analyses have been generated.")
    else:
        print("\n❌ Script failed. Please check the error messages above.")
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())