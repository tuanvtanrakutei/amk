"""The decided items, one row each, on the page a person and an agent both read (A110).

A phase document is read by a person, and a decision is recorded for agents: a
TARGET_INTENT evidence item, cited by the register's `resolved_by`. When the decisions were
applied to the phases, the record came with them: nearly every sentence ended in an
evidence id, some carried the history of a decision taken twice as a list of replaced ids
and errata numbers, and a reader had to decode that list to learn what the replacement does.

So the two layers meet on one generated page, `{APP}_Decisions.md`, beside the phase
documents. A phase cites a decision by its item code (`RA-04`, `D-EXPORT-NAME`); this page
maps each code to the one decision in force, in a sentence, and to the evidence id that
records it. What an earlier decision said is a footnote, not a column of the text.

What is decided, and what is in force:

- An item is decided when the identifier register closes it with a TARGET_INTENT item, or
  when a TARGET_INTENT item names it: `attribution.question_id`, else the `row X` of its
  `source_location`. The second reaches a decision-record row that is in no register
  (`D-EXPORT-NAME`): a decider records what the replacement does about something no phase
  allocated an identifier for.
- A decision is superseded when an errata entry lists its evidence id
  (`superseded_evidence_ids`), or when a later TARGET_INTENT item decides the same code.
  Two more are the record's own words: a later item whose notes or statement say it
  `replaces` this evidence id or this code, and an item whose own notes say it was
  `superseded by` something. Without those, a decision recorded under a new row code
  (`D-LABEL-B` replacing `D-LABEL-A`) would stay in force beside its replacement.
- "Later" is `created_at`, then the evidence id's number.

Nothing here reads a file but the decision records' own tables, for the `About` cell of a
row code no register titles. No date is written, so the same registers give the same page.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import decision_agenda as da
import decision_queue as dq

GENERATED = "<!-- generated-by: ak decisions, decided items"
AUDIENCE = "Audience: bridge"
TARGET_INTENT = "TARGET_INTENT"
RECORD_ROWS = "record"
UNDECIDED_WORD = "decided"

# The same shape the conformance checker cites by, so one id is one id on both sides.
EVIDENCE_ID = re.compile(r"\b[A-Z][A-Z0-9_-]{1,15}-P[1-6]-[A-Z][A-Z0-9_]*-\d{3,}\b")
ERRATA_ID = re.compile(r"\bE-\d{2}\b")
CODE_TOKEN = re.compile(r"(?<![\w-])(?:[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+|Q\d{1,3})(?![\w-])")
ROW_CODE = re.compile(r"^\s*row\s+([^\s,;]+)", re.IGNORECASE)
REPLACES = re.compile(r"\breplac(?:es|ed|ing)\b([^.;]*)", re.IGNORECASE)
SUPERSEDED_BY = re.compile(r"\bsuperseded\b[^.;]*?\bby\b([^.;]*)", re.IGNORECASE)
DECIDED_ON = re.compile(r"\s*\((?:decided|recorded)\b[^)]*\)", re.IGNORECASE)
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z`(\"'*])")
MITIGATION_PREFIX = re.compile(r"^Do what its Mitigation says:\s*", re.IGNORECASE)
# A record row written by hand often opens with its word: `preserve: ...`, `fix (minimal): ...`.
LEADING_WORD = re.compile(r"^(" + "|".join(dq.DISPOSITIONS) + r")\b(?:\s*\([^)]*\))?\s*:\s*",
                          re.IGNORECASE)
NOTE_PREFIX = "Decider's note:"

GROUPS: tuple[tuple[str, str], ...] = (
    ("RD-", "Data risks (RD-)"),
    ("RA-", "Application risks (RA-)"),
    ("RW-", "Workflow risks (RW-)"),
    ("RS-", "Security risks (RS-)"),
    ("UK-", "Unknowns (UK-)"),
    ("Q", "Questions (Q)"),
    ("AS-", "Assumptions (AS-)"),
)
ABOUT_LIMIT = 110
DOES_LIMIT = 320
NONE = "—"


@dataclass
class Decision:
    code: str
    item: dict[str, Any]
    superseded_by: list[str] = field(default_factory=list)

    @property
    def evidence_id(self) -> str:
        return str(self.item.get("id"))


@dataclass
class Page:
    rows: list[Decision]
    superseded: list[Decision]
    withdrawn: list[str]                 # codes with no decision left in force
    unplaced: list[str]                  # TARGET_INTENT items that name no item code
    replaces: dict[tuple[str, str], list[str]]
    problems: list[str]
    namespaces: dict[str, str]


def _when(item: dict[str, Any]) -> datetime:
    text = str(item.get("created_at") or "").strip()
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _order(item: dict[str, Any]) -> tuple[datetime, tuple[tuple[int, Any], ...]]:
    return _when(item), da.natural(str(item.get("id") or ""))


def _text(item: dict[str, Any]) -> str:
    return " ".join(str(item.get(key) or "") for key in ("statement", "notes"))


def named_after(pattern: re.Pattern[str], text: str) -> set[str]:
    """Evidence ids, `E-` numbers and item codes named in the clause each match opens."""
    found: set[str] = set()
    for match in pattern.finditer(text):
        span = match.group(1)
        found |= set(EVIDENCE_ID.findall(span)) | set(ERRATA_ID.findall(span))
        found |= set(CODE_TOKEN.findall(EVIDENCE_ID.sub(" ", span)))
    return found


def codes_of(item: dict[str, Any], resolved: dict[str, list[str]]) -> list[str]:
    """The item codes one TARGET_INTENT item decides."""
    codes = list(resolved.get(str(item.get("id")), []))
    attribution = item.get("attribution") if isinstance(item.get("attribution"), dict) else {}
    question = str((attribution or {}).get("question_id") or "").strip()
    if question:
        codes.append(question)
    else:
        row = ROW_CODE.match(str(item.get("source_location") or ""))
        if row:
            codes.append(row.group(1).strip("`*").rstrip(".:"))
    return sorted(set(codes), key=da.natural)


def build(entries: list[dict[str, Any]], evidence: list[dict[str, Any]],
          errata: list[dict[str, Any]] | None = None) -> Page:
    """Which decision is in force for every decided item, and which ones it replaced."""
    targets = sorted((i for i in evidence if isinstance(i, dict) and i.get("id")
                      and i.get("evidence_class") == TARGET_INTENT), key=_order)
    by_id = {str(i["id"]): i for i in targets}
    namespaces = {str(e["id"]): str(e.get("namespace") or "") for e in entries if e.get("id")}
    resolved: dict[str, list[str]] = {}
    for entry in entries:
        closer = str(entry.get("resolved_by") or "").strip()
        if entry.get("id") and closer in by_id:
            resolved.setdefault(closer, []).append(str(entry["id"]))

    errata_of: dict[str, list[str]] = {}
    for entry in errata or []:
        for evidence_id in entry.get("superseded_evidence_ids") or []:
            errata_of.setdefault(str(evidence_id), []).append(str(entry.get("id")))

    pairs: list[Decision] = []
    unplaced: list[str] = []
    for item in targets:
        codes = codes_of(item, resolved)
        if not codes:
            unplaced.append(str(item["id"]))
        pairs += [Decision(code, item) for code in codes]

    position = {str(i["id"]): n for n, i in enumerate(targets)}
    replaced_by_name = {str(i["id"]): named_after(REPLACES, _text(i)) for i in targets}
    for decision in pairs:
        here = position[decision.evidence_id]
        reasons = list(errata_of.get(decision.evidence_id, []))
        later = [p for p in pairs if p.code == decision.code and position[p.evidence_id] > here]
        if later:
            reasons.append(later[0].evidence_id)
        for other in targets[here + 1:]:
            named = replaced_by_name[str(other["id"])]
            if decision.evidence_id in named or (decision.code in named
                                                 and decision.code not in codes_of(other, resolved)):
                reasons.append(str(other["id"]))
        own = named_after(SUPERSEDED_BY, str(decision.item.get("notes") or ""))
        if SUPERSEDED_BY.search(str(decision.item.get("notes") or "")):
            reasons += sorted(own - {decision.code}, key=da.natural) or ["its own record"]
        decision.superseded_by = sorted(dict.fromkeys(reasons), key=da.natural)

    current = {p.code: p for p in pairs if not p.superseded_by}
    superseded = [p for p in pairs if p.superseded_by]
    withdrawn = sorted({p.code for p in superseded} - set(current), key=da.natural)

    replaces: dict[tuple[str, str], list[str]] = {}
    for code, decision in current.items():
        earlier = [p for p in superseded
                   if p.code == code or decision.evidence_id in p.superseded_by]
        named = replaced_by_name[decision.evidence_id]
        ids = {p.evidence_id for p in earlier} | {n for n in named if EVIDENCE_ID.fullmatch(n)}
        numbers = {e for p in earlier for e in p.superseded_by if ERRATA_ID.fullmatch(e)}
        numbers |= {n for n in named if ERRATA_ID.fullmatch(n)}
        numbers |= {e for i in ids for e in errata_of.get(i, [])}
        replaces[(code, decision.evidence_id)] = (sorted(ids - {decision.evidence_id}, key=da.natural)
                                                  + sorted(numbers, key=da.natural))

    problems: list[str] = []
    for entry in entries:
        code, closer = str(entry.get("id") or ""), str(entry.get("resolved_by") or "").strip()
        if closer in by_id and code in current and current[code].evidence_id != closer:
            problems.append(f"the register closes {code} with {closer}; the decision in force is "
                            f"{current[code].evidence_id}")
    rows = sorted(current.values(), key=lambda d: (_group(d.code, namespaces), da.natural(d.code)))
    return Page(rows=rows, superseded=sorted(superseded, key=lambda d: (da.natural(d.code), _order(d.item))),
                withdrawn=withdrawn, unplaced=unplaced, replaces=replaces, problems=problems,
                namespaces=namespaces)


def _group(code: str, namespaces: dict[str, str]) -> int:
    namespace = namespaces.get(code)
    for index, (prefix, _title) in enumerate(GROUPS):
        if namespace == prefix:
            return index
    return len(GROUPS) if namespace else len(GROUPS) + 1


def _heading(index: int) -> str:
    if index < len(GROUPS):
        return GROUPS[index][1]
    return "Other register items" if index == len(GROUPS) else "Decision-record rows"


def _flat(text: Any) -> str:
    return " ".join(str(text or "").split())


def shorten(text: str, limit: int) -> str:
    """The first sentence, cut at a word when it is still longer than the limit."""
    first = SENTENCE.split(_flat(text))[0] if _flat(text) else ""
    if len(first) <= limit:
        return first
    cut = first[:limit].rsplit(" ", 1)[0].rstrip(",;:")
    return cut + " …"


def decision_word(item: dict[str, Any]) -> str:
    """The disposition the item records, else the word its statement opens with, else `decided`."""
    recorded = dq.recorded_disposition(item)
    if recorded:
        return recorded
    match = LEADING_WORD.match(_flat(item.get("statement")))
    return match.group(1).lower() if match else UNDECIDED_WORD


def what_it_does(item: dict[str, Any]) -> str:
    """One sentence: what the replacement does. The decider's note follows when there is one."""
    statement = _flat(item.get("statement"))
    match = dq.DISPOSITION_STATEMENT.match(statement)
    if match:
        statement = statement[match.end():].strip()
    statement = DECIDED_ON.sub("", LEADING_WORD.sub("", MITIGATION_PREFIX.sub("", statement))).strip()
    note = ""
    if NOTE_PREFIX in statement:
        statement, _, note = statement.partition(NOTE_PREFIX)
        note = f" Note: {shorten(note.strip(), 160)}"
    sentence = shorten(statement.strip(), DOES_LIMIT)
    return (sentence + note).strip() or NONE


def record_abouts(root: Path, evidence: list[dict[str, Any]]) -> dict[str, str]:
    """Row code -> the `About` cell of the decision record that holds it.

    A row code is in no register, so nothing else titles it. A record that cannot be read,
    or has no `About` column, gives nothing, and the page says so with a dash.
    """
    abouts: dict[str, str] = {}
    paths = sorted({str(i.get("source_path") or "") for i in evidence
                    if isinstance(i, dict) and i.get("evidence_class") == TARGET_INTENT})
    for relative in paths:
        if not relative:
            continue
        path = root / relative
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            continue
        for table in dq.tables(text):
            header = [h.casefold() for h in table.header]
            if "about" not in header:
                continue
            column = header.index("about")
            for row in table.rows:
                if len(row.cells) > column and row.cells[0]:
                    code = row.cells[0].strip().strip("`*").strip()
                    abouts.setdefault(code, row.cells[column])
    return abouts


def render(page: Page, app: str, *, titles: dict[str, str] | None = None,
           abouts: dict[str, str] | None = None, sources: str = "the registers") -> str:
    titles, abouts = titles or {}, abouts or {}
    app = app or "App"
    out = [
        f"{GENERATED} -->",
        f"# {app} {NONE} Decisions",
        "",
        f"{AUDIENCE}. A person reads it to learn what was decided for the replacement; an agent "
        "reads it to find the evidence id behind an item code.",
        "",
        "One row per decided item, with the decision in force only. Phase documents cite a decision "
        "by its item code (`RA-04`, `D-EXPORT-NAME`), never by its evidence id, and say nothing about how it "
        f"was reached; this page maps the code to the record. Generated by `$ak decisions` from "
        f"{sources}; edit the registers, not this file. It has no date on purpose: the same registers "
        "give the same file.",
        "",
    ]
    if not page.rows:
        out += ["No item has been decided yet.", ""]
    groups: dict[int, list[Decision]] = {}
    for decision in page.rows:
        groups.setdefault(_group(decision.code, page.namespaces), []).append(decision)
    for group in sorted(groups):
        out += [f"## {_heading(group)}", "",
                "| Item code | About | Decision | What the replacement does | Evidence id | Replaces |",
                "|---|---|---|---|---|---|"]
        for decision in groups[group]:
            about = titles.get(decision.code) or abouts.get(decision.code) or ""
            replaced = page.replaces.get((decision.code, decision.evidence_id)) or []
            out.append("| " + " | ".join(da._cell(c) for c in (
                decision.code, shorten(about, ABOUT_LIMIT) or NONE,
                decision_word(decision.item),
                what_it_does(decision.item), decision.evidence_id,
                ", ".join(replaced) or NONE)) + " |")
        out.append("")

    if page.superseded or page.withdrawn or page.unplaced:
        out += ["## Superseded", "",
                "Earlier decisions no longer in force. The errata page says what changed and why.", ""]
        for decision in page.superseded:
            out.append(f"- {decision.evidence_id} ({decision.code}): superseded by "
                       + ", ".join(decision.superseded_by) + ".")
        for code in page.withdrawn:
            out.append(f"- {code}: every decision recorded for it is superseded, and none is in force.")
        if page.unplaced:
            out.append(f"- Not listed: {len(page.unplaced)} target-intent item(s) name no item code "
                       f"({', '.join(page.unplaced)}).")
        out.append("")

    parts = [f"{_heading(g).split(' (')[0].lower()} {len(groups[g])}" for g in sorted(groups)]
    out.append(f"{len(page.rows)} decided item(s)" + (f": {', '.join(parts)}" if parts else "")
               + f"; {len(page.superseded)} superseded decision(s).")
    return "\n".join(out) + "\n"
