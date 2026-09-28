#!/usr/bin/env python3
"""
Cooling Center Validation Analysis
This script matches validation CSV data with cooling center database records
and analyzes visitation patterns for validated vs non-validated centers.

Author: Project contributors
Date: June 2025
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Import database utilities from your existing codebase
import sys
import os
sys.path.append('./src')
from src.utils import fetch_data, fetch_spatial_data, connect_to_db

class CoolingCenterValidator:
    """Class to handle validation matching and analysis"""
    
    def __init__(self, validation_csv_path):
        """Initialize with validation CSV data"""
        self.validation_csv_path = validation_csv_path
        self.validation_data = None
        self.cooling_centers_db = None
        self.matched_centers = None
        self.analysis_results = {}
        
    def load_validation_data(self):
        """Load and clean validation CSV data"""
        print("Loading validation data...")
        self.validation_data = pd.read_csv(self.validation_csv_path)
        
        # Clean and standardize location names
        self.validation_data['location_name_clean'] = (
            self.validation_data['location_name']
            .str.lower()
            .str.replace('_', ' ')
            .str.replace('-', ' ')
            .str.strip()
        )
        
        # Convert date column
        self.validation_data['date'] = pd.to_datetime(self.validation_data['date'])
        
        # Calculate total visits per location
        self.location_totals = (
            self.validation_data
            .groupby('location_name_clean')
            .agg({
                'visits': ['sum', 'mean', 'count'],
                'date': ['min', 'max']
            })
            .round(2)
        )
        
        print(f"✓ Loaded {len(self.validation_data)} validation records")
        print(f"✓ Found {len(self.location_totals)} unique locations")
        return self.validation_data
    
    def load_cooling_centers_from_db(self, table_name="cooling_centers"):
        """Load cooling center data from database"""
        print(f"Loading cooling centers from database table: {table_name}")
        
        # Try different possible table names/queries
        possible_queries = [
            f"SELECT * FROM {table_name}",
            "SELECT * FROM cooling_centers",
            "SELECT * FROM parcels_with_cooling_centers_v5 WHERE nearest_center_names IS NOT NULL LIMIT 100",
            "SHOW TABLES"  # To see what tables are available
        ]
        
        for i, query in enumerate(possible_queries):
            try:
                if i == len(possible_queries) - 1:  # Last query is SHOW TABLES
                    tables = fetch_data(query)
                    print("Available tables:")
                    print(tables)
                    break
                else:
                    self.cooling_centers_db = fetch_data(query)
                    if self.cooling_centers_db is not None and not self.cooling_centers_db.empty:
                        print(f"✓ Successfully loaded cooling centers with query {i+1}")
                        print(f"✓ Found {len(self.cooling_centers_db)} cooling center records")
                        print(f"✓ Columns: {list(self.cooling_centers_db.columns)}")
                        return self.cooling_centers_db
            except Exception as e:
                print(f"Query {i+1} failed: {e}")
                continue
        
        # If database queries fail, create sample cooling center data for demonstration
        print("⚠️  Could not load from database. Creating sample data for demonstration...")
        self.create_sample_cooling_center_data()
        return self.cooling_centers_db
    
    def create_sample_cooling_center_data(self):
        """Create sample cooling center data based on validation locations"""
        unique_locations = self.validation_data['location_name_clean'].unique()
        
        # Create sample cooling center database
        sample_data = []
        for i, location in enumerate(unique_locations):
            sample_data.append({
                'center_id': i + 1,
                'center_name': location,
                'center_name_variations': location.replace(' ', '_'),
                'address': f"Sample Address {i+1}",
                'capacity': np.random.randint(50, 500),
                'type': np.random.choice(['library', 'community_center', 'rec_center', 'other'])
            })
        
        self.cooling_centers_db = pd.DataFrame(sample_data)
        print(f"✓ Created sample cooling center data with {len(self.cooling_centers_db)} centers")
    
    def fuzzy_match_locations(self, similarity_threshold=0.8):
        """Match validation locations with cooling center database using fuzzy matching"""
        from difflib import SequenceMatcher
        
        print("Performing fuzzy matching between validation data and cooling center database...")
        
        # Prepare cooling center names for matching
        if 'center_name' in self.cooling_centers_db.columns:
            cc_names = self.cooling_centers_db['center_name'].fillna('').str.lower().str.strip()
        elif 'name' in self.cooling_centers_db.columns:
            cc_names = self.cooling_centers_db['name'].fillna('').str.lower().str.strip()
        else:
            # Use first string column as name
            string_cols = self.cooling_centers_db.select_dtypes(include=['object']).columns
            if len(string_cols) > 0:
                cc_names = self.cooling_centers_db[string_cols[0]].fillna('').str.lower().str.strip()
            else:
                print("⚠️  No suitable name column found in cooling center data")
                return pd.DataFrame()
        
        validation_locations = self.validation_data['location_name_clean'].unique()
        
        matches = []
        for val_loc in validation_locations:
            best_match = None
            best_score = 0
            best_cc_idx = None
            
            for cc_idx, cc_name in enumerate(cc_names):
                # Calculate similarity
                similarity = SequenceMatcher(None, val_loc, cc_name).ratio()
                
                # Also check if words overlap
                val_words = set(val_loc.split())
                cc_words = set(cc_name.split())
                word_overlap = len(val_words.intersection(cc_words)) / max(len(val_words), len(cc_words))
                
                # Combined score
                combined_score = max(similarity, word_overlap)
                
                if combined_score > best_score:
                    best_score = combined_score
                    best_match = cc_name
                    best_cc_idx = cc_idx
            
            matches.append({
                'validation_location': val_loc,
                'matched_center': best_match,
                'match_score': best_score,
                'is_validated': best_score >= similarity_threshold,
                'center_index': best_cc_idx
            })
        
        self.matched_centers = pd.DataFrame(matches)
        
        validated_count = self.matched_centers['is_validated'].sum()
        print(f"✓ Matched {validated_count}/{len(validation_locations)} locations above threshold ({similarity_threshold})")
        
        return self.matched_centers
    
    def tag_cooling_centers_with_validation(self):
        """Add validation tags to cooling center database"""
        print("Tagging cooling centers with validation status...")
        
        # Create validation mapping
        validated_centers = self.matched_centers[self.matched_centers['is_validated']]
        validated_indices = validated_centers['center_index'].tolist()
        
        # Add validation tag to cooling center database
        self.cooling_centers_db['validate_tag'] = 0
        self.cooling_centers_db.loc[validated_indices, 'validate_tag'] = 1
        
        validated_count = self.cooling_centers_db['validate_tag'].sum()
        total_count = len(self.cooling_centers_db)
        
        print(f"✓ Tagged {validated_count}/{total_count} cooling centers as validated")
        
        return self.cooling_centers_db
    
    def analyze_visitation_patterns(self):
        """Analyze visitation patterns for validated vs non-validated centers"""
        print("Analyzing visitation patterns...")
        
        # Get validation location totals
        validated_locations = self.matched_centers[
            self.matched_centers['is_validated']
        ]['validation_location'].tolist()
        
        # Aggregate validation data by validation status
        self.validation_data['is_validated_location'] = (
            self.validation_data['location_name_clean'].isin(validated_locations)
        )
        
        # Calculate summary statistics
        validation_stats = (
            self.validation_data
            .groupby('is_validated_location')
            .agg({
                'visits': ['sum', 'mean', 'median', 'std', 'count'],
                'location_name_clean': 'nunique'
            })
            .round(2)
        )
        
        # Store results
        self.analysis_results = {
            'validation_stats': validation_stats,
            'total_validated_visits': self.validation_data[
                self.validation_data['is_validated_location']
            ]['visits'].sum(),
            'total_non_validated_visits': self.validation_data[
                ~self.validation_data['is_validated_location']
            ]['visits'].sum(),
            'validated_location_count': len(validated_locations),
            'non_validated_location_count': len(self.validation_data['location_name_clean'].unique()) - len(validated_locations)
        }
        
        print("✓ Visitation analysis complete")
        return self.analysis_results
    
    def create_visualizations(self, save_path="./figures/"):
        """Create comprehensive visualizations"""
        print("Creating visualizations...")
        
        # Ensure output directory exists
        os.makedirs(save_path, exist_ok=True)
        
        # Set up the plotting style
        plt.style.use('default')
        sns.set_palette("husl")
        
        # 1. Validation Match Scores Distribution
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        
        # Match scores histogram
        axes[0,0].hist(self.matched_centers['match_score'], bins=20, alpha=0.7, edgecolor='black')
        axes[0,0].axvline(0.8, color='red', linestyle='--', label='Validation Threshold')
        axes[0,0].set_title('Distribution of Match Scores')
        axes[0,0].set_xlabel('Match Score')
        axes[0,0].set_ylabel('Frequency')
        axes[0,0].legend()
        
        # Validation status pie chart
        validation_counts = self.matched_centers['is_validated'].value_counts()
        axes[0,1].pie(validation_counts.values, labels=['Not Validated', 'Validated'], 
                     autopct='%1.1f%%', startangle=90)
        axes[0,1].set_title('Cooling Centers Validation Status')
        
        # Total visits by validation status
        validated_visits = self.validation_data[
            self.validation_data['is_validated_location']
        ]['visits'].sum()
        non_validated_visits = self.validation_data[
            ~self.validation_data['is_validated_location']
        ]['visits'].sum()
        
        visit_data = [validated_visits, non_validated_visits]
        axes[1,0].bar(['Validated Centers', 'Non-Validated Centers'], visit_data, 
                     color=['green', 'red'], alpha=0.7)
        axes[1,0].set_title('Total Visits by Validation Status')
        axes[1,0].set_ylabel('Total Visits')
        
        # Average visits per day by validation status
        avg_visits = (
            self.validation_data
            .groupby('is_validated_location')['visits']
            .mean()
        )
        axes[1,1].bar(['Non-Validated', 'Validated'], avg_visits.values, 
                     color=['red', 'green'], alpha=0.7)
        axes[1,1].set_title('Average Daily Visits by Validation Status')
        axes[1,1].set_ylabel('Average Visits per Day')
        
        plt.tight_layout()
        plt.savefig(f"{save_path}validation_analysis_overview.png", dpi=300, bbox_inches='tight')
        plt.show()
        
        # 2. Time series analysis
        fig, axes = plt.subplots(2, 1, figsize=(15, 10))
        
        # Daily visits over time
        daily_visits = (
            self.validation_data
            .groupby(['date', 'is_validated_location'])['visits']
            .sum()
            .reset_index()
        )
        
        for validated in [True, False]:
            subset = daily_visits[daily_visits['is_validated_location'] == validated]
            label = 'Validated Centers' if validated else 'Non-Validated Centers'
            color = 'green' if validated else 'red'
            axes[0].plot(subset['date'], subset['visits'], label=label, color=color, alpha=0.7)
        
        axes[0].set_title('Daily Visits Over Time by Validation Status')
        axes[0].set_xlabel('Date')
        axes[0].set_ylabel('Total Daily Visits')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)
        
        # Weekly aggregated visits
        self.validation_data['week'] = self.validation_data['date'].dt.to_period('W')
        weekly_visits = (
            self.validation_data
            .groupby(['week', 'is_validated_location'])['visits']
            .sum()
            .reset_index()
        )
        weekly_visits['week_start'] = weekly_visits['week'].dt.start_time
        
        for validated in [True, False]:
            subset = weekly_visits[weekly_visits['is_validated_location'] == validated]
            label = 'Validated Centers' if validated else 'Non-Validated Centers'
            color = 'green' if validated else 'red'
            axes[1].bar(subset['week_start'], subset['visits'], 
                       alpha=0.7, label=label, color=color, width=5)
        
        axes[1].set_title('Weekly Visits by Validation Status')
        axes[1].set_xlabel('Week')
        axes[1].set_ylabel('Total Weekly Visits')
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(f"{save_path}validation_time_series.png", dpi=300, bbox_inches='tight')
        plt.show()
        
        print(f"✓ Visualizations saved to {save_path}")
    
    def generate_report(self):
        """Generate a comprehensive analysis report"""
        print("\n" + "="*80)
        print("COOLING CENTER VALIDATION ANALYSIS REPORT")
        print("="*80)
        
        print(f"\n📊 DATA SUMMARY:")
        print(f"   • Validation records: {len(self.validation_data):,}")
        print(f"   • Unique locations in validation data: {len(self.validation_data['location_name_clean'].unique())}")
        print(f"   • Cooling centers in database: {len(self.cooling_centers_db)}")
        print(f"   • Successfully matched centers: {self.matched_centers['is_validated'].sum()}")
        
        print(f"\n🎯 VALIDATION RESULTS:")
        validated_centers = self.cooling_centers_db['validate_tag'].sum()
        total_centers = len(self.cooling_centers_db)
        validation_rate = (validated_centers / total_centers) * 100
        print(f"   • Validated centers: {validated_centers}/{total_centers} ({validation_rate:.1f}%)")
        
        print(f"\n📈 VISITATION ANALYSIS:")
        validated_visits = self.analysis_results['total_validated_visits']
        non_validated_visits = self.analysis_results['total_non_validated_visits']
        total_visits = validated_visits + non_validated_visits
        
        print(f"   • Total visits: {total_visits:,}")
        print(f"   • Visits to validated centers: {validated_visits:,} ({validated_visits/total_visits*100:.1f}%)")
        print(f"   • Visits to non-validated centers: {non_validated_visits:,} ({non_validated_visits/total_visits*100:.1f}%)")
        
        # Average visits per location
        val_stats = self.analysis_results['validation_stats']
        if not val_stats.empty:
            print(f"\n📊 AVERAGE DAILY VISITS:")
            try:
                validated_avg = val_stats.loc[True, ('visits', 'mean')]
                non_validated_avg = val_stats.loc[False, ('visits', 'mean')]
                print(f"   • Validated centers: {validated_avg:.1f} visits/day")
                print(f"   • Non-validated centers: {non_validated_avg:.1f} visits/day")
            except:
                print("   • Could not calculate averages")
        
        print(f"\n🔍 TOP VISITED LOCATIONS:")
        top_locations = (
            self.validation_data
            .groupby('location_name_clean')['visits']
            .sum()
            .sort_values(ascending=False)
            .head(10)
        )
        
        for i, (location, visits) in enumerate(top_locations.items(), 1):
            validated_status = "✓" if location in self.matched_centers[
                self.matched_centers['is_validated']
            ]['validation_location'].values else "✗"
            print(f"   {i:2d}. {location:<30} {visits:>8,} visits {validated_status}")
        
        print("\n" + "="*80)
    
    def save_results(self, output_path="./results/"):
        """Save all results to files"""
        print(f"Saving results to {output_path}...")
        os.makedirs(output_path, exist_ok=True)
        
        # Save updated cooling center database with validation tags
        self.cooling_centers_db.to_csv(f"{output_path}cooling_centers_with_validation.csv", index=False)
        
        # Save matching results
        self.matched_centers.to_csv(f"{output_path}validation_matching_results.csv", index=False)
        
        # Save aggregated validation statistics
        validation_summary = (
            self.validation_data
            .groupby(['location_name_clean', 'is_validated_location'])
            .agg({
                'visits': ['sum', 'mean', 'count'],
                'date': ['min', 'max']
            })
            .reset_index()
        )
        validation_summary.to_csv(f"{output_path}validation_summary_by_location.csv", index=False)
        
        print(f"✓ Results saved to {output_path}")

def main():
    """Main execution function"""
    # Initialize the validator
    validator = CoolingCenterValidator('validate_cooling_summer_2024_panel.csv')
    
    # Step 1: Load validation data
    validator.load_validation_data()
    
    # Step 2: Load cooling centers from database
    validator.load_cooling_centers_from_db()
    
    # Step 3: Match locations using fuzzy matching
    validator.fuzzy_match_locations(similarity_threshold=0.8)
    
    # Step 4: Tag cooling centers with validation status
    validator.tag_cooling_centers_with_validation()
    
    # Step 5: Analyze visitation patterns
    validator.analyze_visitation_patterns()
    
    # Step 6: Create visualizations
    validator.create_visualizations()
    
    # Step 7: Generate comprehensive report
    validator.generate_report()
    
    # Step 8: Save all results
    validator.save_results()
    
    print("\n🎉 Analysis complete! Check the results and figures directories for outputs.")

if __name__ == "__main__":
    main()