# `interjection/` — messages delivered while a turn was running

This test fixture is a redacted excerpt of `27a459ba-1251-4b25-8a3a-66cb888223b5.jsonl`, recorded with **Claude Code 2.1.220** on 2026-07-27 in `~/.claude/projects/-Users-nob-repos-mac-settings/`.

The fixture retains host lines 5, 18, 61, 63, 65–68, 115–116, 119–122, 175–176, and 195–196 out of 199 total lines, and inserts two **borrowed** records (below). This yields three turns containing three queued commands, each attributed differently:

- A task notification written before the first prompt, belonging to no turn
- A message the person typed while the second turn was actively running (host line 119, the original session's sole queued command)
- A pasted image with accompanying text, queued during the third turn

Because the host session ran in `mac_settings` rather than the mycelia project filtered by the analyze tier, adding this fixture does not move any analyze pins. However, it still contributes to corpus-wide totals, including the project list and the planted-enrichment cycle in `tests/view/scenarios.py:DESCRIBED_TURN`.

## The factory session: every sender, on main and in an agent run

`af7e1907-fa0b-42b2-a8b2-9eea773aa7a6.jsonl` contains a redacted excerpt of a session from `~/.claude/projects/-Users-nob-repos-factory/`. Recorded on 2026-09-07 with **Claude Code 2.1.259** and later resumed under **2.1.263**, it preserves host lines 1, 8, 165, 277, 278, 416, and 543 out of 3,671, plus one borrowed record appended at the end:

- Lines 8 and 416 open the session's two turns.
- Line 165 contains an 839-character task notification, exceeding the enrichment prompt's 400-character cap.
- Lines 277 and 278 capture the `Agent` invocation that spawned the subagent run below, along with its result.
- Line 543 records a message the person typed during the second turn.

Its companion subagent log, `subagents/agent-aaceab3ee53af97d8.jsonl`, retains lines 1, 182–184, 312, 330, and 418 of that run's 418 total lines. Across its single turn, it receives messages from two tasks interleaved with a message from its coordinator (line 312, featuring `origin.kind: "coordinator"` and no `attachment.timestamp`). The adjacent `.meta.json` file is complete, apart from a redacted `description`.

## The writer session: a notice filed by where it sits

`1d58565d-b635-46e0-bb78-4a64a8eecf1a.jsonl` provides a redacted excerpt from `~/.claude/projects/-Users-nob-repos-writer/`, recorded on 2026-09-17 using **Claude Code 2.1.267**. The excerpt retains host lines 2, 1482, 1483, 1493, and 1515 out of 1,638 total lines: a `/compact` command, its output, the subsequent prompt, and a task notification. Although the task notice bears a timestamp of 15:53:42 (placing it chronologically within the `/compact` turn), the file records it after the 15:54:26 prompt, assigning it to the prompt's turn.

The assistant records that originally sat between the prompt and the notification were omitted because 2.1.267 writes fields on them that no record model declares yet.

## The relayed session: every sender as a `user` record

Besides the `queued_command` attachment, Claude Code writes a mid-turn message to an agent run as a `user` record with `isMeta: true`, an `origin`, and a fixed first line naming the sender. Agent runs on disk carry this spelling from 2.1.195 through 2.1.280 (scanned 2026-09-25). `bccd8048-2f6d-42f0-a221-b072563afbc1.jsonl` is a redacted excerpt of a session from `~/.claude/projects/-Users-nob-repos-hyphae/`, recorded on 2026-08-26 with **Claude Code 2.1.221** while the project still lived at `/Users/nob/repos/aiobserve`. It keeps host lines 1, 7, 215, 216 and 253 out of 378:

- Line 7 opens the session's one turn, the `/manager` command.
- Lines 215 and 216 hold the `Agent` call that spawned the implementer run below, and its result.
- Line 253 is a message another session wrote into this one after its work had stopped. Its first line is `Another Claude session sent a message:`, without the mid-turn lead's `while you were working`.

Its subagent log `subagents/agent-ae43615953608c70b.jsonl` keeps lines 1, 23, 25, 74, 102 and 189 of that run's 189, plus two borrowed records between 102 and 189. The run's one turn hears a task notice (74), its coordinator (102), the person (borrowed), and a second task (borrowed) whose event and finish arrived as two notices in one message. That record replaces line 185, a single notice. Lines 23 and 25 hold the `Agent` call that spawned the doc-writer run nested under it, and its result.

`subagents/agent-a0621f9014147e13c.jsonl` keeps lines 1, 131 and 141 of the nested run's 141: its instruction, a message from another session (line 131, `origin.senderTaskId` naming the implementer run), and its closing reply. Its `.meta.json` carries `parentAgentId` and `spawnDepth: 2`. Both `.meta.json` files are complete apart from a redacted `description`.

Each of these messages keeps Claude Code's own text whole: the first line, and the advice paragraph after the sender's words, such as `Address this before completing your current task.`. A task notice keeps its `[SYSTEM NOTIFICATION - NOT USER INPUT]` preamble. The sender's own words are `[redacted]`, and on a peer's message so are `origin.body`, `origin.from` and `origin.name`, and the `from` attribute of the `<agent-message>` wrapper that repeats it. Every host record keeps the `parentUuid` it was recorded with, so most point at a dropped line.

## Pruned records and dangling references

The excerpt strips all `task_reminder` attachments, bookkeeping entries (`mode`, `permission-mode`, `bridge-session`, `last-prompt`, `ai-title`, and `file-history-*`), and all but one of the 26 `output_style` attachments (preserving only the attachment directly following the queued command).

The two `Write` invocations between the second prompt and its queued command were also dropped. Because turn attribution relies on file order rather than `parentUuid`, the queued command's `parentUuid` still references the dropped tool result. This dangling reference is an intentional design choice of the trimmed fixture.

## Borrowed records

The borrowed records follow the same redaction pattern as the host. Their `sessionId`, `session_id`, `cwd`, and `gitBranch` fields were updated to match the host session, and their envelope and attachment timestamps were shifted into the host session's time window.

| Record | Source | CC version | Shape it carries |
| --- | --- | --- | --- |
| Task notification (line 1) | `e684d4da-e05b-49a4-b91e-2c409568a934` line 6, mycelia | 2.1.220 | A `task-notification` queued prior to the session's first prompt, containing no `origin`. Its `parentUuid` is set to null, and `forkedFrom` is dropped. |
| Block-list prompt (line 18) | `480206e4-d851-460a-8770-7d8a7bda290e` line 62, hyphae | 2.1.221 | The only recorded queued command whose `prompt` is a list: a `text` block and an `image` block, beside `imagePasteIds`. Its `parentUuid` is rechained to the third prompt. |
| Peer message (`af7e1907` line 8) | `dc22318a-c21f-4c29-bfa7-547fc2ec771d` line 244, factory | 2.1.259 | A message another session wrote into this one: `commandMode: "prompt"`, as the person's is, with `origin.kind: "peer"`. `origin.name` is redacted, `parentUuid` is rechained to line 543, and both timestamps are set to 2026-09-07T13:49:58.000Z. |
| Person's message (`bccd8048`'s implementer run, line 6) | `19d449bf-c39f-4fdb-8e2b-96f76e6f2f0f` `subagents/agent-a83050fa56493a5fa.jsonl` line 856, hyphae | 2.1.221 | A message the person typed into a running agent: an `isMeta` `user` record with `origin.kind: "human"` and the lead `The user sent a new message while you were working:`. Its `agentId` and `slug` were rewritten to the host run's too, `parentUuid` is rechained to the coordinator's message before it, and the timestamp is set to 2026-08-26T19:25:00.000Z. |
| Two task notices in one message (`bccd8048`'s implementer run, line 7) | `ea5d66b4-0c9b-4f18-8a47-6cc1246f4ca7` `subagents/agent-aab8052e8edb0b308.jsonl` line 231, hyphae | 2.1.221 | One `isMeta` `user` record under the task lead that carries two `<task-notification>` blocks: an `<event>` the task reported, then the same task's finish. 28 of the 371 recorded task notices written as `user` records carry more than one (scanned 2026-09-25). Its `agentId` and `slug` were rewritten to the host run's, `parentUuid` is rechained to the person's message before it, and the timestamp is set to line 185's, 2026-08-26T19:32:22.984Z. `<event>` is redacted like `<summary>`. |

## Redaction rules

Every string omitted from the structural allowlist is replaced with `[redacted]`, and `gitBranch` is pseudonymised as `fixture-branch-N`.

Key structural and attribution metadata are preserved:

- `commandMode` and `origin.kind` remain intact to identify message senders.
- The image block keeps its original `media_type`, while its `data` is redacted.
- The task notification retains its leaf tag structure. Text within each leaf tag is replaced with `[redacted]` padding matching the recorded character count. Identifiers, status values, and usage numbers are preserved unchanged, ensuring the prompt length matches the original recording.
