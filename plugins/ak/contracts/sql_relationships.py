"""What the SQL says about how tables relate, when the database declares nothing.

Access databases often declare **zero** relationships; one project's declared none. That is not a collection gap - DAO
was asked and the answer was none - so the catalogue's `FK` column could never be
filled from the schema, and a migration would have had to guess which columns were
meant to match.

The SQL knows. 79 saved queries and 118 record sources carry `JOIN ... ON` clauses,
and a join is a stronger statement about how the application *actually* relates two
tables than a declared constraint would be: a declared FK says what is permitted, a
join says what is done. It is weaker in the other direction - it constrains nothing,
and two columns joined once may have been a mistake - so everything here is INFERRED
and says so.

Three things are derived, and the limits of each are stated rather than smoothed over:

  relationships   Column pairs joined in real SQL, with how many places do it. Covers
                  only tables that appear in a join; a work table filled by VBA
                  string-built SQL will not.

  candidate keys  The column a table is most often joined *on*. For a master table
                  that is its key in practice. It cannot be confirmed here: proving a
                  column is unique needs rows, which means SAMPLE_DATA. A `WK*` work
                  table having no key is normal, not a finding.

  dangling refs   SQL naming a table or query that exists nowhere and is created
                  nowhere. Five queries in one project did this, which makes them unrunnable, and
                  nothing in the application distinguishes them from working ones.

Alias resolution is the fiddly part and the reason this is a module rather than a
regex at a call site: `ON t1.商品コード = m1.商品コード` names nothing until `FROM
商品マスタ AS m1` is read. An unresolved alias is counted and reported, never guessed.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

# One `a.b = c.d` term of a join condition, allowing bracketed names, which Access
# uses for anything with a space or a symbol in it.
EQUALITY = re.compile(
    r"(\[[^\]]+\]|[^\s=().]+)\s*\.\s*(\[[^\]]+\]|[^\s=()]+)"
    r"\s*=\s*(\[[^\]]+\]|[^\s=().]+)\s*\.\s*(\[[^\]]+\]|[^\s=(),;]+)",
    re.IGNORECASE,
)
# Where a join condition starts, and where it stops. A condition is read whole, so
# `ON a.x = b.x AND a.y = b.y` is one join on two columns rather than one join on
# `x` with the rest of the clause discarded - which is what reading only the first
# equality after `ON` did.
ON_KEYWORD = re.compile(r"\bON\b", re.IGNORECASE)
CONDITION_END = re.compile(
    r"\b(?:ON|INNER|LEFT|RIGHT|FULL|CROSS|JOIN|WHERE|GROUP|ORDER|HAVING|UNION)\b|;",
    re.IGNORECASE,
)


def join_conditions(text: str) -> list[list[tuple[str, str, str, str]]]:
    """Every `ON` condition in `text`, as its list of `table.column = table.column` terms.

    A term comparing a column with a literal (`AND a.flag = 1`) is not a join term and
    is left out; the terms that remain are the columns the join matches on.
    """
    found: list[list[tuple[str, str, str, str]]] = []
    for start in ON_KEYWORD.finditer(text):
        end = CONDITION_END.search(text, start.end())
        segment = text[start.end():end.start() if end else len(text)]
        terms = EQUALITY.findall(segment)
        if terms:
            found.append(terms)
    return found
# `FROM x AS y` / `JOIN x y`. The alias is the short name the ON clause will use.
ALIAS_CLAUSE = re.compile(
    r"\b(?:FROM|JOIN)\s+(\[[^\]]+\]|[^\s,()]+)\s+(?:AS\s+)?([A-Za-z]\w*)\b",
    re.IGNORECASE,
)
# Anything the SQL reads from or writes to.
OBJECT_REF = re.compile(
    r"\b(?:FROM|JOIN|INTO|UPDATE)\s+(\[[^\]]+\]|[^\s,();]+)", re.IGNORECASE
)
# A table this SQL creates, so naming it is not a dangling reference.
CREATES = re.compile(r"\b(?:INTO|CREATE\s+TABLE)\s+(\[[^\]]+\]|[^\s,();]+)", re.IGNORECASE)

# `... FROM x IN "L:\path\other.mdb"` - Access runs the query against another database
# file named by absolute path, so a table absent from the acquired copy is not missing;
# it is expected somewhere this run never opened.
#
# Missing this cost a wrong published claim (E-09): two working screens were reported
# as unable to open because their record source named a table that "does not exist".
# It also hid the mechanism - 35 of 51 forms in one project queried a backend this way, 145 times,
# naming four locations, one of them on a different drive letter than the stored links.
IN_DATABASE = re.compile(r"\bIN\s+\\{0,2}\"([^\"]{2,200})", re.IGNORECASE)

# Words that follow FROM/JOIN/INTO without being an object name.
NOT_A_NAME = {"select", "distinct", "distinctrow", "top"}

# A word that follows a table name without being its alias. `FROM 元商品マスタC LEFT
# JOIN ...` reads as alias `LEFT` otherwise, which then put the real table name into
# the alias values and made every dangling reference in one project's queries invisible -
# the check reported 0 where a plainer regex had found 5.
NOT_AN_ALIAS = {
    "left", "right", "inner", "outer", "full", "cross", "join", "on", "where",
    "group", "order", "having", "union", "as", "in", "and", "or", "not", "with",
    "select", "from", "into", "set", "values", "by", "asc", "desc", "distinct",
}


def unbracket(name: str) -> str:
    return name.strip().strip("[]").strip()


@dataclass
class Relationship:
    """One join between two tables, on one column or on several matched together.

    A composite join `ON a.x = b.x AND a.y = b.y` is one relationship on `(x, y)`, not
    two relationships on `x` and on `y`: neither column identifies the row alone, and
    reporting them apart says two keys exist where there is one.
    """

    left_table: str
    left_columns: tuple[str, ...]
    right_table: str
    right_columns: tuple[str, ...]
    occurrences: int = 1
    seen_in: list[str] = field(default_factory=list)

    @property
    def left_column(self) -> str:
        return ", ".join(self.left_columns)

    @property
    def right_column(self) -> str:
        return ", ".join(self.right_columns)

    @property
    def is_composite(self) -> bool:
        return len(self.left_columns) > 1

    @property
    def same_column_name(self) -> bool:
        """A join between two columns of the same name is the ordinary case here."""
        return self.left_columns == self.right_columns


@dataclass
class Analysis:
    relationships: list[Relationship]
    candidate_keys: dict[str, list[tuple[str, int]]]
    dangling: dict[str, list[str]]
    external_databases: dict[str, list[str]]
    unresolved_aliases: dict[str, int]
    joined_through_query: dict[str, int]
    sources_scanned: int

    @property
    def tables_in_a_join(self) -> set[str]:
        return {t for r in self.relationships for t in (r.left_table, r.right_table)}


def analyse(
    sources: dict[str, str],
    table_names: set[str],
    query_names: set[str] | None = None,
) -> Analysis:
    """Read every SQL source and report what it says about relationships.

    `sources` maps a label a reader will recognise - a query or screen name - to its
    SQL. The label is carried into each result so a claim can be followed back.
    """
    query_names = query_names or set()
    known = table_names | query_names

    pairs: dict[tuple[str, tuple[str, ...], str, tuple[str, ...]], Relationship] = {}
    unresolved: Counter[str] = Counter()
    through_query: Counter[str] = Counter()
    dangling: dict[str, list[str]] = {}
    external: dict[str, list[str]] = {}

    for label, text in sources.items():
        if not text:
            continue
        aliases = {
            alias.lower(): unbracket(real)
            for real, alias in ALIAS_CLAUSE.findall(text)
            if unbracket(real).lower() not in NOT_A_NAME
            and alias.lower() not in NOT_AN_ALIAS
        }

        def resolve(name: str) -> str:
            cleaned = unbracket(name)
            return aliases.get(cleaned.lower(), cleaned)

        for terms in join_conditions(text):
            # The terms of one condition, grouped by the pair of tables they match. One
            # condition can join more than one pair when Access nests its joins.
            grouped: dict[tuple[str, str], list[tuple[str, str]]] = {}
            for left_table, left_column, right_table, right_column in terms:
                left, right = resolve(left_table), resolve(right_table)
                if left not in table_names or right not in table_names:
                    # A join onto a saved query is legitimate and is not a relationship
                    # between tables, so it is counted separately rather than reported
                    # as unresolved. What remains unresolved is a name that is neither
                    # table, nor query, nor a resolvable alias - which in one project
                    # was exactly the two staging variants that do not exist.
                    for name in (left, right):
                        if name in table_names:
                            continue
                        if name in query_names:
                            through_query[name] += 1
                        else:
                            unresolved[name] += 1
                    continue
                left_column, right_column = unbracket(left_column), unbracket(right_column)
                # One ordering, so A-B and B-A are the same relationship.
                if (right, right_column) < (left, left_column):
                    left, right = right, left
                    left_column, right_column = right_column, left_column
                columns = grouped.setdefault((left, right), [])
                if (left_column, right_column) not in columns:
                    columns.append((left_column, right_column))
            for (left, right), columns in grouped.items():
                # Sorted, so `x AND y` and `y AND x` are the same composite join.
                columns.sort()
                flat = (left, tuple(c for c, _ in columns),
                        right, tuple(c for _, c in columns))
                existing = pairs.get(flat)
                if existing is None:
                    pairs[flat] = Relationship(*flat, occurrences=1, seen_in=[label])
                else:
                    existing.occurrences += 1
                    if label not in existing.seen_in:
                        existing.seen_in.append(label)

        created = {resolve(name) for name in CREATES.findall(text)}
        absent = sorted({
            resolve(name) for name in OBJECT_REF.findall(text)
            if unbracket(name).lower() not in NOT_A_NAME
            and not unbracket(name).startswith("(")
            and resolve(name) not in known
            and resolve(name) not in aliases.values()
            and resolve(name).lower() not in {a.lower() for a in aliases}
            and resolve(name) not in created
        })
        elsewhere = sorted({m.strip().rstrip("\\ ") for m in IN_DATABASE.findall(text)})
        if elsewhere:
            external[label] = elsewhere
        if absent and not elsewhere:
            dangling[label] = absent

    # A table's candidate key: the column it is most often joined on. Both sides
    # count - a join names the same conceptual key from either direction. A composite
    # join offers its columns together, as `x, y`, because that is the key it uses.
    joined_on: dict[str, Counter[str]] = defaultdict(Counter)
    for relationship in pairs.values():
        joined_on[relationship.left_table][relationship.left_column] += relationship.occurrences
        joined_on[relationship.right_table][relationship.right_column] += relationship.occurrences

    return Analysis(
        relationships=sorted(pairs.values(),
                             key=lambda r: (-r.occurrences, r.left_table, r.left_column)),
        candidate_keys={table: counts.most_common()
                        for table, counts in sorted(joined_on.items())},
        dangling=dict(sorted(dangling.items())),
        external_databases=dict(sorted(external.items())),
        unresolved_aliases=dict(unresolved.most_common()),
        joined_through_query=dict(through_query.most_common()),
        sources_scanned=len([t for t in sources.values() if t]),
    )


def is_work_table(name: str) -> bool:
    """A work table with no primary key is normal and should not read as a finding.

    Named by convention in this application family: `WK` or `W` prefix, or a `ＢＫ`
    backup prefix. The convention is not a guarantee, which is why the catalogue says
    "by naming convention" wherever it uses this.
    """
    return name.startswith(("WK", "W", "ＷＫ", "ＢＫ", "BK", "tmp", "TMP", "Temp"))



# --- who writes each table --------------------------------------------------
#
# The catalogue's "business role" column needs a document and cannot be filled from a
# name: rule EC-03 says a name is not a meaning, so classifying `商品マスタ` as master
# data because it ends in `マスタ` is exactly what the kit forbids.
#
# What *is* evidence is who writes the table. A table nothing writes behaves as
# reference data; a table deleted and refilled by the form that prints a report is
# scratch - which is how one project's `WK*` tables turned out to be used, confirming an
# assumption Phase 1 could only state. That is a USAGE claim from CODE, and it lets a
# reader classify without the analysis pretending to know meaning.
#
# The limit is stated rather than smoothed over: 129 of 152 `OpenRecordset` calls in
# one project took a built string, so a write through one of those cannot be attributed to a
# named table without dataflow analysis. "No writer attributable" is therefore never
# reported as "never written".

WRITE_STATEMENT = re.compile(
    r"(UPDATE|INSERT\s+INTO|DELETE\s+(?:\*\s+)?FROM|SELECT\b[^\"';]{0,200}?\bINTO)\s+"
    # `:` is excluded because VBA separates statements with it, so `FROM WK集計: rs...`
    # would otherwise capture the colon as part of the table name and the write would
    # be silently attributed to nothing.
    r"(\[[^\]]+\]|[^\s,;:()\"']+)",
    re.IGNORECASE,
)
TRANSFER_CALL = re.compile(
    r"DoCmd\.Transfer(?:Database|Text|Spreadsheet)[^\r\n]{0,240}", re.IGNORECASE
)
RECORDSET_BUILT = re.compile(r"OpenRecordset\s*\(\s*[A-Za-z_]", re.IGNORECASE)

# --- make-table queries -----------------------------------------------------
#
# `SELECT ... INTO <table> FROM ...` begins with SELECT and writes: it creates the
# target, replacing it if it exists. Classified by its first word it is a read, which
# undercounted the writing queries of one application by more than half.

_LITERAL_OR_BRACKET = re.compile(r"\[[^\]]*\]|'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"")
MAKE_TABLE = re.compile(
    r"^\s*(?:PARAMETERS\b[^;]*;\s*)?SELECT\b(?:(?!\bFROM\b).)*?\bINTO\s+"
    r"(\[[^\]]+\]|[^\s,;()\"']+)",
    re.IGNORECASE | re.DOTALL,
)


def make_table_target(sql: str) -> str | None:
    """The table a `SELECT ... INTO` statement creates, or None for any other statement.

    Read from a whole statement only - a saved query's SQL or a record source - and
    anchored at its start. `INTO` counts only before the first `FROM`, with bracketed
    names and quoted literals blanked first, so a column called `[INTO]` or a literal
    holding the word is not a target.
    """
    if not sql:
        return None
    blanked = _LITERAL_OR_BRACKET.sub(lambda m: "\x00" * len(m.group(0)), sql)
    match = MAKE_TABLE.search(blanked)
    if not match:
        return None
    start, end = match.span(1)
    return unbracket(sql[start:end])


# --- recordset writes -------------------------------------------------------
#
# A table filled only through a DAO or ADO recordset has no write statement to find:
# the code opens the table, then `.AddNew` or `.Edit` ... `.Update`. The write is
# attributed to the procedure that does it, and only where the recordset variable is
# opened on a name this reader can see - a literal table name, or a literal `SELECT`
# on one table. A recordset opened on a built string stays unattributed, and is counted
# by `built_string_opens`.

# A VBA identifier. A Japanese application names its procedures and variables in
# Japanese, so a letter is any Unicode letter, not `[A-Za-z]`.
_IDENT = r"[^\W\d]\w*"
PROCEDURE_START = re.compile(
    r"^\s*(?:(?:Public|Private|Friend)\s+)?(?:Static\s+)?"
    r"(?:Sub|Function|Property\s+(?:Get|Let|Set))\s+(" + _IDENT + ")",
    re.IGNORECASE,
)
PROCEDURE_END = re.compile(r"^\s*End\s+(?:Sub|Function|Property)\b", re.IGNORECASE)
_STRING = r"\"((?:[^\"]|\"\")*)\""
# `Set rs = db.OpenRecordset("T", ...)` (DAO) and `Set rs = cn.Execute("T")` are not
# the same thing; only the first opens an updatable recordset, so only it is read.
DAO_OPEN = re.compile(
    r"\bSet\s+(" + _IDENT + r")\s*=\s*[\w.()!\[\]]*?\.?OpenRecordset\s*\(\s*"
    r"(?:" + _STRING + r"|(" + _IDENT + r")\s*[,)])",
    re.IGNORECASE,
)
WITH_DAO_OPEN = re.compile(
    r"^\s*With\s+[\w.()!\[\]]*?\.?OpenRecordset\s*\(\s*(?:" + _STRING
    + r"|(" + _IDENT + r")\s*[,)])",
    re.IGNORECASE,
)
# `rs.Open "T", cn, ...` or `rs.Open("T", ...)` or `rs.Open Source:="T"` (ADO).
ADO_OPEN = re.compile(
    r"(?<![\w.])(" + _IDENT + r")\s*\.\s*Open\b\s*\(?\s*(?:Source\s*:=\s*)?"
    r"(?:" + _STRING + r"|(" + _IDENT + r")\s*[,)\s]|(" + _IDENT + r")$)",
    re.IGNORECASE,
)
WITH_VARIABLE = re.compile(r"^\s*With\s+(" + _IDENT + r")\s*$", re.IGNORECASE)
END_WITH = re.compile(r"^\s*End\s+With\b", re.IGNORECASE)
RECORDSET_VERB = re.compile(
    r"(?:^|[^\w.])(" + _IDENT + r")?\s*\.\s*(AddNew|Edit|Delete)\b", re.IGNORECASE)
LITERAL_ASSIGNMENT = re.compile(
    r"^\s*(?:Let\s+)?(" + _IDENT + r")\s*=\s*" + _STRING + r"\s*$", re.IGNORECASE)
SINGLE_TABLE_SELECT = re.compile(
    r"^\s*SELECT\b.*?\bFROM\s+(\[[^\]]+\]|[^\s,;()\"']+)\s*(.*)$",
    re.IGNORECASE | re.DOTALL,
)


def is_comment_line(line: str) -> bool:
    """A VBA line that is wholly a comment: `' ...` or `Rem ...`."""
    stripped = line.lstrip()
    return stripped.startswith("'") or bool(re.match(r"Rem(?:\s|$)", stripped, re.IGNORECASE))


def logical_lines(text: str) -> list[str]:
    """VBA lines with ` _` continuations joined, and comment lines dropped."""
    out: list[str] = []
    pending = ""
    for raw in text.splitlines():
        line = pending + raw if pending else raw
        if re.search(r"\s_\s*$", line):
            pending = re.sub(r"\s_\s*$", " ", line)
            continue
        pending = ""
        if not is_comment_line(line):
            out.append(line)
    if pending and not is_comment_line(pending):
        out.append(pending)
    return out


def recordset_source_table(source: str, table_names: set[str]) -> str | None:
    """The table a recordset source names: a table name, or a `SELECT` on one table.

    A `SELECT` joining tables, or listing several after `FROM`, opens a recordset on a
    join, and which table an `.AddNew` writes is then not a fact in the text.
    """
    cleaned = unbracket(source.replace('""', '"'))
    if cleaned in table_names:
        return cleaned
    match = SINGLE_TABLE_SELECT.match(source)
    if not match:
        return None
    name, rest = unbracket(match.group(1)), match.group(2)
    if rest.lstrip().startswith(",") or re.search(r"\bJOIN\b", rest, re.IGNORECASE):
        return None
    return name if name in table_names else None


def recordset_writes(text: str, table_names: set[str]) -> list[tuple[str, str]]:
    """`(procedure, table)` for each recordset write that can be attributed.

    `procedure` is empty for code outside any procedure. A variable is bound to the
    last table it was opened on within the procedure, and a write on it - `rs.AddNew`,
    `rs.Edit`, `rs.Delete`, or `.AddNew` inside `With rs` - is a write to that table.
    """
    found: list[tuple[str, str]] = []
    procedure = ""
    bound: dict[str, str] = {}
    literals: dict[str, str] = {}
    with_stack: list[str | None] = []

    def table_of(literal: str | None, variable: str | None) -> str | None:
        if literal is not None:
            return recordset_source_table(literal, table_names)
        if variable:
            held = literals.get(variable.lower())
            return recordset_source_table(held, table_names) if held is not None else None
        return None

    for line in logical_lines(text):
        start = PROCEDURE_START.match(line)
        if start:
            procedure, bound, literals, with_stack = start.group(1), {}, {}, []
            continue
        if PROCEDURE_END.match(line):
            procedure, bound, literals, with_stack = "", {}, {}, []
            continue
        assignment = LITERAL_ASSIGNMENT.match(line)
        if assignment:
            literals[assignment.group(1).lower()] = assignment.group(2)
        for match in DAO_OPEN.finditer(line):
            table = table_of(match.group(2), match.group(3))
            if table:
                bound[match.group(1).lower()] = table
            else:
                bound.pop(match.group(1).lower(), None)
        for match in ADO_OPEN.finditer(line):
            table = table_of(match.group(2), match.group(3) or match.group(4))
            if table:
                bound[match.group(1).lower()] = table
        with_open = WITH_DAO_OPEN.match(line)
        if with_open:
            with_stack.append(table_of(with_open.group(1), with_open.group(2)))
            continue
        with_variable = WITH_VARIABLE.match(line)
        if with_variable:
            with_stack.append(bound.get(with_variable.group(1).lower()))
            continue
        if re.match(r"^\s*With\b", line, re.IGNORECASE):
            with_stack.append(None)
            continue
        if END_WITH.match(line):
            if with_stack:
                with_stack.pop()
            continue
        for match in RECORDSET_VERB.finditer(line):
            variable = match.group(1)
            table = (bound.get(variable.lower()) if variable
                     else (with_stack[-1] if with_stack else None))
            if table and (procedure, table) not in found:
                found.append((procedure, table))
    return found


@dataclass
class WriteProfile:
    """Every writer of one table that could be attributed, and how."""

    writers: dict[str, set[str]]
    built_string_opens: int
    statements_naming_a_non_table: int

    def of(self, table: str) -> list[str]:
        return sorted(self.writers.get(table, ()))

    def summary(self, table: str) -> str:
        """One cell. Says "not attributable" rather than "never written"."""
        who = self.of(table)
        if not who:
            return "no writer attributable"
        verbs = sorted({w.rsplit("(", 1)[-1].rstrip(")") for w in who if "(" in w})
        return f"{len(who)} writer(s): {', '.join(verbs)}"


def write_profile(sources: dict[str, str], table_names: set[str]) -> WriteProfile:
    """Read every source for a statement or call that writes a named table.

    `sources` maps a label a reader recognises - `query X`, `form Y`, `module Z` - to
    its text. Query SQL and VBA are both read, because in this application family
    every write performed in normal operation is in VBA rather than in a saved query.
    """
    writers: dict[str, set[str]] = defaultdict(set)
    built = 0
    orphan = 0
    for label, text in sources.items():
        if not text:
            continue
        built += len(RECORDSET_BUILT.findall(text))
        for verb, target in WRITE_STATEMENT.findall(text):
            name = unbracket(target)
            first = verb.split()[0].upper()
            if name in table_names:
                writers[name].add(
                    f"{label} ({'SELECT INTO' if first == 'SELECT' else first})")
            else:
                orphan += 1
        # A whole statement - a saved query or a record source - is read again for a
        # make-table target, because the scan above stops at 200 characters and at a
        # quote, which a long column list or a literal in it reaches before `INTO`.
        made = make_table_target(text)
        if made in table_names:
            writers[made].add(f"{label} (SELECT INTO)")
        for call in TRANSFER_CALL.findall(text):
            for name in table_names:
                if '"' + name + '"' in call:
                    writers[name].add(f"{label} (TRANSFER)")
        for procedure, name in recordset_writes(text, table_names):
            where = f"{label}.{procedure}" if procedure else label
            writers[name].add(f"{where} (RECORDSET)")
    return WriteProfile(dict(writers), built, orphan)
