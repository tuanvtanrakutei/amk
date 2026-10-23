---
name: review-queue
description: "Write the project's review queue - one page of everything that waits on a person: open decisions, unacknowledged errata, plan rows nobody decided, unsigned manual tests, screens waiting for acceptance, issue rows that need a decision, asks of other teams not yet delivered, with due dates. Writes docs/Review_Queue.md and docs/review_queue.json and nothing else. Trigger when the user or an owner asks what needs them, what is waiting on a person, what to decide today, or wants the queue refreshed. Examples: \"/ak:review-queue\", \"what is waiting on me\", \"what needs a decision today\", \"refresh the review queue\"."
---

# Review Queue

Agents maintain the phases and the modernize documents; people review and decide. This skill
writes the one page that says what a person has to do. It decides nothing and answers nothing.

## Run it

From the modernize repository:

```bash
python "${CLAUDE_PLUGIN_ROOT}/modernize/scripts/review_queue.py" --repo .
```

It finds the docs folder (`docs`, or the one folder holding `PROJECT_CONFIG.md`; `--docs-dir`
overrides) and the investigation workspace (`--workspace`, else `AK_RUN_DIR`, else the repo's
parent folder when it holds `manifest.yaml` and `output/`). It writes:

- `docs/Review_Queue.md`, `Audience: person`: a count line, then one table sorted by risk, kind
  and screen. When nothing waits, one line says so.
- `docs/review_queue.json`, for agents and the pipeline: the same items with every field
  (`id`, `kind`, `risk`, `screens`, `ask`, `evidence`, `how_to_record`, `source`, `status`,
  `start`, `due`), and the `as_of` day.

`--as-of YYYY-MM-DD` (default today) is the day overdue is counted against; the same state and
the same `--as-of` give the same bytes. A file it did not write is refused (exit 1); pass
`--force` only when the user says to replace it. `--dry-run` prints the count line and writes
nothing. Exit 2 means it could not run.

## What it reads

| Kind | Source | Waits while |
|---|---|---|
| decision | `{APP}_DecisionQueue.json` (`$ak decisions`) | an item is blocking, proceeding on a default, waiting behind another, or answered by the customer and not recorded |
| decision | `Coding_Records/{screen}.md` 7.1 Pending Answers | a row is not `answered` |
| erratum | `{APP}_Errata.json` | an entry has no `acknowledged_by` |
| plan approval | `Screen_plans/{screen}.md` §5 `open-decision`, §6 `open` | the row cites no decision-queue item |
| test sign-off | `Test_Instruction/{screen}.md` §4.4 Tier 3 | `Verified by` is empty |
| review | `Final_Acceptance/{screen}.md` | User decision is `pending` |
| issue | `Known_Issues.md` Active Log | `open` and `business` or `legacy-bug`, or `traceability` `open (HIGH)`, and not a pointer to a queue item |
| issue | `Screens_Registry.md` | a track is `blocked` and nothing above names the screen |
| external | `External_Dependencies.md` | a row's State is not `done`: an ask of another team or system |

Items already with the customer and items settled by standing policy are counted in a note,
not listed: the owner cannot act on them.

## Risk

From the source's own severity or blocking flag:

- decision from the queue: high with no default or a HIGH severity, medium for MEDIUM, low otherwise;
- pending answer in a coding record: high, because the track is blocked;
- erratum: its severity, medium when it has none;
- plan approval and test sign-off: medium;
- review: high unless the recommendation is approve or approve with follow-ups;
- issue: high for `open (HIGH)` and for a blocked track, else the row's suffix, medium without one;
- external: high when it blocks a screen in the registry and is still `to-send`, or when it is
  overdue; medium otherwise.

## Due dates

An item has a `start` only when its source records a date: an erratum's `created_at`, a
dependency's `Sent on`, a pending answer's `Asked on`, an issue row's `Date`. Its `due` is the
source's own `Due` (a column, or an erratum's `due` field), else `start` plus the kind's days
in `REVIEW_DUE_DAYS` (`docs/PROJECT_CONFIG.md`, e.g. `erratum=5, decision=3, external=10`; a
kind left out takes the default, `n/a` turns the defaults off). No start, no due. The JSON
carries only the two dates; the page's Status column says `overdue` or `due YYYY-MM-DD`,
counted as of `--as-of`.

## Report

Print the count line and the high rows. Each row's *How to record* is the exact command or file
edit that closes it; offer to run the command once the person has given the answer. Never
record an answer, acknowledge an erratum, sign a test or accept a screen on a person's behalf.
