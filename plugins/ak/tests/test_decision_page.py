"""`{APP}_Decisions.md`: one row per decided item, with the decision in force (A110).

A phase cites a decision by its item code and says nothing about how it was reached; this
page is where the code meets its record. So it has to be right about which decision is in
force: an erratum, a later decision for the same code, and a later record that says what it
replaces each retire the earlier one, and the earlier one moves to a footnote.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
for _path in (PACKAGE / "contracts", PACKAGE / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import build_decisions  # noqa: E402
import decision_page as page_contract  # noqa: E402


def target(serial: int, statement: str, *, question: str | None = None, row: str | None = None,
           created: str = "2026-10-01T09:00:00+00:00", notes: str = "",
           source: str = "input/target-intent/A99_Decisions_2026-10-01.md") -> dict:
    return {
        "id": f"A99-P5-TARGET-{serial:03d}", "evidence_class": "TARGET_INTENT",
        "statement": statement, "created_at": created, "notes": notes,
        "attribution": {"person": "Person One", "role": "decider",
                        **({"question_id": question} if question else {})},
        "source_location": f"row {row}" if row else ("row " + question if question else "whole record"),
        "source_path": source,
    }


def risk(eid: str, title: str, resolved_by: str | None = None, phase: int = 2) -> dict:
    namespace = eid.split("-")[0] + "-"
    return {"id": eid, "namespace": namespace, "phase": phase, "title": title,
            **({"resolved_by": resolved_by} if resolved_by else {})}


def disposition(serial: int, item: str, word: str, meaning: str, **kw: object) -> dict:
    return target(serial, f"Disposition of {item}: {word}. {meaning}", question=item, **kw)


# --- which decision is in force ----------------------------------------------------

def test_an_erratum_retires_the_decision_it_lists_and_the_later_one_is_in_force() -> None:
    entries = [risk("RA-04", "A failed import loses the earlier files.", "A99-P5-TARGET-002")]
    evidence = [
        disposition(1, "RA-04", "fix", "Do what its Mitigation says: Keep every file."),
        disposition(2, "RA-04", "fix", "Do what its Mitigation says: Import in one transaction.",
                    created="2026-10-02T09:00:00+00:00"),
    ]
    errata = [{"id": "E-02", "superseded_evidence_ids": ["A99-P5-TARGET-001"]}]
    page = page_contract.build(entries, evidence, errata)
    assert [(d.code, d.evidence_id) for d in page.rows] == [("RA-04", "A99-P5-TARGET-002")]
    assert [(d.evidence_id, d.superseded_by) for d in page.superseded] == [
        ("A99-P5-TARGET-001", ["A99-P5-TARGET-002", "E-02"])]
    assert page.replaces[("RA-04", "A99-P5-TARGET-002")] == ["A99-P5-TARGET-001", "E-02"]


def test_an_erratum_alone_can_leave_an_item_with_no_decision_in_force() -> None:
    evidence = [disposition(1, "RW-01", "drop", "The behaviour is not carried into the new system.")]
    errata = [{"id": "E-01", "superseded_evidence_ids": ["A99-P5-TARGET-001"]}]
    page = page_contract.build([risk("RW-01", "A report nobody opens.")], evidence, errata)
    assert page.rows == [] and page.withdrawn == ["RW-01"]
    text = page_contract.render(page, "A99")
    assert "RW-01: every decision recorded for it is superseded" in text


def test_a_later_item_for_the_same_code_retires_the_earlier_one_without_an_erratum() -> None:
    evidence = [
        disposition(1, "RD-02", "preserve", "Keep the legacy behaviour as it is."),
        disposition(2, "RD-02", "fix", "Do what its Mitigation says: Use one key type.",
                    created="2026-10-03T09:00:00+00:00"),
    ]
    page = page_contract.build([risk("RD-02", "A key declared four ways.", "A99-P5-TARGET-002", 1)],
                               evidence, [])
    assert [d.evidence_id for d in page.rows] == ["A99-P5-TARGET-002"]
    assert page.superseded[0].superseded_by == ["A99-P5-TARGET-002"]
    assert page.problems == []


def test_later_is_the_time_recorded_not_the_order_of_the_register() -> None:
    evidence = [
        disposition(2, "RD-02", "fix", "Use one key type.", created="2026-10-01T09:00:00+07:00"),
        disposition(1, "RD-02", "preserve", "Keep it.", created="2026-10-01T09:00:00+00:00"),
    ]
    page = page_contract.build([risk("RD-02", "A key.", phase=1)], evidence, [])
    # 09:00+07:00 is 02:00 UTC, before 09:00 UTC: item 1 is the later decision.
    assert [d.evidence_id for d in page.rows] == ["A99-P5-TARGET-001"]


def test_a_record_that_says_what_it_replaces_retires_a_row_code_of_another_name() -> None:
    evidence = [
        target(1, "The export is named with the store first (decided 2026-10-01).", row="D-LABEL-A"),
        target(2, "The export is named with the date first (decided 2026-10-02, replaces D-LABEL-A).",
               row="D-LABEL-B", created="2026-10-02T09:00:00+00:00",
               notes="Replaces A99-P5-TARGET-001."),
    ]
    page = page_contract.build([], evidence, [])
    assert [d.code for d in page.rows] == ["D-LABEL-B"]
    assert page.withdrawn == ["D-LABEL-A"]
    assert page.replaces[("D-LABEL-B", "A99-P5-TARGET-002")] == ["A99-P5-TARGET-001"]
    row = next(line for line in page_contract.render(page, "A99").splitlines()
               if line.startswith("| D-LABEL-B |"))
    # What the replacement does, without the record's date or history.
    assert "The export is named with the date first." in row and "replaces" not in row.split("|")[4]


def test_an_item_whose_own_notes_say_it_was_superseded_is_not_in_force() -> None:
    evidence = [target(1, "Rows sort by code.", row="D-ROW-ORDER",
                       notes="Superseded by E-03: rows sort by name.")]
    page = page_contract.build([], evidence, [])
    assert page.rows == [] and page.superseded[0].superseded_by == ["E-03"]


# --- item codes --------------------------------------------------------------------

def test_record_row_codes_come_from_the_question_id_else_the_row_location() -> None:
    evidence = [
        target(1, "Out of scope.", question="Q7", row="D-IGNORED"),
        target(2, "The two fields come from the master.", row="D-EXPORT-NAME"),
        target(3, "A scope table with no row.", created="2026-10-02T09:00:00+00:00"),
    ]
    entries = [{"id": "Q7", "namespace": "Q", "phase": 1, "title": "Is the error screen used?",
                "resolved_by": "A99-P5-TARGET-001"}]
    page = page_contract.build(entries, evidence, [])
    assert [d.code for d in page.rows] == ["Q7", "D-EXPORT-NAME"]
    assert page.unplaced == ["A99-P5-TARGET-003"]


def test_an_item_the_register_closes_with_a_record_that_names_no_code_is_still_decided() -> None:
    evidence = [target(1, "Both error screens are out of scope.")]
    entries = [{"id": "Q3", "namespace": "Q", "phase": 2, "title": "Error screens?",
                "resolved_by": "A99-P5-TARGET-001"},
               {"id": "UK-S01", "namespace": "UK-", "phase": 2, "title": "Who prints it?",
                "resolved_by": "A99-P5-TARGET-001"}]
    page = page_contract.build(entries, evidence, [])
    assert [d.code for d in page.rows] == ["UK-S01", "Q3"]
    assert page.unplaced == []


def test_a_record_row_that_opens_with_its_word_shows_that_word() -> None:
    item = target(1, "fix (minimal): the date field takes a valid date or stays empty.", row="D-DATE-EDIT")
    assert page_contract.decision_word(item) == "fix"
    assert page_contract.what_it_does(item) == "the date field takes a valid date or stays empty."
    assert page_contract.decision_word(target(2, "accept: the column stays.", row="D-X")) == "decided"


def test_an_interview_answer_is_not_a_decision() -> None:
    evidence = [{"id": "A99-P1-INTERVIEW-001", "evidence_class": "INTERVIEW", "statement": "Yes."}]
    entries = [{"id": "Q1", "namespace": "Q", "phase": 1, "resolved_by": "A99-P1-INTERVIEW-001"}]
    assert page_contract.build(entries, evidence, []).rows == []


def test_a_register_that_closes_an_item_with_a_retired_decision_is_reported() -> None:
    evidence = [disposition(1, "RA-01", "fix", "Fix it."),
                disposition(2, "RA-01", "drop", "Drop it.", created="2026-10-02T09:00:00+00:00")]
    page = page_contract.build([risk("RA-01", "A thing.", "A99-P5-TARGET-001")], evidence, [])
    assert page.problems == ["the register closes RA-01 with A99-P5-TARGET-001; the decision in "
                             "force is A99-P5-TARGET-002"]


# --- the page ----------------------------------------------------------------------

def sample() -> tuple[list[dict], list[dict], list[dict]]:
    entries = [risk("RW-01", "Exports take whatever batch is loaded.", "A99-P5-TARGET-003", 4),
               risk("RA-04", "A failed import loses files.", "A99-P5-TARGET-002"),
               {"id": "Q2", "namespace": "Q", "phase": 1, "title": "Who completes a new store?",
                "resolved_by": "A99-P5-TARGET-004"}]
    evidence = [
        disposition(1, "RA-04", "fix", "Do what its Mitigation says: Keep every file."),
        disposition(2, "RA-04", "fix", "Do what its Mitigation says: Import in one transaction. "
                    "Decider's note: no files are kept.", created="2026-10-02T09:00:00+00:00"),
        disposition(3, "RW-01", "preserve", "Keep the legacy behaviour as it is."),
        target(4, "Staff complete it in the store master system.", question="Q2"),
        target(5, "The print layout keeps two columns.", row="D-PRINT-COLS"),
    ]
    errata = [{"id": "E-01", "superseded_evidence_ids": ["A99-P5-TARGET-001"]}]
    return entries, evidence, errata


def test_rows_are_grouped_by_namespace_sorted_and_end_with_a_count() -> None:
    entries, evidence, errata = sample()
    built = page_contract.build(entries, evidence, errata)
    text = page_contract.render(built, "A99", titles={e["id"]: e["title"] for e in entries},
                                abouts={"D-PRINT-COLS": "How many columns the print has."})
    lines = text.splitlines()
    assert lines[0].startswith(page_contract.GENERATED)
    assert lines[3].startswith("Audience: bridge")
    headings = [line for line in lines if line.startswith("## ")]
    assert headings == ["## Application risks (RA-)", "## Workflow risks (RW-)", "## Questions (Q)",
                        "## Decision-record rows", "## Superseded"]
    assert ("| RA-04 | A failed import loses files. | fix | Import in one transaction. Note: no files "
            "are kept. | A99-P5-TARGET-002 | A99-P5-TARGET-001, E-01 |") in lines
    assert "| RW-01 | Exports take whatever batch is loaded. | preserve | Keep the legacy behaviour as it is. " \
           "| A99-P5-TARGET-003 | — |" in lines
    assert "| Q2 | Who completes a new store? | decided |" in text
    assert "| D-PRINT-COLS | How many columns the print has. | decided |" in text
    assert "- A99-P5-TARGET-001 (RA-04): superseded by A99-P5-TARGET-002, E-01." in lines
    assert lines[-1] == ("4 decided item(s): application risks 1, workflow risks 1, questions 1, "
                         "decision-record rows 1; 1 superseded decision(s).")
    assert text.endswith("\n") and "\r" not in text


def test_the_same_registers_give_the_same_bytes_whatever_their_order() -> None:
    entries, evidence, errata = sample()
    one = page_contract.render(page_contract.build(entries, evidence, errata), "A99")
    two = page_contract.render(page_contract.build(list(reversed(entries)), list(reversed(evidence)),
                                                   errata), "A99")
    assert one == two
    assert "2026" not in one.split("## ")[0]


def test_the_about_of_a_row_code_is_read_from_its_record(tmp_path: Path) -> None:
    record = tmp_path / "input" / "target-intent" / "A99_Decisions_2026-10-01.md"
    record.parent.mkdir(parents=True)
    record.write_text("# Record\n\n| Item | About | Decision |\n|---|---|---|\n"
                      "| D-PRINT-COLS | The column count of the print. | Two. |\n", encoding="utf-8")
    _, evidence, _ = sample()
    assert page_contract.record_abouts(tmp_path, evidence) == {
        "D-PRINT-COLS": "The column count of the print."}


# --- written by `$ak decisions` ----------------------------------------------------

def make_workspace(tmp_path: Path) -> Path:
    root = tmp_path / "A99"
    (root / "input" / "decisions").mkdir(parents=True)
    (root / "input" / "decisions" / "parties.yaml").write_text(
        "parties:\n  Store office:\n    aliases: [Office]\n", encoding="utf-8")
    registers = root / "output" / "registers"
    registers.mkdir(parents=True)
    entries, evidence, errata = sample()
    for entry in entries:
        if entry["namespace"] != "Q":
            entry["needs"] = {"kind": "DISPOSITION", "party": "decider", "default": "mitigation",
                              "class": "behaviour"}
            entry["severity"] = "MEDIUM"
    for name, body in (("A99_Identifiers.json", {"app_id": "A99", "entries": entries}),
                       ("A99_Evidence.json", {"app_id": "A99", "items": evidence}),
                       ("A99_Errata.json", {"app_id": "A99", "entries": errata})):
        (registers / name).write_text(json.dumps(body, indent=1, sort_keys=True) + "\n",
                                      encoding="utf-8", newline="\n")
    return root


def run(monkeypatch: pytest.MonkeyPatch, root: Path, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["build_decisions.py", "--app-root", str(root), *args])
    return build_decisions.main()


def test_decisions_writes_the_page_beside_the_phase_documents_and_again_unchanged(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    root = make_workspace(tmp_path)
    page = root / "output" / "A99_Decisions.md"
    run(monkeypatch, root)
    first = page.read_bytes()
    assert first.startswith(page_contract.GENERATED.encode("utf-8")) and b"\r" not in first
    assert b"| RA-04 |" in first and b"`A99_Errata.json`" in first
    out = capsys.readouterr().out
    assert "4 decided item(s) in force, 1 superseded decision(s)" in out
    run(monkeypatch, root)
    assert page.read_bytes() == first
    assert f"unchanged {page}" in capsys.readouterr().out


def test_decisions_refuses_to_overwrite_a_page_it_did_not_write(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    root = make_workspace(tmp_path)
    page = root / "output" / "A99_Decisions.md"
    page.write_text("# Our own decisions\n", encoding="utf-8")
    assert run(monkeypatch, root) == 2
    assert "A99_Decisions.md exists and this command did not write it" in capsys.readouterr().err
    assert page.read_text(encoding="utf-8") == "# Our own decisions\n"
    assert not (root / "output" / "A99_QuestionList.md").exists()
    run(monkeypatch, root, "--replace-handwritten")
    assert page.read_text(encoding="utf-8").startswith(page_contract.GENERATED)


def test_a_dry_run_writes_no_page(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                  capsys: pytest.CaptureFixture) -> None:
    root = make_workspace(tmp_path)
    run(monkeypatch, root, "--dry-run")
    assert not (root / "output" / "A99_Decisions.md").exists()
    assert "A99_Decisions.md" in capsys.readouterr().out
