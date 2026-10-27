# Undemocratic Reversals Laboratory Experiment

This repository contains the proposal and oTree implementation for a one-session interactive laboratory experiment on crisis, public-good provision, weakly constrained authority, and democratic reversal.

## Design

Participants complete 10 rounds in Block 1 followed by five rounds in Block 2 of a five-person institutional-choice public-good game, for 15 paid rounds in one session. In every round, they vote between **Group approval required** and **Decision takes effect directly**. The software then selects one citizen to propose an equal fund allocation and any personal transfer. Under the first method, three of the other four citizens must approve; rejection returns the group to voluntary contributions. Under the second, the proposal is implemented without an approval vote.

Participants remain in stable matching pools of 5, 10, or 15. A five-person session keeps the same five together throughout. Larger pools are anonymously reshuffled into five-person groups before every round. Rosters of 5, 10, 15, and 20 form pools of [5], [10], [15], and [10, 10], respectively. In Block 1, all pools face strained public-service conditions: each fund point creates 1.50 group points when approval is required and 2.50 when the proposal takes effect directly. Before Block 2, pools are randomized to recovery or persistence. Recovery jointly reports improved public-service conditions and raises the approval-required rate to 2.50; persistence keeps the crisis and 1.50 rate. The automatic procedure remains unchanged.

The recovery description and rate change form one structural package: the text states that public-service conditions improved, while the higher approval-required rate makes that improvement consequential inside the game. Reversal is measured from individual ballots: a supporter of direct implementation in Block 1, Round 10 later votes to restore group approval. Immediate reversal uses Block 2, Round 1; final reversal uses Block 2, Round 5, after four completed rounds in the assigned condition. The last-three-round summary uses Block-1 Rounds 8–10 and Block-2 Rounds 3–5. Whether the group actually adopts the approval rule is recorded separately.

Each round begins with 20 points per participant. One uniformly selected round out of 10 in Block 1 and one out of five in Block 2 determine a performance bonus capped at EUR 5, in addition to a EUR 10 participation payment. The selected-round points convert at 24 points = EUR 1. The two blocks carry equal payment weight. The maximum total is EUR 15 per participant, or EUR 4,500 for 300 completed participants. Payments depend on the two selected rounds rather than the sum across all rounds.

Strategic choice pages display a 90-second countdown and remind participants to choose an answer and click Next. At zero, the page stays open. The software records response time and flags delays, and the researcher or trained research assistant can help participants continue. It never generates a ballot or allocation.

## Interface language and English reference

The participant interface is in Finnish. Variable names, stored response codes,
analysis scripts, and researcher-facing configuration names remain in English.
The paper and its English screenshots also remain in English.

The final English interface and accompanying paper are preserved by the Git tag
[`english-final-2026-10-27`](https://github.com/hbahamonde/panel_lab_experiment/tree/english-final-2026-10-27).
This is a complete reference version, not a second project folder. Changing
`LANGUAGE_CODE` alone does not restore the English text. Use the tagged version
to inspect the original wording without changing a live session.

The translation preserves question order and scales, response codes, matching,
randomization, payoff rules, and payment exports. Decimal commas are a display
convention only. Before lab use, a Finnish-speaking researcher should review the
consent, instructions, both condition descriptions, questionnaire wording and
scale anchors, feedback form, and debrief against the English reference.
Set the laboratory browser's interface language to Finnish. Native number-input
validation prompts follow the browser's interface language, while oTree's
server-side validation messages use Finnish.

| English reference | Finnish participant label | Stored response code |
| --- | --- | --- |
| Group approval required | Ryhmän hyväksyntä vaaditaan | `approval` |
| Decision takes effect directly | Päätös tulee voimaan suoraan | `automatic` |
| Approve the proposal | Hyväksyn ehdotuksen | `approve` |
| Reject the proposal | Hylkään ehdotuksen | `reject` |
| Next | Seuraava | No response code |
| Selected person | Valittu henkilö | No response code |
| Public-services fund | Julkisten palvelujen rahasto | No response code |
| Block / round | Osio / kierros | Existing numeric block and round fields |

The two method badges use **R** and **P**, the initials of the Finnish labels.
The paper's research notation remains **D** for required approval and **A** for
direct implementation.

## Browser-testing prototype

The public prototype is at <https://panel-lab-experiment.onrender.com>.
For testing alone, use either direct link:

- [Conditions improve](https://panel-lab-experiment.onrender.com/demo/panel_lab_solo_recovery)
- [Conditions remain unchanged](https://panel-lab-experiment.onrender.com/demo/panel_lab_solo_persistence)

Each creates a separate demonstration with one tester and four simulated
citizens, so there is no need to advance other participants. Use dummy answers
only. Render is for technical browser testing, not research data collection or
the laboratory pre-test. Test data are disposable and may disappear on restarts
or redeployments. Research sessions and their data use the UTU server.

## Start a clean development server

On macOS, double-click `start_otree_dev.command` in Finder. The launcher:

1. resets the local oTree database without prompting;
2. starts the development server on port 8000; and
3. opens `http://localhost:8000` in the default browser.

Every launch erases local development sessions and responses. Keep the Terminal window open while testing and press Control-C to stop the server.
The launcher refuses to reset a database when `DATABASE_URL` is set and forces the separate development allocation namespace.

## oTree configurations

The production configuration is `panel_lab_experiment`. After the consenting roster is known, create the oTree session with exactly 5, 10, 15, or 20 participants. These rosters form one five-person pool, one ten-person pool, one fifteen-person pool, or two ten-person pools, respectively. Five-person pools keep their membership. Larger pools are reshuffled into groups of five every round. Start a fresh session for this protocol rather than continuing sessions created with earlier settings.

### Treatment allocation and its audit file

After everyone completes Block 1, treatment is drawn from independently shuffled four-pool randomization sets within each exact pool size (5, 10, and 15). Each complete set contains two recovery and two persistence pools. Incomplete sets can differ by up to two pools. All production cohorts use the same persistent study allocation namespace, `reslide_2026`, unless a different study-wide value is set with `TREATMENT_ALLOCATION_NAMESPACE` before collection. Do not change that value between sessions. Two ten-person pools in one session follow the same size-10 sequence and need not receive opposite assignments. Treatment does not depend on Block-1 choices.

The ledger commits each assignment once, keyed by the unique matching-pool code. Reloading the page or restarting the server reuses it. It is protected against simultaneous allocation requests. Demos use a separate `development` namespace. Use a separate namespace and a disposable database when running automated production-configuration tests.

On PostgreSQL, the ledger is kept in the study database specified by `DATABASE_URL`. On local SQLite installations, it is kept separately in `otree_project/treatment_allocation.sqlite3`, or the explicit path supplied by `TREATMENT_ALLOCATION_DB`. Keep and back up this file together with the oTree research database throughout collection. Resetting the oTree development database does not reset the allocation ledger. Do not remove or replace the production ledger during collection.

The standard oTree export retains pool size, pool UID, and randomization-set number. The full allocation metadata are also stored in participant/session variables. Export the consumed-only allocation audit separately from payment records:

```sh
../.venv/bin/python treatment_allocation.py export --namespace reslide_2026
```

The CSV identifies pool size, sequence position within that size, randomization-set number and position, assigned condition, and the unique randomization-set ID. Join it to research data by matching-pool UID. Never merge it with named payment receipts. It does not reveal unused assignments. Randomization inference must recreate two-of-four assignments separately within each size-specific set, including the appropriate marginal distribution for an incomplete set. The analysis accounts for pool size and, where estimable, checks results excluding fixed five-person pools.

Local allocation tests cover concurrent requests, restarts, and complete sessions using SQLite. Before collection on a PostgreSQL host, run the opt-in allocation integration test against a separate test database using `ALLOCATION_TEST_POSTGRES_URL`, then rehearse a complete session on the UTU setup. Do not use a research database for integration tests or change the production allocation namespace between cohorts.

The `panel_lab_demo` configuration runs a complete ten-participant test while allowing survey fields to be skipped. For testing alone, use `panel_lab_solo_recovery` or `panel_lab_solo_persistence`. These configurations create one human participant plus four simulated citizens. Testing controls set their method and approval ballots, allowing automatic implementation, approval, and rejection/fallback paths to be tested in one browser.

The active app sequence is:

1. `intro_consent`
2. `block1_crisis`
3. `block2_reversal`

Before a live session, set `OTREE_ADMIN_PASSWORD` and a distinct, private
`OTREE_SECRET_KEY`. The hard-coded key is a development fallback, not a live-study
credential. Use the secure room URLs backed by `_rooms/panel_lab_labels.txt`. The
label file provides sufficient room capacity for the planned 300 completed
participants and technical testing.

The ethics packet identifies protocol amendments separately from the favorable
statement for the submitted study. Coauthor agreement does not replace any
applicable ethics amendment. Before collecting research data, complete the UTU
server rehearsal, verify payment exports and backups, and check that proxy logging
is disabled for anonymous feedback.

## Optional feedback in the first session

The first ten-person session can offer six optional questions after all outcome and background questions and before the debriefing and payment screen. The questions cover instructions, the distinction between the methods, payment clarity, screen difficulties, improvements, and participants' understanding of the study's purpose. The debriefing remains part of every session.

Set the server environment variable `PRETEST_FEEDBACK_ENABLED=1` before starting the server and creating this ten-person session. For a local solo rehearsal, start the development launcher with the same variable and use a solo configuration. For all subsequent sessions, remove the variable or set it to `0` and restart the server. Feedback is off by default. No changes to the questions or app sequence are needed to switch it off.
If fewer than ten arrive for the intended pre-test, disable this option before creating a five-person session. The optional feedback protocol itself requires ten participants.

Use the supplied server entry point so the separate feedback form is available:

```sh
../.venv/bin/python study_server.py prodserver1of2
```

The standard worker command remains `otree prodserver2of2`. The supplied `Procfile` and development launcher use the feedback-compatible entry point. The feedback form is at the same common `/pilot-feedback` address for everyone. The invitation sends no participant code or referrer and does not track whether a participant opens or completes the form.

Feedback is stored separately from oTree participant records. The three rating questions are pooled as counts, and the three written questions are stored as independent shuffled lists. Answers are not linked across questions. No study or session codes, payment details, IP addresses, timestamps, or submission sequence are stored with feedback. All items are optional and have no payment consequences. Participants are asked not to include names or identifying details.

The server disables request access logs. Before using feedback at UTU, configure its reverse proxy and any monitoring service not to log `/pilot-feedback` requests or bodies. Check this during the technical rehearsal. Do not add analytics to the form. Export the pooled feedback from the server with:

```sh
../.venv/bin/python anonymous_feedback.py export
```

Review pooled feedback only after the session. The feedback export withholds answers until at least five forms have been submitted. It is not included in oTree research or payment exports. A local development database reset does not erase the separate feedback store. Use a disposable project copy when rehearsing with dummy feedback. Any substantive protocol changes suggested by the pre-test need review and a prespecified decision about the pre-test observations before further collection.
