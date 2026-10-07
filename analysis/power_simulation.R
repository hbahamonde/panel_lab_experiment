#!/usr/bin/env Rscript

# Design-based power simulation for the primary sustained-reversal outcome.
#
# The simulation mirrors the implemented design:
#   * 300 completed participants in 28, 29, or 30 matching pools
#   * 10- or 15-person pools and five-person playing groups
#   * recovery assigned to whole pools after Block 1
#   * paired assignment when a 20-person session contains two 10-person pools
#   * a fair independent draw for a session containing one unmatched pool
#   * analysis restricted to final-round Block-1 supporters of direct
#     implementation
#   * a two-sided randomization-inference test using the actual assignment rule
#
# Power is necessarily conditional on quantities that are unknown before the
# pilot: eligibility for the primary subgroup, the persistence reversal rate,
# and within-pool similarity in reversal. The script therefore reports a
# sensitivity analysis rather than a single unconditional power number.

options(stringsAsFactors = FALSE)

seed <- as.integer(Sys.getenv("POWER_SEED", "20261006"))
simulation_reps <- as.integer(Sys.getenv("POWER_NSIM", "5000"))
randomization_reps <- as.integer(Sys.getenv("POWER_NPERM", "1999"))
curve_simulation_reps <- as.integer(Sys.getenv("POWER_CURVE_NSIM", "2500"))
curve_randomization_reps <- as.integer(Sys.getenv("POWER_CURVE_NPERM", "999"))
alpha_level <- 0.05

if (
  simulation_reps < 100 || randomization_reps < 199 ||
  curve_simulation_reps < 100 || curve_randomization_reps < 199
) {
  stop("Use at least 100 simulated experiments and 199 random assignments.")
}

set.seed(seed)

make_design <- function(label) {
  if (label == "30 pools") {
    pool_size <- rep(10L, 30L)
    stratum <- rep(seq_len(15L), each = 2L)
  } else if (label == "29 pools") {
    # Thirteen 20-person sessions, one 10-person session, and two 15-person
    # sessions. The last three pools are independently randomized.
    pool_size <- c(rep(10L, 27L), 15L, 15L)
    stratum <- c(rep(seq_len(13L), each = 2L), 14L, 15L, 16L)
  } else if (label == "28 pools") {
    # Twelve 20-person sessions and four 15-person sessions. The last four
    # pools are independently randomized.
    pool_size <- c(rep(10L, 24L), rep(15L, 4L))
    stratum <- c(rep(seq_len(12L), each = 2L), 13L:16L)
  } else {
    stop("Unknown design label: ", label)
  }

  stopifnot(sum(pool_size) == 300L)
  list(label = label, pool_size = pool_size, stratum = stratum)
}

make_balanced_design <- function(completed_participants) {
  if (
    completed_participants < 20L ||
    completed_participants %% 20L != 0L
  ) {
    stop("Scaling designs require a positive multiple of 20 participants.")
  }
  pools <- completed_participants / 10L
  list(
    label = paste(completed_participants, "participants"),
    pool_size = rep(10L, pools),
    stratum = rep(seq_len(pools / 2L), each = 2L)
  )
}

draw_assignments <- function(n_draws, stratum) {
  z <- matrix(0L, nrow = n_draws, ncol = length(stratum))
  for (s in unique(stratum)) {
    idx <- which(stratum == s)
    if (length(idx) == 2L) {
      first_treated <- rbinom(n_draws, 1L, 0.5)
      z[, idx[1L]] <- first_treated
      z[, idx[2L]] <- 1L - first_treated
    } else if (length(idx) == 1L) {
      z[, idx] <- rbinom(n_draws, 1L, 0.5)
    } else {
      stop("Every randomization stratum must contain one or two pools.")
    }
  }
  z
}

draw_beta_binomial_counts <- function(n, size, mean, icc) {
  if (icc <= 0) {
    return(rbinom(n, size, mean))
  }
  concentration <- 1 / icc - 1
  probability <- rbeta(
    n,
    shape1 = mean * concentration,
    shape2 = (1 - mean) * concentration
  )
  rbinom(n, size, probability)
}

cluster_probability <- function(u, mean, icc) {
  if (icc <= 0) {
    return(rep(mean, length(u)))
  }
  concentration <- 1 / icc - 1
  qbeta(
    u,
    shape1 = mean * concentration,
    shape2 = (1 - mean) * concentration
  )
}

simulate_power <- function(
  design,
  eligible_share,
  persistence_rate,
  effect,
  outcome_icc,
  eligibility_icc = 0.05,
  n_sim = simulation_reps,
  n_perm = randomization_reps,
  alpha = alpha_level
) {
  if (persistence_rate + effect >= 1) {
    stop("The persistence rate plus the risk difference must be below one.")
  }

  j <- length(design$pool_size)
  z_observed <- draw_assignments(n_sim, design$stratum)
  z_random <- draw_assignments(n_perm, design$stratum)

  eligible <- matrix(0L, nrow = n_sim, ncol = j)
  reversals <- matrix(0L, nrow = n_sim, ncol = j)

  for (pool in seq_len(j)) {
    eligible[, pool] <- draw_beta_binomial_counts(
      n_sim,
      design$pool_size[pool],
      eligible_share,
      eligibility_icc
    )

    latent_rank <- runif(n_sim)
    arm_mean <- persistence_rate + effect * z_observed[, pool]
    probability <- numeric(n_sim)
    for (arm in c(0L, 1L)) {
      idx <- which(z_observed[, pool] == arm)
      probability[idx] <- cluster_probability(
        latent_rank[idx],
        persistence_rate + effect * arm,
        outcome_icc
      )
    }
    reversals[, pool] <- rbinom(n_sim, eligible[, pool], probability)
  }

  treated_y <- rowSums(z_observed * reversals)
  treated_n <- rowSums(z_observed * eligible)
  total_y <- rowSums(reversals)
  total_n <- rowSums(eligible)
  control_y <- total_y - treated_y
  control_n <- total_n - treated_n

  observed_stat <- treated_y / treated_n - control_y / control_n

  # Matrix multiplication evaluates every simulated dataset under the same
  # Monte Carlo sample from the prespecified assignment mechanism.
  perm_treated_y <- z_random %*% t(reversals)
  perm_treated_n <- z_random %*% t(eligible)
  perm_control_y <- matrix(
    total_y,
    nrow = n_perm,
    ncol = n_sim,
    byrow = TRUE
  ) - perm_treated_y
  perm_control_n <- matrix(
    total_n,
    nrow = n_perm,
    ncol = n_sim,
    byrow = TRUE
  ) - perm_treated_n

  perm_stat <- perm_treated_y / perm_treated_n -
    perm_control_y / perm_control_n
  exceed <- sweep(abs(perm_stat), 2L, abs(observed_stat), FUN = ">=")
  p_value <- (1 + colSums(exceed, na.rm = TRUE)) / (n_perm + 1)
  valid <- is.finite(observed_stat) & is.finite(p_value)
  power <- mean(p_value[valid] < alpha)

  data.frame(
    design = design$label,
    pools = j,
    paired_strata = sum(table(design$stratum) == 2L),
    unmatched_pools = sum(table(design$stratum) == 1L),
    eligible_share = eligible_share,
    persistence_rate = persistence_rate,
    outcome_icc = outcome_icc,
    eligibility_icc = eligibility_icc,
    risk_difference = effect,
    power = power,
    monte_carlo_se = sqrt(power * (1 - power) / sum(valid)),
    mean_eligible = mean(total_n[valid]),
    simulations = sum(valid),
    random_assignments = n_perm,
    stringsAsFactors = FALSE
  )
}

designs <- lapply(c("30 pools", "29 pools", "28 pools"), make_design)

# The central planning scenario is not a claim about behavior. It is a common
# reference point: half of participants enter the primary subgroup, 20 percent
# reverse under persistence, and the outcome ICC is 0.05.
effect_grid <- seq(0, 0.35, by = 0.025)
central_results <- do.call(
  rbind,
  lapply(designs, function(design) {
    do.call(
      rbind,
      lapply(effect_grid, function(effect) {
        simulate_power(
          design = design,
          eligible_share = 0.50,
          persistence_rate = 0.20,
          effect = effect,
          outcome_icc = 0.05
        )
      })
    )
  })
)
central_results$scenario <- "Central"

# Sensitivity scenarios retain the preferred 30-pool configuration and vary
# the main unknown determinants of power.
sensitivity_definitions <- list(
  list(name = "Lower eligibility, higher clustering", eligible = 0.40,
       persistence = 0.20, outcome_icc = 0.10, eligibility_icc = 0.10),
  list(name = "Central", eligible = 0.50,
       persistence = 0.20, outcome_icc = 0.05, eligibility_icc = 0.05),
  list(name = "Higher eligibility, lower clustering", eligible = 0.60,
       persistence = 0.20, outcome_icc = 0.02, eligibility_icc = 0.02),
  list(name = "Higher persistence reversal", eligible = 0.50,
       persistence = 0.35, outcome_icc = 0.05, eligibility_icc = 0.05)
)

sensitivity_results <- do.call(
  rbind,
  lapply(sensitivity_definitions, function(scenario) {
    result <- do.call(
      rbind,
      lapply(effect_grid, function(effect) {
        simulate_power(
          design = designs[[1L]],
          eligible_share = scenario$eligible,
          persistence_rate = scenario$persistence,
          effect = effect,
          outcome_icc = scenario$outcome_icc,
          eligibility_icc = scenario$eligibility_icc
        )
      })
    )
    result$scenario <- scenario$name
    result
  })
)

all_results <- rbind(
  central_results,
  sensitivity_results[sensitivity_results$scenario != "Central", ]
)
all_results <- all_results[, c(
  "scenario", "design", "pools", "paired_strata", "unmatched_pools",
  "eligible_share", "persistence_rate", "outcome_icc", "eligibility_icc",
  "risk_difference", "power", "monte_carlo_se", "mean_eligible",
  "simulations", "random_assignments"
)]

# Resolve the output directory from the script path when run with Rscript.
script_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
if (length(script_arg) == 1L) {
  script_path <- normalizePath(sub("^--file=", "", script_arg))
  output_dir <- dirname(script_path)
} else {
  output_dir <- normalizePath("analysis")
}

output_file <- file.path(output_dir, "power_simulation_results.csv")
write.csv(all_results, output_file, row.names = FALSE)

interpolate_mde <- function(data, target = 0.80) {
  data <- data[order(data$risk_difference), ]
  above <- which(data$power >= target)
  if (!length(above)) {
    return(NA_real_)
  }
  hi <- above[1L]
  if (hi == 1L) {
    return(data$risk_difference[hi])
  }
  lo <- hi - 1L
  x0 <- data$risk_difference[lo]
  x1 <- data$risk_difference[hi]
  y0 <- data$power[lo]
  y1 <- data$power[hi]
  if (y1 == y0) {
    return(x1)
  }
  x0 + (target - y0) * (x1 - x0) / (y1 - y0)
}

mde_groups <- split(
  all_results,
  interaction(all_results$scenario, all_results$design, drop = TRUE)
)
mde <- do.call(
  rbind,
  lapply(mde_groups, function(data) {
    data.frame(
      scenario = data$scenario[1L],
      design = data$design[1L],
      mde_80 = interpolate_mde(data, 0.80),
      stringsAsFactors = FALSE
    )
  })
)
mde_file <- file.path(output_dir, "power_simulation_mde.csv")
write.csv(mde, mde_file, row.names = FALSE)

# Sample-size curves use the cleanest scaling path for this design: every
# additional 20 completed participants create two new 10-person pools and one
# additional paired treatment assignment. This isolates the statistical value
# of adding independent pools from the incidental mix of 10- and 15-person
# pools in the fixed 300-participant design.
sample_grid <- seq(100L, 2500L, by = 100L)
curve_effects <- c(0.10, 0.15, 0.20, 0.25, 0.30)

simulate_curve_point <- function(
  completed_participants,
  eligible_share,
  persistence_rate,
  effect,
  outcome_icc,
  eligibility_icc
) {
  result <- simulate_power(
    design = make_balanced_design(completed_participants),
    eligible_share = eligible_share,
    persistence_rate = persistence_rate,
    effect = effect,
    outcome_icc = outcome_icc,
    eligibility_icc = eligibility_icc,
    n_sim = curve_simulation_reps,
    n_perm = curve_randomization_reps
  )
  result$completed_participants <- completed_participants
  result
}

set.seed(seed + 1L)
effect_curve <- do.call(
  rbind,
  lapply(curve_effects, function(effect) {
    do.call(
      rbind,
      lapply(sample_grid, function(n) {
        simulate_curve_point(
          completed_participants = n,
          eligible_share = 0.50,
          persistence_rate = 0.20,
          effect = effect,
          outcome_icc = 0.05,
          eligibility_icc = 0.05
        )
      })
    )
  })
)
effect_curve$effect_label <- paste0(
  round(100 * effect_curve$risk_difference), " percentage points"
)

curve_scenarios <- list(
  list(name = "Central", eligible = 0.50, persistence = 0.20,
       outcome_icc = 0.05, eligibility_icc = 0.05),
  list(name = "Higher eligibility, lower clustering", eligible = 0.60,
       persistence = 0.20, outcome_icc = 0.02, eligibility_icc = 0.02),
  list(name = "Higher persistence reversal", eligible = 0.50,
       persistence = 0.35, outcome_icc = 0.05, eligibility_icc = 0.05),
  list(name = "Lower eligibility, higher clustering", eligible = 0.40,
       persistence = 0.20, outcome_icc = 0.10, eligibility_icc = 0.10)
)

# Reuse the central 20-point curve and simulate only the three alternative
# assumptions.
scenario_curve <- effect_curve[
  effect_curve$risk_difference == 0.20,
]
scenario_curve$scenario <- "Central"

alternative_curve <- do.call(
  rbind,
  lapply(curve_scenarios[-1L], function(scenario) {
    result <- do.call(
      rbind,
      lapply(sample_grid, function(n) {
        simulate_curve_point(
          completed_participants = n,
          eligible_share = scenario$eligible,
          persistence_rate = scenario$persistence,
          effect = 0.20,
          outcome_icc = scenario$outcome_icc,
          eligibility_icc = scenario$eligibility_icc
        )
      })
    )
    result$scenario <- scenario$name
    result
  })
)
alternative_curve$effect_label <- "20 percentage points"
scenario_curve <- rbind(scenario_curve, alternative_curve)

add_monotone_power <- function(data, group_variable) {
  groups <- split(data, data[[group_variable]])
  do.call(
    rbind,
    lapply(groups, function(group) {
      group <- group[order(group$completed_participants), ]
      group$power_monotone <- pmin(
        1,
        pmax(0, isoreg(group$completed_participants, group$power)$yf)
      )
      group
    })
  )
}

effect_curve <- add_monotone_power(effect_curve, "effect_label")
scenario_curve <- add_monotone_power(scenario_curve, "scenario")

estimate_required_n <- function(data, target = 0.80) {
  data <- data[order(data$completed_participants), ]
  y <- data$power_monotone
  x <- data$completed_participants
  above <- which(y >= target)
  if (!length(above)) {
    return(NA_integer_)
  }
  hi <- above[1L]
  if (hi == 1L) {
    return(as.integer(x[hi]))
  }
  lo <- hi - 1L
  interpolated <- x[lo] +
    (target - y[lo]) * (x[hi] - x[lo]) / (y[hi] - y[lo])
  as.integer(20L * ceiling(interpolated / 20L))
}

effect_thresholds <- do.call(
  rbind,
  lapply(split(effect_curve, effect_curve$effect_label), function(data) {
    data.frame(
      curve = "Treatment effect",
      label = data$effect_label[1L],
      risk_difference = data$risk_difference[1L],
      eligible_share = data$eligible_share[1L],
      persistence_rate = data$persistence_rate[1L],
      intrapool_correlation = data$outcome_icc[1L],
      participants_for_80_power = estimate_required_n(data),
      stringsAsFactors = FALSE
    )
  })
)

scenario_thresholds <- do.call(
  rbind,
  lapply(split(scenario_curve, scenario_curve$scenario), function(data) {
    data.frame(
      curve = "Assumption scenario at 20-point effect",
      label = data$scenario[1L],
      risk_difference = 0.20,
      eligible_share = data$eligible_share[1L],
      persistence_rate = data$persistence_rate[1L],
      intrapool_correlation = data$outcome_icc[1L],
      participants_for_80_power = estimate_required_n(data),
      stringsAsFactors = FALSE
    )
  })
)

effect_curve_file <- file.path(output_dir, "power_curve_effects.csv")
scenario_curve_file <- file.path(output_dir, "power_curve_scenarios.csv")
threshold_file <- file.path(output_dir, "power_curve_thresholds.csv")
write.csv(effect_curve, effect_curve_file, row.names = FALSE)
write.csv(scenario_curve, scenario_curve_file, row.names = FALSE)
write.csv(
  rbind(effect_thresholds, scenario_thresholds),
  threshold_file,
  row.names = FALSE
)

effect_order <- paste0(c(10, 15, 20, 25, 30), " percentage points")
effect_colors <- c("#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7")
scenario_order <- c(
  "Higher eligibility, lower clustering",
  "Central",
  "Higher persistence reversal",
  "Lower eligibility, higher clustering"
)
scenario_colors <- c("#009E73", "#0072B2", "#E69F00", "#D55E00")

draw_power_figure <- function() {
  old_par <- par(
    mfrow = c(1, 2),
    mar = c(4.2, 4.2, 2.6, 0.8),
    oma = c(0.4, 0.4, 0.2, 0.2),
    las = 1,
    family = "serif"
  )
  on.exit(par(old_par))

  plot(
    NA,
    xlim = range(sample_grid),
    ylim = c(0, 1),
    xlab = "Completed participants",
    ylab = "Probability of detecting the effect",
    main = "(a) Different treatment effects",
    xaxt = "n"
  )
  axis(1, at = c(100, 300, 500, 1000, 1500, 2000, 2500))
  abline(h = 0.80, lty = 2, col = "grey45")
  abline(v = 300, lty = 3, col = "grey55")
  for (index in seq_along(effect_order)) {
    data <- effect_curve[effect_curve$effect_label == effect_order[index], ]
    data <- data[order(data$completed_participants), ]
    lines(
      data$completed_participants,
      data$power_monotone,
      col = effect_colors[index],
      lwd = 2.2
    )
    points(
      data$completed_participants,
      data$power,
      col = effect_colors[index],
      pch = 16,
      cex = 0.45
    )
  }
  text(325, 0.08, "Current N = 300", srt = 90, col = "grey35", cex = 0.78)
  text(2450, 0.825, "80%", col = "grey35", cex = 0.78)
  legend(
    "bottomright",
    legend = sub(" percentage points", " pp", effect_order),
    col = effect_colors,
    lwd = 2.2,
    bty = "n",
    cex = 0.82,
    title = "Recovery effect"
  )

  plot(
    NA,
    xlim = c(100, 1200),
    ylim = c(0, 1),
    xlab = "Completed participants",
    ylab = "Probability of detecting the effect",
    main = "(b) Different assumptions, 20 pp effect",
    xaxt = "n"
  )
  axis(1, at = c(100, 300, 500, 700, 900, 1200))
  abline(h = 0.80, lty = 2, col = "grey45")
  abline(v = 300, lty = 3, col = "grey55")
  for (index in seq_along(scenario_order)) {
    data <- scenario_curve[scenario_curve$scenario == scenario_order[index], ]
    data <- data[order(data$completed_participants), ]
    lines(
      data$completed_participants,
      data$power_monotone,
      col = scenario_colors[index],
      lwd = 2.2
    )
    visible <- data$completed_participants <= 1200
    points(
      data$completed_participants[visible],
      data$power[visible],
      col = scenario_colors[index],
      pch = 16,
      cex = 0.45
    )
  }
  text(325, 0.08, "Current N = 300", srt = 90, col = "grey35", cex = 0.78)
  text(1165, 0.825, "80%", col = "grey35", cex = 0.78)
  legend(
    "bottomright",
    legend = c(
      "Higher eligibility / lower ICC",
      "Central",
      "Higher persistence reversal",
      "Lower eligibility / higher ICC"
    ),
    col = scenario_colors,
    lwd = 2.2,
    bty = "n",
    cex = 0.72
  )
}

project_dir <- dirname(output_dir)
figure_pdf <- file.path(project_dir, "figures", "power_simulation_curves.pdf")
figure_png <- file.path(output_dir, "power_simulation_curves.png")
pdf(figure_pdf, width = 10.5, height = 5.0, useDingbats = FALSE)
draw_power_figure()
dev.off()
png(figure_png, width = 2520, height = 1200, res = 240)
draw_power_figure()
dev.off()

cat("Power results written to", output_file, "\n")
cat("Interpolated 80% MDEs written to", mde_file, "\n\n")
print(mde, row.names = FALSE)
cat("\nSample-size thresholds written to", threshold_file, "\n\n")
print(rbind(effect_thresholds, scenario_thresholds), row.names = FALSE)
cat("\nPower figure written to", figure_pdf, "\n")
