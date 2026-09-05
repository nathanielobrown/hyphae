# Design: one row per node kind

Put what varies by node kind on the node page into one table, `KINDS`, and make the NavTree's level table total by type. Eight route closures, two expansion routes, four partial registries and seven adapters become two tables and a handful of URL adapters. No URL, query or rendered byte changes. Every path and line here was read on 2026-09-03; check each at the file before acting on it.

Audit items: `plans/refactor-audit-2026-08-30/findings.md` C3 (routes hand-assemble binding dicts) and C6 (seven one-line NavTree adapters, two builders taking an unused `connection`).

## Problem

A turn is described in nine places, each a different shape and none total:

- `src/hyphae/view/nodes.py:GLYPHS`, `NUMBERED` — the shared vocabulary; total, and fine where they are
- `pages/node/columns.py:LISTED` — the shape of log that lists a kind, partial (4 of 8), read by one function
- `pages/node/nav_tree.py:CHILDREN` — 24 `(Kind, Preset)` cells, kept total by a comment, filled through seven adapters (`_session_level` … `_call_tools`, lines 497–522) that exist only because `_thread_level`, `_calls_level` and `_tools_level` take unpacked ids while the cell takes a `Ref`
- `pages/node/routes/browse.py:TITLED` and `routes/expansions.py:BODIES` — the same four builders written twice, one with the corpus ledger and one with `NO_LEDGER`; `BODIES` also carries the header query, its key binding, the children shape and count column, but only for three kinds, so `run_body` is a hand-written fourth
- `browse.described_node` — an if-chain over three kinds
- `routes/pages.py` — eight routes, each an inner `read` closure assembling a `Seen` by hand: header query and bindings, trail, shape, log page, details, record, citations. `session_page` and `run_page` differ by header, timeline query, details, trail and 404 text — real variation, but written as two 60-line closures around the same skeleton

Adding a kind (the last was `UNATTACHED`) means finding all of these; missing one is a runtime `KeyError` or a `None` that renders as a 404. The `reads.node_facts`, `reads.logged`, `nav_tree._parents`, `_hanging` and `body._facts` match statements are not on this list: the type checker closes a match over an enum, so each is already a total table.

## Call paths, current → proposed

```
current:  turn_page(url parts) ─defines─ read() ─assembles─ Seen ─passes─ browse(viewer, session_id, source, knobs, page, read)
          thread_body(kind) ─BODIES.get─ Body ─reads─ header, Listing ─calls─ expanded(...)
          run_body ─hand-coded copy of thread_body─ expanded(...)
          nav_tree.children ─CHILDREN[(kind, preset)]─ _turn_calls(conn, corpus, at) ─unpacks─ _calls_level(conn, corpus, source, turn_id)

proposed: thread_node_page(kind, …) ─Ref─ browse(viewer, session_id, at, knobs, page) ─KINDS[at.kind]─ header · trail · log · details · titled · describe
          thread_body(kind, …) ─Ref─ expanded(viewer, session_id, at, knobs) ─KINDS[at.kind]─ header · titled · describe · log (page 1, when it opens)
          nav_tree.children ─LEVELS[at.kind].under(preset)─ _calls_level(conn, corpus, at)
```

## File-tree diff

```
src/hyphae/view/
  nodes.py                          unchanged: Kind, GLYPHS, NUMBERED, Ref, Node, the URL minters
  pages/node/
    kinds.py                        new: KindSpec, KINDS, the per-kind cells (header, trail, log, details, titled, describe), spanned
    nav_tree.py                     CHILDREN → LEVELS: dict[Kind, Under]; the three id-taking builders take a Ref; seven adapters deleted
    columns.py                      LISTED and spanned leave; Shape, Column, COLUMNS, css stay — they are per shape, not per kind
    reads.py                        unchanged
    routes/browse.py                browse takes a Ref; Seen, Reader, TITLED, described_node, turn_log, call_log, run_log leave (the log helpers become KINDS cells)
    routes/pages.py                 eight closures → five URL adapters: session, run, thread/{kind}/{id}, unattributed, unattached
    routes/expansions.py            Body, Listing, BODIES, run_body deleted; thread_body and a run mount both call expanded(…, at, …)
    markup/body.py                  imports spanned from kinds instead of columns
tests/view/pages/node/test_kinds.py new: the two tables are total over Kind, and the cross-table invariants below
```

Deletion test: `_session_level`, `_run_level`, `_turn_calls`, `_bucket_calls`, `_turn_tools`, `_bucket_tools`, `_call_tools`, `Builder`'s 24-cell dict, `Seen`, `Reader`, `TITLED`, `described_node`, `Body`, `Listing`, `BODIES`, `run_body`, `LISTED`, and the eight `read` closures. `rg -n 'TITLED|BODIES|LISTED|CHILDREN|Reader\b|Seen\b' src/hyphae/view` returns nothing when the change is done.

## Key contracts

**`kinds.KindSpec` — one `NamedTuple` per kind, `KINDS: dict[Kind, KindSpec]` total over `Kind`.** The interface the page reads through; the row is internal to `pages/node/`.

| cell | type | what it settles today |
| --- | --- | --- |
| `header` | `Callable[[Connection, Corpus, Ref, int], Found \| None]` | the header read; `int` is the detail width (`knobs.detail` on a page, `HEADER_CHARS` in an expansion). Five kinds use `keyed(Page.X_HEADER, "x_id")`, a factory returning the cell; compaction filters `Page.COMPACTIONS`; the buckets read `nav_tree.unattributed` / `corpus.runs`. `None` is the 404 the route raises with `missing` |
| `missing` | `str` | the 404 text, today spelled in eight routes and two expansion mounts |
| `trail` | `Callable[[Ref, Row], list[Ref]]` | what `nav_tree.ancestry` seeds; a call and a tool read the turn off the header row |
| `under` | `Shape` | the children log's shape (`Seen.shape`, `Body.shape`) |
| `counts` | `str \| None` | the header column counting the children (`Body.children`) |
| `opens` | `bool` | whether an expansion lists the level rather than counting it — true for the api call alone |
| `log` | `Callable[[Connection, Corpus, Ref, int, int], Log] \| None` | one page of the children log: `(page, size)` in, `Log(rows, total, ran)` out; today's `turn_log`, `call_log`, `run_log`, the two `window(...)` timelines and `sliced(loose)` |
| `details` | `Callable[[Row, Node, int], list[Detail]]` | the fat values the pane previews; the tool's reads a syntax off the row, which is why this is code and not a list of names |
| `record` | `Callable[[Connection, Ref], tuple[int \| None, Ran]] \| None` | the transcript line, turn only |
| `titled` | `Callable[[str, str, Row, Ledger, str \| None], Node] \| None` | the pane's own node from its header; `None` where the NavTree's row already names it (session, compaction, buckets). One signature for both mounts: the page passes `corpus.held`, an expansion `NO_LEDGER` |
| `describe` | `Callable[[Descriptions, Ref], Enrichment \| None] \| None` | which map a pass wrote the node into; `None` for the five kinds no pass describes |
| `listed_as` | `Shape \| None` | the log that lists this kind; what `spanned` reads for an expansion's colspan |

`Found(row: Row, ran: Ran)` and `Log(rows: list[Logged], total: int, ran: Ran)` are the two small `NamedTuple`s the cells return. Every cell takes the `Ref` and derives ids from it — no cell closes over URL parts, which is what makes `browse(viewer, session_id, at, knobs, page)` the whole interface.

**`nav_tree.Under(NamedTuple)`: `full`, `no_api`, `agents`**, each a `Builder = Callable[[Connection, Corpus, Ref], Level]`; `LEVELS: dict[Kind, Under]`. `Under.at(preset) -> Builder` is a match the checker closes. `_thread_level`, `_calls_level` and `_tools_level` derive `source`, `turn_id`, `api_call_id` and the unattached flag from `at.kind` the way `_agent_thread` already does at `nav_tree.py:482`. Builders that read nothing keep the `connection` parameter: a uniform signature is the price of a table cell, and C6 offered either.

**Invariants a test holds** (`tests/view/pages/node/test_kinds.py`): `set(KINDS) == set(Kind) == set(LEVELS)`; `opens` implies `KINDS[child].under is Shape.NONE` for the kind `under` lists; `counts is None` iff `under is Shape.NONE`; `listed_as` is a key of `COLUMNS` or `None`.

**Route grammar unchanged.** `/session/{id}`, `/session/{id}/run/{run_id}`, `/session/{id}/thread/{source}/{kind}/{node_id}`, `/session/{id}/thread/{source}/unattributed`, `/session/{id}/unattached`. The `{kind}` handler resolves `Kind(kind)` and answers 404 on a bad word, as `thread_body` and `node_numbers` do today. The thread `browse` reads on is `at.source or MAIN_SOURCE`.

## Chosen test seam

The URL, as the suite already drives it: every node kind has a page scenario and the four listed kinds have a body scenario in `tests/view/scenarios.py`, and the leaves under `tests/view/pages/node/` and `tests/view/test_bounds__node.py` read the bytes. Before slice 1, capture every fixture page's bytes with `tests/view/conftest.py:render_pages` to scratch under the OS temp directory; re-run after each slice and require an empty diff. Nothing rendered changes, so the diff is the proof.

No test imports the registries this design deletes (`rg -n 'CHILDREN|BODIES|TITLED|LISTED|Seen|Reader' tests/view` finds a test-local `CHILDREN` dict in `test_node.py:228` and comments naming `columns.LISTED`; update the comments). The only new test is the invariant leaf above, which is the table's own contract and not a test of a module behind it.

## Slices

Each is one commit, green on `mise run check` alone, with an empty byte diff.

1. **Ref-taking level builders (C6).** `_thread_level`, `_calls_level`, `_tools_level` take `at: Ref`; delete the seven adapters; `CHILDREN` → `LEVELS: dict[Kind, Under]`; `children()` reads `LEVELS[at.kind].at(preset)`. Add `test_kinds.py` with the `LEVELS` totality assertion. This slice proves the seam: the NavTree's bytes are unchanged with the table replaced under it
2. **`kinds.py` and the expansions.** `KindSpec`, `KINDS` with every cell filled (the page-only cells are ready one slice early, which is the cost of one table); `expanded(viewer, session_id, at, knobs)` reads `header`, `titled`, `describe`, `counts`, `opens`, `log`. Delete `Body`, `Listing`, `BODIES`, `run_body`; two mounts remain. `spanned` moves to `kinds.py`; `LISTED` goes; `body.py` follows the import. Extend `test_kinds.py` with the `KINDS` invariants
3. **`browse` reads the row.** `browse(viewer, session_id, at, knobs, page)`; delete `Seen`, `Reader`, `TITLED`, `described_node`; `turn_log`, `call_log`, `run_log` become `log` cells; `pages.py` becomes five URL adapters. C3 closes here: the only binding dicts left are inside the cells that run the query they bind
4. **Docs.** Glossary lines below; `.claude/rules/viewer-ui.md` and `docs/viewer.md` name no deleted symbol (verified by `rg`), so this is `CONTEXT.md`, the module docstrings, `mise run cogs`, and a doc-sync pass over the branch

## Decisions

- **Two tables, not one** — rejected a single `KindSpec` carrying the three NavTree builders: `kinds.py` would import `nav_tree.py`'s builders while `nav_tree.children` imports `kinds.py`, and breaking the cycle means splitting `nav_tree.py` into a levels module and a tree module — a move this change does not need. Nothing reads a kind's header and its NavTree levels in one place, so one row would be wider, not deeper. Both tables are total over `Kind` and one test holds both
- **Match statements stay** — rejected folding `reads.node_facts`, `reads.logged`, `_parents`, `_hanging` and `body._facts` into the table: the checker closes a match over an enum, and a dict is closed only by a test. What goes in the table is what a dict or a closure already held partially
- **`GLYPHS` and `NUMBERED` stay in `nodes.py`** — `Node.icon` and `Node.numbers` read them in the shared layer, which `test_layout.py` forbids from reaching a page. The candidate counted them among the nine; leaving them costs no duplication
- **Cells are callables over a `Ref`, not data** — rejected a data row (`header: Page`, `keyed: str`, `details: list[str]`): compaction has no header query, the buckets have no row, the tool's details read a syntax off the row. Five of eight headers *are* data, so the `keyed(page, key)` factory writes those cells in one line each. A cell is code where the kinds genuinely differ, which is the honest width of the variation
- **Five URL adapters, not eight** — the thread kinds share `/thread/{source}/{kind}/{node_id}` the way `expansions.thread_body` and `popovers.node_numbers` already do; a route that resolves a `Kind` from the URL and answers 404 on a bad one is the existing pattern
- **`browse.py` stays under `routes/`** — it raises `HTTPException` and returns a `Response`. `kinds.py` raises nothing: a header cell returns `None` and the route says 404, so the table is already framework-free
- **Relation to `plans/deepen-viewer-reads/design.md`: compatible, and a prerequisite of its node-page step.** That plan's slice 4 removes the callback `Reader`, keeps "kind-specific variation private" and moves `browse` toward a framework-free `browser.py`; `KINDS` is the mechanism for the first two and leaves the third untouched. Land this first: it is byte-identical and smaller. `Found` and `Log` stay in `kinds.py` rather than a `models.py` because they never cross into markup — the `models.py` rule in `test_layout.py` still reads zero after this change. Adopt that plan's byte-capture discipline here
- **`opens` is spelled, not derived** — rejected deriving "an expansion lists its level iff the children open nothing further": true today, but a rule a reader has to work out; the invariant test says the same thing loudly
- **Exemplar** — the brief named `plans/records-as-parser/design.md`, which does not exist; this follows `plans/view-layout/design.md`

## Out of scope

- Collapsing `Shape` into `Kind` (a log's shape is the kind of child it lists, plus `NONE`): it changes served `data-shape` values, the stylesheet and the byte pins. Once `KINDS` exists it is a one-column edit; do it as its own change
- Moving `browse.py` out of `routes/`, the two-dependency chain, and `models.py` — `plans/deepen-viewer-reads/`
- A compaction header query to make the sixth header a `keyed(...)` cell; the Python filter over `Page.COMPACTIONS` is one line and the query library is versioned
- Popovers (`routes/popovers.py`): four routes keyed by URL grammar, one branch on `Kind.TOOL`, nothing duplicated across kinds

## Open questions

- **Does `Under.at(preset)` earn a method, or should `LEVELS` stay keyed `(Kind, Preset)` with the adapters gone?** The NamedTuple makes the preset axis checker-total; the tuple key keeps `children()` a one-line lookup. The design prefers the NamedTuple; the implementer should keep the other if the match reads worse than the 24 lines it replaces
- **Should the tool's `details` cell read `result_type` at all**, or should `view_tool_header.sql` ship the syntax name? Out of this change either way, but it is the one cell that keeps `details` from being data

## Glossary changes

`CONTEXT.md`, under "Node-page anatomy", after **Node**:

- `- **Kind** — which of the eight things a node is; its row in `src/hyphae/view/pages/node/kinds.py:KINDS` says what its page reads, lists and previews, and `nav_tree.LEVELS` what hangs under it in each preset`
- `- **Shape** — the kind of child a children log lists, or none; the columns are the shape's (`src/hyphae/view/pages/node/columns.py:COLUMNS`), and a kind's row names both the shape under it and the shape that lists it`
