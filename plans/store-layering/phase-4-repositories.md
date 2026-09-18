# Phase 4: one repository per area, returning models

Replace the viewer's three query enums and `fetch` with typed methods on repositories built over the `Store` handle, each returning a model from `models/`. One enabling PR, then one PR per repository. Each PR leaves every page rendering the same bytes.

Back to [the overview](overview.md). Stacks on [phase 3](phase-3-sql-library.md). Revised 2026-09-17 against `origin/main` = `c8a942d` to answer the phase-4 design audit; every count and caller below was read that day — verify at the file before building on it.

## Problem

After phase 3, a page reads through `store.pages.page_rows(store, Page.SESSION_HEADER, **bindings)` and gets `dict[str, Any]` rows, then a page module picks fields out of the dict by name. The SQL has one home but no interface: nothing contracts what a statement returns against what a page reads, and testing a query means testing a page.

The 43 members of `Page` (21), `Fragment` (5) and `Value` (17) in `src/hyphae/store/pages.py` are the method list this phase writes (`awk` over the three `StrEnum` blocks, 2026-09-17). They do not partition by page: `view/detail.py:DETAILS` holds 16 of the 17 `Value` members in one tuple, node facts and enrichment lines side by side, all fetched by `pages/node/fragments.py:detailed` — so the two repositories that own them cannot be independent PRs until the registry stops naming queries. That is what PR 4.0 does.

## Call paths, current → proposed

```
current:  pages/sessions/read.py ─calls─ store.pages.sorted_sessions(store, sort, direction, size, filters, bindings, described=…) ─returns─ Listing ─picked into─ pages/sessions/models.py
          pages/node/fragments.py:59-74 ─calls─ page_rows(store, Fragment.NUMBERS, **bound(Fragment.NUMBERS, POPOVER_WIDTHS, …)) ─returns─ list[Row] ─picked by─ reads.node_numbers(row) ─into─ Numbers
          pages/node/fragments.py:detailed ─reads─ spec.whole: Value ─calls─ page_rows(store, spec.whole, **bound(spec.whole, HEADER_WIDTHS, **keys)) ─into─ Whole(row["value"], spec.name, citation)

after 4.0: pages/node/fragments.py:detailed ─calls─ spec.whole(store, keys) ─returns─ models.node.WholeValue | None    (spec.whole is a callable; 4.0 builds it from today's Value via detail.fetched)
proposed: pages/sessions/read.py ─calls─ SessionRepository(store).listing(sort, direction, size, filters, widths=…, described=…) ─returns─ models.listing.Listing ─mapped into─ page models
          pages/node/fragments.py ─calls─ NodeRepository(store).numbers(session_id, source, node_id, kind, widths=…) ─returns─ models.node.Numbers
          view/detail.py:DETAILS ─holds─ spec.whole = lambda store, keys: NodeRepository(store).value("call_text", keys, widths=…)   (4.6)
          view/enrichment.py:LINES ─holds─ spec.whole = lambda store, keys: EnrichmentRepository(store).line(Level.TURN, "description", keys)   (4.5)
```

The mapping step in a page's `read.py` (the node page's `reads.py`) stays: a page model adds hrefs, labels and cut marks no repository knows about. What leaves the page is the query name, the binding and the raw row.

## File-tree diff

```
src/hyphae/
  store/
    handle.py            ~ 4.0: a repositories block, one placeholder comment per area separated by blank lines; each PR replaces its own with a `cached_property`
    library.py           ~ 4.0: bind(name, widths, sizes, **keys) — the body of view/bounds.py:bound, keyed by statement name; ParamValue moves out to models/citation.py
    sessions.py          + 4.1 SessionRepository: SESSIONS, PROJECTS, PROJECT_ROLLUPS, DESCRIBED_SESSIONS, SESSION_HEADER; absorbs pages.py's sorted_sessions, SHOWN, SORTS
    records.py           + 4.2 RecordRepository: RECORDS
    offloads.py          + 4.2 OffloadRepository: OFFLOAD
    failures.py          + 4.3 FailureRepository: SESSION_ERRORS
    analysis.py          + 4.4 AnalysisRepository: a corpus statement by name with bindings, plus the three private relation statements analyze/runner.py runs today (runner.py:117-140)
    enrichment.py        ~ 4.5 EnrichmentStore takes a Store instead of a path (commit 1), absorbs view/enrichment.py's ENRICHMENT and enriched() reads and the six line Values TURN/RUN/SESSION_{DESCRIPTION,FRICTION}, then is renamed EnrichmentRepository (last commit)
    nodes.py             + 4.6 NodeRepository: RUN_HEADER, TURN_HEADER, CALL_HEADER, TOOL_HEADER and the ten node Values CALL_TEXT, CALL_THINKING, TOOL_INPUT, TOOL_RESULT, TOOL_COMMAND, TURN_PROMPT, TURN_COMMAND_ARGS, RUN_BRIEF, RUN_PROMPT, RUN_RESULT
                         ~ 4.7 adds TURN_CALLS, CALL_TOOLS, NUMBERS, TOOL_NUMBERS, COMPACTION_NUMBERS, TURN_RECORDS, RECORD, and the timeline/compactions methods kinds.py's logs read
    nav.py               + 4.8 NavRepository: NAV_TREE_TURNS, NAV_TREE_CALLS, NAV_TREE_TOOLS, RUNS; nav_tree.py's reads of TIMELINE, RUN_TIMELINE, COMPACTIONS move onto 4.7's methods and the members die here
    pages.py             ~ 4.0 regroups the enum members under one comment heading per repository; each PR deletes the members under its heading, leaves the heading, and deletes the helpers whose last caller it moved; phase 5 deletes the file
  models/
    citation.py          + 4.0 Citation(name, bindings) NamedTuple, and ParamValue beside it
    node.py              + 4.0 WholeValue; 4.6 headers; 4.7 Numbers, Logged rows
    listing.py           + 4.1 Listing, SessionFigures and the SessionRollup and SessionHeader over it, ProjectRollup, the filter and sort types
    record.py            + 4.2 Record, RecordSlice, Offload
    failure.py           + 4.3 Failure
    nav.py               + 4.8 NavRow, TimelineRow
  view/
    detail.py            ~ 4.0 Spec loses header, whole becomes a Fetch callable; DETAILS keeps the ten node specs; fetched(value) builds today's read as a Fetch
    enrichment.py        ~ 4.0 LINES: the six enrichment-line specs; Descriptions carries its own citation. 4.5: described/enriched call the repository
    citation.py          ~ 4.0 Ran = list[Citation]; cited(citation)
    bounds.py            ~ 4.0 bound becomes a shim over library.bind; deleted with the last Page member (4.8)
    pages/node/routes/details.py ~ 4.0 registers (*DETAILS, *LINES); no route name (nothing calls url_for — rg empty)
    pages/node/{browser,kinds,nav_tree,walk,fragments}.py, pages/errors/read.py, view/failures.py ~ 4.0 build Citation instead of (Page, bindings) pairs
    pages/*/read.py, pages/node/{reads,fragments,kinds,browser,nav_tree,levels}.py ~ per PR: call a repository; map to page models
docs/layering.md, src/hyphae/store/handle.py docstring ~ 4.0: hp enrich moves behind the handle in 4.5; hp export-otlp stays on the writers the store owns
CONTEXT.md               ~ 4.0: Detail spec, Widths; 4.5: Store handle
tests/store/test_library__bind.py + 4.0 the binding checklist, over the catalog
tests/store/test_catalog.py       + 4.0 totality: every view_ statement is named somewhere in the store package
tests/store/test_handle.py        + 4.0 the outside-callers ratchet; phase 5 pins it empty
tests/store/test_<repository>.py  + one per repository
```

The import graph does not change. `models` sits on the contract's bottom line (`pyproject.toml:279`) and `store/trace_store.py`, `trace_reader.py`, `enrichment.py` already import `hyphae.models.*`, so `store → models` needs no layers line and no forbidden-contract line changes (verified against `pyproject.toml` 2026-09-17). That bottom line is also why `Citation` lives in `models/citation.py` rather than `store/library.py`: `models/node.py:WholeValue` carries one, and `models` may not import `store`. `ParamValue` goes with it, since a citation's bindings are typed by it. Only the payload crossing `view → store` changes: models instead of rows.

## Key contracts

**A detail spec names its fetch, not its query.**

```python
Fetch = Callable[[Store, Mapping[str, str]], WholeValue | None]   # keys off the route; None when no row

class Spec(NamedTuple):
    name: str          # the column the header previews and the label the pane prints
    route: str         # the fetch route; its template names the keys
    whole: Fetch       # answers the value whole, with its citation
    written: Written

@dataclass(frozen=True)          # models/node.py
class WholeValue:
    value: str | None            # the value whole; None is the 404 "Nothing in this store is stored under that id."
    citation: Citation
    result_type: str | None = None   # only the named-file read declares it (syntax_of); None where the statement has no such column
```

A fetch builds `WholeValue(citation=…, **row)`, so a statement answering a column the model lacks raises. The enrichment-tables gate stays in `fragments.detailed` (`spec.written is Written.LINE and not enriched(store)`), so 4.5 changes `enriched`'s body without touching the node page. The callable-in-a-registry follows `kinds.py:KINDS`, whose rows already hold reader callables.

**A repository method selects exactly the fields of the model it returns.** Rows map to models by column name (`Model(**row)`); an extra column or a missing one raises at construction. Each repository test drives every method on the corpus store, so the row-to-model contract runs per method rather than per page.

**A repository method binds exactly the parameters its statement declares.** Signatures are keyword-only, one keyword per key; widths arrive as `widths: Mapping[str, int]` (a page passes `bounds.HEADER_WIDTHS._asdict()`), sizes likewise, and the method calls `library.bind(name, widths, sizes, **keys)`, which fills every width the statement declares off the mapping and refuses a key spelled as a width. DuckDB 1.5.5 refuses both a missing and an excess named parameter (probed 2026-09-17), so a drifted signature fails in the repository test before any page runs.

**Models derive, they do not copy.** Within `models/listing.py`: `SessionFigures` holds the twenty columns the list row and the header share, and `SessionRollup` and `SessionHeader` each add what its own surface prints. Not `SessionRollup(Session)`: `trace.Session` shares four of its eleven fields by name (`id` is `session_id` in the store, `active_ms` is nullable there), so deriving from it would need a `.sql` change, which no phase-4 PR makes. PR 4.1 settles dataclass-or-pydantic on this case (deferred PR 1.3, see Slices).

**Widths are bindings, not model fields.** `view/bounds.py` keeps declaring every surface's `Widths`; the footer still quotes what was bound.

**Every read carries its citation.** `models/citation.py:Citation(name, bindings)`; `Ran = list[Citation]`; `view/citation.py:cited(citation) -> Cited`. A repository method whose statement a footer cites returns the `Citation` beside its rows (`Listing.citation`, `WholeValue.citation`, `Descriptions.ran`), and the page appends what it was handed. No page names a query.

**The NavTree reads each level once.** `pages/node/nav_tree.py:Corpus` and `levels.py:Levels` stay in the viewer. 4.8 re-keys the memo on the repository method name and its bindings instead of the enum member; the `SESSION_HEADER` read leaves the memo in 4.1, when `Corpus` carries a `SessionHeader` model — `head: SessionHeader | None`, because `browser.opened()` builds a hollow corpus for an expansion and reads no header.

**A repository is a value over the handle: `SessionRepository(store)`.** A plain class holding a `Store`, reading through `store.rows` and building rows through `library.fetch`. Plain rather than a dataclass because mutmut 3.7 skips every decorated class, so a dataclass repository's methods would never be scored; frozen would buy nothing behind the handle's `cached_property` anyway. `Store` also exposes each as a `cached_property` (`store.sessions`), added by the PR that creates the repository. Phase 4 does not make `Store.connection` or `Store.rows` private: the last outside `rows` callers are `analyze/runner.py:117-140` (4.4) and `view/enrichment.py:104` (4.5), which are siblings, so no phase-4 PR can be the one that closes the door. Phase 5's deletion commit does it, with `tests/store/test_handle.py` pinning `{name for name in vars(Store) if not name.startswith("_")}` to the repository names and the 4.0 ratchet at `set()`. Until then the ratchet's `==` literal is 4.0's alone: 4.4 and 4.5 each prove their own module left it with a `not in` leaf in their own test file, so no two siblings edit one line.

## Chosen test seam

Three levels, all over real recorded sessions:

- **`tests/store/test_<repository>.py`** drives each method against the corpus store `tests/conftest.py` builds from `tests/fixtures/`: field values from sessions the fixture README names, a `Model(**row)` construction per method, the citation for one binding, a keyword left off and a keyword added (both raise). Run `mise run mutate 'hyphae.store.<name>.*'` before opening the PR.
- **Catalog-parametrized leaves that never go blind.** Today `tests/view/test_bounds__binding.py:MEMBERS = (*Page, *Fragment, *Value)` and `test_bounds.py:239-270` parametrize over the live enums, so they shrink silently as members leave. 4.0 reparametrizes all three over the catalog, `[name for name in library.names() if name.startswith(VIEW_PREFIX)]`, which no PR shrinks:
  - `tests/store/test_library__bind.py`: `SURFACES: dict[str, Widths]` keyed by statement name, pinned `set(SURFACES) == set(view names)`; each name binds exactly `library.parameters(name)`; the refusal leaves (surface short, key-as-width, key-as-size, planted `.sql`) move with it
  - `tests/view/test_bounds.py`: the fat-column scan over every catalog name minus a test-side `WHOLE` frozenset of the 17 per-value names, and the per-value scan over `WHOLE`; `set(WHOLE) <= catalog` pinned
  - `tests/store/test_catalog.py`: the set of `view_*` string literals in `src/hyphae/store/**/*.py` (AST scan; enum values are string constants too) `==` the catalog. A statement no module names, or a name no statement backs, fails here in every PR
- **The unchanged viewer tier** is the byte oracle: `tests/view/test_bounds__*.py` pins bytes at every setting, `tests/gallery` serves every scenario, `mise run e2e` runs on every PR touching the node page. `tests/view/conftest.py:122 reading` stays a raw connection: it plants rows, it reads nothing through the store.

Leaves that reach into `store.pages` move with their member: `tests/view/budgets.py` (`SHOWN`, `Page.SESSIONS`, `Page.DESCRIBED_SESSIONS`) and `tests/view/pages/query/test_query.py:142` in 4.1; `tests/view/test_bounds__lists.py:313` (`cursorless_rows(Store(store), Page.TIMELINE, …)`) in 4.8, onto `NavRepository`. The DETAILS-parametrized leaves (`tests/analyze/test_queries.py:362`, `tests/view/test_app.py:297`, `tests/view/pages/node/test_node__registry.py:74`) parametrize over `(*DETAILS, *LINES)` after 4.0; `test_queries.py`'s leaf loses its `spec.header` half (the registry test renders every spec's preview on a scenario page, which reads `row[spec.name]` and `row[f"{spec.name}_chars"]` — verify each spec has a scenario before deleting) and its whole half becomes `WholeValue(**row)` inside the fetch.

## Slices

PR 4.0 lands first; 4.1 second, alone. The rest fan out from `main` after 4.1: 4.2, 4.3, 4.4, 4.5 and the node stack 4.6 → 4.7 → 4.8 are siblings. Independence is a file claim: no two siblings touch the same file, except `store/pages.py` and `store/handle.py`, where each edits only its own group and leaves its heading standing — git rebases two edits cleanly only when an unchanged line stands between them, and in `pages.py` the heading is that line: a blank alone is not, because ruff folds two blanks in a class body into one, so the pre-commit hook pulls one into each deletion and two adjacent groups' deletions touch (probed 2026-09-18 in a scratch repo: adjacent blank-separated deletions conflict, adjacent heading-separated ones merge clean in either order). In `handle.py` a placeholder comment becomes a `cached_property` in place, so the blank lines around it stay unchanged. `tests/view/test_layout.py:STORE` enumerates the store modules a route may take URL words from, by exact name, so each sibling that gives its routes a repository module adds that module to the tuple — `cli.py`, where 4.4 edits `_query` and 4.5 edits `_enrich`, sixty lines apart — and `tests/analyze/test_queries.py`, which imports `analyze.manifest` (4.4's) and `view/enrichment.py:LINES` (4.5's): it is 4.4's file, and 4.5 leaves `LINES` a tuple of `Spec`s so the leaf parametrized over it needs no edit. The ratchet in `tests/store/test_handle.py` is not a fourth: 4.0 pins its set with `==` and no sibling edits that literal; 4.4 and 4.5 each add a `not in` leaf in their own repository test file, and phase 5 sets the literal to `set()`. Rendered bytes: **none** in any PR, except a `.sql` comment rewrite, which goes in its own commit and changes only that statement's Query page (the phase-3 precedent).

0. **PR 4.0, the detail registry names its fetch** (enabling refactor, one PR, commits in this order):
   1. `Citation` NamedTuple in `models/citation.py`, with `ParamValue`; `Ran = list[Citation]`; `cited(citation)`; every `(Page.X, binds)` pair in `browser.py`, `kinds.py`, `nav_tree.py`, `walk.py`, `view/failures.py`, `errors/read.py` becomes `Citation(Page.X.value, binds)`; `Descriptions.queried` becomes `ran: Ran`, which `browser.py` extends its own with. The enrichment citation keeps quoting keys alone, as the footer always has, though `described` binds widths too — a byte-changing fix for its own commit, not this PR
   2. `library.bind(name, widths, sizes, **keys)` takes `bounds.bound`'s body; `bound` becomes `bind(page.value, widths._asdict(), …)`; `test_bounds__binding.py` becomes `tests/store/test_library__bind.py` over the catalog; the fat-column scans go over the catalog; `tests/store/test_catalog.py`
   3. `Spec(name, route, whole: Fetch, written)`; `models/node.py:WholeValue`; `detail.fetched(value: Value) -> Fetch` (bind at `HEADER_WIDTHS`, `page_rows`, `WholeValue(citation=…, **rows[0])`); the six line specs move to `view/enrichment.py:LINES` with `fetched(Value.TURN_DESCRIPTION)` etc.; `routes/details.py` registers `(*DETAILS, *LINES)` without `name=` (nothing calls `url_for`, so no leaf can pin the drop; the render diff is the evidence); `fragments.detailed` calls `spec.whole(store, keys)`; the three DETAILS leaves parametrize over both; `test_queries.py:362` reshaped as above
   4. `handle.py` repositories block and `pages.py` regrouped by repository; `tests/store/test_handle.py` ratchet, an AST scan: every `Attribute` whose receiver spells `store` — the bare name or `self.store` — and whose attr is `rows` or `connection`, in any module outside `store/`, `== {"analyze/runner.py", "view/enrichment.py"}`. The receiver is keyed by name, not type, because a type-keyed scan misses `runner.py:117-118` (`store = opened.enter_context(open_store(...))`), and `levels.py:Levels.rows` is a decoy no `store.` receiver reaches; the spelling convention the scan leans on — every `Store` parameter and every opened handle outside the store is named `store` — gets its own leaf beside it
   5. Doc-sync: `docs/layering.md:13`, `handle.py:3,:32` docstring, `CONTEXT.md` Detail spec and Widths lines
   Files: the ones listed under 4.0 in the file-tree diff — all shared files are touched here and nowhere else until 4.1. Verify: `mise run check`; `tests/store/test_library__bind.py` and `test_catalog.py` each parametrize over 43 names; `mise run e2e`.
1. **PR 4.1, sessions and projects** — lands alone, because `SESSION_HEADER` is read by `errors/read.py`, `browser.py` (×5) and `kinds.py:_session_header`. Commit 1 is deferred PR 1.3: `models/listing.py` built as `pydantic.dataclasses.dataclass` unless the listing needs a BaseModel-only feature (phase 1's criterion), with `strict=True` so lax coercion cannot change a byte silently, and `work_cut: int | None` — the column is NULL for any listed session no pass reached, and a restyle with `int` reds at base; `WholeValue` restyled to match; `trace.py` and `items.py` stay as phase 1 left them. The fixture corpus cannot split lax from strict (no `Decimal`, `date` or int-for-float row exists), so the `HYPHAE_LIVE_STORE` leaf is the only evidence over real shapes: run it before the PR opens. Then `SessionRepository` with `listing`, `projects`, `rollups`, `header(session_id, widths=…) -> SessionHeader | None` — no `described`: nothing in production reads the description rows alone, and `listing(described=True)` carries them; `Corpus.head: SessionHeader | None`; `_session_header` reads `corpus.head`; `errors/read.py` keeps its 404 on `header(...) is None`; `sorted_sessions`, `SHOWN`, `SORTS`, `HEADINGS`' source move into the repository. Files: `store/sessions.py`, `store/library.py` (`core`, `fetch`), `models/listing.py`, `models/node.py`, `pages/sessions/{read,models,markup,routes}.py`, `pages/projects/read.py`, `pages/errors/read.py`, `pages/node/{browser,kinds,nav_tree}.py`, `view/bounds.py`, `view/builders.py`, `pages.py`, `handle.py`, `tests/view/budgets.py`, `tests/view/pages/query/test_query.py`, `tests/analyze/test_queries.py` (4.4's file; only the `store/pages.py:SHOWN` key it names moves). Rendered bytes: the comment lines of `store/queries/view_sessions.sql` and `view_described_sessions.sql` that named the viewer as the wrapper, in their own commit — three query pages change and nothing else. Verify: `tests/store/test_sessions.py`, whose rollups leaf binds `as_of=2026-07-28` because the render's window columns are all `None` at `utcnow()` over the July-2026 fixture; `pytest tests/view/test_sessions* tests/view/test_projects* tests/view/test_errors*` unchanged and green; the render is the oracle — the whole-store dump hashes rows and is blind to a model restyle, so it is 4.5's oracle, not this PR's.
2. **PR 4.2, records and offload.** `RecordRepository.page(...)` (RECORDS) and `OffloadRepository.chunk(...)` (OFFLOAD). Not `RECORD` or `TURN_RECORDS`: their only callers are the node page (`fragments.py:143`, `kinds.py:402`), so they are 4.7's. Files: `store/{records,offloads}.py`, `models/record.py`, `pages/{records,offload}/read.py`, `pages.py`, `handle.py`. Verify: `tests/store/test_records.py`, `test_offloads.py`; Records and Offload page tests unchanged.
3. **PR 4.3, failures.** `FailureRepository.failures(session_id) -> Failures` with its `ran`; `view/failures.py` keeps `stepped`. Files: `store/failures.py`, `models/failure.py`, `view/failures.py`, `pages/errors/read.py`, `pages.py`, `handle.py`. `browser.py` is untouched because `failures.failures(store, session_id)` keeps its signature. Verify: `tests/store/test_failures.py`; `tests/view/test_errors*` unchanged.
4. **PR 4.4, analysis.** `AnalysisRepository.run(name, bindings) -> Answered(columns, rows, citation)` and the three relation statements `runner.py` embeds; `hp query` and the Query page on it. Files: `store/analysis.py`, `analyze/{runner,manifest}.py`, `cli.py` (`_query` only), `handle.py`, `tests/analyze/test_queries.py`; not `pages/query/read.py`, which opens no store (it reads `library.names()`, `library.load` and `macros.needed_by`). Verify: `hp query` output byte-identical for every manifest statement over the fixture corpus (`tests/analyze`); a `"analyze/runner.py" not in reached()` leaf in `tests/store/test_analysis.py` (the ratchet literal stays 4.0's).
5. **PR 4.5, enrichment** — not a rename, three commits:
   1. Enabling refactor: `EnrichmentStore.__init__(self, store: Store)`; `prepare()` holds `check_shape` and the DDL (today's constructor tail, `enrichment.py:143-160`); `hp enrich` does `with open_store(args.db, read_only=False, wait=CLI_WAIT) as store: repo = EnrichmentStore(store); repo.prepare()`; a read-only handle skips `prepare` and a write on it fails loud in DuckDB; `tests/conftest.py` gains `enriching(path)` (open + prepare, as a context manager) and the 64 construction sites (`rg 'EnrichmentStore\(' src tests`) move to it, the four-pass and `hp query` harnesses included, or the oracle cannot run at head; `EnrichmentStore.connection` keeps delegating to the handle's public `connection`, so the 46 test lines in 7 files that execute SQL on it move nothing — phase 5 owns them, with `Store.connection`'s privacy (a second read-only open raises `ConnectionException` at once, so "open their own store" was never an option)
   2. The reads: `described`, `enriched` (as `held()`, on `duckdb_tables()`), and the six lines `line(level, field, keys)`; `view/enrichment.py:LINES` fetches call it; `view/enrichment.py` reduced to `Enrichment`/`Descriptions` presentation mapping; `items.py` restyled only if 4.1 chose pydantic
   3. Rename `EnrichmentStore → EnrichmentRepository`, `Store.enrichment`
   Files: `store/enrichment.py`, `view/enrichment.py`, `cli.py` (`_enrich` only), `enrich/*`, `tests/enrich/*`, `tests/conftest.py`, `tests/store/test_enrichment.py`, `tests/store/test_schema.py`, `pages.py`, `handle.py`. `cli.py` is shared with 4.4 by file but not by function; if that reads as a violation, land 4.4 first. Verify: `tests/enrich`, `tests/store/test_enrichment.py`, the enrichment scenarios in the gallery, the whole-store dump; a `"view/enrichment.py" not in reached()` leaf in `tests/store/test_enrichment.py`.
6. **PR 4.6, node headers and details** (first of the node stack). `NodeRepository.header(kind, keys, widths=…, sizes=…)` for the four headers, `value(name, keys, widths=…) -> WholeValue | None` for the ten node Values; `DETAILS` specs' `whole` become repository lambdas; `detail.fetched` shrinks to the lines' use, or dies here if 4.5 landed first (the 4.7 line states the rule). `paged` has two callers (`records/read.py:29`, `browser.py:80`), so it stays in `pages.py` until 4.8. Files: `store/nodes.py`, `models/node.py`, `view/detail.py`, `pages/node/{kinds,reads,browser}.py` (`keyed` and the four `_x_details` readers), `pages.py`, `handle.py`. Count `Turn`'s fields the header shows before deriving `TurnHeader` from `Turn` or standing it alone. Verify: `tests/store/test_nodes.py`; the node page's header and detail tests; `mise run e2e`.
7. **PR 4.7, node children and numbers** (on 4.6). `children(...)` for TURN_CALLS and CALL_TOOLS, `timeline`/`run_timeline`/`compactions` as paged methods over `store/paging.py` (today's `window`, `cursorless_rows`, `TURN_CURSOR`, `listed`, `dropped` moved; `paged` follows in 4.8), `numbers`, `tool_numbers`, `compaction_numbers`, `turn_records` (TURN_RECORDS), `record(session_id, source, line_no)` (RECORD); `detail.fetched` is not 4.7's to delete: DETAILS leave it in 4.6 and LINES in 4.5, and the PR at whose head the live-caller scan reads zero deletes it — 4.6, or 4.5's rebase, whichever lands second. Each owner's tuple gets a leaf that no `spec.whole.__qualname__` starts with `fetched.`, which is what makes the rule checkable. `kinds.py`'s logs switch; `nav_tree.py` keeps reading `Page.TIMELINE`/`RUN_TIMELINE`/`COMPACTIONS` through the memo until 4.8, so those three members stay. Files: `store/nodes.py`, `store/paging.py`, `models/node.py`, `pages/node/{kinds,reads,fragments}.py`, `pages.py`. Verify: `tests/store/test_nodes.py`; `tests/view/test_bounds__node.py`; `mise run e2e`.
8. **PR 4.8, the NavTree and the walk** (on 4.7). `NavRepository.level(...)` for the three NAV_TREE reads, `runs(session_id, widths=…)` (RUNS); `nav_tree.py`, `walk.py`, `levels.py` (memo re-keyed on method name and bindings) and `browser.py` on it; the last `Page` members die, `bounds.bound` and the rest of `pages.py`'s helpers with them; `test_bounds__lists.py:313` onto the repository. Files: `store/nav.py`, `models/nav.py`, `pages/node/{nav_tree,walk,levels,browser}.py`, `view/bounds.py`, `pages.py`, `handle.py`, `tests/view/test_bounds__lists.py`. Verify: `tests/store/test_nav.py`; NavTree scenarios, walk tests, `mise run e2e`; `rg 'Page\.|Fragment\.|Value\.' src tests` empty, `pages.py` left holding only what phase 5 deletes.

## Decisions

- **An enabling PR over one big PR or a declared 4.5/4.6 stack.** The registry's coupling is a design flaw (a declaration naming its query), and the overview prefers enabling refactors; a stack would leave the flaw and order two unrelated repositories. Rejected: one PR for enrichment and node details — the two smallest reviewable units glued by a tuple.
- **`Spec.whole` is a callable, `Spec.header` is gone.** A registry row that names a query has to name a repository once the enum goes; a callable lets each owner supply its own without the registry importing either repository. `header` had one reader (`tests/analyze/test_queries.py:381`), whose obligation the registry render already carries. Rejected: `whole: str` naming a catalog statement — pins the registry to the library, which is what 4.0 exists to cut.
- **The six enrichment lines live in `view/enrichment.py:LINES`, not in `DETAILS`.** The routes register both; each owner edits its own module. Rejected: one tuple with an `owner` field — same file, two PRs.
- **Repositories are values over the handle, and also `Store` properties.** `SessionRepository(store)` is buildable in a test with no property; the property is the page's spelling. Rejected: properties only — phase 5 has to move construction inside `Store` to privatize `rows`, and a value type makes that a one-line change.
- **`Store.connection` privacy goes to phase 5, with a ratchet now.** The last two outside `rows` callers are siblings; the ratchet in 4.0 stops a new one. Rejected: ordering 4.4 before 4.5 so 4.5 closes the door — buys a stack for one deletion phase 5 makes anyway. Phase 5's document needs the bullet (Open questions).
- **`RECORD` and `TURN_RECORDS` are node reads.** Their only callers are node modules; a `RecordRepository.one` nothing on the records page calls would be a method with no caller in its own page. Rejected: keeping them on `RecordRepository` and having 4.7 edit `store/records.py` — a sibling editing another sibling's file.
- **`SESSION_HEADER` is a session read, and 4.1 lands alone.** Its three callers span two sibling groups; one ordered PR beats two shared files. Rejected: `NodeRepository.header(Kind.SESSION)` in 4.6 — leaves `errors/read.py` and 4.3 waiting on the node stack.
- **The node page is a stack of three.** `kinds.py` and `nav_tree.py` read the same timeline and compaction statements, and the memo keys on the member; no file split makes 4.6–4.8 independent without moving code for the sake of a diff. Rejected: one node PR — 22 members across five modules; and re-splitting the node package in 4.0 to make siblings — churn a reviewer would have to read as refactor.
- **The binding checklist reparametrizes over the catalog in 4.0, not per slice.** A leaf whose population is the library cannot shrink when an enum does. Rejected: each repository test re-deriving "declared == bound" — eight copies of one leaf, and blind between PRs.
- **`bound` moves into the store as `library.bind`.** Binding widths to a statement's declared parameters is a fact about the statement; with the enum gone the page has nothing to hand `bound` but a name. Rejected: repositories taking one keyword per width — `HEADER_WIDTHS` has more fields than any one statement declares, so every call would spell the subset.
- **PR 1.3 (pydantic) lands as 4.1's first commit.** 4.1 is the first row-built variant with real width — dates, ints, a derived rollup; phase 1 deferred to exactly this PR. Rejected: deciding it in 4.0 on `WholeValue`, one nullable string.
- **`EnrichmentStore` takes a handle, and the rename is 4.5's last commit.** The constructor opened a writable, 10-second-wait connection; a page's handle is read-only at 1 second, so folding the two means splitting open from prepare. Rejected: the rename in phase 5 under "renames last" — phase 5's list is the export pair, and a phase-4 PR that leaves the store's one repository misnamed leaves phase 4 unfinished.
- **`hp export-otlp` stays on the writers the store owns; 4.0 corrects `docs/layering.md:13`.** Nothing in `view` or `analyze` reads the delivery ledger, and the page-side privacy phase 5 wants does not need it. Rejected: a 4.9 `Store.delivery` — a repository with one caller (`cli.py:420`) and no page.
- **Result models in `models/`, page models in the viewer, `AnalysisRepository` by name** — unchanged from the 2026-09-16 draft: one home for cross-package types; no href in a result model; 29 corpus statements do not want 29 signatures.

## Out of scope

- Making `Store.connection` or `Store.rows` private: phase 5's deletion commit, on the ratchet 4.0 lands.
- `hp export-otlp` behind the handle: it hands a raw connection from `cli.py:420` to `DeliveryLedger` and `StoreSource`, and stays so.
- The trace writer: takes a `SessionTrace`, stays as phase 2 left it.
- Restyling `models/trace.py` and `models/items.py` to whatever 4.1 picks: `items.py` follows in 4.5 only if the pick is pydantic; `trace.py` is the extractors' and not built from rows.
- Caching across requests; changing what a page renders. A page found reading a column no statement returns gets its own PR first.
- Deleting `store/pages.py` and the `Page`/`Fragment`/`Value` names from tests and docs: phase 5. `detail.fetched` goes earlier, under the live-caller rule in 4.7's line.

## Open questions

- **Phase 5's document** (`plans/store-layering/phase-5-closeout.md`) needs two bullets this design assumes: the deletion commit makes `Store.rows` and `Store.connection` private by building repositories inside the handle, pinned by `tests/store/test_handle.py` (public names == repository names; the 4.0 ratchet == empty); and `bounds.bound` is already gone by then (4.8). Nathaniel decides whether to amend now or let the phase-5 implementer fold it in.
- **`TokenUsage` and `CostSplit`** (`pricing.py`) ride to the viewer through `Numbers`. Whether they move to `models/` with `Numbers` in 4.7 is decided by `rg 'TokenUsage|CostSplit' src/hyphae/extract`: used at write time, they stay in `pricing.py` and `Numbers` imports them; otherwise they move. The 4.7 implementer runs the grep.
