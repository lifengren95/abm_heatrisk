library(readxl)

# Read files
lib_visits <- read_excel("./data/validate_data/raw/lib_visits.xlsx")
cooling_center <- read.csv("./data/raw/Data/cooling_centers.csv")

# Merge
merged_data <- merge(lib_visits, cooling_center, 
                     by.x = "Location Name", by.y = "name", 
                     all = TRUE)

# Create validate column
merged_data$validate <- ifelse(!is.na(merged_data$id) & !is.na(merged_data[["Record Date"]]), 1, 0)

# Create subset where validate == 1
validated_subset <- merged_data[merged_data$validate == 1, ]

# Save the subset
write.csv(validated_subset, "validated_data.csv", row.names = FALSE)