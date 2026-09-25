# Attachment records

The fields of an `attachment` record, what each means, and the recording that proves it. Claude Code writes an `attachment` record to inject context alongside a turn; hyphae reads only attachments carrying messages delivered while a turn was actively running.

This table is generated using the same process as the tables in [the telemetry schema](schema.md), and follows the same recording citation rules.

## Queued commands and unmodeled attachments

Hyphae models `queued_command` attachments field by field. It preserves all other attachment kinds intact as raw dicts, which remain unread.

<!-- aigarden:cog sh "uv run python -m tools.gen_schema attachments" -->
| Field | Records | Meaning | Evidence |
| --- | --- | --- | --- |
| `attachment` | `attachment` | What was attached, dispatched on its `type`. Only a `queued_command` is modelled; the other kinds are kept whole and read by nothing | `tests/fixtures/interjection/`, CC 2.1.220 — a queued command and an `output_style` |
| `attachment.type` | `attachment` | The attachment kind | `tests/fixtures/interjection/`, CC 2.1.220 |
| `attachment.prompt` | `attachment` | The message whole. One corpus prompt is a list of blocks, a `text` beside an `image`; every other is a string | `tests/fixtures/interjection/`, CC 2.1.220 |
| `attachment.prompt.text` | `attachment` | Prose in a block-form queued prompt | `tests/fixtures/interjection/`, CC 2.1.221 |
| `attachment.prompt.text.text` | `attachment` | What the person typed beside the picture | `tests/fixtures/interjection/`, CC 2.1.221 |
| `attachment.prompt.image` | `attachment` | A picture pasted into a queued prompt | `tests/fixtures/interjection/`, CC 2.1.221 — its `data` redacted |
| `attachment.prompt.image.source` | `attachment` | The picture itself, as a `type`, a `media_type` and base64 `data`. Nothing has opened it | `tests/fixtures/interjection/`, CC 2.1.221 — its `data` redacted |
| `attachment.commandMode` | `attachment` | `prompt` for a message someone typed, `task-notification` for a task's notice. A coordinator's message omits it | `tests/fixtures/interjection/`, CC 2.1.220 — both values |
| `attachment.timestamp` | `attachment` | When the message was queued. Every fixture record repeats it as its own timestamp, even a notice written 48 seconds later, in the next turn. Omitted where `commandMode` is | `tests/fixtures/interjection/`, CC 2.1.220; `tests/fixtures/interjection/`, CC 2.1.267 — the notice that waited |
| `attachment.origin` | `attachment` | Who sent it. A task's notice carries none, since `commandMode` says so | `tests/fixtures/interjection/`, CC 2.1.220 |
| `attachment.origin.kind` | `attachment` | The sender, as `human`, `coordinator` or `peer` on a queued command. A `user` record also writes `task-notification` (3,949 records) and `auto-continuation` (1) | `tests/fixtures/interjection/`, CC 2.1.220 — `human`, on a prompt and on a queued command |
| `attachment.origin.body` | `attachment` | What the peer sent. It is part of the text the message delivered | corpus scan: the canonical store, 86,166 `attachment` records in 1,469 sessions, scanned 2026-09-25 — peer messages only |
| `attachment.origin.from` | `attachment` | The peer's address: an agent name, an agent id, or a `uds:` socket path | corpus scan: the canonical store, 86,166 `attachment` records in 1,469 sessions, scanned 2026-09-25 — peer messages only |
| `attachment.origin.name` | `attachment` | The peer's display name. It usually repeats `from`; 3 `user` records omit it | corpus scan: the canonical store, 86,166 `attachment` records in 1,469 sessions, scanned 2026-09-25 — peer messages only |
| `attachment.origin.senderTaskId` | `attachment` | The id of the task the peer was running | corpus scan: the canonical store, 86,166 `attachment` records in 1,469 sessions, scanned 2026-09-25 — peer messages only |
| `attachment.origin.fromMode` | `attachment` | A mode the peer ran in. All three recorded values are `bypass` | corpus scan: the canonical store, 86,166 `attachment` records in 1,469 sessions, scanned 2026-09-25 — only `2.1.259` writes it |
| `attachment.origin.hopChain` | `attachment` | The relays a message passed through. One queued command carries it | corpus scan: the canonical store, 86,166 `attachment` records in 1,469 sessions, scanned 2026-09-25 — only `2.1.259` writes it |
| `attachment.origin.msg_id` | `attachment` | The message's own id, a uuid | corpus scan: the canonical store, 86,166 `attachment` records in 1,469 sessions, scanned 2026-09-25 — only `2.1.259` writes it |
| `attachment.origin.verifiedPeerPid` | `attachment` | The process id Claude Code confirmed the peer runs as | corpus scan: the canonical store, 86,166 `attachment` records in 1,469 sessions, scanned 2026-09-25 — only `2.1.259` writes it |
| `attachment.origin.handback` | `attachment` | A flag recorded once, as true, on a `user` record. What it changes is unrecorded | corpus scan: the canonical store, 86,166 `attachment` records in 1,469 sessions, scanned 2026-09-25 — only `2.1.280` writes it |
| `attachment.source_uuid` | `attachment` | A uuid on 56 of 1,227 queued commands that matches no record of its session, so what it names is unknown | corpus scan: the canonical store, 86,166 `attachment` records in 1,469 sessions, scanned 2026-09-25 — `2.1.206`–`2.1.280`; `tests/fixtures/interjection/`, CC 2.1.263 |
| `attachment.isMeta` | `attachment` | Always true where present, on 35 queued commands, nearly all a coordinator's or a peer's. What it changes is unrecorded | corpus scan: the canonical store, 86,166 `attachment` records in 1,469 sessions, scanned 2026-09-25; `tests/fixtures/interjection/`, CC 2.1.259 — a coordinator's and a peer's |
| `attachment.imagePasteIds` | `attachment` | The images pasted into the message, by id | `tests/fixtures/interjection/`, CC 2.1.221 |
| `rendered` | `attachment` | What Claude Code showed the model for the attachment, as a list of `content` objects. Nothing has opened it. Claude Code added it in `2.1.259` | corpus scan: the canonical store, 86,166 `attachment` records in 1,469 sessions, scanned 2026-09-25 — 48,753 records; `tests/fixtures/interjection/`, CC 2.1.259; absent from `tests/fixtures/interjection/`, CC 2.1.220 |
| `renderedInHumanTurn` | `attachment` | The same, as shown inside the person's turn. Only queued commands carry it. Nothing has opened it | corpus scan: the canonical store, 86,166 `attachment` records in 1,469 sessions, scanned 2026-09-25 — 749 records, from `2.1.259`; `tests/fixtures/interjection/`, CC 2.1.259 — task notices only; absent from `tests/fixtures/interjection/`, CC 2.1.220 |
<!-- aigarden:end -->
