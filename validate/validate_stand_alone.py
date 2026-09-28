#!/usr/bin/env python3
"""
Standalone Validation Analysis
Analyzes your validation CSV without requiring database connection.
Creates a mock cooling center database based on your validation data.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
from datetime import datetime

def analyze_validation_csv(csv_path=r"~\hennepin\data\validate_data\intermediate\validate_cooling_summer_2024_panel.csv"):
    """Complete analysis of validation CSV data"""
    
    print("🌡️ COOLING CENTER VALIDATION ANALYSIS")
    print("="*60)
    
    # Load and clean data
    print(f"\n📂 Loading data from {csv_path}...")
    df = pd.read_csv(csv_path)
    
    # Clean location names
    df['location_clean'] = (
        df['location_name']
        .str.lower()
        .str.replace('_', ' ')
        .str.replace('-', ' ')
        .str.strip()
    )
    
    # Convert date
    df['date'] = pd.to_datetime(df['date'])
    
    print(f"✅ Loaded {len(df):,} records")
    print(f"✅ Date range: {df['date'].min().strftime('%Y-%m-%d')} to {df['date'].max().strftime('%Y-%m-%d')}")
    print(f"✅ Unique locations: {df['location_clean'].nunique()}")
    print(f"✅ Total visits: {df['visits'].sum():,}")
    
    # Create mock cooling center database
    print(f"\n🏢 Creating mock cooling center database...")
    unique_locations = df['location_clean'].unique()
    
    # Create comprehensive cooling center database
    mock_centers = []
    np.random.seed(42)  # For reproducible results
    
    center_types = ['library', 'community_center', 'recreation_center', 'senior_center', 'school']
    
    for i, location in enumerate(unique_locations):
        mock_centers.append({
            'center_id': i + 1,
            'center_name': location,
            'center_type': np.random.choice(center_types),
            'capacity': np.random.randint(50, 400),
            'has_ac': np.random.choice([True, False], p=[0.9, 0.1]),
            'hours_open': np.random.randint(8, 12),
            'address': f"Sample Address {i+1}, Minneapolis, MN",
            'validate_tag': 1  # All locations in validation CSV are considered "validated"
        })
    
    # Add some additional "non-validated" centers not in validation data
    additional_centers = [
        'city hall', 'mall of america', 'target center', 'us bank stadium',
        'minneapolis convention center', 'state fairgrounds', 'walker art center',
        'mill city museum', 'guthrie theater', 'first avenue'
    ]
    
    for i, center in enumerate(additional_centers):
        mock_centers.append({
            'center_id': len(unique_locations) + i + 1,
            'center_name': center,
            'center_type': np.random.choice(center_types),
            'capacity': np.random.randint(100, 500),
            'has_ac': np.random.choice([True, False], p=[0.95, 0.05]),
            'hours_open': np.random.randint(6, 14),
            'address': f"Additional Address {i+1}, Minneapolis, MN",
            'validate_tag': 0  # Not validated (no visitation data)
        })
    
    centers_df = pd.DataFrame(mock_centers)
    
    print(f"✅ Created mock database with {len(centers_df)} cooling centers")
    print(f"   - Validated centers (with data): {centers_df['validate_tag'].sum()}")
    print(f"   - Non-validated centers: {(centers_df['validate_tag'] == 0).sum()}")
    
    # Analyze visitation patterns
    print(f"\n📊 ANALYZING VISITATION PATTERNS...")
    
    # Daily statistics
    daily_stats = df.groupby('date')['visits'].agg(['sum', 'mean', 'count']).round(2)
    
    # Location statistics
    location_stats = df.groupby('location_clean').agg({
        'visits': ['sum', 'mean', 'count', 'std'],
        'date': ['min', 'max']
    }).round(2)
    
    location_stats.columns = ['_'.join(col).strip() for col in location_stats.columns.values]
    location_stats = location_stats.sort_values('visits_sum', ascending=False)
    
    # Create visualizations
    print(f"\n📈 Creating visualizations...")
    os.makedirs('./figures', exist_ok=True)
    
    # Set up plotting style
    plt.style.use('default')
    sns.set_palette("husl")
    
    # Figure 1: Overview Dashboard
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # Top 15 locations by total visits
    top_15 = location_stats.head(15)
    axes[0,0].barh(range(len(top_15)), top_15['visits_sum'], color='skyblue', alpha=0.8)
    axes[0,0].set_yticks(range(len(top_15)))
    axes[0,0].set_yticklabels(top_15.index, fontsize=10)
    axes[0,0].set_xlabel('Total Visits')
    axes[0,0].set_title('Top 15 Locations by Total Visits')
    axes[0,0].grid(True, alpha=0.3)
    
    # Daily visits over time
    axes[0,1].plot(daily_stats.index, daily_stats['sum'], color='green', linewidth=2)
    axes[0,1].set_title('Total Daily Visits Over Time')
    axes[0,1].set_xlabel('Date')
    axes[0,1].set_ylabel('Total Visits')
    axes[0,1].tick_params(axis='x', rotation=45)
    axes[0,1].grid(True, alpha=0.3)
    
    # Visit distribution
    axes[1,0].hist(df['visits'], bins=30, alpha=0.7, color='orange', edgecolor='black')
    axes[1,0].set_title('Distribution of Daily Visits per Location')
    axes[1,0].set_xlabel('Visits per Day')
    axes[1,0].set_ylabel('Frequency')
    axes[1,0].grid(True, alpha=0.3)
    
    # Validation status pie chart
    validation_counts = centers_df['validate_tag'].value_counts()
    axes[1,1].pie(validation_counts.values, 
                  labels=['Non-Validated', 'Validated (Have Data)'], 
                  autopct='%1.1f%%', 
                  startangle=90,
                  colors=['lightcoral', 'lightgreen'])
    axes[1,1].set_title('Cooling Centers by Validation Status')
    
    plt.tight_layout()
    plt.savefig('./figures/validation_overview_dashboard.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    # Figure 2: Time Series Analysis
    fig, axes = plt.subplots(2, 1, figsize=(16, 10))
    
    # Weekly aggregation
    df['week'] = df['date'].dt.to_period('W-MON')
    weekly_stats = df.groupby('week')['visits'].agg(['sum', 'mean']).reset_index()
    weekly_stats['week_start'] = weekly_stats['week'].dt.start_time
    
    axes[0].bar(weekly_stats['week_start'], weekly_stats['sum'], 
               alpha=0.7, color='steelblue', width=5)
    axes[0].set_title('Weekly Total Visits to All Validated Cooling Centers')
    axes[0].set_xlabel('Week Starting')
    axes[0].set_ylabel('Total Weekly Visits')
    axes[0].grid(True, alpha=0.3)
    
    # Monthly aggregation
    df['month'] = df['date'].dt.to_period('M')
    monthly_stats = df.groupby('month')['visits'].agg(['sum', 'mean']).reset_index()
    monthly_stats['month_start'] = monthly_stats['month'].dt.start_time
    
    axes[1].bar(monthly_stats['month_start'], monthly_stats['sum'], 
               alpha=0.7, color='darkgreen', width=20)
    axes[1].set_title('Monthly Total Visits to All Validated Cooling Centers')
    axes[1].set_xlabel('Month')
    axes[1].set_ylabel('Total Monthly Visits')
    axes[1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('./figures/validation_time_series_analysis.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    # Generate comprehensive report
    print(f"\n📋 COMPREHENSIVE ANALYSIS REPORT")
    print("="*60)
    
    print(f"\n📊 DATA SUMMARY:")
    print(f"   • Total validation records: {len(df):,}")
    print(f"   • Unique validated locations: {df['location_clean'].nunique()}")
    print(f"   • Date range: {df['date'].min().strftime('%Y-%m-%d')} to {df['date'].max().strftime('%Y-%m-%d')}")
    print(f"   • Total days of data: {(df['date'].max() - df['date'].min()).days + 1}")
    print(f"   • Total visits recorded: {df['visits'].sum():,}")
    
    print(f"\n🏢 COOLING CENTER DATABASE:")
    print(f"   • Total cooling centers: {len(centers_df)}")
    print(f"   • Validated centers (with visitation data): {centers_df['validate_tag'].sum()}")
    print(f"   • Non-validated centers: {(centers_df['validate_tag'] == 0).sum()}")
    print(f"   • Validation rate: {(centers_df['validate_tag'].sum() / len(centers_df) * 100):.1f}%")
    
    print(f"\n📈 VISITATION STATISTICS:")
    print(f"   • Average daily visits across all centers: {df['visits'].mean():.1f}")
    print(f"   • Median daily visits: {df['visits'].median():.1f}")
    print(f"   • Peak daily visits: {df['visits'].max():,}")
    print(f"   • Minimum daily visits: {df['visits'].min()}")
    print(f"   • Standard deviation: {df['visits'].std():.1f}")
    
    print(f"\n🏆 TOP 10 MOST VISITED LOCATIONS:")
    top_10 = location_stats.head(10)
    for i, (location, row) in enumerate(top_10.iterrows(), 1):
        total_visits = int(row['visits_sum'])
        avg_visits = row['visits_mean']
        print(f"   {i:2d}. {location:<35} {total_visits:>8,} total ({avg_visits:>6.1f} avg/day)")
    
    print(f"\n📅 TEMPORAL PATTERNS:")
    print(f"   • Peak week: {weekly_stats.loc[weekly_stats['sum'].idxmax(), 'week']} ({weekly_stats['sum'].max():,} visits)")
    print(f"   • Average weekly visits: {weekly_stats['sum'].mean():,.0f}")
    print(f"   • Peak month: {monthly_stats.loc[monthly_stats['sum'].idxmax(), 'month']} ({monthly_stats['sum'].max():,} visits)")
    print(f"   • Average monthly visits: {monthly_stats['sum'].mean():,.0f}")
    
    # Save results
    print(f"\n💾 SAVING RESULTS...")
    os.makedirs('./results', exist_ok=True)
    
    # Save cooling centers with validation tags
    centers_df.to_csv('./results/cooling_centers_with_validation_tags.csv', index=False)
    
    # Save location statistics
    location_stats.to_csv('./results/location_visitation_statistics.csv')
    
    # Save daily aggregated data
    daily_stats.to_csv('./results/daily_visitation_summary.csv')
    
    # Save weekly and monthly summaries
    weekly_stats.to_csv('./results/weekly_visitation_summary.csv', index=False)
    monthly_stats.to_csv('./results/monthly_visitation_summary.csv', index=False)
    
    # Save enhanced validation data
    df_export = df.copy()
    df_export['validate_tag'] = 1  # All locations in CSV are validated
    df_export.to_csv('./results/validation_data_enhanced.csv', index=False)
    
    print(f"✅ Results saved to ./results/ directory:")
    print(f"   • cooling_centers_with_validation_tags.csv")
    print(f"   • location_visitation_statistics.csv")
    print(f"   • daily_visitation_summary.csv")
    print(f"   • weekly_visitation_summary.csv")
    print(f"   • monthly_visitation_summary.csv")
    print(f"   • validation_data_enhanced.csv")
    
    print(f"\n🎨 Visualizations saved to ./figures/ directory:")
    print(f"   • validation_overview_dashboard.png")
    print(f"   • validation_time_series_analysis.png")
    
    # Return key results for further analysis
    results = {
        'validation_data': df,
        'cooling_centers': centers_df,
        'location_stats': location_stats,
        'daily_stats': daily_stats,
        'weekly_stats': weekly_stats,
        'monthly_stats': monthly_stats,
        'total_visits': df['visits'].sum(),
        'validated_centers_count': centers_df['validate_tag'].sum(),
        'validation_rate': centers_df['validate_tag'].sum() / len(centers_df)
    }
    
    print(f"\n🎉 ANALYSIS COMPLETE!")
    print(f"="*60)
    
    return results

def create_heat_model_integration_example(results):
    """Show how to integrate validation results with your heat risk model"""
    
    print(f"\n🔗 INTEGRATION WITH HEAT RISK MODEL")
    print("="*60)
    
    print(f"\nTo integrate these validation results with your existing heat risk model:")
    print(f"")
    
    # Create example integration code
    integration_code = '''
# Example: How to use validation results in your heat risk model

import pandas as pd
import numpy as np

# Load validation results
cooling_centers = pd.read_csv('./results/cooling_centers_with_validation_tags.csv')
location_stats = pd.read_csv('./results/location_visitation_statistics.csv')

# In your HeatEvent.load_data() method, you can now filter or weight 
# cooling centers based on validation status:

def enhanced_load_data(self):
    """Enhanced version that considers validation status"""
    
    # Your existing parcel loading code...
    query = """
    SELECT p.*, cc.validate_tag 
    FROM parcels_with_cooling_centers_v5 p
    LEFT JOIN cooling_centers cc ON p.nearest_center_names[1] = cc.center_name
    WHERE p.prop_type_res = 'Residential'
    """
    parcel_gdf = fetch_spatial_data(query)
    
    # Now you can modify decision-making based on validation:
    for idx, row in parcel_gdf.iterrows():
        attrs = {
            # ... your existing attributes ...
            'nearest_center_validated': row.get('validate_tag', 0)
        }
        
        # Adjust cooling distance penalty based on validation
        cooling_distance = row['nearest_center_distances'][0]
        if row.get('validate_tag', 0) == 1:
            # Validated centers are more attractive (reduce effective distance)
            cooling_distance *= 0.8
        else:
            # Non-validated centers are less attractive (increase effective distance)
            cooling_distance *= 1.2
            
        self.parcels.append(Parcel(
            parcel_id=row['pid'],
            nearest_cooling_centers=row['nearest_center_names'],
            cooling_distance=cooling_distance,
            attributes=attrs
        ))

# In your Parcel.move2cooling_proba() method:
def enhanced_move2cooling_proba(self, temp_thr=70, age_thr=70, income_thr=70000):
    """Enhanced probability calculation considering validation"""
    
    # Your existing probability calculations...
    temp_proba = max(0.1, np.log(temp - temp_thr)/np.log(temp))
    age_proba = max(0.1, 1 - 1 / (1 + np.exp(0.1*(age_thr-age))))
    income_proba = max(0.1, 1 / (1 + np.exp((income/10000 - income_thr/10000) * 0.5)))
    cooling_proba = max(0.1, 1 / (1 + np.exp((cooling_dist - 1609) * 0.001)))
    ac_proba = 0.01 if ac==1 else 0.3
    
    # NEW: Add validation bonus
    validation_bonus = 1.2 if self.attributes.get('nearest_center_validated', 0) == 1 else 1.0
    
    # Apply validation bonus to cooling probability
    cooling_proba *= validation_bonus
    
    # Calculate final probability
    final_proba = (temp_proba * age_proba * income_proba * cooling_proba * ac_proba) ** (1/5)
    return final_proba
'''
    
    print(integration_code)
    
    # Save integration example
    with open('./results/integration_example.py', 'w') as f:
        f.write(integration_code)
    
    print(f"\n📝 Integration example saved to: ./results/integration_example.py")

def generate_model_recommendations(results):
    """Generate recommendations for model improvement"""
    
    print(f"\n💡 MODEL ENHANCEMENT RECOMMENDATIONS")
    print("="*60)
    
    validation_data = results['validation_data']
    location_stats = results['location_stats']
    
    # Analyze patterns
    high_usage_locations = location_stats[location_stats['visits_sum'] > location_stats['visits_sum'].quantile(0.75)]
    low_usage_locations = location_stats[location_stats['visits_sum'] < location_stats['visits_sum'].quantile(0.25)]
    
    print(f"\n🎯 KEY FINDINGS & RECOMMENDATIONS:")
    
    print(f"\n1. VALIDATED COOLING CENTER USAGE PATTERNS:")
    print(f"   • High-usage centers ({len(high_usage_locations)}): {location_stats['visits_sum'].quantile(0.75):.0f}+ total visits")
    print(f"   • Low-usage centers ({len(low_usage_locations)}): <{location_stats['visits_sum'].quantile(0.25):.0f} total visits")
    print(f"   • Usage varies by {location_stats['visits_sum'].max() / location_stats['visits_sum'].min():.1f}x between highest and lowest")
    
    print(f"\n2. MODEL CALIBRATION SUGGESTIONS:")
    print(f"   • Use validation_tag = 1 to weight cooling center attractiveness")
    print(f"   • High-usage centers should have increased attractiveness in model")
    print(f"   • Consider capacity constraints based on historical usage patterns")
    print(f"   • Adjust distance penalties based on actual usage data")
    
    print(f"\n3. SCENARIO MODELING IMPROVEMENTS:")
    print(f"   • Use historical peak usage ({validation_data['visits'].max():,} visits/day) for capacity planning")
    print(f"   • Consider seasonal variations (summer 2024 data: {validation_data['date'].min().strftime('%b')} - {validation_data['date'].max().strftime('%b')})")
    print(f"   • Account for different center types in decision-making logic")
    
    print(f"\n4. DATA INTEGRATION PRIORITIES:")
    print(f"   • Tag your cooling center database with validate_tag field")
    print(f"   • Use historical usage to calibrate probability functions")
    print(f"   • Consider implementing usage-based capacity constraints")
    print(f"   • Validate model predictions against this historical data")

def main():
    """Main function - run the complete standalone analysis"""
    
    # Check if CSV file exists
    csv_file = 'validate_cooling_summer_2024_panel.csv'
    if not os.path.exists(csv_file):
        print(f"❌ Could not find {csv_file}")
        print(f"Please make sure the file is in the current directory")
        return None
    
    try:
        # Run main analysis
        results = analyze_validation_csv(csv_file)
        
        # Show integration example
        create_heat_model_integration_example(results)
        
        # Generate recommendations
        generate_model_recommendations(results)
        
        print(f"\n🚀 NEXT STEPS:")
        print(f"   1. Review the validation results in ./results/")
        print(f"   2. Update your heat risk model using ./results/integration_example.py")
        print(f"   3. Use validate_tag to improve cooling center attractiveness calculations")
        print(f"   4. Validate your model predictions against this historical usage data")
        
        return results
        
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    # Run the complete standalone analysis
    analysis_results = main()