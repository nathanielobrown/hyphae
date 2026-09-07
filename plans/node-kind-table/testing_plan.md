# Testing plan: one row per node kind

What the tests must show for `plans/node-kind-table/design.md`: that eight route closures, two
expansion mounts, four partial registries and seven NavTree adapters collapse into `KINDS` and
`LEVELS` while every page and every fragment serves the bytes it serves today, and that the two
tables — not a comment and not a hand-kept list in a test — are what holds every kind covered.

Nothing is mocked. The evidence is the recorded fixture corpus opened through `build_app`
(`tests/view/conftest.py:client`, `store`, `enriched_client`, `corpus_pages`), the kind and shape
selections read out of that store rather than pinned (`tests/view/selections.py:KINDS`, `LEVELS`),
and the scenario corpus `tests/view/scenarios.py`. Invented data is flagged on the leaves that use
it: the planted fat strings in `tests/view/test_bounds__node.py` and the model-written fields of
`enriched_db`, which no fixture records.

## Ordering: this lands on three siblings

Plan against the tree after `plans/sql-self-manifest/`, `plans/detail-registry/` and
`plans/width-profiles/`. Verified consequences, each a design claim to re-read at the file before
acting on it:

- **`src/hyphae/view/manifest.py` does not exist.** Nothing in this design names it, so nothing is
  void — but slice 3's "the only binding dicts left are inside the cells" is a smaller claim than
  it was: `store.bound()` already owns the width half of every dict
- **`queries.HEADER_CHARS` is gone.** The `header` cell's `int` parameter, described as "`knobs.detail`
  on a page, `HEADER_CHARS` in an expansion" (design, Key contracts), is **void as spelled**. After
  width-profiles the expansion reads its widths off a `bounds.<SURFACE>` profile through
  `store.bound()`; today's spelling is `expansions.py:175-178` and `pages.py:94,159,232,305`. The
  contract survives — one width parameter, two callers, two values — but the implementer writes it
  against the profile, not against a constant
- **`details` is no longer ten hand-written `detail_of(...)` calls.** detail-registry replaces them
  with `preview(...)` over `view/detail.py:DETAILS`. The design's `details` cell
  (`Callable[[Row, Node, int], list[Detail]]`) still type-checks, but its *justification* — "the
  tool's reads a syntax off the row, which is why this is code and not a list of names" — is
  weakened to one cell: after detail-registry, seven of eight kinds' details are a selection from
  `DETAILS`. The open question the brief settles ("the tool `details` cell keeps reading
  `result_type`") stands: detail-registry renames `result_head` → `result`, not `result_type`
  (`view_tool_header.sql:60`), so the cell is unaffected by the rename
- **`tests/view/test_bounds.py` reads `manifest.catalog()`** and `tests/view/test_layout.py` carries
  the new "no width off `analyze.queries` outside `bounds.py`" leaf. Both are sibling territory;
  this change must not reintroduce a width literal into `kinds.py`

Leaves below marked **[after width-profiles]** cannot be written before it lands.

## The obligations

### 1. Byte identity — integration, the fixture corpus through `build_app`

The design's own proof: nothing rendered changes. The mechanism already exists as
`tests/view/conftest.py:render_pages(path)`, a plain function over a store path with the
session-scoped `corpus_pages` fixture over it.

- **Every node page of the fixture corpus serves the same bytes before and after each slice.**
  *Evidence:* `render_pages(corpus_db)` captured to scratch under the OS temp directory on `main`,
  re-run after slices 1, 2 and 3, diffed to empty. `conftest.pages` derives the URL list from the
  store — one per session, turn, run, api call, tool call, compaction, plus each thread's
  `unattributed` and each session's `unattached` where the store puts a row in them — so the sweep
  is the corpus, not a list. This is a working-tree check by the implementer, not a committed leaf;
  the committed leaves that hold the same bytes are sections 2–6
- **`render_pages` does not reach a fragment, so the byte diff cannot prove slice 2.** See
  *Unreachable* below. The expansion's byte identity is discharged by the leaf in §4 instead

### 2. The two tables are total and agree — unit, no I/O

New file `tests/view/pages/node/test_kinds.py`, the design's one new leaf, extended per slice.
Note the name collision to resolve: `tests/view/selections.py` already exports a `KINDS` dict, and
`tests/view/pages/node/test_node.py` imports it — the new test must import
`hyphae.view.pages.node.kinds.KINDS` under a distinct name.

- **`set(LEVELS) == set(Kind)`** — slice 1's whole claim. Today's totality is held by a comment over
  24 `(Kind, Preset)` cells (`nav_tree.py:531`); a dict is closed only by a test. *Evidence:* the set
  equality, asserted against `Kind` itself rather than a literal list of eight
- **Every `Under` field is a callable of the builder signature.** With the `Under(NamedTuple)` the
  checker closes the preset axis, so this is thin — but the implementer may keep the
  `(Kind, Preset)` tuple key (the design's stated lean allows it), and then the preset axis is only
  as total as this leaf. *Evidence:* under the NamedTuple, `assert callable(...)` on `full`,
  `no_api`, `agents` for each kind; under the tuple key, `set(LEVELS) == set(product(Kind, Preset))`
- **`set(KINDS) == set(Kind)`** — slice 2. *Evidence:* set equality against `Kind`
- **`counts is None` iff `under is Shape.NONE`.** The two ways a kind says "nothing hangs here"
  cannot disagree: a `counts` column with no shape prints a number nothing lists, and a shape with
  no count is a heading with no total. *Evidence:* the biconditional over every row of `KINDS`
- **`opens` implies the listed child's own `under is Shape.NONE`.** The design's stated reason for
  spelling `opens` rather than deriving it — an expansion that listed a level whose rows open
  further would be the accordion-of-accordions the UI rule forbids. Today this is prose in
  `expansions.py:Listing`'s docstring. *Evidence:* for each kind with `opens`, look up the kind its
  `under` shape lists and assert that kind's `under is Shape.NONE`
- **`listed_as` is a key of `COLUMNS` or `None`.** `spanned` indexes `COLUMNS[LISTED[Kind(kind)]]`
  (`columns.py:133`) and a wrong shape opens a row narrower or wider than the table it lands in.
  *Evidence:* membership in `COLUMNS` for every non-`None` `listed_as`
- **Every deleted symbol is gone.** *Evidence:* the design's own deletion test —
  `rg -n 'TITLED|BODIES|LISTED|CHILDREN|Reader\b|Seen\b' src/hyphae/view` returns nothing — run by
  the implementer at slice 3. Not a committed leaf: `tests/view/test_layout.py` is where a source
  scan belongs, and a scan for names that no longer exist rots the day someone reuses one

### 3. Every kind still serves its page — integration, existing leaves, unchanged

These already sweep `selections.KINDS`, which is all eight. They are the regression net for slices
1 and 3 and should need **no edit**; an edit needed here is a finding.

- **Every kind of node serves a page that says what it is** — the mark, the title, the crumb, the
  selected NavTree row. *Evidence:* `tests/view/pages/node/test_node.py:84`
  (`test_every_kind_of_node_serves_a_page_that_says_what_it_is`), parametrized over all eight kinds
- **Every kind renders a body and every shape a log** across the whole rendered corpus.
  *Evidence:* `test_node.py:585:test_every_kind_renders_a_body_and_every_shape_a_log` over
  `corpus_pages`
- **A miss on any key a node URL carries is a 404** — the `header` cell returning `None` and the
  route raising with `missing`. *Evidence:* `test_node.py:132:test_a_node_the_store_does_not_hold_is_a_404`,
  which swaps the session on every kind and the node id on every kind that has one
- **A turn's page carries its transcript record** — the one kind with a `record` cell.
  *Evidence:* `test_node.py:148` and the `/fragment/record/...` assertion in it
- **The crumb chain is the `trail` cell, resolved.** A call and a tool read their turn off their own
  header row, which is the cell's stated shortcut. *Evidence:* `test_node.py:439`
  (`test_the_crumb_chain_leads_with_the_way_back_out_of_the_session`) and `:476`
- **The enrichment block appears exactly where a pass wrote one** — the `describe` cell, `None` for
  five kinds. *Evidence:* the `enriched_client` arm of `test_node.py:236` and `tests/view/test_enrichment.py`
  over `corpus_pages`
- **Walk and error-stepper still step the node's own level.** They read the trail the page built.
  *Evidence:* `tests/view/pages/node/test_walk.py` over `corpus_pages`

### 4. Expansions — integration, the two mounts

Slice 2's real net. This is where the byte-diff sweep does not reach.

- **A log row expands to the body its own page wraps, fact for fact, for all four listed kinds.**
  The strongest single leaf in the tier and the one that proves `KINDS` serves one body through two
  mounts: it walks every kind's page, opens every `data-child` row's body mount, and compares
  `fields(body, "data-body", child)` against the same fields on the child's own page — then asserts
  `opened == {"turn", "call", "tool", "run"}` so a shape the sweep missed is a failure. Run twice,
  over `client` and `enriched_client`, because a body that read enrichment differently from the page
  wrapping it would tell a reader two things. *Evidence:*
  `test_node.py:236:test_a_log_row_expands_to_the_body_its_own_page_wraps` — **existing, unchanged**
- **An api call's expansion lists the tools it called, one level and no further** — the `opens` cell,
  and the `listed` half of it. *Evidence:* `test_node.py:309:test_a_call_opened_in_its_turn_lists_the_tools_it_called`,
  which compares row for row against the call's own page and asserts the rows carry no opener
- **A kind with no level under it stands the count and the link instead** — `counts is None`
  rendering "its own page" rather than a number. *Evidence:* the `else` arm of `test_node.py:236`
  (`assert "children" not in counted`)
- **An expansion spans exactly the columns of the log that lists it** — the `listed_as` cell, which
  is what `spanned` moving from `columns.py` to `kinds.py` must not disturb. *Evidence:*
  `tests/view/pages/node/test_node__logs.py:247` (the `colspan` assertion at the end of the
  per-shape leaf) and `test_node__logs.py:306` (`test_a_log_row_opens_the_body_from_a_button_that_says_so`,
  which pins the span against `len(COLUMNS[Shape.TOOLS])`). **Edit needed:** the comment at
  `test_node__logs.py:247` names `columns.LISTED` and must name `kinds.KINDS[...].listed_as`
- **A body mount for a kind no log lists is a 404.** Today `thread_body` guards with
  `BODIES.get(kind)`, a four-entry dict; after the change `KINDS` is total over `Kind`, so the guard
  must become `listed_as is None → 404` and not simply disappear. *Evidence:* an assertion, new,
  in `test_node__logs.py` beside the existing mount leaves: `/fragment/body/.../compaction/{id}`,
  `.../session/{id}` and `.../unattributed` each answer 404. **This obligation is new to this design
  and absent from it** — see *Findings*
- **An expansion carries no page chrome.** The design's `expanded(viewer, session_id, at, knobs)`
  must not grow the crumbs, NavTree, walk or details the page wraps around the same body.
  *Evidence:* the `for wrapper in ("data-crumb", "data-nav-tree", "data-walk", "data-detail")`
  assertion inside `test_node.py:236`

### 5. NavTree levels — integration, the preset axis

Slice 1. The bytes are the proof; these leaves are what reads them.

- **Every preset shows the children it is meant to, for every kind that has any.** *Evidence:*
  `tests/view/pages/node/test_nav_tree__presets.py`, over `selections.KINDS` and the three presets
- **A level whose preset hides the path's own next step comes back in full.** `nav_tree.children`
  falls back to `CHILDREN[(at.kind, Preset.FULL)]` (`nav_tree.py:581`); under `Under` that becomes
  `LEVELS[at.kind].full`, and a NamedTuple makes it a field read rather than a second lookup. A
  fallback silently dropped renders a NavTree with the reader's own node missing from it.
  *Evidence:* the existing fallback leaf in `test_nav_tree__presets.py` — the implementer names it
  in the slice-1 commit; if none exists, it is added there, over a `noapi` reader standing on an
  api call
- **A level a `+N more` row left out still opens** — the `kin` mount reads a level from a `Ref` with
  no page under it, which is the design's stated reason identity is the whole of what a level needs.
  *Evidence:* the two `/fragment/kin/...` scenarios (`scenarios.py:247`, `:253`) and
  `tests/view/nav_trees.py`'s readers over them
- **Cost badges, compaction badges and context bars are unchanged.** The `Level` a builder returns
  feeds all three. *Evidence:* `test_nav_tree__badges.py`, `test_nav_tree__bars.py`,
  `test_nav_tree__rows.py`, `test_nav_tree__names.py` — existing, unchanged
- **A run's level is read from its run id and a thread's from its source, and a fork does not
  cross-attach.** The three id-taking builders now derive `source`, `turn_id`, `api_call_id` and the
  unattached flag from `at.kind` the way `_agent_thread` already does (`nav_tree.py:480`). The trap
  is a fork: `_agent_call` matches on the thread as well as the id because a fork's transcript
  replays its parent's calls. *Evidence:* `test_nav_tree.py` over the fork fixture session, and the
  fork arm of `tests/view/test_app__safety.py:125`, which fetches a body under `FORK_ORIGIN_RUN`

### 6. Route grammar — integration, the URL surface

Slice 3's collapse from eight routes to five. **The riskiest part of the change**, and the part the
design under-describes.

- **The five templates serve exactly the eight URLs the eight closures served.** *Evidence:* every
  URL in `conftest.pages` answers 200 through `render_pages` (§1), which covers all eight kinds
- **A `{kind}` segment that is not a word answers 404.** *Evidence:* an assertion, new, in
  `test_node.py` beside `test_a_node_the_store_does_not_hold_is_a_404`: `/session/{id}/thread/main/banana/{id}`
  is 404, as `node_numbers` answers today (`popovers.py:125`)
- **A `{kind}` segment naming a kind that is not on a thread answers 404.** `session`, `run`,
  `unattributed` and `unattached` all resolve to a `KindSpec` once `KINDS` is total, so
  `/session/{id}/thread/main/session/{id}` would read a session header keyed by a thread it has no
  business on. Today no such URL can be built: the four thread routes are literal.
  *Evidence:* the same new assertion, over all four off-thread kinds. **New to this design and
  absent from it** — see *Findings*
- **Route declaration order is safe.** `popovers.py:98` carries a live example of a `{kind}` route
  shadowing a sibling. Here the three-segment `unattributed` mount and the four-segment `{kind}`
  mount cannot collide, and the run mount carries no `thread`. *Evidence:* the 200s in §1 plus the
  route-set equality leaves in §7 — if a template shadowed another, one of the eight URLs would
  answer the wrong page and its `data-body` kind would fail `test_node.py:84`
- **No response leaks a reflected URL segment.** A route that echoes an unresolved `{kind}` into its
  404 text would be new. *Evidence:* `tests/view/test_app__safety.py:56`
  (`test_planted_markup_arrives_inert`) and the CSP leaf at `:51`

### 7. Generated artifacts about routes — the tooling tier

**Not in the design's file-tree diff, and every one of these is red the moment slice 3 lands.**
Verified against the working tree.

- **`docs/viewer.md`'s route table names every page the app serves.** `tools/gen_routes.py:PAGE_NAMES`
  is keyed by route template and *crashes* the generator on a route with no name; four of its
  entries ("A turn", "An api call", "A tool call", "A compaction") name templates that will not
  exist. The description column is the handler's own first sentence, so four descriptions become
  one. *Evidence:* `tests/tools/test_gen_routes.py:47:test_every_page_the_app_serves_is_in_the_table`,
  `:101:test_every_page_name_still_names_a_route_the_app_serves`, and
  `:108:test_a_page_name_is_the_short_term_the_glossary_fixes` — the collapsed row's name must be a
  term `CONTEXT.md` fixes, for which **Node page** already exists
- **`SCENARIOS` is exactly the route set the shipped viewer exposes.** *Evidence:*
  `tests/view/test_bounds.py:551` (`assert exposed == set(SCENARIOS)`) and
  `tests/view/test_dev.py:215-216` (`assert declared(client) == set(SCENARIOS)`). Four scenario keys
  must merge into one; the design says scenarios do not change
- **`tests/e2e/routes.json` is byte for byte what `SCENARIOS` generates.** *Evidence:*
  `tests/tools/test_gen_e2e_routes.py:21`; regenerated in the same commit
- **No two scenarios share a title, and every scenario names its group.** Merging four keys into one
  leaves one title where there were four, so the browser tier loses three Chromatic baselines.
  *Evidence:* `tests/view/test_scenarios.py:test_no_two_scenarios_share_a_title` stays green either
  way — which is exactly why the *loss* needs a decision, not a test. See *Findings*

### 8. Budgets, bounds and layout — the rules that must not move

- **A node page and an expansion still cost what the ceiling budgets, at the worst knobs.**
  *Evidence:* `tests/view/test_bounds__node.py:352`, `:383`, `:407`, and `:440`
  (`test_an_expansion_weighs_a_body_and_the_one_page_of_rows_it_lists`), the last of which fetches
  body mounts for `call`, `turn` and `tool` over a planted store. Invented data, and labelled as
  such in the file: the fat strings are planted past each cut on purpose, because no recorded
  session holds a value at every ceiling at once. **[after width-profiles]** — the leaf reads
  `queries.HEADER_CHARS` at `:99`, `:319`, `:459` today and reads a profile after the sibling lands
- **The exact byte pins hold under `HYPHAE_PIN_EXACT=1`.** *Evidence:* `tests/view/budgets.py:174`
  and the pinned rows it guards; a passing `mise run check` plus one `HYPHAE_PIN_EXACT=1` run by the
  implementer at each slice
- **`kinds.py` reaches no web framework and imports no markup.** The design's claim that the table
  is framework-free — a header cell returns `None` and the route says 404. *Evidence:*
  `tests/view/test_layout.py:225:test_only_a_pages_routes_module_reaches_a_web_framework` and
  `:256:test_only_a_markup_module_imports_htpy`. `kinds.py` sits outside `routes/`, so the first leaf
  covers it with no edit
- **`kinds.py` is not a `models.py` in disguise.** `Found` and `Log` stay in `kinds.py` because they
  never cross into markup; the rule reads zero either way. *Evidence:*
  `test_layout.py:281:test_a_models_module_appears_only_where_a_second_markup_module_reads_it`
- **The shared node layer still reads nothing from a page** — `GLYPHS` and `NUMBERED` stay in
  `nodes.py` for this reason. *Evidence:* `test_layout.py:363:test_the_shared_node_model_reads_nothing_from_a_page`
- **No module of a page is named for nothing.** `kinds.py` is a new module name in a package the
  rule scans. *Evidence:* `test_layout.py:268:test_no_module_of_a_page_is_named_for_nothing`

### 9. Mutation

- **The invariant leaf kills mutants in `kinds.py`'s own cells.** A table read by every page is
  covered by everything, which makes a survivor there easy to miss. *Evidence:*
  `mise run mutate 'hyphae.view.pages.node.kinds.*'` and `'hyphae.view.pages.node.nav_tree.*'`,
  cold and serial, reported in the PR with the survivor count

## Deliberately not covered

- **That `KINDS` has exactly eight rows.** A count pins the population, not the contract; the
  set equality against `Kind` forbids both a missing row and an extra one, and says which
- **Which query each header cell runs.** The citation footer already pins it per page
  (`tests/view/test_app.py`), and re-asserting it in `test_kinds.py` would compare two copies of
  one fact — the mistake `plans/sql-self-manifest/` is deleting two leaves for
- **`Shape` collapsed into `Kind`.** Out of scope by the design; it moves served `data-shape` values
- **Popovers.** Out of scope by the design; `routes/popovers.py` keeps its own `{kind}` route and its
  `NUMBERED` guard, and `test_numbers*.py` is untouched
- **The browser tier.** `mise run e2e` is out of `check`; §7's regenerated `routes.json` is what
  keeps it honest, and no spec here asserts a pixel

## Unreachable through the design's seam, and findings

**Unreachable: the design's byte-diff proof does not cover slice 2.** `render_pages` builds its URL
list from `tests/view/conftest.py:pages`, which emits node *pages* only — no `/fragment/body`, no
`/fragment/kin`. Slice 2 rewrites exactly the fragments the sweep cannot see. The obligation is not
dropped and not moved down a level: it is discharged at the same level by §4's first leaf, which
compares each expanded body against the page body for all four listed kinds, plus §8's expansion
budget leaf over the three widest mounts. The implementer should extend the working-tree capture to
the body and kin mounts for slice 2 — the URLs are already derivable from the `hx-get` values on
each page the sweep renders.

**Finding 1 — the route table changes, and the design says it does not.** "No URL, query or rendered
byte changes" is true of served URLs and false of route *templates*, which are a generated, tested,
documented artifact in four places (§7). Collapsing four templates into one costs `docs/viewer.md`
four named rows, `SCENARIOS` four keys, `tests/e2e/routes.json` four entries and the browser tier
three Chromatic baselines — the turn page, the api call page, the tool call page and the compaction
page stop being separately snapshotted. Slice 4 anticipates `mise run cogs` but names none of this.
The implementer needs a decision before slice 3: either accept the loss and re-key `SCENARIOS`, or
keep the four page routes as thin declarations over one shared adapter so the templates survive.
The second keeps every artifact in §7 green and still deletes the eight `read` closures, which is
where the duplication actually lives.

**Finding 2 — a total `KINDS` opens URLs the partial registries closed.** `thread_body` guards with
`BODIES.get(kind)` (four entries) and `node_numbers` with `kind not in nodes.NUMBERED`; both are
partial *by design*, and that partiality is the 404. `KINDS` is total, so the `{kind}` handler must
carry its own rule for which kinds may appear in a thread slot. The design's Key contracts do not
mention one. Two new leaves cover it (§4 and §6); the design needs the rule spelled.

**Finding 3 — three claims in the design's test seam are wrong, verified.** (a) "the four listed
kinds have a body scenario in `tests/view/scenarios.py`" — there are **two** body scenarios, a turn
via the thread mount (`scenarios.py:234`) and a run (`:239`); call and tool bodies have no scenario,
and the all-four evidence lives in `test_node.py:236` instead. (b) "`thread_body` … resolves
`Kind(kind)`" — it does not; it does `BODIES.get(kind)` (`expansions.py:168`). (c) "comments naming
`columns.LISTED`" is one comment, `test_node__logs.py:247`. The test-local `CHILDREN` dict at
`test_node.py:228` is correctly identified and is unrelated to `nav_tree.CHILDREN`.

**Verified as stated:** the seven adapters at `nav_tree.py:497-522`, the 24-cell `CHILDREN` at
`:531`, `Seen`/`Reader`/`TITLED`/`described_node` at `browse.py:48/78/82/98`, `Body`/`Listing`/
`BODIES`/`run_body` at `expansions.py:41/55/76/226`, `LISTED`/`spanned` at `columns.py:123/131`,
eight `@router.get` closures in `pages.py`, and that no test imports a deleted registry.
`_agent_thread` is at `nav_tree.py:480`, not `:482` — the design's own instruction to check each
line at the file applies.
