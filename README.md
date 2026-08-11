# Undemocratic Reversals Laboratory Experiment

This repository contains the proposal and oTree implementation for a one-session interactive laboratory experiment on crisis, public-good provision, weakly constrained authority, and democratic reversal.

## Design

Participants complete two ten-round blocks of a five-person institutional-choice public-good game. In every round, each participant chooses between **Each person chooses** and **One person chooses for the group**. The option selected by at least three group members determines who controls allocations to a public-services fund and whether the selected decision-maker may move fund points to their own payoff.

Participants are anonymously rematched before every round within stable ten-person pools. In Block 1, each fund point creates 1.50 group points when each person chooses and 2.50 when one person chooses for the group. Before Block 2, pools are randomized to recovery or persistence. Recovery raises the first rate to 2.50; persistence leaves it at 1.50. The one-person rule remains unchanged.

Each round begins with 20 points per participant. One randomly selected round from each block is paid at EUR 0.20 per point, in addition to a EUR 10 participation payment.

## Start a clean development server

On macOS, double-click `start_otree_dev.command` in Finder. The launcher:

1. resets the local oTree database without prompting;
2. starts the development server on port 8000; and
3. opens `http://localhost:8000` in the default browser.

Every launch erases local development sessions and responses. Keep the Terminal window open while testing and press Control-C to stop the server.

## oTree configurations

The production configuration is `panel_lab_experiment`. Production session sizes must be multiples of ten; sessions containing an even number of ten-person pools allow every pool to be paired for treatment assignment.

The `panel_lab_demo` configuration runs a complete ten-participant test while allowing survey fields to be skipped. For testing alone, use `panel_lab_solo_recovery` or `panel_lab_solo_persistence`. These configurations create one human participant plus four simulated group members. A testing control on each institutional-choice page sets how many simulated members select **One person chooses for the group**, allowing both majority outcomes to be tested in one browser.

The active app sequence is:

1. `intro_consent`
2. `block1_crisis`
3. `block2_reversal`

Before a live session, set `OTREE_ADMIN_PASSWORD` and use the secure room URLs backed by `_rooms/panel_lab_labels.txt`. The label file contains 400 participant codes (`p001`--`p400`).
