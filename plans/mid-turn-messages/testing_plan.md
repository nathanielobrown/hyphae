# Testing plan: mid-turn messages (HP-26)

The design binds this plan: [design.md](design.md). Scope follows Nathaniel's approval. The work runs slices 1–4, and slice 4 renders interjections from all three senders, with a task notification capped at 400 characters. Slice 5, the 1,068 interjections written as `user` records, landed later in a stacked PR; its leaves sit beside slice 2's in `tests/extract/test_claude_code__interjections.py`, and this plan does not list them.

Every fixture source and line number below was read from the on-disk transcripts under `~/.claude/projects` on 2026-09-25, printing shapes only (type, `commandMode`, `origin.kind`, lengths, tag offsets) and never text. The canonical store was not opened. Where a line number feeds a trim, the implementer re-reads it before cutting.

## Design findings: what the chosen seam cannot reach

The design's seam is two trimmed sessions: mac_settings `27a459ba` and factory thread `aaceab3ee53af97d8`. Four obligations cannot go red against those two alone:

1. **File order against timestamp.** Neither fixture holds a record where the two rules disagree, so a parser that attributes by timestamp passes every leaf. Recorded fix: writer `1d58565d-b635-46e0-bb78-4a64a8eecf1a` (2.1.267). Line 1515 is a task notification stamped 15:53:42, between the `/command` turn at line 1482 (15:53:10) and the prompt at line 1493 (15:54:26). File order gives the turn at 1493, and the timestamp gives the one at 1482.
2. **A pre-prompt record gets `turn_id = NULL`.** Neither fixture has a record before its thread's first prompt. The only one on disk is mycelia `e684d4da-e05b-49a4-b91e-2c409568a934` line 6, a task notification at 2.1.220 (the design counted 13 in the store, but the rest have been pruned or split differently under my approximate turn rule). A new mycelia session would move the analyze pins, so **borrow** that record into `27a459ba` ahead of its first prompt (line 5). The borrowed record keeps its recorded content and version, 2.1.220 like its host. Only its position is invented. Label it the way `fork_origin/README.md` labels its borrowed compaction.
3. **A `prompt`-mode record from a peer resolves to `AGENT`.** This is the reason readers key on `origin.kind`, and neither fixture holds one. Recorded fix: factory `dc22318a-c21f-4c29-bfa7-547fc2ec771d` line 244 (2.1.259, `commandMode: prompt`, `origin.kind: peer`). It also carries `fromMode`, `hopChain`, `msg_id` and `verifiedPeerPid`, which gives four `Origin` keys a fixture citation instead of a scan citation. Borrow it into the trimmed `af7e1907` main (same project, same 2.1.259) rather than adding a session.
4. **`replayed = True` on an interjection.** The design words this leaf as "an annotated duplicated fixture line". A duplicate within one file tests `resolve_duplicates`, not replay. Replay requires a record copied between two transcripts of one session, and the design's own census found none. Only a borrowed record reaches it. Put one recorded queued_command into `fork_origin/`'s copied prefix, in both the auditor and the fork, following that fixture's borrowed-compaction precedent. This also gives the `live_interjections` leaf and the OTLP privacy leaf a non-empty case, since `fork_origin` is under the analyzed project.

The slice-4 cap needs one more recorded record. Every task notification in thread `aaceab3ee53af97d8` is 375–396 characters, under the 400 cap, so the cap never bites on it. `af7e1907` main line 165 is 839 characters, with `</status>` closing at 218 and `<result>` opening at 517. Keep it in the main trim, together with the prompt at line 156 that opens its turn.

Items 1–3 and the cap record need recorded data beyond the design's two trims but stay inside its seam, so none is unreachable. Item 4 is reachable only with a borrowed (positionally invented) record.

## Fixture trimming

Put everything under `tests/fixtures/interjection/`, one README per the `fork_origin/README.md` pattern. Each source's README entry records the path, the kept line ranges out of the total, the Claude Code version, the date, what each kept record is for, and every borrowed record with its origin.

1. **`27a459ba` main** (mac_settings, 2.1.220, 2026-07-27, 199 lines). Keep the bookkeeping head, the prompts at lines 5, 63 and 176, the `prompt`/`human` record at line 119, and enough calls to keep line 119 inside the turn opened at 63. Borrow `e684d4da` line 6 ahead of line 5 and rewrite its `sessionId` to the host's.
2. **`af7e1907` main plus thread `aaceab3ee53af97d8`** (factory, 2.1.259–2.1.263, 2026-09-06). In main, keep the turn at line 156 with the task notification at 165, the parent `Agent` call and its result, and the turn at line 536 with its `prompt`/`human` record at 543 (2.1.263, which carries `rendered`). Borrow `dc22318a` line 244 into that turn, after 543. The thread keeps its opening prompt (line 1), task notifications 184 and 330, the coordinator record at 312, and its `.meta.json`. Drop the compaction at lines 186–187, because it is not what these leaves test and a compaction row would change compaction counts elsewhere.
3. **`1d58565d` main** (writer, 2.1.267, 2026-09-17). Keep the bookkeeping head, lines 1482, 1493 and 1515, and the records between them only as far as the turn rules need them.
4. **`fork_origin/`**. Copy one recorded task notification (from trim 2) into the copied prefix of both subagent files under one uuid, and extend that fixture's README.

Redaction rules:

- Replace what a person, coordinator or peer typed with `[redacted]`. Keep Claude Code's own wrapper sentences in `rendered`, which are harness text.
- In a task notification, redact the text inside each tag and keep every tag. Pad the redacted text to its original length so the tag offsets survive, because the cap leaf depends on `</status>` sitting before 400 and `<result>` after it.
- Scrub `hopChain`, `msg_id` and `verifiedPeerPid` values to same-typed placeholders.

Checks before committing:

- Every trimmed file validates through `read_lines` with no unknown field or kind (the corpus leaf below).
- Each new session's date is checked against the analyze corpus span. The design claims `tests/analyze/conftest.py`'s pins are mycelia-scoped. A past fixture outside the span churned six files, so confirm this by running `tests/analyze` unchanged, not by assumption.
- `mise run test` is green before any source change except the registry. This proves the trims and borrows are well-formed on their own.

Block-list prompts: the one recorded `[text, image]` prompt (2.1.221) was left out of the design's fixtures because of its base64 image. Prefer redacting it, with the image `data` swapped for a short placeholder and the text replaced by `[redacted]`, over an invented line. Recorded candidates are the files holding both `imagePasteIds` and `queued_command`, found by grep: mycelia `8320539c`, `483cec84` and mac_settings `18b73483`. If the record sits in a mycelia session, borrow it into `27a459ba`. Fall back to a labeled invented line only if none of these holds it.

## Test obligations

- **records (unit)**: model validation with no I/O beyond reading fixture files. Recorded records stand in for the world, and invented records appear only where a shape has no recording. Lives in `tests/extract/test_records.py` unless noted.
  - **Every record in the fixture corpus, attachments of all ten recorded kinds included, carries no field the models leave undeclared.** This is critical because moving `attachment` off `ArchivedRecord` removes an `OPAQUE` stop, so every attachment envelope key must now be declared. *Evidence:* `test_no_recorded_record_carries_a_field_the_models_do_not_declare` stays green unchanged over the new fixtures. Red-check: delete `rendered` from `AttachmentRecord` and the report names `attachment.rendered`.
  - A `queued_command` resolves to `QueuedCommand`, and every other attachment kind resolves to the dict arm. *Evidence:* a new leaf over `fixture_records("tests/fixtures/interjection")` and the zoo's `deferred_tools_delta`, asserting the `attachment` field's type for each.
  - **A malformed `queued_command` raises and does not fall back to the dict arm.** *Evidence:* an invented `tests/fixtures/invented/invented-bad-queued-command.jsonl` (a `prompt` of type int) plus a leaf in `tests/extract/test_claude_code.py` beside `test_an_unknown_content_block_crashes`. It asserts `TranscriptSchemaError` and a message free of the `SUPER-SECRET-PAYLOAD` sentinel. Invented because no recording is malformed. Add a row to `invented/README.md`.
  - An attachment kind no model names validates through the dict arm. *Evidence:* a zoo attachment with `type` rewritten in the test, following `test_a_field_claude_code_adds_later_rides_along`.
  - `UserRecord.origin` and `QueuedCommand.origin` are the one `Origin` model. *Evidence:* both annotations equal `Origin | None`. Remove `(UserRecord, "origin")` from `test_an_object_no_reader_opens_is_declared_as_a_dict_rather_than_modelled`.
  - The registry change is consistent. *Evidence:* `test_every_registered_shape_has_a_model_or_a_stated_reason` and `test_no_reason_is_left_for_a_shape_that_no_longer_exists` pass with `attachment` gone from `ARCHIVED_UNREAD`. `test_a_kind_borrowed_from_the_other_registry_is_unknown` swaps `ArchiveRecordType.ATTACHMENT` for another archived type. `test_an_archived_kind_keeps_its_envelope_and_carries_the_rest_whole` swaps its `attachment` example for another archived kind and loses the "24k attachments" comment. `test_exactly_two_models_stop_the_walk_and_each_says_why` stays unchanged.
  - Each new field's citation holds. `rendered` is shown in the factory trim and cited absent from `27a459ba` (2.1.220). Each `Origin` key is cited to a fixture where one holds it (items 2–3 above) and to a scan otherwise. *Evidence:* `test_every_citation_shows_the_field_in_the_fixture_it_names` and `test_every_cited_fixture_exists`, unchanged. The `docs/schema.md` cog stays fresh under `mise run check`.

- **extract (parser)**: `ClaudeCodeExtractor().extract(fixture_source(...))` over the trimmed sessions, with no store. The topic is new, so it gets a new file, `tests/extract/test_claude_code__interjections.py`.
  - Each fixture's interjections come out whole. *Evidence:* whole-row equality against a list of `Interjection` for `27a459ba` (one PERSON row plus the borrowed pre-prompt TASK row) and for `af7e1907` (main: TASK at 165 with its 839 characters whole, PERSON at 543, the borrowed peer; thread: TASK, AGENT, TASK in file order). Ids are the record uuids, and `source` is `main` or the agent id.
  - **A `prompt`-mode record from a peer is `AGENT`, not `PERSON`.** Critical: it is the one record where `commandMode` and `origin.kind` point different ways. *Evidence:* the borrowed `dc22318a` row inside the whole-row equality. Red-check: map `prompt` to `PERSON` and it fails.
  - **An interjection belongs to the turn open at its place in the file, not the turn open when it was stamped.** *Evidence:* the `1d58565d` line-1515 row's `turn_id` equals the uuid of the prompt at line 1493. Red-check: attribute by timestamp and it yields line 1482's turn.
  - A record before the thread's first prompt has `turn_id = None` and is still a row. *Evidence:* the borrowed `e684d4da` row in the `27a459ba` whole-row list.
  - The `timestamp` field is the envelope's: typed-at when `attachment.timestamp` exists, delivered-at for the no-mode coordinator record. *Evidence:* the whole-row values for the records at lines 119 and 312, compared against each record's own envelope in the fixture.
  - A block-list prompt flattens to text joined by blank lines, with `[image]` in place of each image. *Evidence:* the redacted 2.1.221 record (or the labeled invented fallback). Its row's `text` is asserted whole.
  - **An `origin.kind` outside the three raises a schema error naming the session, line and value, and quoting no text.** *Evidence:* an invented `invented-unknown-sender.jsonl` in a leaf shaped like `test_a_record_with_no_timestamp_crashes_naming_the_kind_it_was`, asserting the whole message. A `prompt`-mode record with no `origin` joins the parametrized `test_a_record_missing_a_field_a_reader_needs_crashes_naming_that_field` as `invented-no-origin` (field `origin`, kind `attachment`). Both are invented and get rows in `invented/README.md`. One session's failure staying contained is already `tests/test_pipeline.py:test_a_session_the_parser_refuses_costs_only_itself`. The new error must subclass `ExtractionError` to inherit that proof, which the `pytest.raises(TranscriptSchemaError)` here pins.
  - **A queued_command a fork copied is a replay in the fork and live in the transcript that ran it.** *Evidence:* extend `tests/extract/test_claude_code__forks.py:test_a_copied_record_belongs_to_the_transcript_that_ran_it` with `{(AUDITOR, False), (FORK, True)}` over `extracted.interjections`. Borrowed data (finding 4).

- **store (DuckDB on disk)**: the real `StoreExporter` and `StoreExtractor` over temporary stores built from fixtures. Parametrized leaves pick up the new table automatically. The ones below need edits.
  - DDL and version move together. *Evidence:* `tests/store/test_schema.py` gets the new trace digest at `SCHEMA_VERSION = 11`. `test_a_tables_ddl_columns_are_exactly_its_models_fields` and `test_a_live_rows_field_names_the_table_holding_its_row_type` gain their `interjections` cases by parametrization.
  - Every column round-trips, the `NULL` turn included. *Evidence:* `tests/store/test_trace_store.py:test_a_trace_round_trips` adds `("interjections", ...)` from the `27a459ba` trace, whose borrowed row carries the `NULL`.
  - `live_interjections` holds what the trace calls live. *Evidence:* `FORK_ROWS["interjections"] = (2, 1)` in `test_the_live_views_hold_what_the_trace_calls_live`. Without the `fork_origin` borrow this case is `(0, 0)`, which proves nothing.
  - The store rebuilds the trace, interjections included. *Evidence:* `tests/store/test_trace_reader.py:test_every_fixture_session_round_trips` over the new fixtures, unchanged.
  - **Migration 10→11 opens an old store with its rows and an empty `interjections` table shaped and keyed like the DDL.** *Evidence:* extend `tests/store/test_trace_store__migrations.py:test_an_older_store_is_migrated_and_keeps_its_rows` with the same three assertions it makes for `session_tags`: count 0, shape, keys. Red-check: remove the step's `CREATE TABLE` and it fails at the shape assertion.

- **store repository (`store.nodes.interjections`)**: the session-scoped `corpus_db` built from fixtures. Planted rows in a copied store cover shapes the corpus lacks. Lives in `tests/store/test_nodes.py`.
  - A turn's rows come back in file order, cut at `INTERJECTIONS.text_chars`, with the citation naming `view_turn_interjections`. *Evidence:* whole-list equality for the `aaceab3ee53af97d8` turn (three rows) and the citation's name and bindings.
  - A ninth row comes back as the lookahead, and `dropped` counts the rest. *Evidence:* nine or more planted rows under one turn in a copied store. Synthetic, because no fixture turn holds nine, though the store's p99 is 28.
  - The binder refuses a wrong keyword or width. *Evidence:* the new method added to `test_a_keyword_left_off_or_added_is_refused` and `test_a_key_or_a_width_the_statement_lacks_is_refused_by_the_binder`.

- **viewer (FastAPI `TestClient`)**: the app over the fixture corpus store. Planted stores cover ceilings. The section is a new topic, so it gets a new file, `tests/view/pages/node/test_node__interjections.py`, plus edits to the bounds files.
  - The turn page shows a "Mid-turn messages" section between the facts and the children log, one `data-interjection` row per message with sender, timestamp and cut text. *Evidence:* the `aaceab3ee53af97d8` turn page, with section order asserted by position in the markup.
  - A turn with no interjections draws no section, not an empty heading. *Evidence:* a `spine` turn page carries no `data-interjection` and no heading.
  - **Task-notification markup reaches the reader as text, not as elements.** Critical, because recorded interjection text is full of `<task-notification>` tags. *Evidence:* the visible text (via `tests/view/conftest.py`'s markup-to-text helper) contains the literal `<status>`, and the parsed markup holds no `status` element. Red-check: mark the text safe and it fails.
  - More than eight rows prints "+N more" with N from the store. *Evidence:* the planted store from the repository leaf, with N asserted against `count(*)`.
  - A pre-prompt row shows on no turn page and stays on the Records page. *Evidence:* the borrowed `27a459ba` record's line appears on the thread's Records page, and no turn page carries its uuid.
  - The footer cites the statement, and the query page rebinds it. *Evidence:* the existing footer-to-query-page sweep reaches `view_turn_interjections`. Confirm the sweep walks every citation, and add the scenario if it walks scenarios only.
  - The new width profile is pinned. *Evidence:* `INTERJECTIONS` added to `PROFILES` in `tests/view/test_bounds__widths.py:test_every_surface_declares_the_widths_it_prints_at`.
  - **A turn page with eight rows of `&` at `text_chars` stays within `NODE_BYTES`, weighed row by row.** *Evidence:* `tests/view/test_bounds__node.py:escaped_at_every_cap` plants nine rows of `&` under one turn. `swept()` splits the new `interjection` row class, and `tests/view/budgets.py` gains its measured markup and allocates eight rows. `test_a_node_page_at_the_sizes_a_reader_gets_costs_what_the_ceiling_budgets` weighs them. Synthetic by design, like the rest of that plant.
  - The gallery holds the page. *Evidence:* a `tests/view/scenarios.py` entry at the `aaceab3ee53af97d8` turn URL, `test_scenarios.py` green, and `tests/e2e/routes.json` regenerated fresh under `mise run check`.

- **enrichment render (slice 4)**: `render_turn` and `render_run` over `fixture_db`, with `"interjection"` added to `tests/conftest.py:ENRICHMENT_FIXTURES`, and `mutable_db` for edits. Lives in `tests/enrich/test_prompts.py` and `test_prompts__budget.py`.
  - **A turn renders each interjection under the prompt, headed by its sender.** *Evidence:* whole-string goldens for two `af7e1907` main turns, beside `test_a_plain_main_turn_renders_its_prompt_then_its_calls`: the turn at line 156 (TASK) and the turn at line 536 (PERSON at 543 plus the borrowed peer AGENT, placed in that turn). Together they cover all three senders. Red-check: skip interjections in `render_turn` and both fail.
  - A run renders the same, with a coordinator message and task notifications. *Evidence:* a whole-string golden for the `aaceab3ee53af97d8` run.
  - **A task notification is capped at 400 characters and keeps its status.** *Evidence:* the rendered 839-character record at line 165 contains `</status>` and lacks `<result>`. Red-check: set the cap to 200 and `</status>` is lost. Remove the cap and `<result>` appears.
  - PERSON and AGENT text is capped at the prompt's width. *Evidence:* a `mutable_db` UPDATE lengthening one row's text past the prompt cap. Synthetic length, labeled.
  - A replayed interjection renders only under the transcript that ran it. *Evidence:* the `fork_origin` borrow, following `test_a_replayed_turn_is_not_the_runs_task`. The design is silent here. If items read corpus rows rather than live ones, this leaf is a design question for Nathaniel.
  - An item without interjections renders byte-for-byte as before, so only items with interjections go stale. *Evidence:* the existing goldens (`spine`, `server_tools`, `teammate` and others) stay green with no edit. `test_input_hash_reads_the_rendered_content_and_nothing_else` gains one step: an UPDATE to an interjection's text moves the hash.
  - `prompt_version` is unchanged. *Evidence:* the pinned version literals in `test_prompts.py` stay unedited.
  - Real items stay within budget. *Evidence:* `test_no_real_item_renders_past_its_budget` behind `HYPHAE_LIVE_STORE`. This is a manual run, because task notifications reach 30,889 characters and only the cap keeps them in.

- **OTLP (fake receiver)**: the existing `planted` store and `Receiver`, in `tests/export/`.
  - Interjection text never ships. *Evidence:* `("interjections", "text")` added to `EXCLUDED` in `tests/export/test_otlp__privacy.py`. The `fork_origin` borrow gives the analyzed project a row to plant the sentinel in.
  - Interjections produce no span. *Evidence:* the census and shaping counts in `tests/export/test_otlp__census.py` stay unedited.

- **live census (manual, `HYPHAE_LIVE_STORE`)**: the canonical store, read by the existing slow leaves. CI cannot run them.
  - Every one of the store's attachments validates, with no undeclared field, `Origin` key types included (design open question 2). *Evidence:* `tests/extract/test_records__census.py:test_every_recorded_record_validates_against_its_model` and `test_no_recorded_record_carries_a_field_the_models_do_not_declare`. State the run and its date in the PR fact sheet.
  - A re-extract yields the design's counts. *Evidence:* a read-only count of `interjections` by sender after `hp extract` into a scratch `--db` in `data/`: 1,223 rows expected from on-disk files. This is a check on the design's numbers, not a CI leaf.

## Red-green discipline

Every bolded leaf names its red-check above. Beyond those:

- Before trusting a new leaf, break the line it guards and watch it fail. Examples: return `[]` from `_interjections`, drop `replayed` (always `False`), attach pre-prompt records to the first turn, and truncate `text` at extract. Each must fail at least one leaf by name.
- Run `mise run mutate` on the branch's changed sources, cold and serial as `.claude/rules/testing.md` requires. Read each survivor in `_interjections`, the sender mapping, the flattening, the repository method and the render functions. Each one is either an assertion to add or a finding about unreachable code. Quote the survivor count in the PR.

## Not covered, and why

- **The nine in-file rewinds.** `resolve_duplicates` collapses them before any parser runs, and `test_a_duplicate_uuid_resolves_to_its_last_occurrence` already proves that. `_interjections` reads only the collapsed lines, so a leaf here would retest the collapse.
- **A transcript rebuilt from `raw_records` by line number.** That extractor belongs to the canonical-model stack and does not exist yet. The design's claim that `_interjections` reads only transcript lines and the session's own files is inferred. The stack's own round-trip will test it.
- **The `EXTRACTOR_VERSION` bump.** A test would only restate the constant. `test_a_bumped_extractor_version_re_extracts_everything` covers what a bump does, and review of the diff covers that it happened.
- **The `queue-operation` journal, the other 48 attachment kinds' schemas, inline image rendering, and OTLP spans.** All are out of scope per the design.
- **The browser tier.** The section adds no interaction. The gallery scenario feeds `mise run e2e` for a visual check, but no spec asserts on it.
