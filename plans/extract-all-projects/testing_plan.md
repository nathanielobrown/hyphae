# Testing plan: `hp extract` picks its projects

What the tests must prove for `design.md` beside this file. Each leaf is an obligation; the implementer discharges it and the auditor traces it to the evidence named. Repo claims below were checked at `6a54065` on 2026-09-15.

Real data available: every recorded fixture under `tests/fixtures/` carries `cwd` `/Users/nob/repos/mycelia`; `spine/` opens with three records that carry none and holds two borrowed records whose `cwd` is `/Users/nob/repos/mycelia/.claude/worktrees/wk-triage` (a real, since-deleted worktree path); `fork_byref/`'s main transcript carries no `cwd` at all. The only fixtures under another `cwd` are invented (`/invented/project`, `/repo`), so a two-project root always mixes one invented transcript in.

- **unit (grouping)** — `tests/extract/test_grouping.py`; `base_project()` over a real git repository built with `git init` and `git worktree add` under `tmp_path`, plus path strings nothing on disk backs. Every `git` call carries a timeout; the module takes `@pytest.mark.xdist_group("git_repo")` so one worker builds the repo
  - A recorded `.claude/worktrees/<name>` path that no longer exists folds to the repository above it, by the path rule alone. *Evidence:* the `wk-triage` path from `spine/` maps to `/Users/nob/repos/mycelia`; the test runs where that path does not exist
  - A `worktrees/<name>` segment without `.claude` folds the same way, and a subdirectory below the segment folds too. *Evidence:* `<x>/worktrees/w/src` maps to `<x>`; invented paths
  - **A repository root maps to itself, as an absolute path.** Bold: from the top level `git rev-parse --git-common-dir` prints the relative `.git`, so a naive `Path(out).parent` yields `.`. *Evidence:* `base_project(repo)` equals `repo` after `resolve()`
  - A subdirectory of a repository maps to the repository. *Evidence:* `repo/src/pkg` maps to `repo`
  - **A live worktree cut beside its repository maps to the repository it was cut from.** The layout this checkout uses (`repos/hyphae-wt/extract-picker`), which no path rule reaches. *Evidence:* `git worktree add ../wt` then `base_project(wt)` equals `repo`
  - A directory that exists but is inside no repository maps to itself, and git's refusal is not an error. *Evidence:* `base_project(tmp_path)` returns `tmp_path`; nothing raised
  - **A parent of repositories does not fold into any of them.** The `/Users/nob/repos` case that would swallow every repo. *Evidence:* `tmp/repos` holding `tmp/repos/a` (a repo) maps to `tmp/repos`
  - A path that does not exist and matches no rule maps to itself. *Evidence:* invented `/gone/x`

- **unit (layout and discovery)** — `tests/extract/test_layout.py`, `tests/extract/test_discover.py`; `make_projects_root` grown to copy real fixture transcripts (and a session's directory) and to set mtimes with `os.utime`; `discover(root, now=...)` with a pinned clock
  - `find_sessions(project_dir)` still refuses a missing directory. *Evidence:* the existing `test_find_sessions_raises_when_the_project_has_no_recorded_sessions` passes with the caller encoding the path itself, and the error names the directory
  - `find_project_dirs` returns only directories holding a top-level transcript, by name. *Evidence:* a root with two transcript directories, an empty directory, a directory holding only a session subdirectory, and a stray file; the two come back sorted. Invented layout
  - `find_project_dirs` on a root that does not exist raises rather than returning nothing. *Evidence:* `pytest.raises(FileNotFoundError)`; see findings
  - **`cwd` comes from the first record that carries one in the newest transcript.** *Evidence:* `spine/` (first three records have none) copied beside `invented-truncated-tail` (`cwd` `/repo`); with the invented one's mtime newer, `cwd` is `/repo`; with `spine`'s newer, `/Users/nob/repos/mycelia`
  - A directory whose newest transcript carries no `cwd` has `cwd=None`, `base=None`, and its label is the directory name. *Evidence:* `fork_byref/`'s main transcript; the `ProjectDir` compared whole
  - `sessions` counts top-level transcripts only; subagent transcripts do not count. *Evidence:* `spine/` copied with its `subagents/` directory gives `sessions == 1`
  - `recent` counts transcripts with mtime inside seven days of `now`; older ones are counted in `sessions` only. *Evidence:* three transcripts at 1, 6 and 8 days before a pinned `now`; `recent == 2`, `sessions == 3`. Invented mtimes
  - `base` is `base_project(cwd)`. *Evidence:* a transcript whose `cwd` is the `wk-triage` path (invented copy of the borrowed spine record) discovers with `base == /Users/nob/repos/mycelia`
  - Rows sort by `recent` desc, then `sessions` desc, then name. *Evidence:* four directories arranged so each key alone would misorder; the name list asserted whole. Invented mtimes
  - `ClaudeCodeExtractor.sessions(project)` and `sessions_in(root / encode_project_path(project))` return the same sources, fingerprints included. *Evidence:* the two lists compare equal over a copied `spine/`

- **unit (settings)** — `tests/test_user_settings.py`; `read`/`write` over a path under `tmp_path`, and the default path with `HOME` moved
  - A written mapping reads back equal. *Evidence:* `{"extract": {"projects": [...]}}` round trip; and `"all"` round trips as the string
  - A missing file reads as an empty mapping. *Evidence:* `read(tmp_path / "none.json") == {}`
  - A malformed file crashes rather than reading as empty. *Evidence:* `pytest.raises(json.JSONDecodeError)` on invented text
  - `write` creates the directory above the file. *Evidence:* `tmp_path / "a" / "b" / "settings.json"` exists after
  - **The default path is `$HOME/.hyphae/settings.json`, not the store's directory.** The suite pins `HP_DB=/pinned/traces.duckdb` for every test, so a settings path derived from `default_store().parent` would land at `/pinned/`. *Evidence:* with `HOME` set to `tmp_path` and `HP_DB` still pinned, `write` lands at `tmp_path / ".hyphae" / "settings.json"`

- **unit (picker)** — `tests/extract/test_picker.py`; `choices()` and the pure selection function (see findings) over `ProjectDir` rows built by hand from real `cwd` values; nothing drives prompt_toolkit
  - The Everything row comes first, and its value is `"all"`. *Evidence:* `choices(rows, [])[0].value == EVERYTHING`
  - **Two directories sharing a base fold into one row whose value carries both names, whose counts are summed, and whose title says `+1 directories`.** *Evidence:* rows for `-Users-nob-repos-mycelia` and the `wk-triage` directory; the `Choice` fields compared whole
  - A row with no base, or a base nobody else shares, stands alone under its own label. *Evidence:* the `fork_byref`-style row (no `cwd`) titled by name; the `/repo` row titled by `cwd`
  - A grouped row is checked when any member is remembered. *Evidence:* remembered `[wk-triage name]` checks the mycelia row
  - Remembered `"all"` checks the Everything row and nothing else. *Evidence:* the `checked` list asserted whole
  - A remembered name no longer on disk checks nothing and raises nothing. *Evidence:* remembered `["-gone"]` gives no checked row
  - A confirm with nothing chosen exits with a message. *Evidence:* the selection function raises `SystemExit`; the message asserted. Design finding below
  - A confirm that includes Everything yields `"all"`; one that does not yields the flattened member names. *Evidence:* two calls, return compared whole

- **unit (pipeline)** — `tests/test_pipeline.py`; `refresh(extractor.sessions(project), ...)` over the existing fixture corpus and the existing wrapping extractors
  - Every existing leaf passes unchanged in behaviour once callers hand `refresh` the sources. *Evidence:* the file's assertions are untouched; only the call sites change
  - `refresh` over no sources reports empty lists and touches the exporter only to read fingerprints. *Evidence:* `refresh([], ...)` with a counting exporter; `RefreshResult([], [], [])`
  - The OTLP callers pass the same way. *Evidence:* `tests/export/test_otlp__delivery.py`, `test_otlp__cli.py`, `test_otlp__census.py` and `tests/export/conftest.py` pass with `StoreSource(...).sessions(Path(MYCELIA))` handed in

- **cli** — `tests/test_cli.py`; `cli.main("extract", ..., "--projects-root", root, "--db", db)` over a fake root of copied fixtures, `HOME` monkeypatched to `tmp_path`, `picker.pick` monkeypatched where the bare command runs. A two-project root is `spine/` under `-Users-nob-repos-mycelia` and `invented-no-cache-creation` under `-invented-project` (the one clean fixture with another `cwd`; invented content, real placement)
  - **The pinned surface.** `SURFACES["extract"]` holds the new namespace: `project` a list, `all_projects` and `last_picked` false, `--tag` and `--db` as before; `sessions` keeps its single positional. *Evidence:* `test_every_subcommand_the_parser_exposes_is_pinned_above` and the table
  - A typed path and either flag, or the two flags together, are refused. *Evidence:* parametrized `pytest.raises(SystemExit)` over `PATH --all-projects`, `PATH --last-picked`, `--all-projects --last-picked`
  - **Two typed paths extract both directories, one summary line each, and memory is untouched.** *Evidence:* the store holds both session ids; stdout has two `<label>: 1 session(s) extracted, 0 unchanged` lines; no `settings.json` under `HOME`
  - The existing extract leaves (tags, undeclared fields, unknown kinds, refusal) hold with the summary line carrying its label. *Evidence:* `test_the_tags_typed_at_the_flag_reach_the_store` and the three tally leaves pass with `printed[0]` re-pinned
  - A refusal in the first directory does not stop the second, and the run still exits nonzero naming it. *Evidence:* `invented-wrong-field-type` under one directory, `spine` under another; both summaries printed, `spine` in the store, `SystemExit` names the bad session and says nothing of its payload
  - `--all-projects` extracts every directory, `--tag` reaches every session, memory untouched. *Evidence:* both ids in `sessions`, a `session_tags` row per session, no settings file
  - **`--last-picked` prints the remembered rows, skips a vanished name with a line, runs the rest.** *Evidence:* settings written with `["-Users-nob-repos-mycelia", "-gone"]`; stdout names both up front, marks `-gone` skipped, and summarises mycelia; the store holds `spine`
  - `--last-picked` with `"all"` remembered runs every directory. *Evidence:* both ids in the store
  - `--last-picked` with nothing remembered exits with a message that names the bare command. *Evidence:* no settings file; `pytest.raises(SystemExit)`; see findings
  - **The bare command hands the picker the discovered rows and the remembered names, runs what it returns, and writes that choice.** *Evidence:* `pick` monkeypatched to record its arguments and return `["-Users-nob-repos-mycelia"]`; the rows passed are `discover(root)`'s and the remembered list is what the test wrote; `spine` is in the store and the file reads back `{"extract": {"projects": ["-Users-nob-repos-mycelia"]}}`, the vanished name gone
  - The bare command with `"all"` picked runs every directory and remembers `"all"`. *Evidence:* both ids stored; file holds the string
  - A picker that exits writes nothing and extracts nothing. *Evidence:* `pick` monkeypatched to raise `SystemExit`; no settings file, no store rows

- **not covered**
  - prompt_toolkit rendering, `use_search_filter`, keystrokes: needs a terminal. The PR description reports the manual run in Cursor's terminal and Terminal.app
  - The real `~/.claude/projects` and the real `~/.hyphae`: private session data and a person's preference; every leaf runs over `tmp_path`
  - git absent from `PATH`: not a machine this runs on
  - A layout error stopping a multi-directory run: unchanged behaviour, already pinned by `tests/extract/test_layout.py`

## Design findings

- **The empty confirm and the "all" mapping live inside `pick()`, which the seam cannot reach.** Split `pick` into the questionary call and a pure function (say `selected(answer) -> list[str] | Literal["all"]`) that raises `SystemExit` on nothing chosen and flattens grouped values; `pick` becomes two lines. questionary's `.ask()` also returns `None` on Ctrl-C, which the pure function should treat as nothing chosen
- **`--last-picked` with nothing remembered is unspecified.** `user_settings.read()["extract"]["projects"]` raises `KeyError` on a fresh machine. Recommend `SystemExit("nothing remembered: run `hp extract` once to pick")`; the cli leaf above assumes it
- **The summary label for a typed path is unspecified.** Typed paths skip `discover()`, so there is no `cwd` to label with. Recommend printing the path as typed; the cli leaves assume it
- **`find_project_dirs` on a missing root is unspecified.** A missing `~/.claude/projects` means Claude Code never ran here; raising matches `find_sessions`'s reasoning. The layout leaf assumes it
- **The file-tree diff is incomplete.** `cli._export_otlp` calls `refresh(args.project, extractor=StoreSource(...))` twice, and `tests/export/test_otlp__delivery.py`, `test_otlp__cli.py`, `test_otlp__census.py` and `tests/export/conftest.py` call `refresh(Path(MYCELIA), ...)`; all change in slice 1
- **Grouping tests must not touch the real filesystem outside `tmp_path`.** `/Users/nob/repos` exists on the machine that runs the suite; the parent-of-repos leaf builds its own
