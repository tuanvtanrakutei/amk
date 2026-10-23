#!/usr/bin/env python3
"""Write the review queue: everything in a project that waits on a person, on one page (A111).

    python3 review_queue.py --repo <modernize repo> [--docs-dir DIR] [--workspace DIR]
                            [--dry-run] [--force]

Agents maintain the investigation phases and the modernize documents; people review and
decide. What waits on a person was spread over six places, and no page said what an owner
had to do today. This reads each of them and writes two files into the repo's docs folder:

  Review_Queue.md      read by a person (`Audience: person`): a count line, then one table
                       sorted by risk, kind and screen
  review_queue.json    read by agents and the pipeline: the same items, with every field

Sources, each read only when it exists:

  decision queue       `{APP}_DecisionQueue.json` in the investigation workspace, as
                       `$ak decisions` wrote it: open items an owner can act on now (blocking,
                       proceeding on a default, waiting behind another item, answered by the
                       customer and not recorded). Items already with the customer and items a
                       standing policy settled are counted in a note, not listed.
  errata               `{APP}_Errata.json` entries with no `acknowledged_by`: a correction to a
                       published claim waits until a person confirms it.
  coding records       `Coding_Records/{screen}.md` 7.1 Pending Answers rows not yet answered:
                       the track is `blocked` while one is open.
  screen plans         `Screen_plans/{screen}.md` gap-matrix rows `open` and mapping rows
                       `open-decision` that cite no decision-queue item: a decision the queue
                       cannot route. A row citing an item is the queue's, and listed there.
  test instructions    `Test_Instruction/{screen}.md` 4.4 Tier 3 rows with no `Verified by`.
  final acceptance     `Final_Acceptance/{screen}.md` whose User decision is `pending`.
  issue log            `Known_Issues.md` Active Log rows `open` of type `business` or
                       `legacy-bug` (a decision needed) and `traceability` rows `open (HIGH)`,
                       unless the row points at a decision-queue item.
  registry             a `blocked` track in `Screens_Registry.md` that nothing above names.

Risk comes from the source's own severity or blocking flag; `RISK_RULES` below is the mapping.
No source carries a due date, so every item is `waiting`; `overdue` is reserved.

The workspace is `--workspace`, else `AK_RUN_DIR` in `PROJECT_CONFIG.md` resolved against the
repository root, else the repository's parent folder when it is a workspace (`manifest.yaml`
beside `output/`), which is where bootstrap looks.

No date in either file, so the same state gives the same bytes. Neither file is overwritten
when this script did not write it, unless `--force`.

Exit 0 when written (or with --dry-run), 1 when a file it did not write is in the way, 2 when
it cannot run.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

GENERATED_MD = "<!-- generated-by: ak review-queue"
GENERATED_BY = "ak review-queue"
PAGE = "Review_Queue.md"
DATA = "review_queue.json"

KINDS = ("decision", "erratum", "plan approval", "test sign-off", "review", "issue")
RISKS = ("high", "medium", "low")
SEVERITY = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

# What sets each item's risk. Printed in the skill and the backlog entry; one place in code.
RISK_RULES = {
    "decision (queue)": "high when no default (BLOCKING) or the item, or what it blocks, is HIGH; "
                        "medium when MEDIUM; low otherwise",
    "decision (coding record)": "high: the track is blocked while the question is open",
    "erratum": "the entry's severity; medium when it has none",
    "plan approval": "medium",
    "test sign-off": "medium",
    "review": "high when the recommendation is not approve or approve with follow-ups; medium otherwise",
    "issue": "high for `open (HIGH)` and for a blocked track; otherwise the row's severity suffix, "
             "medium when it has none",
}

# Buckets of the decision queue an owner acts on now (decision_agenda.BUCKETS).
ACTIONABLE = ("blocking", "proceeding", "waiting", "to_record")
DECIDER = "decider"
CHOICES = ("fix", "preserve", "drop", "defer")
# An identifier the decision queue routes: a question, an unknown or a risk.
QUEUE_ID = re.compile(r"(?<![A-Za-z0-9_-])(?:Q[0-9]{1,3}|UK-[A-Z][0-9]{2}|R[DAWS]-[A-Z0-9]{1,6})(?![A-Za-z0-9_-])")
F_ID = re.compile(r"(?<![A-Za-z0-9_-])F-[0-9]+(?![A-Za-z0-9_-])")
BLANK = {"", "-", "–", "—", "n/a", "none", "tbd"}
ASK_LIMIT = 220


class CannotRun(Exception):
    """An input that cannot be used. The message says which."""


# --- small readers ----------------------------------------------------------------

def norm(text: Any) -> str:
    """A name as compared: NFC, whitespace collapsed, markup stripped. Never fuzzy."""
    value = unicodedata.normalize("NFC", str(text if text is not None else ""))
    return " ".join(value.replace("`", "").replace("**", "").split())


def blank(text: Any) -> bool:
    return norm(text).casefold() in BLANK


def short(text: Any, limit: int = ASK_LIMIT) -> str:
    value = norm(text)
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def read_json(path: Path) -> Any:
    try:
        return json.loads(read_text(path))
    except (OSError, json.JSONDecodeError) as error:
        raise CannotRun(f"{path} cannot be read: {error}") from error


def posix(path: Path, base: Path) -> str:
    try:
        return Path(os.path.relpath(path, base)).as_posix()
    except ValueError:
        return path.as_posix()


def config_value(config: str, key: str) -> str:
    match = re.search(r"^\|\s*`%s`\s*\|([^|]*)\|" % re.escape(key), config, re.M)
    return match.group(1).strip().strip("`").strip() if match else ""


def tables(text: str, heading: re.Pattern[str]) -> list[tuple[list[str], list[tuple[int, list[str]]]]]:
    """Each table under a heading matching `heading`, up to the next heading of that level or higher.

    A table is (header cells lower-cased, [(line number, cells)]). A separator row and a row
    that repeats the header are dropped.
    """
    lines = text.split("\n")
    found: list[tuple[list[str], list[tuple[int, list[str]]]]] = []
    level = None
    header: list[str] | None = None
    rows: list[tuple[int, list[str]]] = []

    def close() -> None:
        nonlocal header, rows
        if header is not None:
            found.append((header, rows))
        header, rows = None, []

    for number, line in enumerate(lines, 1):
        mark = re.match(r"^(#{1,6})\s+(.*)$", line)
        if mark:
            depth = len(mark.group(1))
            if level is not None and depth <= level:
                close()
                level = None
            if level is None and heading.search(mark.group(2)):
                level = depth
            continue
        if level is None:
            continue
        if not line.startswith("|"):
            close()
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            header = [norm(c).casefold() for c in cells]
            continue
        if all(set(c) <= set("-: ") for c in cells):
            continue
        if [norm(c).casefold() for c in cells] == header:
            continue
        rows.append((number, cells))
    close()
    return found


def column(header: list[str], *names: str) -> int | None:
    for name in names:
        for index, cell in enumerate(header):
            if cell == name or cell.startswith(name):
                return index
    return None


def cell(cells: list[str], index: int | None) -> str:
    return cells[index] if index is not None and index < len(cells) else ""


def queue_ids(text: str) -> list[str]:
    blanked = re.sub(r"`[^`\n]*`", lambda m: " " * len(m.group(0)), text)
    return QUEUE_ID.findall(blanked)


# --- the project -----------------------------------------------------------------

class Project:
    """Where the repo's docs and the investigation workspace are, and the screen names."""

    def __init__(self, repo: Path, docs: Path | None, workspace: Path | None) -> None:
        self.repo = repo.resolve()
        if not self.repo.is_dir():
            raise CannotRun(f"--repo {repo} is not a directory")
        self.docs = (docs if docs is not None else self._find_docs()).resolve()
        if not self.docs.is_dir():
            raise CannotRun(f"the docs folder {self.docs} does not exist")
        config = self.docs / "PROJECT_CONFIG.md"
        self.config = read_text(config) if config.is_file() else ""
        self.notes: list[str] = []
        self.workspace = self._find_workspace(workspace)
        self.screens = self._registry_screens()

    def _find_docs(self) -> Path:
        default = self.repo / "docs"
        if (default / "PROJECT_CONFIG.md").is_file():
            return default
        found = sorted(p.parent for p in self.repo.glob("*/PROJECT_CONFIG.md"))
        if len(found) == 1:
            return found[0]
        return default

    def _find_workspace(self, given: Path | None) -> Path | None:
        if given is not None:
            if not given.is_dir():
                raise CannotRun(f"--workspace {given} is not a directory")
            return given.resolve()
        value = config_value(self.config, "AK_RUN_DIR")
        if value and not value.lower().startswith("n/a") and "{{" not in value:
            path = Path(value) if os.path.isabs(value) else self.repo / value
            if path.is_dir():
                return path.resolve()
            self.notes.append(f"`AK_RUN_DIR` is `{value}`, which does not exist; the workspace was not read")
            return None
        parent = self.repo.parent
        if (parent / "manifest.yaml").is_file() and (parent / "output").is_dir():
            return parent.resolve()
        self.notes.append("no investigation workspace was found (`AK_RUN_DIR` unset and the repository's "
                          "parent is not one), so no decision or erratum was read")
        return None

    def rel(self, path: Path) -> str:
        return posix(path, self.repo)

    def register(self, pattern: str) -> Path | None:
        if self.workspace is None:
            return None
        for where in (self.workspace / "output" / "registers", self.workspace / "output", self.workspace):
            found = sorted(where.glob(pattern))
            if len(found) > 1:
                self.notes.append(f"{len(found)} files match {pattern} under {self.rel(where)}; "
                                  f"{found[0].name} was read")
            if found:
                return found[0]
        return None

    def ak_root(self) -> str:
        return self.rel(self.workspace) if self.workspace is not None else "<workspace>"

    def _registry_screens(self) -> list[dict[str, str]]:
        path = self.docs / "Screens_Registry.md"
        if not path.is_file():
            return []
        screens: list[dict[str, str]] = []
        for header, rows in tables(read_text(path), re.compile(r"^Active Screens\b", re.I)):
            i_screen = column(header, "screen")
            i_be, i_fe = column(header, "status_be"), column(header, "status_fe")
            for _number, cells in rows:
                name = norm(cell(cells, i_screen))
                if not name or "{{" in name:
                    continue
                screens.append({"screen": name, "status_be": norm(cell(cells, i_be)),
                                "status_fe": norm(cell(cells, i_fe))})
        return screens

    def names(self) -> set[str]:
        return {s["screen"] for s in self.screens}


def outputs(register: Path) -> Path:
    """The folder of the person-layer pages: `output/`, beside `output/registers/`."""
    return register.parent.parent if register.parent.name == "registers" else register.parent


# --- items ------------------------------------------------------------------------

def make(kind: str, risk: str, screens: list[str], ask: str, evidence: str, how: str,
         source: str, ident: str, **extra: Any) -> dict[str, Any]:
    item = {"id": ident, "kind": kind, "risk": risk, "screens": sorted(set(screens)),
            "ask": short(ask), "evidence": evidence, "how_to_record": how, "source": source,
            "status": "waiting"}
    item.update(extra)
    return item


class ScreenNames:
    """`F-` identifier -> the registry's screen name, matched by the register's title, exactly."""

    def __init__(self, project: Project) -> None:
        self.registry = project.names()
        self.titles: dict[str, str] = {}
        path = project.register("*_Identifiers.json")
        if path is not None:
            data = read_json(path)
            for entry in (data.get("entries") if isinstance(data, dict) else None) or []:
                if isinstance(entry, dict) and str(entry.get("id") or "").startswith("F-"):
                    self.titles[str(entry["id"])] = norm(entry.get("title"))

    def of(self, identifier: str, title: str = "") -> str:
        name = norm(title) or self.titles.get(identifier, "")
        if name in self.registry:
            return name
        return f"{identifier} {name}".strip()

    def in_text(self, text: str) -> list[str]:
        found = [self.of(f) for f in F_ID.findall(text)]
        found += [name for name in self.registry if name and name in norm(text)]
        return found


def decision_items(project: Project, names: ScreenNames) -> tuple[list[dict[str, Any]], set[str]]:
    """Open decision-queue items an owner can act on, and every id the queue knows."""
    path = project.register("*_DecisionQueue.json")
    if path is None:
        if project.workspace is not None:
            project.notes.append("the workspace has no `*_DecisionQueue.json`; run `$ak decisions --app-root "
                                 f"{project.ak_root()}` to build it")
        return [], set()
    data = read_json(path)
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise CannotRun(f"{path} is not a decision queue (no `items` list)")
    app = str(data.get("app_id") or "")
    known = {str(i.get("id")) for i in data["items"] if isinstance(i, dict)}
    known |= {str(c.get("id")) for c in data.get("closed") or [] if isinstance(c, dict)}
    source = project.rel(path)
    page = project.rel(outputs(path) / f"{app}_QuestionList.md") if app else source
    ws = project.ak_root()
    items: list[dict[str, Any]] = []
    elsewhere = {"with_customer": 0, "settled": 0}
    for entry in data["items"]:
        if not isinstance(entry, dict):
            continue
        bucket = str(entry.get("bucket") or "")
        if bucket in elsewhere:
            elsewhere[bucket] += 1
            continue
        if bucket not in ACTIONABLE:
            continue
        ident = str(entry.get("id") or "")
        title = norm(entry.get("title"))
        kind = str(entry.get("kind") or "")
        party = str(entry.get("party") or "")
        blocks = [b for b in entry.get("blocks") or [] if isinstance(b, dict)]
        screens = [names.of(str(b["id"]), str(b.get("title") or "")) for b in blocks
                   if str(b.get("id") or "").startswith("F-")]
        severity = max([SEVERITY.get(str(b.get("severity")), 0) for b in blocks]
                       + [SEVERITY.get(str(entry.get("severity")), 0)])
        if entry.get("posture") == "BLOCKING" or severity == 3:
            risk = "high"
        elif severity == 2:
            risk = "medium"
        else:
            risk = "low"
        default = entry.get("default")
        if bucket == "to_record":
            qa = ", ".join(str(q.get("id")) for q in (entry.get("customer") or {}).get("qa") or [])
            ask = f"The customer answered {ident} (Q&A {qa}): does that answer settle it? {title}"
            how = (f"record the answer as INTERVIEW evidence, set `resolved_by` on {ident} in "
                   f"`{app}_Identifiers.json`, then `$ak decisions --app-root {ws}`")
        elif party == DECIDER or kind in ("DISPOSITION", "SCOPE", "POLICY"):
            options = entry.get("options") or (list(CHOICES) if kind == "DISPOSITION" else [])
            choice = (" Choose " + " / ".join(str(o) for o in options) + "." if options else "")
            lean = (" Default: fix, as its Mitigation says." if isinstance(default, dict)
                    and default.get("mitigation") else "")
            ask = f"{ident} {title}.{choice}{lean}"
            how = f"`$ak decisions --app-root {ws} --decide --by <name>`"
        else:
            lean = ""
            if isinstance(default, dict) and default.get("id"):
                lean = f" Work proceeds meanwhile on {default['id']}."
            ask = f"Ask {party or 'the party named'}: {title}{lean}"
            how = (f"record the answer as INTERVIEW evidence and set `resolved_by` on {ident}, then "
                   f"`$ak decisions --app-root {ws}`; to proceed before it arrives, "
                   f"`$ak decisions --app-root {ws} --assume {ident} --that <...> --if-wrong <...> --by <name>`")
        evidence = f"{page} {ident}"
        if entry.get("evidence_ids"):
            evidence += " (" + ", ".join(str(e) for e in entry["evidence_ids"][:3]) + ")"
        items.append(make("decision", risk, screens, ask, evidence, how, source, f"decision:{ident}",
                          source_id=ident))
    if elsewhere["with_customer"]:
        project.notes.append(f"{elsewhere['with_customer']} decision item(s) are already with the customer "
                             "and are not listed; the question list shows them")
    if elsewhere["settled"]:
        project.notes.append(f"{elsewhere['settled']} decision item(s) are settled by standing policy "
                             "and are not listed")
    return items, known


def erratum_items(project: Project, names: ScreenNames) -> list[dict[str, Any]]:
    path = project.register("*_Errata.json")
    if path is None:
        return []
    data = read_json(path)
    entries = data.get("entries") if isinstance(data, dict) else data
    app = str(data.get("app_id") or "") if isinstance(data, dict) else ""
    app = app or path.name.split("_Errata", 1)[0]
    page = project.rel(outputs(path) / f"{app}_Errata.md")
    items = []
    for entry in entries or []:
        if not isinstance(entry, dict) or not blank(entry.get("acknowledged_by")):
            continue
        ident = str(entry.get("id") or "?")
        affected = entry.get("affected") or []
        affected = [str(a) for a in affected] if isinstance(affected, list) else [str(affected)]
        risk = {"HIGH": "high", "MEDIUM": "medium", "LOW": "low"}.get(str(entry.get("severity")), "medium")
        ask = (f"Is correction {ident} right, and does every affected passage now say it? "
               f"Now reads: {norm(entry.get('corrected'))}")
        how = (f"add `\"acknowledged_by\": \"<name>\", \"acknowledged_on\": \"YYYY-MM-DD\"` to {ident} in "
               f"`{project.rel(path)}`; if it is wrong, add a new erratum instead")
        evidence = f"{page} {ident}; affects " + "; ".join(norm(a) for a in affected) if affected else f"{page} {ident}"
        items.append(make("erratum", risk, names.in_text(" ".join(affected)), ask, short(evidence, 300), how,
                          project.rel(path), f"erratum:{ident}", source_id=ident))
    return items


def per_screen_files(project: Project, folder: str) -> list[Path]:
    where = project.docs / folder
    if not where.is_dir():
        return []
    return sorted(p for p in where.glob("*.md") if p.name.lower() != "readme.md")


def coding_items(project: Project) -> list[dict[str, Any]]:
    items = []
    for path in per_screen_files(project, "Coding_Records"):
        screen = norm(path.stem)
        for header, rows in tables(read_text(path), re.compile(r"Pending Answers", re.I)):
            i_no, i_q = column(header, "#"), column(header, "question")
            i_track, i_to, i_status = column(header, "track"), column(header, "asked to"), column(header, "status")
            for number, cells in rows:
                question = cell(cells, i_q)
                status = norm(cell(cells, i_status)).casefold()
                if blank(question) or status.startswith(("answered", "closed", "resolved")):
                    continue
                row = norm(cell(cells, i_no)) or str(number)
                track = norm(cell(cells, i_track))
                asked = norm(cell(cells, i_to))
                ask = (f"{question}" + (f" (asked to {asked})" if not blank(asked) else "")
                       + (f"; blocks the {track} track" if not blank(track) else ""))
                items.append(make("decision", "high", [screen], ask,
                                  f"{project.rel(path)} §7.1 row {row}",
                                  f"write the answer into `{project.rel(path)}` §7.1 row {row} and set its Status "
                                  "to `answered`; the coding stage then clears `blocked`",
                                  project.rel(path), f"decision:{screen}:7.1#{row}"))
    return items


def plan_items(project: Project, known: set[str]) -> list[dict[str, Any]]:
    items = []
    for path in per_screen_files(project, "Screen_plans"):
        screen = norm(path.stem)
        text = read_text(path)
        for section, label, open_word in (("Gap Matrix", "§6", "open"),
                                          ("Legacy-To-New Mapping", "§5", "open-decision")):
            for header, rows in tables(text, re.compile(re.escape(section), re.I)):
                i_status = column(header, "status")
                i_topic = column(header, "topic", "rule")
                i_new = column(header, "new behavior", "new behaviour")
                i_no = column(header, "#")
                for number, cells in rows:
                    if norm(cell(cells, i_status)).casefold() != open_word:
                        continue
                    if queue_ids(" ".join(cells)):
                        continue        # cites a decision-queue item: that item is the ask
                    topic = norm(cell(cells, i_topic))
                    meanwhile = norm(cell(cells, i_new))
                    row = norm(cell(cells, i_no)) or f"line {number}"
                    ask = (f"Decide {topic or 'this row'} for {screen}"
                           + (f"; the plan proceeds on: {meanwhile}" if not blank(meanwhile) else ""))
                    outcome = ("`matched`, `accepted-difference` or `fixed-deliberately`" if label == "§6"
                               else "`planned` or `accepted-difference`")
                    items.append(make("plan approval", "medium", [screen], ask,
                                      f"{project.rel(path)} {label} {row}",
                                      f"set the row's Status in `{project.rel(path)}` {label} to {outcome}, "
                                      "with the decision in the row; or raise it in the decision queue",
                                      project.rel(path), f"plan:{screen}:{label}#{row}"))
    return items


def test_items(project: Project) -> list[dict[str, Any]]:
    items = []
    for path in per_screen_files(project, "Test_Instruction"):
        screen = norm(path.stem)
        for header, rows in tables(read_text(path), re.compile(r"Tier 3|Residual Manual", re.I)):
            i_no, i_case = column(header, "#"), column(header, "case")
            i_sample, i_by = column(header, "legacy sample"), column(header, "verified by")
            if i_by is None:
                continue
            for number, cells in rows:
                case = norm(cell(cells, i_case))
                if blank(case) or not blank(cell(cells, i_by)):
                    continue
                row = norm(cell(cells, i_no)) or f"line {number}"
                sample = norm(cell(cells, i_sample))
                ask = (f"Run manual case {row} on {screen} and compare: {case}"
                       + (f" (against {sample})" if not blank(sample) else ""))
                items.append(make("test sign-off", "medium", [screen], ask,
                                  f"{project.rel(path)} §4.4 row {row}",
                                  f"fill Result and `Verified by` (your name and the date) in `{project.rel(path)}` "
                                  f"§4.4 row {row}",
                                  project.rel(path), f"test:{screen}:4.4#{row}"))
    return items


def _field(text: str, label: str) -> list[str]:
    """Values of `**label**: value` lines, leaving out the template's `a | b | c` vocabulary line."""
    values = []
    for match in re.finditer(r"\*\*%s\*\*\s*:\s*(.*)$" % re.escape(label), text, re.M | re.I):
        value = norm(match.group(1))
        if "|" not in value:
            values.append(value.casefold())
    return values


def acceptance_items(project: Project) -> list[dict[str, Any]]:
    items = []
    for path in per_screen_files(project, "Final_Acceptance"):
        screen = norm(path.stem)
        text = read_text(path)
        decisions = _field(text, "User decision")
        if not decisions or any(v.startswith(("accepted", "rejected", "changed")) for v in decisions):
            continue
        if not any(v.startswith("pending") for v in decisions):
            continue
        recommendation = next((v for v in _field(text, "Recommendation") if v), "")
        risk = "medium" if recommendation.startswith(("approve with follow-ups", "approve")) else "high"
        ask = (f"Accept {screen}? Recommendation: {recommendation or 'not stated'}")
        items.append(make("review", risk, [screen], ask, f"{project.rel(path)} §5",
                          f"set **User decision** in `{project.rel(path)}` to `accepted`, `rejected` or `changed`, "
                          "with a User decision note",
                          project.rel(path), f"review:{screen}"))
    return items


def issue_items(project: Project, known: set[str], names: ScreenNames) -> list[dict[str, Any]]:
    path = project.docs / "Known_Issues.md"
    if not path.is_file():
        return []
    items = []
    for header, rows in tables(read_text(path), re.compile(r"^Active Log\b", re.I)):
        i_no, i_type, i_title = column(header, "#"), column(header, "type"), column(header, "title")
        i_affects, i_status = column(header, "affects"), column(header, "status")
        i_next = column(header, "decision")
        for _number, cells in rows:
            row = norm(cell(cells, i_no))
            kind = norm(cell(cells, i_type)).casefold()
            status = norm(cell(cells, i_status))
            title = norm(cell(cells, i_title))
            if not row.isdigit() or blank(title):
                continue
            word = status.split("(")[0].strip().casefold()
            suffix = re.search(r"\((HIGH|MEDIUM|LOW)\)", status)
            if word != "open":
                continue
            if kind == "traceability":
                if not suffix or suffix.group(1) != "HIGH":
                    continue        # MEDIUM and LOW are confirmed by the Stage 5 reviewer
            elif kind not in ("business", "legacy-bug"):
                continue
            if any(i in known for i in queue_ids(" ".join(cells))):
                continue            # a pointer to a decision-queue item: the queue lists it
            risk = suffix.group(1).lower() if suffix else "medium"
            nxt = norm(cell(cells, i_next))
            if kind == "traceability":
                ask = f"Gate finding #{row}: {title}. Examine, defer or cancel?"
            elif kind == "legacy-bug":
                ask = f"#{row} {title}: preserve the legacy behaviour or fix it?"
            else:
                ask = f"#{row} {title}" + (f": {nxt}" if not blank(nxt) else "")
            items.append(make("issue", risk, names.in_text(cell(cells, i_affects)), ask,
                              f"{project.rel(path)} #{row}",
                              f"set row #{row}'s Status in `{project.rel(path)}` to `resolved`, `deferred` or "
                              "`wont_fix`, with the decision and `Closed: YYYY-MM-DD` in Decision / Next step",
                              project.rel(path), f"issue:#{row}"))
    return items


def blocked_items(project: Project, others: list[dict[str, Any]]) -> list[dict[str, Any]]:
    named = {s for item in others for s in item["screens"]}
    path = project.docs / "Screens_Registry.md"
    items = []
    for row in project.screens:
        tracks = [t for t in ("be", "fe") if row[f"status_{t}"].casefold() == "blocked"]
        if not tracks or row["screen"] in named:
            continue
        which = " and ".join("backend" if t == "be" else "frontend" for t in tracks)
        items.append(make("issue", "high", [row["screen"]],
                          f"{row['screen']}'s {which} track is `blocked` and nothing names the cause: "
                          "what blocks it?",
                          f"{project.rel(path)} {row['screen']}",
                          "open a row in `Known_Issues.md`, or a Pending Answers row in the screen's coding "
                          "record, naming the blocker; or set the status back if it no longer holds",
                          project.rel(path), f"issue:registry:{row['screen']}"))
    return items


# --- the queue --------------------------------------------------------------------

def _natural(text: str) -> tuple[Any, ...]:
    return tuple((0, int(p)) if p.isdigit() else (1, p) for p in re.split(r"(\d+)", text) if p)


def order_key(item: dict[str, Any]) -> tuple[Any, ...]:
    screens = item["screens"]
    return (RISKS.index(item["risk"]), KINDS.index(item["kind"]),
            (1, "") if not screens else (0, screens[0]), _natural(item["id"]))


def build(project: Project) -> dict[str, Any]:
    names = ScreenNames(project)
    decisions, known = decision_items(project, names)
    items = decisions + erratum_items(project, names) + coding_items(project) + plan_items(project, known)
    items += test_items(project) + acceptance_items(project) + issue_items(project, known, names)
    items += blocked_items(project, items)
    items.sort(key=order_key)
    counts = {"total": len(items),
              "by_risk": {r: sum(1 for i in items if i["risk"] == r) for r in RISKS},
              "by_kind": {k: sum(1 for i in items if i["kind"] == k) for k in KINDS}}
    return {"generated_by": GENERATED_BY, "version": 1,
            "workspace": project.ak_root() if project.workspace is not None else None,
            "counts": counts, "risk_rules": RISK_RULES, "items": items, "notes": project.notes}


def count_line(queue: dict[str, Any]) -> str:
    c = queue["counts"]
    if not c["total"]:
        return "Nothing waits on a person."
    noun = "item waits" if c["total"] == 1 else "items wait"
    return (f"{c['total']} {noun} on a person: " + ", ".join(f"{c['by_risk'][r]} {r}" for r in RISKS) + ".")


def _cell(text: Any) -> str:
    return str(text).replace("|", chr(92) + "|").replace("\n", " ")


def render_markdown(queue: dict[str, Any]) -> str:
    out = [f"{GENERATED_MD} -->", "# Review queue", "", "Audience: person", "", count_line(queue), ""]
    if queue["items"]:
        out += ["Everything in this project that waits on a person, highest risk first. Each row is one "
                "question; answer it where *How to record* says, then run `review_queue.py` again. "
                "Paths are relative to the repository root. "
                "Generated from the sources named in *Source*; edit those, not this file. It has no "
                "date on purpose: the same state gives the same file.", ""]
        overdue = any(i["status"] != "waiting" for i in queue["items"])
        head = ["#", "Risk", "Kind", "Screen", "Ask", "Evidence", "How to record", "Source"]
        if overdue:
            head.append("Status")
        out += ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
        for number, item in enumerate(queue["items"], 1):
            row = [str(number), item["risk"], item["kind"], ", ".join(item["screens"]) or "—",
                   item["ask"], item["evidence"], item["how_to_record"], item["source"]]
            if overdue:
                row.append(item["status"])
            out.append("| " + " | ".join(_cell(v) for v in row) + " |")
        out.append("")
        by_kind = [f"{n} {k}" for k, n in queue["counts"]["by_kind"].items() if n]
        out += ["By kind: " + ", ".join(by_kind) + ".", ""]
    if queue["notes"]:
        out += ["## Notes", ""] + [f"- {n}" for n in queue["notes"]] + [""]
    return "\n".join(out).rstrip("\n") + "\n"


def render_json(queue: dict[str, Any]) -> str:
    return json.dumps(queue, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def ours(path: Path, kind: str) -> bool:
    """Whether an existing file was written by this script."""
    if not path.exists():
        return True
    text = read_text(path)
    if kind == "md":
        return text.startswith(GENERATED_MD)
    try:
        return json.loads(text).get("generated_by") == GENERATED_BY
    except (json.JSONDecodeError, AttributeError):
        return False


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--repo", required=True, type=Path, help="the modernize repository")
    parser.add_argument("--docs-dir", type=Path, help="its docs folder; default `docs`, or the one folder "
                                                      "holding PROJECT_CONFIG.md")
    parser.add_argument("--workspace", type=Path, help="the investigation workspace; default AK_RUN_DIR, "
                                                       "else the repository's parent when it is one")
    parser.add_argument("--dry-run", action="store_true", help="print the count line and write nothing")
    parser.add_argument("--force", action="store_true", help="overwrite a queue file this script did not write")
    args = parser.parse_args(argv)
    try:
        project = Project(args.repo, args.docs_dir, args.workspace)
        queue = build(project)
    except CannotRun as problem:
        print(f"review_queue: {problem}", file=sys.stderr)
        return 2
    print(count_line(queue))
    for kind, n in queue["counts"]["by_kind"].items():
        if n:
            print(f"  {kind}: {n}")
    for note in queue["notes"]:
        print(f"  note: {note}")
    if args.dry_run:
        print("dry run: nothing written")
        return 0
    page, data = project.docs / PAGE, project.docs / DATA
    foreign = [p.name for p, k in ((page, "md"), (data, "json")) if not ours(p, k)]
    if foreign and not args.force:
        print(f"review_queue: {', '.join(foreign)} exists and this script did not write it; move it aside, "
              "or pass --force", file=sys.stderr)
        return 1
    for path, text in ((page, render_markdown(queue)), (data, render_json(queue))):
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    print(f"wrote {project.rel(page)} and {project.rel(data)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
