#!/usr/bin/env Rscript

# Power conditional on attendance composition. All plans contain 300 completed
# participants. Five-person pools retain the same partners, whereas larger
# pools rematch into five-person playing groups. Stronger within-pool similarity
# and different subgroup eligibility in fixed groups are assumptions, not data.

options(stringsAsFactors = FALSE)
script_arg <- grep("^--file=", commandArgs(FALSE), value = TRUE)
script_path <- normalizePath(sub("^--file=", "", script_arg))
output_dir <- dirname(script_path)
project_dir <- dirname(output_dir)
previous_functions_only <- Sys.getenv("POWER_FUNCTIONS_ONLY", unset = NA)
Sys.setenv(POWER_FUNCTIONS_ONLY = "1")
source(file.path(output_dir, "power_simulation.R"))
if (is.na(previous_functions_only)) {
  Sys.unsetenv("POWER_FUNCTIONS_ONLY")
} else {
  Sys.setenv(POWER_FUNCTIONS_ONLY = previous_functions_only)
}

n_sim <- as.integer(Sys.getenv("POWER_MIXED_NSIM", "5000"))
n_perm <- as.integer(Sys.getenv("POWER_MIXED_NPERM", "1999"))
if (n_sim < 100L || n_perm < 199L) {
  stop("Use at least 100 experiments and 199 reallocations.")
}

plans <- data.frame(
  plan = c("Ten-person pools", "10% in five-person pools",
           "20% in five-person pools", "40% in five-person pools",
           "Five-, ten-, and fifteen-person mix", "Fifteen-heavy mix",
           "Fifteen-person pools", "Five-person pools"),
  n5 = c(0L, 6L, 12L, 24L, 12L, 6L, 0L, 60L),
  n10 = c(30L, 27L, 24L, 18L, 18L, 18L, 0L, 0L),
  n15 = c(0L, 0L, 0L, 0L, 4L, 6L, 20L, 0L)
)
plans$participants <- 5 * plans$n5 + 10 * plans$n10 + 15 * plans$n15
plans$pools <- plans$n5 + plans$n10 + plans$n15
plans$share_in_five <- 5 * plans$n5 / plans$participants
stopifnot(all(plans$participants == 300L))

make_mixed_design <- function(plan) {
  list(
    label = plan$plan,
    pool_size = c(rep(5L, plan$n5), rep(10L, plan$n10), rep(15L, plan$n15))
  )
}

# Every pool has marginal recovery probability one half. The realized prefix
# of an incomplete four-pool allocation block is kept, including AA and DD
# two-pool prefixes. These checks also cover a size represented by only one pool.
set.seed(20261022L)
allocation_checks <- do.call(rbind, lapply(c(1L, 2L, 3L, 4L, 6L), function(j) {
  assignments <- draw_assignments(20000L, rep(5L, j))
  if (j >= 4L) stopifnot(all(rowSums(assignments[, 1:4]) == 2L))
  stopifnot(max(abs(colMeans(assignments) - 0.5)) < 0.025)
  data.frame(pools_in_size_stream = j,
             minimum_recovery = min(rowSums(assignments)),
             maximum_recovery = max(rowSums(assignments)),
             mean_recovery = mean(rowSums(assignments)),
             first_slot_recovery_probability = mean(assignments[, 1L]),
             probability_all_prefix_recovery = mean(rowSums(assignments) == j))
}))
stopifnot(allocation_checks$probability_all_prefix_recovery[
  allocation_checks$pools_in_size_stream == 2L] > 0.14)
write.csv(allocation_checks,
          file.path(output_dir, "mixed_pool_allocation_checks.csv"), row.names = FALSE)

assumptions <- data.frame(
  assumption = c("Equal similarity", "Greater fixed-group similarity",
                 "Strong fixed-group similarity"),
  icc_five = c(0.05, 0.10, 0.20)
)
effect_grid <- c(0, seq(0.15, 0.35, by = 0.025))

set.seed(20261023L)
results <- list()
row_index <- 0L
for (p in seq_len(nrow(plans))) {
  plan <- plans[p, ]
  # Without five-person pools, the three history assumptions are identical.
  applicable <- if (plan$n5 == 0L) 1L else seq_len(nrow(assumptions))
  for (a in applicable) {
    assumption <- assumptions[a, ]
    for (effect in effect_grid) {
      result <- simulate_power(
        design = make_mixed_design(plan),
        eligible_share = 0.50,
        persistence_rate = 0.20,
        effect = effect,
        outcome_icc = 0.05,
        outcome_icc_five = assumption$icc_five,
        n_sim = n_sim,
        n_perm = n_perm
      )
      result$assumption <- assumption$assumption
      result$share_in_five <- plan$share_in_five
      row_index <- row_index + 1L
      results[[row_index]] <- result
    }
  }
  cat("Finished attendance plan:", plan$plan, "\n")
}
results <- do.call(rbind, results)
write.csv(results, file.path(output_dir, "mixed_pool_power.csv"), row.names = FALSE)

# Eligibility and effect-size sensitivity for one plausible composition.
# Lower eligibility is not asserted to follow from fixed partners. Likewise,
# the 25% weaker effect scenario illustrates an unobserved behavioral change.
stress_plan <- plans[plans$plan == "20% in five-person pools", ]
stress_definitions <- data.frame(
  assumption = c("Lower fixed-group eligibility", "Weaker fixed-group effect"),
  eligible_five = c(0.40, 0.50),
  effect_multiplier_five = c(1, 0.75)
)
stress <- do.call(rbind, lapply(seq_len(nrow(stress_definitions)), function(s) {
  setting <- stress_definitions[s, ]
  do.call(rbind, lapply(c(0, 0.20, 0.25, 0.30), function(effect) {
    result <- simulate_power(
      design = make_mixed_design(stress_plan),
      eligible_share = 0.50,
      eligible_share_five = setting$eligible_five,
      persistence_rate = 0.20,
      effect = effect,
      effect_five = effect * setting$effect_multiplier_five,
      outcome_icc = 0.05,
      outcome_icc_five = 0.20,
      eligibility_icc_five = 0.10,
      n_sim = n_sim,
      n_perm = n_perm
    )
    result$assumption <- setting$assumption
    result$share_in_five <- stress_plan$share_in_five
    eligible_five <- 5 * stress_plan$n5 * setting$eligible_five
    eligible_other <- (300 - 5 * stress_plan$n5) * 0.50
    result$expected_subgroup_average_effect <- (
      eligible_five * result$risk_difference_five + eligible_other * effect
    ) / (eligible_five + eligible_other)
    result
  }))
}))
write.csv(stress, file.path(output_dir, "mixed_pool_stress_checks.csv"),
          row.names = FALSE)

interpolated_mde <- function(data, target = 0.80) {
  data <- data[order(data$risk_difference), ]
  monotone <- isoreg(data$risk_difference, data$power)$yf
  hi <- which(monotone >= target)[1L]
  if (is.na(hi)) return(NA_real_)
  if (hi == 1L) return(data$risk_difference[hi])
  lo <- hi - 1L
  data$risk_difference[lo] + (target - monotone[lo]) *
    diff(data$risk_difference[c(lo, hi)]) / diff(monotone[c(lo, hi)])
}

grouped <- split(results, interaction(results$design, results$assumption,
                                     drop = TRUE))
summary <- do.call(rbind, lapply(grouped, function(data) {
  selected_power <- function(effect) data$power[
    abs(data$risk_difference - effect) < 1e-8
  ]
  data.frame(plan = data$design[1L], assumption = data$assumption[1L],
             participants = 300L, pools = data$pools[1L],
             n5 = data$five_person_pools[1L], n10 = data$ten_person_pools[1L],
             n15 = data$fifteen_person_pools[1L],
             share_in_five = data$share_in_five[1L],
             outcome_icc_five = data$outcome_icc_five[1L],
             type1_error = selected_power(0),
             power_20pp = selected_power(0.20),
             power_25pp = selected_power(0.25),
             power_30pp = selected_power(0.30),
             mde_80 = interpolated_mde(data),
             simulations = n_sim, random_assignments = n_perm)
}))
rownames(summary) <- NULL
write.csv(summary, file.path(output_dir, "mixed_pool_power_summary.csv"),
          row.names = FALSE)
write.csv(plans, file.path(output_dir, "mixed_pool_plans.csv"), row.names = FALSE)

draw_mixed_figure <- function() {
  old_par <- par(mfrow = c(1, 2), mar = c(4.5, 4.4, 2.9, 0.8),
                 oma = c(0.2, 0.1, 0, 0), family = "serif", las = 1)
  on.exit(par(old_par))
  colors <- c("#0072B2", "#E69F00", "#D55E00")
  main_plans <- plans$plan[1:4]
  plot(NA, xlim = c(0, 40), ylim = c(0.45, 0.85),
       xlab = "Participants in five-person pools (%)",
       ylab = "Probability of detecting the effect",
       main = "(a) Attendance mix, 20 pp effect", xaxt = "n")
  axis(1, at = c(0, 10, 20, 40))
  abline(h = 0.80, lty = 2, col = "grey50")
  for (i in seq_len(nrow(assumptions))) {
    data <- summary[summary$plan %in% main_plans &
                      (summary$assumption == assumptions$assumption[i] |
                         summary$plan == "Ten-person pools"), ]
    data <- data[order(data$share_in_five), ]
    lines(100 * data$share_in_five, data$power_20pp,
          col = colors[i], lwd = 2.2, type = "b", pch = c(16, 17, 15)[i],
          cex = 0.8)
  }
  legend("bottomleft", legend = c("Five-person ICC 0.05", "Five-person ICC 0.10",
                               "Five-person ICC 0.20"), col = colors,
         lwd = 2.2, pch = c(16, 17, 15), bty = "n", cex = 0.77)
  text(39, 0.815, "80%", adj = 1, col = "grey40", cex = 0.8)

  curves <- list(
    list(plan = "Ten-person pools", assumption = "Equal similarity",
         label = "30 ten-person pools"),
    list(plan = "20% in five-person pools", assumption = "Equal similarity",
         label = "20% in five-person pools, ICC 0.05"),
    list(plan = "20% in five-person pools", assumption = "Strong fixed-group similarity",
         label = "20% in five-person pools, ICC 0.20")
  )
  plot(NA, xlim = c(15, 35), ylim = c(0, 1),
       xlab = "Assumed final-ballot recovery effect (pp)",
       ylab = "Probability of detecting the effect",
       main = "(b) Effect size, 300 participants")
  abline(h = 0.80, lty = 2, col = "grey50")
  for (i in seq_along(curves)) {
    curve <- curves[[i]]
    data <- results[results$design == curve$plan &
                      results$assumption == curve$assumption &
                      results$risk_difference > 0, ]
    data <- data[order(data$risk_difference), ]
    lines(100 * data$risk_difference,
          isoreg(data$risk_difference, data$power)$yf,
          col = colors[i], lwd = 2.2)
    points(100 * data$risk_difference, data$power,
           col = colors[i], pch = c(16, 17, 15)[i], cex = 0.65)
  }
  legend("bottomright", legend = vapply(curves, `[[`, "", "label"),
         col = colors, lwd = 2.2, bty = "n", cex = 0.72)
}

figure <- file.path(project_dir, "figures", "mixed_pool_power.pdf")
pdf(figure, width = 10.5, height = 4.8, useDingbats = FALSE)
draw_mixed_figure()
dev.off()
png(file.path(output_dir, "mixed_pool_power.png"),
    width = 2520, height = 1152, res = 240)
draw_mixed_figure()
dev.off()

cat("\nMixed-pool power and null rejection checks\n")
print(summary, row.names = FALSE)
cat("\nEligibility and effect sensitivity\n")
print(stress, row.names = FALSE)
cat("\nFigure:", figure, "\n")
