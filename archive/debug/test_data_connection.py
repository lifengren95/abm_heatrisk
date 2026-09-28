# fixed_test_data_connection.py
# Updated test that recognizes materialized views

import sys
sys.path.append('./src')

from utils import connect_to_db, fetch_data

def test_database_access():
    """Test if we can access the required database and materialized view"""
    
    print("Testing database connection...")
    
    # Test basic connection
    conn = connect_to_db()
    if conn is None:
        print("✗ Database connection failed!")
        print("Possible issues:")
        print("  - Database server not accessible")
        print("  - Wrong credentials in src/utils.py")
        print("  - Firewall blocking connection")
        return False
    
    print("✓ Database connection successful!")
    conn.close()
    
    # Test if required materialized view exists (updated query)
    print("Testing required materialized view access...")
    
    query = """
    SELECT matviewname 
    FROM pg_matviews 
    WHERE matviewname = 'parcels_with_cooling_centers_v5'
    """
    
    result = fetch_data(query)
    if result is None or result.empty:
        print("✗ Required materialized view 'parcels_with_cooling_centers_v5' not found!")
        return False
    
    print("✓ Required materialized view found!")
    
    # Test data access
    print("Testing data access...")
    
    count_query = """
    SELECT COUNT(*) as count 
    FROM parcels_with_cooling_centers_v5 
    WHERE prop_type_res = 'Residential'
    """
    
    count_result = fetch_data(count_query)
    if count_result is not None and not count_result.empty:
        parcel_count = count_result.iloc[0]['count']
        print(f"✓ Found {parcel_count:,} residential parcels")
        if parcel_count == 0:
            print("⚠️ Warning: No residential parcels found!")
        return True
    else:
        print("✗ Could not query parcel data")
        return False

def test_required_columns():
    """Test if all required columns exist"""
    print("\nTesting required columns...")
    
    sample_query = """
    SELECT pid, prop_type_res, medianhhi, nearest_center_names, 
           nearest_center_distances, hh_owns_central_ac_2024, 
           hh_owns_ductless_ac_2024, geom
    FROM parcels_with_cooling_centers_v5 
    LIMIT 1
    """
    
    result = fetch_data(sample_query)
    if result is not None and not result.empty:
        print("✓ All required columns present!")
        print("Sample columns:", list(result.columns))
        return True
    else:
        print("✗ Could not verify required columns")
        return False

if __name__ == "__main__":
    print("=== Heat Risk Model Database Test (Fixed) ===")
    
    db_success = test_database_access()
    
    if db_success:
        columns_success = test_required_columns()
        
        if columns_success:
            print("\n✅ Database setup is COMPLETE!")
            print("🎉 You can now run the heat risk model!")
            print("\nNext steps:")
            print("1. Run the heat model with: python simple_run.py")
            print("2. Or open the Jupyter notebook: Model_final.ipynb")
        else:
            print("\n⚠️ Database works but some columns may be missing")
    else:
        print("\n✗ Database issues found. Check your connection settings.")
        print("\nNext steps:")
        print("1. Verify PostgreSQL is running")
        print("2. Check credentials in src/utils.py")
        print("3. Ensure materialized views are refreshed")