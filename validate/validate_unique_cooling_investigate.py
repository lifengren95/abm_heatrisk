import os
# -------------------------------------------------------------------
# investigate_cooling_center_parcel_matches.py
# -------------------------------------------------------------------
import geopandas as gpd
import pandas as pd
import sqlalchemy as sa
import textwrap
import os

# ---------- connection ----------
engine = sa.create_engine(
    os.environ["DATABASE_URL"]
)

parcel_geom  = "geometry"    # geometry column in public.parcels
center_geom  = "geometry"    # geometry column in public.clean_cooling_centers

# ---------- 1. CRS sanity check ----------
srid_df = pd.read_sql(textwrap.dedent(f"""
    SELECT
      (SELECT ST_SRID({parcel_geom}) FROM public.parcels LIMIT 1) AS srid_parcels,
      (SELECT ST_SRID({center_geom}) FROM public.clean_cooling_centers LIMIT 1) AS srid_centers
"""), engine)

print("\nCRS check:")
print(srid_df.to_string(index=False))

# ---------- 2. helper for unmatched IDs ----------
def unmatched_ids(sql_where):
    """Return list of cooling-center ids that didn't match parcels given a WHERE clause"""
    q = f"""
        SELECT c.id
        FROM   public.clean_cooling_centers AS c
        LEFT JOIN public.parcels          AS p
          ON ({sql_where})
        WHERE p.{parcel_geom} IS NULL
    """
    return pd.read_sql(q, engine)["id"].tolist()

# rule 1: strict contains
rule1 = f"ST_Contains(p.{parcel_geom}, c.{center_geom})"
rule2 = f"ST_Intersects(p.{parcel_geom}, c.{center_geom})"
# buffer 1 meter (adjust if degrees):
buffer_distance = 60        # 1 meter or 0.00001 degrees
rule3 = f"ST_Intersects(p.{parcel_geom}, ST_Buffer(c.{center_geom}, {buffer_distance}))"

unmatched_contains   = unmatched_ids(rule1)
unmatched_intersects = unmatched_ids(rule2)
unmatched_buffer     = unmatched_ids(rule3)

print(f"\nCooling-center count: {pd.read_sql('SELECT COUNT(*) FROM public.clean_cooling_centers', engine).iloc[0,0]}")
print(f"Unmatched (ST_Contains):                {len(unmatched_contains)}")
print(f"Unmatched (ST_Intersects):              {len(unmatched_intersects)}")
print(f"Unmatched (ST_Intersects + buffer {buffer_distance}): {len(unmatched_buffer)}")

# ---------- 3. Export still-unmatched after buffered match ----------
if unmatched_buffer:
    ids_str = ",".join(map(str, unmatched_buffer))
    pts_sql = f"""
        SELECT *
        FROM public.clean_cooling_centers
        WHERE id IN ({ids_str})
    """
    unmatched_gdf = gpd.read_postgis(
        pts_sql, engine, geom_col=center_geom, crs="EPSG:4326"
    )

    out_dir = os.environ.get("HEAT_OUTPUT_DIR", "./output")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "unmatched_cooling_centers.gpkg")
    unmatched_gdf.to_file(out_path, layer="unmatched_centers", driver="GPKG")
    print(f"\n→ Exported {len(unmatched_buffer)} unmatched points to {out_path}")
else:
    print("\nGreat! All centers matched after buffered intersects.")

print("\nDone.")
