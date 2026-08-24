# Undemocratic Reversals Laboratory Experiment

This repository contains the proposal and oTree implementation for a one-session interactive laboratory experiment on crisis, public-good provision, weakly constrained authority, and democratic reversal.

## Design

Participants complete two ten-round blocks of a five-person institutional-choice public-good game. In every round, they vote between **Group approval required** and **Decision takes effect directly**. The software then selects one citizen to propose an equal fund allocation and any personal transfer. Under the first method, three of the other four citizens must approve; rejection returns the group to voluntary contributions. Under the second, the proposal is implemented without an approval vote.

Participants are anonymously rematched before every round within stable ten-person pools. In Block 1, all pools face strained public-service conditions: each fund point creates 1.50 group points when approval is required and 2.50 when the proposal takes effect directly. Before Block 2, pools are randomized to recovery or persistence. Recovery jointly reports improved public-service conditions and raises the approval-required rate to 2.50; persistence keeps the crisis and 1.50 rate. The automatic procedure remains unchanged.

The recovery description and rate change form one structural package: the text states that public-service conditions improved, while the higher approval-required rate makes that improvement consequential inside the game. Reversal is measured from individual ballots: a previous supporter of direct implementation later votes to restore group approval. Whether the group actually adopts that rule is recorded separately.

Each round begins with 20 points per participant. One randomly selected round from each block is paid at EUR 0.20 per point, in addition to a EUR 10 participation payment.

Strategic choice pages do not advance automatically and the software never generates a ballot or allocation. It records response time and flags decisions that exceed 90 seconds so the laboratory manager can monitor the session and prompt delayed participants to complete their decisions.

## Start a clean development server

On macOS, double-click `start_otree_dev.command` in Finder. The launcher:

1. resets the local oTree database without prompting;
2. starts the development server on port 8000; and
3. opens `http://localhost:8000` in the default browser.

Every launch erases local development sessions and responses. Keep the Terminal window open while testing and press Control-C to stop the server.

## oTree configurations

The production configuration is `panel_lab_experiment`. Production session sizes must be multiples of ten; sessions containing an even number of ten-person pools allow every pool to be paired for treatment assignment.

The `panel_lab_demo` configuration runs a complete ten-participant test while allowing survey fields to be skipped. For testing alone, use `panel_lab_solo_recovery` or `panel_lab_solo_persistence`. These configurations create one human participant plus four simulated citizens. Testing controls set their method and approval ballots, allowing automatic implementation, approval, and rejection/fallback paths to be tested in one browser.

The active app sequence is:

1. `intro_consent`
2. `block1_crisis`
3. `block2_reversal`

Before a live session, set `OTREE_ADMIN_PASSWORD` and use the secure room URLs backed by `_rooms/panel_lab_labels.txt`. The label file contains 400 participant codes (`p001`--`p400`).
