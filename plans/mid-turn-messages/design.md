# Mid-turn messages (HP-26)

Every count below was read from the canonical store on 2026-09-25 (1,633 sessions, Claude Code 2.1.186–2.1.280, `raw_records`, opened read-only), and every code claim was re-read in the tree at `dfcdbdd3`. Nothing here quotes a prompt.

## Problem

While a turn runs, Claude Code lets the person type; it queues the text and delivers it to the model mid-turn as an `attachment` record with `attachment.type = "queued_command"`. The extractor currently archives every `attachment` verbatim (`ArchiveRecordType.ATTACHMENT`, `shapes.py`) without reading it. Consequently, pages, queries, and enrichment passes only see a turn's initial prompt—any mid-turn correction like "stop, do X instead" remains invisible everywhere except the Records page.

The store holds 1,227 of these in three distinct shapes, covering more than direct user input:

| `commandMode` | count | where | `origin.kind` | what it is |
| --- | --- | --- | --- | --- |
| `task-notification` | 1,111 (396 main, 715 agent threads) | 102 + 18 sessions | never carried | a background task ended; the body is `<task-notification>` markup with a `<status>` (completed 970, failed 42, killed 18, blank 81) |
| `prompt` | 83, all `main` | 57 sessions, 2.1.195–2.1.263 | human 81, peer 2 | what the person typed mid-turn, or another session's message |
| absent | 33, all agent threads | 10 sessions, 2.1.259–2.1.278 | coordinator 25, peer 7, human 1 | what a coordinator or peer sent a running subagent |

Claude Code's wrapper on the record (`rendered`, present from 2.1.259) matches `origin.kind`: "The user sent a new message while you were working:" for humans, and a coordinator or external-session sentence otherwise. The two human-facing shapes coexisted across 2.1.259–2.1.263, with the final `prompt`-mode record dated 2026-09-09. While the 46 sessions at 2.1.264 or later contain none, their total enqueue volume is too low to prove the shape was retired; the absence remains unbounded. Readers must therefore key on `origin.kind` and treat `commandMode` merely as a label, not an authoritative discriminator.

Attribution: the extractor writes the record at its delivery position in the transcript. For shapes containing an `attachment.timestamp` (1,194 instances, always identical to the envelope's), Claude Code stamps when the person typed: 964 have a `parentUuid` pointing to a prior tool result that bears a later timestamp, 261 reference an earlier attachment, and 9 reference an item appearing later in the file. The 33 entries without a mode omit `attachment.timestamp`, and their parent entries carry timestamps equal to or earlier than their own; their envelope timestamp represents delivery time. File order and timestamp map to the same turn for all but 18 items (tie-sensitive, varying between 18 and 20 across runs: 16 fall earlier by timestamp, 2 later). Across both ordering rules, 13 task notifications precede their thread's first prompt. `source_uuid` resolves to no record in its session (56/56). Every one of the 1,227 carries `uuid` and `parentUuid`. Nine are in-file rewinds — the same uuid written twice in one transcript, which `resolve_duplicates` collapses to the last write before any parser runs — so a thread holds 1,218 distinct uuids. Twelve uuids recur across sessions (25 records; a resume copies its parent's history), which the store keeps as separate rows per session, as it does the 541 api-call ids in the same position. No queued_command is copied between two transcripts of one session today, so `replayed` is `False` on every row; the column stays because `parse` threads the flag through every row family.

One `prompt` is not a string: a 2.1.221 record with `imagePasteIds` contains a list of content blocks, `[text, image]`. Among string prompts, task notifications reach up to 30,889 characters; `prompt`-mode records range from 15 to 1,881 characters, with a median of 100.

## Call paths

Current:

```
read_lines → model_for → ArchivedRecord (attachment) → raw_records only
```

Proposed:

```
read_lines → model_for → AttachmentRecord            (RecordType.ATTACHMENT, one model for every attachment)
               .attachment: QueuedCommand | dict     (discriminated on attachment.type)
parse._interjections(lines, turn_by_line, replayed) → Interjection rows → Parsed.interjections
SessionTrace.interjections → TABLES["interjections"] → live_interjections / corpus_interjections
  → store.nodes.interjections(turn, widths)  → turn page: "Mid-turn messages" section
  → store.enrichment.turn_items / run sections → render_turn / render_run   (slice 4, if taken)
```

Turn assembly remains unchanged: `_turns` still initializes one turn per prompt, and interjections look up `turn_by_line[line_no]` identically to `ApiCall` (`parse.py`). Any record delivered before the thread's initial prompt assigns `turn_id = NULL` while remaining an accessible store row.

`_interjections` reads only what `parse` already hands every other row family: the thread's deduplicated lines, the turn map built from them, and the replay set `replayed_lines` derives from the session's own transcripts and `.meta.json` files (`claude_code.py`). It reads no other session, no store row and no journal, so a transcript rebuilt from `raw_records` by line number parses the same (the canonical-model plan's store-backed extractor, `handoffs/handoff_2026_09_25_canonical-model-context.md`). `queue-operation` enqueue and dequeue timing plays no part in placing an interjection: file order places it, and the journal's timestamps would only add queue latency.

## File-tree diff

```
src/hyphae/extract/records/registry.py   ATTACHMENT moves from ArchiveRecordType to RecordType
src/hyphae/extract/records/attachments.py  AttachmentRecord, QueuedCommand, Origin           (new)
src/hyphae/extract/records/conversation.py UserRecord.origin: dict → Origin (the same object, declared once)
src/hyphae/extract/records/shapes.py     RECORD_MODELS gains AttachmentRecord; ArchivedRecord docstring loses its attachment count
src/hyphae/extract/parse.py              _interjections; Parsed gains interjections; Sender mapping
src/hyphae/extract/claude_code.py        EXTRACTOR_VERSION bump (a new row family from the same files)
src/hyphae/models/trace.py               Interjection, Sender; LiveRows and SessionTrace gain interjections
src/hyphae/store/trace_store.py          DDL + TABLES["interjections"]
src/hyphae/store/schema.py               SCHEMA_VERSION 11; migration creates the table
src/hyphae/store/queries/view_turn_interjections.sql   (new)
src/hyphae/store/nodes.py                NodeRepository.interjections()
src/hyphae/view/bounds.py                INTERJECTIONS widths: text_chars, and the fixed row count
src/hyphae/view/pages/node/markup/page.py   section on the turn mount, between facts and log
src/hyphae/view/text/labels.py           the label
tests/fixtures/interjection/             two trimmed sessions, one .meta.json, README   (new)
tests/view/budgets.py                    the section's cost on a turn page
tests/extract/test_records.py, test_claude_code.py, tests/store/test_schema.py, test_trace_store.py,
tests/view/scenarios.py                  the leaves the seam names
CONTEXT.md, docs/schema.md (cog), docs/store.md (ERD, migration 11), docs/viewer.md, docs/otlp-export.md
--- slice 4 only ---
src/hyphae/store/enrichment.py, src/hyphae/models/items.py, src/hyphae/enrich/prompts.py, tests/enrich/…, docs/enrichment.md
```

## Key contracts

**Record model.** `attachment` joins `RecordType`, serviced by a single model: `AttachmentRecord(SessionContext)`. Its envelope models `rendered` and `renderedInHumanTurn` as `list[dict] | None`—each item shaped as `{"content": str}`, present from version 2.1.259 and cited using the fixtures below alongside `Cited(absent=…)`. The `attachment` field uses `QueuedCommand | dict[str, Any]`, discriminated on `attachment.type` so that invalid `queued_command` payloads raise validation errors rather than falling back to the dict branch. The dict branch safely handles the remaining 48 attachment variants as uninspected leaves, identical to `ArchivedRecord` today. This avoids a second-level dispatch and keeps `kind_of`, `model_for`, `carries()`, `REGISTERED`, and `field_tables.spell` unchanged. `ARCHIVED_UNREAD` removes `attachment` by construction, and `test_a_kind_borrowed_from_the_other_registry_is_unknown` switches to another archived type.

The `QueuedCommand(Described)` model specifies `type`, `prompt: str | list[TextBlock | ImageBlock]` (the list shape cited by scan: one record in 2.1.221), optional `commandMode: str | None` and `timestamp: … | None` (both omitted in the no-mode variant), `origin: Origin | None`, `source_uuid`, `isMeta`, and `imagePasteIds`. To cover origins, `Origin(Described)` models every key observed in store carriers—`kind`, peer metadata (`body`, `from`, `name`, `senderTaskId`, `fromMode`, `hopChain`, `msg_id`, `verifiedPeerPid`), and `handback` from `user` records—backed by scan citations. Migration updates `UserRecord.origin` from `dict[str, Any]` to this shared model, retiring the "declared as a dict" test leaf in `tests/extract/test_records.py`. We introduce no new `OPAQUE` model, leaving `test_exactly_two_models_stop_the_walk_and_each_says_why` intact.

**When the schema moves.** The model preserves `commandMode` and `origin.kind` as raw source strings; readers perform the mapping. In `_interjections`, `Sender` resolves via the `required` path: `task-notification` maps to `TASK` (origin is always absent); otherwise it inspects `required(origin).kind`, mapping `human` to `PERSON`, and `coordinator` or `peer` to `AGENT`. Any unhandled value raises an `ExtractionError` that cites the session, line number, and value. Under `pipeline.py`, this fails only that specific session and records it in the extraction summary while `refresh` proceeds; resolving the failure requires a one-line enum update and an extractor re-run, guaranteeing no records are stored under an incorrect sender. Any newly introduced attachment kinds route to the dict fallback and archive cleanly — until the canonical-model stack replaces that arm with a closed registry, which is its decision, not this ticket's.

**Entity.** We define `Interjection` in `models/trace.py`: `id` (the attachment record's own `uuid`, which every queued_command carries, and the id the canonical-model stack's `harness_messages` row will share), `session_id`, `source`, `turn_id: str | None`, `timestamp` (the envelope timestamp—typed-at when `attachment.timestamp` exists, delivered-at for no-mode payloads), `sender: Sender`, `text`, and `replayed`. When `attachment.prompt` is a string, `text` holds it in full; the parser flattens content block lists into text blocks joined by blank lines, substituting `[image]` for image blocks so the single image record remains readable. The primary key is `(session_id, source, id)`, unique once `resolve_duplicates` has collapsed the nine in-file rewinds, ordered `(source, id)` in `TABLES`; the text stays inline (the stack's `texts` table can take it later); `LiveRows.interjections` supplies the `live_`/`corpus_` pair. We omit the `rendered` payload from storage, as `raw_records` preserves it.

**Store.** `SCHEMA_VERSION = 11`; migration 10→11 defines the table with inlined DDL (`schema.py` imports nothing from `hyphae`, following the 9→10 pattern). This migration lands first; the canonical-model stack numbers its own after it and rebases onto this one. There is no data back-fill (unlike migration 8→9); rows populate through a re-extract triggered across all on-disk transcripts by the `EXTRACTOR_VERSION` bump. The re-extract misses only 4 records across 2 sessions that Claude Code has pruned from disk, retaining 1,223 of the 1,227 total records. `tests/store/test_schema.py` updates the trace DDL digest, and the LiveRows→TABLES test leaf adds parametrization for the new field.

**Viewer.** Rendered strictly on the turn page mount (`markup/page.py`) in a new "Mid-turn messages" section positioned between the facts block and the children log. Each row displays the sender, timestamp, and text truncated to `INTERJECTIONS.text_chars` via the `cut` macro and `format.cut`. The section uses a fixed row budget matching the header PR list: the query fetches up to nine rows (first eight by file order plus one lookahead), rendering an overflow label ("+N more") via `library.dropped` if the ninth row exists. While human and agent interjections peak at 3 per turn, task notifications reach up to 41 (p99 of 28), making the cap essential. No URL knob, NavTree entry, new `Kind`, interactive expansion, or `Detail` view is added; full payloads remain one click away on the Records page. Records with `NULL` turns (13 task notifications) appear only on the Records page, as the thread's Unattributed bucket renders only when an API call lacks an enclosing turn (`nav_tree.py:unattributed`). `tests/view/budgets.py` allocates the byte budget for eight rows at `text_chars` against `NODE_BYTES`.

**Enrichment (slice 4).** `render_turn` and `render_run` print each interjection directly below the prompt under a heading identifying its sender. `PERSON` and `AGENT` text is capped at the width the prompt already gets. It caps `TASK` interjections at 400 characters, retaining the `<task-id>`, `<summary>`, and `<status>` tags (the `<status>` tag consistently closes by character 340) while discarding the verbose result payload. We retain task notifications because failed or killed background executions leave no other trace: the initiating tool call returns only an initial launch confirmation with `is_error=False`. Because `input_hash` covers rendered text, only items containing interjections go stale: at most 116 person/agent records across 65 sessions and 1,111 task notifications across 108 sessions. The `prompt_version` remains untouched, as instructions are unaltered.

**OTLP.** We exclude OTLP export from this ticket. Because `otlp.py` uses explicit table mappings, the exporter ignores the unmapped table without extra feature flags; `docs/otlp-export.md` documents the omission. The `EXTRACTOR_VERSION` bump will invalidate existing session fingerprints, causing the subsequent run to re-export all on-disk sessions under existing span IDs—standard behavior for extractor version increments (`docs/otlp-export.md`).

## Chosen test seam

Two trimmed, redacted fixtures under `tests/fixtures/interjection/`, with their Claude Code versions recorded in the README, validate against current models without undeclared fields or unknown kinds:

- `main` of session `27a459ba-1251-4b25-8a3a-66cb888223b5` (2.1.220, 2026-07-27, mac_settings, 199 lines, one thread, three turns): contains a `prompt`-mode record with `origin.kind = human` at line 119. It predates the introduction of `rendered`, covering the `Cited(absent=…)` branch. It sits outside mycelia, leaving the mycelia-scoped pins in `tests/analyze/conftest.py` (`MYCELIA_SESSIONS`, `WEEKS`, `POOL_AT_*`, `IN_WINDOW_AT_*`) untouched; slice 1 confirms this by building the store.
- Thread `aaceab3ee53af97d8` of session `af7e1907-fa0b-42b2-a8b2-9eea773aa7a6` (2.1.259, 2026-09-06, factory, 418 lines, one turn): contains an un-moded coordinator record at line 312 and task notifications at lines 184, 252, 289, and 330. All carry `rendered`, and the task notifications include `renderedInHumanTurn`. The fixture is trimmed to the initial turn prompt, the coordinator message, two task notifications, the parent `Agent` call with its result from `main`, and the thread's `.meta.json` (reflecting the `spine/` and `teammate/` file layout). Belonging to factory data, it impacts no analyze assertions.

Both files match the `corpus_transcripts` glob, allowing schema tests in `tests/extract/test_records.py` to reference them while `UnknownFields` guards completeness. The block-list `prompt` shape is verified via scan citations; its source record contains a base64-encoded image and is omitted from fixtures.

Individual contract test leaves verify each requirement directly. Parsing tests cover sender resolution across shapes, file-order `turn_id` attribution including pre-prompt `NULL` values, block-list flattening via a labeled synthetic line, and duplicate UUID `replayed` flags via an annotated duplicated fixture line. Additional leaves check single-session error containment on an unexpected `origin.kind`, `TraceReader` store roundtrips, and migration 10→11 execution on a v10 file with schema digest updates. View tests in `tests/view/scenarios.py` assert on `data-interjection` markup and the "+N more" overflow state, while slice 4 adds a golden regression test that fails if `render_turn` omits interjections. The live census (`HYPHAE_LIVE_STORE`) serves as a manual check to ensure all production fields are accounted for; CI coverage relies on the fixture tests.

## Slices

1. Records: registry update, `AttachmentRecord`, shared `Origin` model, test fixtures, and `docs/schema.md` cog. Validate against live store census.
2. Core pipeline: `Interjection` entity, `_interjections` parser, store DDL, migration, reader roundtrip, `EXTRACTOR_VERSION` increment, glossary updates, `docs/store.md`, and OTLP documentation note.
3. UI presentation: turn page view section, test scenario, layout bounds, and byte budgets.
4. Enrichment integration: prompt rendering and item updates; document invalidation impacts in `docs/enrichment.md` (contingent on Nathaniel's sign-off).
5. User records: read the `isMeta` + `origin` spelling of the same channel (1,068 records on agent threads, 2.1.195–2.1.267) into the same `Interjection`, under the lead-line rules in `docs/transcript-reading.md`, and increment `EXTRACTOR_VERSION`. No schema change.

Slices 3 and 4 are decoupled from each other; both depend on slice 2, as slice 5 does.

## Decisions

**One `AttachmentRecord` with a discriminated `attachment` field, not a second-level dispatch.** Implementing `attachment/<type>` identically to `system/<subtype>` would alter `Record.SUBTYPE`, establish a third archived category, and modify `kind_of`, `model_for`, `REGISTERED`, `carries()`, and `field_tables.spell`. That approach would force either a 49-variant `AttachmentType` registry or custom dispatch branches. Using a discriminated union models the single variant HP-26 requires while leaving the other 48 variants uninspected—matching existing behavior with zero regressions. The canonical-model stack will close the registry over every attachment kind after this lands, and `QueuedCommand` and `Origin` carry over into it unchanged, so the union is the smaller first step rather than a stance against the registry.

**Strings on the model, `Sender` in the reader.** Using strict `CommandMode`/`OriginKind` enums directly in the record model would reject an entire session during ingestion due to an unfamiliar value that only the interjection parser inspects. Deferring this mapping to `_interjections` matches `.claude/rules/python.md` guidance for consumer-specific fields while maintaining an identical blast radius of one session.

**Declare `Origin` whole and share it with `UserRecord`, not a third `OPAQUE` model.** We pin the opaque set at two. Reading an untyped dictionary via `.get("kind")` would bypass `DICT_READ` checks but violates the convention of accessing records through typed models. Modeling ten validated keys with scan citations is the preferred trade-off.

**Three senders, not two.** Merging into a binary `user`/`notification` enum would misattribute 36 coordinator- and peer-originated messages to human operators, contradicting both `origin.kind` and the transcript wrapper text. Storing raw `origin.kind` and `commandMode` strings and requiring consumers to derive them was rejected, as it would duplicate mapping logic across three call sites.

**`turn_id` by file order, not timestamp.** Transcript order reflects the sequence presented to the language model and matches `ApiCall` attribution. The 18 records where the two rules split were delivered under a different prompt from the one open when they were typed. The timestamp column is retained with documentation explaining both semantics.

**A section on the turn page, not a NavTree node.** Creating a compaction-style tree node would demand a `KindSpec`, header query, breadcrumb trail, integration scenario, and NavTree byte overhead for an unopenable row. A dedicated page section requires a single read and render pass, providing the exact view that a future tree node would point to.

**A fixed row count, not a knob.** Adding an interactive URL toggle incurs state management overhead across every rendered link. An eight-row display with an overflow indicator ("+N more") accommodates every known human and agent interaction while signaling high-volume task-notification spikes without flooding the layout with up to 41 rows.

**Store `attachment.prompt` whole; flatten a block list to text.** Truncating during the extraction step would leave `raw_records` as the only text-searchable source. Content block lists substitute `[image]` placeholders to keep the `text` column pure string data; raw blocks remain intact in `raw_records`.

**Task notifications in the render, capped (slice 4).** Omitting notifications conceals the only record of crashed or killed background tasks. Rendering them completely consumes up to 30,889 characters for a single payload. A 400-character cap preserves the task identifier, summary, and terminal status while dropping the verbose task output.

**Not an OTLP span in this ticket.** While generating a zero-duration child span under the turn (mirroring `_compaction_span`) requires minimal code, the exporter ships no transcript text by default (`docs/otlp-export.md`), and shipping interjection text is a policy decision the ticket does not ask for.

## Out of scope

- The queue journal: `queue-operation` records (8,719 enqueues across 1,325 sessions, along with dequeue, remove, and popAll actions) trace queue timestamps and payloads without envelope UUIDs, and remain archived. Since 81 of the 83 `prompt`-mode messages align with an enqueue entry in the same session, this journal provides queue latency rather than missing user text, and is deferred to a future ticket.
- `main`'s 3,578 task notices written as `user` records without `isMeta`, and the 32 peer messages to an idle session: neither is mid-turn, so both belong to the turn model rather than to interjections.
- Exhaustive schema coverage for the remaining 48 attachment types: the canonical-model stack owns that registry and lands it after this ticket.
- Rendering inline images from mid-turn content blocks: image blocks are extracted and marked inline, but not rendered as image assets.
- Exporting mid-turn records over OTLP spans.

## Decisions for Nathaniel

1. **Slice 4 (enrichment).** Extends beyond core scope and triggers re-enrichment across all items containing any of the 1,227 records (affecting 108 sessions with task notifications and 65 with human or agent messages). Recommendation: adopt slice 4, including all three senders and the 400-character cap on task notifications. Mid-turn corrections capture critical prompt evolution, and aborted tasks leave no other trace in the trace log.
2. **The user-record interjections.** Decided: slice 5, with the 371 task notices written the same way, and with coordinator and peer both `Sender.AGENT`.

## Open questions

1. For enrichment rendering, should the `Sender` header distinguish between "the coordinator" and "another session", or label both as "an agent"? The row does not keep `Origin.kind`: the extractor folds coordinator and peer into `Sender.AGENT` (`extract/parse.py:_SENDERS`), and `interjections` stores only the sender. Telling them apart takes a new `Sender` value, an `EXTRACTOR_VERSION` bump and a re-extract, not just an edit to `prompts.py`.
2. Exact primitive types for `Origin` attributes will be finalized from live store census distributions (`json_type` checks per key: strings, one array, one integer); slice 1 will codify the observed types.

## Glossary changes

- **Interjection** — a message delivered to the model while a turn was already running: what the person typed mid-turn, what a coordinator or peer sent a running agent, or a task's completion notice; keyed to the turn that was open where it landed in the transcript
- **Sender** — who an interjection came from: person, agent, or task
