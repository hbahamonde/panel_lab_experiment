# Undemocratic Reversals Laboratory Experiment

This repository contains the proposal and oTree implementation for a one-session interactive laboratory experiment on institutional capacity, leader discretion, and democratic reversal.

## Design

Participants attend one synchronized 75--90 minute laboratory session containing two ten-round blocks of a five-person institutional-choice public-good game. In every round, participants cast a secret ballot between letting citizens decide individually and letting one leader decide for everyone. The majority-selected method binds the group and determines who controls the points placed in a public-services fund and whether the leader can move fund points to a personal account.

Participants are anonymously rematched before every round within stable ten-person pools. All pools face low citizen-led capacity in Block 1. Before Block 2, pools are assigned to recovered citizen-led capacity or continued low capacity, and the new multiplier is explicitly disclosed. The leader-led method remains productive and equally discretionary in both blocks. This within-session change preserves repeated individual choices and a directly observed reversal while eliminating a second visit and its associated attrition.

## Incentives

- Each round begins with 20 points per participant.
- One randomly selected game round from each block is paid.
- The exchange rate is EUR 0.20 per point, plus a EUR 10 participation payment.

## oTree sessions

Run oTree from `otree_project/`. The production configuration is `panel_lab_experiment`. The `panel_lab_demo` configuration provides a full ten-participant test with optional survey responses. Production session sizes should be multiples of ten so that each treatment-matched pool can be divided into two complete five-person groups in every round.

For testing alone, use `panel_lab_solo_recovery` or `panel_lab_solo_persistence`. Each creates one human participant and four simulated citizens. On every voting page, a test-only control sets how many simulated citizens vote for the leader; the human ballot is then added to produce the displayed five-vote result. Simulated citizens put 10 points each in the public-services fund when Citizens decide wins, and the human participant serves as leader when A leader decides wins.

The active app sequence is:

1. `intro_consent`
2. `wave1_threat`
3. `wave2_discontinuity`

For a quick end-to-end test without advancing four additional browser windows, create either solo configuration. The software supplies four simulated citizens in each round, and a testing control on the ballot page lets the tester set how many of them vote for the leader. This makes both majority outcomes directly testable from one browser.

Before creating a production session, set `OTREE_ADMIN_PASSWORD` and use the secure room URLs backed by `_rooms/panel_lab_labels.txt`. The label file contains 400 participant codes (`p001`--`p400`).
