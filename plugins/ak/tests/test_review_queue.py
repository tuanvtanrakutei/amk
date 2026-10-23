"""The review queue lists what waits on a person, from every source that records it (A111).

Each source has a test that fails without its reader; the page is sorted by risk, kind and
screen; the same state and the same --as-of give the same bytes; an empty queue says so in one
line; and a queue file the script did not write is never overwritten without --force. A114 adds
asks of other teams (`external`) and due dates counted from a source's own start date.

The workspace and repository are invented, in tmp dirs.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
SCRIPT = PACKAGE / "modernize" / "scripts" / "review_queue.py"
sys.path.insert(0, str(SCRIPT.parent))

import review_queue as rq  # noqa: E402

APP = "A99"
ENTRY, LIST, MENU = "OrderEntry", "OrderList", "MainMenu"

CONFIG = """# Project Config

| Key | Value | Notes |
|---|---|---|
| `SUBSYSTEM_CODE` | `A99` | |
| `DOCS_DIR` | `docs` | |
| `AK_RUN_DIR` | `{run}` | |
"""

REGISTRY = """# Screens Registry

## Status Vocabulary

| Value | Meaning | Set by | Run mode it implies |
|---|---|---|---|
| `blocked` | Cannot proceed | Abort gate | Pipeline stops |

## Active Screens

| # | screen | screen_key | url_segment | module | module_prefix | fe_route | status_be | status_fe |
|---|---|---|---|---|---|---|---|---|
| 1 | `MainMenu` | `main-menu` | `main-menu` | `order` | `order/` | `/a99/main-menu` | `blocked` | `not_started` |
| 2 | `OrderEntry` | `order-entry` | `order-entry` | `order` | `order/` | `/a99/order-entry` | `blocked` | `implemented` |
| 3 | `OrderList` | `order-list` | `order-list` | `order` | `order/` | `/a99/order-list` | `implemented` | `implemented` |

## Future Scope

| # | screen | screen_key (proposed) | module (proposed) |
|---|---|---|---|
| 1 | `Archive` | `archive` | `order` |
"""

CODING = """# OrderEntry — Coding Record

## 7. Open Items And Q&A

### 7.1 Pending Answers (block progress)

| # | Track | Question | Type | Asked to | Asked on | Status |
|---|---|---|---|---|---|---|
| 1 | backend | Which tax rate applies to a returned line? | business | Sales office | 2026-01-05 | open |
| 2 | backend | Is the order number reused after a cancel? | business | Sales office | 2026-01-05 | answered |

### 7.2 Not Yet Implemented (intentional)

| # | Track | Item | Reason for deferral | Tracked in |
|---|---|---|---|---|
| 1 | both | Export | later | this file |
"""

PLAN = """# OrderList (order module)

## 5. Legacy-To-New Mapping

| # | Rule (BR- id) | Legacy anchor | Backend location | Frontend location | Status |
|---|---|---|---|---|---|
| 1 | BR-ORD-01 | `cmdOk_Click` | `services.py` | `page.tsx` | planned |
| 2 | BR-ORD-02 rounding of totals | `calc` | `services.py` | — | open-decision |

## 6. Gap Matrix

| Topic | Legacy behavior | New behavior | Status |
|---|---|---|---|
| Sort order of the list | by entry time | by entry time | matched |
| Print button shows a preview | prints at once | shows a preview first | open |
| Q7 delivery date default | today | today | open |

## 7. Acceptance And Validation Scenarios
"""

TESTS = """# OrderList — Test Instruction

### 4.4 Tier 3 — Residual Manual

| # | Case | Exact steps | Legacy sample to compare | Result | Verified by |
|---|---|---|---|---|---|
| 1 | Printed list page breaks | print 3 pages | `samples/list.pdf` | | |
| 2 | Logo position | print | `samples/list.pdf` | match | A Person 2026-01-09 |

### 4.5 Commands And Results
"""

ACCEPTANCE = """# OrderList — Final Acceptance

## 1. Summary

- **Recommendation**: approve | approve with follow-ups | fix required
- **User decision**: pending | accepted | rejected | changed

## 5. Recommendation

- **Recommendation**: approve with follow-ups
- **User decision**: pending until the user answers
"""

ISSUES = """# Known Issues

## Active Log

| # | Date | Type | Title | Affects | Status | Owner | Decision / Next step |
|---|---|---|---|---|---|---|---|
| 5 | 2026-01-08 | traceability | G2: rule BR-ORD-03 has no mapping row | `OrderList` | open (HIGH) | — | examine |
| 4 | 2026-01-07 | traceability | G3: a hint text is missing | `OrderList` | open (LOW) | — | Stage 5 |
| 3 | 2026-01-06 | legacy-bug | Totals drop the last line | `OrderList` | open | — | see RD-02 |
| 2 | 2026-01-05 | business | Who may cancel a printed order | all screens | open | — | ask the office |
| 1 | 2026-01-04 | tech-stack | Lint is slow | — | open | — | — |
"""


DEPENDENCIES = """# External Dependencies

Audience: person

## State Vocabulary

| Value | Meaning |
|---|---|
| `to-send` | not yet sent |
| `done` | delivered |

## Dependencies

| ID | Party | Ask | Source decision | Blocks | State | Sent on | Due | Link |
|---|---|---|---|---|---|---|---|---|
| EXT-05 | Stock team | rename a column | Q1 | `OrderEntry` | done | 2026-01-01 | | |
| EXT-04 | Billing system | widen a code field | Q7 | `OrderEntry` | in-progress | 2026-01-02 | 2026-02-01 | |
| EXT-03 | Billing system | export the tax table | Q7 | `OrderList` | sent | 2026-01-02 | | https://example.invalid/3 |
| EXT-02 | Stock team | open the stock interface | RD-02 | Archive | to-send | | | |
| EXT-01 | Stock team | add a reorder flag | Q1 | F-001 | to-send | | | |
"""


def queue_item(ident: str, bucket: str, *, posture: str = "PROCEEDS_ON_DEFAULT", kind: str = "FACT",
               party: str = "Sales office", blocks: list | None = None, severity: str | None = None,
               default: dict | None = None, **extra: object) -> dict:
    return {"id": ident, "title": f"question {ident}", "kind": kind, "party": party, "bucket": bucket,
            "posture": posture, "blocks": blocks or [], "severity": severity,
            "default": default, "evidence_ids": [], **extra}


def decision_queue() -> dict:
    return {"app_id": APP, "counts": {}, "items": [
        queue_item("Q1", "blocking", posture="BLOCKING", blocks=[{"id": "F-002", "title": ENTRY}]),
        queue_item("RD-02", "proceeding", kind="DISPOSITION", party="decider", severity="MEDIUM",
                   default={"mitigation": True}, blocks=[]),
        queue_item("Q7", "proceeding", default={"id": "AS-01", "title": "today"},
                   blocks=[{"id": "F-003", "title": LIST}]),
        queue_item("Q8", "to_record", customer={"state": "answered_unrecorded", "qa": [{"id": 4}]}),
        queue_item("Q9", "with_customer"),
        queue_item("RA-03", "settled", kind="DISPOSITION", party="decider"),
    ], "closed": [{"id": "Q2"}]}


def errata() -> dict:
    return {"app_id": APP, "entries": [
        {"id": "E-01", "original": "x", "corrected": "the list sorts by entry time", "affected": ["Phase 2", "F-003"],
         "source": "s", "cause": "EVIDENCE_MISREAD", "severity": "HIGH", "created_at": "2026-01-01T00:00:00+00:00"},
        {"id": "E-02", "original": "y", "corrected": "z", "affected": ["Phase 1"], "source": "s",
         "cause": "EVIDENCE_MISREAD", "created_at": "2026-01-02T00:00:00+00:00",
         "acknowledged_by": "A Person", "acknowledged_on": "2026-01-03"},
    ]}


def identifiers() -> dict:
    return {"app_id": APP, "entries": [
        {"id": "F-001", "namespace": "F-", "title": MENU},
        {"id": "F-002", "namespace": "F-", "title": ENTRY},
        {"id": "F-003", "namespace": "F-", "title": LIST},
    ]}


def build_project(tmp_path: Path, *, run: str = "..", full: bool = True) -> Path:
    """An invented workspace with the modernize repo inside it, as bootstrap lays them out."""
    ws = tmp_path / "ws"
    registers = ws / "output" / "registers"
    registers.mkdir(parents=True)
    (ws / "manifest.yaml").write_text("app_id: A99\n", encoding="utf-8")
    repo = ws / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    (docs / "PROJECT_CONFIG.md").write_text(CONFIG.format(run=run), encoding="utf-8")
    (docs / "Screens_Registry.md").write_text(REGISTRY, encoding="utf-8")
    for folder in ("Coding_Records", "Screen_plans", "Test_Instruction", "Final_Acceptance"):
        (docs / folder).mkdir()
        (docs / folder / "README.md").write_text("# README\n\n| # | Question | Status |\n|---|---|---|\n"
                                                  "| 1 | not a row | open |\n", encoding="utf-8")
    if full:
        (registers / f"{APP}_DecisionQueue.json").write_text(json.dumps(decision_queue()), encoding="utf-8")
        (registers / f"{APP}_Errata.json").write_text(json.dumps(errata()), encoding="utf-8")
        (registers / f"{APP}_Identifiers.json").write_text(json.dumps(identifiers()), encoding="utf-8")
        (docs / "Coding_Records" / f"{ENTRY}.md").write_text(CODING, encoding="utf-8")
        (docs / "Screen_plans" / f"{LIST}.md").write_text(PLAN, encoding="utf-8")
        (docs / "Test_Instruction" / f"{LIST}.md").write_text(TESTS, encoding="utf-8")
        (docs / "Final_Acceptance" / f"{LIST}.md").write_text(ACCEPTANCE, encoding="utf-8")
        (docs / "Known_Issues.md").write_text(ISSUES, encoding="utf-8")
    else:
        (docs / "Screens_Registry.md").write_text(REGISTRY.replace("`blocked`", "`implemented`"),
                                                  encoding="utf-8")
    return repo


def run(repo: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), "--repo", str(repo), *extra],
                          capture_output=True, text=True, encoding="utf-8")


def queue_of(repo: Path, as_of: str | None = None) -> dict:
    return rq.build(rq.Project(repo, None, None), date.fromisoformat(as_of) if as_of else None)


def with_dependencies(tmp_path: Path, config: str = "") -> Path:
    repo = build_project(tmp_path)
    (repo / "docs" / rq.DEPENDENCIES).write_text(DEPENDENCIES, encoding="utf-8")
    if config:
        path = repo / "docs" / "PROJECT_CONFIG.md"
        path.write_text(path.read_text(encoding="utf-8") + f"| `REVIEW_DUE_DAYS` | `{config}` | |\n",
                        encoding="utf-8")
    return repo


def by_id(queue: dict) -> dict[str, dict]:
    return {item["id"]: item for item in queue["items"]}


# --- each source ------------------------------------------------------------------

def test_decision_queue_items_an_owner_can_act_on(tmp_path: Path) -> None:
    items = by_id(queue_of(build_project(tmp_path)))
    assert items["decision:Q1"]["risk"] == "high"               # no default: blocking
    assert items["decision:Q1"]["screens"] == [ENTRY]
    assert items["decision:RD-02"]["risk"] == "medium"          # its own severity
    assert "--decide --by <name>" in items["decision:RD-02"]["how_to_record"]
    assert items["decision:Q7"]["risk"] == "low"                # proceeds on a default
    assert "--assume Q7" in items["decision:Q7"]["how_to_record"]
    assert "Q&A 4" in items["decision:Q8"]["ask"]
    assert "decision:Q9" not in items and "decision:RA-03" not in items


def test_items_with_the_customer_or_settled_are_counted_in_a_note(tmp_path: Path) -> None:
    notes = " ".join(queue_of(build_project(tmp_path))["notes"])
    assert "1 decision item(s) are already with the customer" in notes
    assert "1 decision item(s) are settled by standing policy" in notes


def test_errata_wait_until_acknowledged(tmp_path: Path) -> None:
    items = by_id(queue_of(build_project(tmp_path)))
    assert items["erratum:E-01"]["risk"] == "high"
    assert items["erratum:E-01"]["screens"] == [LIST]          # F-003 named as the registry names it
    assert "acknowledged_by" in items["erratum:E-01"]["how_to_record"]
    assert "erratum:E-02" not in items


def test_erratum_with_no_severity_is_medium(tmp_path: Path) -> None:
    repo = build_project(tmp_path)
    path = repo.parent / "output" / "registers" / f"{APP}_Errata.json"
    data = errata()
    del data["entries"][0]["severity"]
    path.write_text(json.dumps(data), encoding="utf-8")
    assert by_id(queue_of(repo))["erratum:E-01"]["risk"] == "medium"


def test_coding_record_pending_answers(tmp_path: Path) -> None:
    items = by_id(queue_of(build_project(tmp_path)))
    pending = items[f"decision:{ENTRY}:7.1#1"]
    assert pending["risk"] == "high" and pending["screens"] == [ENTRY]
    assert "tax rate" in pending["ask"]
    assert f"decision:{ENTRY}:7.1#2" not in items              # answered
    assert not any("README" in i["source"] for i in items.values())


def test_plan_rows_that_cite_no_queue_item(tmp_path: Path) -> None:
    items = by_id(queue_of(build_project(tmp_path)))
    plans = [i for i in items.values() if i["kind"] == "plan approval"]
    asks = " ".join(i["ask"] for i in plans)
    assert len(plans) == 2
    assert "Print button shows a preview" in asks and "rounding of totals" in asks
    assert "delivery date" not in asks                          # cites Q7: the queue's item


def test_unsigned_manual_tests(tmp_path: Path) -> None:
    items = by_id(queue_of(build_project(tmp_path)))
    signed = [i for i in items.values() if i["kind"] == "test sign-off"]
    assert [i["id"] for i in signed] == [f"test:{LIST}:4.4#1"]
    assert "page breaks" in signed[0]["ask"]


def test_final_acceptance_pending(tmp_path: Path) -> None:
    item = by_id(queue_of(build_project(tmp_path)))[f"review:{LIST}"]
    assert item["risk"] == "medium" and "approve with follow-ups" in item["ask"]


def test_final_acceptance_decided_is_not_listed(tmp_path: Path) -> None:
    repo = build_project(tmp_path)
    path = repo / "docs" / "Final_Acceptance" / f"{LIST}.md"
    path.write_text(ACCEPTANCE.replace("pending until the user answers", "accepted"), encoding="utf-8")
    assert f"review:{LIST}" not in by_id(queue_of(repo))


def test_known_issues_that_need_a_decision(tmp_path: Path) -> None:
    items = by_id(queue_of(build_project(tmp_path)))
    assert items["issue:#5"]["risk"] == "high"                  # open (HIGH)
    assert items["issue:#2"]["risk"] == "medium"                # business
    assert "issue:#4" not in items                              # LOW: the reviewer confirms it
    assert "issue:#3" not in items                              # points at RD-02, a queue item
    assert "issue:#1" not in items                              # tech-stack: no decision needed


def test_a_blocked_track_nothing_explains(tmp_path: Path) -> None:
    items = by_id(queue_of(build_project(tmp_path)))
    assert items[f"issue:registry:{MENU}"]["risk"] == "high"
    assert f"issue:registry:{ENTRY}" not in items               # its coding record names the blocker


# --- external dependencies and due dates (A114) -------------------------------------

def test_an_unsent_ask_blocking_a_registry_screen_is_high(tmp_path: Path) -> None:
    item = by_id(queue_of(with_dependencies(tmp_path), "2026-01-09"))["external:EXT-01"]
    assert item["kind"] == "external" and item["risk"] == "high"
    assert item["screens"] == [MENU]                            # F-001, named as the registry names it
    assert item["ask"].startswith("Send EXT-01 to Stock team") and "`sent`" in item["how_to_record"]


def test_an_unsent_ask_blocking_no_registry_screen_is_medium(tmp_path: Path) -> None:
    item = by_id(queue_of(with_dependencies(tmp_path), "2026-01-09"))["external:EXT-02"]
    assert item["risk"] == "medium" and item["screens"] == ["Archive"]


def test_a_sent_ask_is_medium_until_it_is_overdue(tmp_path: Path) -> None:
    repo = with_dependencies(tmp_path)
    assert by_id(queue_of(repo, "2026-01-12"))["external:EXT-03"]["risk"] == "medium"    # due that day
    assert by_id(queue_of(repo, "2026-01-13"))["external:EXT-03"]["risk"] == "high"      # a day late
    assert "https://example.invalid/3" in by_id(queue_of(repo))["external:EXT-03"]["evidence"]


def test_done_rows_are_not_listed(tmp_path: Path) -> None:
    items = by_id(queue_of(with_dependencies(tmp_path), "2026-01-09"))
    assert "external:EXT-05" not in items
    assert sorted(i for i in items if i.startswith("external:")) == [f"external:EXT-0{n}" for n in (1, 2, 3, 4)]


def test_the_default_due_and_a_due_the_source_gives(tmp_path: Path) -> None:
    items = by_id(queue_of(with_dependencies(tmp_path), "2026-01-09"))
    assert (items["external:EXT-03"]["start"], items["external:EXT-03"]["due"]) == ("2026-01-02", "2026-01-12")
    assert items["external:EXT-04"]["due"] == "2026-02-01"      # its own Due wins
    assert items["erratum:E-01"]["due"] == "2026-01-06"         # created_at + 5
    assert items[f"decision:{ENTRY}:7.1#1"]["due"] == "2026-01-08"   # Asked on + 3
    assert items["issue:#2"]["due"] == "2026-01-10"             # Date + 5


def test_project_config_sets_the_days_per_kind(tmp_path: Path) -> None:
    items = by_id(queue_of(with_dependencies(tmp_path, "external=20, test_sign-off=2, nonsense"), "2026-01-09"))
    assert items["external:EXT-03"]["due"] == "2026-01-22"
    assert items["external:EXT-04"]["due"] == "2026-02-01"      # the source's Due still wins
    assert items["erratum:E-01"]["due"] == "2026-01-06"         # a kind left out keeps its default


def test_not_applicable_turns_the_defaults_off(tmp_path: Path) -> None:
    items = by_id(queue_of(with_dependencies(tmp_path, "n/a"), "2026-01-09"))
    assert items["external:EXT-03"]["due"] is None and items["external:EXT-03"]["start"] == "2026-01-02"
    assert items["external:EXT-04"]["due"] == "2026-02-01"


def test_a_bad_due_days_entry_is_a_note(tmp_path: Path) -> None:
    notes = " ".join(queue_of(with_dependencies(tmp_path, "external=ten"))["notes"])
    assert "`external=ten`" in notes


def test_an_erratum_due_field_overrides_the_default(tmp_path: Path) -> None:
    repo = build_project(tmp_path)
    data = errata()
    data["entries"][0]["due"] = "2026-03-01"
    (repo.parent / "output" / "registers" / f"{APP}_Errata.json").write_text(json.dumps(data), encoding="utf-8")
    assert by_id(queue_of(repo))["erratum:E-01"]["due"] == "2026-03-01"


def test_no_start_date_gives_no_due_date(tmp_path: Path) -> None:
    items = by_id(queue_of(with_dependencies(tmp_path), "2026-12-31"))
    for ident in ("external:EXT-01", "decision:Q1", f"test:{LIST}:4.4#1", f"review:{LIST}"):
        assert (items[ident]["start"], items[ident]["due"]) == (None, None), ident
    assert items["external:EXT-02"]["risk"] == "medium"         # no due, so never overdue
    assert all(i["due"] is None for i in items.values() if i["kind"] == "plan approval")


def test_the_page_says_overdue_or_due_as_of_the_day_given(tmp_path: Path) -> None:
    repo = with_dependencies(tmp_path)
    assert run(repo, "--as-of", "2026-01-09").returncode == 0
    page = (repo / "docs" / rq.PAGE).read_text(encoding="utf-8")
    assert next(line for line in page.split("\n") if "Send EXT-01" in line).endswith("| waiting |")
    ext3 = next(line for line in page.split("\n") if "EXT-03 is with" in line)
    assert ext3.endswith("| due 2026-01-12 |")
    assert "| overdue |" in page and "overdue as of 2026-01-09" in page    # E-01 was due 2026-01-06
    assert run(repo, "--as-of", "2026-01-13").returncode == 0
    page = (repo / "docs" / rq.PAGE).read_text(encoding="utf-8")
    assert next(line for line in page.split("\n") if "EXT-03 is with" in line).endswith("| overdue |")


def test_a_bad_as_of_cannot_run(tmp_path: Path) -> None:
    result = run(build_project(tmp_path), "--as-of", "2026-13-01")
    assert result.returncode == 2 and "--as-of" in result.stderr


# --- the page ---------------------------------------------------------------------

def test_sorted_by_risk_then_kind_then_screen(tmp_path: Path) -> None:
    items = queue_of(build_project(tmp_path))["items"]
    keys = [(rq.RISKS.index(i["risk"]), rq.KINDS.index(i["kind"]), i["screens"][:1] or ["~"]) for i in items]
    assert keys == sorted(keys)
    assert items[0]["risk"] == "high" and items[-1]["risk"] == "low"
    highs = [i["kind"] for i in items if i["risk"] == "high"]
    assert highs == sorted(highs, key=rq.KINDS.index)


def test_page_starts_with_the_count_line(tmp_path: Path) -> None:
    repo = build_project(tmp_path)
    assert run(repo).returncode == 0
    page = (repo / "docs" / rq.PAGE).read_text(encoding="utf-8")
    lines = page.split("\n")
    assert lines[0].startswith(rq.GENERATED_MD) and "Audience: person" in lines
    data = json.loads((repo / "docs" / rq.DATA).read_text(encoding="utf-8"))
    c = data["counts"]
    assert (f"{c['total']} items wait on a person: {c['by_risk']['high']} high, "
            f"{c['by_risk']['medium']} medium, {c['by_risk']['low']} low.") in lines
    assert "review the whole" not in page.lower()
    assert page.count("\n| ") == c["total"] + 1                 # one header row, one row per item


def test_same_state_and_as_of_give_the_same_bytes(tmp_path: Path) -> None:
    repo = build_project(tmp_path)
    (repo / "docs" / rq.DEPENDENCIES).write_text(DEPENDENCIES, encoding="utf-8")
    assert run(repo, "--as-of", "2026-01-09").returncode == 0
    first = [(repo / "docs" / n).read_bytes() for n in (rq.PAGE, rq.DATA)]
    assert run(repo, "--as-of", "2026-01-09").returncode == 0
    assert [(repo / "docs" / n).read_bytes() for n in (rq.PAGE, rq.DATA)] == first
    assert all(b"\r" not in b for b in first)
    items = json.loads(first[1])["items"]                       # the JSON carries dates, never the verdict
    assert all(i["status"] == "waiting" and "overdue" not in i for i in items)
    assert run(repo, "--as-of", "2026-03-01").returncode == 0
    assert (repo / "docs" / rq.PAGE).read_bytes() != first[0]


def test_empty_queue_says_so_in_one_line(tmp_path: Path) -> None:
    repo = build_project(tmp_path, full=False)
    assert run(repo).returncode == 0
    page = (repo / "docs" / rq.PAGE).read_text(encoding="utf-8")
    body = [line for line in page.split("\n")[1:] if line and not line.startswith(("#", "Audience", "-"))]
    assert body == ["Nothing waits on a person."]
    assert "|" not in page


def test_a_foreign_file_is_refused_unless_forced(tmp_path: Path) -> None:
    repo = build_project(tmp_path)
    page = repo / "docs" / rq.PAGE
    page.write_text("# Review queue, by hand\n", encoding="utf-8")
    result = run(repo)
    assert result.returncode == 1 and "did not write" in result.stderr
    assert page.read_text(encoding="utf-8") == "# Review queue, by hand\n"
    assert not (repo / "docs" / rq.DATA).exists()
    assert run(repo, "--force").returncode == 0
    assert page.read_text(encoding="utf-8").startswith(rq.GENERATED_MD)


def test_a_foreign_json_is_refused(tmp_path: Path) -> None:
    repo = build_project(tmp_path)
    (repo / "docs" / rq.DATA).write_text('{"items": []}\n', encoding="utf-8")
    assert run(repo).returncode == 1
    assert not (repo / "docs" / rq.PAGE).exists()


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    repo = build_project(tmp_path)
    result = run(repo, "--dry-run")
    assert result.returncode == 0 and "items wait on a person" in result.stdout
    assert not (repo / "docs" / rq.PAGE).exists() and not (repo / "docs" / rq.DATA).exists()


# --- finding the workspace --------------------------------------------------------

@pytest.mark.parametrize("value", ["n/a", "{{AK_RUN_DIR}}"])
def test_the_parent_folder_is_the_workspace_when_the_config_names_none(tmp_path: Path, value: str) -> None:
    queue = queue_of(build_project(tmp_path, run=value))
    assert "decision:Q1" in by_id(queue)
    assert queue["workspace"] == ".."


def test_no_workspace_is_a_note_not_a_failure(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    (repo / "docs" / "PROJECT_CONFIG.md").write_text(CONFIG.format(run="n/a"), encoding="utf-8")
    queue = queue_of(repo)
    assert queue["items"] == [] and "no investigation workspace" in " ".join(queue["notes"])


def test_a_missing_repo_cannot_run(tmp_path: Path) -> None:
    assert run(tmp_path / "absent").returncode == 2
