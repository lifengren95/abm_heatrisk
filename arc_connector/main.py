import os
import string
import json
from flask import Flask, request, jsonify
import psycopg2
from psycopg2 import sql

# Database connection
conn = psycopg2.connect(
    dbname=os.environ["PGDATABASE"],
    user=os.environ["PGUSER"],
    password=os.environ["PGPASSWORD"],
    host=os.environ["PGHOST"],
    port="5432"
)

cur = conn.cursor()

app = Flask(__name__)

@app.route("/get_table/<table_name>")
def get_polygon(table_name):
    return jsonify(get_geojson(table_name))
    
def get_geojson(table_name):
    try:
        query = sql.SQL("""
            SELECT json_build_object(
                'type', 'FeatureCollection',
                'features', json_agg(
                    json_build_object(
                        'type', 'Feature',
                        'geometry', ST_AsGeoJSON(ST_Transform(geometry, 4326))::json,
                        'properties', to_jsonb(t) - 'geometry'
                    )
                )
            )
            FROM {} t;
        """).format(sql.Identifier(table_name))

        cur.execute(query)

        geojson = cur.fetchone()[0] 
        # cur.close()
        # conn.close()
        return geojson
    except Exception as e:
        conn.rollback()  # Rollback failed transaction
        print("Error:", e)
        return {"error": str(e)}
    
if __name__ == "__main__":
    app.run(
      debug=True, 
      host='0.0.0.0', 
      port=8080)
