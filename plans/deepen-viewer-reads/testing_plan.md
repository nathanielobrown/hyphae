# Testing plan: deepen each viewer page behind composed dependencies

What the tests must show for `plans/deepen-viewer-reads/design.md`: that every full document moves
behind a parameter → read → markup dependency chain while every URL answers the same status, the
same bytes and the same citation, and that the new seam is held by the source-tree contract rather
than by review.

The seam is settled by the decision record (`deepen_viewer_reads_questions.md`, Q2): **the URL
served by `build_app`**. No leaf below calls a dependency, a page model or a read function
directly. Nothing is mocked. The evidence is the recorded fixture corpus opened through
`tests/view/conftest.py` (`client`, `store`, `enriched_client`, `corpus_pages`), the scenario list
`tests/view/scenarios.py`, and the source scan in `tests/view/test_layout.py`. Invented data is
flagged on the leaves that use it: every `plant`/`enriched_plant` store, whose fat strings and
model-written fields no recorded session carries.

Every leaf names an existing test unless it says **new**. Forty of the forty-eight are existing
leaves that must stay green with no edit; an edit needed there is a finding.

## Ordering: this lands on four view siblings

Plan against the tree after `plans/sql-self-manifest/`, `plans/detail-registry/`,
`plans/width-profiles/` and `plans/node-kind-table/`. Each design claim below was checked at the
file on `main` on 2026-09-05; treat them as hypotheses to re-run.

**Void as written in the design:**

- **`routes/enrichment.py` in the proposed node tree does not exist.** detail-registry deletes it
  and registers the six enrichment lines and ten detail fetches from `view/detail.py:DETAILS`
  through one `fetch(spec)` closure. Slice 5's "for details and enrichment lines, keep one
  dependency when a second typed seam would only carry one value" is **already discharged** — what
  remains for this change is moving `fetched(...)` out of `routes/details.py`
- **Slice 4's "remove the callback-shaped `Reader` interface and any route-owned raw row
  mapping".** node-kind-table deletes `Reader`, `Seen`, `TITLED` and `described_node` in its own
  slice 3. Nothing is left to remove
- **"The eight URLs remain FastAPI adapters" and "migrate the other node kinds one at a time".**
  Five route templates remain (`/session/{id}`, `.../run/{run_id}`,
  `.../thread/{source}/{kind}/{node_id}`, `.../thread/{source}/unattributed`, `.../unattached`),
  and per-kind variation lives in `pages/node/kinds.py:KINDS`. Slice 4 is one move of `browse`,
  not eight
- **The proposed node package shape omits `kinds.py`.** It is where the header, log, details,
  trail and title cells live after node-kind-table; the design's `reads.py` ("row-to-node, facts,
  children-log mapping") and `browser.py` must be drawn around it, not over it
- **`src/hyphae/view/manifest.py` does not exist.** The query page's read owns
  `analyze.manifest.names()` / `catalog()` and `queries.load(name)`, not `manifest.QUERIES`
  (`pages/query/routes.py:29` today)
- **Half of slice 6's grep is already answered.** width-profiles moves every width off
  `analyze.queries` onto `store.bound(page, bounds.<SURFACE>, **keys)` and deletes
  `store.header_bound` and `DESCRIBED_BOUND`, which the errors and sessions routes call today.
  What slice 6 still finds is `open_store`, `page_rows`, `Page.`, `Row` and `ParamValue`

**Verified as stated:** `deps.py`'s `Db` window docstring and `checked`; `KnobsDep` in
`routes/knobs.py`; `page: int = 1` on all eight node page routes; `test_layout.py:281`
(`test_a_models_module_appears_only_where_a_second_markup_module_reads_it`) asserting **zero**
`models.py` today; `tests/view/conftest.py:render_pages`; `plans/view-layout/improvements.md`.

## The obligations

### 1. Byte identity — the working-tree capture

The design's own proof: nothing rendered changes. This is a working-tree check by the implementer
at each slice, not a committed leaf; sections 3–8 are what hold the same bytes in `check`.

- **Every page and fragment the viewer exposes serves the same bytes before and after each
  slice.** *Evidence:* a capture over `tests/view/scenarios.py:SCENARIOS` — 40 URLs, one per
  route, held equal to the app's declared route set by `tests/view/test_bounds.py:540` and
  `tests/view/test_dev.py:215` — plus `render_pages(corpus_db)` for the node sweep; both to
  scratch under the OS temp directory, diffed to empty after slices 1–5
- **`render_pages` alone cannot prove slices 2, 3 and 5.** `conftest.pages` emits `/` and node
  pages only — no `/sessions`, no errors, records, offload or query page, no fragment. See
  *Unreachable* below; `SCENARIOS` is the capture basis that reaches them

### 2. The new seam holds — source scan, `tests/view/test_layout.py`

The architecture contract, and the only test surface the design allows besides the URL. Slice 1
rewrites the model rule; the rest land as each page moves.

- **A `models.py` is read by its page's read module and its markup, and by no sibling page.**
  Replaces the current zero-model assertion, which reds the moment slice 1 lands — by design.
  *Evidence:* `test_layout.py:281`, rewritten: for every `models.py`, the page's read module and
  at least one markup module of the same page import it, and
  `test_no_page_package_imports_a_sibling_page` (`:309`) already forbids the third reader
- **A page model is neutral.** *Evidence:* **new** leaf beside it — no `models.py` names
  `fastapi`, `starlette`, `htpy`, `duckdb`, or `store.Row`, read through the existing `named()`
  and `imports()` helpers
- **A read module reaches no web framework and writes no markup.** *Evidence:*
  `test_layout.py:225:test_only_a_pages_routes_module_reaches_a_web_framework` and
  `:256:test_only_a_markup_module_imports_htpy` — both already cover a new `read.py`, because they
  scan everything that is not `routes` and everything that is not `markup`. **No edit expected**
- **The seam points one way: markup does not import its page's read module.** A markup module that
  reached back for a row would erase the seam this design exists for. *Evidence:* **new** leaf —
  no markup module of a page imports that page's `read`/`reads`/`browser` module
- **No routes module of a page names the store's vocabulary.** The deletion test as a committed
  leaf: `open_store`, `page_rows`, `Page.`, `Row`, `ParamValue`. `Db` stays where a fragment's lock
  window is deliberate, but the query member, the bindings and the raw row go behind the read.
  *Evidence:* **new** leaf, modelled on width-profiles' "no width off `analyze.queries` outside
  `bounds.py`". **Consequence to accept before writing it:** `routes/details.py:fetched` and the
  popovers' `page_rows` call must move into a read module, or the leaf carries an exception list
  that will rot
- **No module of a page is named for nothing, and each page holds one routes kind and one markup
  kind.** `read.py` and `models.py` are new module names in a package these rules scan.
  *Evidence:* `test_layout.py:268` and `:244`, unchanged
- **Imports still point down or sideways.** *Evidence:* `test_layout.py:330` and `:348`,
  unchanged

### 3. The Store window — how long a request holds the file

The design's hardest rule and the one the URL sees least of.

- **A full document opens the store once and closes it before markup runs.** *Evidence:* see
  *Unreachable* — no URL response distinguishes one open from two. Discharged by a URL-driven
  probe that counts entries to `view.store.open_store` across one request to each full document
  and asserts one, plus the `Db`-free routes scan in §2
- **A page waits out a short writer and a locked store answers 503, on both a page and a
  fragment.** The two reach the store differently on purpose, which is the window rule made
  visible. *Evidence:* `tests/view/test_lifecycle.py:54` and `:72`, parametrized over `REACHES`
  (`/` and `/fragment/numbers/...`) — **existing, unchanged**
- **A store replaced under the viewer is caught per request, on both.** A read dependency that
  cached a connection across requests would red here. *Evidence:* `test_lifecycle.py:98`
- **A component that raises mid-page answers 500 and sends nothing.** The markup dependency must
  not become a place where a half-page escapes: `Viewer.html` still renders whole before the
  response exists. *Evidence:* `test_lifecycle.py:155`
- **Serving the store leaves it read-only.** *Evidence:* `tests/view/test_app.py:406`

### 4. URL parameters — every default, ceiling and refusal survives

Slices 2 and 3 rebuild the parameter graph. Q3's answer is "share wherever it makes sense", so what
the tests must pin is the *meanings that differ*.

- **A page number below one is refused on a node children log and on the session list, in each
  page's own words.** The two shared-validator candidates the design names. Their messages differ
  today — "Ask for a children log page from one upwards." (`browse.py:135`) and "Ask for page 1 or
  later, at a size between 1 and {ceiling}." (`sessions/routes.py:139`) — and the design says to
  preserve every useful refusal message. *Evidence:*
  `tests/view/pages/node/test_node__logs.py:142` (`?page=0` → 400) and
  `tests/view/test_app__list.py:458:test_a_page_outside_the_bounds_is_refused`, **each extended
  to assert its message text**, which no test pins today
- **Every bounded size keeps its own default and ceiling.** Five `Bound`s, five ceilings.
  *Evidence:* `test_app__list.py:458` (list), `tests/view/pages/records/test_records.py:378`,
  `tests/view/pages/offload/test_offload.py:193`, `tests/view/pages/node/test_nav_tree.py:583`
  (the four knobs) — existing, unchanged
- **An offload offset below zero is refused.** The one page-specific cursor rule with a 400 and no
  test: `offload/routes.py:40`. A shared positive-page check would swallow it. *Evidence:*
  **new** assertion in `test_offload.py`, beside `:193`
- **A records cursor past the end of a thread is a 404, not an empty page.** The other
  page-specific cursor. *Evidence:*
  `test_records.py:367:test_a_record_the_store_does_not_hold_is_a_404` and `:55`
- **An unknown query key on the session list is a 400, and every key filled in is a narrowing.**
  The parameter dependency inherits `narrowing`'s closed key set; FastAPI ignores what it was not
  declared with, so a key check lost here reads as an answer. *Evidence:*
  `tests/view/test_app__filters.py:112` and `:125`
- **An unparseable typed filter is a 400 naming the type.** *Evidence:* the second half of
  `test_app__filters.py:112`, over `TEXT`, `INTEGER` and `DATE`
- **A filter value reaches DuckDB only as a binding.** The parameter model carries checked values;
  nothing composed into SQL. *Evidence:* `test_app__filters.py:87`
- **An unknown sort or direction is a 400.** *Evidence:* `test_app__list.py:349`
- **`?nav=` outside the three presets is a 400 on every node page.** `KnobsDep` stays.
  *Evidence:* `tests/view/pages/node/test_nav_tree__presets.py:312`
- **A `{kind}` a node URL cannot carry, and a key the store does not hold, are 404s.**
  *Evidence:* `tests/view/pages/node/test_node.py:132` plus the two `{kind}` leaves the
  node-kind-table plan adds — inherited, unchanged

### 5. Citations — the evidence moves with the read

A page model carries the citations for the queries that produced it, built from the same mapping
the query bound. This is where a refactor of the read most easily lies.

- **Every page runs at the production sizes and cites the bindings it ran.** The strongest
  citation net in the tier: one assertion per page over the cited bindings, which after
  width-profiles reads the surface profiles. *Evidence:*
  `tests/view/test_bounds.py:283:test_the_pages_run_at_the_production_sizes`
- **A node page cites every query it ran.** *Evidence:* `tests/view/test_app.py:50`
- **The list cites its query and what was composed around it** — the sort and direction that bind
  nothing, stated beside the bindings that do. *Evidence:* `test_app__list.py:361` and
  `test_app__filters.py:145` (a filter rides the links and the citation)
- **The session list cites the enrichment query only when it joined one.** The design's named
  conditional-evidence case. *Evidence:* `tests/view/test_enrichment.py:91` and `:270`
  (`test_a_store_no_enrichment_pass_has_touched_renders_every_page`) — the second over a store
  with no enrichment tables, which is what makes the absence bounded
- **The errors page cites the failures query and never the session-header probe it did not run.**
  The other named conditional case: the header is read only when there is a 404 to word.
  *Evidence:* `tests/view/pages/errors/test_errors.py:170`, **extended** to assert that a session
  *with* failures cites the failures query alone — the current leaf checks the queries behind the
  page and the stepper, not the absence of the probe
- **The projects page cites its query and the window it ran.** *Evidence:*
  `tests/view/pages/projects/test_projects.py:284`
- **The records and offload pages cite the cursor and offset they served at.** *Evidence:*
  `test_records.py:93:test_a_citation_tuple_maps_to_a_working_url` and the citation assertion in
  `test_offload.py:26`
- **Every citation a page carries links to a query page that serves it, with its bindings quoted.**
  The query page's read is the other end of every citation above. *Evidence:*
  `tests/view/pages/query/test_query.py:74`, `:100`, `:118`, and `:210`
  (`test_only_a_name_the_library_declares_is_served`)
- **A fragment cites the query that fetched it.** *Evidence:* `test_app.py:295`

### 6. What each page shows — the per-page regression nets

These sweep the fixture corpus and should need **no edit**. They are why the refactor can move a
read without re-deriving what the page means.

- **The landing page prints a row per project, its windows, its order and its cut.** Slice 1's
  net. *Evidence:* `test_projects.py:91`, `:149`, `:167`, `:214`, `:297`, `:344`
- **The list holds every session with its own numbers, pages without repeating, and reads the
  clock at render.** Slice 2's net. *Evidence:* `test_app__list.py:61`, `:378`, `:420`, `:125`
- **A filter narrows the list to exactly the sessions the store says it should.** *Evidence:*
  `test_app__filters.py:50` and `:62`
- **The errors page lists every failure of the session in order, and a session with none has no
  errors page.** The absent-session / no-failures distinction the design calls out. *Evidence:*
  `test_errors.py:62` and `:91`
- **The records browser pages by line number without repeating or skipping, and opens the one
  record a citation named.** *Evidence:* `test_records.py:55`, `:133`, `:258`
- **An offloaded result is served in chunks that reassemble it, under a name that survives
  escaping.** *Evidence:* `test_offload.py:26`, `:151`, `:177`
- **Every kind of node serves a page that says what it is, and every kind renders a body and every
  shape a log.** Slice 4's net, over all eight kinds and the whole rendered corpus. *Evidence:*
  `test_node.py:84` and `:585`
- **A log row expands to the body its own page wraps, fact for fact, over both a bare and an
  enriched store.** Slice 5's strongest leaf, and the one the byte capture reaches only through
  `SCENARIOS`. *Evidence:* `test_node.py:236`
- **The same node URL serves the same bytes cold and warm.** A read dependency FastAPI caches
  within one request must not carry anything across two. *Evidence:* `test_node.py:408`
- **Walk, crumbs and the error stepper still step the node's own level.** *Evidence:*
  `tests/view/pages/node/test_walk.py`, `test_node.py:439`, `test_errors.py:106`
- **A popover prints the charges and the breakout of the node it hangs off.** Slice 5's other
  fragment. *Evidence:* `tests/view/pages/node/test_numbers.py`, `test_numbers__spend.py`,
  `test_numbers__compaction.py` — reading the field names width-profiles' slice 5 sets
- **Every value a pane previews is fetchable whole from its own URL, and a fragment naming nothing
  is a 404.** *Evidence:* `test_app.py:262`, `:355`, and the `DETAILS` loop detail-registry leaves
  in `tests/view/pages/node/test_node__details.py`

### 7. Budgets and bounds — the ceilings that must not move

- **Every page and fragment stays under the ceiling it is priced at, and the exact pins hold.**
  Planted stores: invented fat strings, labelled as such in the files, because no recorded session
  holds a value at every ceiling at once. *Evidence:*
  `tests/view/test_bounds.py:369`, `:516`, `:555`, `tests/view/test_bounds__node.py`,
  `tests/view/test_bounds__lists.py:49`, `:176`, `:235`, plus one `HYPHAE_PIN_EXACT=1` run per
  slice
- **Every route the viewer exposes is in the payload sweep, and `SCENARIOS` is the route set.**
  This change adds and removes no route, so the equality is also the proof that the capture in §1
  swept everything. *Evidence:* `test_bounds.py:540` and `test_dev.py:207`, `:215`

### 8. Generated artifacts

- **`docs/viewer.md`'s route table still names every page the app serves, and
  `tests/e2e/routes.json` is what `SCENARIOS` generates.** No route template changes here; a
  moved handler docstring does change the table's description column, which `mise run cogs`
  regenerates. *Evidence:* `tests/tools/test_gen_routes.py` and
  `tests/tools/test_gen_e2e_routes.py`

### 9. Mutation

- **The parameter dependencies kill their own mutants.** The refusal branches are the only
  decision logic this change concentrates rather than moves; a shared positive-page check covered
  by everything is where a survivor hides. *Evidence:* `mise run mutate` over the changed viewer
  modules, cold and serial, with the survivor count in the PR

## Deliberately not covered

- **Dependency functions, page models and read functions called directly.** Q2 settles it: the URL
  is the seam. A test that asserted FastAPI called a dependency would pin the shape this refactor
  exists to be free to change
- **That a page has a `models.py` at all.** The rule is conditional — a model appears only where a
  typed value crosses the seam — so §2's leaf holds the contract and never the population
- **The browser tier.** `mise run e2e` is out of `check`; nothing rendered changes, and §7's
  route-set equality is what keeps `routes.json` honest
- **Which query each read runs, re-asserted per page.** The citation footer already pins it (§5);
  a second copy would be the mirror `plans/sql-self-manifest/` is deleting two leaves for

## Unreachable through the design's seam, and findings

**Unreachable: "one request must not open the Store twice", and "the connection closes before
markup runs".** Two responses that differ only in how many times the file was opened are byte for
byte identical, and `tests/view/test_lifecycle.py` reaches the window only as *whether* a route
holds the lock across rendering — it cannot count opens or time the close. The obligation is not
dropped and not moved down a level: it is discharged at the URL level by a leaf that drives each
full-document URL through `TestClient` with a counter wrapped around `view.store.open_store` and
asserts exactly one entry per request. That leaf observes an internal name while driving a URL,
which the design's "do not add direct tests for dependency functions" does not cover either way.
The alternative — timing a writer that takes the lock while markup renders — is flaky and proves
less. **Nathaniel's call; the plan assumes the counter.**

**Finding 1 — the byte-capture basis named in the design under-covers the change.**
`tests/view/conftest.py:render_pages` builds its URLs from `conftest.pages`, which emits `/` and
node pages only. Slices 2, 3 and 5 rewrite the session list, the errors, records, offload and query
pages and every fragment — none of which the sweep renders. Capture over `SCENARIOS` instead: 40
URLs, one per route, already held equal to the app's route set by two leaves, and already the
gallery's list. Fragments included.

**Finding 2 — the two "positive page" checks are not one check.** `browse.py:135` and
`sessions/routes.py:139` refuse different numbers with different words, and the list's check is
fused with its size check. Under the design's own rule that every useful refusal message survives,
what they share is a one-line predicate, not a dependency. Sharing more than that changes a served
400's body. §4's first leaf pins both messages before the move — neither is pinned today.

**Finding 3 — slice 5's fragment work is mostly already done, and what is left is one hard
choice.** After detail-registry, the sixteen details and enrichment lines are one `fetch(spec)`
closure over `DETAILS`; after width-profiles, the popover's read is typed through
`reads.node_numbers`. What remains is §2's routes-module scan, which forces
`routes/details.py:fetched` and the popovers' `page_rows` call into a read module — or an
exception list. The design should say which before slice 5.

**Finding 4 — the errors page's conditional citation has no leaf today.** `test_errors.py:170`
asserts the queries behind the page and the stepper; nothing asserts that a page whose session
*has* failures does not cite the header probe. That is the design's own named example of evidence
that must survive the move, so it is pinned before it moves, not after.

**Forty-eight obligations.** Eight need test code: one rewritten rule (§2's model contract), four
new leaves (§2's three source scans, §4's offload offset), two extensions (§4's refusal messages,
§5's errors citation), and the contested open-count probe in §3. Three are working-tree checks —
the byte capture, the `HYPHAE_PIN_EXACT=1` run, the mutation pass. The other forty ride existing
leaves unchanged.
