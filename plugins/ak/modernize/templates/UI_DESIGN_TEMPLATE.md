# UI Design — {{PROJECT_NAME}}

> **Template.** Copy to the path `UI_DESIGN_DOC` names (the repository root, beside the frontend
> pattern documents, unless the project prefers otherwise) and fill every `{{...}}` and every
> `<...>`. Bootstrap offers a first draft from the frontend's theme file, its component library
> configuration and the extraction's To-be register; edit it, do not trust it.

What a screen of this system **looks like**. `{{FE_PATTERN_DOCS}}` say how a screen is
**built**; the extraction's wireframes (`{APP_ID}_Wireframes.html`) say what a given screen
**contains**. Where they disagree: a decision recorded in a screen plan wins, then this file,
then the component library's default.

## 1. Principles

1. **Familiar first.** Keep a screen's regions, their order, its tabs, its button groups and
   its labels as the legacy runtime view shows them. A layout change names the technical gap it
   fixes.
2. **Colours that mean something stay.** A colour the legacy screen used to signal a state, or
   to tell one kind of action from another (a menu that captions imports, exports and inquiries
   in different colours), keeps its meaning (section 3), in an accessible shade. Only a colour
   that tells the operator nothing is decoration; when unsure, keep it and ask.
3. **One primary for everything else.** A control with no colour of its own (a default button,
   the open tab, a file picker, the current page, navigation) uses the primary token.
4. **One theme.** Do not introduce a second styling mechanism for one screen.
5. **Keyboard first.** Enter moves to the next field and never submits.

## 2. Foundations

Theme file: `<frontend theme file, e.g. src/index.css>`. Component library: `<library, style,
base colour, icon set>`. Use the tokens, never a raw colour.

| Token | Value | Use |
|---|---|---|
| `<primary>` | `<value>` | Default buttons, active tab, links |
| `<destructive>` | `<value>` | Delete, errors |
| `<required marker>` | `<value>` | Required field marker |
| `<table head / selected row / edited row>` | `<value>` | Lists |

Type: `<root font size, body size, font stack>`. Systems of one family keep the same root font
size: every rem-based size, padding and gap scales with it, so one rule in the theme file makes
every screen of one system smaller or larger than its siblings.

## 3. Colours with a meaning

One row per state the legacy screens signalled with colour. Legacy values come from the
extraction's To-be register (`{APP_ID}_ToBe.json`, the `color` and `background` of a region's
fields, columns and actions).

| Meaning | Legacy | Replacement | State |
|---|---|---|---|
| `<what it signals, on which screens>` | `<legacy colour>` | `<token, contrast on its background>` | `<exists / to add with the first screen that uses it>` |

## 4. Layout

`<page header, field layout, action footer, tabs: which shared component, in what order>`

## 5. Lists and tables

`<table classes or component, header and width rules, row states, pagination sizes and default,
totals, the three states (loading, empty, error)>`

## 6. Forms

`<field components per type, label and required marker, date format shown and sent, message
constants and dialogs>`

## 7. Legacy control → component

| Legacy control | Component | Notes |
|---|---|---|
| Form caption | `<>` | |
| Label | `<>` | |
| Text box (editable / locked) | `<>` | |
| Combo box | `<>` | |
| Check box, option group | `<>` | |
| Command button | `<>` | |
| Tab control | `<>` | |
| Continuous form, datasheet | `<>` | |
| Subform | `<>` | |
| Report | `<>` | |
| Message box | `<>` | |

## 8. Changing this file

Change it in its own merge request, naming the screen that needed the change. A token this file
proposes is added to the theme in the merge request of the first screen that uses it.
