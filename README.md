# Undemocratic Reversals Laboratory Experiment

This repository contains the proposal and oTree implementation for a two-wave interactive laboratory panel on institutional capacity and executive delegation.

## Design

Participants attend two synchronized 55--65 minute visits separated by seven days. Each wave contains ten paid rounds of a five-person institutional-choice public-good game. In every round, participants cast a secret ballot between a constrained collective procedure and executive delegation. The majority-selected procedure binds the group and determines who controls contributions, how the public account is produced, and whether an executive can make a private transfer.

Participants are anonymously rematched before every round within stable ten-person pools. All pools face low ordinary institutional capacity in Wave 1. In Wave 2, pools are assigned to recovered ordinary capacity or continued low capacity; executive technology and discretion remain unchanged. Wave 2 begins with pre-information memory measures and a second costly information board.

## Incentives

- Each round begins with 20 points per participant.
- One randomly selected game round from each wave is paid.
- Participants receive a 24-point information endowment across the panel; opening a report costs 4 points and unspent points are paid.
- Completing Wave 2 adds 25 points, and the scored recovery belief adds 0--5 points.
- The exchange rate is EUR 0.20 per point, plus a EUR 10 participation payment.

## oTree sessions

Run oTree from `otree_project/`. The production configuration is `panel_lab_experiment`; it enforces the two scheduled dates. The `panel_lab_demo` configuration disables date gates for testing. Production session sizes should be multiples of ten so that each treatment-matched pool can be divided into two complete five-person groups in every round.

The active app sequence is:

1. `intro_consent`
2. `wave1_threat`
3. `wave2_discontinuity`

The legacy `wave3_election` directory is retained only to preserve project history. It is not included in any active session configuration and cannot be reached by participants.

Before creating a production session, confirm the dates in `settings.py`, set `OTREE_ADMIN_PASSWORD`, and use the secure room URLs backed by `_rooms/panel_lab_labels.txt`. The label file contains 400 participant codes (`p001`--`p400`).
