#!/usr/bin/env python3
"""
Parcel Summary Statistics and Mapping Script
Generates publication-quality maps and statistics for age, income, AC condition, and cooling distance
Integrates external AC data following the pattern from parallel processing code
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
import pickle
from pathlib import Path
import warnings
import time
from scipy import stats
import json

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


class ParcelSummaryMapper:
    def __init__(self):
        """Initialize paths and settings"""
        # Data paths
        self.parcels_path = r"~\hennepin\data\preprocessed_data\parcels_prepared.pkl"
        self.ac_data_path = r"~\hennepin\data\raw\Parcel_AC\hennepin_parcel_ac_avail.csv"
        
        # Output paths
        self.output_dir = Path(r"~\hennepin\output")
        self.figures_dir = self.output_dir / "figures" / "summary_stats"
        self.stats_dir = self.output_dir / "statistics" / "summary_covar"
        
        # Create directories if they don't exist
        self.figures_dir.mkdir(parents=True, exist_ok=True)
        self.stats_dir.mkdir(parents=True, exist_ok=True)
        
        # Nature publication settings
        self.figure_dpi = 300
        self.figure_size = (10, 12)  # Width, Height in inches
        self.font_size = 10
        self.title_size = 12
        
        # Color schemes for Nature style
        self.colormaps = {
            'age_median': 'viridis',
            'elderly_pct': 'YlOrRd',
            # 'income': 'RdBu_r',  # Remove this line - no longer needed
            # 'ac': 'RdYlBu_r',     # Remove this line - no longer needed
            'distance': 'plasma_r'
        }
        
        # Missing data color
        self.missing_color = '#CCCCCC'
        
        print("="*60)
        print("PARCEL SUMMARY STATISTICS AND MAPPING")
        print("="*60)
        print(f"Output directories created:")
        print(f"  Figures: {self.figures_dir}")
        print(f"  Statistics: {self.stats_dir}")
    
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
        print(f"   ✓ Total columns: {len(gdf.columns)}")
        
        # Check for age-related columns
        age_related = [col for col in gdf.columns if any(word in col.lower() for word in ['age', 'pop', 'elderly'])]
        if age_related:
            print(f"   ✓ Age-related columns found: {', '.join(age_related)}")
        
        return gdf
    
    def load_external_ac_data(self):
        """Load external AC data following the pattern from parallel processing code"""
        print("\n2. Loading external AC data...")
        start_time = time.time()
        
        ac_lookup = {}
        
        try:
            if not Path(self.ac_data_path).exists():
                print(f"   ⚠ AC data file not found: {self.ac_data_path}")
                print("   Using database AC values only")
                return ac_lookup
            
            # Read CSV with REM_ACCT_NUM as string to preserve leading zeros
            ac_df = pd.read_csv(self.ac_data_path, dtype={'REM_ACCT_NUM': str})
            
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
                else:  # Empty or other values
                    empty_count += 1
            
            load_time = time.time() - start_time
            
            print(f"   ✓ Loaded AC data in {load_time:.2f} seconds")
            print(f"   ✓ Total parcels in AC file: {len(ac_df):,}")
            print(f"   ✓ Parcels with AC='YES': {yes_count:,} ({yes_count/len(ac_df)*100:.1f}%)")
            print(f"   ✓ Parcels with AC='NO': {no_count:,} ({no_count/len(ac_df)*100:.1f}%)")
            print(f"   ✓ Parcels with empty/unknown AC: {empty_count:,}")
            print(f"   ✓ Valid AC entries in lookup: {len(ac_lookup):,}")
            
            return ac_lookup
            
        except Exception as e:
            print(f"   ❌ Error loading AC data: {str(e)}")
            print("   Using database AC values only")
            return {}
    
    def calculate_median_age(self, row):
        """Calculate weighted median age estimate"""
        try:
            # Check which column pattern we have
            # Pattern 1: From the extraction script (broader age groups)
            if 'ageunder18' in row.index:
                midpoints = {
                    'ageunder18': 9,      # 0-18 years
                    'age18_39': 28.5,     # 18-39 years
                    'age40_64': 52,       # 40-64 years
                    'age65up': 75         # 65+ years
                }
            # Pattern 2: More detailed age groups
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
            
            # Get populations for each group
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
            # Check which column pattern we have
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
    
    def prepare_variables(self, gdf, ac_lookup):
        """Prepare all variables for mapping and statistics"""
        print("\n3. Preparing variables...")
        
        # First, check which age columns we have
        print("   Checking available columns for age calculation...")
        age_cols_pattern1 = ['ageunder18', 'age18_39', 'age40_64', 'age65up', 'poptotal']
        age_cols_pattern2 = ['pop_under_5', 'pop_5_17', 'pop_18_34', 'pop_35_64', 'pop_over_65', 'total_pop']
        
        has_pattern1 = all(col in gdf.columns for col in age_cols_pattern1)
        has_pattern2 = all(col in gdf.columns for col in age_cols_pattern2)
        
        if has_pattern1:
            print("   ✓ Found age columns: ageunder18, age18_39, age40_64, age65up, poptotal")
        elif has_pattern2:
            print("   ✓ Found age columns: pop_under_5, pop_5_17, pop_18_34, pop_35_64, pop_over_65")
        else:
            print("   ⚠ Warning: Age columns not found in expected patterns")
            available_age_cols = [col for col in gdf.columns if any(word in col.lower() for word in ['age', 'pop'])]
            print(f"     Available columns with 'age' or 'pop': {available_age_cols}")
        
        # 1. Age variables
        print("   Calculating age variables...")
        gdf['age_median'] = gdf.apply(self.calculate_median_age, axis=1)
        gdf['elderly_pct'] = gdf.apply(self.calculate_elderly_pct, axis=1)
        
        valid_median = gdf['age_median'].notna().sum()
        valid_elderly = gdf['elderly_pct'].notna().sum()
        print(f"   ✓ Median age calculated: {valid_median:,}/{len(gdf):,} parcels")
        if valid_median > 0:
            print(f"     Mean: {gdf['age_median'].mean():.1f} years, Median: {gdf['age_median'].median():.1f} years")
        print(f"   ✓ Elderly % calculated: {valid_elderly:,}/{len(gdf):,} parcels")
        if valid_elderly > 0:
            print(f"     Mean: {gdf['elderly_pct'].mean():.1f}%, Median: {gdf['elderly_pct'].median():.1f}%")
        
        # 2. Income variable (convert to thousands)
        print("   Processing income data...")
        gdf['income_k'] = gdf['medianhhi'] / 1000
        valid_income = gdf['income_k'].notna().sum()
        print(f"   ✓ Income data available: {valid_income:,}/{len(gdf):,} parcels")
        
        # 3. AC condition with external data integration
        print("   Integrating AC data...")
        gdf['AC_final'] = gdf['AC'].copy()  # Start with database values
        gdf['AC_source'] = 'database'
        
        external_count = 0
        database_count = 0
        
        for idx, row in gdf.iterrows():
            pid_str = str(row['pid']).strip()
            if pid_str in ac_lookup:
                gdf.at[idx, 'AC_final'] = ac_lookup[pid_str]
                gdf.at[idx, 'AC_source'] = 'external'
                external_count += 1
            else:
                database_count += 1
        
        print(f"   ✓ AC data sources:")
        print(f"     - External: {external_count:,} ({external_count/len(gdf)*100:.1f}%)")
        print(f"     - Database: {database_count:,} ({database_count/len(gdf)*100:.1f}%)")
        
        # 4. Cooling distance (convert meters to miles)
        print("   Converting cooling distance to miles...")
        gdf['cooling_distance_miles'] = gdf['cooling_distance'] * 0.000621371
        
        # Handle infinite or very large values
        gdf.loc[gdf['cooling_distance_miles'] > 100, 'cooling_distance_miles'] = np.nan
        
        valid_distance = gdf['cooling_distance_miles'].notna().sum()
        print(f"   ✓ Valid cooling distances: {valid_distance:,}/{len(gdf):,} parcels")
        
        # Print summary of missing data
        print("\n   Missing data summary:")
        print(f"     - Median age: {gdf['age_median'].isna().sum():,} ({gdf['age_median'].isna().sum()/len(gdf)*100:.1f}%)")
        print(f"     - Elderly %: {gdf['elderly_pct'].isna().sum():,} ({gdf['elderly_pct'].isna().sum()/len(gdf)*100:.1f}%)")
        print(f"     - Income: {gdf['income_k'].isna().sum():,} ({gdf['income_k'].isna().sum()/len(gdf)*100:.1f}%)")
        print(f"     - AC: {gdf['AC_final'].isna().sum():,} ({gdf['AC_final'].isna().sum()/len(gdf)*100:.1f}%)")
        print(f"     - Distance: {gdf['cooling_distance_miles'].isna().sum():,} ({gdf['cooling_distance_miles'].isna().sum()/len(gdf)*100:.1f}%)")
        
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
    
    def create_nature_style_map(self, gdf, variable, title, cmap_name, unit, 
                                output_name, vmin=None, vmax=None):
        """Create publication-quality map for Nature"""
        print(f"   Creating map: {output_name}...")
        
        fig, ax = plt.subplots(figsize=self.figure_size, dpi=self.figure_dpi)
        
        # Prepare data with missing values
        data = gdf.copy()
        
        # Identify missing data
        missing_mask = data[variable].isna()
        valid_mask = ~missing_mask
        
        # Get color bounds
        if valid_mask.sum() > 0:
            if vmin is None:
                vmin = data.loc[valid_mask, variable].quantile(0.02)
            if vmax is None:
                vmax = data.loc[valid_mask, variable].quantile(0.98)
        else:
            vmin, vmax = 0, 1
        
        # Plot missing data in grey first
        if missing_mask.sum() > 0:
            data[missing_mask].plot(
                ax=ax,
                color=self.missing_color,
                edgecolor='none',
                linewidth=0
            )
        
        # Plot valid data with colormap
        if valid_mask.sum() > 0:
            data[valid_mask].plot(
                column=variable,
                ax=ax,
                legend=False,
                cmap=cmap_name,
                edgecolor='none',
                linewidth=0,
                vmin=vmin,
                vmax=vmax
            )
        
        # Add title
        ax.set_title(title, fontsize=self.title_size, fontweight='bold', pad=20)
        
        # Remove axes
        ax.set_axis_off()
        
        # Add colorbar
        sm = plt.cm.ScalarMappable(cmap=cmap_name, norm=Normalize(vmin=vmin, vmax=vmax))
        sm.set_array([])
        
        cbar = plt.colorbar(sm, ax=ax, fraction=0.03, pad=0.04, 
                           orientation='vertical', aspect=20)
        cbar.set_label(unit, fontsize=self.font_size)
        cbar.ax.tick_params(labelsize=9)
        
        # Add note about missing data if present
        if missing_mask.sum() > 0:
            missing_pct = missing_mask.sum() / len(data) * 100
            ax.text(0.02, 0.02, f'Grey = No data ({missing_pct:.1f}%)', 
                   transform=ax.transAxes, fontsize=8,
                   bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        # Add scale bar
        scalebar = ScaleBar(1, 'm', length_fraction=0.15, location='lower right',
                           box_alpha=0.8, pad=0.5, sep=2, 
                           font_properties={'size': 9})
        ax.add_artist(scalebar)
        
        # Add north arrow
        self.add_north_arrow(ax)
        
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
        
    def create_ac_discrete_map(self, gdf, output_name):
        """Create discrete map for AC availability (boolean)"""
        print(f"   Creating map: {output_name}...")
        
        fig, ax = plt.subplots(figsize=self.figure_size, dpi=self.figure_dpi)
        
        # Prepare data
        data = gdf.copy()
        
        # Define colors for each category
        colors = ['#d7191c', '#2b83ba', '#CCCCCC']  # Red (No AC), Blue (Has AC), Grey (Missing)
        labels = ['No AC', 'Has AC', 'No Data']
        
        # Plot each category
        no_ac = data[data['AC_final'] == 0]
        has_ac = data[data['AC_final'] == 1]
        missing = data[data['AC_final'].isna()]
        
        # Plot in order (missing first as background)
        if len(missing) > 0:
            missing.plot(ax=ax, color=colors[2], edgecolor='none', linewidth=0)
        if len(no_ac) > 0:
            no_ac.plot(ax=ax, color=colors[0], edgecolor='none', linewidth=0)
        if len(has_ac) > 0:
            has_ac.plot(ax=ax, color=colors[1], edgecolor='none', linewidth=0)
        
        # Add title
        ax.set_title('Air Conditioning Availability by Parcel', 
                    fontsize=self.title_size, fontweight='bold', pad=20)
        
        # Remove axes
        ax.set_axis_off()
        
        # Create legend instead of colorbar
        legend_elements = []
        if len(has_ac) > 0:
            legend_elements.append(mpatches.Patch(color=colors[1], label=f'Has AC ({len(has_ac)/len(data)*100:.1f}%)'))
        if len(no_ac) > 0:
            legend_elements.append(mpatches.Patch(color=colors[0], label=f'No AC ({len(no_ac)/len(data)*100:.1f}%)'))
        if len(missing) > 0:
            legend_elements.append(mpatches.Patch(color=colors[2], label=f'No Data ({len(missing)/len(data)*100:.1f}%)'))
        
        ax.legend(handles=legend_elements, loc='lower left', frameon=True, 
                fancybox=True, shadow=True, fontsize=9)
        
        # Add scale bar
        scalebar = ScaleBar(1, 'm', length_fraction=0.15, location='lower right',
                        box_alpha=0.8, pad=0.5, sep=2, 
                        font_properties={'size': 9})
        ax.add_artist(scalebar)
        
        # Add north arrow
        self.add_north_arrow(ax)
        
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


    def generate_all_maps(self, gdf):
        """Generate all 5 maps"""
        print("\n4. Generating maps...")
        
        # 1. Median age map
        self.create_nature_style_map(
            gdf, 'age_median',
            'Estimated Median Age by Parcel',
            self.colormaps['age_median'],
            'Age (years)',
            'age_median_distribution_map.png'
        )
        
        # 2. Elderly percentage map
        self.create_nature_style_map(
            gdf, 'elderly_pct',
            'Percentage of Population Aged 65+ by Parcel',
            self.colormaps['elderly_pct'],
            'Elderly Population (%)',
            'age_elderly_pct_map.png',
            vmin=0, vmax=50
        )
        
        # 3. Income map - CHANGED TO SEQUENTIAL COLORMAP
        self.create_nature_style_map(
            gdf, 'income_k',
            'Median Household Income by Parcel',
            'viridis',  # Changed from 'RdBu_r' to sequential colormap
            'Income ($1000s)',
            'income_distribution_map.png'
        )
        
        # 4. AC condition map - NOW USES DISCRETE METHOD
        self.create_ac_discrete_map(
            gdf,
            'ac_condition_map.png'
        )
        
        # 5. Cooling distance map
        self.create_nature_style_map(
            gdf, 'cooling_distance_miles',
            'Distance to Nearest Cooling Center by Parcel',
            self.colormaps['distance'],
            'Distance (miles)',
            'cooling_distance_map.png',
            vmin=0, vmax=5
        )
        
        print("   ✓ All maps generated successfully")
    
    def calculate_summary_statistics(self, gdf):
        """Calculate comprehensive statistics"""
        print("\n5. Calculating summary statistics...")
        
        # Variables to analyze
        variables = {
            'age_median': 'Median Age (years)',
            'age_elderly_pct': 'Elderly Percentage (%)',
            'household_income': 'Household Income ($)',
            'ac_condition': 'AC Availability',
            'cooling_distance_miles': 'Cooling Distance (miles)'
        }
        
        # Prepare data
        analysis_data = {
            'age_median': gdf['age_median'],
            'age_elderly_pct': gdf['elderly_pct'],
            'household_income': gdf['medianhhi'],
            'ac_condition': gdf['AC_final'],
            'cooling_distance_miles': gdf['cooling_distance_miles']
        }
        
        # Calculate statistics
        stats_list = []
        
        for var_key, var_name in variables.items():
            data_col = analysis_data[var_key]
            valid_data = data_col.dropna()
            
            # Basic statistics
            stats_dict = {
                'variable': var_name,
                'mean': valid_data.mean() if len(valid_data) > 0 else np.nan,
                'median': valid_data.median() if len(valid_data) > 0 else np.nan,
                'std': valid_data.std() if len(valid_data) > 0 else np.nan,
                'min': valid_data.min() if len(valid_data) > 0 else np.nan,
                'p25': valid_data.quantile(0.25) if len(valid_data) > 0 else np.nan,
                'p50': valid_data.quantile(0.50) if len(valid_data) > 0 else np.nan,
                'p75': valid_data.quantile(0.75) if len(valid_data) > 0 else np.nan,
                'max': valid_data.max() if len(valid_data) > 0 else np.nan,
                'missing_count': data_col.isna().sum(),
                'missing_pct': (data_col.isna().sum() / len(data_col)) * 100,
                'valid_count': len(valid_data),
                'skewness': stats.skew(valid_data) if len(valid_data) > 2 else np.nan,
                'kurtosis': stats.kurtosis(valid_data) if len(valid_data) > 3 else np.nan
            }
            
            # Add data source for AC
            if var_key == 'ac_condition':
                external_count = (gdf['AC_source'] == 'external').sum()
                database_count = (gdf['AC_source'] == 'database').sum()
                total = external_count + database_count
                if total > 0:
                    stats_dict['data_source'] = f"mixed(external:{external_count/total*100:.1f}%,database:{database_count/total*100:.1f}%)"
                else:
                    stats_dict['data_source'] = 'none'
            else:
                stats_dict['data_source'] = 'calculated' if 'age' in var_key or 'distance' in var_key else 'database'
            
            stats_list.append(stats_dict)
        
        # Create DataFrame
        stats_df = pd.DataFrame(stats_list)
        
        # Print summary
        print("\n   Summary Statistics:")
        print("   " + "="*50)
        for idx, row in stats_df.iterrows():
            print(f"\n   {row['variable']}:")
            print(f"     Mean: {row['mean']:.2f}" if pd.notna(row['mean']) else "     Mean: N/A")
            print(f"     Median: {row['median']:.2f}" if pd.notna(row['median']) else "     Median: N/A")
            print(f"     Std Dev: {row['std']:.2f}" if pd.notna(row['std']) else "     Std Dev: N/A")
            print(f"     Range: [{row['min']:.2f}, {row['max']:.2f}]" if pd.notna(row['min']) else "     Range: N/A")
            print(f"     Missing: {row['missing_count']:,} ({row['missing_pct']:.1f}%)")
            print(f"     Data Source: {row['data_source']}")
        
        return stats_df
    
    def save_results(self, gdf, stats_df):
        """Save all outputs"""
        print("\n6. Saving results...")
        
        # Save statistics CSV
        stats_file = self.stats_dir / "summary_stats.csv"
        stats_df.to_csv(stats_file, index=False)
        print(f"   ✓ Statistics saved: {stats_file}")
        
        # Save AC source breakdown
        ac_source_file = self.stats_dir / "ac_data_sources.csv"
        ac_source_summary = gdf['AC_source'].value_counts().to_frame('count')
        ac_source_summary['percentage'] = (ac_source_summary['count'] / len(gdf)) * 100
        ac_source_summary.to_csv(ac_source_file)
        print(f"   ✓ AC source breakdown saved: {ac_source_file}")
        
        # Save metadata
        metadata = {
            'processing_date': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_parcels': len(gdf),
            'external_ac_file': self.ac_data_path,
            'ac_sources': {
                'external': int((gdf['AC_source'] == 'external').sum()),
                'database': int((gdf['AC_source'] == 'database').sum())
            },
            'variables_processed': [
                'age_median', 'elderly_pct', 'income_k', 
                'AC_final', 'cooling_distance_miles'
            ],
            'maps_generated': [
                'age_median_distribution_map.png',
                'age_elderly_pct_map.png',
                'income_distribution_map.png',
                'ac_condition_map.png',
                'cooling_distance_map.png'
            ]
        }
        
        metadata_file = self.stats_dir / "processing_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"   ✓ Metadata saved: {metadata_file}")
        
        print("\n   All results saved successfully!")
    
    def run(self):
        """Main execution"""
        start_time = time.time()
        
        try:
            # 1. Load parcel data
            gdf = self.load_parcel_data()
            
            # 2. Load external AC data
            ac_lookup = self.load_external_ac_data()
            
            # 3. Prepare variables
            gdf = self.prepare_variables(gdf, ac_lookup)
            
            # 4. Generate maps
            self.generate_all_maps(gdf)
            
            # 5. Calculate statistics
            stats_df = self.calculate_summary_statistics(gdf)
            
            # 6. Save results
            self.save_results(gdf, stats_df)
            
            # Final summary
            elapsed_time = time.time() - start_time
            print("\n" + "="*60)
            print("PROCESSING COMPLETE")
            print("="*60)
            print(f"Total execution time: {elapsed_time:.2f} seconds")
            print(f"Total parcels processed: {len(gdf):,}")
            print(f"\nOutputs saved to:")
            print(f"  - Maps: {self.figures_dir}")
            print(f"  - Statistics: {self.stats_dir}")
            
            # Print final AC statistics
            external_ac = (gdf['AC_source'] == 'external').sum()
            database_ac = (gdf['AC_source'] == 'database').sum()
            print(f"\nFinal AC data distribution:")
            print(f"  - External AC data: {external_ac:,} parcels ({external_ac/len(gdf)*100:.1f}%)")
            print(f"  - Database AC data: {database_ac:,} parcels ({database_ac/len(gdf)*100:.1f}%)")
            
            # AC availability statistics
            has_ac = (gdf['AC_final'] == 1).sum()
            no_ac = (gdf['AC_final'] == 0).sum()
            print(f"\nAC availability:")
            print(f"  - Has AC: {has_ac:,} parcels ({has_ac/len(gdf)*100:.1f}%)")
            print(f"  - No AC: {no_ac:,} parcels ({no_ac/len(gdf)*100:.1f}%)")
            
            return gdf, stats_df
            
        except Exception as e:
            print(f"\n❌ Error during processing: {str(e)}")
            import traceback
            traceback.print_exc()
            return None, None


def main():
    """Main entry point"""
    print("Starting Parcel Summary Statistics and Mapping...")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Create and run mapper
    mapper = ParcelSummaryMapper()
    gdf, stats_df = mapper.run()
    
    if gdf is not None and stats_df is not None:
        print("\n✅ Script completed successfully!")
        print("All outputs have been saved to the specified directories.")
    else:
        print("\n❌ Script failed. Please check the error messages above.")
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())