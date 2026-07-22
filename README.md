# Undemocratic Reversals Laboratory Experiment

This repository contains the proposal and oTree implementation for a two-wave interactive laboratory panel on institutional capacity and executive delegation.

## Design

Participants attend two synchronized 55--65 minute visits separated by seven days. Each wave contains ten paid rounds of a five-person institutional-choice public-good game. In every round, participants cast a secret ballot between a constrained collective procedure and executive delegation. The majority-selected procedure binds the group and determines who controls contributions, how the public account is produced, and whether an executive can make a private transfer.

Participants are anonymously rematched before every round within stable ten-person pools. All pools face low ordinary institutional capacity in Wave 1. In Wave 2, pools are assigned to recovered ordinary capacity or continued low capacity; executive technology and discretion remain unchanged. Wave 2 begins with memory measures and an expectation about recovery. Participants then learn how effectively the collective procedure is working from the returns produced during the rounds.

## Incentives

- Each round begins with 20 points per participant.
- One randomly selected game round from each wave is paid.
- Completing Wave 2 adds 25 points.
- The exchange rate is EUR 0.20 per point, plus a EUR 10 participation payment.

## oTree sessions

Run oTree from `otree_project/`. The production configuration is `panel_lab_experiment`; it enforces the two scheduled dates. The `panel_lab_demo` configuration disables date gates for a full ten-participant test. Production session sizes should be multiples of ten so that each treatment-matched pool can be divided into two complete five-person groups in every round.

For testing alone, use `panel_lab_solo_recovery` or `panel_lab_solo_persistence`. Each creates one human participant and four simulated citizens. On every voting page, a test-only control sets how many simulated citizens vote for the leader; the human ballot is then added to produce the displayed five-vote result. Simulated citizens contribute 10 points each when the collective procedure wins, and the human participant serves as leader when delegation wins.

The active app sequence is:

1. `intro_consent`
2. `wave1_threat`
3. `wave2_discontinuity`

Before creating a production session, confirm the dates in `settings.py`, set `OTREE_ADMIN_PASSWORD`, and use the secure room URLs backed by `_rooms/panel_lab_labels.txt`. The label file contains 400 participant codes (`p001`--`p400`).
