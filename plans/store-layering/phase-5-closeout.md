# Phase 5: close-out

Delete what phase 4 carried so its PRs stayed moves, make the handle's two verbs private, hold the graph the code already draws with the contract, rename the two store classes that still name the driver, and bring the documents to the code. Four PRs; the rename opens last.

Back to [the overview](overview.md). Amended 2026-09-18 against `origin/main` = `13dc9f7`, after PR 4.8 landed; every path and count below was read that day — verify at the file before building on it.

## Problem

After 4.8 no module outside `store/` reaches `Store.rows` or `Store.connection` (`tests/store/test_handle.py:REACHING == frozenset()`), but the tree still says otherwise. `store/pages.py` holds one alias, `Row = dict[str, Any]`, that the NavTree's builders take (`rg -l 'from hyphae.store.pages import Row' src tests`), so the store still exports a dict type a page takes. The two verbs are public because phase 4 could not close the door mid-move (`phase-4-repositories.md:112`, `:156`), and `handle.py`'s docstrings, `store/__init__.py`'s (which `AGENTS.md`'s layout gloss prints), `docs/store.md:43` and `CONTEXT.md`'s **Store handle** line all describe `rows` as the way a package outside the store runs SQL. `tests/view/test_layout.py:STORE` is an enumerated deny-roster, so a store module added tomorrow is one a routes module may import until someone lists it. The layers contract puts `analyze | export` under `view | enrich`, so `view → analyze` is legal by the gate; `tests/tools/test_gen_imports.py:83-101` holds three of the four edges the collapse newly forbids at test tier; `enrich → analyze` is held by nothing, and nothing declarative names any of them. `DuckDbExporter` and `StoreSource` name the driver and a shape rather than their pipeline roles. And `lint-imports` runs in `check-fast` and CI but not in `tools/pre-commit`.

What 4.7 and 4.8 called "phase 5's fold" — the builders and `nodes.ledger` taking row models instead of `Row` — is not a layering move, and this phase does not do it (Decisions).

## Call paths, current → proposed

```
current:  view/builders.py ─takes─ store.pages.Row ─made by─ nav_tree.py:asdict(NavTurnRow) …
proposed: view/builders.py ─takes─ view.nodes.Row  (the same alias, now the viewer's own); store/pages.py gone

current:  SessionRepository ─calls─ store.rows(sql, bindings)      EnrichmentRepository.connection ─returns─ store.connection
proposed: SessionRepository ─calls─ store._rows(sql, bindings)     EnrichmentRepository.connection ─returns─ store._connection
          (every caller is in `src/hyphae/store/`, where SLF001 is ignored per file; the repository's `connection` stays the planter's door)

current:  layers "view | enrich" over "analyze | export"; the peer edges held by test_gen_imports.py's diagram leaf
proposed: one line "view | enrich | analyze | export"; a forbidden contract keeps the four off `extract`, the edge layers cannot say

current:  cli.py ─builds─ trace_store.DuckDbExporter (an Exporter)   trace_reader.StoreSource (an Extractor)
proposed: cli.py ─builds─ trace_store.StoreExporter                  trace_reader.StoreExtractor
```

## File-tree diff

```
PR 5.1  the alias and the roster
src/hyphae/store/pages.py          deleted; `rg 'store\.pages' src tests tools .claude` empty at head
src/hyphae/view/nodes.py           ~ `Row = dict[str, Any]` lands here, the SHARED module every taker sits at or above (`tests/view/test_layout.py:LAYERED`); the importers re-point
tests/view/test_layout.py          ~ `STORE` derived from `pkgutil.iter_modules(hyphae.store.__path__)` minus `library`; the page-models leaf checks `Row` against `hyphae.view.nodes`; the `:53` comment
.claude/rules/viewer-ui.md         ~ `:11` glob drops `pages` from its member list
src/hyphae/store/macros.py         ~ the comment above `SETUP` names `view/pages/query/`, not `view/pages.py:query_page`
src/hyphae/view/bounds.py          ~ `:192` names `library.bind`, not the deleted `bound`

PR 5.2  the handle's privacy and the documents
src/hyphae/store/handle.py         ~ `_connection`, `_rows`; module and class docstrings to the present: the repositories are the interface, nothing says "until"
src/hyphae/store/{analysis,enrichment,library}.py  ~ `store._rows`; `enrichment.py`'s `connection` returns `store._connection`, docstring rewritten (`rg 'store\.(rows|connection)\b' src`)
pyproject.toml                     ~ `per-file-ignores`: `SLF001` off for `src/hyphae/store/**` and `tests/store/**`, with the note that the underscore is the store's package line, and that the test glob also frees a module-level `_name` such as `nodes._windowed` — none reached at head
tests/store/*.py                   ~ the direct verb sites re-spelled (`rg 'store\.(rows|connection)\b' tests/store`); `test_handle.py:10-12`, `:35-38` say what holds now; `VERBS` scans the private spellings and the delegate
src/hyphae/store/__init__.py       ~ docstring: no "only way any other package runs SQL"; `mise run cogs` carries it into `AGENTS.md`
CONTEXT.md                         ~ **Store handle**: its repositories are the only reads, and the driver never leaves the package; **Store**: "the reads a viewer page runs" → the repositories
docs/store.md                      ~ `:43`; a "Who reads and writes" paragraph: one repository per area (`handle.py`'s properties), the trace writer and reader by module path, the OTLP ledger, only `store` names the driver

PR 5.3  the contract says what the graph draws
tests/tools/conftest.py            ~ `contract(name)` selects by contract name, not type (`:39-43` single-unpacks one per type and raises on a second forbidden)
tests/tools/test_import_contract.py ~ `run_contract` writes every contract the table holds, any one's sources overridable by the contract's name; `KEPT` counts three; the two lifts retargeted; one new red case
pyproject.toml                     ~ layers: "view | enrich | analyze | export" on one line; a third contract below
tools/pre-commit                   ~ `lint-imports` beside pyrefly when Python is staged; the header (`:2-4`) says so
docs/layering.md                   ~ the prose names three contracts and drops "Later phases of the store-layering plan edit the list"
CONTEXT.md                         ~ **Forbidden contract** covers both forbidden contracts
mise.toml                          ~ the `lint-imports` description names all three
tests/view/test_layout.py          ~ the routes leaf denies the store and the root package taken whole, and any `as` name bound under the store; the models leaf denies `nodes` taken whole
tests/store/test_handle.py         ~ the handle scan sees a copy of a handle, plain, typed or stashed, with a positive leaf per spelling; a public-namespace leaf over the class and a fresh instance

PR 5.4  renames, opened after 5.1–5.3 land
src/hyphae/store/trace_store.py    ~ DuckDbExporter → StoreExporter
src/hyphae/store/trace_reader.py   ~ StoreSource → StoreExtractor; every importer, `rg 'DuckDbExporter|StoreSource' src tests tools docs` empty at head
CONTEXT.md                         ~ **Extractor**: "reads sessions into the model — an agent's recordings, or the store's own rows"
src/hyphae/pipeline.py             ~ the `Extractor` protocol, the module and `SessionSource` docstrings say the same widened thing
```

## Key contracts

The layers contract after 5.3, matching the overview's after-diagram and the graph `docs/layering.md` generates today (probed with import-linter `--no-cache` at head: both kept, `|` is independence):

```toml
layers = [
  "cli",
  "view | enrich | analyze | export",   # peers: none imports another; all four read the store
  "store | extract",
  "pipeline",
  "user_settings",
  "models | projects | pricing | settings | store_path",
]

[[tool.importlinter.contracts]]
name = "Nothing above the store parses a transcript"
type = "forbidden"
source_modules = ["hyphae.view", "hyphae.enrich", "hyphae.analyze", "hyphae.export"]
forbidden_modules = ["hyphae.extract"]
```

The handle after 5.2: `Store._connection` and `Store._rows(sql, bindings) -> Fetched`, both private; the public names are the repository properties. The repositories are already built inside `Store` (`handle.py`'s `cached_property` bodies), so what privacy costs is the underscore at every in-package caller and one `per-file-ignores` line: ruff's `SLF001` (on, `pyproject.toml:138`) flags `store._rows` from a repository, and `.claude/rules/python.md` says a conflicting rule is disabled in `pyproject.toml`, never with `noqa`. The test glob is there for the 13 direct verb sites over five files (`rg 'store\.(rows|connection)\b' tests/store`): `test_handle.py` is the verb's own leaf and pins the verb's spelling, not a helper's, and a helper would need two `noqa`s (`_rows`, `_connection`), past the one site the house rule allows; the price is that a `tests/store` leaf may reach any store module's `_name`. Outside those two globs `SLF001` stays on, so the lint is the door at the hook, and the ratchet leaf (`reached() == frozenset()`, `VERBS` re-spelled `_rows`/`_connection`, plus `connection` on a `store.enrichment` receiver) the same door at test tier. `EnrichmentRepository.connection` stays public: the writers, `check_shape` and the 46 planter sites in `tests/enrich` and `tests/store/test_enrichment.py` run on it, and none of them is a package line.

`Row` after 5.1 is `hyphae.view.nodes.Row`, the same `dict[str, Any]`; no signature it appears in changes. "No store module exports a dict type a page takes" is held by the derived `STORE` leaf and `queried()` — `library.fetch` and `one` still return dict rows, and the leaf is what keeps them out of a routes module.

Glossary: **Repository** and **Store handle** exist; 5.2 rewrites the latter's second clause; 5.4 widens **Extractor** so the rename honours the term. No new term.

## Chosen test seam

Every PR renders the same bytes; the oracle table is phase 4's, rebuilt from the repo rather than from `/tmp`:

| Oracle | What it is | 5.1 | 5.2 | 5.3 | 5.4 |
| --- | --- | --- | --- | --- | --- |
| Render vs base | every scenario in `tests/view/scenarios.py` and every `/query/<name>` page over `tests.conftest.build_enriched_store`, served by `tests.gallery`, diffed against `main` | no change | no change | no change | no change |
| Bindings dump | `library.bind` calls logged during the render, sorted | no change | no change | — | no change |
| Whole-store dump | every table's rows, minus the three build-time timestamps | no change | no change | — | no change |
| `hp query` × every `library.names()` | citation and CSV over the fixture store | no change | no change | — | no change |
| `mise run e2e` | the browser tier | run | run | — | — |
| `mise run lint-imports` | contracts kept | 2 | 2 | 3 | 3 |
| `mise run mutate` | — | none: no logic moves | — | — | — |

Leaves that go red on the wrong edit: 5.1's derived `STORE` reds a routes module taking any store module a future PR adds, and a planted `from hyphae.view.nodes import Row` in a page's `models.py` reds the page-models leaf. 5.2's ratchet reds `store._rows` in any module outside the store; `ruff check` reds the same edit in any file outside the two globs, tests included. 5.3's new case widens the third contract's sources to `hyphae.cli`, the one importer of `hyphae.extract` (`rg -l '^(from|import) hyphae\.extract' src/hyphae --glob '!src/hyphae/extract/**'`), and reads `1 broken` — the shape `test_import_contract.py:161` already uses; the two lifts (`store_above_view`, `enrich_above_view`) retarget to the wider line. The hook change has no leaf: `mise run lint-shell` lints the script and nothing runs it; a staged `view/x.py` importing `hyphae.extract` failing the hook is a manual probe the PR body records, with the caveat that grimp reads the tree, not the index, as pyrefly already does there. 5.4 has no leaf but the suite and `rg` for the old names.

## Slices

Independence is a file claim: 5.1 and 5.2 share no file, and 5.3's `pyproject.toml` hunk sits sixty lines from 5.2's under another table (`git merge-tree` of the two on a scratch clone: clean), so all three are siblings off `main`. 5.4 touches only the two store modules, `cli.py`, `store/delivery.py`'s comment, `tools/gen_routes.py`, `CONTEXT.md`'s **Extractor** line, `pipeline.py`'s docstrings and the tests that build a writer or reader, and opens last (Decisions, renames last).

1. **PR 5.1, the alias and the roster** — two commits: (1) `Row` to `view/nodes.py`, the importers re-pointed, `store/pages.py` deleted, the `viewer-ui.md` glob, `STORE` derived and the page-models leaf re-pointed; (2) the two stale comments. Verify: `mise run check`, `mise run e2e`, the four dumps against `main`.
2. **PR 5.2, the handle's privacy and the documents** — three commits: (1) the underscores, the `per-file-ignores` line, the test sites, the ratchet's `VERBS`; (2) the docstrings, `CONTEXT.md`, `mise run cogs`; (3) `docs/store.md`. Verify: `mise run check`, the four dumps, `mise run e2e`; plant `store._rows` in `view/deps.py` and watch both the ratchet and `ruff check` go red.
3. **PR 5.3, the contract** — four commits: (1) the harness: `contract(name)`, `run_contract` writing every contract, green over the two it finds; (2) `pyproject.toml`, `KEPT` to three (a count the harness commit cannot bump ahead of the table) and the new red case; (3) `tools/pre-commit` and `docs/layering.md`; (4) the spellings the 5.1 and 5.2 audits found the AST scans blind to, each held in the leaf that owns the scan: a helper for the alias, a second scan pass for a copied handle with a positive leaf beside it, and a public-namespace leaf reading the class and a fresh instance. Verify: `mise run lint-imports` says three kept; the hook probe above.
4. **PR 5.4, the renames** — two commits, one per class, each a `fastmod` over `src tests tools docs` with the class docstring reread, the glossary line and `pipeline.py`'s docstrings in the second; a third renames the `source` locals the OTLP send and its tests bind a `StoreExtractor` to, since `refresh(sources, *, extractor, exporter)` gives each word one meaning. Verify: `rg` empty, `mise run check`, the four dumps: a rename cannot reach a row, since `trace.extractor` credits the recorded extractor (`tests/store/test_trace_reader.py:114-118`).

Overview row: `5.1 the alias and the roster; 5.2 the handle's privacy and the documents; 5.3 the contract and the hook; 5.4 the renames — 5.1–5.3 siblings off main, 5.4 after all`.

## Decisions

- **Four PRs, not one.** Each is one refactor under the overview's rule: a deletion, a privatization, a contract, a rename. Rejected: the 2026-09-16 draft's one PR of three commits — a reviewer reading a rename diff beside a deletion diff reads neither.
- **The verbs go private, with one `per-file-ignores` line.** Phase 4 promised it (`:112`, `:156`), the ratchet holds outside callers at zero, and the house rule prefers a scoped ignore to a `noqa`. Rejected: leaving them public with a `vars(Store)` pin — `connection` is set in `__init__`, so a class-namespace scan never sees it; `ignore-names = ["_rows"]` — global, and `_connection` would need a second entry.
- **`EnrichmentRepository.connection` stays public.** It is the writers' spelling of the handle's connection and what the planter sites run on; the pass is the store's tenant, not a package line. Rejected: `store._connection` at every site — a `tests/enrich` glob in the ignore list for churn that moves no edge.
- **The builders' fold is not phase 5's.** `builders.py` reads optional columns with `row.get("context")`, `.get("tools")`, `.get("fields")`, `.get("call_cost_usd")` because one builder serves rows of two to four models that differ by those columns; folding onto models is a viewer design about how one builder serves four shapes, and the largest diff in this document by far. The layering property — the store exports no dict type a page takes — is met by moving the alias. Rejected: a 5.5 doing the fold with a `Protocol` per builder — the optional columns have no Protocol spelling, so the design has forks a close-out should not settle in passing.
- **`Row` lands in `view/nodes.py`, not `models/`.** A `dict[str, Any]` is not a model, and `models/row.py` holds `ROW`, the config every row model is declared under. Rejected: `view/builders.py` — `nodes.py:ledger` takes it too and sits below.
- **Collapse the layer line, then forbid `extract` alone.** `test_gen_imports.py` already holds `view → analyze` and `view → enrich` out of the diagram at test tier; what the wider line buys is every pair among the four, at `check-fast` and the hook, declared in the TOML a reader consults — and that leaf stays as the diagram's pin. `extract` sits below the four and stays legal by layers, so one forbidden contract holds that edge. Rejected: the draft's four-module forbidden contract over today's layers — restates what a line can say; no contract — the hold stays a test over a rendered graph.
- **`STORE` derived, `library` excepted by name.** A routes module takes `FIRST_PAGE` and `BINDABLE` from the library, held by the `queried()` leaf beside it; every other store module is denied whole — wider than the 4.6 audit's "minus the handle, the library and the writers", because a routes module takes its `Store` from `deps` as a `Db` and never opens one. Rejected: keep the tuple — an enumerated deny-roster is green for a module nobody listed.
- **`lint-imports` in the hook.** 0.1s uncached; the hook's stated scope is "format, lint, type-check", and the layers contract is a lint. Rejected: leave it to `check` — the gate phase 0 bought is the one a commit should meet.
- **`StoreExporter` and `StoreExtractor`, with the glossary widened.** `OtlpExporter` and `ClaudeCodeExtractor` spell sink-or-source then pipeline role, and `pipeline.py` types the seam in those roles; **Extractor** today says "one agent's sessions", so 5.4 bends the line in the same PR. Rejected: the draft's `TraceWriter`/`TraceReader` — honours the term untouched but names the modules and loses the role the seam is typed in.
- **`nodes.unattributed` keeps citing without `cap`.** 4.8 landed the bucket footer that way; citing it now is a rendered-byte change this phase does not make. `_windowed` cites its wrapper's `offset` and `limit`, so the two are inconsistent, and a later viewer PR that names the byte change may align them.
- **`TABLES` is not folded: it already was.** `TableSpec.order` drives `trace_reader._read` and `tests/store/test_trace_reader.py:55-62` reads it off the same registry.
- **Renames last** — unchanged: a rename in a move PR hides the move.

## Out of scope

- The builders and `nodes.ledger` on row models, `Found.row`'s union, `reads._read` by attribute, and with them the `nav_tree.NAV` spelling (a module constant handed to reads that take a `Mapping` and write nothing) and `Levels.asked: dict[Asked, Any]` (a heterogeneous memo has no `T` to keep). A plan of their own.
- The `project=None` passthrough gap the 4.5 mutants exposed — `run_items`, `_session_children` and `_command_results` never select under a project filter (`handoffs/handoff_2026_09_18_impl-pr-4-5.md`), the 47 `store.enrichment` survivors with it: a test-only follow-up PR of its own, since every 5.x PR is a move, a contract or a rename. The six `library` survivors are equivalent.
- `Failures` and `ProjectRollups` into one `Cut[T]`: two three-field tuples with different docstrings is a coincidence until a third arrives; `Paged` carries a cursor and is not one.
- A "no import-only module" leaf: a statement-count probe over `src/hyphae` cannot tell `pages.py` from `models/row.py` or `settings.py` (a docstring and one assignment), so no leaf separates the alias module from the ones that stay; 5.1 deletes the last one by hand.
- `reports/` citing `src/hyphae/analyze/queries/`: dated passes describe the repo as it was, and `aigarden.toml` exempts them from `bare-path` for that reason.
- `hp export-otlp` behind the handle, `tests/view/conftest.py:reading` as a raw connection, a `.claude/rules/` file for the store, the Notion page: as phase 4 left them.

## Open questions

- **Where the fold's plan lives** — `plans/view-row-models/` is the suggestion; Nathaniel decides whether it opens after phase 5 or waits for a page that needs it.
- **`Nothing above the store parses a transcript`** — settled by 5.3 (#76): the contract went in, and the harness reshape (`contract(name)`, `run_contract` over every contract) cost one commit.
- **The rename targets** — settled by 5.4: `StoreExporter`/`StoreExtractor`, with **Extractor** and `pipeline.py`'s docstrings widened to match.

## What the plan leaves open

Every follow-up the phase-5 PR bodies named, consolidated for the close-out. Each PR body holds the evidence; this list only points. The Out of scope list above stands beside it.

From #74 (5.1):

- The builders and `nodes.ledger` on row models instead of `Row`: the viewer design the Decisions defer. (The three alias and whole-package evasions it named were closed by 5.3's fourth commit.)

From #75 (5.2):

- The ratchet's receiver check misses a copied handle when the first hop sits deeper than the second in walk order (`if x: a = store` at one level, `b = a` at the function's); a chain in one scope is seen. (The `rows = _rows` public-namespace gap was closed by 5.3.)
- `tests/store/**` disables `SLF001`, so a leaf there reaches any `_name` without a lint; review holds it.

From #76 (5.3):

- Two scanner mutations survive: the routes leaf's whole-package loop cut to `for module in STORE:`, and the models leaf's `assert not whole(...)` to `pass`; killing them needs a planted route or model seam the leaves lack.
- Dynamic imports (`importlib.import_module`, `__import__`) evade every AST scan; no in-tree module does it, and an `rg 'import_module|__import__' src` leaf would bound it.
- `repo = store.enrichment; repo.connection.execute(...)` passes the ratchet, which watches the handle's private verbs rather than a repository's public `connection`; whether a repository may export its connection is a phase-6 question.
- The `project=None` passthrough gap (Out of scope above) stays open.

From 5.4's audit, a tooling finding:

- On macOS, `mise run mutate` cannot score a mutant whose forked child reaches a watchfiles-driving test: mutmut runs the clean suite in-process and then `os.fork()`s per mutant, and a child that watches again after the parent has dies with SIGABRT, scored 🤔 — unknown, not killed. `tests/view/test_dev.py`'s reload-stream test is the one in the tree; keep it out of the mutant child (an env guard or a mutmut exclusion), then re-score `trace_store._connect`, where the 🤔 verdicts hide at least one killable mutant and one probable survivor.
