from __future__ import annotations

import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
MODERNIZE_SCRIPTS = PACKAGE / "modernize" / "scripts"
sys.path.insert(0, str(MODERNIZE_SCRIPTS))

import validate_docs  # noqa: E402


def test_instance_placeholder_examples_and_report_are_ignored(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    report = docs / "validate-docs-report.md"
    (docs / "MASTER_WORKFLOW.md").write_text(
        "Example {{PLACEHOLDER}} and unresolved {{REAL_PROJECT_KEY}}.\n",
        encoding="utf-8",
    )
    report.write_text("Old finding for {{STALE_REPORT_KEY}}.\n", encoding="utf-8")

    findings = validate_docs.Findings()
    validate_docs.check_placeholders_in_instance(findings, str(docs), {str(report)})

    assert findings.rows == [
        (
            "MEDIUM",
            "unresolved-placeholder",
            "MASTER_WORKFLOW.md:1",
            "{{REAL_PROJECT_KEY}} was never substituted",
        )
    ]


def test_plugin_templates_resolve_document_references(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    plugin = tmp_path / "plugin"
    docs.mkdir()
    (plugin / "templates").mkdir(parents=True)
    (docs / "FRONTEND_CODING.md").write_text(
        "Use `templates/FRONTEND_API_PATTERNS_TEMPLATE.md` and "
        "`templates/FRONTEND_UI_PATTERNS_TEMPLATE.md`.\n",
        encoding="utf-8",
    )
    for name in ("FRONTEND_API_PATTERNS_TEMPLATE.md", "FRONTEND_UI_PATTERNS_TEMPLATE.md"):
        (plugin / "templates" / name).write_text("template\n", encoding="utf-8")

    findings = validate_docs.Findings()
    validate_docs.check_dangling_doc_refs(findings, str(docs), [str(plugin)])

    assert findings.rows == []


def test_issue_citations_scan_code_but_not_markdown(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    source = tmp_path / "source"
    docs.mkdir()
    source.mkdir()
    issues = docs / "Known_Issues.md"
    issues.write_text(
        "| # | Date | Type | Title | Affects | Status | Owner | Decision / Next step |\n"
        "|---|---|---|---|---|---|---|---|\n"
        "| 1 | 2026-08-10 | process | Existing | all | open | — | — |\n",
        encoding="utf-8",
    )
    (source / "Known_Issues_Archive.md").write_text("Example Known_Issues.md #12.\n", encoding="utf-8")
    (source / "validate-docs-report.md").write_text("Old finding Known_Issues.md #13.\n", encoding="utf-8")
    (source / "service.py").write_text("# Known_Issues.md #14\n", encoding="utf-8")

    findings = validate_docs.Findings()
    validate_docs.check_issues(findings, str(docs), str(issues), str(source))

    assert findings.rows == [
        (
            "HIGH",
            "dangling-issue-ref",
            "service.py",
            "code cites Known_Issues.md #14 but no such row exists",
        )
    ]


# --- A69: the plugin's own documents against the plugin's own template --------
#
# `FRONTEND_CODING.md` section 15.2 says to run every frontend command through
# `{{PACKAGE_MANAGER}}`, and `templates/PROJECT_CONFIG.md` declared no such row. Every
# project bootstrapped from that template inherited a rule it could not follow, and the
# check that finds it only ran once somebody pointed it at a real project. The two files
# ship together, so they can be checked together here.


def test_the_plugin_docs_only_consume_keys_its_own_template_declares() -> None:
    plugin = PACKAGE / "modernize"
    findings = validate_docs.Findings()
    validate_docs.check_config(
        findings,
        str(plugin / "docs"),
        str(plugin),
        str(plugin / "templates" / "PROJECT_CONFIG.md"),
    )
    missing = [row for row in findings.rows if row[1] == "missing-config-key"]
    assert not missing, missing


# --- A71: a citation qualified by another subsystem is not a broken one -------
#
# One subsystem's backend inherited `auth_client` and `format_bulk_validation_errors` from
# another, and the comments that explain why they exist cite the other's issue rows. Scanned
# as if they were its own, they read as two dangling references, and three more came from walking into
# `.claude`, a symlink to the plugin whose own test fixtures cite issue numbers.


def test_a_citation_qualified_by_another_subsystem_is_not_dangling(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    source = tmp_path / "src"
    docs.mkdir()
    source.mkdir()
    (docs / "Known_Issues.md").write_text("# log\n", encoding="utf-8")
    (source / "conftest.py").write_text(
        "# Inherited from A98 - see A98 Known_Issues.md #41.\n", encoding="utf-8")

    findings = validate_docs.Findings()
    validate_docs.check_issues(findings, str(docs), str(docs / "Known_Issues.md"),
                               str(source))

    assert [r for r in findings.rows if r[1] == "dangling-issue-ref"] == []


def test_an_unqualified_citation_with_no_row_is_still_dangling(tmp_path: Path) -> None:
    """The check has to keep working - this is the defect it was written for."""
    docs = tmp_path / "docs"
    source = tmp_path / "src"
    docs.mkdir()
    source.mkdir()
    (docs / "Known_Issues.md").write_text("# log\n", encoding="utf-8")
    (source / "svc.py").write_text("# See Known_Issues.md #41.\n", encoding="utf-8")

    findings = validate_docs.Findings()
    validate_docs.check_issues(findings, str(docs), str(docs / "Known_Issues.md"),
                               str(source))

    rows = [r for r in findings.rows if r[1] == "dangling-issue-ref"]
    assert len(rows) == 1 and "#41" in rows[0][3]


def test_the_scan_does_not_walk_into_dot_claude(tmp_path: Path) -> None:
    """`.claude/ak-runtime` is a symlink to the plugin on a real project, and the
    plugin's own tests cite issue numbers that are fixtures."""
    docs = tmp_path / "docs"
    source = tmp_path / "src"
    docs.mkdir()
    (source / ".claude" / "tests").mkdir(parents=True)
    (source / ".claude" / "tests" / "test_x.py").write_text(
        "# See Known_Issues.md #12.\n", encoding="utf-8")
    (docs / "Known_Issues.md").write_text("# log\n", encoding="utf-8")

    findings = validate_docs.Findings()
    validate_docs.check_issues(findings, str(docs), str(docs / "Known_Issues.md"),
                               str(source))

    assert [r for r in findings.rows if r[1] == "dangling-issue-ref"] == []


def _registry(tmp_path: Path, *rows: str) -> list:
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    path = docs / "Screens_Registry.md"
    path.write_text(
        "| screen | screen_key | status_be | status_fe | rule_prefix |\n"
        "|---|---|---|---|---|\n" + "".join(r + "\n" for r in rows),
        encoding="utf-8",
    )
    findings = validate_docs.Findings()
    validate_docs.check_registry(findings, str(docs), str(path))
    return [(sev, kind) for sev, kind, _where, _why in findings.rows]


def test_a_rule_prefix_must_have_the_shape_rule_ids_are_read_back_by(tmp_path: Path) -> None:
    rows = _registry(
        tmp_path,
        "| Order entry | order-entry | verified | verified | ORD |",
        "| Stock | stock | verified | verified | stk |",
        "| Location | location | verified | verified | LOC-1 |",
        "| Reason | reason | verified | verified | TOOLONGX |",
    )
    assert rows == [("HIGH", "registry-rule-prefix-invalid")] * 3


def test_two_screens_may_not_declare_the_same_rule_prefix(tmp_path: Path) -> None:
    rows = _registry(
        tmp_path,
        "| Order entry | order-entry | verified | verified | ORD |",
        "| Order list | order-list | verified | verified | `ORD` |",
    )
    assert rows == [("HIGH", "registry-rule-prefix-duplicate")]


def test_every_documented_registry_status_passes_and_an_undocumented_one_does_not(tmp_path: Path) -> None:
    rows = _registry(
        tmp_path,
        "| Order entry | order-entry | partial | blocked | ORD |",
        "| Order list | order-list | not_started | implemented | OLS |",
        "| Stock | stock | verified | `partial` | STK |",
        "| Location | location | in_progress | deferred | LOC |",
    )
    assert rows == [("MEDIUM", "registry-status-unknown")] * 2


def test_an_empty_rule_prefix_or_no_column_is_not_a_finding(tmp_path: Path) -> None:
    assert _registry(
        tmp_path,
        "| Order entry | order-entry | verified | verified |  |",
        "| Order list | order-list | verified | verified | — |",
        "| Template | {{SCREEN_KEY}} | verified | verified | {{RULE_PREFIX}} |",
    ) == []
    docs = tmp_path / "plain"
    docs.mkdir()
    path = docs / "Screens_Registry.md"
    path.write_text("| screen | screen_key | status_be | status_fe |\n|---|---|---|---|\n| A | a | verified | verified |\n", encoding="utf-8")
    findings = validate_docs.Findings()
    validate_docs.check_registry(findings, str(docs), str(path))
    assert findings.rows == []


def test_a_citation_qualified_in_parentheses_is_not_dangling(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    source = tmp_path / "src"
    docs.mkdir()
    source.mkdir()
    (docs / "Known_Issues.md").write_text("# log\n", encoding="utf-8")
    (source / "auth.py").write_text("# Ported from A98 (Known_Issues.md #14).\n", encoding="utf-8")

    findings = validate_docs.Findings()
    validate_docs.check_issues(findings, str(docs), str(docs / "Known_Issues.md"), str(source))

    assert [r for r in findings.rows if r[1] == "dangling-issue-ref"] == []


def _checklist_project(tmp_path: Path, registry_row: str) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    (repo / "backend" / "app" / "orders").mkdir(parents=True)
    evidence = tmp_path / "workspace" / "input" / "screenshots"
    evidence.mkdir(parents=True)
    (docs / "PROJECT_CONFIG.md").write_text(
        "| `BACKEND_ROOT` | `backend/app` | x |\n"
        f"| `EVIDENCE_UI_DIR` | `{evidence.as_posix()}` | x |\n"
        "| `EVIDENCE_OUTPUT_DIR` | `n/a` | none supplied |\n"
        f"| `AK_RUN_DIR` | `{(tmp_path / 'workspace').as_posix()}` | x |\n"
        "\n### Modules\n\n| module | url prefix | owns |\n|---|---|---|\n"
        "| `orders` | `orders/` | the order screens |\n"
        "| `master` | `master/` | the store master |\n\n### Shared Backend Components\n",
        encoding="utf-8")
    (docs / "Screens_Registry.md").write_text(
        "## Active Screens\n\n| # | screen | screen_key | status_be | status_fe |\n|---|---|---|---|---|\n"
        + registry_row + "\n\n## Future Scope\n", encoding="utf-8")
    return repo, docs


def test_the_checklist_reports_a_module_without_an_app_and_an_empty_evidence_folder(tmp_path: Path) -> None:
    repo, docs = _checklist_project(tmp_path, "| 1 | `{{SCREEN_1}}` | `{{SCREEN_1_KEY}}` | `not_started` | `not_started` |")

    findings = validate_docs.Findings()
    validate_docs.check_checklist(findings, str(docs), str(docs / "PROJECT_CONFIG.md"),
                                  str(docs / "Screens_Registry.md"), str(repo))

    kinds = sorted((r[1], r[3].split(" ")[1] if r[1] == "checklist-module-missing" else r[3][:15])
                   for r in findings.rows)
    assert ("checklist-module-missing", "`master`") in kinds
    assert not any("`orders`" in r[3] for r in findings.rows)
    assert any(r[1] == "checklist-evidence-missing" and "EVIDENCE_UI_DIR" in r[3] for r in findings.rows)
    assert any(r[1] == "checklist-registry-empty" for r in findings.rows)
    assert not any("EVIDENCE_OUTPUT_DIR" in r[3] for r in findings.rows)


def test_the_checklist_is_quiet_on_a_project_that_meets_it(tmp_path: Path) -> None:
    repo, docs = _checklist_project(tmp_path, "| 1 | `受注照会` | `screen-F001` | `not_started` | `not_started` |")
    (repo / "backend" / "app" / "master").mkdir()
    (tmp_path / "workspace" / "input" / "screenshots" / "f.png").write_bytes(b"x")

    findings = validate_docs.Findings()
    validate_docs.check_checklist(findings, str(docs), str(docs / "PROJECT_CONFIG.md"),
                                  str(docs / "Screens_Registry.md"), str(repo))

    assert findings.rows == []


def test_the_checklist_reports_a_design_document_that_is_not_there(tmp_path: Path) -> None:
    repo, docs = _checklist_project(tmp_path, "| 1 | `受注照会` | `screen-F001` | `not_started` | `not_started` |")
    (repo / "backend" / "app" / "master").mkdir()
    (tmp_path / "workspace" / "input" / "screenshots" / "f.png").write_bytes(b"x")
    (repo / "PATTERNS.md").write_text("x\n", encoding="utf-8")
    config = docs / "PROJECT_CONFIG.md"
    config.write_text(config.read_text(encoding="utf-8")
                      + "| `FE_PATTERN_DOCS` | `PATTERNS.md` | x |\n| `UI_DESIGN_DOC` | `UI-DESIGN.md` | x |\n",
                      encoding="utf-8")

    findings = validate_docs.Findings()
    validate_docs.check_checklist(findings, str(docs), str(config), str(docs / "Screens_Registry.md"), str(repo))

    assert [(r[1], "UI-DESIGN.md" in r[3]) for r in findings.rows] == [("checklist-doc-missing", True)]


def test_the_checklist_reports_a_required_key_left_not_applicable(tmp_path: Path) -> None:
    repo, docs = _checklist_project(tmp_path, "| 1 | `受注照会` | `screen-F001` | `not_started` | `not_started` |")
    (repo / "backend" / "app" / "master").mkdir()
    (tmp_path / "workspace" / "input" / "screenshots" / "f.png").write_bytes(b"x")
    config = docs / "PROJECT_CONFIG.md"
    config.write_text(config.read_text(encoding="utf-8")
                      + "| `FE_E2E_TEST_CMD` | `n/a` | no config yet |\n"
                      + "| `FE_UNIT_TEST_CMD` | `n/a` | no unit test runner |\n",
                      encoding="utf-8")

    findings = validate_docs.Findings()
    validate_docs.check_checklist(findings, str(docs), str(config), str(docs / "Screens_Registry.md"), str(repo))

    assert [(r[0], r[1], r[3].split(" ")[0]) for r in findings.rows] == [
        ("HIGH", "checklist-required-na", "FE_E2E_TEST_CMD")]


# --- A114: External_Dependencies.md, read against its template's vocabulary -----
#
# The review queue counts a dependency's due date from `Sent on` and skips `done` rows, so a
# sent row without a date, a state nobody defined, or one ID on two rows each loses or
# doubles an item. The states are read from the template, not copied (A103).

DEPENDENCIES_HEADER = (
    "# External Dependencies\n\n## Dependencies\n\n"
    "| ID | Party | Ask | Source decision | Blocks | State | Sent on | Due | Link |\n"
    "|---|---|---|---|---|---|---|---|---|\n"
)


def _dependencies(tmp_path: Path, *rows: str) -> list[tuple[str, str, str]]:
    docs = tmp_path / "docs"
    docs.mkdir()
    path = docs / "External_Dependencies.md"
    path.write_text(DEPENDENCIES_HEADER + "".join(r + "\n" for r in rows), encoding="utf-8")
    findings = validate_docs.Findings()
    validate_docs.check_dependencies(findings, str(docs), str(path), validate_docs.dependency_states())
    return [(r[0], r[1], r[2].rsplit(":", 1)[1]) for r in findings.rows]


def test_the_dependency_states_are_read_from_the_template() -> None:
    assert validate_docs.dependency_states() == {"to-send", "sent", "in-progress", "done"}


def test_well_formed_dependency_rows_pass(tmp_path: Path) -> None:
    assert _dependencies(
        tmp_path,
        "| EXT-01 | Stock team | add a flag | Q1 | OrderEntry | to-send | | | |",
        "| EXT-02 | Stock team | open an interface | Q2 | — | `sent` | 2026-01-02 | | |",
        "| EXT-03 | Billing | widen a field | Q3 | OrderList | in-progress | 2026-01-03 | 2026-02-01 | x |",
        "| EXT-04 | Billing | rename a column | Q4 | OrderList | done | | | |",
    ) == []


def test_a_sent_or_in_progress_row_needs_a_sent_on_date(tmp_path: Path) -> None:
    assert _dependencies(
        tmp_path,
        "| EXT-01 | Stock team | add a flag | Q1 | OrderEntry | sent | | | |",
        "| EXT-02 | Stock team | add a flag | Q1 | OrderEntry | in-progress | last week | | |",
    ) == [("MEDIUM", "external-sent-on-missing", "7"), ("MEDIUM", "external-sent-on-missing", "8")]


def test_dependency_ids_are_unique_and_states_in_the_vocabulary(tmp_path: Path) -> None:
    assert _dependencies(
        tmp_path,
        "| EXT-01 | Stock team | add a flag | Q1 | OrderEntry | to-send | | | |",
        "| EXT-01 | Stock team | add another | Q1 | OrderEntry | waiting | | | |",
    ) == [("HIGH", "external-id-duplicate", "8"), ("MEDIUM", "external-state-unknown", "8")]


def test_the_template_itself_is_a_clean_dependency_file() -> None:
    template = PACKAGE / "modernize" / "templates" / "External_Dependencies.md"
    findings = validate_docs.Findings()
    validate_docs.check_dependencies(findings, str(template.parent), str(template),
                                     validate_docs.dependency_states())
    assert findings.rows == []


def test_a_key_a_script_reads_by_name_is_not_dead() -> None:
    plugin = PACKAGE / "modernize"
    findings = validate_docs.Findings()
    validate_docs.check_config(findings, str(plugin / "docs"), str(plugin),
                               str(plugin / "templates" / "PROJECT_CONFIG.md"))
    assert not [r for r in findings.rows if r[1] == "dead-config-key" and "REVIEW_DUE_DAYS" in r[3]]
