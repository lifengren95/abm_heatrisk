# # Load required libraries
# library(data.table)
# library(readxl)
# library(lubridate)
# library(stringr)
# 
# # Define file paths
# base_path <- "./data/validate_data/raw"
# intermediate_path <- "./data/validate_data/intermediate"
# 
# # Read the existing summer recreation data
# summer_recreation_file <- file.path(intermediate_path, "summer_2024_combined_recreation_data.csv")
# summer_dt <- fread(summer_recreation_file)
# summer_dt[, date := as.Date(date)]
# 
# # Read library visits data
# lib_visits_file <- file.path(base_path, "lib_visits.xlsx")
# lib_visits_dt <- as.data.table(read_excel(lib_visits_file))
# 
# # Clean column names for library data
# setnames(lib_visits_dt, c("location_name", "record_date", "visits"))
# 
# # Convert date column
# lib_visits_dt[, date := as.Date(record_date)]
# 
# # Filter library data for summer period (June 1 - August 31, 2024)
# start_date <- as.Date("2024-06-01")
# end_date <- as.Date("2024-08-31")
# lib_visits_dt <- lib_visits_dt[date >= start_date & date <= end_date]
# 
# # Clean location names for column naming (remove spaces, convert to lowercase, add _visits)
# lib_visits_dt[, clean_location := tolower(gsub("[^A-Za-z0-9]", "_", location_name))]
# lib_visits_dt[, clean_location := gsub("_+", "_", clean_location)] # Remove multiple underscores
# lib_visits_dt[, clean_location := gsub("^_|_$", "", clean_location)] # Remove leading/trailing underscores
# lib_visits_dt[, column_name := paste0(clean_location, "_visits")]
# 
# cat("Unique library locations found:\n")
# print(unique(lib_visits_dt[, .(location_name, column_name)]))
# 
# # Reshape library data to wide format
# lib_wide_dt <- dcast(lib_visits_dt, date ~ column_name, value.var = "visits", fill = NA)
# 
# # Merge recreation data with library data
# merged_dt <- merge(summer_dt, lib_wide_dt, by = "date", all.x = TRUE)
# 
# # Display summary of merged data
# cat("\nMerged data summary:\n")
# cat("Date range:", as.character(min(merged_dt$date)), "to", as.character(max(merged_dt$date)), "\n")
# cat("Total records:", nrow(merged_dt), "\n")
# cat("Total columns:", ncol(merged_dt), "\n")
# 
# # Save the merged dataset
# merged_output_file <- file.path(intermediate_path, "validate_cooling_summer_2024.csv")
# fwrite(merged_dt, merged_output_file)
# cat("Merged data saved to:", merged_output_file, "\n")
# 
# # ===== CREATE PANEL DATA FORMAT =====
# 
# # Prepare recreation location data
# recreation_panel <- rbindlist(list(
#   # Elm Creek (combine swim + vehicle)
#   summer_dt[, .(
#     location_name = "elm_creek",
#     date = date,
#     visits = ifelse(is.na(elm_creek_swim_pass) & is.na(elm_creek_vehicle_count), NA,
#                     ifelse(is.na(elm_creek_swim_pass), elm_creek_vehicle_count,
#                            ifelse(is.na(elm_creek_vehicle_count), elm_creek_swim_pass,
#                                   elm_creek_swim_pass + elm_creek_vehicle_count)))
#   )],
#   
#   # Lake Minnetonka
#   summer_dt[, .(
#     location_name = "lake_minnetonka",
#     date = date,
#     visits = lake_minnetonka_swim_pass
#   )]
# ))
# 
# # Prepare library panel data
# library_panel <- lib_visits_dt[, .(
#   location_name = clean_location,
#   date = date,
#   visits = visits
# )]
# 
# # Combine recreation and library panel data
# panel_dt <- rbindlist(list(recreation_panel, library_panel))
# 
# # Sort by location and date
# setorder(panel_dt, location_name, date)
# 
# # Display panel data summary
# cat("\n=== PANEL DATA SUMMARY ===\n")
# cat("Total records:", nrow(panel_dt), "\n")
# cat("Unique locations:", length(unique(panel_dt$location_name)), "\n")
# cat("Date range:", as.character(min(panel_dt$date)), "to", as.character(max(panel_dt$date)), "\n")
# 
# # Show sample of panel data
# cat("\nSample of panel data (first 20 rows):\n")
# print(panel_dt[1:20])
# 
# cat("\nLocations included:\n")
# location_summary <- panel_dt[, .(
#   total_records = .N,
#   non_na_visits = sum(!is.na(visits)),
#   mean_visits = round(mean(visits, na.rm = TRUE), 2),
#   max_visits = max(visits, na.rm = TRUE)
# ), by = location_name]
# print(location_summary)
# 
# # Save panel data
# panel_output_file <- file.path(intermediate_path, "validate_cooling_summer_2024_panel.csv")
# fwrite(panel_dt, panel_output_file)
# cat("\nPanel data saved to:", panel_output_file, "\n")
# 
# # Show first few rows of merged data for verification
# cat("\n=== MERGED DATA PREVIEW ===\n")
# cat("First 5 rows of merged data:\n")
# print(merged_dt[1:5])
# 
# cat("\nColumn names in merged data:\n")
# print(names(merged_dt))











# Load required libraries
library(data.table)
library(readxl)
library(lubridate)
library(stringr)

# Define file paths
base_path <- "./data/validate_data/raw"
intermediate_path <- "./data/validate_data/intermediate"

# Read the existing summer recreation data
summer_recreation_file <- file.path(intermediate_path, "summer_2024_combined_recreation_data.csv")
summer_dt <- fread(summer_recreation_file)
summer_dt[, date := as.Date(date)]

# ===== FILTER OUT SUNDAYS AND HOLIDAYS =====
# Define dates to exclude
holiday_dates <- as.Date(c("2024-06-19", "2024-07-04"))  # Juneteenth and Independence Day

# Identify Sundays in summer recreation data
summer_dt[, is_sunday := weekdays(date) == "Sunday"]
sunday_dates <- unique(summer_dt[is_sunday == TRUE, date])

# Combine excluded dates
excluded_dates <- c(holiday_dates, sunday_dates)
excluded_dates <- unique(excluded_dates)

cat("=== FILTERING OUT PROBLEMATIC DATES ===\n")
cat("Holiday dates excluded:", paste(as.character(holiday_dates), collapse = ", "), "\n")
cat("Sunday dates excluded:", paste(as.character(sunday_dates), collapse = ", "), "\n")
cat("Total dates excluded:", length(excluded_dates), "\n")

# Filter recreation data
summer_dt_filtered <- summer_dt[!date %in% excluded_dates]
summer_dt_filtered[, is_sunday := NULL]  # Remove helper column

cat("Recreation data filtered:\n")
cat("Original records:", nrow(summer_dt), "\n")
cat("Filtered records:", nrow(summer_dt_filtered), "\n")
cat("Records removed:", nrow(summer_dt) - nrow(summer_dt_filtered), "\n")

# Read library visits data
lib_visits_file <- file.path(base_path, "lib_visits.xlsx")
lib_visits_dt <- as.data.table(read_excel(lib_visits_file))

# Clean column names for library data
setnames(lib_visits_dt, c("location_name", "record_date", "visits"))

# Convert date column
lib_visits_dt[, date := as.Date(record_date)]

# Filter library data for summer period (June 1 - August 31, 2024) AND exclude problematic dates
start_date <- as.Date("2024-06-01")
end_date <- as.Date("2024-08-31")
lib_visits_dt <- lib_visits_dt[date >= start_date & date <= end_date & !date %in% excluded_dates]

cat("Library data filtered:\n")
cat("Summer period + excluded dates filter applied\n")
cat("Filtered library records:", nrow(lib_visits_dt), "\n")

# Clean location names for column naming (remove spaces, convert to lowercase, add _visits)
lib_visits_dt[, clean_location := tolower(gsub("[^A-Za-z0-9]", "_", location_name))]
lib_visits_dt[, clean_location := gsub("_+", "_", clean_location)] # Remove multiple underscores
lib_visits_dt[, clean_location := gsub("^_|_$", "", clean_location)] # Remove leading/trailing underscores
lib_visits_dt[, column_name := paste0(clean_location, "_visits")]

cat("Unique library locations found:\n")
print(unique(lib_visits_dt[, .(location_name, column_name)]))

# Reshape library data to wide format
lib_wide_dt <- dcast(lib_visits_dt, date ~ column_name, value.var = "visits", fill = NA)

# Merge recreation data with library data (both now filtered)
merged_dt <- merge(summer_dt_filtered, lib_wide_dt, by = "date", all.x = TRUE)

# Display summary of merged data
cat("\n=== MERGED DATA SUMMARY ===\n")
cat("Date range (filtered):", as.character(min(merged_dt$date)), "to", as.character(max(merged_dt$date)), "\n")
cat("Total records:", nrow(merged_dt), "\n")
cat("Total columns:", ncol(merged_dt), "\n")
cat("Sundays and holidays excluded during merge process\n")

# Save the merged dataset (now filtered for Sundays and holidays)
merged_output_file <- file.path(intermediate_path, "validate_cooling_summer_2024.csv")
fwrite(merged_dt, merged_output_file)
cat("Merged data (filtered) saved to:", merged_output_file, "\n")

# ===== CREATE PANEL DATA FORMAT =====

# Prepare recreation location data
recreation_panel <- rbindlist(list(
  # Elm Creek (combine swim + vehicle)
  summer_dt[, .(
    location_name = "elm_creek",
    date = date,
    visits = ifelse(is.na(elm_creek_swim_pass) & is.na(elm_creek_vehicle_count), NA,
                    ifelse(is.na(elm_creek_swim_pass), elm_creek_vehicle_count,
                           ifelse(is.na(elm_creek_vehicle_count), elm_creek_swim_pass,
                                  elm_creek_swim_pass + elm_creek_vehicle_count)))
  )],
  
  # Lake Minnetonka
  summer_dt[, .(
    location_name = "lake_minnetonka",
    date = date,
    visits = lake_minnetonka_swim_pass
  )]
))

# Prepare library panel data
library_panel <- lib_visits_dt[, .(
  location_name = clean_location,
  date = date,
  visits = visits
)]

# Combine recreation and library panel data
panel_dt <- rbindlist(list(recreation_panel, library_panel))

# Sort by location and date
setorder(panel_dt, location_name, date)

# Display panel data summary
cat("\n=== PANEL DATA SUMMARY ===\n")
cat("Total records:", nrow(panel_dt), "\n")
cat("Unique locations:", length(unique(panel_dt$location_name)), "\n")
cat("Date range (filtered):", as.character(min(panel_dt$date)), "to", as.character(max(panel_dt$date)), "\n")
cat("Sundays and holidays excluded during creation\n")

# Show sample of panel data
cat("\nSample of panel data (first 20 rows):\n")
print(panel_dt[1:20])

cat("\nLocations included:\n")
location_summary <- panel_dt[, .(
  total_records = .N,
  non_na_visits = sum(!is.na(visits)),
  mean_visits = round(mean(visits, na.rm = TRUE), 2),
  max_visits = max(visits, na.rm = TRUE)
), by = location_name]
print(location_summary)

# Save panel data (now filtered for Sundays and holidays)
panel_output_file <- file.path(intermediate_path, "validate_cooling_summer_2024_panel.csv")
fwrite(panel_dt, panel_output_file)
cat("Panel data (filtered) saved to:", panel_output_file, "\n")

# Show first few rows of merged data for verification
cat("\n=== MERGED DATA PREVIEW ===\n")
cat("First 5 rows of merged data:\n")
print(merged_dt[1:5])

cat("\nColumn names in merged data:\n")
print(names(merged_dt))

# ===== VERIFICATION =====
cat("\n=== FINAL VERIFICATION ===\n")

# Check that no excluded dates remain in merged data
remaining_holidays_merged <- sum(merged_dt$date %in% holiday_dates)
remaining_sundays_merged <- sum(weekdays(merged_dt$date) == "Sunday")

# Check that no excluded dates remain in panel data
remaining_holidays_panel <- sum(panel_dt$date %in% holiday_dates)
remaining_sundays_panel <- sum(weekdays(panel_dt$date) == "Sunday")

cat("Verification results:\n")
cat("Holidays remaining in merged data:", remaining_holidays_merged, "\n")
cat("Sundays remaining in merged data:", remaining_sundays_merged, "\n")
cat("Holidays remaining in panel data:", remaining_holidays_panel, "\n")
cat("Sundays remaining in panel data:", remaining_sundays_panel, "\n")

if(remaining_holidays_merged == 0 && remaining_sundays_merged == 0 && 
   remaining_holidays_panel == 0 && remaining_sundays_panel == 0) {
  cat("✓ SUCCESS: All holidays and Sundays successfully excluded from both datasets!\n")
} else {
  cat("⚠ WARNING: Some holidays or Sundays may still remain!\n")
}

# Show day of week distribution
cat("\nDay of week distribution in final datasets:\n")
cat("Merged data:\n")
merged_dow <- table(weekdays(merged_dt$date))
print(merged_dow)

cat("\nPanel data (unique dates):\n")
panel_unique_dates <- unique(panel_dt$date)
panel_dow <- table(weekdays(panel_unique_dates))
print(panel_dow)

cat("\nFinal datasets created with Sundays and holidays excluded from the start!\n")