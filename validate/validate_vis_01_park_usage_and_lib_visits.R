# Load required libraries
library(data.table)
library(ggplot2)
library(lubridate)
library(scales)

# Define file paths
intermediate_path <- "./data/validate_data/intermediate"
panel_file <- file.path(intermediate_path, "validate_cooling_summer_2024_panel.csv")

# Read panel data
panel_dt <- fread(panel_file)
panel_dt[, date := as.Date(date)]

# Identify location types
recreation_locations <- c("elm_creek", "lake_minnetonka")
library_locations <- unique(panel_dt[!location_name %in% recreation_locations, location_name])

cat("Recreation locations:", paste(recreation_locations, collapse = ", "), "\n")
cat("Library locations:", paste(library_locations, collapse = ", "), "\n")
cat("Total locations:", length(unique(panel_dt$location_name)), "\n")

# Check for complete cases by date
complete_cases_by_date <- panel_dt[, .(
  total_locations = .N,
  non_na_locations = sum(!is.na(visits)),
  complete_case = all(!is.na(visits))
), by = date]

cat("\nComplete cases analysis:\n")
cat("Total dates:", nrow(complete_cases_by_date), "\n")
cat("Dates with complete data:", sum(complete_cases_by_date$complete_case), "\n")
cat("Dates with missing data:", sum(!complete_cases_by_date$complete_case), "\n")

# Show dates with missing data
missing_dates <- complete_cases_by_date[complete_case == FALSE]
if(nrow(missing_dates) > 0) {
  cat("\nDates with missing data:\n")
  print(missing_dates)
}

# Exclude holidays and Sundays
holiday_dates <- as.Date(c("2024-06-19", "2024-07-04"))  # Juneteenth and Independence Day

# Identify Sundays in the complete date range
complete_cases_by_date[, is_sunday := weekdays(date) == "Sunday"]
sunday_dates <- complete_cases_by_date[is_sunday == TRUE, date]

# Combine holidays and Sundays for exclusion
excluded_dates <- c(holiday_dates, sunday_dates)

complete_dates <- complete_cases_by_date[complete_case == TRUE & !date %in% excluded_dates, date]
panel_complete_dt <- panel_dt[date %in% complete_dates]

cat("\nExcluded holiday dates:", paste(holiday_dates, collapse = ", "), "\n")
cat("Excluded Sunday dates:", paste(as.character(sunday_dates), collapse = ", "), "\n")
cat("Total excluded dates:", length(excluded_dates), "\n")
cat("Filtered data summary:\n")
cat("Dates retained:", length(complete_dates), "\n")
cat("Date range:", as.character(min(complete_dates)), "to", as.character(max(complete_dates)), "\n")

# ===== INVESTIGATE UNUSUAL LOW VISITATION DATES =====

# Ensure date column is properly formatted
panel_complete_dt[, date := as.Date(date)]

# Calculate daily library totals to identify unusual dates
daily_lib_totals <- panel_complete_dt[location_name %in% library_locations, .(
  daily_library_total = sum(visits, na.rm = TRUE),
  libraries_with_data = .N
), by = date]

# Ensure date column is Date class
daily_lib_totals[, date := as.Date(date)]

# Find dates with unusually low library visitation (bottom 5%)
low_threshold <- quantile(daily_lib_totals$daily_library_total, 0.05)
unusual_dates <- daily_lib_totals[daily_library_total <= low_threshold, date]

cat("\n=== INVESTIGATING UNUSUAL LOW VISITATION DATES ===\n")
cat("Low visitation threshold (5th percentile):", round(low_threshold, 0), "visits\n")
cat("Dates with unusually low library visitation:\n")

if(length(unusual_dates) > 0) {
  for(i in 1:length(unusual_dates)) {
    unusual_date <- as.Date(unusual_dates[i], origin = "1970-01-01")
    cat("\n--- Date:", as.character(unusual_date), "---\n")
    
    # Get library data for this date
    date_data <- panel_complete_dt[date == unusual_date & location_name %in% library_locations]
    
    # Sort by visits (ascending)
    setorder(date_data, visits)
    
    cat("Total library visits:", sum(date_data$visits, na.rm = TRUE), "\n")
    cat("Libraries with lowest visitation:\n")
    print(date_data[1:min(10, nrow(date_data)), .(location_name, visits)])
    
    # Check day of week
    cat("Day of week:", weekdays(unusual_date), "\n")
  }
} else {
  cat("No unusually low visitation dates found.\n")
}

# Also check for any potential holidays or unusual patterns
cat("\n=== ADDITIONAL DATE ANALYSIS ===\n")
daily_lib_totals[, date := as.Date(date)]  # Ensure proper date format
daily_lib_totals[, day_of_week := weekdays(date)]
daily_lib_totals[, is_weekend := day_of_week %in% c("Saturday", "Sunday")]

# Show lowest 10 visitation days
cat("10 lowest library visitation days:\n")
lowest_days <- daily_lib_totals[order(daily_library_total)][1:10]
print(lowest_days[, .(date, day_of_week, daily_library_total)])

# Show if there are any Sundays or other patterns
sunday_visits <- daily_lib_totals[day_of_week == "Sunday", .(date, daily_library_total)]
if(nrow(sunday_visits) > 0) {
  cat("\nSunday library visitation (many libraries may be closed):\n")
  print(sunday_visits)
}

# Show Saturday patterns too
saturday_visits <- daily_lib_totals[day_of_week == "Saturday", .(date, daily_library_total)]
if(nrow(saturday_visits) > 0) {
  cat("\nSaturday library visitation:\n")
  print(saturday_visits)
}

# Calculate daily aggregations
daily_summary <- panel_complete_dt[, .(
  total_visitation = sum(visits, na.rm = TRUE),
  library_visitation = sum(visits[location_name %in% library_locations], na.rm = TRUE),
  three_river_park_visitation = sum(visits[location_name %in% recreation_locations], na.rm = TRUE)
), by = date]

# Display summary statistics
cat("\nDaily visitation summary statistics:\n")
summary_stats <- daily_summary[, .(
  metric = c("Total", "Library", "Three River Parks"),
  mean_visits = c(
    round(mean(total_visitation), 0),
    round(mean(library_visitation), 0),
    round(mean(three_river_park_visitation), 0)
  ),
  max_visits = c(
    max(total_visitation),
    max(library_visitation),
    max(three_river_park_visitation)
  ),
  min_visits = c(
    min(total_visitation),
    min(library_visitation),
    min(three_river_park_visitation)
  )
)]
print(summary_stats)

# Create output directory for figures
figures_dir <- file.path(intermediate_path, "figures")
if (!dir.exists(figures_dir)) {
  dir.create(figures_dir, recursive = TRUE)
}

# 1. Total Visitation Trend
p1 <- ggplot(daily_summary, aes(x = date, y = total_visitation)) +
  geom_line(color = "steelblue", size = 1.2) +
  geom_point(color = "steelblue", size = 2, alpha = 0.7) +
  geom_smooth(method = "loess", se = TRUE, color = "red", alpha = 0.3) +
  scale_x_date(date_labels = "%b %d", date_breaks = "1 week") +
  scale_y_continuous(labels = comma_format()) +
  labs(
    title = "Total Daily Visitation - Summer 2024",
    subtitle = paste("Libraries + Three River Parks (holidays & Sundays excluded) |", 
                     min(complete_dates), "to", max(complete_dates)),
    x = "Date",
    y = "Total Visits",
    caption = "Note: Only dates with complete data; excludes Sundays, Juneteenth (6/19) & Independence Day (7/4)"
  ) +
  theme_minimal() +
  theme(
    plot.title = element_text(size = 14, face = "bold"),
    plot.subtitle = element_text(size = 12),
    axis.text.x = element_text(angle = 45, hjust = 1),
    panel.grid.minor = element_blank()
  )

ggsave(file.path(figures_dir, "total_visitation_trend.png"), p1, 
       width = 12, height = 6, dpi = 300)

# 2. Library Visitation Trend
p2 <- ggplot(daily_summary, aes(x = date, y = library_visitation)) +
  geom_line(color = "forestgreen", size = 1.2) +
  geom_point(color = "forestgreen", size = 2, alpha = 0.7) +
  geom_smooth(method = "loess", se = TRUE, color = "orange", alpha = 0.3) +
  scale_x_date(date_labels = "%b %d", date_breaks = "1 week") +
  scale_y_continuous(labels = comma_format()) +
  labs(
    title = "Library Daily Visitation - Summer 2024",
    subtitle = paste("Hennepin County Libraries (holidays & Sundays excluded) |", 
                     min(complete_dates), "to", max(complete_dates)),
    x = "Date",
    y = "Library Visits",
    caption = "Note: Only dates with complete data; excludes Sundays, Juneteenth (6/19) & Independence Day (7/4)"
  ) +
  theme_minimal() +
  theme(
    plot.title = element_text(size = 14, face = "bold"),
    plot.subtitle = element_text(size = 12),
    axis.text.x = element_text(angle = 45, hjust = 1),
    panel.grid.minor = element_blank()
  )

ggsave(file.path(figures_dir, "library_visitation_trend.png"), p2, 
       width = 12, height = 6, dpi = 300)

# 3. Three River Parks Visitation Trend
p3 <- ggplot(daily_summary, aes(x = date, y = three_river_park_visitation)) +
  geom_line(color = "darkorange", size = 1.2) +
  geom_point(color = "darkorange", size = 2, alpha = 0.7) +
  geom_smooth(method = "loess", se = TRUE, color = "purple", alpha = 0.3) +
  scale_x_date(date_labels = "%b %d", date_breaks = "1 week") +
  scale_y_continuous(labels = comma_format()) +
  labs(
    title = "Three River Parks Daily Visitation - Summer 2024", 
    subtitle = paste("Elm Creek + Lake Minnetonka (holidays & Sundays excluded) |", 
                     min(complete_dates), "to", max(complete_dates)),
    x = "Date",
    y = "Park Visits",
    caption = "Note: Only dates with complete data; excludes Sundays, Juneteenth (6/19) & Independence Day (7/4)"
  ) +
  theme_minimal() +
  theme(
    plot.title = element_text(size = 14, face = "bold"),
    plot.subtitle = element_text(size = 12),
    axis.text.x = element_text(angle = 45, hjust = 1),
    panel.grid.minor = element_blank()
  )

ggsave(file.path(figures_dir, "three_river_parks_visitation_trend.png"), p3, 
       width = 12, height = 6, dpi = 300)

# Display the plots
print(p1)
print(p2)
print(p3)

# Save the complete daily summary data
daily_summary_file <- file.path(intermediate_path, "daily_visitation_summary_no_sundays_holidays.csv")
fwrite(daily_summary, daily_summary_file)

cat("\nAnalysis complete!\n")
cat("Original date range: June 1 - August 31, 2024 (92 days)\n")
cat("Dates excluded due to incomplete data:", sum(!complete_cases_by_date$complete_case), "\n")
cat("Sundays excluded:", length(sunday_dates), "\n")
cat("Holidays excluded:", length(holiday_dates), "\n")
cat("Total dates excluded:", length(excluded_dates), "\n")
cat("Final analysis dates:", length(complete_dates), "\n")
cat("Figures saved to:", figures_dir, "\n")
cat("Daily summary data saved to:", daily_summary_file, "\n")

# Show correlation analysis
cat("\nCorrelation between visitation types:\n")
cor_matrix <- cor(daily_summary[, .(total_visitation, library_visitation, three_river_park_visitation)])
print(round(cor_matrix, 3))

# Show day of week patterns
daily_summary[, date := as.Date(date)]  # Ensure proper date format
daily_summary[, day_of_week := wday(date, label = TRUE)]
dow_summary <- daily_summary[, .(
  mean_total = round(mean(total_visitation), 0),
  mean_library = round(mean(library_visitation), 0), 
  mean_parks = round(mean(three_river_park_visitation), 0)
), by = day_of_week]

cat("\nVisitation by day of week (Sundays excluded from analysis):\n")
print(dow_summary)


# # Load required libraries
# library(data.table)
# library(ggplot2)
# library(lubridate)
# library(scales)
# 
# # Define file paths
# intermediate_path <- "./data/validate_data/intermediate"
# panel_file <- file.path(intermediate_path, "validate_cooling_summer_2024_panel.csv")
# 
# # Read panel data
# panel_dt <- fread(panel_file)
# panel_dt[, date := as.Date(date)]
# 
# # Identify location types
# recreation_locations <- c("elm_creek", "lake_minnetonka")
# library_locations <- unique(panel_dt[!location_name %in% recreation_locations, location_name])
# 
# cat("Recreation locations:", paste(recreation_locations, collapse = ", "), "\n")
# cat("Library locations:", paste(library_locations, collapse = ", "), "\n")
# cat("Total locations:", length(unique(panel_dt$location_name)), "\n")
# 
# # Check for complete cases by date
# complete_cases_by_date <- panel_dt[, .(
#   total_locations = .N,
#   non_na_locations = sum(!is.na(visits)),
#   complete_case = all(!is.na(visits))
# ), by = date]
# 
# cat("\nComplete cases analysis:\n")
# cat("Total dates:", nrow(complete_cases_by_date), "\n")
# cat("Dates with complete data:", sum(complete_cases_by_date$complete_case), "\n")
# cat("Dates with missing data:", sum(!complete_cases_by_date$complete_case), "\n")
# 
# # Show dates with missing data
# missing_dates <- complete_cases_by_date[complete_case == FALSE]
# if(nrow(missing_dates) > 0) {
#   cat("\nDates with missing data:\n")
#   print(missing_dates)
# }
# 
# # Exclude holidays
# holiday_dates <- as.Date(c("2024-06-19", "2024-07-04"))  # Juneteenth and Independence Day
# complete_dates <- complete_cases_by_date[complete_case == TRUE & !date %in% holiday_dates, date]
# panel_complete_dt <- panel_dt[date %in% complete_dates]
# 
# cat("\nExcluded holiday dates:", paste(holiday_dates, collapse = ", "), "\n")
# cat("Filtered data summary:\n")
# cat("Dates retained:", length(complete_dates), "\n")
# cat("Date range:", as.character(min(complete_dates)), "to", as.character(max(complete_dates)), "\n")
# 
# # ===== INVESTIGATE UNUSUAL LOW VISITATION DATES =====
# 
# # Ensure date column is properly formatted
# panel_complete_dt[, date := as.Date(date)]
# 
# # Calculate daily library totals to identify unusual dates
# daily_lib_totals <- panel_complete_dt[location_name %in% library_locations, .(
#   daily_library_total = sum(visits, na.rm = TRUE),
#   libraries_with_data = .N
# ), by = date]
# 
# # Ensure date column is Date class
# daily_lib_totals[, date := as.Date(date)]
# 
# # Find dates with unusually low library visitation (bottom 5%)
# low_threshold <- quantile(daily_lib_totals$daily_library_total, 0.05)
# unusual_dates <- daily_lib_totals[daily_library_total <= low_threshold, date]
# 
# cat("\n=== INVESTIGATING UNUSUAL LOW VISITATION DATES ===\n")
# cat("Low visitation threshold (5th percentile):", round(low_threshold, 0), "visits\n")
# cat("Dates with unusually low library visitation:\n")
# 
# if(length(unusual_dates) > 0) {
#   for(i in 1:length(unusual_dates)) {
#     unusual_date <- as.Date(unusual_dates[i], origin = "1970-01-01")
#     cat("\n--- Date:", as.character(unusual_date), "---\n")
#     
#     # Get library data for this date
#     date_data <- panel_complete_dt[date == unusual_date & location_name %in% library_locations]
#     
#     # Sort by visits (ascending)
#     setorder(date_data, visits)
#     
#     cat("Total library visits:", sum(date_data$visits, na.rm = TRUE), "\n")
#     cat("Libraries with lowest visitation:\n")
#     print(date_data[1:min(10, nrow(date_data)), .(location_name, visits)])
#     
#     # Check day of week
#     cat("Day of week:", weekdays(unusual_date), "\n")
#   }
# } else {
#   cat("No unusually low visitation dates found.\n")
# }
# 
# # Also check for any potential holidays or unusual patterns
# cat("\n=== ADDITIONAL DATE ANALYSIS ===\n")
# daily_lib_totals[, date := as.Date(date)]  # Ensure proper date format
# daily_lib_totals[, day_of_week := weekdays(date)]
# daily_lib_totals[, is_weekend := day_of_week %in% c("Saturday", "Sunday")]
# 
# # Show lowest 10 visitation days
# cat("10 lowest library visitation days:\n")
# lowest_days <- daily_lib_totals[order(daily_library_total)][1:10]
# print(lowest_days[, .(date, day_of_week, daily_library_total)])
# 
# # Show if there are any Sundays or other patterns
# sunday_visits <- daily_lib_totals[day_of_week == "Sunday", .(date, daily_library_total)]
# if(nrow(sunday_visits) > 0) {
#   cat("\nSunday library visitation (many libraries may be closed):\n")
#   print(sunday_visits)
# }
# 
# # Show Saturday patterns too
# saturday_visits <- daily_lib_totals[day_of_week == "Saturday", .(date, daily_library_total)]
# if(nrow(saturday_visits) > 0) {
#   cat("\nSaturday library visitation:\n")
#   print(saturday_visits)
# }
# 
# # Calculate daily aggregations
# daily_summary <- panel_complete_dt[, .(
#   total_visitation = sum(visits, na.rm = TRUE),
#   library_visitation = sum(visits[location_name %in% library_locations], na.rm = TRUE),
#   three_river_park_visitation = sum(visits[location_name %in% recreation_locations], na.rm = TRUE)
# ), by = date]
# 
# # Display summary statistics
# cat("\nDaily visitation summary statistics:\n")
# summary_stats <- daily_summary[, .(
#   metric = c("Total", "Library", "Three River Parks"),
#   mean_visits = c(
#     round(mean(total_visitation), 0),
#     round(mean(library_visitation), 0),
#     round(mean(three_river_park_visitation), 0)
#   ),
#   max_visits = c(
#     max(total_visitation),
#     max(library_visitation),
#     max(three_river_park_visitation)
#   ),
#   min_visits = c(
#     min(total_visitation),
#     min(library_visitation),
#     min(three_river_park_visitation)
#   )
# )]
# print(summary_stats)
# 
# # Create output directory for figures
# figures_dir <- file.path(intermediate_path, "figures")
# if (!dir.exists(figures_dir)) {
#   dir.create(figures_dir, recursive = TRUE)
# }
# 
# # 1. Total Visitation Trend
# p1 <- ggplot(daily_summary, aes(x = date, y = total_visitation)) +
#   geom_line(color = "steelblue", size = 1.2) +
#   geom_point(color = "steelblue", size = 2, alpha = 0.7) +
#   geom_smooth(method = "loess", se = TRUE, color = "red", alpha = 0.3) +
#   scale_x_date(date_labels = "%b %d", date_breaks = "1 week") +
#   scale_y_continuous(labels = comma_format()) +
#   labs(
#     title = "Total Daily Visitation - Summer 2024",
#     subtitle = paste("Libraries + Three River Parks (holidays excluded) |", 
#                      min(complete_dates), "to", max(complete_dates)),
#     x = "Date",
#     y = "Total Visits",
#     caption = "Note: Only dates with complete data; excludes Juneteenth (6/19) & Independence Day (7/4)"
#   ) +
#   theme_minimal() +
#   theme(
#     plot.title = element_text(size = 14, face = "bold"),
#     plot.subtitle = element_text(size = 12),
#     axis.text.x = element_text(angle = 45, hjust = 1),
#     panel.grid.minor = element_blank()
#   )
# 
# ggsave(file.path(figures_dir, "total_visitation_trend.png"), p1, 
#        width = 12, height = 6, dpi = 300)
# 
# # 2. Library Visitation Trend
# p2 <- ggplot(daily_summary, aes(x = date, y = library_visitation)) +
#   geom_line(color = "forestgreen", size = 1.2) +
#   geom_point(color = "forestgreen", size = 2, alpha = 0.7) +
#   geom_smooth(method = "loess", se = TRUE, color = "orange", alpha = 0.3) +
#   scale_x_date(date_labels = "%b %d", date_breaks = "1 week") +
#   scale_y_continuous(labels = comma_format()) +
#   labs(
#     title = "Library Daily Visitation - Summer 2024",
#     subtitle = paste("Hennepin County Libraries (holidays excluded) |", 
#                      min(complete_dates), "to", max(complete_dates)),
#     x = "Date",
#     y = "Library Visits",
#     caption = "Note: Only dates with complete data; excludes Juneteenth (6/19) & Independence Day (7/4)"
#   ) +
#   theme_minimal() +
#   theme(
#     plot.title = element_text(size = 14, face = "bold"),
#     plot.subtitle = element_text(size = 12),
#     axis.text.x = element_text(angle = 45, hjust = 1),
#     panel.grid.minor = element_blank()
#   )
# 
# ggsave(file.path(figures_dir, "library_visitation_trend.png"), p2, 
#        width = 12, height = 6, dpi = 300)
# 
# # 3. Three River Parks Visitation Trend
# p3 <- ggplot(daily_summary, aes(x = date, y = three_river_park_visitation)) +
#   geom_line(color = "darkorange", size = 1.2) +
#   geom_point(color = "darkorange", size = 2, alpha = 0.7) +
#   geom_smooth(method = "loess", se = TRUE, color = "purple", alpha = 0.3) +
#   scale_x_date(date_labels = "%b %d", date_breaks = "1 week") +
#   scale_y_continuous(labels = comma_format()) +
#   labs(
#     title = "Three River Parks Daily Visitation - Summer 2024", 
#     subtitle = paste("Elm Creek + Lake Minnetonka (holidays excluded) |", 
#                      min(complete_dates), "to", max(complete_dates)),
#     x = "Date",
#     y = "Park Visits",
#     caption = "Note: Only dates with complete data; excludes Juneteenth (6/19) & Independence Day (7/4)"
#   ) +
#   theme_minimal() +
#   theme(
#     plot.title = element_text(size = 14, face = "bold"),
#     plot.subtitle = element_text(size = 12),
#     axis.text.x = element_text(angle = 45, hjust = 1),
#     panel.grid.minor = element_blank()
#   )
# 
# ggsave(file.path(figures_dir, "three_river_parks_visitation_trend.png"), p3, 
#        width = 12, height = 6, dpi = 300)
# 
# # Display the plots
# print(p1)
# print(p2)
# print(p3)
# 
# # Save the complete daily summary data
# daily_summary_file <- file.path(intermediate_path, "daily_visitation_summary_complete_cases.csv")
# fwrite(daily_summary, daily_summary_file)
# 
# cat("\nAnalysis complete!\n")
# cat("Figures saved to:", figures_dir, "\n")
# cat("Daily summary data saved to:", daily_summary_file, "\n")
# 
# # Show correlation analysis
# cat("\nCorrelation between visitation types:\n")
# cor_matrix <- cor(daily_summary[, .(total_visitation, library_visitation, three_river_park_visitation)])
# print(round(cor_matrix, 3))
# 
# # Show day of week patterns
# daily_summary[, date := as.Date(date)]  # Ensure proper date format
# daily_summary[, day_of_week := wday(date, label = TRUE)]
# dow_summary <- daily_summary[, .(
#   mean_total = round(mean(total_visitation), 0),
#   mean_library = round(mean(library_visitation), 0), 
#   mean_parks = round(mean(three_river_park_visitation), 0)
# ), by = day_of_week]
# 
# cat("\nVisitation by day of week:\n")
# print(dow_summary)




# Load required libraries
library(data.table)
library(ggplot2)

# Define file paths
intermediate_path <- "./data/validate_data/intermediate"
panel_file <- file.path(intermediate_path, "validate_cooling_summer_2024_panel.csv")

# Read panel data
panel_dt <- fread(panel_file)
panel_dt[, date := as.Date(date)]

# Identify library locations (exclude recreation locations)
recreation_locations <- c("elm_creek", "lake_minnetonka")
library_locations <- unique(panel_dt[!location_name %in% recreation_locations, location_name])

cat("Total unique library locations identified:", length(library_locations), "\n")
cat("Library locations:\n")
print(library_locations)

# Filter to library data only
library_panel_dt <- panel_dt[location_name %in% library_locations]

# Calculate library count by date (count libraries with non-NA visitation data)
lib_count_by_date <- library_panel_dt[, .(
  lib_count = sum(!is.na(visits)),  # Count non-NA visits
  total_libraries = .N,             # Total library records (including NA)
  libraries_with_data = sum(!is.na(visits)),  # Same as lib_count for clarity
  libraries_missing_data = sum(is.na(visits)) # Count of libraries with missing data
), by = date]

# Sort by date
setorder(lib_count_by_date, date)

# Display summary
cat("\n=== LIBRARY DATA AVAILABILITY SUMMARY ===\n")
cat("Date range:", as.character(min(lib_count_by_date$date)), "to", as.character(max(lib_count_by_date$date)), "\n")
cat("Total dates:", nrow(lib_count_by_date), "\n")
cat("Maximum libraries reporting on any day:", max(lib_count_by_date$lib_count), "\n")
cat("Minimum libraries reporting on any day:", min(lib_count_by_date$lib_count), "\n")

# Show distribution of library counts
cat("\nDistribution of library counts per day:\n")
count_distribution <- lib_count_by_date[, .N, by = lib_count][order(lib_count)]
print(count_distribution)

# Show first 10 days
cat("\nFirst 10 days:\n")
print(lib_count_by_date[1:10, .(date, lib_count)])

# Show last 10 days
cat("\nLast 10 days:\n")
print(lib_count_by_date[(.N-9):.N, .(date, lib_count)])

# Identify dates with incomplete library data
incomplete_dates <- lib_count_by_date[lib_count < max(lib_count_by_date$lib_count)]
if(nrow(incomplete_dates) > 0) {
  cat("\nDates with incomplete library data (< maximum):\n")
  print(incomplete_dates[, .(date, lib_count, libraries_missing_data)])
} else {
  cat("\nAll dates have complete library data!\n")
}

# Create simple dataset with just date and lib_count
lib_count_simple <- lib_count_by_date[, .(date, lib_count)]

# Save the dataset
output_file <- file.path(intermediate_path, "library_count_by_date.csv")
fwrite(lib_count_simple, output_file)
cat("\nLibrary count dataset saved to:", output_file, "\n")

# Also save the detailed version
detailed_output_file <- file.path(intermediate_path, "library_data_availability_detailed.csv")
fwrite(lib_count_by_date, detailed_output_file)
cat("Detailed library availability data saved to:", detailed_output_file, "\n")

# Create a visualization of library data availability
p <- ggplot(lib_count_by_date, aes(x = date, y = lib_count)) +
  geom_line(color = "steelblue", size = 1) +
  geom_point(color = "steelblue", size = 2, alpha = 0.7) +
  geom_hline(yintercept = max(lib_count_by_date$lib_count), 
             linetype = "dashed", color = "red", alpha = 0.7) +
  scale_x_date(date_labels = "%b %d", date_breaks = "1 week") +
  scale_y_continuous(breaks = seq(0, max(lib_count_by_date$lib_count), by = 5)) +
  labs(
    title = "Library Data Availability - Summer 2024",
    subtitle = paste("Number of Libraries Reporting Visitation Data by Date"),
    x = "Date",
    y = "Number of Libraries with Data",
    caption = paste("Maximum possible libraries:", max(lib_count_by_date$lib_count))
  ) +
  theme_minimal() +
  theme(
    plot.title = element_text(size = 14, face = "bold"),
    plot.subtitle = element_text(size = 12),
    axis.text.x = element_text(angle = 45, hjust = 1),
    panel.grid.minor = element_blank()
  )

# Create figures directory and save plot
figures_dir <- file.path(intermediate_path, "figures")
if (!dir.exists(figures_dir)) {
  dir.create(figures_dir, recursive = TRUE)
}

ggsave(file.path(figures_dir, "library_data_availability.png"), p, 
       width = 12, height = 6, dpi = 300)

print(p)

cat("\nVisualization saved to:", file.path(figures_dir, "library_data_availability.png"), "\n")

# Show statistics
cat("\n=== STATISTICS ===\n")
cat("Mean libraries per day:", round(mean(lib_count_by_date$lib_count), 1), "\n")
cat("Standard deviation:", round(sd(lib_count_by_date$lib_count), 1), "\n")
cat("Days with complete data:", sum(lib_count_by_date$lib_count == max(lib_count_by_date$lib_count)), "\n")
cat("Days with incomplete data:", sum(lib_count_by_date$lib_count < max(lib_count_by_date$lib_count)), "\n")













