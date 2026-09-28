library(data.table)
library(dplyr)
library(sf)
library(osmdata)
library(stringr)

setDT(sim_validate_final_panel)

# --- 0) Targets ---------------------------------------------------------------
types_target <- c("Library", "Rec Com Cntr", "Shopping Mall")
names_by_type <- sim_validate_final_panel[
  type %in% types_target, .(name = unique(name)), by = type
][order(type, name)]

libs  <- names_by_type[type == "Library",        name]
recs  <- names_by_type[type == "Rec Com Cntr",   name]
malls <- names_by_type[type == "Shopping Mall",  name]

# Hennepin County bbox (you can swap in an exact county polygon if you have one)
hennepin_bbox <- getbb("Hennepin County, Minnesota, USA")

# --- 1) Helper: chunk a character vector (avoid very long Overpass queries) ---
chunk_vec <- function(x, n = 20) split(x, ceiling(seq_along(x) / n))

# --- 2) Query functions per type (points + polygons) --------------------------
get_libs <- function(nms) {
  out <- list()
  for (chunk in chunk_vec(nms, 20)) {
    q <- opq(bbox = hennepin_bbox) |>
      add_osm_feature(key = "amenity", value = "library") |>
      add_osm_feature(key = "name", value = chunk, value_exact = FALSE, match_case = FALSE)
    r <- osmdata_sf(q)
    out <- c(out, list(r))
  }
  out
}

get_recs <- function(nms) {
  # try several common tags for rec/community centers
  out <- list()
  for (chunk in chunk_vec(nms, 15)) {
    # community centres
    q1 <- opq(bbox = hennepin_bbox) |>
      add_osm_feature("amenity", "community_centre") |>
      add_osm_feature("name", chunk, value_exact = FALSE, match_case = FALSE)
    out <- c(out, list(osmdata_sf(q1)))
    
    # sports centres / fitness centres (many MPRB recs fall here)
    q2 <- opq(bbox = hennepin_bbox) |>
      add_osm_feature("leisure", c("sports_centre","fitness_centre")) |>
      add_osm_feature("name", chunk, value_exact = FALSE, match_case = FALSE)
    out <- c(out, list(osmdata_sf(q2)))
  }
  out
}

get_malls <- function(nms) {
  out <- list()
  for (chunk in chunk_vec(nms, 20)) {
    q <- opq(bbox = hennepin_bbox) |>
      add_osm_feature("shop", "mall") |>
      add_osm_feature("name", chunk, value_exact = FALSE, match_case = FALSE)
    r <- osmdata_sf(q)
    out <- c(out, list(r))
  }
  out
}

# --- 3) Compact extractor for points & polygons from an osmdata list ----------
bind_osm <- function(lst, type_label) {
  if (length(lst) == 0) return(NULL)
  pts <- lapply(lst, \(x) try(x$osm_points, silent = TRUE))
  pol <- lapply(lst, \(x) try(x$osm_polygons, silent = TRUE))
  mul <- lapply(lst, \(x) try(x$osm_multipolygons, silent = TRUE))
  
  sf_pts <- do.call(rbind, lapply(pts, \(x) if (inherits(x, "try-error") || is.null(x)) NULL else st_as_sf(x)))
  sf_pol <- do.call(rbind, lapply(pol, \(x) if (inherits(x, "try-error") || is.null(x)) NULL else st_as_sf(x)))
  sf_mul <- do.call(rbind, lapply(mul, \(x) if (inherits(x, "try-error") || is.null(x)) NULL else st_as_sf(x)))
  
  # tag the type and keep only relevant columns
  keep_cols <- function(g) {
    if (is.null(g)) return(NULL)
    g |> mutate(type = type_label) |>
      select(type, name, building, `building:levels`, amenity, leisure, shop, everything())
  }
  
  list(
    pts = keep_cols(sf_pts),
    polys = keep_cols(rbind(sf_pol, sf_mul))
  )
}

# --- 4) Run queries -----------------------------------------------------------
lib_res  <- bind_osm(get_libs(libs),   "Library")
rec_res  <- bind_osm(get_recs(recs),   "Rec Com Cntr")
mall_res <- bind_osm(get_malls(malls), "Shopping Mall")

# Merge results for each geometry type
pts_all   <- rbind(lib_res$pts,  rec_res$pts,  mall_res$pts)
polys_all <- rbind(lib_res$polys,rec_res$polys,mall_res$polys)

# --- 5) If we have polygons with names, compute areas directly ----------------
# Project to UTM 15N for accurate areas
proj_crs <- 26915
polys_all <- suppressWarnings(st_make_valid(polys_all))
polys_all_utm <- st_transform(polys_all, proj_crs)

if (nrow(polys_all_utm)) {
  polys_all_utm$area_m2  <- as.numeric(st_area(polys_all_utm))
  polys_all_utm$area_ft2 <- polys_all_utm$area_m2 * 10.7639
  # levels (optional)
  polys_all_utm$levels <- suppressWarnings(as.numeric(polys_all_utm$`building:levels`))
  polys_all_utm$levels[is.na(polys_all_utm$levels) | polys_all_utm$levels < 1] <- 1
  polys_all_utm$floor_area_ft2 <- polys_all_utm$area_ft2 * polys_all_utm$levels
}

# --- 6) For POINT matches: fetch nearby building footprints & compute areas ---
# (small buffer per point to capture the building shell)
fetch_buildings_near <- function(pt_sf, radius_m = 60) {
  if (nrow(pt_sf) == 0) return(NULL)
  # buffer in projected CRS, then back to WGS84 to build bbox for Overpass
  pt_utm <- st_transform(pt_sf, proj_crs)
  buf    <- st_buffer(pt_utm, dist = radius_m)
  bb_wgs <- st_bbox(st_transform(buf, 4326))
  
  q <- opq(bbox = bb_wgs) |> add_osm_feature(key = "building")
  r <- try(osmdata_sf(q), silent = TRUE)
  if (inherits(r, "try-error")) return(NULL)
  
  # Use polygons; if none, return NULL
  bp <- rbind(
    tryCatch(st_as_sf(r$osm_polygons), error = \(e) NULL),
    tryCatch(st_as_sf(r$osm_multipolygons), error = \(e) NULL)
  )
  if (is.null(bp) || nrow(bp) == 0) return(NULL)
  
  bp <- suppressWarnings(st_make_valid(bp))
  bp_utm <- st_transform(bp, proj_crs)
  bp_utm$area_m2  <- as.numeric(st_area(bp_utm))
  bp_utm$area_ft2 <- bp_utm$area_m2 * 10.7639
  bp_utm$levels   <- suppressWarnings(as.numeric(bp_utm$`building:levels`))
  bp_utm$levels[is.na(bp_utm$levels) | bp_utm$levels < 1] <- 1
  bp_utm$floor_area_ft2 <- bp_utm$area_ft2 * bp_utm$levels
  
  # keep the largest building as the primary footprint
  bp_utm |> arrange(desc(area_m2)) |> slice(1)
}

point_rows <- NULL
if (!is.null(pts_all) && nrow(pts_all) > 0) {
  pts_all$src_name <- pts_all$name
  # keep only points whose names are in your list (defensive)
  pts_all <- pts_all |>
    filter(
      (type == "Library"        & src_name %in% libs)  |
        (type == "Rec Com Cntr"   & src_name %in% recs)  |
        (type == "Shopping Mall"  & src_name %in% malls)
    )
  
  # For each point, fetch nearby building
  res_list <- vector("list", nrow(pts_all))
  for (i in seq_len(nrow(pts_all))) {
    b <- fetch_buildings_near(pts_all[i, , drop = FALSE], radius_m = 80)
    if (!is.null(b) && nrow(b) > 0) {
      b$type     <- pts_all$type[i]
      b$src_name <- pts_all$src_name[i]
      res_list[[i]] <- b
    }
    # polite pause for Overpass
    Sys.sleep(0.5)
  }
  point_rows <- do.call(rbind, res_list)
}

# --- 7) Union polygon-based results ------------------------------------------
poly_rows <- NULL
if (!is.null(polys_all_utm) && nrow(polys_all_utm) > 0) {
  # keep only polygons whose names match your list
  polys_all_utm$src_name <- polys_all_utm$name
  poly_rows <- polys_all_utm |>
    filter(
      (type == "Library"        & src_name %in% libs)  |
        (type == "Rec Com Cntr"   & src_name %in% recs)  |
        (type == "Shopping Mall"  & src_name %in% malls)
    )
}

matched_polys <- rbind(poly_rows, point_rows)

# Deduplicate by (type, src_name), keeping the largest footprint
if (!is.null(matched_polys) && nrow(matched_polys) > 0) {
  matched_polys <- matched_polys |>
    st_drop_geometry() |>
    group_by(type, src_name) |>
    slice_max(order_by = area_m2, n = 1, with_ties = FALSE) |>
    ungroup()
} else {
  matched_polys <- tibble()
}

# --- 8) Occupant-load factors (ft2/person) & capacity ranges ------------------
occ_factors <- function(typ) {
  if (typ == "Library")          return(c(min_pp = 50,  max_pp = 100))  # reading vs stacks
  if (typ == "Shopping Mall")    return(c(min_pp = 30,  max_pp = 60))   # mercantile range
  if (typ == "Rec Com Cntr")     return(c(min_pp = 15,  max_pp = 15))   # assembly (tables & chairs)
  return(c(min_pp = 60, max_pp = 60))
}

capacity_tbl <- NULL
if (nrow(matched_polys) > 0) {
  capacity_tbl <- as.data.table(matched_polys)[
    , c("ft2_pp_low","ft2_pp_high") := {
      v <- occ_factors(type[1])
      list(v["min_pp"], v["max_pp"])
    }, by = .(type)
  ][
    , `:=`(
      # prefer floor area if levels present; else footprint
      used_area_ft2 = ifelse(!is.na(floor_area_ft2) & floor_area_ft2 > area_ft2, floor_area_ft2, area_ft2),
      capacity_low  = floor(used_area_ft2 / ft2_pp_high),  # conservative
      capacity_high = ceiling(used_area_ft2 / ft2_pp_low)  # optimistic
    )
  ][
    , .(type, name = src_name,
        area_m2 = round(area_m2, 1),
        area_ft2 = round(area_ft2, 1),
        building_levels = ifelse(is.na(levels), NA_real_, levels),
        est_floor_area_ft2 = round(used_area_ft2, 1),
        ft2_per_person_low  = ft2_pp_low,
        ft2_per_person_high = ft2_pp_high,
        capacity_low, capacity_high)
  ]
}

# --- 9) Outputs ---------------------------------------------------------------
names_table[]         # your full list of names by type
capacity_tbl[]        # area + estimated capacity (should not be empty now)

