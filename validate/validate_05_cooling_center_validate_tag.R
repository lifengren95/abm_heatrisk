
library(readxl)
library(data.table)
library(dplyr)

# Read files
lib_visits <- read_excel("./data/validate_data/raw/lib_visits.xlsx")
cooling_center <- read.csv("./data/raw/Data/cooling_centers.csv")

# Extract unique Location Names as a data.table
DT_unique_libs <- data.table(Location_Name = unique(lib_visits$`Location Name`))

# Standardize column names if necessary
setnames(cooling_center, old = "Location Name", new = "Location_Name", skip_absent = TRUE)

# Merge the datasets (inner join by default, or use `all.x = TRUE` for left join)
merged_data <- merge(DT_unique_libs, cooling_center, by.x = "Location_Name", by.y = "name", all.x = TRUE)

# View result
print(merged_data)

merged_data <- merged_data[Location_Name != "Plymouth Library"]
setDT(cooling_center)

# Rename 'name' to 'Location_Name' once
setnames(cooling_center, old = "name", new = "Location_Name", skip_absent = TRUE)

elm_creek_row <- cooling_center[`Location_Name` == "Elm Creek Park Reserve"]

# Append to merged_data (use fill = TRUE to allow differing columns)
merged_data <- rbind(merged_data, elm_creek_row, fill = TRUE)

merged_data[, validate := NULL]
setnames(merged_data, old = "Location_Name", new = "name", skip_absent = TRUE)

# 1. Create a new column in merged_data
merged_data[, validate_tag := 1]


setnames(cooling_center, old = "Location_Name", new = "name", skip_absent = TRUE)
# 3. Merge — assuming you want a left join from cooling_center to include validate_tag
cooling_center_validate <- merge(cooling_center, merged_data[, .(name, validate_tag)],
                               by = "name", all.x = TRUE)

cooling_center_validate[, validate := NULL]

# Replace NA in validate_tag with 0
cooling_center_validate[is.na(validate_tag), validate_tag := 0]
# Save to file
fwrite(cooling_center_validate, "./data/validate_data/intermediate/cooling_center.csv")


hennepin_daily_tmax_2024_no_heat <- hennepin_daily_tmax_2024[!(hennepin_daily_tmax_2024$date %in% c(20240826, 20240827)), ]


mean(hennepin_daily_tmax_2024_no_heat$max_temp_f)

validate_cooling_summer_2024_panel <- read_csv("./data/validate_data/intermediate/validate_cooling_summer_2024_panel.csv")


library(dplyr)

# Define heat event dates
heat_dates <- as.Date(c("2024-08-26", "2024-08-27"))

# Process
summary_visits <- validate_cooling_summer_2024_panel %>%
  mutate(event_type = if_else(date %in% heat_dates, "heat_event", "other")) %>%
  group_by(location_name, event_type) %>%
  summarise(avg_visits = mean(visits, na.rm = TRUE), .groups = "drop")

# Step 3: Convert location_name to Title Case + fix underscores for merge
summary_visits <- summary_visits %>%
  mutate(Location_Name = str_replace_all(str_to_title(location_name), "_", " "))

cooling_center_visits_summary <- read_csv("./data/validate_data/output/cooling_center_visits_summary.csv")


# Step 1: Add event_type to cooling_center_visits_summary
cooling_center_visits_tagged <- cooling_center_visits_summary %>%
  mutate(event_type = if_else(sim_temp_level == 94.73, "heat_event", "other"))

# Step 2: Standardize cooling_center name for merge
cooling_center_visits_tagged <- cooling_center_visits_tagged %>%
  mutate(Location_Name = str_to_lower(cooling_center))

# Step 3: Standardize Location_Name in summary_visits for join
summary_visits_clean <- summary_visits %>%
  mutate(Location_Name = str_to_lower(Location_Name))

# Step 4: Join on Location_Name and event_type
merged_data <- cooling_center_visits_tagged %>%
  left_join(summary_visits_clean, by = c("Location_Name", "event_type")) %>%
  select(cooling_center, sim_temp_level, visitation_simulated, event_type, avg_visits)

fwrite(merged_data, "./data/validate_data/output/validation_compare.csv")










###################################################################################









# # Load required libraries
# library(ggplot2)
# library(dplyr)
# library(tidyr)
# library(gridExtra)  # For side-by-side plots
# 
# # Set output directory
# output_dir <- "./data/validate_data/output"
# 
# # Create directory if it doesn't exist
# if (!dir.exists(output_dir)) {
#   dir.create(output_dir, recursive = TRUE)
# }
# 
# # Remove rows with NA values in avg_visits for cleaner visualization
# merged_data_clean <- merged_data %>% 
#   filter(!is.na(avg_visits))
# 
# # ===== PLOT 1: Side by side comparison of averages =====
# 
# # Calculate overall averages for simulated vs real visits
# avg_comparison <- merged_data_clean %>%
#   group_by(event_type) %>%
#   summarise(
#     Simulated = mean(visitation_simulated, na.rm = TRUE),
#     Real = mean(avg_visits, na.rm = TRUE),
#     .groups = 'drop'
#   ) %>%
#   pivot_longer(cols = c(Simulated, Real), 
#                names_to = "Data_Type", 
#                values_to = "Average_Visits")
# 
# # Create side-by-side bar plot
# plot1_heat <- avg_comparison %>%
#   filter(event_type == "heat_event") %>%
#   ggplot(aes(x = Data_Type, y = Average_Visits, fill = Data_Type)) +
#   geom_col(alpha = 0.8, width = 0.6) +
#   scale_fill_manual(values = c("Real" = "#d62728", "Simulated" = "#ff7f0e")) +
#   labs(title = "Heat Events",
#        x = "Data Type",
#        y = "Average Visits") +
#   theme_minimal() +
#   theme(legend.position = "none") +
#   ylim(0, max(avg_comparison$Average_Visits) * 1.1)
# 
# plot1_other <- avg_comparison %>%
#   filter(event_type == "other") %>%
#   ggplot(aes(x = Data_Type, y = Average_Visits, fill = Data_Type)) +
#   geom_col(alpha = 0.8, width = 0.6) +
#   scale_fill_manual(values = c("Real" = "#1f77b4", "Simulated" = "#2ca02c")) +
#   labs(title = "Other Days",
#        x = "Data Type",
#        y = "Average Visits") +
#   theme_minimal() +
#   theme(legend.position = "none") +
#   ylim(0, max(avg_comparison$Average_Visits) * 1.1)
# 
# # Combine plots side by side
# plot1_combined <- grid.arrange(plot1_heat, plot1_other, ncol = 2,
#                                top = "Average Library Visitation: Simulated vs Real")
# 
# # Save plot 1
# ggsave(filename = file.path(output_dir, "05_average_comparison_sidebyside.png"), 
#        plot = plot1_combined, width = 12, height = 6, dpi = 300)
# 
# # ===== PLOT 2: Difference distribution with density and bars =====
# 
# # Calculate differences (Real - Simulated) for each cooling center
# differences_data <- merged_data_clean %>%
#   mutate(difference = avg_visits - visitation_simulated) %>%
#   group_by(cooling_center, event_type) %>%
#   summarise(
#     avg_difference = mean(difference, na.rm = TRUE),
#     .groups = 'drop'
#   )
# 
# # Create density plot for heat events
# plot2_heat <- differences_data %>%
#   filter(event_type == "heat_event") %>%
#   ggplot(aes(x = avg_difference)) +
#   # Density curve
#   geom_density(fill = "#d62728", alpha = 0.3, color = "#d62728", size = 1.2) +
#   # Individual bars for each center
#   geom_histogram(aes(y = ..density..), bins = 15, alpha = 0.6, 
#                  fill = "#d62728", color = "white", size = 0.5) +
#   labs(title = "Heat Events",
#        subtitle = paste("n =", nrow(filter(differences_data, event_type == "heat_event")), "centers"),
#        x = "Difference (Real - Simulated)",
#        y = "Density") +
#   theme_minimal() +
#   geom_vline(xintercept = 0, linetype = "dashed", color = "black", alpha = 0.7)
# 
# # Create density plot for other days
# plot2_other <- differences_data %>%
#   filter(event_type == "other") %>%
#   ggplot(aes(x = avg_difference)) +
#   # Density curve
#   geom_density(fill = "#1f77b4", alpha = 0.3, color = "#1f77b4", size = 1.2) +
#   # Individual bars for each center
#   geom_histogram(aes(y = ..density..), bins = 15, alpha = 0.6, 
#                  fill = "#1f77b4", color = "white", size = 0.5) +
#   labs(title = "Other Days",
#        subtitle = paste("n =", nrow(filter(differences_data, event_type == "other")), "centers"),
#        x = "Difference (Real - Simulated)",
#        y = "Density") +
#   theme_minimal() +
#   geom_vline(xintercept = 0, linetype = "dashed", color = "black", alpha = 0.7)
# 
# # Combine difference plots side by side
# plot2_combined <- grid.arrange(plot2_heat, plot2_other, ncol = 2,
#                                top = "Distribution of Differences (Real - Simulated Visits)")
# 
# # Save plot 2
# ggsave(filename = file.path(output_dir, "06_difference_distribution_sidebyside.png"), 
#        plot = plot2_combined, width = 12, height = 6, dpi = 300)
# 
# # ===== Summary statistics for differences =====
# difference_summary <- differences_data %>%
#   group_by(event_type) %>%
#   summarise(
#     n_centers = n(),
#     mean_difference = mean(avg_difference, na.rm = TRUE),
#     median_difference = median(avg_difference, na.rm = TRUE),
#     sd_difference = sd(avg_difference, na.rm = TRUE),
#     min_difference = min(avg_difference, na.rm = TRUE),
#     max_difference = max(avg_difference, na.rm = TRUE),
#     .groups = 'drop'
#   )
# 
# cat("\n=== DIFFERENCE ANALYSIS SUMMARY ===\n")
# print(difference_summary)
# 
# # Save difference summary
# write.csv(difference_summary, 
#           file = file.path(output_dir, "difference_summary.csv"), 
#           row.names = FALSE)
# 
# # Save detailed differences by center
# write.csv(differences_data, 
#           file = file.path(output_dir, "center_differences_detailed.csv"), 
#           row.names = FALSE)
# 
# # Print completion message
# cat("\n=== NEW FILES SAVED ===\n")
# cat("Additional plots and summaries saved to:", output_dir, "\n")
# cat("New files created:\n")
# cat("- 05_average_comparison_sidebyside.png\n")
# cat("- 06_difference_distribution_sidebyside.png\n")
# cat("- difference_summary.csv\n")
# cat("- center_differences_detailed.csv\n")


# Load required libraries
library(ggplot2)
library(dplyr)
library(tidyr)
library(gridExtra)  # For side-by-side plots

# Set output directory
# NOTE: You will need to define the 'merged_data' object before this script can run successfully.
# For example:
# merged_data <- read.csv("path/to/your/merged_data.csv")

output_dir <- "./data/validate_data/output"

# Create directory if it doesn't exist
if (!dir.exists(output_dir)) {
  dir.create(output_dir, recursive = TRUE)
}

# Remove rows with NA values in avg_visits for cleaner visualization
merged_data_clean <- merged_data %>% 
  filter(!is.na(avg_visits))

# ===== PLOT 1: Side by side comparison of averages =====

# Calculate overall averages for simulated vs real visits
avg_comparison <- merged_data_clean %>%
  group_by(event_type) %>%
  summarise(
    Simulated = mean(visitation_simulated, na.rm = TRUE),
    Real = mean(avg_visits, na.rm = TRUE),
    .groups = 'drop'
  ) %>%
  pivot_longer(cols = c(Simulated, Real), 
               names_to = "Data_Type", 
               values_to = "Average_Visits")

# Create side-by-side bar plot
plot1_heat <- avg_comparison %>%
  filter(event_type == "heat_event") %>%
  ggplot(aes(x = Data_Type, y = Average_Visits, fill = Data_Type)) +
  geom_col(alpha = 0.8, width = 0.6) +
  scale_fill_manual(values = c("Real" = "#d62728", "Simulated" = "#ff7f0e")) +
  labs(title = "Heat Events",
       x = "Data Type",
       y = "Average Visits") +
  theme_minimal() +
  theme(legend.position = "none") +
  ylim(0, max(avg_comparison$Average_Visits) * 1.1)

plot1_other <- avg_comparison %>%
  filter(event_type == "other") %>%
  ggplot(aes(x = Data_Type, y = Average_Visits, fill = Data_Type)) +
  geom_col(alpha = 0.8, width = 0.6) +
  scale_fill_manual(values = c("Real" = "#1f77b4", "Simulated" = "#2ca02c")) +
  labs(title = "Other Days",
       x = "Data Type",
       y = "Average Visits") +
  theme_minimal() +
  theme(legend.position = "none") +
  ylim(0, max(avg_comparison$Average_Visits) * 1.1)

# Combine plots side by side
plot1_combined <- grid.arrange(plot1_heat, plot1_other, ncol = 2,
                               top = "Average Library Visitation: Simulated vs Real")

# Save plot 1
ggsave(filename = file.path(output_dir, "05_average_comparison_sidebyside.png"), 
       plot = plot1_combined, width = 12, height = 6, dpi = 300)

# ===== PLOT 2: Relative error distribution with individual center bars =====

# Calculate relative error (Simulated - Real) / Real for each cooling center
relative_error_data <- merged_data_clean %>%
  group_by(cooling_center, event_type) %>%
  summarise(
    avg_simulated = mean(visitation_simulated, na.rm = TRUE),
    avg_real = mean(avg_visits, na.rm = TRUE),
    .groups = 'drop'
  ) %>%
  mutate(relative_error = (avg_simulated - avg_real) / avg_real) %>%
  filter(!is.infinite(relative_error) & !is.na(relative_error))

# Create plot for heat events with individual bars for each center
heat_data <- relative_error_data %>% 
  filter(event_type == "heat_event") %>%
  arrange(relative_error) %>%
  mutate(center_rank = row_number())

# Main bar plot for heat events
plot2_heat_bars <- ggplot(heat_data, aes(x = center_rank, y = relative_error)) +
  geom_col(fill = "#d62728", alpha = 0.7, width = 0.8) +
  labs(title = "Heat Events - Individual Center Errors",
       x = "Cooling Centers (ranked by error)",
       y = "Relative Error: (Sim - Real) / Real") +
  theme_minimal() +
  geom_hline(yintercept = 0, linetype = "dashed", color = "black", alpha = 0.7) +
  theme(axis.text.x = element_blank(), axis.ticks.x = element_blank())

# Density plot for heat events  
plot2_heat_density <- ggplot(heat_data, aes(x = relative_error)) +
  geom_density(fill = "#d62728", alpha = 0.5, color = "#d62728", size = 1.2) +
  geom_rug(alpha = 0.8, color = "#d62728") +
  labs(title = "Heat Events - Error Distribution",
       x = "Relative Error: (Sim - Real) / Real",
       y = "Density") +
  theme_minimal() +
  geom_vline(xintercept = 0, linetype = "dashed", color = "black", alpha = 0.7)

# Create plot for other days
other_data <- relative_error_data %>% 
  filter(event_type == "other") %>%
  arrange(relative_error) %>%
  mutate(center_rank = row_number())

# Main bar plot for other days
plot2_other_bars <- ggplot(other_data, aes(x = center_rank, y = relative_error)) +
  geom_col(fill = "#1f77b4", alpha = 0.7, width = 0.8) +
  labs(title = "Other Days - Individual Center Errors",
       x = "Cooling Centers (ranked by error)",
       y = "Relative Error: (Sim - Real) / Real") +
  theme_minimal() +
  geom_hline(yintercept = 0, linetype = "dashed", color = "black", alpha = 0.7) +
  theme(axis.text.x = element_blank(), axis.ticks.x = element_blank())

# Density plot for other days
plot2_other_density <- ggplot(other_data, aes(x = relative_error)) +
  geom_density(fill = "#1f77b4", alpha = 0.5, color = "#1f77b4", size = 1.2) +
  geom_rug(alpha = 0.8, color = "#1f77b4") +
  labs(title = "Other Days - Error Distribution",
       x = "Relative Error: (Sim - Real) / Real",
       y = "Density") +
  theme_minimal() +
  # --- FIX: Removed stray double quote after 0.7 ---
  geom_vline(xintercept = 0, linetype = "dashed", color = "black", alpha = 0.7)

# Combine all plots in a 2x2 grid
plot2_combined <- grid.arrange(plot2_heat_bars, plot2_heat_density,
                               plot2_other_bars, plot2_other_density,
                               ncol = 2, nrow = 2,
                               top = "Relative Error Analysis: (Simulated - Real) / Real")

# Save plot 2 (now a 2x2 grid)
ggsave(filename = file.path(output_dir, "06_relative_error_analysis_grid.png"), 
       plot = plot2_combined, width = 14, height = 10, dpi = 300)

# ===== Summary statistics for relative errors =====
relative_error_summary <- relative_error_data %>%
  group_by(event_type) %>%
  summarise(
    n_centers = n(),
    mean_rel_error = mean(relative_error, na.rm = TRUE),
    median_rel_error = median(relative_error, na.rm = TRUE),
    sd_rel_error = sd(relative_error, na.rm = TRUE),
    min_rel_error = min(relative_error, na.rm = TRUE),
    max_rel_error = max(relative_error, na.rm = TRUE),
    # Add percentage of centers with positive/negative errors
    pct_overestimate = mean(relative_error > 0, na.rm = TRUE) * 100,
    pct_underestimate = mean(relative_error < 0, na.rm = TRUE) * 100,
    .groups = 'drop'
  )

cat("\n=== RELATIVE ERROR ANALYSIS SUMMARY ===\n")
print(relative_error_summary)

# Save relative error summary
write.csv(relative_error_summary, 
          file = file.path(output_dir, "relative_error_summary.csv"), 
          row.names = FALSE)

# Save detailed relative errors by center
write.csv(relative_error_data, 
          file = file.path(output_dir, "center_relative_errors_detailed.csv"), 
          row.names = FALSE)

# Print completion message
cat("\n=== NEW FILES SAVED ===\n")
cat("Additional plots and summaries saved to:", output_dir, "\n")
cat("New files created:\n")
cat("- 05_average_comparison_sidebyside.png\n")
cat("- 06_relative_error_analysis_grid.png\n")
cat("- relative_error_summary.csv\n")
cat("- center_relative_errors_detailed.csv\n")

