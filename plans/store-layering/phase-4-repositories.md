# Phase 4: one repository per area, returning models

Replace the viewer's three query enums and `fetch` with typed methods on repositories on the `Store` handle, each returning a model from `models/`. One PR per repository. Once phase 3 lands, the PRs are independent siblings that can run in parallel worktrees. Each PR leaves every page rendering the same bytes.

Back to [the overview](overview.md). Stacks on [phase 3](phase-3-sql-library.md).

## Problem

After phase 3, a page reads through `store.pages.fetch(store, Page.SESSION_HEADER, bindings)` and gets `dict[str, Any]` rows, then `reads.py` picks fields out of the dict by name. The SQL has one home but no interface: nothing contracts what a statement returns against what a page reads, and testing a query requires testing a page. The 37 enum members form the method list this phase writes, grouped by the area they read.

## Call paths, current → proposed

```
current:  pages/sessions/read.py ─calls─ store.pages.sorted_sessions(store, …) ─returns─ list[Row] ─picked into─ pages/sessions/models.py
          pages/node/reads.py ─calls─ fetch(store, Page.NUMBERS, …) ─returns─ Row ─picked into─ Numbers

proposed: pages/sessions/read.py ─calls─ store.sessions.listing(filter, sort, window) ─returns─ list[models.listing.SessionRollup] ─mapped into─ page models
          pages/node/reads.py ─calls─ store.nodes.numbers(ref) ─returns─ models.node.Numbers
```

The mapping step in `read.py` stays: a page model adds hrefs, labels, and cut marks that no repository knows about.

## File-tree diff

```
src/hyphae/
  store/
    handle.py            ~ Store gains one attribute per repository, built lazily over the connection
    sessions.py          + SessionRepository: SESSIONS, PROJECTS, PROJECT_ROLLUPS, SESSION_HEADER, DESCRIBED_SESSIONS
    nodes.py             + NodeRepository: RUN_HEADER, TURN_HEADER, CALL_HEADER, TOOL_HEADER, NUMBERS, TOOL_NUMBERS, COMPACTION_NUMBERS, TURN_CALLS, CALL_TOOLS, RUNS, COMPACTIONS, and every Value: CALL_TEXT … RUN_RESULT
    nav.py               + NavRepository: NAV_TREE_TURNS, NAV_TREE_CALLS, NAV_TREE_TOOLS, TIMELINE, RUN_TIMELINE
    failures.py          + FailureRepository: SESSION_ERRORS
    records.py           + RecordRepository: RECORDS, TURN_RECORDS, RECORD
    offloads.py          + OffloadRepository: OFFLOAD
    enrichment.py        ~ EnrichmentStore becomes EnrichmentRepository and absorbs view/enrichment.py's two reads: ENRICHMENT and `enriched()`
    analysis.py          + AnalysisRepository: run a corpus statement by name with bindings, returning rows and the citation; what `hp query` and the Query page need
    pages.py             ~ shrinks as each PR deletes the members it replaced; phase 5 deletes the file
  models/
    listing.py           + SessionRollup(Session), ProjectRollup, and the listing filter and sort types
    node.py              + the headers, Numbers, Logged rows, Detail values
    nav.py               + NavRow, TimelineRow
    failure.py           + Failure
    record.py            + Record, RecordSlice
  view/
    pages/*/read.py      ~ call a repository; map to page models
    enrichment.py, failures.py ~ deleted or reduced to presentation mapping
tests/store/test_<repository>.py   + one per repository
```

The import graph does not change in this phase. Only the payload crossing the `view → store` edge changes: models instead of rows.

## Key contracts

**A repository method selects exactly the fields of the model it returns.** Rows map to models by column name (`Model(**row)`). A test in each repository asserts that every method's SQL column names match the model's field names, binding the query and model into a single contract. If a page needs a column, add it to the model; if no page reads a field, remove it from the SQL.

**Models derive, they do not copy.** `Session` is the entity `extract` builds. `SessionRollup(Session)` adds what `live_session_rollups` computes: counts, tokens, and cost. A listing that needs less than the entity derives the other way, from a base the entity also extends. Whether the base is a dataclass or a pydantic model is phase 1's open decision; PR 4.1 settles it on a real case.

**Widths are bindings, not model fields.** A shaped read cutting a value at a surface width takes the width as a parameter, as `SHOWN` does today; `bounds.py` in the viewer keeps deciding it. The footer still quotes what was bound.

**The NavTree reads each level once.** `view/pages/node/nav_tree.py:51 Corpus` memoizes levels so the walk asks nothing the NavTree already asked. `NavRepository.level(ref)` returns one level. The memo stays in the viewer, keyed the same way, because it is a per-request cache of what one page asked, not a property of the store.

**Store exposes repositories as cached properties.**

```python
class Store:
    @cached_property
    def sessions(self) -> SessionRepository: ...
    @cached_property
    def nodes(self) -> NodeRepository: ...
    # nav, failures, records, offloads, enrichment, analysis
```

**Cited methods return citations beside their rows.** If a footer cites a query, the repository method returns the citation alongside the rows. The repository calls `citation(name, bindings)`, not the page.

## Chosen test seam

Two levels, both over real recorded sessions:

- **`tests/store/test_<repository>.py`** drives each method against the corpus store that `tests/conftest.py` builds from `tests/fixtures/`. It asserts the returned model: field values from sessions named in the fixture README, the column-equals-field check, and the citation for one binding. This is where a query gets tested as a query for the first time.
- **The unchanged viewer tier** is the oracle that a PR moved reads without changing pages: `tests/view/test_bounds__*.py` pins bytes at every setting, `tests/gallery` serves every scenario, and `mise run e2e` runs on every PR touching the node page.

Run `mise run mutate 'hyphae.store.<name>.*'` on each new repository before opening its PR. A shaped read has branches a green page test does not reach.

## Slices

PR 4.1 lands first and serves as the template; the rest fan out from `main` after it.

1. **PR 4.1, sessions and projects.** `SessionRepository`, `models/listing.py`, and the projects and sessions pages on it. These are the smallest pages, and the only ones with sorting, filtering, and windowing, setting the pattern for parameters. Decides dataclass or pydantic. Verify: `tests/store/test_sessions.py`; `pytest tests/view/test_sessions* tests/view/test_projects*` unchanged and green.
2. **PR 4.2, records and offload.** Two repositories, two pages, one PR because both are slices of a single column. Verify: Records and Offload page tests pass unchanged.
3. **PR 4.3, failures.** `FailureRepository`, the errors page, and the error stepper on it; `view/failures.py` keeps `stepped`, which handles navigation. Verify: `tests/view/test_errors*` unchanged and green.
4. **PR 4.4, analysis.** `AnalysisRepository` under `analyze/runner.py` and the Query page. `hp query` output must be byte-identical for every manifest statement over the fixture corpus; `tests/analyze` is the oracle.
5. **PR 4.5, enrichment.** `EnrichmentStore` renamed to `EnrichmentRepository`; the enricher and the viewer's two enrichment reads on it; `view/enrichment.py` reduced to presentation mapping. Verify: `tests/enrich` and the enrichment scenarios in the gallery.
6. **PR 4.6, node headers and details.** `NodeRepository` for the four headers and every `Value`. Verify: the node page's detail and header tests; `mise run e2e`.
7. **PR 4.7, node children and numbers.** The child logs, `NUMBERS` and its two siblings, `RUNS`, and `COMPACTIONS`. Verify: `tests/view/test_bounds__node.py`; `mise run e2e`.
8. **PR 4.8, the NavTree and the walk.** `NavRepository` and the timelines; `Corpus` reads through it. The largest and last. Verify: NavTree scenarios, walk tests, `mise run e2e`.

## Decisions

- **Repositories by area, not one class.** Eight areas with 37 reads and the enrichment writes; one class would be the shallowest module in the repo. The split follows the pages because that is how the reads are used and tested.
- **Result models in `models/`, not beside the repository.** Decided 2026-09-16: one home for every type that crosses a package boundary. The cost is that `models/` grows to about six modules; the guard is the derive-don't-copy rule.
- **The viewer keeps page models.** A result model has no href, no label, and no cut mark. Alternative rejected: returning page models from the store, which points the import edge the wrong way.
- **`AnalysisRepository` runs statements by name.** `hp query` runs statements by name, and the manifest holds production defaults. Wrapping 29 corpus statements in 29 methods would give each a signature no caller uses. The named form is the interface for statements a person runs; the typed form is the interface for reads a page makes.
- **PR 4.1 decides pydantic.** With one repository, one model family, and one row-to-model call site in hand, the decision has a concrete case instead of an abstract preference.

## Out of scope

- Any write path except enrichment. The trace writer takes a `SessionTrace` and stays as phase 2 left it.
- Caching across requests. `Store` is per-request; the memo is per-page.
- Changing what a page renders. A PR that finds a page reading a column no statement returns must fix it in a separate PR first.

## Open questions

- `TokenUsage` and `CostSplit` live in `pricing.py` and are returned to the viewer through `Numbers`. Whether they move to `models/` when `Numbers` does depends on whether `extract` uses them at write time; check `extract/parse.py:20`.
- How far derivation goes. `SessionRollup(Session)` is clear. Whether `TurnHeader` derives from `Turn` or stands alone depends on how many of `Turn`'s fields the header shows; count them in PR 4.6 before choosing.
