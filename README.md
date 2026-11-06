# Lab implementation

One laboratory session of about 60 minutes, with 10 rounds in Block 1 and five
in Block 2. Participant screens are in Finnish. Variable names remain in English.
Keep the whole `otree_project/` folder together.

## 1. Prepare the UTU server

Use the UTU server for the laboratory pretest and data collection. Install
`otree_project/requirements.txt` in the lab's Python environment. Set private
`OTREE_ADMIN_PASSWORD` and `OTREE_SECRET_KEY` values. Configure persistent
storage with IT, using `DATABASE_URL` for PostgreSQL. Do not use the development
secret key for collection.

Set `OTREE_PRODUCTION=1` and `OTREE_AUTH_LEVEL=STUDY` on UTU to hide debug
panels and require administrator login.

From `otree_project/`, run these as two separate processes, as specified in
`Procfile`:

```sh
python study_server.py prodserver1of2
otree prodserver2of2
```

Rehearse the full session on UTU using a separate test database and
`TREATMENT_ALLOCATION_NAMESPACE=development`. Restore the study database and
namespace before collection. Check database compatibility, payment exports,
backups, protocol approval and Finnish wording. Use Finnish-language browsers
and secure room links configured through `_rooms/panel_lab_labels.txt`.

## 2. Create the session

Confirm attendance, then create a new session using **`panel_lab_experiment`**.

| Participants | Matching pools | Five-person groups per round |
| --- | --- | --- |
| 5 | One pool of 5 | 1 |
| 10 | One pool of 10 | 2 |
| 15 | One pool of 15 | 3 |
| 20 | Two pools of 10 | 4 |

For other attendance numbers, use the largest listed roster that does not exceed
attendance. Fewer than five cannot start. Do not add or replace participants
after paid play begins.

Five-person pools stay together. Larger pools reshuffle before each round.
The software handles leader selection and assigns recovery or persistence
after Block 1. Everyone in a pool receives the same condition. Do not assign
conditions manually or redraw them to balance an individual session.

## 3. During the session

Each round starts with a vote. Three of the five votes select the method.
The software then randomly selects a person to propose an allocation and
personal transfer. When approval is required, at least three of the other four
must approve. A 2–2 tie rejects the proposal, and everyone then chooses their
own fund allocation. Under direct implementation, the proposal goes ahead
without an approval vote.

The 90-second countdown is a reminder, not a deadline. It never submits or
chooses an answer. The researcher or trained assistant monitors delays and
helps participants continue without deciding for them.

## 4. Payments and exports

Participants receive **€10 plus a bonus of up to €5**. The software randomly
selects one paying round from each block. Their combined points convert at
**24 points = €1**.

Use oTree's **`block2_reversal` custom export** for payments. It contains only
`participant_code` and `total_payment_eur`. The participant shows their code to
the person making payment. Keep named receipts separate, with no study code
on the receipt. Export research responses separately.

## 5. Feedback in the first pretest

For the first **ten-person** pretest, set `PRETEST_FEEDBACK_ENABLED=1` before
starting the server and creating the session. This adds six optional feedback
questions at the end. If fewer than ten can start, disable this option first.

For later sessions, remove the variable or set it to `0`, then restart the
server. Feedback is off by default.

The feedback form uses the shared `/pilot-feedback` address and is separate
from participant records. Disable proxy and monitoring logs for its requests
and bodies, and do not add analytics. Review feedback only after the session.
From `otree_project/`, export it with:

```sh
python anonymous_feedback.py export
```

Answers are withheld until at least five forms have been submitted.

## 6. Preserve the data and treatment ledger

Keep the same `TREATMENT_ALLOCATION_NAMESPACE` throughout collection.
The default is `reslide_2026`. Never reset the research database or allocation
ledger between sessions.

With PostgreSQL, the ledger is in `DATABASE_URL`. With local SQLite, back up
`treatment_allocation.sqlite3`, `db.sqlite3`, and, if present,
`pilot_feedback.sqlite3`. Export the allocation audit separately:

```sh
python treatment_allocation.py export --namespace reslide_2026
```

Use the actual namespace if IT configured a different study-wide value.

## 7. Technical testing only

[Open the browser test menu](https://panel-lab-experiment.onrender.com).
Choose either **Testaa yksin** option, then click **P1**. Four simulated
citizens let one reviewer try the game alone. `panel_lab_demo` is the
ten-person testing configuration. Never use these configurations for collection.

Use dummy answers on Render. Its test data are disposable. Do not include
`local_data/` or existing databases in the code handoff.

**The macOS `start_otree_dev.command` launcher deletes its working local
database every time. Use it only for development, never data collection.**
