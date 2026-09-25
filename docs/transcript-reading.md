# Reading transcript records

Read a Claude Code transcript by these rules: which `user` records start a turn, where a slash command's output went, which turn a mid-turn message belongs to, and which timestamps were measured rather than assigned.

[The schema reference](schema.md) says what each field is. This document says what the fields mean together, which is where a query goes wrong without ever looking wrong.

## A leading tag distinguishes prompts from other records

When a `user` record contains a string, its leading XML-like tag often determines whether the record starts a turn.

- Count `<command-name>` and `<command-message>` as a turn. They mark a slash command, can appear in either order, and carry `<command-args>` beside them. The wrapper is the whole prompt: all 451 command turns in the canonical store hold the tags and nothing else, so a command turn's `prompt` says no more than its `command_name` and `command_args` do (scanned 2026-08-24)
- Count `<teammate-message>` as a turn
- Don't count `<task-notification>`, `<local-command-stdout>`, `<bash-input>`, or `<bash-stdout>`. Claude Code wrote these to itself

Counting every string-valued `user` record as a turn inflates the total several-fold. The mycelia corpus contains 2,157 `<task-notification>` records but 968 prompts ([trace-pipeline design](../plans/trace-pipeline/design.md)). The extractor crashes on an unregistered tag instead of guessing, because the next machine-written tag would silently inflate the count again.

Tags can carry attributes, as in `<teammate-message teammate_id="team-lead" summary="…">`. Parse the name only to the first whitespace or `>`. Keep the full opening tag in `Turn.prompt` because it identifies the sender. The 132 corpus `<teammate-message>` records all occur in subagent transcripts from one mycelia session, so a census of main transcripts misses them (scanned 2026-08-07).

*Evidence:* `tests/fixtures/spine/` contains both slash-command orderings at CC 2.1.221, `<bash-input>` and `<bash-stdout>` at CC 2.1.212, and `<teammate-message>` at CC 2.1.211.

## Attach slash-command output to the command turn

`<local-command-stdout>` does not start a turn. It records what a slash command printed, and its `parentUuid` points to the command turn. Many command turns produce no model reply, making this output the only record of what happened.

Claude Code writes the output in two shapes:

- A `user` record with the tag in `message.content`: 279 of 316 mycelia records
- A `system` record with `subtype: local_command` and the tag in `content`: the other 37

The text between the tags can span lines, so don't stop at the first line. It can also be empty. All 21 recorded `/clear` outputs are empty, compared with a median body length of 71 characters and a maximum of 2,038 (scanned 2026-08-13).

A resumed session can replay the same output under the plain turn that now precedes it. The corpus contains 183 such records. If `parentUuid` points to a turn that ran no command, the output has no owning turn in that thread; the archive is not malformed.

*Evidence:* `tests/fixtures/spine/`, CC 2.1.221, contains the `user` carrier; `tests/fixtures/model_only/`, CC 2.1.215, contains the `system` carrier and an empty `/clear` body; `tests/fixtures/resume_pair/`, CC 2.1.202, contains the replay.

## File a mid-turn message by where it sits

An `attachment` record whose `attachment.type` is `queued_command` carries a message Claude Code delivered while a turn was already running: what the person typed, what a coordinator or peer sent a running agent, or a background task's notice that it ended. It never starts a turn. It belongs to the turn open where the record sits in the file, the rule that places an api call, and one written before the thread's first prompt belongs to no turn. The extractor stores each as an interjection.

Don't place it by its timestamp. Where `attachment.timestamp` is present, the record's own timestamp repeats it, and both say when the message was queued rather than when the model read it. A message can wait out the rest of one turn and land in the next: 18 records in the canonical store fall on different turns under the two rules ([the mid-turn messages design](../plans/mid-turn-messages/design.md#decisions), scanned 2026-09-25). A coordinator's message omits `attachment.timestamp`, and its record timestamp is when it was delivered.

Tell the sender by `origin.kind`, not `commandMode`. A peer's message is `prompt`-mode like the person's, and a coordinator's has no mode at all. Only a task's notice is told by its mode, `task-notification`, because it carries no `origin`. The extractor refuses a session holding an `origin.kind` it has not seen.

Only this carrier is read. The 706 `user` records that wrap a coordinator's or peer's message in `isMeta` markup start no turn and are not yet interjections either (the design's out-of-scope list).

*Evidence:* `tests/fixtures/interjection/`, CC 2.1.220, contains a notice before the first prompt and a message the person typed mid-turn; CC 2.1.259 contains a coordinator's message without `attachment.timestamp`; CC 2.1.267 contains a notice queued during one turn and filed under the next.

## Start parallel local calls at the batch's first timestamp

One assistant message can issue several local tool calls at once. Claude Code usually writes one record per call in execution order, so calls issued together receive different timestamps. Only 156 of 23,371 multi-call messages in the mycelia corpus use one timestamp for the whole batch (scanned 2026-08-07). Treating each record timestamp as its call's start mistakes queue position for duration.

Start every call in such a batch at the earliest record timestamp and set `ToolCall.duration_synthetic` to show that the start was assigned rather than measured. A lone call keeps its own timestamp and sets the flag to false.

Define the batch by records, not calls. One record can contain several `tool_use` blocks; those calls were issued together and keep their shared, measured record timestamp. Counting blocks would mark that real start as synthetic.

*Evidence:* `tests/fixtures/spine/`, CC 2.1.221, contains three calls under `msg_011CdmMjFXDofyYSMxYtXa5n`; `tests/fixtures/parallel_tools/`, CC 2.1.211, contains one message of each shape.

## Time a server-side call from its own record

A `server_tool_use` shares the assistant stream with local calls but does not join their batch. Claude Code did not execute it, so its record marks the request rather than a queue position. Keep that timestamp, set `duration_synthetic` to false, and end the call when Claude Code writes the `advisor_tool_result` in the same message.

Store the call in `tool_calls` with `server_side` set. Before the extractor registered this block, it produced no row, text, or crash; sessions that used the advisor looked as though they had not.

*Evidence:* `tests/fixtures/server_tools/`, CC 2.1.201, contains a subagent message with two local calls and one server-side call.

## Keep the last record when a uuid repeats

Rewinding leaves both the old and new records under the same uuid. Their token usage differs. The extractor keeps the last record because it reflects the session's final state; keeping the first changes token totals in four mycelia sessions.

No recorded duplicate pair changes `message.content`. Such a change would mean that Claude Code rewrote the conversation itself, so the extractor crashes if it finds one.

*Evidence:* `tests/fixtures/dup_uuid/`, CC 2.1.211, contains five uuids twice each.

## Read compaction from the boundary record

Every `system` / `compact_boundary` record has a corresponding `user` record with `isCompactSummary`. The mycelia corpus contains 1,026 of each, with matching counts in every file (CC 2.1.191–2.1.221; scanned 2026-08-07).

Subagents compact much more often than main threads. Attribute a compaction to the file that reached the limit, not to the session as a whole.

*Evidence:* `tests/fixtures/compaction/`, CC 2.1.198, contains one `auto` and one `manual` boundary, each with its summary.

## Preserve both cache-creation totals

The total and the split disagree in 53 of about 290,000 mycelia assistant records, as [the `cache_creation` rows](schema.md#api-replies-models-and-tokens) record. The extractor stores the total as `cache_creation_tokens` and the split as `cache_5m_tokens` and `cache_1h_tokens`. Cost uses the split when present, so those 53 calls use a value that the total does not confirm.

## Split records only on newline characters

String values can contain raw U+2028 and U+2029 separators. Python's `splitlines()` treats them as record boundaries and breaks JSON objects. Split transcript files on `"\n"`.
