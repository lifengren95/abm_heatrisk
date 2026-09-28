# # Task: Summary Statistics 
# # Author: Project contributors
# 

library(data.table)
library(sf)

setwd("./validate/analysis")

sim_validate_analysis_panel <- fread("../../../../data/validate_data/analysis/sim_validate_final_panel.csv")


# Summary Stats.

library(data.table)
dt <- as.data.table(sim_validate_analysis_panel)

# Clean to 5-digit ZIP
dt[, zip5 := {
  z <- as.character(zip)
  z <- sub("^\\s+|\\s+$", "", z)                # trim
  z <- sub("^(\\d{5}).*$", "\\1", z)            # keep first 5 digits
  fifelse(grepl("^\\d{5}$", z), z, NA_character_)
}]

# Flag libraries vs. cooling options
dt[, is_library := grepl("\\blib", tolower(type))]
dt[, is_cooling := !is_library]

# --- Top 5 ZIPs by cooling options (unique sites) ---
cool_by_zip <- dt[is_cooling & !is.na(zip5),
                  .(cooling_options = uniqueN(name)), by = zip5][order(-cooling_options, zip5)]
top5_cooling <- cool_by_zip[1:5]
top5_cooling

# (Optional) Top 5 ZIPs by libraries
lib_by_zip <- dt[is_library & !is.na(zip5),
                 .(libraries = uniqueN(name)), by = zip5][order(-libraries, zip5)]
top5_libraries <- lib_by_zip[1:5]
top5_libraries


library(data.table)
library(ggplot2)
library(scales)

dt <- as.data.table(sim_validate_analysis_panel)
dt[, date := as.IDate(date)]

# ── 1) SUMMARY STATS -----------------------------------------------------------
lib_summary <- dt[, .(
  variable = "lib_visits",
  n_nonmiss = sum(!is.na(lib_visits)),
  n_miss    = sum(is.na(lib_visits)),
  mean      = mean(lib_visits, na.rm = TRUE),
  sd        = sd(lib_visits, na.rm = TRUE),
  min       = min(lib_visits, na.rm = TRUE),
  p25       = quantile(lib_visits, 0.25, na.rm = TRUE),
  median    = quantile(lib_visits, 0.50, na.rm = TRUE),
  p75       = quantile(lib_visits, 0.75, na.rm = TRUE),
  max       = max(lib_visits, na.rm = TRUE)
)]

cell_summary <- dt[, .(
  variable = "cellphone_visits",
  n_nonmiss = sum(!is.na(cellphone_visits)),
  n_miss    = sum(is.na(cellphone_visits)),
  mean      = mean(cellphone_visits, na.rm = TRUE),
  sd        = sd(cellphone_visits, na.rm = TRUE),
  min       = min(cellphone_visits, na.rm = TRUE),
  p25       = quantile(cellphone_visits, 0.25, na.rm = TRUE),
  median    = quantile(cellphone_visits, 0.50, na.rm = TRUE),
  p75       = quantile(cellphone_visits, 0.75, na.rm = TRUE),
  max       = max(cellphone_visits, na.rm = TRUE)
)]

ed_summary <- dt[, .(
  variable = "ed_encounters",
  n_nonmiss = sum(!is.na(ed_encounters)),
  n_miss    = sum(is.na(ed_encounters)),
  mean      = mean(ed_encounters, na.rm = TRUE),
  sd        = sd(ed_encounters, na.rm = TRUE),
  min       = min(ed_encounters, na.rm = TRUE),
  p25       = quantile(ed_encounters, 0.25, na.rm = TRUE),
  median    = quantile(ed_encounters, 0.50, na.rm = TRUE),
  p75       = quantile(ed_encounters, 0.75, na.rm = TRUE),
  max       = max(ed_encounters, na.rm = TRUE)
)]

summary_table <- rbindlist(list(lib_summary, cell_summary, ed_summary), use.names = TRUE, fill = TRUE)
summary_table[]
# fwrite(summary_table, "summary_visits_ed.csv")

# ── 2) VISUALS -----------------------------------------------------------------
# (A) Histograms (free y-scales)
ggplot(dt[!is.na(lib_visits)], aes(x = lib_visits)) +
  geom_histogram(bins = 50) +
  scale_x_continuous(labels = comma) +
  labs(title = "Distribution: Library Visits", x = "lib_visits", y = "Count")

ggplot(dt[!is.na(cellphone_visits)], aes(x = cellphone_visits)) +
  geom_histogram(bins = 50) +
  scale_x_continuous(labels = comma) +
  labs(title = "Distribution: Cellphone Visits", x = "cellphone_visits", y = "Count")

ggplot(dt[!is.na(ed_encounters)], aes(x = ed_encounters)) +
  geom_histogram(bins = 50) +
  scale_x_continuous(labels = comma) +
  labs(title = "Distribution: ED Encounters", x = "ed_encounters", y = "Count")

# (B) Daily totals time series (one plot per metric)
lib_ts  <- dt[!is.na(lib_visits),        .(value = sum(lib_visits,        na.rm = TRUE)), by = date]
cell_ts <- dt[!is.na(cellphone_visits),  .(value = sum(cellphone_visits,  na.rm = TRUE)), by = date]
ed_ts   <- dt[!is.na(ed_encounters),     .(value = sum(ed_encounters,     na.rm = TRUE)), by = date]

ggplot(lib_ts, aes(date, value))  + geom_line() + labs(title = "Daily Total: Library Visits",   x = NULL, y = "Total")
ggplot(cell_ts, aes(date, value)) + geom_line() + labs(title = "Daily Total: Cellphone Visits", x = NULL, y = "Total")
ggplot(ed_ts, aes(date, value))   + geom_line() + labs(title = "Daily Total: ED Encounters",    x = NULL, y = "Total")


# (C) Boxplots by cluster (Cluster 4 tags), faceted by metric
long_dt <- melt(
  dt,
  measure.vars = c("lib_visits", "cellphone_visits"),
  variable.name = "metric",
  value.name = "value"
)

ggplot(long_dt[!is.na(value) & !is.na(cluster4_tag)],
       aes(x = factor(cluster4_tag), y = value)) +
  geom_boxplot(outlier.alpha = 0.2) +
  facet_wrap(~ metric, scales = "free_y") +
  labs(title = "Values by Cluster (4-group)", x = "cluster4_tag", y = NULL)





















library(data.table)
library(lmtest)
library(sandwich)

dt <- as.data.table(sim_validate_analysis_panel)

# Ensure Date + make year and month-day keys
dt[, date := as.IDate(date)]
dt[, year := as.integer(format(date, "%Y"))]
dt[, md   := format(date, "%m-%d")]   # e.g., "07-01"

# ----- Build July inputs -------------------------------------------------------

# (A) Cellphone: mean of 2020 & 2021 for each id and month-day in July
cell_july <- dt[md %like% "^07-" & year %in% c(2020, 2021) & !is.na(cellphone_visits),
                .(mean_cellphone_visit_2020_2021_july = mean(cellphone_visits, na.rm = TRUE)),
                by = .(id, name, md)
]

# (B) Library: 2024 July visits for each id and month-day (mean if dup rows)
lib_july <- dt[md %like% "^07-" & year == 2024 & !is.na(lib_visits),
               .(lib_visits_2024_july = mean(lib_visits, na.rm = TRUE)),
               by = .(id, name, md)
]

# (C) Merge to get the exact subset you asked for (id, md, both series)
panel_july <- merge(
  lib_july[, .(id, name, md, lib_visits_2024_july)],
  cell_july[, .(id, name, md, mean_cellphone_visit_2020_2021_july)],
  by = c("id","name","md"), all = FALSE
)

# Optional: inspect / save
# head(panel_july)
# fwrite(panel_july, "panel_july_lib2024_vs_cell_avg2020_2021.csv")

# ----- Regress, one site at a time --------------------------------------------

reg_by_site <- panel_july[, {
  if (.N >= 3 && var(mean_cellphone_visit_2020_2021_july, na.rm = TRUE) > 0) {
    m  <- lm(lib_visits_2024_july ~ mean_cellphone_visit_2020_2021_july)
    V  <- vcovHC(m, type = "HC1")                # Stata-style robust (HC1)
    ct <- coeftest(m, vcov. = V)
    data.table(
      beta_cell = unname(ct["mean_cellphone_visit_2020_2021_july","Estimate"]),
      se_robust = unname(ct["mean_cellphone_visit_2020_2021_july","Std. Error"]),
      t_stat    = unname(ct["mean_cellphone_visit_2020_2021_july","t value"]),
      p_value   = unname(ct["mean_cellphone_visit_2020_2021_july","Pr(>|t|)"]),
      n         = nobs(m),
      r2        = summary(m)$r.squared
    )
  } else {
    data.table(beta_cell = NA_real_, se_robust = NA_real_, t_stat = NA_real_,
               p_value = NA_real_, n = .N, r2 = NA_real_)
  }
}, by = .(id, name)]

# Significance stars
reg_by_site[, sig := fifelse(!is.na(p_value) & p_value <= 0.01, "***",
                             fifelse(!is.na(p_value) & p_value <= 0.05, "**",
                                     fifelse(!is.na(p_value) & p_value <= 0.10, "*", "")))]

setorder(reg_by_site, p_value)
# head(reg_by_site)
# fwrite(reg_by_site, "reg_by_site_lib2024_on_cell_avg2020_2021_july.csv")


# ----- Pooled regression (ALL sites combined) ----------------------------------

# Keep complete rows
pooled <- panel_july[!is.na(lib_visits_2024_july) &
                       !is.na(mean_cellphone_visit_2020_2021_july)]

# (1) Simple pooled OLS with robust (HC1) SEs
m_pool <- lm(lib_visits_2024_july ~ mean_cellphone_visit_2020_2021_july, data = pooled)
ct_pool <- coeftest(m_pool, vcov. = vcovHC(m_pool, type = "HC1"))

# (2) (Recommended) Cluster-robust SEs by site id
ct_pool_cl <- coeftest(m_pool, vcov. = vcovCL(m_pool, cluster = pooled$id, type = "HC1"))

# (3) (Optional) Site fixed effects + robust (HC1)
m_pool_fe <- lm(lib_visits_2024_july ~ mean_cellphone_visit_2020_2021_july + factor(id),
                data = pooled)
ct_pool_fe <- coeftest(m_pool_fe, vcov. = vcovHC(m_pool_fe, type = "HC1"))

# Tidy one-row summary for each model
star <- function(p) ifelse(p <= .01, "***", ifelse(p <= .05, "**", ifelse(p <= .10, "*", "")))
pool_tbl <- data.table(
  model     = c("Pooled OLS (HC1)", "Pooled OLS (cluster id)", "Site FE (HC1)"),
  beta_cell = c(ct_pool["mean_cellphone_visit_2020_2021_july","Estimate"],
                ct_pool_cl["mean_cellphone_visit_2020_2021_july","Estimate"],
                ct_pool_fe["mean_cellphone_visit_2020_2021_july","Estimate"]),
  se        = c(ct_pool["mean_cellphone_visit_2020_2021_july","Std. Error"],
                ct_pool_cl["mean_cellphone_visit_2020_2021_july","Std. Error"],
                ct_pool_fe["mean_cellphone_visit_2020_2021_july","Std. Error"]),
  t_stat    = c(ct_pool["mean_cellphone_visit_2020_2021_july","t value"],
                ct_pool_cl["mean_cellphone_visit_2020_2021_july","t value"],
                ct_pool_fe["mean_cellphone_visit_2020_2021_july","t value"]),
  p_value   = c(ct_pool["mean_cellphone_visit_2020_2021_july","Pr(>|t|)"],
                ct_pool_cl["mean_cellphone_visit_2020_2021_july","Pr(>|t|)"],
                ct_pool_fe["mean_cellphone_visit_2020_2021_july","Pr(>|t|)"]),
  n         = c(nobs(m_pool), nobs(m_pool), nobs(m_pool_fe)),
  r2        = c(summary(m_pool)$r.squared, summary(m_pool)$r.squared,
                summary(m_pool_fe)$r.squared)
)[, sig := star(p_value)]

pool_tbl[]
# fwrite(pool_tbl, "pooled_lib_on_cell_results.csv")

