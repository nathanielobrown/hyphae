# Phase 1: the shape of a corpus-wide extract

What I found before asking (verified 2026-09-14, this machine):

- `~/.claude/projects` holds 253 project directories and 2,168 top-level transcripts, 3.8 GB. The store holds 641 sessions from about nine projects, all of them from `hp extract <path>` runs
- About 200 of those directories are scratch: `/private/tmp/claude-501/.../scratchpad-*` and `/private/var/folders/.../T/dogfood-*` working directories that mycelia's eval runs created and deleted. The biggest real ones are mycelia (577), mycelia/backend (349), two mycelia worktrees (243, 216), hyphae (68), mac_settings (42)
- A session's `project_dir` comes from the first record's `cwd`, not from the directory name. That matters because the directory name is lossy: Claude Code encodes `mac_settings` as `-Users-nob-repos-mac-settings`, and `hp sessions ~/repos/mac_settings` fails today because hyphae only replaces `/`. A corpus-wide walk never decodes a name, so it sidesteps that bug (which wants its own fix)
- `hp extract ~/repos/hyphae` halts today on an unknown system record subtype, `model_fallback`. The parser is closed-world by design; this is what a corpus-wide run will hit repeatedly at first
- `hp enrich` already has the "no project means everything" shape, but spelled as an optional `--project` flag. `sessions`, `extract`, and `export-otlp` take a required positional `project`
- The pipeline seam is `Extractor.sessions(project)`, implemented by the Claude Code extractor and by `StoreSource` (the store read back out for OTLP). `refresh()` loops over what `sessions()` returns and skips fingerprint matches; each session's export is atomic, so an interrupted or halted run resumes where it stopped

Decided without asking, because one answer is clearly right:

- Projects are walked in directory-name order, so two runs over the same disk do the same work in the same order
- An empty projects root raises, as a missing project directory does today: it is a mistyped `--projects-root`, not an empty corpus
- The seam becomes `sessions(project: Path | None)`, with `None` meaning every project. A separate `projects()` method would have to hand back paths, and the lossy directory encoding means the extractor cannot mint one from a directory name



## 1. Should a bare `hp extract` mean "every project", or should the corpus-wide run need an explicit flag?

Today `project` is a required positional argument. Making it optional is the smallest change and matches how you phrased the task. The alternative is an explicit `--all`, which guards against an accidental bare invocation kicking off a run over 2,168 sessions.


| Option              | Shape                                                  | Trade-off                                                       |
| ------------------- | ------------------------------------------------------ | --------------------------------------------------------------- |
| Optional positional | `hp extract` = all, `hp extract ~/repos/mycelia` = one | Smallest change; a bare command does a lot of work              |
| Explicit flag       | `hp extract --all`; bare `hp extract` errors           | Guards the accident; one more thing to type for the common case |
| Flag like enrich    | `hp extract --project ~/repos/mycelia`; bare = all     | Consistent with `hp enrich`; breaks every documented invocation |


Stakes: low. The run is idempotent and resumes, so an accidental corpus-wide extract costs minutes, not data. Reversible by editing one argparse line.

### Recommendation: optional positional

A bare command doing the whole corpus is the point of the change, and nothing bad happens when it runs by accident. We give up consistency with `hp enrich --project`; see the pending question on harmonizing that.

### User Response:



## 2. Which subcommands get the no-project form: `extract` alone, or `sessions` and `export-otlp` too?

`sessions` and `extract` share one argument-declaring function, so `sessions` inherits whatever `extract` does unless we split them. `export-otlp` has its own positional, but it drives the same `refresh()` seam through `StoreSource`, so the protocol change reaches it whether or not the CLI exposes it.


| Option                   | What changes                                                                                          | Trade-off                                                                                                   |
| ------------------------ | ----------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `extract` only           | Split the shared argument function; `StoreSource` gets a `None` branch it never receives from the CLI | Smallest CLI surface; a seam that half the callers cannot exercise                                          |
| `extract` and `sessions` | Shared argument function changes once; `hp sessions` lists the whole disk                             | Free once `extract` has it; `sessions` output over 2,168 rows needs a project column to be readable         |
| All three                | `export-otlp` ships the whole store to a backend when given no project                                | One consistent seam and CLI; a corpus-wide OTLP send is outward-facing and the biggest act any command does |


Stakes: medium. The seam is internal and easy to revisit. `export-otlp` without a project is the one that sends 641 sessions' spans somewhere the first time someone types it.

### Recommendation: all three

The protocol change makes `StoreSource` handle `None` anyway, and the delivery ledger already makes an OTLP send idempotent, so a corpus-wide send is a large first run and a small every run after. The cost is a wider diff and one more command whose bare form does a lot.

### User Response:



## 3. When one session in a corpus-wide run fails to parse, should the run halt or carry on and report at the end?

The parser and the layout walk are closed-world: an unknown record shape or an unplaceable file raises, and today that halts the run. Per-session atomicity means the store keeps every session extracted before the halt and a rerun skips them. Over 253 project directories spanning a year of Claude Code versions, the first corpus-wide run will halt several times: it halts on hyphae's own sessions right now.


| Option                                  | Behaviour                                                                           | Trade-off                                                                                                     |
| --------------------------------------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Halt (today)                            | Stop at the first failing session, say which project and session, exit non-zero     | Every completed run is a full-fidelity archive; the first run takes several fix-and-rerun cycles              |
| Carry on                                | Skip the failing session, keep going, print every failure at the end, exit non-zero | The corpus lands in one run; the store silently lacks the sessions that failed until someone reads the report |
| Carry on within a project, halt between | Finish the current project's other sessions, then stop                              | Splits the difference and is harder to explain than either                                                    |


Stakes: high, and it is a project value rather than a mechanism. "An absence is bounded or it isn't a finding": a store with holes nobody recorded cannot bound an absence. Reversible in code, but a store filled under "carry on" cannot tell you which sessions it is missing.

### Recommendation: halt

Closed-world parsing is how the schema documentation stays true, and fingerprint-based resume makes a halt cheap: fix the parser, rerun, and the run picks up in under a second of skipping. We give up the one-shot first extract and accept a few cycles of teaching the parser shapes it has not seen.

### User Response:



## 4. Should the walk take every directory under the projects root, including the ~200 scratch working directories mycelia's evals created and deleted?

Most of the projects root is temp directories that no longer exist on disk: `/private/tmp/claude-501/<uuid>-scratchpad-*` and `/private/var/folders/.../T/dogfood-*-repo`. Their transcripts are real Claude Code sessions, and they are exactly the sessions mycelia's eval analysis is about. But they would outnumber every real project on the viewer's projects page.


| Option               | Rule                                                       | Trade-off                                                                                               |
| -------------------- | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Everything           | Every directory under the root is a project                | The store is the archive; the projects page lists ~250 entries                                          |
| Skip vanished cwds   | Only directories whose recorded `cwd` still exists on disk | Drops the eval corpus, which is the analysis target; a deleted checkout of a real project also vanishes |
| Include/exclude flag | `--skip <glob>` or an allow-list                           | Puts judgment in the invocation; every run has to remember it                                           |


Stakes: medium. Extracting is additive and the analysis layer already scopes by project, so over-inclusion costs disk and a long projects page. Under-inclusion costs a corpus you would have to notice was missing.

### Recommendation: everything

The store is the archive and the viewer is where judgment about projects belongs. We give up a tidy projects page until it learns to fold scratch directories; see pending.

### User Response:



## 5. Should `--tag` be allowed on a run with no project?

A tag is a property of the extraction that says what the run was for, and a re-extract replaces a session's whole tag set. On a corpus-wide run, `--tag run_id=x` would stamp every changed session in every project with a tag meant for one experiment.

Allowing it is consistent: the flag means the same thing at every scope, and `docs/store.md` already warns that an untagged re-extract clears tags. Refusing it is a guard: a corpus-wide sweep is for nothing in particular, so a tag on it is almost always a mistake, and the refusal is one line.

Stakes: low. A mis-stamped tag set is repaired by the next targeted extract of a changed session, or by a `--tag` extract after touching the sessions.

### Recommendation: allow

The flag's meaning should not depend on which other arguments are present, and a legitimate corpus-wide tag exists (`machine=laptop`). We give up the guard against a broadcast `run_id`.

### User Response:



## Pending questions (depends on answers above)

- Should `hp enrich --project` become a positional like the other commands, or should nothing change? — depends on Q1
- Does the projects page need to fold scratch directories under the project that spawned them, or does a filter do? — depends on Q4
- Progress output: one summary line per project as it completes, or keep the single total line? — depends on Q3 (a halting run needs to say where it stopped) and Q2 (`hp sessions` over the whole disk needs a project column)
- Does `export-otlp`'s dry-run census break down by project when no project is given? — depends on Q2
- Does the README quickstart become a bare `hp extract`? — depends on Q1



# Phase 2: a remembered multi-select picker

Direction from chat on 2026-09-15: a bare `hp extract` opens a multi-select picker over the project directories, sorted by sessions active in the last seven days, pre-checked with whatever was chosen last time, and remembers the new choice. That answers Phase 1 Q1 (no sweep, no flag: a picker) and replaces Q2 and Q4 with Q8 and Q10 below. **Q3 (halt or carry on) and Q5 (**`--tag` **without a project) still stand; answer them in place.**

Library, settled by research rather than asked (checked 2026-09-15):


| Library          | Stars | Last push | Runtime deps              | Multi-select with type-to-filter                                                                         |
| ---------------- | ----- | --------- | ------------------------- | -------------------------------------------------------------------------------------------------------- |
| questionary      | 2,178 | 2026-08   | prompt_toolkit only       | Yes: `checkbox(use_search_filter=True)`, `Choice(checked=True)` for pre-selection, `description` per row |
| python-inquirer  | 1,138 | 2026-09   | blessed, editor, readchar | Checkbox, no filter                                                                                      |
| simple-term-menu | 568   | 2024-12   | none                      | Yes, but curses-style and quiet for two years                                                            |
| InquirerPy       | 479   | 2024-08   | prompt_toolkit, pfzy      | Fuzzy multi-select, unmaintained                                                                         |
| beaupy           | 240   | 2026-09   | rich, emoji, yakh, questo | Yes, four deps for a picker                                                                              |


questionary wins on every axis you named. It also has `a` to toggle all and `i` to invert, which a list of 250 rows wants.

Decided without asking, because one answer is clearly right:

- The positional becomes `project*`: zero paths opens the picker, one or more paths extracts those and skips it. The picker yields several projects, so the CLI path must be able to say the same thing
- Only the picker writes the remembered set. Explicit paths are one-offs and never clobber it
- A row's label is the `cwd` read from the directory's newest transcript, not the directory name: `-Users-nob-repos-mac-settings` is unreadable and lossy, `/Users/nob/repos/mac_settings` is the truth. A directory holding no transcript is not offered; there is nothing to extract
- "Active in the last seven days" is the count of top-level transcripts whose mtime is within seven days. A stat per file, no parsing. Rows sort by that count, then by total sessions, then by name. Each row prints both counts
- Confirming an empty selection aborts and leaves the remembered set alone
- Confirming rewrites the remembered set whole, so a remembered directory that vanished from disk drops out on the next confirm
- Once a selection is in hand, the run is a loop of today's single-project extract over it, printing one summary line per project



## 6. Where does the remembered selection live: a file beside the store in `~/.hyphae/`, or a table inside the trace store?

The store is the archive at `~/.hyphae/traces.duckdb`, and `--db` or `HP_DB` can point a run at another file. The remembered selection is a preference about this person on this machine, not a fact about any archive.

A file in `~/.hyphae/` (say `extract-projects.json`) is per person and per machine, survives deleting or rebuilding the store, and is readable and editable by hand. But a run with `--db data/scratch.duckdb` shares it, and the test suite needs a way to redirect it, as `HP_DB` does for the store today. A table in the store travels with the archive: a scratch store gets its own memory and the tests get isolation free. But it puts a UI preference in the thing every doc calls the archive, and `docs/store.md` would have to explain a table that holds no telemetry.

Stakes: low. The content is a list of directory names; wherever it lives, moving it later is a one-off.

### Recommendation: a file in `~/.hyphae/`

It is a preference and belongs with the person, not the archive. We give up free test isolation and take on one more redirection knob (an env var or a parameter the tests set).

### User Response:

Let's do ~/.hyphae/settings.json

## 7. What does the remembered set record for each project: the directory name under the projects root, or the `cwd` its transcripts recorded?

The walk finds directories; extraction reads a directory. The `cwd` is what a person recognizes and what every store query filters on. The two do not round-trip: Claude Code turns `/`, `_` and `.` into `-`, so a remembered `cwd` cannot be turned back into a directory name without walking the root and reading each directory's newest transcript again.

Recording the directory name means the picker can pre-check rows without reading a transcript, and extraction has exactly what it needs. Recording the `cwd` means a file a person can read (`/Users/nob/repos/mycelia`), and a set that stays valid if Claude Code ever changes its encoding, at the cost of one transcript read per directory before the picker can pre-check anything. The picker reads those anyway for its labels, so the cost is only paid on the scripted path that skips the picker.

Stakes: low and reversible; the file can be regenerated by opening the picker once.

### Recommendation: the directory name

It is the one identifier that reaches extraction without a lookup, and the scripted path (Q9) should not have to open 250 transcripts to find out what to extract. We give up a human-readable file.

### User Response:

The directory name

## 8. Should the picker list every directory flat, or fold a directory under the project whose path it extends?

253 rows: mycelia's sessions sit in four directories (`mycelia`, `mycelia/backend`, two `.claude/worktrees/...` checkouts), and about 200 rows are scratch under `/private/tmp` and `/private/var/folders`. The store's project filter already treats a path under a project as that project's, so a fold would match how queries count.


| Option                    | Rule                                                                                                                              | Trade-off                                                                                                                                      |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Flat, with type-to-filter | One row per directory; sort by activity sinks the scratch tail; typing `myc` narrows to mycelia's rows                            | Matches what a single `hp extract <path>` does today (one directory); four mycelia rows to check                                               |
| Fold by path prefix       | A row whose `cwd` starts with another row's `cwd` plus `/` nests under it, counts summed, selecting the parent takes the children | `/Users/nob/repos` has 20 sessions of its own and would swallow every repo; `/private/tmp` would fold 100 scratch rows into one, which is nice |
| Fold worktrees only       | Nest a row only when its path passes through a `worktrees` segment                                                                | Handles the two big mycelia worktree directories; special-cases a Claude Code convention; leaves `mycelia/backend` and the scratch tail flat   |


Stakes: medium. Folding changes what "select mycelia" extracts, and the `/Users/nob/repos` trap is the same one `project_predicate` has when someone types a parent path. Reversible; nothing persists but the selected directory names.

### Recommendation: flat, with type-to-filter

One row per directory is what extraction operates on, and the sort already puts the eight real projects first. We give up the tidy `/private/tmp` fold and check four rows for mycelia instead of one. Folding by prefix is not safe while `/Users/nob/repos` is itself a project.

### User Response:

Should be flat and we should try to group as much as possible. If we can trace the repository to a base project, that's better. We may want to consider grouping by git remote, but that may be a future task.

## 9. How does a script or cron job run the remembered selection without a terminal to draw the picker in?

The picker needs a TTY. A nightly `hp extract` from launchd, or a `mise` task that pipes output, has none. Two shapes: detect the missing TTY and fall back to the remembered set, or require an explicit flag and refuse a bare `hp extract` when there is no TTY.

Detection is convenient and invisible, which is the problem: the same command does two things depending on where it runs, and a pipe in a shell (`hp extract | tee log`) silently skips the picker. An explicit flag (name pending) says what the run will extract, and a bare `hp extract` without a TTY fails with a message that names the flag.

Stakes: low. Adding the flag later is additive; removing detection later breaks someone's cron job.

### Recommendation: an explicit flag, no detection

The command should mean one thing wherever it runs. We give up the convenience of a bare `hp extract` in a cron job.

### User Response:

`hp extract --last-extracted` uses whatever is saved in settings. `hp extract --all-projects` does everything

## 10. Does the picker also front `hp sessions` and `hp export-otlp`, sharing the one remembered set?

`sessions` and `extract` share one argument-declaring function, so `sessions` inherits the optional positional unless we split them. `export-otlp` reads the store, not the disk, so the picker's rows (directories under the projects root) are not quite its universe: it would want rows from the store's `project_dir` values.

Extract only keeps the change small and the remembered set's meaning single: "what I extract". `sessions` too costs a split of the shared argument function either way, and a picker in front of a listing command is odd. All three would need a second picker source (store rows) and a decision about whether "what I export" is the same set as "what I extract".

Stakes: low. Each command can grow the picker later without touching the others.

### Recommendation: extract only

The remembered set is "the projects I extract", and that is the only command whose universe is the projects root. We give up consistency: `hp sessions` and `hp export-otlp` keep a required path.

### User Response:

Extract only

## Pending questions (depends on answers above)

- The scripting flag's name (`--remembered`, `--saved`, `--last`?) and whether it also prints what it is about to extract before starting — depends on Q9
- How tests redirect the memory file: an env var like `HP_DB`, or a parameter on the function — depends on Q6
  - Do whatever you think is best
- Whether `docs/store.md` grows a section on what else `~/.hyphae` holds, or a new short doc covers the CLI's memory — depends on Q6
- Whether a remembered directory that has vanished should be reported when the scripted flag runs, or skipped quietly — depends on Q7 and Q9
- Whether the picker's fold rule, if any, should also fix `project_predicate`'s parent-path trap — depends on Q8



# Phase 3: grouping, tracing, and what counts as "last extracted"

Taken from your answers: the memory is `~/.hyphae/settings.json`, keyed by directory name; `hp extract --last-extracted` runs it and `hp extract --all-projects` runs every directory; only `extract` gets the picker.

Decided without asking:

- Phase 1 Q3 and Q5 went unanswered twice, so the recommendations stand: a session that fails to parse halts the run (per-session atomicity and fingerprints make the rerun resume), and `--tag` is allowed at every scope. Say so if you disagree
- `--all-projects` takes every directory under the projects root, scratch included
- The three ways to name projects (paths, `--last-extracted`, `--all-projects`) are mutually exclusive; argparse enforces it
- `settings.json` is namespaced by command from day one: `{"extract": {"projects": ["-Users-nob-repos-mycelia", ...]}}`, so the next remembered thing has a place
- The settings path is a parameter defaulting to `~/.hyphae/settings.json`; tests point `HOME` at a temp dir, as the store tests can. No env var until something needs one
- `hp sessions` keeps its required positional; the shared argument function splits
- A group sorts by its members' summed seven-day count; members within it by their own

What I measured for Q12 (2026-09-15): of the 250 directories holding a transcript, the recorded `cwd` still exists on disk for 28 and is gone for 222. mycelia's two biggest worktree directories (243 and 216 sessions) are gone; `mycelia/backend` (349) and one small worktree exist. Git can trace `mycelia/backend` to mycelia via its toplevel and the live worktree via its common dir. `/Users/nob/repos` and `/private/tmp` are not git repositories, so git never folds anything under them.

## 11. Is a group one collapsed row that selects all its directories, or a heading with each directory as its own row?

You asked for flat rows grouped as much as possible. questionary can do either: a `Choice` per group whose value is the member list, or a `Separator` heading with a `Choice` per member. Either way the memory stores member directory names (Q7), so the two differ only in what the person sees and clicks.


| Option                   | Selecting mycelia                                                                                               | Trade-off                                                                                                                               |
| ------------------------ | --------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| One row per group        | One keystroke checks mycelia and its four extension directories; the row prints the summed counts and `+4 dirs` | A new worktree directory joins the group on the next picker confirm, not on `--last-extracted`; you cannot pick `mycelia/backend` alone |
| Heading plus member rows | Check the rows you want under a `mycelia` heading; `a` toggles all                                              | Four keystrokes for mycelia; every row is one directory, so the picker and the memory say exactly the same thing                        |


```
One row per group                         Heading plus member rows
◉ /Users/nob/repos/mycelia  41 wk  1401  ── /Users/nob/repos/mycelia ──────
    +4 directories                          ◉ /Users/nob/repos/mycelia           30 wk   577
◉ /Users/nob/repos/hyphae    9 wk    68    ◉ …/mycelia/backend                  11 wk   349
◯ /Users/nob/repos/mac_settings 2 wk 42    ◯ …/.claude/worktrees/agent-a98…/backend  0  243
◯ /private/tmp/claude-501/…  0 wk    56    ◯ …/.claude/worktrees/agent-ac0…/backend  0  216
                                            ◯ …/.claude/worktrees/wk-refb/backend     0   16
                                          ── /Users/nob/repos/hyphae ───────
                                            ◉ /Users/nob/repos/hyphae             9 wk    68
```

Stakes: low; a picker layout change touches one function and nothing stored.

### Recommendation: one row per group

The point of grouping is to stop thinking about worktrees, and a row per directory keeps making you think about them. We give up picking one extension directory alone, and accept that `--last-extracted` runs exactly the directories confirmed last time, so a worktree created since then waits for the next picker.

### User Response:

One row per group

## 12. How is a directory traced to its base project: git, a path rule, or both?

Git answers only for the 28 directories whose `cwd` still exists: `rev-parse --show-toplevel` folds a subdirectory into its repository, and `--git-common-dir` folds a live worktree into the repository it was cut from. A path rule reads the `cwd` string alone: a path with a `.claude/worktrees/<name>` or `worktrees/<name>` segment traces to the part before it, which covers Claude Code's own worktrees whether or not they still exist.


| Option         | Groups today                                 | Trade-off                                                                                                |
| -------------- | -------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Git only       | `mycelia/backend`, one live worktree         | True by construction; misses the 459 sessions in mycelia's two deleted worktrees, which stay as two rows |
| Path rule only | All four mycelia extensions except `backend` | No subprocess; encodes a Claude Code convention that could change; `backend` stays its own row           |
| Both           | All four mycelia extensions                  | Two mechanisms to explain; git runs once per existing directory, ~28 calls                               |


Stakes: low. Grouping is presentation; a wrong group costs one extra row or one row too few, and nothing stored depends on it. Grouping by git remote, which you flagged as future, would replace the git half of this cleanly.

### Recommendation: both

A row for a deleted worktree with 243 sessions is exactly the clutter grouping exists to remove, and git is the only honest answer for `backend`. We give up one mechanism's simplicity and take on a convention that Claude Code owns.

### User Response:

Both

## 13. Which runs write the memory that `--last-extracted` reads: the picker only, or every run that names projects?

Phase 2 decided that only the picker writes it, on the theory that explicit paths are one-offs. The flag name you chose, `--last-extracted`, reads as "whatever ran last", which would include `hp extract ~/repos/hyphae` typed for a quick refresh, and arguably `--all-projects`.

If explicit paths write it too, the name is honest, but a one-off `hp extract /tmp/probe` silently retargets tonight's cron job. If only the picker writes it, the cron job runs what you deliberately chose, and the name is slightly off: it is "last picked", not "last extracted". Letting `--all-projects` write it would make `--last-extracted` mean everything after one sweep, which no one wants.

Stakes: low but sticky. The semantics are easy to change; a cron job that quietly extracts the wrong set is the kind of bug nobody notices for a month.

### Recommendation: the picker only, and consider `--saved` or `--picked` as the flag name

A remembered selection should change only when you deliberately select. We give up the literal reading of `--last-extracted`; if you keep the name, its help text says "the projects last chosen in the picker".

### User Response:

Picker only, and let's do `--last-picked`

## Pending questions (depends on answers above)

- Whether `--last-extracted` should print the projects it is about to run, and whether it fails or warns when a remembered directory has vanished — depends on Q13
  - Yes, should print
- Whether `hp extract` with the picker should also offer "everything" as a first row, making `--all-projects` the scripted twin of a picker choice — depends on Q11
  - Yes, offer everything as an option
- Whether the grouping rule should be written once for the picker and the store's `project_predicate`, so the viewer's projects page and the picker fold the same way — depends on Q12
  - Use your best judgement

