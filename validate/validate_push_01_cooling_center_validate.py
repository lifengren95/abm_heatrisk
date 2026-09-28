#!/usr/bin/env python3
"""
Script to update cooling_centers table in database with new validate_tag column
Author: Project contributors
Date: 2025-06-26

This script reads the updated cooling_center.csv file and replaces the existing 
cooling_centers table in the PostgreSQL database.
"""
import os

import pandas as pd
import psycopg2
from psycopg2 import sql
import sys
import os
from sqlalchemy import create_engine
import geopandas as gpd
from shapely.geometry import Point

# Database connection parameters (matching your existing configuration)
DB_CONFIG = {
    'host': os.environ["PGHOST"],
    'database': os.environ["PGDATABASE"],
    'user': os.environ["PGUSER"],
    'password': os.environ["PGPASSWORD"],
    'port': '15432'
}


def connect_to_db():
    """Establish connection to PostgreSQL database"""
    try:
        connection = psycopg2.connect(**DB_CONFIG)
        print("✓ Connection to database successful!")
        return connection
    except Exception as error:
        print(f"✗ Error while connecting to PostgreSQL: {error}")
        return None

def create_sqlalchemy_engine():
    """Create SQLAlchemy engine for pandas to_sql operations"""
    try:
        connection_string = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
        engine = create_engine(connection_string)
        print("✓ SQLAlchemy engine created successfully!")
        return engine
    except Exception as error:
        print(f"✗ Error creating SQLAlchemy engine: {error}")
        return None

def backup_existing_table(connection):
    """Create a backup of the existing cooling_centers table"""
    try:
        cursor = connection.cursor()
        
        # Create backup table with timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_table_name = f"cooling_centers_backup_{timestamp}"
        
        backup_query = sql.SQL("""
            CREATE TABLE {} AS 
            SELECT * FROM cooling_centers;
        """).format(sql.Identifier(backup_table_name))
        
        cursor.execute(backup_query)
        connection.commit()
        cursor.close()
        print(f"✓ Backup table created: {backup_table_name}")
        return backup_table_name
        
    except Exception as error:
        print(f"✗ Error creating backup: {error}")
        connection.rollback()
        return None

def read_cooling_center_csv(csv_path):
    """Read the cooling center CSV file and prepare for database insertion"""
    try:
        # Read CSV file
        df = pd.read_csv(csv_path)
        print(f"✓ CSV file loaded successfully with {len(df)} rows")
        print(f"✓ Columns: {list(df.columns)}")
        
        # Check if validate_tag column exists
        if 'validate_tag' not in df.columns:
            print("✗ Error: 'validate_tag' column not found in CSV file")
            return None
        
        # Display validate_tag distribution
        validate_counts = df['validate_tag'].value_counts()
        print(f"✓ Validate_tag distribution:")
        print(f"  - No validation needed (0): {validate_counts.get(0, 0)}")
        print(f"  - Validation needed (1): {validate_counts.get(1, 0)}")
        
        return df
        
    except Exception as error:
        print(f"✗ Error reading CSV file: {error}")
        return None

def prepare_geodataframe(df):
    """Convert DataFrame to GeoDataFrame if geometry columns exist"""
    try:
        # Check if lat/lon or x/y columns exist to create geometry
        if 'latitude' in df.columns and 'longitude' in df.columns:
            # Create geometry from lat/lon
            geometry = [Point(xy) for xy in zip(df['longitude'], df['latitude'])]
            gdf = gpd.GeoDataFrame(df, geometry=geometry)
            gdf = gdf.set_crs('EPSG:4326')  # WGS84
            # Transform to your project CRS (assuming UTM Zone 15N like in your code)
            gdf = gdf.to_crs('EPSG:26915')
            print("✓ Geometry created from latitude/longitude columns")
            return gdf
            
        elif 'x' in df.columns and 'y' in df.columns:
            # Create geometry from x/y coordinates
            geometry = [Point(xy) for xy in zip(df['x'], df['y'])]
            gdf = gpd.GeoDataFrame(df, geometry=geometry)
            gdf = gdf.set_crs('EPSG:26915')  # Assuming UTM Zone 15N
            print("✓ Geometry created from x/y columns")
            return gdf
            
        else:
            print("⚠ Warning: No coordinate columns found. Uploading as regular DataFrame.")
            return df
            
    except Exception as error:
        print(f"✗ Error creating GeoDataFrame: {error}")
        return df

def update_cooling_centers_table(df, engine, connection):
    """Replace the cooling_centers table with new data"""
    try:
        cursor = connection.cursor()
        
        # Drop existing table
        drop_query = "DROP TABLE IF EXISTS cooling_centers CASCADE;"
        cursor.execute(drop_query)
        print("✓ Existing cooling_centers table dropped")
        
        # Close cursor before using pandas to_sql
        cursor.close()
        
        # Handle GeoDataFrame differently to avoid geoalchemy2 dependency
        if isinstance(df, gpd.GeoDataFrame):
            # Convert geometry to WKT format for upload
            df_for_upload = df.copy()
            df_for_upload['geom_wkt'] = df_for_upload['geometry'].apply(lambda x: x.wkt)
            # Drop the geometry column for regular upload
            df_for_upload = df_for_upload.drop(columns=['geometry'])
            
            # Upload as regular DataFrame
            df_for_upload.to_sql(
                name='cooling_centers_temp',
                con=engine,
                if_exists='replace',
                index=False,
                method='multi'
            )
            print("✓ Data uploaded to temporary table")
            
            # Now create the final table with proper geometry using SQL
            cursor = connection.cursor()
            
            # Get the SRID from the original GeoDataFrame (should be 26915 based on your code)
            srid = df.crs.to_epsg() if df.crs else 26915
            
            create_final_table_query = f"""
                CREATE TABLE cooling_centers AS
                SELECT 
                    name, id, address, city, zip, phone, type, status, hours, website, 
                    fee, in_out, notes, joinfield, utm_x, utm_y, latitude, longitude, 
                    climateana, censustrac, inhennepin, inside_hennepin, validate_tag,
                    ST_GeomFromText(geom_wkt, {srid}) as geom
                FROM cooling_centers_temp;
            """
            
            cursor.execute(create_final_table_query)
            
            # Drop the temporary table
            cursor.execute("DROP TABLE cooling_centers_temp;")
            
            # Create spatial index for better performance
            cursor.execute("CREATE INDEX idx_cooling_centers_geom ON cooling_centers USING GIST (geom);")
            
            cursor.close()
            print("✓ New cooling_centers table created with PostGIS geometry")
            
        else:
            # For regular DataFrame, use to_sql
            df.to_sql(
                name='cooling_centers',
                con=engine,
                if_exists='replace',
                index=False,
                method='multi'
            )
            print("✓ New cooling_centers table created")
        
        connection.commit()
        print(f"✓ Successfully uploaded {len(df)} cooling centers to database")
        
        return True
        
    except Exception as error:
        print(f"✗ Error updating table: {error}")
        connection.rollback()
        return False

def verify_update(connection):
    """Verify the table was updated correctly"""
    try:
        cursor = connection.cursor()
        
        # Check table structure
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'cooling_centers'
            ORDER BY ordinal_position;
        """)
        
        columns = cursor.fetchall()
        print("✓ Table structure verification:")
        for col_name, col_type in columns:
            print(f"  - {col_name}: {col_type}")
        
        # Check validate_tag column specifically
        cursor.execute("""
            SELECT validate_tag, COUNT(*) 
            FROM cooling_centers 
            GROUP BY validate_tag 
            ORDER BY validate_tag;
        """)
        
        validate_distribution = cursor.fetchall()
        print("✓ Validate_tag distribution in database:")
        for tag_value, count in validate_distribution:
            status = "No validation needed" if tag_value == 0 else "Validation needed"
            print(f"  - {tag_value} ({status}): {count} cooling centers")
        
        cursor.close()
        return True
        
    except Exception as error:
        print(f"✗ Error during verification: {error}")
        return False

def main():
    """Main function to update cooling centers table"""
    
    print("🌡️ Updating Cooling Centers Database")
    print("=" * 50)
    
    # Get CSV file path
    default_path = r"~\hennepin\data\validate_data\intermediate\cooling_center.csv"
    csv_path = input(f"Enter path to cooling_center.csv file (or press Enter for '{default_path}'): ").strip()
    if not csv_path:
        csv_path = default_path
    
    # Check if file exists
    if not os.path.exists(csv_path):
        print(f"✗ Error: File not found: {csv_path}")
        sys.exit(1)
    
    # Read CSV file
    df = read_cooling_center_csv(csv_path)
    if df is None:
        sys.exit(1)
    
    # Prepare geometry if possible
    df = prepare_geodataframe(df)
    
    # Connect to database
    connection = connect_to_db()
    if connection is None:
        sys.exit(1)
    
    # Create SQLAlchemy engine
    engine = create_sqlalchemy_engine()
    if engine is None:
        connection.close()
        sys.exit(1)
    
    try:
        # Create backup of existing table
        backup_name = backup_existing_table(connection)
        if backup_name is None:
            print("⚠ Warning: Could not create backup, continuing anyway...")
        
        # Confirm before proceeding
        confirm = input("\n⚠ This will replace the existing cooling_centers table. Continue? (y/N): ").strip().lower()
        if confirm != 'y':
            print("Operation cancelled by user.")
            return
        
        # Update the table
        success = update_cooling_centers_table(df, engine, connection)
        
        if success:
            # Verify the update
            verify_update(connection)
            print("\n✅ Cooling centers table updated successfully!")
            print("You can now run your heat risk simulations with the updated data.")
            if backup_name:
                print(f"💾 Backup table available as: {backup_name}")
        else:
            print("\n❌ Failed to update cooling centers table")
    
    except Exception as error:
        print(f"✗ Unexpected error: {error}")
    
    finally:
        # Close connections
        if connection:
            connection.close()
        if engine:
            engine.dispose()
        print("📝 Database connections closed.")

if __name__ == "__main__":
    main()