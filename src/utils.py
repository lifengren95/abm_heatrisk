import os
import psycopg2
import pandas as pd
import geopandas as gpd

# Database connection parameters
DB_CONFIG = {
    'host': os.environ["PGHOST"], 
    'database': os.environ["PGDATABASE"], 
    'user': os.environ["PGUSER"], 
    'password': os.environ["PGPASSWORD"], 
    'port': os.environ.get("PGPORT", "5432") 
}

def connect_to_db():
    """Establish connection to PostgreSQL database"""
    try:
        connection = psycopg2.connect(**DB_CONFIG)
        print("Connection successful!")
        return connection
    except Exception as error:
        print(f"Error while connecting to PostgreSQL: {error}")
        return None

def fetch_data(query, params=None):
    """Execute a query and return results as a pandas DataFrame"""
    connection = connect_to_db()
    if connection:
        try:
            df = pd.read_sql(query, connection, params=params)
            return df
        except Exception as error:
            print(f"Error executing query: {error}")
            return None
        finally:
            connection.close()
            print("PostgreSQL connection closed.")
    return None

def fetch_spatial_data(query, params=None):
    """Execute a spatial query and return results as a GeoDataFrame"""
    connection = connect_to_db()
    if connection:
        try:
            gdf = gpd.read_postgis(query, connection, geom_col='geom', params=params)
            return gdf
        except Exception as error:
            print(f"Error executing spatial query: {error}")
            return None
        finally:
            connection.close()
            print("PostgreSQL connection closed.")
    return None