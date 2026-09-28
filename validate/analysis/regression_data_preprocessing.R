##############################################
# Libraries & Setup
##############################################
library(data.table)
library(stringdist)   # for amatch/stringdist

setwd("./validate/analysis")

##############################################
# Step 1: Clean Cooling Center data
##############################################

# Inputs
cooling_center_data_buffercovar <- fread("../../../../data/validate_data/intermediate/cooling_center_with_buildyr_catchment.csv")
cooling_center_cluster          <- fread("../../../../data/validate_data/intermediate/cooling_center_with_buildyr_clustered.csv")

# Drop unused columns
cols_to_drop <- c(
  "ABBREV_ADD","ABSTR_TORR","ADDITION_N","BLDG_MV1","BLDG_MV2","BLDG_MV3","BLDG_MV4","BLOCK",
  "BUILD_YR","COMP_JUDG_","CONDO_NO","CONT_IND1","CONT_IND2","CONT_IND3","CONT_IND4","CO_OP_IND",
  "DIV_PEND_I","DIV_STATUS","EARLIEST_D","FEATURECOD","FORFEIT_LA","FRAC_HOUSE","GR_ACRE_OP","HMSTD_CD1",
  "HMSTD_CD2","HMSTD_CD3","HMSTD_CD4","HMS_EXCL1","HMS_EXCL2","HMS_EXCL3","HMS_EXCL4","HOUSE_NO",
  "LAND_MV1","LAND_MV2","LAND_MV3","LAND_MV4","LAT","LON","LOT","MACH_MV1","MACH_MV2","MACH_MV3",
  "MACH_MV4","MAILING_MU","MAILING__1","METES_BNDS","METES_BN_1","METES_BN_2","METES_BN_3","MKT_VAL_TO",
  "MORE_METES","MTG_CO_NBR","MULTI_ADDR","MUNIC_CD","MUNIC_NM","NET_IMPRV_","NET_TAX1","NET_TAX2",
  "NET_TAX3","NET_TAX4","NET_TAX_PD","NET_TC1","NET_TC2","NET_TC3","NET_TC4","OBJECTID","OWNER_NM",
  "OWNER_PCT1","OWNER_PCT2","OWNER_PCT3","OWNER_PCT4","PARCEL_ARE","PETITION_R","PID","PID_TEXT",
  "PRI_SEC_CO","PROPERTY_S","PR_TYP_CD1","PR_TYP_CD2","PR_TYP_CD3","PR_TYP_CD4","PR_TYP_NM1","PR_TYP_NM2",
  "PR_TYP_NM3","PR_TYP_NM4","QUAL_IMPR1","QUAL_IMPR2","QUAL_IMPR3","QUAL_IMPR4","SALE_CODE","SALE_CODE_",
  "SALE_DATE","SALE_PRICE","SCHOOL_DIS","SEWER_DIST","STATE_CD","STREET_NM","ShapeSTAre","ShapeSTLen",
  "TAXABLE_VA","TAXPAYER_1","TAXPAYER_2","TAXPAYER_3","TAXPAYER_N","TAX_ADJ_PE","TAX_TOT","TIF_PROJEC",
  "TORRENS_TY","TOTAL_MV1","TOTAL_MV2","TOTAL_MV3","TOTAL_MV4","TOT_NET_TA","TOT_PENALT","TOT_SPEC_T",
  "VET_EXCL1","VET_EXCL2","VET_EXCL3","VET_EXCL4","WATERSHED_","ZIP_CD","analyze"
)
cooling_center_data_buffercovar[, (cols_to_drop) := NULL]

# Standardize id
setnames(cooling_center_data_buffercovar, "cooling_center_id", "id", skip_absent = TRUE)

# Keep cluster essentials
cooling_center_cluster <- cooling_center_cluster[, .(
  id, build_yr, cluster4_tag, cluster8_tag, cluster4_centroid_dist, cluster8_centroid_dist
)]

# Ensure DT & merge left by id
setDT(cooling_center_data_buffercovar)
setDT(cooling_center_cluster)

clean_cooling_centers_covar <- merge(
  cooling_center_data_buffercovar,
  cooling_center_cluster,
  by = "id",
  all.x = TRUE
)

# Save
fwrite(clean_cooling_centers_covar, "../../../../data/validate_data/analysis/clean_cooling_centers_covar.csv")

##############################################
# Step 2: Clean Validation Data
##############################################

## 2.1 Cellphone visitation (2020/2021 July)
cellphonefiles <- c(
  "../../../../data/validate_data/raw/cellphone_pid_data/cooling_center_visitation_2020July.csv",
  "../../../../data/validate_data/raw/cellphone_pid_data/cooling_center_visitation_2021July.csv"
)
cellphone_visitation_2020 <- fread(cellphonefiles[1])
cellphone_visitation_2021 <- fread(cellphonefiles[2])

cellphone_visitation <- rbindlist(
  list(cellphone_visitation_2020, cellphone_visitation_2021),
  use.names = TRUE, fill = TRUE
)

# Standardize names
setnames(cellphone_visitation,
         old = c("Date","Visitation","Name"),
         new = c("date","visits","name"),
         skip_absent = TRUE)

# Parse date robustly
cellphone_visitation[, date := as.IDate(date)]
if (cellphone_visitation[is.na(date), .N] > 0) {
  cellphone_visitation[, date := as.IDate(date, format = "%m/%d/%Y")]
}

# Rename to cellphone_visits BEFORE subsetting
if ("visits" %in% names(cellphone_visitation) && !"cellphone_visits" %in% names(cellphone_visitation)) {
  setnames(cellphone_visitation, "visits", "cellphone_visits")
}

# If 'id' missing but we have 'name', attach via normalized join to cooling centers
norm_key <- function(x) {
  x <- iconv(x, to = "ASCII//TRANSLIT")
  x <- tolower(x)
  x <- gsub("&", " and ", x, fixed = TRUE)
  x <- gsub("\\bsaint\\b", "st", x, perl = TRUE)
  x <- gsub("\\bst\\.?\\b", "st", x, perl = TRUE)
  x <- gsub("[^a-z0-9]+", " ", x)
  x <- gsub("\\s+", " ", x)
  trimws(x)
}

lookup <- unique(clean_cooling_centers_covar[, .(name = trimws(name), id)])
lookup[, name_key := norm_key(name)]

if (!"id" %in% names(cellphone_visitation) && "name" %in% names(cellphone_visitation)) {
  cellphone_visitation[, name_key := norm_key(name)]
  cellphone_visitation <- merge(
    cellphone_visitation,
    lookup[, .(name_key, id)],
    by = "name_key",
    all.x = TRUE
  )
  cellphone_visitation[, name_key := NULL]
}

# Drop unused if present
cellphone_visitation[, address := NULL]

# Minimal
cellphone_visitation_min <- cellphone_visitation[, .(id, date, cellphone_visits)]

## 2.2 Library visitation 2024 (libraries + parks/beaches)
library_visitation_2024 <- fread("../../../../data/validate_data/intermediate/validate_cooling_summer_2024_panel.csv")

library_map <- c(
  "arvonne_fraser_library"      = "Arvonne Fraser Library",
  "augsburg_park_library"       = "Augsburg Park Library",
  "brookdale_library"           = "Brookdale Library",
  "brooklyn_park_library"       = "Brooklyn Park Library",
  "champlin_library"            = "Champlin Library",
  "east_lake_library"           = "East Lake Library",
  "eden_prairie_library"        = "Eden Prairie Library",
  "edina_library"               = "Edina Library",
  "elm_creek"                   = "Elm Creek Park Reserve",
  "excelsior_library"           = "Excelsior Library",
  "franklin_library"            = "Franklin Library",
  "golden_valley_library"       = "Golden Valley Library",
  "hopkins_library"             = "Hopkins Library",
  "hosmer_library"              = "Hosmer Library",
  "lake_minnetonka"             = "Excelsior Commons Beach",
  "linden_hills_library"        = "Linden Hills Library",
  "long_lake_library"           = "Long Lake Library",
  "maple_grove_library"         = "Maple Grove Library",
  "maple_plain_library"         = "Maple Plain Library",
  "minneapolis_central_library" = "Minneapolis Central Library",
  "minnetonka_library"          = "Minnetonka Library",
  "nokomis_library"             = "Nokomis Library",
  "north_regional_library"      = "North Regional Library",
  "northeast_library"           = "Northeast Library",
  "osseo_library"               = "Osseo Library",
  "oxboro_library"              = "Oxboro Library",
  "penn_lake_library"           = "Penn Lake Library",
  "plymouth_library"            = "Plymouth Community Library",
  "ridgedale_library"           = "Ridgedale Library",
  "rockford_road_library"       = "Rockford Road Library",
  "rogers_library"              = "Rogers Library",
  "roosevelt_library"           = "Roosevelt Library",
  "southdale_library"           = "Southdale Library",
  "st_anthony_library"          = "St. Anthony Library",
  "st_bonifacius_library"       = "St. Bonifacius Library",
  "st_louis_park_library"       = "St. Louis Park Library",
  "walker_library"              = "Walker Library",
  "washburn_library"            = "Washburn Library",
  "wayzata_library"             = "Wayzata Library",
  "webber_park_library"         = "Webber Park Library",
  "westonka_library"            = "Westonka Library"
)

setDT(library_visitation_2024)
library_visitation_2024[, date := as.IDate(date)]
if (library_visitation_2024[is.na(date), .N] > 0) {
  library_visitation_2024[, date := as.IDate(date, format = "%m/%d/%Y")]
}

library_visitation_2024[, name := library_map[location_name]]
library_visitation_2024[, name_key := norm_key(name)]

# attach id
library_lookup <- unique(clean_cooling_centers_covar[, .(name = trimws(name), id)])
library_lookup[, name_key := norm_key(name)]

library_visitation_2024_id <- merge(
  library_visitation_2024,
  library_lookup[, .(name_key, id)],
  by = "name_key",
  all.x = TRUE
)

# QA
cat("Library matched ids: ",
    sum(!is.na(library_visitation_2024_id$id)), " / ",
    nrow(library_visitation_2024_id), "\n", sep = "")

still_no_id_lib <- unique(library_visitation_2024_id[is.na(id), name])
if (length(still_no_id_lib)) {
  message("Unmatched library names: ", paste(still_no_id_lib, collapse = " | "))
}

# Tidy
library_visitation_2024_id[, c("name_key","location_name") := NULL]
setnames(library_visitation_2024_id, "visits", "lib_visits", skip_absent = TRUE)
library_visitation_min <- library_visitation_2024_id[, .(id, date, lib_visits)]

## 2.3 ED encounters (daily, county-level)
edfiles <- c(
  "../../../../data/validate_data/raw/ED/ed_encounters_2023_0501_0930.csv",
  "../../../../data/validate_data/raw/ED/ed_encounters_2024_0501_0930.csv"
)
ed_encounters_2023 <- fread(edfiles[1])
ed_encounters_2024 <- fread(edfiles[2])

ed_encounters_2023[, year := 2023]
ed_encounters_2024[, year := 2024]

ed_encounters <- rbindlist(list(ed_encounters_2023, ed_encounters_2024), use.names = TRUE, fill = TRUE)

# Standardize column name if needed
if (!"ed_encounters" %in% names(ed_encounters)) {
  if ("encounters" %in% names(ed_encounters)) {
    setnames(ed_encounters, "encounters", "ed_encounters")
  }
}

# Parse date & aggregate by date
ed_encounters[, date := as.IDate(date, format = "%m/%d/%Y")]
ed_encounters <- ed_encounters[, .(ed_encounters = sum(ed_encounters, na.rm = TRUE)), by = .(date)]

## 2.4 Build master panel (id, name, date) and merge real-world visitation
all_dates <- unique(sort(c(
  seq(as.IDate("2020-07-01"), as.IDate("2020-07-31"), by = "day"),
  seq(as.IDate("2021-07-01"), as.IDate("2021-07-31"), by = "day"),
  seq(as.IDate("2023-05-01"), as.IDate("2023-09-30"), by = "day"),
  seq(as.IDate("2024-05-01"), as.IDate("2024-09-30"), by = "day")
)))

id_name_lookup <- unique(clean_cooling_centers_covar[, .(id, name)])
ids <- sort(unique(id_name_lookup$id))

panel <- CJ(id = ids, date = all_dates, unique = TRUE)
panel <- merge(panel, id_name_lookup, by = "id", all.x = TRUE)
setcolorder(panel, c("id","name","date"))

# Join cellphone + library on id/date
cellphone_lib_merged <- merge(
  library_visitation_min, cellphone_visitation_min,
  by = c("id","date"), all = TRUE
)

validate_panel <- merge(panel, cellphone_lib_merged, by = c("id","date"), all.x = TRUE)
validate_panel <- merge(validate_panel, ed_encounters, by = "date", all.x = TRUE)
setorder(validate_panel, id, date)

# ---------------------------
# De-duplicate validate_panel
# ---------------------------
setDT(validate_panel)

cat("Rows before:", nrow(validate_panel), "\n")

# 1) drop exact dup rows (all columns identical)
validate_panel <- unique(validate_panel)

# 2) collapse to one row per (id,date), keeping the one with most non-missing info
#    build an info score from the columns you care about
info_cols <- intersect(
  c("lib_visits", "cellphone_visits", "ed_encounters", "simulate_parcel_visits"),
  names(validate_panel)
)

if (length(info_cols) == 0L) {
  validate_panel[, info_score := 0L]
} else {
  validate_panel[, info_score := rowSums(!is.na(.SD)), .SDcols = info_cols]
}

# sort: best (highest info_score) first within (id,date)
setorder(validate_panel, id, date, -info_score)

# keep first per (id,date)
validate_panel <- unique(validate_panel, by = c("id","date"))

# clean up
validate_panel[, info_score := NULL]

# final checks
cat("Rows after :", nrow(validate_panel), "\n")
stopifnot(validate_panel[, .N, by = .(id, date)][, max(N) == 1L])

# Save
fwrite(validate_panel, "../../../../data/validate_data/analysis/validate_panel.csv")

##############################################
# Step 3: Merge Simulation Data (no Step 4)
##############################################

## 3.1 County-level sim metrics
msi_runs_alldates <- fread("../../../../output/results/geometric_model_1000runs/combined_summary_all_years.csv")
setDT(msi_runs_alldates)
msi_runs_alldates[, date := as.IDate(as.character(date), format = "%Y%m%d")]
msi_runs_alldates[, year := NULL]

vars_to_rename <- c(
  "total_parcels","stayed_home","moved",
  "stayed_home_pct","moved_pct",
  "avg_probability","avg_stability","avg_temperature",
  "ac_data_source","ac_external_pct"
)
setnames(msi_runs_alldates,
         old = vars_to_rename,
         new = paste0(vars_to_rename, "_allcounty"),
         skip_absent = TRUE)

## 3.2 Individual cooling option sim visitation
sim_cooling_visits <- fread("../../../../output/results/geometric_model_1000runs/sim_cooling_visits_geometric_abm.csv")
setDT(sim_cooling_visits)
sim_cooling_visits[, date := as.IDate(as.character(date), format = "%Y%m%d")]

# Attach county-level metrics
sim_individual_and_allcounty <- merge(
  sim_cooling_visits, msi_runs_alldates,
  by = "date", all.x = TRUE
)
setorder(sim_individual_and_allcounty, name, date)

## 3.3 Map sim names -> panel names/ids and merge onto validate_panel
# Canonical panels
dt_panel <- unique(clean_cooling_centers_covar[, .(panel_name = name)])
panel_lookup <- unique(clean_cooling_centers_covar[, .(panel_name = name, id)])

# Sim names
dt_sim <- unique(sim_cooling_visits[, .(sim_name = name)])

# Normalization helpers
norm_chars <- function(x) {
  x <- tolower(x)
  x <- gsub("–|—", "-", x)
  x <- gsub("&", " and ", x)
  x <- gsub("'", "", x)
  x <- gsub("[[:punct:]]", " ", x)
  x <- gsub("\\s+", " ", x)
  trimws(x)
}

dt_sim[,  sim_key_full     := norm_chars(sim_name)]
dt_panel[,panel_key_full   := norm_chars(panel_name)]
dt_sim[,  sim_key_noparen  := gsub("\\s*\\(.*?\\)", "", sim_key_full)]
dt_panel[,panel_key_noparen:= gsub("\\s*\\(.*?\\)", "", panel_key_full)]

std_repls <- data.table(
  from = c("\\bctr\\b","\\bcntr\\b","\\brec\\b","\\bst\\.?\\b"),
  to   = c("center","center","recreation","saint")
)
for (i in seq_len(nrow(std_repls))) {
  dt_sim[,  sim_key_full     := gsub(std_repls$from[i], std_repls$to[i], sim_key_full)]
  dt_panel[,panel_key_full   := gsub(std_repls$from[i], std_repls$to[i], panel_key_full)]
  dt_sim[,  sim_key_noparen  := gsub(std_repls$from[i], std_repls$to[i], sim_key_noparen)]
  dt_panel[,panel_key_noparen:= gsub(std_repls$from[i], std_repls$to[i], panel_key_noparen)]
}

# Exact matches (full, then no-paren)
exact_full <- merge(
  dt_sim[, .(sim_name, sim_key_full)],
  dt_panel[, .(panel_name, panel_key_full)],
  by.x = "sim_key_full", by.y = "panel_key_full", all.x = TRUE
)

unmatched <- exact_full[
  is.na(panel_name),
  .(sim_name, sim_key_noparen = gsub("\\s*\\(.*?\\)", "", norm_chars(sim_name)))
]

exact_noparen <- merge(
  unmatched,
  unique(dt_panel[, .(panel_name, panel_key_noparen)]),
  by.x = "sim_key_noparen", by.y = "panel_key_noparen", all.x = TRUE
)

exact_joined <- merge(
  exact_full[, .(sim_name, panel_name_exact = panel_name)],
  exact_noparen[, .(sim_name, panel_name_exact_noparen = panel_name)],
  by = "sim_name", all.x = TRUE
)
exact_joined[, panel_match :=
               fifelse(!is.na(panel_name_exact), panel_name_exact,
                       fifelse(!is.na(panel_name_exact_noparen), panel_name_exact_noparen, NA_character_))]

# Fuzzy for remaining
still_unmatched <- merge(
  dt_sim[, .(sim_name, sim_key_full, sim_key_noparen)],
  exact_joined[, .(sim_name, panel_match)],
  by = "sim_name", all.x = TRUE
)[is.na(panel_match)]

panel_keys <- unique(c(dt_panel$panel_key_full, dt_panel$panel_key_noparen))
panel_keys_lookup <- unique(rbindlist(list(
  dt_panel[, .(panel_key = panel_key_full, panel_name)],
  dt_panel[, .(panel_key = panel_key_noparen, panel_name)]
)))

still_unmatched[, idx := amatch(sim_key_noparen, panel_keys, method = "osa", maxDist = 6)]
still_unmatched[, panel_key_suggest := ifelse(is.na(idx), NA_character_, panel_keys[idx])]
still_unmatched[, dist := ifelse(is.na(idx), NA_integer_,
                                 stringdist(sim_key_noparen, panel_key_suggest, method = "osa"))]

still_unmatched <- merge(
  still_unmatched[, .(sim_name, sim_key_full, sim_key_noparen, panel_key_suggest, dist)],
  panel_keys_lookup,
  by.x = "panel_key_suggest", by.y = "panel_key", all.x = TRUE
)[order(dist)]

# Manual overrides (extend as needed)
manual_overrides <- data.table(
  sim_name = c(
    "MN Valley National Wildlife Refuge—Bloomington Vis",
    "Wabun (Minnehaha Park) Wading Pool",
    "NorthPoint Health & Wellness Center (formerly Work"
  ),
  panel_name = c(
    "MN Valley National Wildlife Refuge—Bloomington Visitor Center",
    "Wabun Wading Pool (at Minnehaha Regional Park)",
    "NorthPoint Health & Wellness Center (formerly Workforce Center)"
  )
)

# Final mapping: manual > exact > fuzzy (dist<=3)
final_map <- unique(dt_sim[, .(sim_name)])
final_map <- merge(final_map, manual_overrides, by = "sim_name", all.x = TRUE)
final_map <- merge(final_map, exact_joined[, .(sim_name, panel_match)], by = "sim_name", all.x = TRUE)
final_map <- merge(final_map, still_unmatched[, .(sim_name, panel_name_suggest = panel_name, dist)], by = "sim_name", all.x = TRUE)

final_map[, panel_name_final :=
            fifelse(!is.na(panel_name), panel_name,
                    fifelse(!is.na(panel_match), panel_match,
                            fifelse(!is.na(panel_name_suggest) & dist <= 3, panel_name_suggest, NA_character_)))]

# Attach id to sim rows
map_to_id <- merge(
  final_map[, .(sim_name, panel_name_final)],
  panel_lookup, by.x = "panel_name_final", by.y = "panel_name",
  all.x = TRUE
)

sim_individual_and_allcounty <- merge(
  sim_individual_and_allcounty,
  map_to_id[, .(name = sim_name, id)],
  by = "name", all.x = TRUE
)

# Merge sim metrics onto validate_panel by id+date
validate_panel <- merge(
  validate_panel,
  sim_individual_and_allcounty[, .(
    id, date, simulate_parcel_visits,
    stayed_home_allcounty, moved_allcounty,
    stayed_home_pct_allcounty, moved_pct_allcounty,
    avg_probability_allcounty, avg_stability_allcounty,
    avg_temperature_allcounty
  )],
  by = c("id","date"),
  all.x = TRUE
)

# Zero-fill simulated visits
validate_panel[is.na(simulate_parcel_visits), simulate_parcel_visits := 0L]

# Save (this is still Step 3 output; NOT doing Step 4)
fwrite(validate_panel, "../../../../data/validate_data/analysis/validate_panel.csv")

# Optional: separate sim-only panel (name/date grid)
panel_grid <- unique(panel[, .(name, date)])
sim_on_panel <- merge(
  panel_grid,
  merge(
    sim_individual_and_allcounty,
    final_map[, .(name = sim_name, panel_name = panel_name_final)],
    by = "name", all.x = TRUE
  )[
    , .(panel_name, date, simulate_parcel_visits,
        stayed_home_allcounty, moved_allcounty,
        stayed_home_pct_allcounty, moved_pct_allcounty,
        avg_probability_allcounty, avg_stability_allcounty,
        avg_temperature_allcounty)
  ],
  by.x = c("name","date"),
  by.y = c("panel_name","date"),
  all.x = TRUE
)
sim_on_panel <- unique(sim_on_panel, by = c("name","date"))
sim_on_panel[is.na(simulate_parcel_visits), simulate_parcel_visits := 0L]

# --- FIX: avoid name/date collisions before merging covariates ---
covars <- copy(clean_cooling_centers_covar)
covars[, c("name","date") := NULL]   # safe even if "date" doesn't exist

# left side keeps a clean "name" column from panel
left_with_covar <- merge(
  panel[, .(id, name, date)],
  covars,
  by = "id",
  all.x = TRUE
)

# sanity checks (optional)
# print(intersect(names(left_with_covar), c("name","date")))

# now this merge will find "name" and "date" on both sides
final_sim_panel <- merge(
  left_with_covar,
  sim_on_panel,                # must have cols: name, date, simulate_parcel_visits, ...
  by = c("name","date"),
  all.x = TRUE
)

# (optional) verify
stopifnot(all(c("name","date") %in% names(final_sim_panel)))

fwrite(final_sim_panel, "../../../../data/validate_data/analysis/final_sim_panel.csv")

# Done

################################################################################

# Drop sim columns from validate_panel
validate_panel[, c(
  "simulate_parcel_visits",
  grep("_allcounty$", names(validate_panel), value = TRUE)
) := NULL]
validate_panel[, c("name") := NULL]  


head(final_sim_panel)
head(validate_panel)

setDT(final_sim_panel)
setDT(validate_panel)

# 0) Make sure key types align
final_sim_panel[, date := as.IDate(date)]
validate_panel[,   date := as.IDate(date)]
# If id might be character in either:
# final_sim_panel[, id := as.integer(id)]
# validate_panel[,   id := as.integer(id)]

# 1) Choose ONLY validation columns not already in final_sim_panel (besides keys)
val_candidate_cols <- c("lib_visits", "cellphone_visits", "ed_encounters")
val_cols_to_add <- intersect(val_candidate_cols, names(validate_panel))

# 2) Build a slim validation table with just keys + new cols
val_slim <- validate_panel[, c("id", "date", val_cols_to_add), with = FALSE]

# 3) Ensure uniqueness on (id,date) in val_slim
if (val_slim[, .N, by = .(id, date)][, any(N > 1L)]) {
  # keep the richest row per (id,date)
  val_slim[, info_score := rowSums(!is.na(.SD)), .SDcols = val_cols_to_add]
  setorder(val_slim, id, date, -info_score)
  val_slim <- unique(val_slim, by = c("id", "date"))
  val_slim[, info_score := NULL]
}

# 4) Merge onto final_sim_panel by id + date (keep all sim rows)
sim_validate_final_panel <- merge(
  final_sim_panel,
  val_slim,
  by = c("id", "date"),
  all.x = TRUE
)

# 5) Quick QA
stopifnot(sim_validate_final_panel[, .N, by = .(id, date)][, max(N) == 1L])
print(head(sim_validate_final_panel))


## Step 4.2: Last Step Heat Event Tagging ----
setDT(sim_validate_final_panel)

# ensure proper types/columns
sim_validate_final_panel[, date := as.IDate(date)]
stopifnot("avg_temperature_allcounty" %in% names(sim_validate_final_panel))

# start with zeros
sim_validate_final_panel[, heat_tag := 0L]

# 1) fixed heat-event dates for 2024
hot_2024 <- as.IDate(c("2024-08-26","2024-08-27"))
sim_validate_final_panel[date %in% hot_2024, heat_tag := 1L]

# 2) top 5 hottest dates for 2020, 2021, 2023 (by avg_temperature_allcounty)
#    aggregate to a unique (year, date) temperature first
temp_by_date <- sim_validate_final_panel[
  year(date) %in% c(2020, 2021, 2023),
  .(avg_temp = mean(suppressWarnings(as.numeric(avg_temperature_allcounty)), na.rm = TRUE)),
  by = .(yr = year(date), date)
][!is.nan(avg_temp)]

# pick top 5 per year (ties broken by earlier date last)
top5_dates <- temp_by_date[
  order(yr, -avg_temp, date),
  .SD[seq_len(min(.N, 5)), .(date)],
  by = yr
]

# tag those dates
sim_validate_final_panel[date %in% top5_dates$date, heat_tag := 1L]

# quick QA (optional)
sim_validate_final_panel[, .(heat_days = uniqueN(date[heat_tag == 1L])), by = year(date)][order(year)]


# ED tag
sim_validate_final_panel[, ed_tag := fifelse(!is.na(ed_encounters), 1L, 0L)]

# Cellphone tag
sim_validate_final_panel[, cellphone_tag := fifelse(!is.na(cellphone_visits), 1L, 0L)]

# Library + Elm Creek tag
sim_validate_final_panel[, lib_plus_elmcreek_tag := fifelse(!is.na(lib_visits), 1L, 0L)]


fwrite(sim_validate_final_panel, "../../../../data/validate_data/analysis/sim_validate_final_panel.csv")















































































# library(data.table)
# 
# setwd("./validate/analysis")
# 
# 
# cooling_center_data_buffercovar <- fread("../../../../data/validate_data/intermediate/cooling_center_with_buildyr_catchment.csv")
# cooling_center_cluster <- fread("../../../../data/validate_data/intermediate/cooling_center_with_buildyr_clustered.csv")
# 
# 
# 
# ########################################
# # Step 1: Clean Cooling Center data ----
# ########################################
# 
# 
# cols_to_drop <- c(
#   "ABBREV_ADD", "ABSTR_TORR", "ADDITION_N", "BLDG_MV1", "BLDG_MV2", "BLDG_MV3", "BLDG_MV4", "BLOCK",
#   "BUILD_YR", "COMP_JUDG_", "CONDO_NO", "CONT_IND1", "CONT_IND2", "CONT_IND3", "CONT_IND4", "CO_OP_IND",
#   "DIV_PEND_I", "DIV_STATUS", "EARLIEST_D", "FEATURECOD", "FORFEIT_LA", "FRAC_HOUSE", "GR_ACRE_OP", "HMSTD_CD1",
#   "HMSTD_CD2", "HMSTD_CD3", "HMSTD_CD4", "HMS_EXCL1", "HMS_EXCL2", "HMS_EXCL3", "HMS_EXCL4", "HOUSE_NO",
#   "LAND_MV1", "LAND_MV2", "LAND_MV3", "LAND_MV4", "LAT", "LON", "LOT", "MACH_MV1", "MACH_MV2", "MACH_MV3",
#   "MACH_MV4", "MAILING_MU", "MAILING__1", "METES_BNDS", "METES_BN_1", "METES_BN_2", "METES_BN_3", "MKT_VAL_TO",
#   "MORE_METES", "MTG_CO_NBR", "MULTI_ADDR", "MUNIC_CD", "MUNIC_NM", "NET_IMPRV_", "NET_TAX1", "NET_TAX2",
#   "NET_TAX3", "NET_TAX4", "NET_TAX_PD", "NET_TC1", "NET_TC2", "NET_TC3", "NET_TC4", "OBJECTID", "OWNER_NM",
#   "OWNER_PCT1", "OWNER_PCT2", "OWNER_PCT3", "OWNER_PCT4", "PARCEL_ARE", "PETITION_R", "PID", "PID_TEXT",
#   "PRI_SEC_CO", "PROPERTY_S", "PR_TYP_CD1", "PR_TYP_CD2", "PR_TYP_CD3", "PR_TYP_CD4", "PR_TYP_NM1", "PR_TYP_NM2",
#   "PR_TYP_NM3", "PR_TYP_NM4", "QUAL_IMPR1", "QUAL_IMPR2", "QUAL_IMPR3", "QUAL_IMPR4", "SALE_CODE", "SALE_CODE_",
#   "SALE_DATE", "SALE_PRICE", "SCHOOL_DIS", "SEWER_DIST", "STATE_CD", "STREET_NM", "ShapeSTAre", "ShapeSTLen",
#   "TAXABLE_VA", "TAXPAYER_1", "TAXPAYER_2", "TAXPAYER_3", "TAXPAYER_N", "TAX_ADJ_PE", "TAX_TOT", "TIF_PROJEC",
#   "TORRENS_TY", "TOTAL_MV1", "TOTAL_MV2", "TOTAL_MV3", "TOTAL_MV4", "TOT_NET_TA", "TOT_PENALT", "TOT_SPEC_T",
#   "VET_EXCL1", "VET_EXCL2", "VET_EXCL3", "VET_EXCL4", "WATERSHED_", "ZIP_CD", "analyze"
# )
# 
# cooling_center_data_buffercovar[, (cols_to_drop) := NULL]
# 
# setnames(cooling_center_data_buffercovar, "cooling_center_id", "id")
# 
# cooling_center_cluster <- cooling_center_cluster[, .(
#   id,
#   build_yr,
#   cluster4_tag,
#   cluster8_tag,
#   cluster4_centroid_dist,
#   cluster8_centroid_dist
# )]
# 
# # ensure both are data.tables
# setDT(cooling_center_data_buffercovar)
# setDT(cooling_center_cluster)
# 
# # left join by "id"
# clean_cooling_centers_covar <- merge(
#   cooling_center_data_buffercovar,
#   cooling_center_cluster,
#   by = "id",
#   all.x = TRUE
# )
# 
# fwrite(clean_cooling_centers_covar, "../../../../data/validate_data/analysis/clean_cooling_centers_covar.csv")
# 
# ########################################
# # Step 2: Clean Validation Data ----
# ########################################
# 
# ## Step 2.1: Cellphone data ----
# # file paths
# cellphonefiles <- c(
#   "../../../../data/validate_data/raw/cellphone_pid_data/cooling_center_visitation_2020July.csv",
#   "../../../../data/validate_data/raw/cellphone_pid_data/cooling_center_visitation_2021July.csv"
# )
# 
# # read them separately
# cellphone_visitation_2020 <- fread(cellphonefiles[1])
# cellphone_visitation_2021 <- fread(cellphonefiles[2])
# 
# # append cellphone visitation data
# cellphone_visitation <- rbindlist(
#   list(cellphone_visitation_2020, cellphone_visitation_2021),
#   use.names = TRUE,
#   fill = TRUE
# )
# 
# setnames(cellphone_visitation,
#          old = c("Date", "Visitation"),
#          new = c("date", "visits"))
# 
# #-----------#
# ## Step 2.2: library data ----
# 
# library_visitation_2024 <- fread("../../../../data/validate_data/intermediate/validate_cooling_summer_2024_panel.csv")
# 
# # clean name and colnames
# library_map <- c(
#   "arvonne_fraser_library"      = "Arvonne Fraser Library",
#   "augsburg_park_library"       = "Augsburg Park Library",
#   "brookdale_library"           = "Brookdale Library",
#   "brooklyn_park_library"       = "Brooklyn Park Library",
#   "champlin_library"            = "Champlin Library",
#   "east_lake_library"           = "East Lake Library",
#   "eden_prairie_library"        = "Eden Prairie Library",
#   "edina_library"               = "Edina Library",
#   "elm_creek"                   = "Elm Creek Park Reserve",
#   "excelsior_library"           = "Excelsior Library",
#   "franklin_library"            = "Franklin Library",
#   "golden_valley_library"       = "Golden Valley Library",
#   "hopkins_library"             = "Hopkins Library",
#   "hosmer_library"              = "Hosmer Library",
#   "lake_minnetonka"             = "Excelsior Commons Beach",
#   "linden_hills_library"        = "Linden Hills Library",
#   "long_lake_library"           = "Long Lake Library",
#   "maple_grove_library"         = "Maple Grove Library",
#   "maple_plain_library"         = "Maple Plain Library",
#   "minneapolis_central_library" = "Minneapolis Central Library",
#   "minnetonka_library"          = "Minnetonka Library",
#   "nokomis_library"             = "Nokomis Library",
#   "north_regional_library"      = "North Regional Library",
#   "northeast_library"           = "Northeast Library",
#   "osseo_library"               = "Osseo Library",
#   "oxboro_library"              = "Oxboro Library",
#   "penn_lake_library"           = "Penn Lake Library",
#   "plymouth_library"            = "Plymouth Community Library",
#   "ridgedale_library"           = "Ridgedale Library",
#   "rockford_road_library"       = "Rockford Road Library",
#   "rogers_library"              = "Rogers Library",
#   "roosevelt_library"           = "Roosevelt Library",
#   "southdale_library"           = "Southdale Library",
#   "st_anthony_library"          = "St. Anthony Library",
#   "st_bonifacius_library"       = "St. Bonifacius Library",
#   "st_louis_park_library"       = "St. Louis Park Library",
#   "walker_library"              = "Walker Library",
#   "washburn_library"            = "Washburn Library",
#   "wayzata_library"             = "Wayzata Library",
#   "webber_park_library"         = "Webber Park Library",
#   "westonka_library"            = "Westonka Library"
# )
# 
# 
# setDT(library_visitation_2024)
# setDT(clean_cooling_centers_covar)
# 
# # 1) Map snake_case -> cleaned 'name'
# library_visitation_2024[, name := library_map[location_name]]
# 
# # 2) Build a robust normalization function for joining
# norm_key <- function(x) {
#   x <- iconv(x, to = "ASCII//TRANSLIT")      # remove accents/odd chars
#   x <- tolower(x)
#   x <- gsub("&", " and ", x, fixed = TRUE)
#   x <- gsub("\\bsaint\\b", "st", x, perl = TRUE)
#   x <- gsub("\\bst\\.?\\b", "st", x, perl = TRUE)
#   x <- gsub("[^a-z0-9]+", " ", x)             # drop punctuation to spaces
#   x <- gsub("\\s+", " ", x)
#   trimws(x)
# }
# 
# # 3) Create normalized join keys on BOTH tables
# library_visitation_2024[, name_key := norm_key(name)]
# lookup <- unique(clean_cooling_centers_covar[, .(name = trimws(name), id)])
# lookup[, name_key := norm_key(name)]
# 
# # 4) Merge on the normalized key
# library_visitation_2024_id <- merge(
#   library_visitation_2024,
#   lookup[, .(name_key, id)],
#   by = "name_key",
#   all.x = TRUE
# )
# 
# # 5) QA: coverage + any that still failed
# cat("Rows with matched id: ",
#     sum(!is.na(library_visitation_2024_id$id)), " / ",
#     nrow(library_visitation_2024_id), "\n", sep = "")
# 
# still_no_id <- unique(library_visitation_2024_id[is.na(id), name])
# if (length(still_no_id)) {
#   message("Names with no id after normalized merge: ",
#           paste(still_no_id, collapse = " | "))
# }
# 
# # (Optional) keep tidy columns
# library_visitation_2024_id[, name_key := NULL]
# 
# library_visitation_2024_id[, location_name := NULL]
# 
# #-----------#
# ## Step 2.3 ED Visitation Data ----
# 
# # File paths
# edfiles <- c(
#   "../../../../data/validate_data/raw/ED/ed_encounters_2023_0501_0930.csv",
#   "../../../../data/validate_data/raw/ED/ed_encounters_2024_0501_0930.csv"
# )
# 
# # Read separately
# ed_encounters_2023 <- fread(edfiles[1])
# ed_encounters_2024 <- fread(edfiles[2])
# 
# # Add a year tag (optional but useful for QA)
# ed_encounters_2023[, year := 2023]
# ed_encounters_2024[, year := 2024]
# 
# # Combine
# ed_encounters <- rbindlist(list(ed_encounters_2023, ed_encounters_2024), use.names = TRUE, fill = TRUE)
# 
# # Convert date from m/d/yyyy to Date format
# ed_encounters[, date := as.IDate(date, format = "%m/%d/%Y")]
# 
# #-----------#
# ## Step 2.4 Merge all data: Cellphone, Library (include elm creek and lake), and ED----
# 
# head(ed_encounters)
# head(library_visitation_2024_id)
# head(cellphone_visitation)
# 
# 
# # rename visit columns
# setnames(library_visitation_2024_id, "visits", "lib_visits")
# setnames(cellphone_visitation,       "visits", "cellphone_visits")
# 
# # drop unnecessary column
# cellphone_visitation[, address := NULL]
# 
# # keep only needed cols from cellphone to avoid duplicate 'name'
# cellphone_visitation_min <- cellphone_visitation[, .(id, date, cellphone_visits)]
# 
# # merge by id + date (keeps rows from both; change to all.x=TRUE for left join)
# cellphone_lib_merged <- merge(
#   library_visitation_2024_id,
#   cellphone_visitation_min,
#   by = c("id", "date"),
#   all = TRUE
# )
# 
# cellphone_lib_merged[, name := NULL]
# ed_encounters[, year := NULL]
# 
# # merge on date
# ed_cellphone_lib_merged <- merge(
#   cellphone_lib_merged,
#   ed_encounters,
#   by = "date",
#   all = TRUE
# )
# 
# # Reorder columns: id, date, everything else
# setcolorder(ed_cellphone_lib_merged, c("id", "date", setdiff(names(ed_cellphone_lib_merged), c("id", "date"))))
# 
# # Sort by id, then date
# setorder(ed_cellphone_lib_merged, id, date)
# 
# 
# #################################################################
# # Step 2.5: Create Final Panel with a Sequential Join Strategy ----
# #################################################################
# 
# # 1) Define all unique IDs and Dates to build the master panel
# # (Your original code for this part is correct)
# all_dates <- unique(sort(c(
#   seq(as.IDate("2020-07-01"), as.IDate("2020-07-31"), by = "day"),
#   seq(as.IDate("2021-07-01"), as.IDate("2021-07-31"), by = "day"),
#   seq(as.IDate("2023-05-01"), as.IDate("2023-09-30"), by = "day"),
#   seq(as.IDate("2024-05-01"), as.IDate("2024-09-30"), by = "day")
# )))
# ids <- sort(unique(clean_cooling_centers_covar$id))
# 
# # 2) Create the full master panel: a grid of every ID for every Date
# panel <- CJ(id = ids, date = all_dates, unique = TRUE)
# 
# # 3) Prepare the event data tables for joining
# # (These should have been created in your earlier steps)
# cellphone_lib_merged <- cellphone_lib_merged[, .(id, date, lib_visits, cellphone_visits)]
# ed_encounters[, year := NULL] # Drop extra column
# 
# # 4) --- THE CORRECTED MERGE SEQUENCE ---
# # Start with the full panel and left-join each dataset onto it.
# 
# # A) Join the cooling center covariates (matches on "id")
# validate_panel <- merge(
#   panel,
#   clean_cooling_centers_covar,
#   by = "id",
#   all.x = TRUE
# )
# 
# # B) Join the library and cellphone data (matches on "id" AND "date")
# validate_panel <- merge(
#   validate_panel,
#   cellphone_lib_merged,
#   by = c("id", "date"),
#   all.x = TRUE
# )
# 
# # C) Join the ED encounter data (matches only on "date")
# # This will correctly "broadcast" the daily ED value to every 'id' row for that day.
# validate_panel <- merge(
#   validate_panel,
#   ed_encounters,
#   by = "date",
#   all.x = TRUE
# )
# 
# # 5) Final sorting and cleanup
# setorder(validate_panel, id, date)
# 
# # --- VERIFICATION ---
# # Check the row count: should equal nrow(panel)
# cat("Panel Rows:", nrow(panel), " | Final Rows:", nrow(validate_panel), "\n")
# 
# # Check that the last date now contains data
# print(tail(validate_panel[, .(id, date, ed_encounters)]))
# 
# fwrite(validate_panel, "../../../../data/validate_data/analysis/validate_panel.csv")
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# # #------------#
# # ## Step 2.5: Merge with the cooling center data ----
# # #------------#
# # setDT(clean_cooling_centers_covar)
# #
# # # 1) Build the date vector (IDate)
# # all_dates <- c(
# #   seq(as.IDate("2020-07-01"), as.IDate("2020-07-31"), by = "day"),
# #   seq(as.IDate("2021-07-01"), as.IDate("2021-07-31"), by = "day"),
# #   seq(as.IDate("2023-05-01"), as.IDate("2023-09-30"), by = "day"),
# #   seq(as.IDate("2024-05-01"), as.IDate("2024-09-30"), by = "day")
# # )
# # all_dates <- unique(sort(all_dates))  # safety
# #
# # # 2) Get IDs
# # ids <- sort(unique(clean_cooling_centers_covar$id))
# #
# # # 3) Full panel: Cartesian join of ids × dates
# # panel <- CJ(id = ids, date = all_dates, unique = TRUE)
# #
# # # 4) Broadcast covariates from clean_cooling_centers_covar to every date
# # #    (left table first keeps covariate column order; we’ll reorder at end)
# # panel <- clean_cooling_centers_covar[panel, on = "id"]
# #
# # # 5) Put id, date first
# # setcolorder(panel, c("id", "date", setdiff(names(panel), c("id", "date"))))
# #
# # # 6) Quick checks
# # cat("IDs:", length(ids), " | Dates:", length(all_dates),
# #     " | Rows:", nrow(panel), "\n")
# #
# #
# # # Merge by id, date
# # ed_cellphone_lib_with_covar <- merge(
# #   panel,
# #   ed_cellphone_lib_merged,
# #   by = c("id", "date"),
# #   all.x = TRUE
# # )
# #
# # # Optional: sort by id, then date
# # setcolorder(ed_cellphone_lib_with_covar, c("id", "date", setdiff(names(ed_encounters), c("id", "date"))))
# # #setorder(ed_cellphone_lib_with_covar, id, date, )
# #
# # fwrite(ed_cellphone_lib_with_covar, "../../../../data/validate_data/analysis/ed_cellphone_lib_with_covar.csv")
# #
# #
# #
# #
# # head(ed_cellphone_lib_with_covar)
# # head(panel)
# #
# # # 0) Make sure both use IDate
# # panel[, date := as.IDate(date)]
# # ed_cellphone_lib_with_covar[, date := as.IDate(date)]
# #
# # # 1) (Optional but recommended) ensure ED data is unique on (id,date).
# # #    If you *know* it's unique already, you can skip this. Otherwise, either
# # #    dedupe or aggregate — here I just keep the first occurrence.
# # ed_uni <- unique(ed_cellphone_lib_with_covar, by = c("id","date"))
# #
# # # If you need an aggregation instead, replace the line above with something like:
# # # ed_uni <- ed_cellphone_lib_with_covar[
# # #   , .(
# # #       lib_visits = sum(lib_visits, na.rm=TRUE),
# # #       cellphone_visits = sum(cellphone_visits, na.rm=TRUE),
# # #       ed_encounters = sum(ed_encounters, na.rm=TRUE)
# # #       # keep one set of covariates (e.g., by = first) if they’re identical
# # #     ),
# # #   by = .(id, date)
# # # ]
# #
# # # 2) Left join: keep all rows from panel; unmatched become NA
# # #    In data.table, X[i, on=...] keeps rows of 'i'. So use ED as X, panel as i.
# # validate_panel <- ed_uni[panel, on = .(id, date)]
# #
# # # 3) Quick checks
# # nrow(panel)              # reference count
# # nrow(validate_panel)     # should match panel exactly
# # validate_panel[is.na(lib_visits) & is.na(cellphone_visits) & is.na(ed_encounters), .N]  # how many unmatched
# #
# # # 4) (Optional) sanity: verify keys and uniqueness
# # uniqueN(panel, by = c("id","date"))
# # uniqueN(validate_panel, by = c("id","date"))
# 
# 
# 
# ########################################
# # Step 3: Merge all Simulation Data ----
# ########################################
# 
# ## Step 3.1 Whole County all dates sim visitation information ----
# 
# msi_runs_alldates <- fread("../../../../output/results/geometric_model_1000runs/combined_summary_all_years.csv")
# 
# 
# setDT(msi_runs_alldates)
# 
# # 1) Convert date from int YYYYMMDD to Date
# msi_runs_alldates[, date := as.IDate(as.character(date), format = "%Y%m%d")]
# 
# # 2) Drop 'year' column
# msi_runs_alldates[, year := NULL]
# 
# # 3) Add "_allcounty" to specified columns
# vars_to_rename <- c(
#   "total_parcels", "stayed_home", "moved",
#   "stayed_home_pct", "moved_pct",
#   "avg_probability", "avg_stability", "avg_temperature",
#   "ac_data_source", "ac_external_pct"
# )
# 
# setnames(msi_runs_alldates,
#          old = vars_to_rename,
#          new = paste0(vars_to_rename, "_allcounty"))
# 
# 
# ## Step 3.2 each cooling option all dates sim visitation information ----
# 
# sim_cooling_visits <- fread(
#   "../../../../output/results/geometric_model_1000runs/sim_cooling_visits_geometric_abm.csv"
# )
# 
# # Ensure both are data.tables
# setDT(msi_runs_alldates)
# setDT(sim_cooling_visits)
# 
# # 1) Convert sim_cooling_visits$date from int YYYYMMDD to IDate
# sim_cooling_visits[, date := as.IDate(as.character(date), format = "%Y%m%d")]
# 
# # 2) Merge by date
# sim_individual_and_allcounty <- merge(
#   sim_cooling_visits,
#   msi_runs_alldates,
#   by = "date",
#   all.x = TRUE
# )
# 
# # 3) Optional: order by name, then date
# setorder(sim_individual_and_allcounty, name, date)
# 
# 
# 
# # Packages
# library(data.table)
# library(stringdist)   # for amatch/stringdist
# # If you prefer fuzzyjoin instead of amatch, you can: library(fuzzyjoin)
# 
# # 0) Start from your objects
# # sim_cooling_visits and panel already exist with a column `name`
# # 1) Build the name universe from cooling center lookup (has id-name mapping)
# dt_panel <- unique(clean_cooling_centers_covar[, .(panel_name = name)])
# panel_lookup <- unique(clean_cooling_centers_covar[, .(panel_name = name, id)])
# 
# # 2) Sim name universe
# dt_sim <- unique(sim_cooling_visits[, .(sim_name = name)])
# 
# # 1) Build normalization helpers *inline* (no functions), produce join keys
# #    - lower case
# #    - trim
# #    - unify dashes & punctuation
# #    - remove apostrophes and "&"
# #    - drop content in parentheses (we'll also keep a version with parentheses for backup)
# #    - standardize common tokens (e.g., "st." -> "saint", "ctr" -> "center")
# #    - collapse multiple spaces
# norm_chars <- function(x) {
#   x <- tolower(x)
#   x <- gsub("–|—", "-", x)                           # unify dashes
#   x <- gsub("&", " and ", x)
#   x <- gsub("'", "", x)
#   x <- gsub("[[:punct:]]", " ", x)                   # remove punctuation to be safe
#   x <- gsub("\\s+", " ", x)
#   trimws(x)
# }
# 
# # We'll keep two keys: with and without parentheses content
# dt_sim[,  sim_key_full := norm_chars(sim_name)]
# dt_panel[,panel_key_full := norm_chars(panel_name)]
# 
# dt_sim[,  sim_key_noparen := gsub("\\s*\\(.*?\\)", "", sim_key_full)]
# dt_panel[,panel_key_noparen := gsub("\\s*\\(.*?\\)", "", panel_key_full)]
# 
# # Optional: standardize a few common terms
# std_repls <- data.table(
#   from = c("\\bctr\\b", "\\bcntr\\b", "\\brec\\b", "\\bst\\.?\\b"),
#   to   = c("center",    "center",     "recreation", "saint")
# )
# for (i in seq_len(nrow(std_repls))) {
#   dt_sim[,  sim_key_full     := gsub(std_repls$from[i], std_repls$to[i], sim_key_full)]
#   dt_panel[,panel_key_full   := gsub(std_repls$from[i], std_repls$to[i], panel_key_full)]
#   dt_sim[,  sim_key_noparen  := gsub(std_repls$from[i], std_repls$to[i], sim_key_noparen)]
#   dt_panel[,panel_key_noparen:= gsub(std_repls$from[i], std_repls$to[i], panel_key_noparen)]
# }
# 
# # 2) Exact matches (first on full key, then on no-paren key)
# # 2a) Exact on full
# exact_full <- merge(
#   dt_sim[, .(sim_name, sim_key_full)],
#   dt_panel[, .(panel_name, panel_key_full)],
#   by.x = "sim_key_full", by.y = "panel_key_full", all.x = TRUE
# )
# 
# # 2b) For any still-unmatched, try exact on no-paren
# unmatched <- exact_full[
#   is.na(panel_name),
#   .(sim_name, sim_key_noparen = norm_chars(gsub("\\s*\\(.*?\\)", "", sim_name)))
# ]
# 
# exact_noparen <- merge(
#   unmatched,
#   unique(dt_panel[, .(panel_name, panel_key_noparen)]),
#   by.x = "sim_key_noparen",
#   by.y = "panel_key_noparen",
#   all.x = TRUE
# )
# 
# # Stitch back: prefer exact_full if matched; else use exact_noparen
# exact_joined <- merge(
#   exact_full[, .(sim_name, panel_name_exact = panel_name)],
#   exact_noparen[, .(sim_name, panel_name_exact_noparen = panel_name)],
#   by = "sim_name", all.x = TRUE
# )
# 
# exact_joined[, panel_match :=
#                fifelse(!is.na(panel_name_exact), panel_name_exact,
#                        fifelse(!is.na(panel_name_exact_noparen), panel_name_exact_noparen, NA_character_))
# ]
# 
# # 3) Fuzzy suggestions for still-unmatched using amatch (OSA distance)
# still_unmatched <- merge(
#   dt_sim[, .(sim_name, sim_key_full, sim_key_noparen)],
#   exact_joined[, .(sim_name, panel_match)],
#   by = "sim_name", all.x = TRUE
# )[is.na(panel_match)]
# 
# # Build vector of candidate keys from panel (use both forms for more chances)
# panel_keys <- unique(c(dt_panel$panel_key_full, dt_panel$panel_key_noparen))
# panel_lookup <- unique(
#   rbindlist(list(
#     dt_panel[, .(panel_key = panel_key_full, panel_name)],
#     dt_panel[, .(panel_key = panel_key_noparen, panel_name)]
#   ))
# )
# 
# # Try to match by the more forgiving no-paren key first
# still_unmatched[, idx := amatch(sim_key_noparen, panel_keys, method = "osa", maxDist = 6)]
# still_unmatched[, panel_key_suggest := ifelse(is.na(idx), NA_character_, panel_keys[idx])]
# still_unmatched[, dist := ifelse(is.na(idx), NA_integer_,
#                                  stringdist(sim_key_noparen, panel_key_suggest, method = "osa"))]
# 
# # Attach suggested panel_name
# still_unmatched <- merge(
#   still_unmatched[, .(sim_name, sim_key_full, sim_key_noparen, panel_key_suggest, dist)],
#   panel_lookup,
#   by.x = "panel_key_suggest", by.y = "panel_key", all.x = TRUE
# )[order(dist)]
# 
# # 4) Seed a manual override table for the obvious tricky ones
# #    Add rows as you confirm them.
# manual_overrides <- data.table(
#   sim_name = c(
#     "MN Valley National Wildlife Refuge—Bloomington Vis",
#     "Wabun (Minnehaha Park) Wading Pool",
#     "NorthPoint Health & Wellness Center (formerly Work"
#   ),
#   panel_name = c(
#     "MN Valley National Wildlife Refuge—Bloomington Visitor Center",
#     "Wabun Wading Pool (at Minnehaha Regional Park)",
#     "NorthPoint Health & Wellness Center (formerly Workforce Center)"
#   )
# )
# 
# # 4) Attach id via the canonical lookup
# map_to_id <- merge(
#   final_map[, .(sim_name, panel_name_final)],
#   panel_lookup,                            # (panel_name, id)
#   by.x = "panel_name_final",
#   by.y = "panel_name",
#   all.x = TRUE
# )
# 
# # 5) Add id to the sim rows (so we can merge on id+date)
# sim_individual_and_allcounty <- merge(
#   sim_individual_and_allcounty,
#   map_to_id[, .(name = sim_name, id)],
#   by = "name",
#   all.x = TRUE
# )
# 
# # 6) Merge sim metrics onto validate_panel by id & date (keep all panel rows)
# validate_panel <- merge(
#   validate_panel,
#   sim_individual_and_allcounty[, .(
#     id, date, simulate_parcel_visits,
#     stayed_home_allcounty, moved_allcounty,
#     stayed_home_pct_allcounty, moved_pct_allcounty,
#     avg_probability_allcounty, avg_stability_allcounty,
#     avg_temperature_allcounty
#   )],
#   by = c("id","date"),
#   all.x = TRUE
# )
# 
# # 7) Zero-fill missing sim visits; leave other sim fields NA unless you want otherwise
# validate_panel[is.na(simulate_parcel_visits), simulate_parcel_visits := 0L]
# 
# # 8) Sanity checks
# uniqueN(validate_panel$id)        # expect your # of centers
# uniqueN(validate_panel$date)      # expect total dates (e.g., 368)
# nrow(validate_panel)              # expect 90528
# 
# 
# # 5) Build the final mapping:
# #    Priority: manual_overrides > exact matches > fuzzy suggestions (within a distance threshold, e.g., <= 2–3 is very safe; 4–6 needs review)
# final_map <- unique(dt_sim[, .(sim_name)])
# 
# # join manual
# final_map <- merge(final_map, manual_overrides, by = "sim_name", all.x = TRUE)
# 
# # join exact
# final_map <- merge(final_map,
#                    exact_joined[, .(sim_name, panel_match)],
#                    by = "sim_name", all.x = TRUE)
# 
# # join fuzzy suggestion
# still_unmatched_simple <- still_unmatched[, .(sim_name, panel_name_suggest = panel_name, dist)]
# final_map <- merge(final_map, still_unmatched_simple, by = "sim_name", all.x = TRUE)
# 
# # choose panel_name_final
# final_map[, panel_name_final :=
#             fifelse(!is.na(panel_name), panel_name,        # manual override
#                     fifelse(!is.na(panel_match), panel_match,      # exact
#                             fifelse(!is.na(panel_name_suggest) & dist <= 3, panel_name_suggest, NA_character_))) # only auto-accept good fuzzy matches
# ]
# 
# # # 6) Export two artifacts:
# # # - A reviewer file listing any unresolved or fuzzy matches to hand-edit
# # # - The final accepted mapping to use in code
# # fwrite(final_map[is.na(panel_name_final) | (!is.na(panel_name_suggest) & is.na(panel_match) & is.na(panel_name))],
# #        "mapping_candidates_review.csv")
# #
# # fwrite(final_map[, .(sim_name, panel_name_final)], "mapping_final.csv")
# 
# # 7) Example: join mapping back to your sim data
# sim_with_panel_name <- merge(
#   sim_cooling_visits,
#   final_map[, .(name = sim_name, panel_name = panel_name_final)],
#   by = "name", all.x = TRUE
# )
# 
# # Quick QA: which sim names still lack a mapping?
# sim_with_panel_name[is.na(panel_name), unique(name)]
# 
# 
# 
# 
# 
# # 1) Ensure consistent date class
# sim_individual_and_allcounty[, date := as.IDate(date)]
# panel[, date := as.IDate(date)]
# 
# # 2) Attach panel_name to simulation rows (via your mapping)
# #    (panel_name is how sim rows will match to panel$name)
# map_dt <- as.data.table(final_map)[, .(name = sim_name, panel_name = panel_name_final)]
# 
# sim_individual_and_allcounty <- merge(
#   sim_individual_and_allcounty,
#   map_dt,
#   by = "name",
#   all.x = TRUE
# )
# 
# # Optional QA: which sim names didn’t get a panel_name?
# sim_individual_and_allcounty[is.na(panel_name), unique(name)]
# 
# # 3) Build the “full” (name, date) grid from panel (this defines the 90,528 target rows)
# panel_grid <- unique(panel[, .(name, date)])   # should be 246 * 368
# 
# # 4) Bring sim data onto the full grid:
# #    - Join by panel_grid$name == sim.panel_name AND same date
# #    - Keep all panel_grid rows
# #    - After merge, set missing simulate_parcel_visits to 0
# sim_on_panel <- merge(
#   panel_grid,
#   sim_individual_and_allcounty[, .(panel_name, date, simulate_parcel_visits,
#                                    stayed_home_allcounty, moved_allcounty,
#                                    stayed_home_pct_allcounty, moved_pct_allcounty,
#                                    avg_probability_allcounty, avg_stability_allcounty,
#                                    avg_temperature_allcounty)],
#   by.x = c("name", "date"),
#   by.y = c("panel_name", "date"),
#   all.x = TRUE
# )
# 
# # 5) Fill simulate_parcel_visits with 0 when missing (meaning: no simulated visitation that day)
# sim_on_panel[is.na(simulate_parcel_visits), simulate_parcel_visits := 0L]
# 
# # (Leave the other sim_* / allcounty columns as NA unless you explicitly want 0s there too.)
# 
# # 6) If you want to attach the rest of the panel columns now (covariates, etc.)
# #    just merge back onto the full panel table:
# final_sim_panel <- merge(
#   panel,                 # contains the full rows/cols you want to keep
#   sim_on_panel,          # brings simulate_parcel_visits (and any sim all-county vars)
#   by = c("name", "date"),
#   all.x = TRUE
# )
# 
# # # 7) Quick checks
# # uniqueN(final_sim_panel$name)          # expected 246
# # uniqueN(final_sim_panel$date)          # expected 368
# # nrow(final_sim_panel)                  # expected 90528
# 
# # Check if the duplicates are truly identical across all columns
# sim_on_panel[duplicated(sim_on_panel[, .(name, date)]) &
#                !duplicated(sim_on_panel)]  # This should be empty if they are identical
# 
# # Drop exact duplicates (keeps the first occurrence)
# sim_on_panel <- unique(sim_on_panel, by = c("name", "date"))
# 
# # Merge back with panel
# final_sim_panel <- merge(
#   panel,
#   sim_on_panel,
#   by = c("name", "date"),
#   all.x = TRUE
# )
# 
# # Fill missing visits with 0
# final_sim_panel[is.na(simulate_parcel_visits), simulate_parcel_visits := 0L]
# 
# # Sanity checks
# uniqueN(final_sim_panel$name)  # should be 246
# uniqueN(final_sim_panel$date)  # should be 368
# nrow(final_sim_panel)          # should be 90528
# #
# # # 8) Optional: sanity check missing name/date combos in sim
# # #    (these are the ones we just zero-filled)
# # missing_in_sim <- sim_on_panel[simulate_parcel_visits == 0L, .N]
# # missing_in_sim
# #
# # # Ensure same date class
# # sim_individual_and_allcounty[, date := as.IDate(date)]
# # panel[, date := as.IDate(date)]
# #
# # dt_sim_pairs   <- unique(sim_individual_and_allcounty[!is.na(panel_name), .(name = panel_name, date)])
# # dt_panel_pairs <- unique(panel[, .(name, date)])
# #
# # extra_in_sim <- fsetdiff(dt_sim_pairs, dt_panel_pairs)
# # n_extra <- nrow(extra_in_sim)
# # n_extra
# 
# ################################################################################
# 
# # Step 4: Merge Final Sim Panel with the final Real Panel
# 
# head(final_sim_panel)
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# library(data.table)
# 
# # Ensure as data.tables
# setDT(panel)                    # has id, date, name, covariates...
# setDT(sim_individual_and_allcounty)
# 
# # 1) Fix/standardize date in sim (if not already IDate)
# if (!inherits(sim_individual_and_allcounty$date, "IDate")) {
#   sim_individual_and_allcounty[, date := as.IDate(as.character(date), format = "%Y%m%d")]
# }
# 
# # 2) Clean names (trim)
# panel[, name := trimws(name)]
# sim_individual_and_allcounty[, name := trimws(name)]
# 
# # 3) Aggregate sim in case of duplicates per name-date
# sim_agg <- sim_individual_and_allcounty[
#   , .(simulate_parcel_visits = sum(simulate_parcel_visits, na.rm = TRUE)),
#   by = .(name, date)
# ]
# 
# # 4) Merge onto panel by name + date (panel is the universe)
# panel_sim <- merge(
#   panel,
#   sim_agg,
#   by = c("name", "date"),
#   all.x = TRUE
# )
# 
# # 5) Fill missing sim visits (no sim record means 0)
# panel_sim[is.na(simulate_parcel_visits), simulate_parcel_visits := 0L]
# 
# # 6) Report sim rows that aren't in panel
# orphans <- fsetdiff(sim_agg[, .(name, date)], unique(panel[, .(name, date)]))
# if (nrow(orphans)) {
#   message("Sim rows not found in panel: ", nrow(orphans),
#           " (examples: ",
#           paste(utils::head(orphans$name, 5), collapse = " | "),
#           ")")
# }
# 
# # Optional: order nicely
# setorder(panel_sim, name, date)
# 
# # Preview
# head(panel_sim)
# 
# 
# 
# 
# 
# 
# 
