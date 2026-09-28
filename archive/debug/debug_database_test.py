# debug_database_test.py
# Let's see what's actually in the database

import sys
sys.path.append('./src')

from utils import fetch_data

def debug_database():
    print("=== Debugging Database Contents ===")
    
    # Check if the materialized view exists
    print("1. Checking for materialized views...")
    mv_query = """
    SELECT schemaname, matviewname 
    FROM pg_matviews 
    WHERE matviewname LIKE '%parcels_with_cooling_centers%'
    """
    
    mv_result = fetch_data(mv_query)
    if mv_result is not None:
        print("Found materialized views:")
        print(mv_result)
    else:
        print("No materialized views found or query failed")
    
    # Check if it exists as a regular table
    print("\n2. Checking for regular tables...")
    table_query = """
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_name LIKE '%parcels_with_cooling_centers%'
    """
    
    table_result = fetch_data(table_query)
    if table_result is not None:
        print("Found tables:")
        print(table_result)
    else:
        print("No tables found matching pattern")
    
    # Try to query the materialized view directly
    print("\n3. Testing direct access to materialized view...")
    try:
        count_query = "SELECT COUNT(*) as count FROM parcels_with_cooling_centers_v5"
        count_result = fetch_data(count_query)
        if count_result is not None:
            print(f"✓ Success! Found {count_result.iloc[0]['count']} records")
            
            # Get a sample row
            sample_query = "SELECT * FROM parcels_with_cooling_centers_v5 LIMIT 1"
            sample_result = fetch_data(sample_query)
            if sample_result is not None:
                print("Sample columns:", list(sample_result.columns))
        else:
            print("✗ Could not query the materialized view")
    except Exception as e:
        print(f"✗ Error querying materialized view: {e}")
    
    # Check what tables actually exist
    print("\n4. All tables and views in database:")
    all_query = """
    SELECT table_name, table_type 
    FROM information_schema.tables 
    WHERE table_schema = 'public'
    ORDER BY table_name
    """
    
    all_result = fetch_data(all_query)
    if all_result is not None:
        print(all_result.to_string())

if __name__ == "__main__":
    debug_database()