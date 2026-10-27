# Design calculations

The experiment has ten paid Block-1 rounds followed by five paid Block-2
rounds. The first Block-2 ballot precedes experience of the assigned
environment. The fifth follows four completed treatment rounds.

Production rosters contain 5, 10, 15, or 20 participants. They create matching
pools of `[5]`, `[10]`, `[15]`, or `[10, 10]`, respectively. Every playing
group contains five people. Five-person pools keep the same partners, and
larger pools reshuffle only their own members before each round.

Run from the project directory:

```sh
Rscript analysis/power_simulation.R
Rscript analysis/round_horizon_checks.R
Rscript analysis/mixed_pool_power.R
```

The scripts use base R and fixed seeds. `power_simulation.R` reproduces the
pool-level assignment mechanism, subgroup eligibility, a binary final-ballot
outcome, and the two-sided randomization test. Recovery and persistence occupy
two slots each in a randomly permuted block of four pools. Separate streams
are maintained for exact pool sizes 5, 10, and 15 across sessions within the
same collection batch. The simulations retain incomplete-block prefixes
rather than imposing equal arms on the pools observed so far. Every slot has
marginal recovery probability one half. It generates the power curves,
sensitivity tables, and sample-size thresholds. Its default settings use
5,000 simulated experiments and 1,999 reallocations for fixed-sample results,
and 2,500 experiments and 999 reallocations for sample-size curves. Settings
can be changed with the `POWER_NSIM`, `POWER_NPERM`, `POWER_CURVE_NSIM`, and
`POWER_CURVE_NPERM` environment variables.

`round_horizon_checks.R` enumerates every permitted allocation and transfer,
calculates conditional compensation and leader-exposure benchmarks, and
independently checks power at the fifth Block-2 ballot. Its endpoint checks
use 5,000 experiments and 1,999 reallocations by default. Change these with
`POWER_ENDPOINT_NSIM` and `POWER_ENDPOINT_NPERM` if required.

The monetary benchmark assumes selfish preferences, zero voluntary
contributions after rejection, and approval of proposals paying at least as
much as rejection. It identifies the leader's optimal implemented proposal
under these assumptions. It does not establish a unique equilibrium of the
institutional voting game. At the current 20-point transfer cap, that optimum
is approved under either multiplier. After recovery, approved proposals and
automatic implementation yield identical benchmark payoffs.

The round-horizon figure distinguishes two calculations. Its first panel
illustrates additional adjustment **from the first Block-2 ballot toward an
unspecified later limit**. The first ballot may already contain an immediate
treatment effect. Zero additional adjustment at that ballot does not imply
zero immediate effect. The assumed per-round adjustment fractions of 20%,
50%, and 80% are sensitivity scenarios, not estimates from subjects or proof
of convergence within five rounds. Adjustment can occur in either direction.

The second panel shows power conditional on an assumed treatment effect at
the final ballot. Holding final-ballot response rates, subgroup eligibility,
and clustering fixed, the number of earlier rounds does not enter this
terminal-outcome simulation. A shorter follow-up can nevertheless change the
actual final-ballot effect or its within-pool correlation. Pilot observations
are needed to inform those quantities.

The canonical sample-size curves hold pool size at ten. Each additional ten
participants adds one treatment-assignment unit, and consecutive size-block
slots need not be opposite conditions. At 300 completions, the 28-, 29-, and
30-pool configurations illustrate limited use of fifteen-person pools. They
are reference configurations rather than restrictions on the realized mix.
`round5_batch_power_check.csv` evaluates a separate allocation batch for each
pool as a sensitivity check. Reconstructing the test for collected data
requires the recorded batch, exact pool size, slot order, and allocation
blocks. Independently permuting all treatment labels would not reproduce the
design.

`mixed_pool_power.R` evaluates attendance compositions containing 5-, 10-,
and 15-person pools at 300 completed participants. It includes 0%, 10%, 20%,
and 40% of participants in five-person pools, mixed fifteen-person attendance,
and the all-five and all-fifteen bounds. The number of randomization units
can therefore range from 20 to 60. Main calculations assume 50% eligibility,
20% reversal under persistence, and intrapool outcome correlation 0.05 in
larger pools. Fixed five-person pools are evaluated at correlations 0.05,
0.10, and 0.20. These are sensitivity assumptions, not estimates or a claim
that repeated partners necessarily cooperate more. Additional checks lower
five-person eligibility to 40% or reduce their treatment effect by 25%.
The latter explicitly reports the resulting subgroup-average effect, because
it no longer equals the effect in the larger pools.

The mixed-pool script uses 5,000 experiments and 1,999 reallocations per point
by default. Change them with `POWER_MIXED_NSIM` and `POWER_MIXED_NPERM`.
`mixed_pool_power_summary.csv` reports power for 20-, 25-, and 30-percentage-
point effects, interpolated 80% minimum detectable effects, and null rejection
rates. `mixed_pool_power.pdf` displays attendance and fixed-group-correlation
sensitivity. Zero-eligible pools retain their allocation slots. Invalid
reallocations with an empty analysis arm are excluded from that experiment's
permutation denominator and recorded, rather than counted as non-rejections.
All calculations use the participant-weighted recovery-minus-persistence
reversal-rate difference in the pretreatment-defined eligible subgroup.
Pool-size-adjusted analyses and exclusion of fixed groups remain useful
sensitivity checks. The simulation does not identify the causal effect of
pool size, because attendance determines it.

For a composition with 60 participants in twelve five-person pools and 240
in twenty-four ten-person pools, simulated power is about 64% for a
20-percentage-point effect and 81% for a 25-point effect. Increasing
five-person outcome correlation from 0.05 to 0.20 gives approximately 63%
and 80%. The 80% minimum detectable effect is about 25 points. These
conditional calculations support the fallback's feasibility, not a promise
of improved precision. At the all-fifteen bound of twenty pools, corresponding
power is about 58% and 74%. Recruitment composition and the behavior of fixed
groups therefore matter. Null rejection rates across the main mixed-pool
scenarios range from 4.2% to 5.6%, with no invalid experiments or empty-arm
reallocations at the simulated sample size.

At 300 completions, ten Block-1 rounds generate 600 five-person group
decisions and five Block-2 rounds generate 300. These proposal events are
process observations, not independent treatment assignments. Independent
uniform leader selection gives each citizen two expected leader turns in
Block 1 and one in Block 2. The probability of never leading in Block 2 is
32.8%, so realized leader experience is not balanced across citizens.

Payments select one round uniformly from each block, so Block 1 and Block 2
have equal compensation weight despite their different lengths. Conditional
on the selfish institution-choice benchmark, two selected rounds yield 88
expected points, approximately EUR 13.67 total per participant and EUR 4,100
for 300 participants. This is an illustration rather than a spending forecast.
The maximum completed-participant compensation remains EUR 4,500. Shortening
the follow-up reduces the number of decisions, not the payment ceiling.
