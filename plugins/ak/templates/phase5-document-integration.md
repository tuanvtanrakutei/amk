# {{APP_ID}} — Phase 5: Document Integration

Audience: person

<!-- TWO LAYERS, AND WHICH ONE THIS IS (A110)

     This document is in the person layer: a developer reads it once to rebuild the system.
     The record layer - the registers, the catalogues, the target-intent records, the
     traceability matrix, the to-be and the screen model - is read by agents. The two meet
     on `{{APP_ID}}_Decisions.md`, which `$ak decisions` generates: one row per decided
     item, the decision in force, and the evidence id that records it. Keep the
     `Audience: person` line above in every language; the conformance gate looks for it.

     Citation rules. When a round of decisions was applied to one application's phases,
     nearly every sentence came to end in "Decided: ... (<evidence id>)", some carried the
     history of a decision taken twice, per-screen field lists were pasted in, and the
     citations per document roughly doubled. Conformance still passed. So:

     1. Cite a decision by its item code - `RA-04`, `Q12`, or a decision-record row such as
        `D-EXPORT-NAME` - never by its evidence id. Evidence ids stay for facts about the
        legacy system.
     2. Cite at most one code per claim, at the end of the sentence.
     3. Put no decision history in the text: no "superseded", no "decided again", no list
        of replaced ids. Mark a corrected sentence once with its `(E-nn)`. The history is
        on the errata page and in `{{APP_ID}}_Decisions.md`.
     4. A list longer than about 10 rows belongs in a catalogue; this document points to it.
     5. Every evidence id you cite is a link to its row in this document's Evidence
        Register: `[A99-P1-CODE-004](#ev-a99-p1-code-004)`. The anchor is the id in lower
        case after `ev-`, and the register row opens with it (see the Evidence Register).
        Cite an id from another phase the same way, and list it in this register too.

     Writing order: prose first, then tables, then diagrams. Readable prose carries the
     argument - what the system does, why it matters, what the replacement must not get
     wrong. A table holds a set of parallel items the prose refers to. A diagram shows a
     mechanism the prose names: an order of steps, a cycle, a fan-out, a failure branch.
     This is the order of reading, not a ranking: the one-diagram floor below stands, and
     a mechanism still gets its diagram.

     The conformance gate's readability group measures 1, 3 and 5 (`citation_density`,
     `no_decision_history`, `evidence_links`) and warns; it never fails a run.
-->

<!--
  Characteristic claim: what the business says the system does, and where that
  differs from the code.

  This phase was treated as optional and it is the opposite. Everything the earlier
  phases could not say - what a table is for, who uses a screen, how often, why a
  rule exists, what happens outside the software - lives here or nowhere. DOCUMENT
  evidence is required; without it the phase is BLOCKED rather than degraded,
  because there is nothing for it to do.

  Its widest section is the one that used to be missing entirely: the landscape
  around the application. An application analysed without its neighbours produces a
  migration plan that discovers them at cut-over.

  Rule EC-04 governs every disagreement: a document claim contradicted by code
  produces TWO observations and one DISC- entry. Neither side wins silently.

  It is also the developer's hand-off. Phases 1 to 4 describe the legacy system; this one
  ends the set, so it opens with what the developer builds: the target scope, one row per
  in-scope screen, the interfaces and the export specification, and what is still open
  (`## Developer hand-off`). The full decision list is `{{APP_ID}}_Decisions.md`.

  Delete these comment blocks as you fill the document in.
-->

What you must not get wrong:

<!-- At most 7 numbered items, the first thing the reader meets. Each reads: the legacy
     fact, then what the replacement does (item code), then the section that proves it.
     For example:

     1. A cancelled order stays in the order table with a flag set; the replacement
        deletes it instead (RA-02). See §4.

     Before anything is decided, an item states the legacy fact and points to the risk
     that carries it. -->

## Naming Convention

Organisation, system, table and file names are the **production names**, unchanged.
JP-primary with a Romaji alias where they are Japanese. Never translate.

| Japanese (production) | Romaji alias | Kind |
|---|---|---|

## Source Coverage

| Evidence class | Supplied | Scope | What its absence costs |
|---|---|---|---|
| DOCUMENT | | | |
| INTERVIEW | | | |

<!-- WHO READS THIS, AND WHAT THAT COSTS YOU

     A reference file is read by an agent. A phase document is read by a developer who
     has to rebuild the system, and they read it once, under time pressure, looking for
     what they must not get wrong. Two habits follow:

     Open with what they must not get wrong: at most seven numbered items, each reading
     legacy fact, then what the replacement does (item code), then the section that
     proves it. One Phase 2 was correct and unusable before it had one:
     the fact that re-running the morning import destroys the quantities staff typed the
     night before was in the document, four sections deep, in prose.

     Write the prose first, then the tables, then the diagrams (the writing order above):
     prose carries the argument, a table holds a set, a diagram shows a mechanism.
     `references/technical-writing.md` holds the rules: how to write the prose, and which
     diagram for which shape.
     One required diagram per phase is a floor, not a budget. Reach for one whenever the
     thing being described has a shape: an order of steps, a cycle, a lifecycle with a
     failure branch, a fan-out from one object to many, or three artefacts that should
     agree and do not. One Phase 2 carries five and is shorter than the four-diagram
     draft it replaced, because each one removed a paragraph that was describing a picture.

     Mermaid renders, or it is not evidence a reader can see. Check it - `mmdc -i x.mmd -o
     x.svg` - before publishing. A sequence diagram reads better than a flowchart for
     anything with an actor and an order; a flowchart with a red-filled node is the
     cheapest way to say "this is where it goes wrong".

     Keep the document's own revision history out of it. How many drafts a figure went
     through is a fact about the analysis, not about the application, and a developer
     reading once does not need it: one Phase 2 carried a paragraph explaining that a
     count had been "wrong twice before it was right", naming all three numbers and both
     causes, and it was the hardest paragraph in the document to read.

     That history belongs in `BACKLOG.md` and in the commit. What the document keeps is
     the part a reader could otherwise get wrong - what a figure counts and what it
     excludes, stated plainly, so that a recount giving a different number is explained
     before it happens rather than after:

         A recount can legitimately give a different number, so two exclusions are worth
         stating. `DoCmd.OpenQuery` opens a query, not a screen: its 3 edges are excluded
         here, and counting them gives 39.

     The exception is a claim an earlier PUBLISHED phase made and this one corrects. That
     is errata, it has its own register and its own `E-nn` identifier, and it is owed to
     the reader because they may have acted on the earlier statement. A draft nobody
     outside the run ever saw owes nothing.
     For this phase: draw the system landscape and the network, because a reader
     cannot hold either in their head from a list. A document-versus-code
     discrepancy is worth a two-node diagram showing both claims side by side.
-->

## Decided for the replacement

<!-- ONE table, and the only place in this document where a decision's effect is spelled
     out. It replaces the "Decided: ..." text that otherwise ends up after every sentence
     a decision touches. One row per decided item that changes what this phase describes:

       Item                  the item code: a risk (`RA-04`), a question (`Q12`), or a
                             decision-record row no register holds (`D-EXPORT-NAME`).
       Decision              the word `{{APP_ID}}_Decisions.md` gives it: fix, preserve,
                             drop, defer, or decided.
       Effect on this phase  one sentence, with the section it changes.

     No evidence id and no history: the decisions page maps each code to its record and
     lists what it replaced. Before anything is decided, write "Nothing is decided yet."
     under the heading and leave the table empty. -->

| Item | Decision | Effect on this phase |
|---|---|---|

## Developer hand-off

<!-- This phase is the developer's hand-off: the document a developer opens to start
     building, once the five phases and their decisions are in. It holds four things, each
     short and each pointing to where the detail is. The full decision list is
     `{{APP_ID}}_Decisions.md`; point to it rather than copying it here.

     Target scope         what is in scope and what is not, by the item codes of the
                          TARGET_INTENT scope records. A screen, feed or table nobody has
                          scoped says so; an analyst's emphasis is not a scope (EC-07).
     Screens in scope     one row per in-scope screen: what it does differently in the
                          replacement, with the item code that decided it, and the Phase 2
                          section that describes it. Fields and controls stay in the
                          screen catalogue and the to-be.
     Interfaces and export specification
                          every file the replacement reads or writes (§7, `d0n` and
                          `r0n`), and where each export's layout is specified.
     Open points          what is still undecided, with its item code and the party that
                          settles it, as `{{APP_ID}}_QuestionList.md` routes it. The item
                          code goes in the second column: a question's own row in §11 must
                          stay the only row that opens with its id, because
                          `$ak decisions --assume` edits that row. -->

The full decision list is `{{APP_ID}}_Decisions.md`.

### Target scope

### Screens in scope

| Screen | Behaviour change in the replacement | Phase 2 section |
|---|---|---|

### Interfaces and export specification

| ID | Interface | Direction | Specified in |
|---|---|---|---|

### Open points

| Open point | Item | Party |
|---|---|---|

## Contents

1. [Document Inventory and Translation Coverage](#1-document-inventory-and-translation-coverage)
2. [Business Context](#2-business-context)
3. [Organization and Stakeholders](#3-organization-and-stakeholders)
4. [Operational Flow](#4-operational-flow)
5. [System Landscape](#5-system-landscape)
6. [Network Architecture](#6-network-architecture)
7. [Inter-System Data Interfaces](#7-inter-system-data-interfaces)
8. [Operational Function Catalog](#8-operational-function-catalog)
9. [Extracted Business Rules](#9-extracted-business-rules)
10. [Document-to-System Alignment](#10-document-to-system-alignment)
11. [Unresolved Mismatches and Stakeholder Questions](#11-unresolved-mismatches-and-stakeholder-questions)

---

## 1. Document Inventory and Translation Coverage

| Document | Language | Pages / sheets used | Business scope | Evidence |
|---|---|---|---|---|

<!-- A document that could not be read - no text layer, unsupported format - is
     listed with that status, not omitted. It is a gap an operator can close. -->

### Terminology

<!-- Where a Japanese term carries business meaning a gloss would lose, keep the
     term and explain it. This is where a replacement team learns the vocabulary. -->

| Term | Reading | What it means in this business |
|---|---|---|

## 2. Business Context

<!-- What this organisation does, at what scale, for whom. The numbers that make
     the system's constraints legible: sites served, daily volume, cut-off times. -->

| Dimension | Value | Evidence |
|---|---|---|

## 3. Organization and Stakeholders

<!-- Required diagram: the departments, and which uses which system. A migration
     plan needs to know whose work changes. -->

```mermaid
graph TD
```

| Department | What it does | Systems it uses | Evidence |
|---|---|---|---|

## 4. Operational Flow

<!-- What happens outside the software: goods, paper, people, sites. The system
     exists to serve this, and a replacement that models only the data model will
     reproduce the schema and miss the business. Omit the section only if the
     documents genuinely describe none of it - and say so if you do. -->

## 5. System Landscape

<!-- Every neighbouring system, not only the ones this application talks to. State
     the canonical source and its date: a landscape read off one diagram is only as
     current as that diagram. -->

| ID | System | Role | Relationship to {{APP_ID}} | Evidence |
|---|---|---|---|---|

<!-- Where two families of system have similar names and opposite directions - one
     receiving from customers, one issuing to suppliers - state the distinction
     explicitly. Conflating them is a mistake that survives into design. -->

## 6. Network Architecture

<!-- Required diagram: hosts, databases, shares, and what reaches what. Record the
     database engine actually in use, from evidence, not from the surrounding
     convention - the reference set carried a wrong engine for a whole phase. -->

```mermaid
graph TB
```

| Host | Address | Runs | Used by | Evidence |
|---|---|---|---|---|

## 7. Inter-System Data Interfaces

<!-- Required diagram plus two catalogues. These are the most reused artifacts this
     phase produces: the boundary map is built from them, and so is the migration's
     interface inventory. -->

```mermaid
flowchart LR
```

### 7.1 Inbound files

| ID | Name | Format | Source system | Path | Cadence | Evidence |
|---|---|---|---|---|---|---|

### 7.2 Outbound files

| ID | Name | Format | Destination | Path | Cadence | Evidence |
|---|---|---|---|---|---|---|

<!-- d0n and r0n identifiers, allocated here and cited by Phase 4 and the boundary
     map. An interface whose source or destination is recorded as "unknown" in the
     documents keeps that word - it is a real finding about the estate. -->

## 8. Operational Function Catalog

<!-- The functions as the business lists them, with cycle and timing. This is where
     a function the documents call unused, dangerous, or of unknown purpose gets
     recorded - each is a question for §11, and each is a scoping decision. -->

| No. | Function | Cycle | Timing | Status per the documents | Evidence |
|---|---|---|---|---|---|

## 9. Extracted Business Rules

<!-- BR-DOC-nn: a rule the documents state. It may or may not match the code; §10
     is where that is settled. Do not merge a document rule into a code-derived
     BR- from Phase 3 - keep both until they are reconciled. -->

| ID | Rule | Source document | Evidence |
|---|---|---|---|

## 10. Document-to-System Alignment

### 10.1 Confirmed

| Document claim | Code verification | Status |
|---|---|---|

### 10.2 Discrepancies

<!-- DISC-nn. Each names the document's claim AND the observed behaviour, both
     cited, with a severity. Neither side is silently preferred (rule EC-04). -->

| ID | Document says | Code does | Severity | Consequence | Evidence |
|---|---|---|---|---|---|

### 10.3 In the documents, absent from the code

| Item | Where documented | Code status | What it means |
|---|---|---|---|

### 10.4 In the code, absent from the documents

<!-- Usually the more interesting direction: undocumented behaviour a replacement
     would omit without knowing it existed. -->

| Item | Where in the code | Why it matters |
|---|---|---|

## 11. Unresolved Mismatches and Stakeholder Questions

### Carried forward from earlier phases

<!-- REQUIRED in every phase after the first, and written BEFORE this phase's own
     unknowns and questions.

     List every `UK-` and `Q` an earlier phase allocated and left open, one compact row
     each. The answer itself is not repeated here; it is in the row that closed it.

       ID           the identifier, as the earlier phase wrote it.
       From phase   the phase that allocated it: `Phase 1`.
       State        `open` or `closed`. Nothing else: a closed question called
                    "unchanged" is the defect the gate's `decisions_agree` reports.
       Closed by    the item code that closed it - a decided item (`Q12`, `RA-04`,
                    `D-EXPORT-NAME`), the question that answered an unknown, or the
                    identifier it duplicates - or a dash while it is open. An answer
                    that is a fact about the legacy system may cite its evidence id.

     Close it in the register too (`resolved_by`, or `superseded_by` for a duplicate),
     and keep this row in step when a later decision closes it.

     One Phase 2 skipped this section and allocated `Q108`, which asks what Phase 1's
     `Q103` already asked of the same owner about the same file. Two questions to one
     person about one thing is the cheapest kind of waste to avoid and the easiest to
     create.

     Before allocating any new `UK-` or `Q`, read this list. An unknown that is already
     open does not need a second identifier; an unknown this phase can close does not
     need carrying. -->

| ID | From phase | State | Closed by |
|---|---|---|---|

### Unknowns

<!-- `UK-Pnn` - Documents, the letter this phase owns. Each names the evidence
     class that would close it, so the operator is told what to fetch rather than
     that something is missing. -->

<!-- Columns are read by position, in any language - keep the order.
     Party     a name from input/decisions/parties.yaml, never a spelling of your own.
     Asked as  the Q that asks about this unknown. The unknown is the gap in this
               document and the question is the action, so a pair is one decision
               recorded twice on purpose and links through the question's `gap`. An
               unknown nobody is asked about carries its own `needs` in the register
               and says a dash here. -->

| ID | Unknown | Why it matters | What would settle it | Party | Asked as |
|---|---|---|---|---|---|

### Questions

<!-- Columns are read by position, in any language - keep the order.
     Blocks   identifiers only, comma separated (F-, WF-, BR-, RW- ...), or
              `object:<production name>`. It repeats the register's needs.blocks.
     Party    a name from input/decisions/parties.yaml, never a spelling of your own.
     Default  the AS- this phase proceeds on while the question is open, or a dash
              when there is none; the question then blocks what it names.
     Write \| for a pipe inside a cell. A cell that is prose is not wrong, but nothing
     can read it, and the checker counts it instead of comparing it.
     To close a question, set resolved_by in the register AND begin the row with
     **Answered - <evidence id>**. Leave Blocks and Party as they were: one run's Q120 was
     rewritten in place when it was answered, so its Blocks column now holds the original
     question, its owner column an evidence id, and its real owner is gone. -->

| ID | Question | Blocks | Party | Default |
|---|---|---|---|---|

### Assumptions

<!-- `AS-nn`. A belief the phase relies on that the evidence does not
     establish. `If wrong` says what in this document stops holding, which is
     what makes it worth writing down rather than a disclaimer.
     Name the identifiers it feeds (`RW-02`, `WF-001`) in that cell, not only the
     section numbers: they are the refresh set when an answer contradicts it, and the
     register's `if_wrong` for this `AS-nn` is that same sentence (ID-12, ID-13). -->

| ID | Assumption | If wrong |
|---|---|---|

### Observations

<!-- `OB-nn`. A property worth carrying forward that is not yet a rule or a risk.
     Each cites evidence. An observation nobody can act on yet is still worth an
     identifier, because the phase that can act on it needs to cite something. -->

| ID | Observation | Evidence |
|---|---|---|

### Risks

| ID | Risk | Severity | Detail | Mitigation | Decision |
|---|---|---|---|---|---|

<!-- In the register each risk carries a `needs` block (ID-11): kind DISPOSITION, party
     `decider`, default `mitigation`, and a `class` - technical, data, retired or
     behaviour - which is the key input/decisions/policy.yaml settles by. The Mitigation in
     this row is the recommended answer, carried until the decider says otherwise, so write
     it as an action the replacement takes. When it waits on an open question, name the Q
     in it and put the Q in `depends_on`. Write "none proposed" when there is none: the risk
     then has no default, and it blocks.

     Decision holds the disposition word and the code it is recorded under, as
     `{{APP_ID}}_Decisions.md` gives them: `fix (RA-04)`, or `drop (D-EXPORT-NAME)` when a
     decision-record row decided it. Write `open` until it is decided. Once it is, the
     Mitigation says what the replacement will build - the decided action - and the
     gate's `decisions_agree` warns when the row does not name the recorded word. Keep the
     column after Mitigation: the decision tools read the first five by position. -->

<!-- RS-nn for security and compliance risks surfaced by the documents. -->

---

## Evidence Register

<!-- Every claim above resolves here. Status is EXTRACTED, INFERRED or AMBIGUOUS; an
     INFERRED claim carries its confidence and never loses the label.
     Each row opens with its anchor, then the id: `<a id="ev-a99-p1-code-004"></a>A99-P1-CODE-004`
     - the id in lower case after `ev-`. Every citation above links to it, and every id
     cited above has a row here, an id from another phase included (`evidence_links`). -->

| ID | Status | Class | Claim kind | Source | Confidence |
|---|---|---|---|---|---:|
