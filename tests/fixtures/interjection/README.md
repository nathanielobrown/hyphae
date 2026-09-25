# `interjection/` — messages delivered while a turn was running

This test fixture is a redacted excerpt of `27a459ba-1251-4b25-8a3a-66cb888223b5.jsonl`, recorded with **Claude Code 2.1.220** on 2026-07-27 in `~/.claude/projects/-Users-nob-repos-mac-settings/`.

The fixture retains host lines 5, 18, 61, 63, 65–68, 115–116, 119–122, 175–176, and 195–196 out of 199 total lines, and inserts two **borrowed** records. This yields three turns containing three queued commands, each attributed differently:

- A task notification written before the first prompt, belonging to no turn
- A message the person typed while the second turn was actively running (host line 119, the original session's sole queued command)
- A pasted image with accompanying text, queued during the third turn

Because the host session ran in `mac_settings` rather than the mycelia project filtered by the analyze tier, adding this fixture does not move any analyze pins. However, it still contributes to corpus-wide totals, including the project list and the planted-enrichment cycle in `tests/view/scenarios.py:DESCRIBED_TURN`.

## Pruned records and dangling references

The excerpt strips all `task_reminder` attachments, bookkeeping entries (`mode`, `permission-mode`, `bridge-session`, `last-prompt`, `ai-title`, and `file-history-*`), and all but one of the 26 `output_style` attachments (preserving only the attachment directly following the queued command).

The two `Write` invocations between the second prompt and its queued command were also dropped. Because turn attribution relies on file order rather than `parentUuid`, the queued command's `parentUuid` still references the dropped tool result. This dangling reference is an intentional design choice of the trimmed fixture.

## Borrowed records

The two borrowed records follow the same redaction pattern as the host. Their `sessionId`, `session_id`, `cwd`, and `gitBranch` fields were updated to match the host session, and their envelope and attachment timestamps were shifted into the host session's time window.

| Record | Source | CC version | Shape it carries |
| --- | --- | --- | --- |
| Task notification (line 1) | `e684d4da-e05b-49a4-b91e-2c409568a934` line 6, mycelia | 2.1.220 | A `task-notification` queued prior to the session's first prompt, containing no `origin`. Its `parentUuid` is set to null, and `forkedFrom` is dropped. |
| Block-list prompt (line 18) | `480206e4-d851-460a-8770-7d8a7bda290e` line 62, hyphae | 2.1.221 | The only recorded queued command whose `prompt` is a list: a `text` block and an `image` block, beside `imagePasteIds`. Its `parentUuid` is rechained to the third prompt. |

## Redaction rules

Every string omitted from the structural allowlist is replaced with `[redacted]`, and `gitBranch` is pseudonymised as `fixture-branch-N`.

Key structural and attribution metadata are preserved:

- `commandMode` and `origin.kind` remain intact to identify message senders.
- The image block keeps its original `media_type`, while its `data` is redacted.
- The task notification retains its leaf tag structure. Text within each leaf tag is replaced with `[redacted]` padding matching the recorded character count. Identifiers, status values, and usage numbers are preserved unchanged, ensuring the prompt length matches the original recording.
