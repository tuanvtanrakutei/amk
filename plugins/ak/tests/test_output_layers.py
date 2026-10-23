"""The two output layers, held by the conformance gate and the templates (A110).

A phase is read by a person; a register by an agent. When a round of decisions was applied
to one application's phases, the record leaked into the text and conformance still passed.
These checks are the person layer measured: they warn and never fail, so a document another
project already published keeps passing.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
for _path in (PACKAGE / "contracts", PACKAGE / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import decision_agenda as da  # noqa: E402
import decision_queue as dq  # noqa: E402
import errata_render as er  # noqa: E402
import validate_phase_conformance as checker  # noqa: E402

EN = Path("A99_Phase2_ScreenAnalysis_EN.md")
TEMPLATES = {
    1: "phase1-data-understanding.md", 2: "phase2-screen-analysis.md",
    3: "phase3-logic-processing.md", 4: "phase4-workflow-reconstruction.md",
    5: "phase5-document-integration.md",
}


def readability(body: str, path: Path = EN) -> dict[str, dict]:
    return {r["check"]: r for r in checker.readability_checks(2, body, path)}


def template(phase: int) -> str:
    return (PACKAGE / "templates" / TEMPLATES[phase]).read_text(encoding="utf-8")


# --- audience_declared -----------------------------------------------------------

def test_a_document_that_names_its_reader_passes() -> None:
    body = "# A99 - Phase 2\n\nAudience: person\n\n## Naming Convention\n\nText.\n"
    assert readability(body)["audience_declared"]["status"] == "PASS"


def test_a_document_that_does_not_name_its_reader_warns() -> None:
    body = "# A99 - Phase 2\n\n## Naming Convention\n\nAudience: person\n"
    result = readability(body)["audience_declared"]
    assert result["status"] == "WARN" and "Audience: person" in result["detail"]


def test_an_audience_line_inside_a_comment_does_not_count() -> None:
    body = "# A99\n\n<!-- Audience: person -->\n\n## Naming Convention\n"
    assert readability(body)["audience_declared"]["status"] == "WARN"


# --- must_not_list_size ------------------------------------------------------------

def must_not(items: int) -> str:
    rows = "".join(f"{n}. Legacy fact {n}; the replacement does it too (RA-0{n % 10}). See §{n}.\n"
                   "   A second line of the same item.\n" for n in range(1, items + 1))
    return f"# A99\n\nAudience: person\n\nWhat you must not get wrong:\n\n{rows}\n## Naming Convention\n"


def test_seven_items_pass() -> None:
    result = readability(must_not(7))["must_not_list_size"]
    assert result["status"] == "PASS" and result["detail"] == "7 item(s)"


def test_eight_items_warn() -> None:
    result = readability(must_not(8))["must_not_list_size"]
    assert result["status"] == "WARN" and "8 item(s); at most 7" in result["detail"]


def test_a_document_with_no_list_is_skipped_not_passed() -> None:
    assert readability("# A99\n\n## A\n\nText.\n")["must_not_list_size"]["status"] == "SKIP"


def test_the_list_ends_at_the_next_paragraph() -> None:
    body = must_not(3).replace("## Naming Convention", "A closing paragraph.\n\n1. Another list.\n")
    assert readability(body)["must_not_list_size"]["detail"] == "3 item(s)"


# --- citation_density --------------------------------------------------------------

WORDS = " ".join(["word"] * 39) + "."


def test_one_evidence_id_per_forty_words_passes() -> None:
    body = f"## A\n\n{WORDS} [A99-P1-CODE-001]\n"
    result = readability(body)["citation_density"]
    assert result["status"] == "PASS", result


def test_an_evidence_id_on_every_short_sentence_warns() -> None:
    body = "## A\n\n" + "".join(f"The import empties the table (A99-P5-TARGET-{n:03d}).\n"
                                for n in range(1, 6))
    result = readability(body)["citation_density"]
    assert result["status"] == "WARN" and "item code" in result["detail"]


def test_tables_code_and_the_evidence_register_are_not_prose() -> None:
    rows = "".join(f"| A99-P1-CODE-{n:03d} | EXTRACTED |\n" for n in range(1, 20))
    body = (f"## A\n\n{WORDS}\n\n| Claim | Evidence |\n|---|---|\n| x | A99-P1-CODE-001 |\n\n"
            f"```\nA99-P1-CODE-002 A99-P1-CODE-003\n```\n\n"
            f"## Evidence Register\n\n| ID | Status |\n|---|---|\n{rows}\nA99-P1-CODE-004 A99-P1-CODE-005\n")
    assert readability(body)["citation_density"]["status"] == "PASS"


def test_item_codes_are_not_evidence_ids() -> None:
    body = "## A\n\n" + "".join("The import empties the table (RA-04). " for _ in range(10)) + "\n"
    assert readability(body)["citation_density"]["status"] == "PASS"


def test_one_evidence_id_per_thirty_words_warns() -> None:
    """An id on most sentences, averaged over plain paragraphs, still reads as a record."""
    body = "## A\n\n" + (" ".join(["word"] * 29) + " [A99-P1-CODE-001]\n\n") * 4
    assert readability(body)["citation_density"]["status"] == "WARN"


def test_the_threshold_is_a_named_constant() -> None:
    assert checker.CITATION_WORDS_PER_ID == 40


# --- no_decision_history -----------------------------------------------------------

@pytest.mark.parametrize("sentence", [
    "The export keeps two columns; the earlier decision was superseded.",
    "RA-02 is decided again as fix.",
    "RA-02 was re-decided on the second day.",
    "The page replaces A99-P5-TARGET-012 (E-01).",
    "The new rule replaces the earlier decision.",
])
def test_history_in_the_text_warns(sentence: str) -> None:
    result = readability(f"## A\n\n{sentence}\n")["no_decision_history"]
    assert result["status"] == "WARN", sentence


@pytest.mark.parametrize("sentence", [
    "A second import replaces the first batch and keeps no history.",
    "The superseded variants of the order form are grouped in 5.2.",
    "The export keeps two columns (E-01).",
])
def test_a_fact_about_the_legacy_system_is_not_history(sentence: str) -> None:
    assert readability(f"## A\n\n{sentence}\n")["no_decision_history"]["status"] == "PASS", sentence


def test_a_closed_row_may_open_with_its_state_and_the_evidence_register_is_not_read() -> None:
    body = ("## Questions\n\n| ID | Question | Blocks | Party | Default |\n|---|---|---|---|---|\n"
            "| Q5 | **Superseded - Q9.** Who prints it? | F-001 | Office | — |\n\n"
            "## Evidence Register\n\nThe item superseded by E-02 stays listed.\n")
    assert readability(body)["no_decision_history"]["status"] == "PASS"


def test_history_inside_a_table_cell_warns() -> None:
    body = ("## Risks\n\n| ID | Risk | Severity | Detail | Mitigation | Decision |\n"
            "|---|---|---|---|---|---|\n| RA-02 | X | LOW | Y | Decided again: fix. | fix (RA-02) |\n")
    assert readability(body)["no_decision_history"]["status"] == "WARN"


def test_the_layer_checks_do_not_fail_a_run(tmp_path: Path) -> None:
    import test_phase_conformance as base

    base.write(tmp_path, "A99_Phase2_ScreenAnalysis_EN.md",
               "# A\n\n## B\n\nRA-02 is decided again (A99-P5-TARGET-001) (A99-P5-TARGET-002).\n")
    assert base.run(tmp_path, "--group", "readability") == 0


# --- evidence_links ----------------------------------------------------------------

LINKED = """## A

The import empties the table [A99-P1-CODE-004](#ev-a99-p1-code-004).

| ID | Observation | Evidence |
|---|---|---|
| OB-01 | The batch is kept | [A99-P5-DATA-002](#ev-a99-p5-data-002) |

## Evidence Register

| ID | Status | Class | Claim kind | Source | Confidence |
|---|---|---|---|---|---:|
| <a id="ev-a99-p1-code-004"></a>A99-P1-CODE-004 | EXTRACTED | CODE | BEHAVIOUR | module | 1.0 |
| <a id="ev-a99-p5-data-002"></a>A99-P5-DATA-002 | EXTRACTED | SAMPLE_DATA | FORMAT | sample | 1.0 |
"""


def test_the_anchor_is_the_id_in_lower_case_after_ev() -> None:
    assert checker.evidence_anchor("A99-P1-TABLE_INVENTORY-004") == "ev-a99-p1-table_inventory-004"


def test_citations_that_link_to_their_register_rows_pass() -> None:
    result = readability(LINKED)["evidence_links"]
    assert result["status"] == "PASS" and result["detail"].startswith("2 citation(s)")


def test_an_unlinked_citation_warns_in_prose_and_in_a_table() -> None:
    prose_only = LINKED.replace("[A99-P1-CODE-004](#ev-a99-p1-code-004)", "[A99-P1-CODE-004]")
    result = readability(prose_only)["evidence_links"]
    assert result["status"] == "WARN" and "A99-P1-CODE-004" in result["detail"]
    in_table = LINKED.replace("[A99-P5-DATA-002](#ev-a99-p5-data-002)", "A99-P5-DATA-002")
    assert "A99-P5-DATA-002" in readability(in_table)["evidence_links"]["detail"]


def test_a_link_to_an_anchor_the_document_lacks_warns() -> None:
    no_row = LINKED.replace('<a id="ev-a99-p5-data-002"></a>', "")
    result = readability(no_row)["evidence_links"]
    assert result["status"] == "WARN" and "A99-P5-DATA-002 -> #ev-a99-p5-data-002" in result["detail"]
    wrong = LINKED.replace("(#ev-a99-p1-code-004)", "(#ev-a99-p1-code-005)")
    assert readability(wrong)["evidence_links"]["status"] == "WARN"


def test_item_codes_and_the_register_itself_are_not_asked_for_links() -> None:
    body = LINKED.replace("The import empties the table", "The import empties the table (RA-04, D-EXPORT-NAME)")
    assert readability(body)["evidence_links"]["status"] == "PASS"
    listing = "## A\n\n| <a id=\"ev-a99-p1-code-004\"></a>A99-P1-CODE-004 | listed |\n"
    assert readability(listing)["evidence_links"]["status"] == "PASS"


def test_a_question_cleaned_for_the_list_loses_the_whole_link() -> None:
    assert da._clean("Who prints it? [A99-P2-UI-001](#ev-a99-p2-ui-001)") == "Who prints it?"


# --- decisions_agree ---------------------------------------------------------------

RISKS = """## 6. Risks

| ID | Risk | Severity | Consequence at migration | Mitigation | Decision | Evidence |
|---|---|---|---|---|---|---|
| RA-01 | Files lost | HIGH | lost orders | Import in one transaction | fix (RA-01) | A99-P2-CODE-001 |
| RA-02 | Date unused | LOW | none | Keep the edit | preserve (RA-02) | A99-P2-CODE-002 |
"""


def registers(*, word_ra02: str = "preserve", q_closed: bool = True) -> dict:
    evidence = {
        "A99-P5-TARGET-001": {"id": "A99-P5-TARGET-001", "evidence_class": "TARGET_INTENT",
                              "statement": dq.disposition_statement("RA-01", "fix", "Do it.")},
        "A99-P5-TARGET-002": {"id": "A99-P5-TARGET-002", "evidence_class": "TARGET_INTENT",
                              "statement": dq.disposition_statement("RA-02", word_ra02, "Keep it.")},
        "A99-P1-INTERVIEW-001": {"id": "A99-P1-INTERVIEW-001", "evidence_class": "INTERVIEW"},
    }
    entries = [
        {"id": "RA-01", "namespace": "RA-", "phase": 2, "resolved_by": "A99-P5-TARGET-001"},
        {"id": "RA-02", "namespace": "RA-", "phase": 2, "resolved_by": "A99-P5-TARGET-002"},
        {"id": "Q5", "namespace": "Q", "phase": 1,
         **({"resolved_by": "A99-P1-INTERVIEW-001"} if q_closed else {})},
    ]
    return {"identifier_entries": entries, "evidence_items": evidence}


def agree(text: str, regs: dict) -> dict:
    return next(r for r in checker.apparatus_checks(2, text, regs) if r["check"] == "decisions_agree")


def test_risk_rows_that_name_their_disposition_agree() -> None:
    result = agree(RISKS, registers())
    assert result["status"] == "PASS" and result["group"] == "apparatus"


def test_a_risk_row_that_names_another_disposition_warns_and_does_not_fail() -> None:
    result = agree(RISKS, registers(word_ra02="drop"))
    assert result["status"] == "WARN"
    assert "RA-02 is decided drop; its risk row does not say drop" in result["detail"]
    assert "RA-01" not in result["detail"]


def test_a_decided_risk_with_no_row_is_reported() -> None:
    result = agree(RISKS.split("| RA-02")[0], registers())
    assert "RA-02 is decided preserve and has no risk row" in result["detail"]


CARRIED = """### Carried forward from earlier phases

| ID | From phase | State | Closed by |
|---|---|---|---|
| Q5 | Phase 1 | {state} | {closer} |
"""


def test_a_carried_row_still_open_for_a_closed_item_warns() -> None:
    result = agree(RISKS + CARRIED.format(state="open", closer="—"), registers())
    assert result["status"] == "WARN"
    assert "Q5 is closed in the register (A99-P1-INTERVIEW-001) and its carried-forward row says open" \
        in result["detail"]


def test_the_old_carried_shape_saying_unchanged_warns_too() -> None:
    old = ("\n### Carried forward from earlier phases\n\n"
           "| ID | Raised in | Status | What this phase establishes |\n|---|---|---|---|\n"
           "| Q5 | Phase 1 | unchanged | nothing bears on it |\n")
    assert agree(RISKS + old, registers())["status"] == "WARN"


def test_a_carried_row_that_says_closed_agrees() -> None:
    assert agree(RISKS + CARRIED.format(state="closed", closer="Q5"), registers())["status"] == "PASS"
    assert agree(RISKS + CARRIED.format(state="open", closer="—"),
                 registers(q_closed=False))["status"] == "PASS"


def test_without_the_evidence_register_the_check_does_not_run() -> None:
    regs = registers()
    del regs["evidence_items"]
    assert not [r for r in checker.apparatus_checks(2, RISKS, regs) if r["check"] == "decisions_agree"]


# --- the templates -----------------------------------------------------------------

@pytest.mark.parametrize("phase", sorted(TEMPLATES))
def test_every_template_declares_its_reader_and_keeps_the_must_not_list(phase: int) -> None:
    results = {r["check"]: r for r in checker.readability_checks(
        phase, template(phase), Path(f"A99_Phase{phase}_X_EN.md"))}
    for name in ("audience_declared", "must_not_list_size", "citation_density", "no_decision_history",
                 "evidence_links"):
        assert results[name]["status"] == "PASS", (phase, name, results[name])
    text = template(phase)
    assert text.index("What you must not get wrong:") < text.index("## Naming Convention")
    assert "At most 7" in text


@pytest.mark.parametrize("phase", sorted(TEMPLATES))
def test_every_template_carries_the_citation_rules_and_one_decided_table(phase: int) -> None:
    text = template(phase)
    for rule in ("Cite a decision by its item code", "at most one code per claim",
                 "no decision history", "belongs in a catalogue"):
        assert rule.casefold() in text.casefold(), (phase, rule)
    assert text.count("## Decided for the replacement") == 1
    headers = [tuple(t.header) for t in dq.tables(text)]
    assert ("Item", "Decision", "Effect on this phase") in headers


@pytest.mark.parametrize("phase", sorted(TEMPLATES))
def test_every_template_states_the_writing_order_and_keeps_the_diagram_floor(phase: int) -> None:
    text = template(phase)
    assert "Writing order: prose first, then tables, then diagrams." in text
    assert "a diagram shows a mechanism" in text
    assert "One required diagram per phase is a floor" in text
    assert "write prose only for what neither can hold" not in text


@pytest.mark.parametrize("phase", sorted(TEMPLATES))
def test_every_template_links_its_citations_to_anchored_register_rows(phase: int) -> None:
    text = template(phase)
    assert "`[A99-P1-CODE-004](#ev-a99-p1-code-004)`" in text
    register = text[text.index("## Evidence Register"):]
    assert '`<a id="ev-a99-p1-code-004"></a>A99-P1-CODE-004`' in register


@pytest.mark.parametrize("phase", sorted(TEMPLATES))
def test_every_risk_table_has_a_decision_column_after_the_ones_read_by_position(phase: int) -> None:
    risk = next(t for t in dq.tables(template(phase)) if t.header[:3] == ["ID", "Risk", "Severity"])
    assert risk.header[4] == "Mitigation" and risk.header[5] == "Decision"
    # The decision tools read title, severity, detail and mitigation by position.
    cells = ["RA-01", "Title", "HIGH", "Detail", "Mitigation", "fix (RA-01)", "A99-P2-CODE-001"][
        :len(risk.header)]
    assert dq.risk_cells(cells, "RA-01")["mitigation"] == "Mitigation"


@pytest.mark.parametrize("phase", [2, 3, 4, 5])
def test_the_carried_forward_table_is_compact(phase: int) -> None:
    text = template(phase)
    assert "| ID | From phase | State | Closed by |" in text
    assert "| ID | Raised in | Status | What this phase establishes |" not in text


def test_phase2_points_to_the_catalogue_for_fields_and_controls() -> None:
    text = template(2)
    section = text[text.index("## 3. Per-Screen Analysis"):text.index("## 4. ")]
    assert "| User action | VBA event |" not in section
    for field in ("**Purpose:**", "**Who uses it:**", "**What differs in the replacement:**", "**Risks:**"):
        assert field in section
    assert "_ScreenCatalogue.md" in section and "_ToBe.json" in section and "150 words" in section


def test_phase5_is_the_developers_hand_off() -> None:
    text = template(5)
    hand_off = text[text.index("## Developer hand-off"):text.index("## Contents")]
    for part in ("### Target scope", "### Screens in scope", "### Interfaces and export specification",
                 "### Open points", "_Decisions.md"):
        assert part in hand_off, part
    assert "| Screen | Behaviour change in the replacement | Phase 2 section |" in hand_off
    # A question's own row stays the only one that opens with its id (`--assume` edits it).
    assert "| Open point | Item | Party |" in hand_off


PLACEHOLDERS = {"APP_ID", "ENTITY_NAME", "F_ID", "OBJECT_NAME", "PIPELINE_NAME", "FILE_NAME",
                "WF_ID", "WORKFLOW_NAME"}


@pytest.mark.parametrize("phase", sorted(TEMPLATES))
def test_the_layer_sections_add_no_placeholder_a_filled_document_would_leave(phase: int) -> None:
    text = template(phase)
    assert set(re.findall(r"\{\{([A-Z_]+)\}\}", text)) <= PLACEHOLDERS
    filled = re.sub(r"\{\{[A-Z_]+\}\}", "X", text)
    result = next(r for r in checker.content_checks(phase, filled) if r["check"] == "no_unfilled_placeholders")
    assert result["status"] == "PASS"


def test_the_template_tables_still_parse_as_the_decision_tools_read_them() -> None:
    for phase in TEMPLATES:
        headers = {tuple(t.header) for t in dq.tables(template(phase))}
        assert ("ID", "Question", "Blocks", "Party", "Default") in headers
        assert ("ID", "Assumption", "If wrong") in headers


# --- the generated pages -------------------------------------------------------------

def test_the_errata_page_and_the_question_list_name_their_reader() -> None:
    errata = er.render([], "A99").splitlines()
    assert errata[0].startswith(er.GENERATED) and "Audience: person" in errata[:5]
    queue = da.build_queue([], None, app_id="A99")
    listing = da.render_markdown(queue).splitlines()
    assert listing[0].startswith(da.GENERATED) and "Audience: person" in listing[:5]
    assert "Audience: person" not in da.render_markdown(queue, only="decider")


def test_the_output_contract_lists_the_page_and_the_layers() -> None:
    import yaml

    contract = yaml.safe_load((PACKAGE / "specifications" / "output-contract.yaml").read_text(encoding="utf-8"))
    assert "{APP_ID}_Decisions.md" in contract["required_control_outputs"]
    layers = contract["output_layers"]
    assert layers["bridge"]["artefacts"] == ["{APP_ID}_Decisions.md"]
    assert "{APP_ID}_Errata.md" in layers["person"]["artefacts"]
    assert "{APP_ID}_Identifiers.json" in layers["record"]["artefacts"]
