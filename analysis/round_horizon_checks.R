#!/usr/bin/env Rscript

# Exact monetary benchmark, compensation arithmetic, and sensitivity to the
# number of post-treatment observations. No behavioral trajectory is estimated.
# Run from any directory with Rscript analysis/round_horizon_checks.R.

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

# Under selfish monetary preferences the voluntary fallback contributes zero,
# because its marginal private return is 0.30 or 0.50, below the unit cost.
# Nonleaders approve when the implemented proposal strictly beats that fallback.
# Indifference is also accepted below, but does not affect the strict optimum.
proposal_set <- expand.grid(allocation = 0:20, transfer = 0:20)
proposal_set <- proposal_set[
  proposal_set$transfer <= 5 * proposal_set$allocation,
]
benchmark <- do.call(rbind, lapply(
  list(
    list(rule = "Automatic implementation", environment = "Either", rate = 2.5,
         approval = FALSE),
    list(rule = "Approval required", environment = "Crisis/persistence", rate = 1.5,
         approval = TRUE),
    list(rule = "Approval required", environment = "Recovery", rate = 2.5,
         approval = TRUE)
  ),
  function(condition) {
    proposals <- proposal_set
    proposals$nonleader <- 20 - proposals$allocation +
      condition$rate / 5 * (5 * proposals$allocation - proposals$transfer)
    proposals$leader <- proposals$nonleader + proposals$transfer
    if (condition$approval) {
      proposals$implemented <- proposals$nonleader >= 20
      proposals$leader[!proposals$implemented] <- 20
      proposals$nonleader[!proposals$implemented] <- 20
    }
    best <- proposals[which.max(proposals$leader), ]
    stopifnot(best$allocation == 20, best$transfer == 20)
    data.frame(
      rule = condition$rule,
      environment = condition$environment,
      multiplier = condition$rate,
      optimal_equal_allocation = best$allocation,
      optimal_transfer = best$transfer,
      leader_points = best$leader,
      nonleader_points = best$nonleader,
      expected_points_before_leader_draw =
        (best$leader + 4 * best$nonleader) / 5,
      nonleader_gain_over_selfish_fallback = best$nonleader - 20
    )
  }
))
stopifnot(identical(benchmark$leader_points, c(60, 44, 60)))
stopifnot(identical(benchmark$nonleader_points, c(40, 24, 40)))
write.csv(benchmark, file.path(output_dir, "institutional_benchmarks.csv"),
          row.names = FALSE)

# The benchmark specifies optimal proposals conditional on implementation and
# payoff-responsive ratification. It does not establish a unique Nash
# equilibrium of the institutional voting game. After recovery both procedures
# implement the same proposal and yield equal expected monetary payoffs under
# these assumptions. Approval is therefore not binding at the current cap.

conversion <- 5 / 120
budget <- data.frame(
  scenario = c("A in Block 1, D in Block 2 under persistence",
               "Selfish institution-choice benchmark, either condition",
               "Illustration: half B2 D-persistence, half B2 equal-productivity",
               "Maximum compensation"),
  participants = 300L,
  selected_block1_points = c(44, 44, 44, 60),
  selected_block2_points = c(28, 44, 36, 60),
  showup_eur = 10,
  total_per_person_eur = 10 + c(72, 88, 80, 120) * conversion
)
budget$total_eur <- budget$participants * budget$total_per_person_eur
write.csv(budget, file.path(output_dir, "compensation_benchmarks.csv"),
          row.names = FALSE)

leader_exposure <- data.frame(
  phase = c("Block 1", "Block 2", "Whole session"),
  rounds = c(10L, 5L, 15L),
  expected_leader_rounds = c(10L, 5L, 15L) / 5,
  probability_never_leader = (4 / 5)^c(10L, 5L, 15L)
)
write.csv(leader_exposure, file.path(output_dir, "leader_exposure.csv"),
          row.names = FALSE)

# Re-evaluate three useful effect sizes with the actual 10+5 endpoint label.
# The preceding number of rounds is deliberately absent from the outcome
# generator. These are probabilities conditional on assumed final-ballot rates.
endpoint_nsim <- as.integer(Sys.getenv("POWER_ENDPOINT_NSIM", "5000"))
endpoint_nperm <- as.integer(Sys.getenv("POWER_ENDPOINT_NPERM", "1999"))
set.seed(20261020L)
endpoint_power <- do.call(rbind, lapply(
  c("30 pools", "29 pools", "28 pools"),
  function(label) do.call(rbind, lapply(c(0.20, 0.25, 0.30), function(effect) {
    simulate_power(
      design = make_design(label),
      eligible_share = 0.50,
      persistence_rate = 0.20,
      effect = effect,
      outcome_icc = 0.05,
      n_sim = endpoint_nsim,
      n_perm = endpoint_nperm
    )
  }))
))
write.csv(endpoint_power, file.path(output_dir, "round5_power_check.csv"),
          row.names = FALSE)

# Assignment streams continue across sessions within a collection batch.
# Independently evaluate the limiting case of a fresh batch for every pool.
# Its first size-block slot is a fair draw, so this sensitivity check has no
# cross-session balance. The main calculations use a common study batch.
set.seed(20261021L)
batch_power <- do.call(rbind, lapply(
  c("30 pools", "29 pools", "28 pools"),
  function(label) do.call(rbind, lapply(c(0.20, 0.25, 0.30), function(effect) {
    design <- make_design(label)
    design$collection_batch <- seq_along(design$pool_size)
    design$label <- paste(label, "in separate allocation batches")
    simulate_power(
      design = design,
      eligible_share = 0.50,
      persistence_rate = 0.20,
      effect = effect,
      outcome_icc = 0.05,
      n_sim = endpoint_nsim,
      n_perm = endpoint_nperm
    )
  }))
))
write.csv(batch_power,
          file.path(output_dir, "round5_batch_power_check.csv"),
          row.names = FALSE)

# Illustration only: after each completed round, an assumed proportion a of
# the remaining gap FROM THE FIRST BLOCK-2 BALLOT to an unspecified later
# limiting preference closes. The immediate treatment effect at the first
# ballot is unrestricted. Zero here means no additional adjustment yet, not
# zero immediate treatment effect. This is a
# sensitivity analysis, not learning estimated from observations and not
# convergence to a monetary equilibrium. It applies to adjustment in either
# direction. The first ballot follows zero completed treatment rounds.
adjustment <- do.call(rbind, lapply(c(0.20, 0.50, 0.80), function(a) {
  k <- 0:9
  data.frame(
    assumed_adjustment_per_round = a,
    completed_posttreatment_rounds = k,
    block2_ballot = k + 1L,
    fraction_additional_adjustment = 1 - (1 - a)^k
  )
}))
write.csv(adjustment, file.path(output_dir, "round_horizon_sensitivity.csv"),
          row.names = FALSE)

existing_central <- read.csv(file.path(output_dir, "power_simulation_results.csv"))
existing_central <- existing_central[
  existing_central$scenario == "Central" &
    existing_central$design == "30 pools",
]
existing_central <- existing_central[order(existing_central$risk_difference), ]
existing_central$power_monotone <-
  isoreg(existing_central$risk_difference, existing_central$power)$yf

draw_horizon_figure <- function() {
  old_par <- par(mfrow = c(1, 2), mar = c(4.2, 4.2, 2.4, 0.8),
                 oma = c(0, 0, 0, 0), family = "serif", las = 1)
  on.exit(par(old_par))
  colors <- c("#D55E00", "#0072B2", "#009E73")
  plot(NA, xlim = c(1, 10), ylim = c(0, 100),
       xlab = "Block-2 ballot", ylab = "Assumed additional adjustment (%)",
       main = "(a) Additional adjustment after ballot 1", xaxt = "n")
  axis(1, at = c(1, 3, 5, 7, 10))
  abline(v = 5, col = "grey50", lty = 2)
  abline(h = 100, col = "grey80", lty = 3)
  for (i in seq_along(colors)) {
    data <- adjustment[adjustment$assumed_adjustment_per_round ==
                         c(0.20, 0.50, 0.80)[i], ]
    lines(data$block2_ballot, 100 * data$fraction_additional_adjustment,
          col = colors[i], lwd = 2.2)
    idx <- data$block2_ballot == 5
    points(data$block2_ballot[idx],
           100 * data$fraction_additional_adjustment[idx],
           col = colors[i], pch = 16, cex = 0.9)
  }
  legend("bottomright", legend = c("20% of remaining gap / round",
         "50% of remaining gap / round", "80% of remaining gap / round"),
         col = colors, lwd = 2.2, bty = "n", cex = 0.78)
  text(4.85, 35, "Final ballot", adj = 1, col = "grey35", cex = 0.8)

  plot(existing_central$risk_difference * 100, existing_central$power_monotone,
       type = "l", col = "#0072B2", lwd = 2.2,
       xlim = c(0, 35), ylim = c(0, 1),
       xlab = "Assumed recovery effect at final ballot (pp)",
       ylab = "Probability of detecting the effect",
       main = "(b) Conditional power, 300 participants")
  abline(h = 0.80, lty = 2, col = "grey50")
  selected <- endpoint_power[endpoint_power$design == "30 pools", ]
  points(selected$risk_difference * 100, selected$power, pch = 16,
         col = "#D55E00", cex = 0.85)
  legend("bottomright", legend = c("Terminal-outcome sensitivity",
         "Independent Round-5 simulation"),
         col = c("#0072B2", "#D55E00"), lty = c(1, NA),
         pch = c(NA, 16), bty = "n", cex = 0.78)
}

figure_pdf <- file.path(project_dir, "figures", "round_horizon_sensitivity.pdf")
pdf(figure_pdf, width = 10.5, height = 4.5, useDingbats = FALSE)
draw_horizon_figure()
dev.off()
png(file.path(output_dir, "round_horizon_sensitivity.png"),
    width = 2520, height = 1080, res = 240)
draw_horizon_figure()
dev.off()

cat("Exact monetary benchmark\n")
print(benchmark, row.names = FALSE)
cat("\nCompensation arithmetic\n")
print(budget, row.names = FALSE)
cat("\nLeader exposure\n")
print(leader_exposure, row.names = FALSE)
cat("\nRound-5 conditional-power check\n")
print(endpoint_power, row.names = FALSE)
cat("\nRound-5 power when every pool starts a separate allocation batch\n")
print(batch_power, row.names = FALSE)
cat("\nIllustrative adjustment at the fifth and tenth ballots\n")
print(adjustment[adjustment$block2_ballot %in% c(5, 10), ], row.names = FALSE)
cat("\nFigure:", figure_pdf, "\n")
