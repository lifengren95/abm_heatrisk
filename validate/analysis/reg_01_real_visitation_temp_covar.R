# # Task: Regression Model Testing
# # Author: Project contributors
# 
# library(data.table)
# 
# setwd("./validate/analysis")
# 
# runs_res <- fread("../../../../output/results/geometric_model_5runs/2024/combined_summary_all_dates.csv")
# 
# 
# # Basic linear regression
# model <- lm(moved_pct ~ avg_temperature + avg_temperature^2, data = runs_res)
# 
# 
# # Summary of the model
# summary(model)
# 
# library(ggplot2)
# 
# ggplot(runs_res, aes(x = avg_temperature, y = moved_pct)) +
#   geom_point() +
#   geom_smooth(method = "lm", se = TRUE, color = "blue") +
#   labs(title = "Moved % vs Average Temperature",
#        x = "Average Temperature (°F)",
#        y = "Percentage Moved") +
#   theme_minimal()
# 
# # Run quadratic regression
# model_quad <- lm(moved_pct ~ avg_temperature + I(avg_temperature^2), data = runs_res)
# 
# # Show model summary
# summary(model_quad)
# 
# ggplot(runs_res, aes(x = avg_temperature, y = moved_pct)) +
#   geom_point() +
#   stat_smooth(method = "lm", formula = y ~ x + I(x^2), color = "red") +
#   labs(title = "Quadratic Fit: Moved % vs Avg Temperature",
#        x = "Average Temperature (°F)",
#        y = "Percentage Moved") +
#   theme_minimal()
# 
# 
# ################################################################################
# 
# # -----------------------------
# # 1.  Clean real_visits -> temp_dt
# # -----------------------------
# real_visits <- fread(
#   "../../../../data/validate_data/intermediate/validate_cooling_summer_2024.csv"
# )
# 
# visit_cols   <- grep("_visits$", names(real_visits), value = TRUE)
# na_counts    <- sapply(real_visits[, ..visit_cols], \(x) sum(is.na(x)))
# valid_cols   <- names(na_counts[na_counts <= 1])
# 
# temp_dt <- real_visits[
#   complete.cases(real_visits[, ..valid_cols]),
#   .SD,
#   .SDcols = c("date", valid_cols)
# ]
# 
# # -----------------------------
# # 2.  Normalise BOTH date columns
# # -----------------------------
# runs_res[,  date := as.IDate(sprintf("%08d", as.integer(date)), format = "%Y%m%d")]
# temp_dt[,   date := as.IDate(format(as.IDate(date), "%Y-%m-%d"))]  # forces YYYY-MM-DD → IDate
# 
# # quick sanity-check
# stopifnot(length(intersect(runs_res$date, temp_dt$date)) > 0)
# 
# # -----------------------------
# # 3.  Merge temperature
# # -----------------------------
# temp_dt <- merge(
#   temp_dt,
#   runs_res[, .(date, avg_temperature)],
#   by = "date",
#   all.x = TRUE,
#   sort = FALSE
# )
# 
# # -----------------------------
# # 4.  Compute all_lib_visits
# #     (only columns that passed the NA ≤ 1 rule)
# # -----------------------------
# temp_dt[
#   ,
#   all_lib_visits := ifelse(
#     apply(.SD, 1, \(x) any(is.na(x))),  # if any NA in this row among valid cols
#     NA_real_,
#     rowSums(.SD)
#   ),
#   .SDcols = valid_cols
# ]
# 
# # ---------------------------------
# # 5.  Quick verification
# # ---------------------------------
# summary(temp_dt$avg_temperature)   # should now show real numbers
# summary(temp_dt$all_lib_visits)    # same as before, but tied to temp_dt
# 
# 
# ## ------------------------------------------------------------
# ##  Library Visits  ~  Temperature   (temp_dt)
# ## ------------------------------------------------------------
# 
# # Drop rows that still have NA in either variable
# lib_dt <- temp_dt[!is.na(all_lib_visits) & !is.na(avg_temperature)]
# 
# ## 1) Simple linear model
# lib_lin  <- lm(all_lib_visits ~ avg_temperature, data = lib_dt)
# summary(lib_lin)
# 
# ## 2) Quadratic model
# lib_quad <- lm(all_lib_visits ~ avg_temperature + I(avg_temperature^2), data = lib_dt)
# summary(lib_quad)
# 
# ## ------------------------------------------------------------
# ##  Plots
# ## ------------------------------------------------------------
# 
# library(ggplot2)
# 
# # Linear fit
# ggplot(lib_dt, aes(x = avg_temperature, y = all_lib_visits)) +
#   geom_point() +
#   geom_smooth(method = "lm", se = TRUE, color = "blue") +
#   labs(title = "All Library Visits vs Avg Temperature (Linear Fit)",
#        x = "Average Temperature (°F)",
#        y = "All Library Visits") +
#   theme_minimal()
# 
# # Quadratic fit
# ggplot(lib_dt, aes(x = avg_temperature, y = all_lib_visits)) +
#   geom_point() +
#   stat_smooth(method = "lm",
#               formula = y ~ x + I(x^2),
#               se = TRUE,
#               color = "red") +
#   labs(title = "All Library Visits vs Avg Temperature (Quadratic Fit)",
#        x = "Average Temperature (°F)",
#        y = "All Library Visits") +
#   theme_minimal()
# 
# 
# library(lmtest)     # coeftest()
# library(sandwich)   # vcovHC()
# 
# sig_stars <- function(p) {
#   if      (p < 0.001) "***"
#   else if (p < 0.01)  "**"
#   else if (p < 0.05)  "*"
#   else if (p < 0.1)   "."
#   else                ""
# }
# 
# visit_cols <- grep("_visits$", names(temp_dt), value = TRUE)
# 
# reg_out <- rbindlist(lapply(visit_cols, \(col) {
#   
#   dt_sub <- temp_dt[!is.na(avg_temperature) & !is.na(get(col))]
#   
#   # ---------------- Linear ----------------
#   lin  <- lm(get(col) ~ avg_temperature, data = dt_sub)
#   lin_rob <- coeftest(lin, vcov = vcovHC(lin, type = "HC1"))["avg_temperature", ]
#   
#   # ---------------- Quadratic -------------
#   quad <- lm(get(col) ~ avg_temperature + I(avg_temperature^2), data = dt_sub)
#   quad_rob <- coeftest(quad, vcov = vcovHC(quad, type = "HC1"))
#   quad_t1  <- quad_rob["avg_temperature", ]
#   quad_t2  <- quad_rob["I(avg_temperature^2)", ]
#   
#   data.table(
#     cooling_centers           = sub("_visits$", "", col),
#     
#     # ----- linear -----
#     reg_temp_coeff_linear     = lin_rob["Estimate"],
#     reg_temp_std_err_linear   = lin_rob["Std. Error"],
#     reg_temp_linear_sig       = sig_stars(lin_rob["Pr(>|t|)"]),
#     
#     # ----- quadratic (T) -----
#     reg_temp_coeff_quad       = quad_t1["Estimate"],
#     reg_temp_std_err_quad     = quad_t1["Std. Error"],
#     reg_temp_quad_sig         = sig_stars(quad_t1["Pr(>|t|)"]),
#     
#     # ----- quadratic (T²) -----
#     reg_temp2_coeff_quad      = quad_t2["Estimate"],
#     reg_temp2_std_err_quad    = quad_t2["Std. Error"],
#     reg_temp2_quad_sig        = sig_stars(quad_t2["Pr(>|t|)"])
#   )
# }))
# 
# fwrite(reg_out, "./validate/analysis/reg_out.csv")


# Task: Regression Model Testing
# Author: Project contributors

library(data.table)

setwd("./validate/analysis")

sim_validate_analysis_panel <- fread("../../../../data/validate_data/analysis/sim_validate_final_panel.csv")

sim_validate_analysis_panel$build_yr[sim_validate_analysis_panel$build_yr == 0] <- NA
sim_validate_analysis_panel$build_yr[sim_validate_analysis_panel$build_yr == "NA"] <- NA


################################################################################
# Step 1: T Test: Heat vs Non-Heat
################################################################################

# Work on a copy; keep valid heat_tag
dt <- copy(sim_validate_analysis_panel)[heat_tag %in% c(0,1)]

# Resolve library tag column name (user sometimes says "lib_tag")
lib_tag_col <- if ("lib_tag" %in% names(dt)) "lib_tag" else "lib_plus_elmcreek_tag"

# Helper: Welch t-test summarizer
run_welch <- function(yvar, subset_idx, variable_label, subset_label) {
  tmp <- dt[subset_idx & !is.na(get(yvar)), .(heat_tag, y = as.numeric(get(yvar)))]
  g0 <- tmp[heat_tag == 0, y]
  g1 <- tmp[heat_tag == 1, y]
  
  if (length(g0) == 0 | length(g1) == 0) {
    return(data.table(
      variable = variable_label, subset = subset_label,
      n_heat0 = length(g0), n_heat1 = length(g1),
      mean_heat0 = NA_real_, mean_heat1 = NA_real_,
      sd_heat0 = NA_real_, sd_heat1 = NA_real_,
      diff_mean = NA_real_, rel_increase_pct = NA_real_,
      t_stat = NA_real_, df = NA_real_, p_value = NA_real_,
      ci_lower = NA_real_, ci_upper = NA_real_
    ))
  }
  
  mean0 <- mean(g0); mean1 <- mean(g1)
  diff  <- mean1 - mean0
  rel   <- ifelse(mean0 == 0, NA_real_, (diff/mean0) * 100)
  
  tt <- t.test(g1, g0, var.equal = FALSE)  # Welch: mean(heat=1) - mean(heat=0)
  
  data.table(
    variable = variable_label, subset = subset_label,
    n_heat0 = length(g0), n_heat1 = length(g1),
    mean_heat0 = mean0, mean_heat1 = mean1,
    sd_heat0 = sd(g0), sd_heat1 = sd(g1),
    diff_mean = diff, rel_increase_pct = rel,
    t_stat = unname(tt$statistic), df = unname(tt$parameter),
    p_value = unname(tt$p.value),
    ci_lower = tt$conf.int[1], ci_upper = tt$conf.int[2]
  )
}

# Significance stars
sig_stars <- function(p) {
  if      (is.na(p)) "" 
  else if (p < 0.001) "***"
  else if (p < 0.01)  "**"
  else if (p < 0.05)  "*"
  else if (p < 0.1)   "."
  else                ""
}

# -----------------------
# Build result rows
# -----------------------
res <- list()

# (A) Real outcomes, whole sample (drop NAs automatically)
res[[length(res)+1]] <- run_welch("lib_visits",        rep(TRUE, nrow(dt)), "Library visits (real)",        "All rows")
res[[length(res)+1]] <- run_welch("ed_encounters",     rep(TRUE, nrow(dt)), "ED encounters (real)",         "All rows")
res[[length(res)+1]] <- run_welch("cellphone_visits",  rep(TRUE, nrow(dt)), "Cellphone visits (real)",      "All rows")

# (B) Simulation outcome: moved_pct_allcounty, by availability tags
res[[length(res)+1]] <- run_welch("moved_pct_allcounty", dt$`ed_tag` == 1,                   "Moved % (sim)", "ed_tag == 1")
res[[length(res)+1]] <- run_welch("moved_pct_allcounty", dt[[lib_tag_col]] == 1,             "Moved % (sim)", paste0(lib_tag_col," == 1"))
res[[length(res)+1]] <- run_welch("moved_pct_allcounty", dt$`cellphone_tag` == 1,            "Moved % (sim)", "cellphone_tag == 1")

ttest_summary <- rbindlist(res, use.names = TRUE, fill = TRUE)

# Add significance, round, save
ttest_summary[, sig := vapply(p_value, sig_stars, character(1))]

num_cols <- c("mean_heat0","mean_heat1","sd_heat0","sd_heat1",
              "diff_mean","rel_increase_pct","t_stat","df",
              "p_value","ci_lower","ci_upper")
ttest_summary[, (num_cols) := lapply(.SD, function(x) round(x, 3)), .SDcols = num_cols]

setcolorder(ttest_summary, c("variable","subset","n_heat0","n_heat1",
                             "mean_heat0","mean_heat1","diff_mean","rel_increase_pct",
                             "sd_heat0","sd_heat1","t_stat","df","p_value","sig","ci_lower","ci_upper"))

# 5) Save to CSV
out_path <- "../../../../output/validate/analysis/ttest_summary.csv"
fwrite(ttest_summary, out_path)


################################################################################
# Step 2: Regression Analysis
################################################################################

# ──────────────────────────────────────────────────────────────────────────────
# Regression tables & figures by buffer
# Author: Project contributors
# ──────────────────────────────────────────────────────────────────────────────
library(data.table)
library(ggplot2)
library(lmtest)
library(sandwich)
library(tools)

# 0) Data ----------------------------------------------------------------------
dt <- copy(sim_validate_analysis_panel)

# 1) Config -------------------------------------------------------------------
out_dir <- "./output/validate/analysis"
if (!dir.exists(out_dir)) dir.create(out_dir, recursive = TRUE)

buffers <- c("0_5miles","1miles","2miles","4miles","6miles","8miles","10miles")

# Outcomes (Y)
y_list <- c(
  lib_visits       = "lib_visits",
  cellphone_visits = "cellphone_visits",
  ed_encounters    = "ed_encounters"
)

# Temperature regressor (X1)
temp_var <- "avg_temperature_allcounty"
use_quadratic_temp <- FALSE  # set TRUE to include I(temp^2)

pretty_var <- function(v) {
  lab <- c(
    "(Intercept)"                    = "Intercept",
    "avg_temperature_allcounty"      = "Average temperature (°F)",
    "I(avg_temperature_allcounty^2)" = "Temperature^2",
    "parcels"                        = "# Parcels",
    "median_income"                  = "Median income",
    "avg_ac_ownership"               = "Avg AC ownership",
    "total_population"               = "Total population",
    "pct_elderly"                    = "% Elderly",
    "build_yr"                       = "Build year"
  )
  
  # Explicit mapping from covariate *prefix* to base label key in `lab`
  stems <- c(
    "parcels_within"   = "parcels",
    "median_income"    = "median_income",
    "avg_ac_ownership" = "avg_ac_ownership",
    "total_population" = "total_population",
    "pct_elderly"      = "pct_elderly"
  )
  
  # If it’s one of the buffer covariates like "median_income_4miles"
  for (s in names(stems)) {
    if (startsWith(v, paste0(s, "_"))) {
      suffix <- sub(paste0("^", s, "_"), "", v)
      base_key <- stems[[s]]
      base_lab <- if (base_key %in% names(lab)) lab[[base_key]] else base_key
      return(sprintf("%s (%s)", base_lab, suffix))
    }
  }
  
  # Otherwise use direct label or fall back to original name
  if (v %in% names(lab)) lab[[v]] else v
}

# 2) Helpers -------------------------------------------------------------------
# Build covariate names for a given buffer suffix
covars_for_buffer <- function(buf) {
  c(paste0("parcels_within_", buf),
    paste0("median_income_",  buf),
    paste0("avg_ac_ownership_",  buf),
    paste0("total_population_",  buf),
    paste0("pct_elderly_",   buf))
}

# Fit one model with robust SE; return data.table with rows=coeffs, cols=estimate,se
fit_model_robust <- function(data, y, x_vars) {
  fml_str <- if (use_quadratic_temp) {
    paste(y, "~", paste(c(temp_var, sprintf("I(%s^2)", temp_var), x_vars), collapse = " + "))
  } else {
    paste(y, "~", paste(c(temp_var, x_vars), collapse = " + "))
  }
  fml <- as.formula(fml_str)
  
  need_vars <- unique(c(y, temp_var, x_vars, "build_yr"))
  dd <- data[, ..need_vars]
  dd[[y]] <- as.numeric(dd[[y]])
  dd <- dd[complete.cases(dd)]
  
  if (nrow(dd) < 10) {
    vars_out <- c("(Intercept)", temp_var, if (use_quadratic_temp) sprintf("I(%s^2)", temp_var), x_vars, "build_yr")
    return(data.table(variable = vars_out, estimate = NA_real_, std_error = NA_real_, p_value = NA_real_,
                      N = nrow(dd), r2 = NA_real_))
  }
  
  m   <- lm(fml, data = dd)
  rob <- coeftest(m, vcov = vcovHC(m, type = "HC1"))
  
  out <- data.table(
    variable  = rownames(rob),
    estimate  = as.numeric(rob[, "Estimate"]),
    std_error = as.numeric(rob[, "Std. Error"]),
    p_value   = as.numeric(rob[, "Pr(>|t|)"])
  )
  out[, `:=`(N = nrow(dd), r2 = summary(m)$r.squared)]
  out[]
}

stars_fun <- function(p) {
  ifelse(is.na(p), "",
         ifelse(p < 0.01, "***",
                ifelse(p < 0.05, "**",
                       ifelse(p < 0.1, "*", ""))))
}


# Format "coef (se)"
fmt_coef_se <- function(est, se, digits = 3) {
  ifelse(is.na(est), NA_character_,
         sprintf("%.*f (%.*f)", digits, est, digits, se))
}

make_regline_plot <- function(data, y, x_vars, buffer_tag, outfile) {
  need_vars <- unique(c(y, temp_var, x_vars))
  dd <- data[, ..need_vars]
  dd[[y]] <- as.numeric(dd[[y]])
  dd <- dd[complete.cases(dd)]
  if (nrow(dd) < 10) {
    message(sprintf("Skip figure (insufficient rows): %s, %s", buffer_tag, y))
    return(invisible(NULL))
  }
  
  fml_str <- if (use_quadratic_temp) {
    paste(y, "~", paste(c(temp_var, sprintf("I(%s^2)", temp_var), x_vars), collapse = " + "))
  } else {
    paste(y, "~", paste(c(temp_var, x_vars), collapse = " + "))
  }
  m <- lm(as.formula(fml_str), data = dd)
  
  # Temperature grid
  t_seq <- seq(min(dd[[temp_var]], na.rm = TRUE),
               max(dd[[temp_var]], na.rm = TRUE), length.out = 200)
  
  # Hold covariates at means; fallback for build_yr if all NA
  cov_means <- lapply(x_vars, function(v) {
    mv <- mean(dd[[v]], na.rm = TRUE)
    if (is.na(mv) && v == "build_yr") 1970 else mv
  })
  names(cov_means) <- x_vars
  
  # Build newdata explicitly so names match formula terms
  newd <- data.frame(setNames(list(t_seq), temp_var), check.names = FALSE)
  for (v in x_vars) newd[[v]] <- cov_means[[v]]
  
  pred <- predict(m, newdata = newd)
  
  p <- ggplot(dd, aes(x = .data[[temp_var]], y = .data[[y]])) +
    geom_point(alpha = 0.6) +
    geom_line(aes(x = t_seq, y = pred), data = data.frame(t_seq, pred), linewidth = 1) +
    labs(title = sprintf("%s vs Temperature — %s", y, buffer_tag),
         x = "Average Temperature (°F)", y = y) +
    theme_minimal()
  
  ggsave(outfile, p, width = 7, height = 5, dpi = 300)
  invisible(NULL)
}

# 3) Main loop: per buffer, build table & figures --------------------------------
for (buf in buffers) {
  x_buf <- covars_for_buffer(buf)
  x_all <- c(x_buf, "build_yr")
  
  # Fit three models
  res_list <- lapply(y_list, function(yv) fit_model_robust(dt, y = yv, x_vars = x_all))
  
  # Build a table with rows=variables and columns = three outcomes (coef (se))
  # Determine row order from the first model's variables, but ensure full union
  all_vars <- unique(unlist(lapply(res_list, function(dd) dd$variable)))
  # Desired order: intercept, temp, temp^2 (if used), buffer covars, build_yr
  desired <- c("(Intercept)", temp_var, if (use_quadratic_temp) sprintf("I(%s^2)", temp_var),
               x_buf, "build_yr")
  row_order <- unique(c(desired, setdiff(all_vars, desired)))
  
  # Merge into one table
  # Merge into one table
  comb <- data.table(variable = row_order)
  for (nm in names(y_list)) {
    dd_res <- res_list[[nm]][, .(variable, estimate, std_error, p_value, N, r2)]
    setnames(dd_res,
             c("estimate","std_error","p_value","N","r2"),
             c(paste0(nm,"_est"), paste0(nm,"_se"), paste0(nm,"_p"),
               paste0(nm,"_N"),  paste0(nm,"_r2")))
    comb <- merge(comb, dd_res, by = "variable", all.x = TRUE)
  }
  
  # Labels
  comb[, pretty := vapply(variable, pretty_var, character(1))]
  
  # Coef row (with stars in separate Sig columns)
  coef_tab <- comb[, .(
    term                 = pretty,
    `Library coef`       = round(get("lib_visits_est"), 3),
    `Library Sig`        = stars_fun(get("lib_visits_p")),
    `Cellphone coef`     = round(get("cellphone_visits_est"), 3),
    `Cellphone Sig`      = stars_fun(get("cellphone_visits_p")),
    `ED coef`            = round(get("ed_encounters_est"), 3),
    `ED Sig`             = stars_fun(get("ed_encounters_p"))
  )]
  
  # SE row
  se_tab <- comb[, .(
    term                 = paste0(pretty, " (SE)"),
    `Library coef`       = ifelse(is.na(get("lib_visits_se")), NA_character_,
                                  sprintf("(%0.3f)", get("lib_visits_se"))),
    `Library Sig`        = "",
    `Cellphone coef`     = ifelse(is.na(get("cellphone_visits_se")), NA_character_,
                                  sprintf("(%0.3f)", get("cellphone_visits_se"))),
    `Cellphone Sig`      = "",
    `ED coef`            = ifelse(is.na(get("ed_encounters_se")), NA_character_,
                                  sprintf("(%0.3f)", get("ed_encounters_se"))),
    `ED Sig`             = ""
  )]
  
  out_tab <- rbindlist(list(coef_tab, se_tab), use.names = TRUE, fill = TRUE)
  
  # N and R2 rows
  N_row <- data.table(
    term = "N (obs.)",
    `Library coef`   = as.character(as.integer(unique(na.omit(comb$lib_visits_N))[1])),
    `Library Sig`    = "",
    `Cellphone coef` = as.character(as.integer(unique(na.omit(comb$cellphone_visits_N))[1])),
    `Cellphone Sig`  = "",
    `ED coef`        = as.character(as.integer(unique(na.omit(comb$ed_encounters_N))[1])),
    `ED Sig`         = ""
  )
  
  R2_row <- data.table(
    term = "R-squared",
    `Library coef`   = sprintf("%.3f", as.numeric(unique(na.omit(comb$lib_visits_r2))[1])),
    `Library Sig`    = "",
    `Cellphone coef` = sprintf("%.3f", as.numeric(unique(na.omit(comb$cellphone_visits_r2))[1])),
    `Cellphone Sig`  = "",
    `ED coef`        = sprintf("%.3f", as.numeric(unique(na.omit(comb$ed_encounters_r2))[1])),
    `ED Sig`         = ""
  )
  
  out_tab <- rbind(out_tab, N_row, R2_row, fill = TRUE)
  
  # Save CSV
  tab_file <- file.path(out_dir, sprintf("reg_table_buffer_%s.csv", buf))
  fwrite(out_tab, tab_file)
  
  # Figures: one per outcome (total 3 per buffer)
  for (nm in names(y_list)) {
    fig_file <- file.path(out_dir, sprintf("regline_%s_buffer_%s.png", nm, buf))
    make_regline_plot(dt, y = y_list[[nm]], x_vars = x_all, buffer_tag = buf, outfile = fig_file)
  }
}

message("Done. Wrote 7 tables and up to 21 figures to: ", out_dir)


# ──────────────────────────────────────────────────────────────────────────────
# Step 2b. Heat_tag regressions for the 1-mile buffer
# ──────────────────────────────────────────────────────────────────────────────

# Reuse: dt, out_dir, buffers, y_list already defined above

# (A) helpers --------------------------------------------------------------
# stars
stars_fun <- function(p) {
  ifelse(is.na(p), "",
         ifelse(p < 0.01, "***",
                ifelse(p < 0.05, "**",
                       ifelse(p < 0.1, "*", ""))))
}

# pretty label extension for heat_tag
pretty_var_heat <- function(v) {
  base <- pretty_var(v)
  if (v == "heat_tag") return("Heat day (1 = heat)")
  base
}

# robust fit, with heat_tag as regressor in place of temp
fit_model_robust_heat <- function(data, y, x_vars) {
  fml_str <- paste(y, "~", paste(c("heat_tag", x_vars), collapse = " + "))
  fml <- as.formula(fml_str)
  
  need_vars <- unique(c(y, "heat_tag", x_vars))
  dd <- data[, ..need_vars]
  dd[[y]] <- as.numeric(dd[[y]])
  dd <- dd[complete.cases(dd)]
  
  if (nrow(dd) < 10) {
    vars_out <- c("(Intercept)", "heat_tag", x_vars)
    return(data.table(variable = vars_out, estimate = NA_real_, std_error = NA_real_,
                      p_value = NA_real_, N = nrow(dd), r2 = NA_real_))
  }
  
  m   <- lm(fml, data = dd)
  rob <- lmtest::coeftest(m, vcov = sandwich::vcovHC(m, type = "HC1"))
  
  out <- data.table(
    variable  = rownames(rob),
    estimate  = as.numeric(rob[, "Estimate"]),
    std_error = as.numeric(rob[, "Std. Error"]),
    p_value   = as.numeric(rob[, "Pr(>|t|)"])
  )
  out[, `:=`(N = nrow(dd), r2 = summary(m)$r.squared)]
  out[]
}

# Build covariates for 1-mile buffer
covars_for_buffer <- function(buf) {
  c(paste0("parcels_within_", buf),
    paste0("median_income_",  buf),
    paste0("avg_ac_ownership_",  buf),
    paste0("total_population_",  buf),
    paste0("pct_elderly_",   buf))
}

# (B) 1-mile heat_tag table ------------------------------------------------
buf <- "1miles"
x_buf <- covars_for_buffer(buf)
x_all <- c(x_buf, "build_yr")

# Fit three models (heat_tag as key regressor)
res_list_ht <- lapply(y_list, function(yv) fit_model_robust_heat(dt, y = yv, x_vars = x_all))

# Row order: intercept, heat_tag, covars, build_yr (full union in case of drops)
all_vars_ht <- unique(unlist(lapply(res_list_ht, function(dd) dd$variable)))
desired_ht  <- c("(Intercept)", "heat_tag", x_buf, "build_yr")
row_order_ht <- unique(c(desired_ht, setdiff(all_vars_ht, desired_ht)))

# Merge into one wide table
comb_ht <- data.table(variable = row_order_ht)
for (nm in names(y_list)) {
  dd_res <- res_list_ht[[nm]][, .(variable, estimate, std_error, p_value, N, r2)]
  setnames(dd_res,
           c("estimate","std_error","p_value","N","r2"),
           c(paste0(nm,"_est"), paste0(nm,"_se"), paste0(nm,"_p"),
             paste0(nm,"_N"),  paste0(nm,"_r2")))
  comb_ht <- merge(comb_ht, dd_res, by = "variable", all.x = TRUE)
}
comb_ht[, pretty := vapply(variable, pretty_var_heat, character(1))]

# Econ-style: coef row + SE row, stars in separate Sig cols
coef_tab_ht <- comb_ht[, .(
  term                 = pretty,
  `Library coef`       = round(get("lib_visits_est"), 3),
  `Library Sig`        = stars_fun(get("lib_visits_p")),
  `Cellphone coef`     = round(get("cellphone_visits_est"), 3),
  `Cellphone Sig`      = stars_fun(get("cellphone_visits_p")),
  `ED coef`            = round(get("ed_encounters_est"), 3),
  `ED Sig`             = stars_fun(get("ed_encounters_p"))
)]
se_tab_ht <- comb_ht[, .(
  term                 = paste0(pretty, " (SE)"),
  `Library coef`       = ifelse(is.na(get("lib_visits_se")), NA_character_,
                                sprintf("(%0.3f)", get("lib_visits_se"))),
  `Library Sig`        = "",
  `Cellphone coef`     = ifelse(is.na(get("cellphone_visits_se")), NA_character_,
                                sprintf("(%0.3f)", get("cellphone_visits_se"))),
  `Cellphone Sig`      = "",
  `ED coef`            = ifelse(is.na(get("ed_encounters_se")), NA_character_,
                                sprintf("(%0.3f)", get("ed_encounters_se"))),
  `ED Sig`             = ""
)]
out_tab_ht <- rbindlist(list(coef_tab_ht, se_tab_ht), use.names = TRUE, fill = TRUE)

# N and R2 (single values per model)
N_row_ht <- data.table(
  term = "N (obs.)",
  `Library coef`   = as.character(as.integer(unique(na.omit(comb_ht$lib_visits_N))[1])),
  `Library Sig`    = "",
  `Cellphone coef` = as.character(as.integer(unique(na.omit(comb_ht$cellphone_visits_N))[1])),
  `Cellphone Sig`  = "",
  `ED coef`        = as.character(as.integer(unique(na.omit(comb_ht$ed_encounters_N))[1])),
  `ED Sig`         = ""
)
R2_row_ht <- data.table(
  term = "R-squared",
  `Library coef`   = sprintf("%.3f", as.numeric(unique(na.omit(comb_ht$lib_visits_r2))[1])),
  `Library Sig`    = "",
  `Cellphone coef` = sprintf("%.3f", as.numeric(unique(na.omit(comb_ht$cellphone_visits_r2))[1])),
  `Cellphone Sig`  = "",
  `ED coef`        = sprintf("%.3f", as.numeric(unique(na.omit(comb_ht$ed_encounters_r2))[1])),
  `ED Sig`         = ""
)
out_tab_ht <- rbind(out_tab_ht, N_row_ht, R2_row_ht, fill = TRUE)

# Save table
tab_file_ht <- file.path(out_dir, "reg_table_buffer_1miles_HEATTAG.csv")
fwrite(out_tab_ht, tab_file_ht)

# (C) 1-mile heat_tag figure (predicted values for heat=0/1, robust CI) ------
pred_rows <- list()
for (nm in names(y_list)) {
  yv <- y_list[[nm]]
  need_vars <- unique(c(yv, "heat_tag", x_all))
  dd <- dt[, ..need_vars]
  dd[[yv]] <- as.numeric(dd[[yv]])
  dd <- dd[complete.cases(dd)]
  if (nrow(dd) < 10) next
  
  m <- lm(as.formula(paste(yv, "~", paste(c("heat_tag", x_all), collapse = " + "))), data = dd)
  V <- sandwich::vcovHC(m, type = "HC1")
  
  # covariates at means
  cov_means <- lapply(x_all, function(v) mean(dd[[v]], na.rm = TRUE))
  names(cov_means) <- x_all
  
  newd0 <- as.data.frame(c(list(heat_tag = 0), cov_means))
  newd1 <- as.data.frame(c(list(heat_tag = 1), cov_means))
  
  X0 <- model.matrix(delete.response(terms(m)), newd0)
  X1 <- model.matrix(delete.response(terms(m)), newd1)
  
  pred0 <- as.numeric(X0 %*% coef(m))
  pred1 <- as.numeric(X1 %*% coef(m))
  
  se0 <- sqrt(as.numeric(X0 %*% V %*% t(X0)))
  se1 <- sqrt(as.numeric(X1 %*% V %*% t(X1)))
  
  pred_rows[[length(pred_rows)+1]] <- data.table(
    outcome = nm,
    heat_tag = c("No heat (0)", "Heat (1)"),
    pred = c(pred0, pred1),
    se   = c(se0, se1)
  )
}
pred_dt <- rbindlist(pred_rows, use.names = TRUE, fill = TRUE)

if (nrow(pred_dt) > 0) {
  pred_dt[, `:=`(lo = pred - 1.96*se, hi = pred + 1.96*se)]
  p_ht <- ggplot(pred_dt, aes(x = heat_tag, y = pred)) +
    geom_point() +
    geom_errorbar(aes(ymin = lo, ymax = hi), width = 0.15) +
    facet_wrap(~ outcome, scales = "free_y") +
    labs(title = "Predicted outcome by Heat Tag — 1-mile buffer (robust CI)",
         x = "", y = "Predicted value") +
    theme_minimal()
  ggsave(file.path(out_dir, "reg_plot_HEATTAG_1miles.png"), p_ht, width = 8, height = 5, dpi = 300)
}

# (D) By-ID heat_tag table (same covariates) -----------------------------------
byid_rows <- list()
ids <- unique(dt$id)
for (idv in ids) {
  dt_i <- dt[id == idv]
  site_name <- unique(na.omit(dt_i$name))[1]
  
  for (nm in names(y_list)) {
    yv <- y_list[[nm]]
    need_vars <- unique(c(yv, "heat_tag", x_all))
    dd <- dt_i[, ..need_vars]
    dd[[yv]] <- as.numeric(dd[[yv]])
    dd <- dd[complete.cases(dd)]
    
    if (nrow(dd) < 10) {
      byid_rows[[length(byid_rows)+1]] <- data.table(
        id = idv, name = site_name, outcome = nm,
        coef_heat = NA_real_, se_heat = NA_real_, p_heat = NA_real_,
        sig = "", N = nrow(dd), r2 = NA_real_
      )
      next
    }
    
    m <- lm(as.formula(paste(yv, "~", paste(c("heat_tag", x_all), collapse = " + "))), data = dd)
    rob <- lmtest::coeftest(m, vcov = sandwich::vcovHC(m, type = "HC1"))
    
    # pull heat_tag row robust stats
    if (!"heat_tag" %in% rownames(rob)) {
      byid_rows[[length(byid_rows)+1]] <- data.table(
        id = idv, name = site_name, outcome = nm,
        coef_heat = NA_real_, se_heat = NA_real_, p_heat = NA_real_,
        sig = "", N = nrow(dd), r2 = summary(m)$r.squared
      )
    } else {
      coef_h <- as.numeric(rob["heat_tag", "Estimate"])
      se_h   <- as.numeric(rob["heat_tag", "Std. Error"])
      p_h    <- as.numeric(rob["heat_tag", "Pr(>|t|)"])
      byid_rows[[length(byid_rows)+1]] <- data.table(
        id = idv, name = site_name, outcome = nm,
        coef_heat = coef_h, se_heat = se_h, p_heat = p_h,
        sig = stars_fun(p_h), N = nrow(dd), r2 = summary(m)$r.squared
      )
    }
  }
}
byid_tab <- rbindlist(byid_rows, use.names = TRUE, fill = TRUE)

# Round for readability
byid_tab[, `:=`(
  coef_heat = round(coef_heat, 3),
  se_heat   = round(se_heat, 3),
  p_heat    = round(p_heat, 3),
  r2        = round(r2, 3)
)]

# Save
fwrite(byid_tab, file.path(out_dir, "reg_byID_HEATTAG_1miles.csv"))

message("✓ Wrote:",
        "\n - Table: ", tab_file_ht,
        "\n - Figure: ", file.path(out_dir, "reg_plot_HEATTAG_1miles.png"),
        "\n - By-ID table: ", file.path(out_dir, "reg_byID_HEATTAG_1miles.csv"))
