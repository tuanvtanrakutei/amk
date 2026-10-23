# External Dependencies

> **Template.** Copy to `{{DOCS_DIR}}/External_Dependencies.md`.

Audience: person

What this project has asked of another team or system, and waits for: a field added to a
master another team owns, an interface opened, a data extract. A decision of this project's own
often turns into such an ask; the row keeps the two linked, so a screen is never blocked by a
request nobody sent.

`review_queue.py` lists every row that is not `done` (kind `external`). It is high when the row
blocks a screen in `Screens_Registry.md` and is still `to-send`, or when it is past its due
date; otherwise medium. `validate-docs` checks the rows.

## Columns

| Column | Meaning |
|---|---|
| `ID` | `EXT-nn`, unique in this file, never reused |
| `Party` | The other team or system that has to act |
| `Ask` | What they are asked to do, in one sentence |
| `Source decision` | The item code of the decision that led to the ask, e.g. a decision-queue id or a `Known_Issues.md` row |
| `Blocks` | Screens that cannot finish without it, as `Screens_Registry.md` names them or by `F-` id; `—` when none |
| `State` | One of the State Vocabulary below |
| `Sent on` | The date the ask was sent, `YYYY-MM-DD`. Required once the state is `sent` or `in-progress` |
| `Due` | The date the party committed to, `YYYY-MM-DD`. Empty: `REVIEW_DUE_DAYS` in `PROJECT_CONFIG.md` sets it from `Sent on` |
| `Link` | Optional: the issue, ticket or mail thread |

## State Vocabulary

| Value | Meaning |
|---|---|
| `to-send` | Agreed that it must be asked; not yet sent |
| `sent` | Sent; the party has not confirmed it |
| `in-progress` | The party confirmed it and is working on it |
| `done` | Delivered. The row stays, for the audit trail; the review queue skips it |

## Dependencies

Newest first. Never delete a row.

| ID | Party | Ask | Source decision | Blocks | State | Sent on | Due | Link |
|---|---|---|---|---|---|---|---|---|
