import os
# export_cooling_center_parcels_final.py
import geopandas as gpd
import sqlalchemy as sa
import os

# ── database connection ────────────────────────────────────────────
engine = sa.create_engine(
    os.environ["DATABASE_URL"]
)

parcel_geom  = "geometry"   # geometry col in public.parcels
center_geom  = "geometry"   # geometry col in public.clean_cooling_centers
buffer_m     = 60           # ← final buffer distance (metres, EPSG 26915)

sql = f"""
SELECT DISTINCT ON (c.id)
       p.*,
       c.id AS cooling_center_id
FROM   public.parcels               AS p
JOIN   public.clean_cooling_centers AS c
  ON   ST_Intersects(
         p.{parcel_geom},
         ST_Buffer(c.{center_geom}, {buffer_m})
       )
ORDER  BY c.id, ST_Area(p.{parcel_geom});          -- keep smallest if >1
"""

gdf = gpd.read_postgis(sql, engine,
                       geom_col=parcel_geom,
                       crs="EPSG:26915")

assert gdf["cooling_center_id"].nunique() == 246, "Expected 246 unique parcels!"

# ── write to GeoPackage ────────────────────────────────────────────
out_dir = os.environ.get("HEAT_OUTPUT_DIR", "./output")
os.makedirs(out_dir, exist_ok=True)

out_path = os.path.join(out_dir, "cooling_center_parcels_246.gpkg")
gdf.to_file(out_path,
            layer="cooling_center_parcels",
            driver="GPKG")

print(f"✓  Saved 246 parcel footprints → {out_path}")
