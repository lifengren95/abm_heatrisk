# Load required libraries
library(data.table)
library(readxl)
library(lubridate)

# Define file paths
base_path <- "./data/validate_data/raw"
output_path <- "./data/validate_data/intermediate"

lake_minnetonka_file <- file.path(base_path, "Lake Minnetonka Swimming Day Passes.xlsx")
elm_swim_file <- file.path(base_path, "Elm Creek Swimming Day Passes.xlsx")
elm_vehicle_file <- file.path(base_path, "Elm Creek Vehicle Counter - 2024.xlsx")

# Read the 2024 sheets from each Excel file
lake_minnetonka_dt <- as.data.table(read_excel(lake_minnetonka_file, sheet = "2024"))
elm_swim_dt <- as.data.table(read_excel(elm_swim_file, sheet = "2024"))
elm_vehicle_dt <- as.data.table(read_excel(elm_vehicle_file, sheet = "2024"))

# Standardize column names and convert dates
setnames(lake_minnetonka_dt, c("date", "lake_minnetonka_swim_pass"))
setnames(elm_swim_dt, c("date", "elm_creek_swim_pass"))
setnames(elm_vehicle_dt, c("date", "elm_creek_vehicle_count"))

# Convert date columns to Date type
lake_minnetonka_dt[, date := as.Date(date)]
elm_swim_dt[, date := as.Date(date)]
elm_vehicle_dt[, date := as.Date(date)]

# Filter data for summer 2024 period (June 1 - August 31, 2024)
start_date <- as.Date("2024-06-01")
end_date <- as.Date("2024-08-31")

lake_minnetonka_dt <- lake_minnetonka_dt[date >= start_date & date <= end_date]
elm_swim_dt <- elm_swim_dt[date >= start_date & date <= end_date]
elm_vehicle_dt <- elm_vehicle_dt[date >= start_date & date <= end_date]

# Create a complete date sequence for the summer period
date_seq <- data.table(date = seq(start_date, end_date, by = "day"))

# Merge all datasets using left joins on the complete date sequence
combined_dt <- date_seq
combined_dt <- elm_swim_dt[combined_dt, on = "date"]
combined_dt <- lake_minnetonka_dt[combined_dt, on = "date"]
combined_dt <- elm_vehicle_dt[combined_dt, on = "date"]

# Reorder columns to match the requested format
setcolorder(combined_dt, c("date", "elm_creek_swim_pass", "elm_creek_vehicle_count", "lake_minnetonka_swim_pass"))

# Convert negative values to 0 (keep NA as NA for missing dates)
combined_dt[elm_creek_swim_pass < 0, elm_creek_swim_pass := 0]
combined_dt[elm_creek_vehicle_count < 0, elm_creek_vehicle_count := 0]
combined_dt[lake_minnetonka_swim_pass < 0, lake_minnetonka_swim_pass := 0]

# Print summary information
cat("Data Summary:\n")
cat("Date range:", as.character(min(combined_dt$date)), "to", as.character(max(combined_dt$date)), "\n")
cat("Total records:", nrow(combined_dt), "\n")
cat("Columns:", paste(names(combined_dt), collapse = ", "), "\n\n")

# Show first few rows
cat("First 10 rows:\n")
print(combined_dt[1:10])

# Show last few rows
cat("\nLast 10 rows:\n")
print(combined_dt[(.N-9):.N])

# Create output directory if it doesn't exist
if (!dir.exists(output_path)) {
  dir.create(output_path, recursive = TRUE)
}

# Save the combined dataset
output_file <- file.path(output_path, "summer_2024_combined_recreation_data.csv")
fwrite(combined_dt, output_file)

cat("\nData successfully saved to:", output_file, "\n")

# Display basic statistics
cat("\nBasic Statistics:\n")
print(combined_dt[, .(
  elm_creek_swim_mean = round(mean(elm_creek_swim_pass, na.rm = TRUE), 2),
  elm_creek_swim_max = max(elm_creek_swim_pass, na.rm = TRUE),
  elm_creek_vehicle_mean = round(mean(elm_creek_vehicle_count, na.rm = TRUE), 2),
  elm_creek_vehicle_max = max(elm_creek_vehicle_count, na.rm = TRUE),
  lake_minnetonka_swim_mean = round(mean(lake_minnetonka_swim_pass, na.rm = TRUE), 2),
  lake_minnetonka_swim_max = max(lake_minnetonka_swim_pass, na.rm = TRUE)
)])