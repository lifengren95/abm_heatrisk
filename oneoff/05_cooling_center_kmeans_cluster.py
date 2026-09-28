#!/usr/bin/env python3
"""
K-Means Clustering for Cooling Centers
Adds cluster4_tag and cluster8_tag based on geographic location
Uses cooling center parcel centroids from GPKG for clustering
"""
import os

import pandas as pd
import geopandas as gpd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import warnings
import os
from pathlib import Path
import fiona
from shapely.geometry import shape

warnings.filterwarnings('ignore')

# Set environment variables to avoid PROJ issues
os.environ['PROJ_LIB'] = ''
os.environ['GDAL_DATA'] = ''

def cluster_cooling_centers():
    """Main function to cluster cooling centers using K-means"""
    
    print("="*70)
    print("K-MEANS CLUSTERING FOR COOLING CENTERS")
    print("="*70)
    
    # File paths
    input_csv = r"~\hennepin\data\validate_data\intermediate\cooling_center_with_buildyr.csv"
    input_gpkg = r"~\hennepin\data\validate_data\intermediate\cooling_center_with_buildyr.gpkg"
    
    output_csv = r"~\hennepin\data\validate_data\intermediate\cooling_center_with_buildyr_clustered.csv"
    output_gpkg = r"~\hennepin\data\validate_data\intermediate\cooling_center_with_buildyr_clustered.gpkg"
    
    # Step 1: Load CSV data
    print("\n1. Loading data...")
    print("   Loading CSV...")
    df_csv = pd.read_csv(input_csv)
    print(f"   ✓ Loaded {len(df_csv)} cooling centers from CSV")
    
    # Step 2: Load GPKG data with geometry
    print("   Loading GPKG with geometry...")
    
    try:
        # Try standard geopandas read
        gdf = gpd.read_file(input_gpkg)
        print(f"   ✓ Loaded {len(gdf)} cooling centers from GPKG")
    except Exception as e:
        print(f"   ⚠ Standard read failed, using alternative method...")
        
        # Alternative method using fiona
        with fiona.open(input_gpkg, 'r') as src:
            # Read features and geometries
            features = []
            geometries = []
            
            for feat in src:
                properties = dict(feat['properties'])
                geom = shape(feat['geometry'])
                features.append(properties)
                geometries.append(geom)
            
            # Create GeoDataFrame
            gdf = pd.DataFrame(features)
            gdf = gpd.GeoDataFrame(gdf, geometry=geometries)
            
            # Try to set CRS to Minnesota projected system
            try:
                gdf.set_crs('EPSG:26915', inplace=True)
            except:
                pass
        
        print(f"   ✓ Loaded {len(gdf)} cooling centers using alternative method")
    
    # Verify data consistency
    if len(df_csv) != len(gdf):
        print(f"   ⚠ Warning: CSV has {len(df_csv)} records, GPKG has {len(gdf)} records")
    
    # Step 3: Extract centroids from GPKG geometries
    print("\n2. Extracting geographic centroids...")
    
    # Get centroids of cooling center parcels
    gdf['centroid'] = gdf.geometry.centroid
    
    # Extract X, Y coordinates
    gdf['centroid_x'] = gdf.centroid.x
    gdf['centroid_y'] = gdf.centroid.y
    
    # Check for any invalid geometries
    valid_geoms = gdf.geometry.is_valid & ~gdf.geometry.is_empty
    if not valid_geoms.all():
        print(f"   ⚠ Warning: {(~valid_geoms).sum()} cooling centers have invalid geometry")
        # Use only valid geometries for clustering
        valid_gdf = gdf[valid_geoms].copy()
    else:
        valid_gdf = gdf.copy()
        print(f"   ✓ All {len(valid_gdf)} geometries are valid")
    
    # Prepare coordinate matrix for clustering
    X = valid_gdf[['centroid_x', 'centroid_y']].values
    print(f"   ✓ Extracted coordinates for {len(X)} cooling centers")
    print(f"   Coordinate ranges: X [{X[:, 0].min():.0f}, {X[:, 0].max():.0f}], Y [{X[:, 1].min():.0f}, {X[:, 1].max():.0f}]")
    
    # Step 4: Apply K-means clustering for 4 clusters
    print("\n3. Applying K-means clustering...")
    print("   Creating 4 clusters...")
    
    kmeans_4 = KMeans(
        n_clusters=4,
        random_state=42,  # For reproducibility
        n_init=10,        # Number of times to run with different centroid seeds
        init='k-means++'  # Smart initialization
    )
    
    clusters_4 = kmeans_4.fit_predict(X)
    valid_gdf['cluster4_tag'] = clusters_4 + 1  # Convert 0-3 to 1-4
    
    # Calculate silhouette score for 4 clusters
    silhouette_4 = silhouette_score(X, clusters_4)
    inertia_4 = kmeans_4.inertia_
    
    print(f"   ✓ 4-cluster results:")
    print(f"     - Silhouette score: {silhouette_4:.3f}")
    print(f"     - Inertia: {inertia_4:,.0f}")
    
    # Show cluster sizes
    cluster4_counts = valid_gdf['cluster4_tag'].value_counts().sort_index()
    print("     - Cluster sizes:")
    for cluster_id, count in cluster4_counts.items():
        print(f"       Cluster {cluster_id}: {count} cooling centers")
    
    # Step 5: Apply K-means clustering for 8 clusters
    print("\n   Creating 8 clusters...")
    
    kmeans_8 = KMeans(
        n_clusters=8,
        random_state=42,
        n_init=10,
        init='k-means++'
    )
    
    clusters_8 = kmeans_8.fit_predict(X)
    valid_gdf['cluster8_tag'] = clusters_8 + 1  # Convert 0-7 to 1-8
    
    # Calculate silhouette score for 8 clusters
    silhouette_8 = silhouette_score(X, clusters_8)
    inertia_8 = kmeans_8.inertia_
    
    print(f"   ✓ 8-cluster results:")
    print(f"     - Silhouette score: {silhouette_8:.3f}")
    print(f"     - Inertia: {inertia_8:,.0f}")
    
    # Show cluster sizes
    cluster8_counts = valid_gdf['cluster8_tag'].value_counts().sort_index()
    print("     - Cluster sizes:")
    for cluster_id, count in cluster8_counts.items():
        print(f"       Cluster {cluster_id}: {count} cooling centers")
    
    # Step 6: Calculate distances to cluster centroids
    print("\n4. Calculating distances to cluster centroids...")
    
    # For 4 clusters
    valid_gdf['cluster4_centroid_x'] = valid_gdf['cluster4_tag'].map(
        dict(enumerate(kmeans_4.cluster_centers_[:, 0], 1))
    )
    valid_gdf['cluster4_centroid_y'] = valid_gdf['cluster4_tag'].map(
        dict(enumerate(kmeans_4.cluster_centers_[:, 1], 1))
    )
    valid_gdf['cluster4_centroid_dist'] = np.sqrt(
        (valid_gdf['centroid_x'] - valid_gdf['cluster4_centroid_x'])**2 + 
        (valid_gdf['centroid_y'] - valid_gdf['cluster4_centroid_y'])**2
    )
    
    # For 8 clusters
    valid_gdf['cluster8_centroid_x'] = valid_gdf['cluster8_tag'].map(
        dict(enumerate(kmeans_8.cluster_centers_[:, 0], 1))
    )
    valid_gdf['cluster8_centroid_y'] = valid_gdf['cluster8_tag'].map(
        dict(enumerate(kmeans_8.cluster_centers_[:, 1], 1))
    )
    valid_gdf['cluster8_centroid_dist'] = np.sqrt(
        (valid_gdf['centroid_x'] - valid_gdf['cluster8_centroid_x'])**2 + 
        (valid_gdf['centroid_y'] - valid_gdf['cluster8_centroid_y'])**2
    )
    
    print(f"   ✓ Average distance to cluster centroid (4 clusters): {valid_gdf['cluster4_centroid_dist'].mean():.0f} meters")
    print(f"   ✓ Average distance to cluster centroid (8 clusters): {valid_gdf['cluster8_centroid_dist'].mean():.0f} meters")
    
    # Step 7: Merge cluster assignments back to full dataset
    print("\n5. Merging cluster assignments...")
    
    # If we filtered out invalid geometries, merge back
    if len(valid_gdf) < len(gdf):
        # Add cluster tags to original gdf
        gdf = gdf.merge(
            valid_gdf[['cooling_center_id', 'cluster4_tag', 'cluster8_tag', 
                      'cluster4_centroid_dist', 'cluster8_centroid_dist']],
            on='cooling_center_id',
            how='left'
        )
        # Fill NaN values for invalid geometries
        gdf['cluster4_tag'] = gdf['cluster4_tag'].fillna(0).astype(int)
        gdf['cluster8_tag'] = gdf['cluster8_tag'].fillna(0).astype(int)
    else:
        gdf = valid_gdf.copy()
    
    # Step 8: Add cluster tags to CSV
    print("   Adding cluster tags to CSV data...")
    
    # Merge based on cooling center ID
    df_csv = df_csv.merge(
        gdf[['cooling_center_id', 'cluster4_tag', 'cluster8_tag', 
             'cluster4_centroid_dist', 'cluster8_centroid_dist']],
        left_on='id',
        right_on='cooling_center_id',
        how='left'
    )
    
    # Drop redundant cooling_center_id column
    if 'cooling_center_id' in df_csv.columns:
        df_csv = df_csv.drop(columns=['cooling_center_id'])
    
    print(f"   ✓ Added cluster tags to {len(df_csv)} CSV records")
    
    # Step 9: Clean up temporary columns before saving
    print("\n6. Cleaning up data for export...")
    
    # Remove temporary columns from GDF
    columns_to_drop = ['centroid', 'centroid_x', 'centroid_y', 
                       'cluster4_centroid_x', 'cluster4_centroid_y',
                       'cluster8_centroid_x', 'cluster8_centroid_y']
    
    for col in columns_to_drop:
        if col in gdf.columns:
            gdf = gdf.drop(columns=[col])
    
    # Step 10: Save results
    print("\n7. Saving results...")
    
    # Save CSV
    df_csv.to_csv(output_csv, index=False)
    print(f"   ✓ Saved CSV to: {output_csv}")
    
    # Save GPKG
    try:
        gdf.to_file(output_gpkg, driver="GPKG")
        print(f"   ✓ Saved GPKG to: {output_gpkg}")
    except Exception as e:
        print(f"   ⚠ Could not save GPKG: {e}")
        # Try saving without problematic columns
        gdf_simple = gdf.drop(columns=['cluster4_centroid_dist', 'cluster8_centroid_dist'])
        try:
            gdf_simple.to_file(output_gpkg, driver="GPKG")
            print(f"   ✓ Saved GPKG (simplified) to: {output_gpkg}")
        except:
            print(f"   ⚠ Could not save GPKG, saving as shapefile instead")
            shp_path = output_gpkg.replace('.gpkg', '.shp')
            gdf_simple.to_file(shp_path)
            print(f"   ✓ Saved as shapefile: {shp_path}")
    
    # Step 11: Generate cluster summary report
    print("\n8. CLUSTER SUMMARY REPORT")
    print("="*70)
    
    print("\n4-CLUSTER ANALYSIS:")
    for cluster_id in range(1, 5):
        cluster_data = gdf[gdf['cluster4_tag'] == cluster_id]
        if len(cluster_data) > 0:
            print(f"\n   Cluster {cluster_id}:")
            print(f"   - Size: {len(cluster_data)} cooling centers")
            print(f"   - Types: {cluster_data['type'].value_counts().head(3).to_dict()}")
            if 'build_yr' in cluster_data.columns:
                valid_years = cluster_data['build_yr'].dropna()
                if len(valid_years) > 0:
                    print(f"   - Avg building year: {valid_years.mean():.0f}")
            print(f"   - Avg distance to centroid: {cluster_data['cluster4_centroid_dist'].mean():.0f} meters")
    
    print("\n8-CLUSTER ANALYSIS:")
    for cluster_id in range(1, 9):
        cluster_data = gdf[gdf['cluster8_tag'] == cluster_id]
        if len(cluster_data) > 0:
            print(f"\n   Cluster {cluster_id}:")
            print(f"   - Size: {len(cluster_data)} cooling centers")
            print(f"   - Most common type: {cluster_data['type'].mode().values[0] if len(cluster_data['type'].mode()) > 0 else 'N/A'}")
    
    print("\n✅ CLUSTERING COMPLETE!")
    print(f"📊 Files saved:")
    print(f"   - CSV: {output_csv}")
    print(f"   - GPKG: {output_gpkg}")
    
    return df_csv, gdf

if __name__ == "__main__":
    try:
        # Run clustering
        csv_result, gpkg_result = cluster_cooling_centers()
        
        print("\n🎉 Script completed successfully!")
        print("\nNew columns added:")
        print("- cluster4_tag: Cluster assignment (1-4)")
        print("- cluster8_tag: Cluster assignment (1-8)")
        print("- cluster4_centroid_dist: Distance to 4-cluster centroid")
        print("- cluster8_centroid_dist: Distance to 8-cluster centroid")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()