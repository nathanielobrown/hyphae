# Design: `hp extract` picks its projects

A bare `hp extract` opens a multi-select picker over every project Claude Code has recorded, sorted by recent activity, pre-checked with what was picked last time, and remembers the new choice. The decisions behind this shape are in `extract_all_projects_questions.md` beside this file; the question numbers below refer to it.

Every claim here about the code was read on 2026-09-15 at main `6a54065`. Verify before relying on it: the implementer branches from a fresh `main`.

## Problem

`hp extract` takes one required project path and extracts one directory under `~/.claude/projects`. Refreshing the corpus means remembering which paths matter and typing each one. The projects root holds 253 directories, most of them scratch checkouts mycelia's evals deleted, so "extract everything" is the wrong default and "type the path" is the wrong ceremony. A person should choose once and rerun without thinking.

Two constraints decide the shape. Claude Code's directory names are lossy (`mac_settings` → `-Users-nob-repos-mac-settings`), so a remembered project must be the directory name, never a path re-encoded on the way back in (Q7). And only 28 of the 250 recorded working directories still exist on disk, so anything that groups a worktree under its repository must work from the path string alone, with git as a refinement where the path exists (Q12).

## Call paths

Current:

```
cli._extract(args)
  ClaudeCodeExtractor(projects_root, tags)
  pipeline.refresh(args.project, extractor, exporter)
    extractor.sessions(project)            # encode_project_path → find_sessions(project)
    for each source: skip by fingerprint, or export(extract(source))
  print "N extracted, M unchanged"
```

Proposed:

```
cli._extract(args)
  targets = one of, mutually exclusive:
    args.project (one or more typed paths)  → [projects_root / encode_project_path(p)]
    --all-projects                          → discover(projects_root), every directory
    --last-picked                           → user_settings.read()["extract"]["projects"], printed first
    (none)                                  → picker.pick(discover(projects_root), remembered) ; user_settings.write(...)
  for each target directory:
    sources = extractor.sessions_in(directory)
    result = pipeline.refresh(sources, extractor=extractor, exporter=exporter)
    print one line: "<cwd label>: N extracted, M unchanged[, K refused]"
  print the refusals and the undeclared-field report as today
```

`discover()` walks the projects root once: for each directory holding a transcript it reads the newest transcript until a record carries `cwd` (`docs/schema.md`), counts transcripts and those with mtime inside seven days, and asks `base_project(cwd)` which repository the directory extends. The picker folds directories that share a base project into one row (Q11).

## File-tree diff

```
src/hyphae/
  pipeline.py                 changed: refresh(sources, ...) instead of refresh(project, ...)
  user_settings.py            added: ~/.hyphae/settings.json, namespaced by command
  cli.py                      changed: extract's arguments and run; sessions keeps its own positional
  extract/
    layout.py                 changed: find_sessions takes the directory; find_project_dirs added
    claude_code.py            changed: sessions(project) delegates to sessions_in(directory)
    discover.py               added: ProjectDir rows with counts, label and base project
    grouping.py               added: base_project(cwd) — path rule, then git
    picker.py                 added: questionary checkbox over ProjectDir rows
pyproject.toml                changed: questionary dependency, with its one-line reason
tests/
  test_pipeline.py            changed: callers pass extractor.sessions(project)
  test_cli.py                 changed: the pinned extract arguments; new leaves per flag
  test_user_settings.py       added
  extract/test_discover.py    added
  extract/test_grouping.py    added
  extract/test_picker.py      added
README.md, docs/store.md      changed: the bare command, the flags, what else ~/.hyphae holds
CONTEXT.md                    changed: Picker, Base project, Settings file
```

## Key contracts

```python
# pipeline.py — the loop no longer discovers; callers hand it what to refresh
def refresh[SourceT: SessionSource](
    sources: Iterable[SourceT], *, extractor: Extractor[SourceT], exporter: Exporter
) -> RefreshResult: ...

# extract/layout.py
def find_project_dirs(projects_root: Path) -> list[Path]:
    """Every directory under the root holding at least one top-level transcript, by name."""
def find_sessions(project_dir: Path) -> list[SessionFiles]:
    """Raises FileNotFoundError when project_dir is not a directory, as today."""

# extract/claude_code.py
class ClaudeCodeExtractor:
    def sessions(self, project: Path) -> list[ClaudeCodeSource]:      # typed path; encodes, then
    def sessions_in(self, directory: Path) -> list[ClaudeCodeSource]:  # the directory itself

# extract/discover.py
@dataclass(frozen=True)
class ProjectDir:
    name: str                 # the directory name under the root: what settings.json stores
    directory: Path
    cwd: Path | None          # from the newest transcript that records one; None labels by name
    base: Path | None         # base_project(cwd); None when cwd is None
    sessions: int             # top-level transcripts
    recent: int               # of those, mtime within the last seven days
def discover(projects_root: Path, *, now: datetime) -> list[ProjectDir]:
    """Sorted by recent desc, sessions desc, name."""

# extract/grouping.py
def base_project(cwd: Path) -> Path:
    """The repository a working directory extends, or the directory itself.
    Path rule first: cut at a `.claude/worktrees/<name>` or `worktrees/<name>` segment.
    Then, if what remains exists on disk and is inside a git repository, the parent of
    `git rev-parse --git-common-dir` — one call, which folds a subdirectory into its
    repository and a live worktree into the repository it was cut from."""

# extract/picker.py
EVERYTHING = "all"
def choices(rows: list[ProjectDir], remembered: list[str] | Literal["all"]) -> list[questionary.Choice]:
    """Pure: the Everything row first, then one row per base project (members summed, `+N directories`),
    then ungrouped rows; checked when any member is remembered."""
def pick(rows, remembered) -> list[str] | Literal["all"]:
    """Runs the checkbox with use_search_filter=True. An empty confirm raises SystemExit
    with a message and writes nothing."""

# user_settings.py
SETTINGS_NAME = "settings.json"          # beside store_path.STORE_NAME under store_path.STORE_DIR
def read(path: Path = ...) -> dict
def write(settings: dict, path: Path = ...) -> None
# shape: {"extract": {"projects": ["-Users-nob-repos-mycelia", ...]}}  or  {"extract": {"projects": "all"}}
```

CLI surface:

| Invocation | Does |
| --- | --- |
| `hp extract` | picker; writes the remembered set |
| `hp extract PATH [PATH ...]` | those directories; memory untouched (Q13) |
| `hp extract --last-picked` | prints the remembered rows it will run, then runs them; a name no longer on disk prints as skipped and drops out on the next confirm |
| `hp extract --all-projects` | every directory `find_project_dirs` returns, scratch included; memory untouched |

The three are mutually exclusive; argparse or a hand check refuses a mix. `--tag` and `--db` mean the same at every scope.

## Chosen test seam

`cli.main("extract", ..., "--projects-root", root, "--db", db)` over a fake projects root, as `tests/test_cli.py:extracted` does today, with `HOME` pointed at `tmp_path` so `settings.json` lands there. The picker itself is split at `choices()`, a pure function the tests drive directly; the one leaf that runs the bare command monkeypatches `picker.pick` to return a selection. Nothing drives prompt_toolkit.

Fixtures: the fake root is `tests/extract/test_layout.py:make_projects_root` grown to copy real fixture transcripts (they carry `cwd`) and to set mtimes with `os.utime`. Grouping tests build a real git repository and a worktree under `tmp_path`, and pass deleted-worktree paths as strings.

## Slices

1. **The seam.** `refresh(sources)`, `find_sessions(project_dir)`, `sessions_in`, `project*` accepting several paths, one summary line per directory. Verified by `tests/test_pipeline.py` passing unchanged in behaviour, and a new CLI leaf extracting two projects from one command
2. **Discovery, settings, the two flags.** `discover()`, `user_settings`, `--all-projects`, `--last-picked` with its printed plan and skipped-vanished line. Verified by `test_discover.py` (labels, counts, sort, a directory with no `cwd`), `test_user_settings.py` (round trip, missing file, malformed file crashes), and a CLI leaf per flag
3. **Grouping.** `base_project()` and the `base` field on `ProjectDir`. Verified by `test_grouping.py`: subdirectory of a repo, live worktree, deleted `.claude/worktrees` path, a path that is not a repo, and `/Users/nob/repos`-style parent that must not fold
4. **The picker.** questionary added; `choices()` and `pick()`; the bare command; memory written on confirm; Everything row. Verified by `test_picker.py` over `choices()` and one CLI leaf with `pick` monkeypatched, plus a manual run in a terminal that the PR description reports
5. **Docs and glossary.** README's extract section, `docs/store.md`'s sentence on what `~/.hyphae` holds, `CONTEXT.md` entries, `mise run cogs`, then `doc-sync`. Verified by `mise run check`

Each slice is one commit or a few; `commit` skill for the messages.

## Decisions

- **Picker over a corpus-wide default** (Q1, chat). Rejected: bare `hp extract` sweeps everything. 253 directories, ~200 scratch
- **questionary** (Phase 2 research). Rejected: InquirerPy (unmaintained), simple-term-menu (quiet two years), beaupy (four deps), python-inquirer (no filter)
- **Memory in `~/.hyphae/settings.json`** (Q6). Rejected: a table in the store. A preference is the person's, not the archive's
- **Directory names in memory** (Q7). Rejected: recorded `cwd`. It does not round-trip to a directory
- **One row per base project** (Q8, Q11). Rejected: heading plus member rows (four keystrokes for mycelia); fold by bare path prefix (`/Users/nob/repos` has 20 sessions and would swallow every repo)
- **Path rule, then git** (Q12). Rejected: git alone, which reaches 28 of 250 directories and misses 459 sessions in deleted mycelia worktrees
- **Explicit flags, no TTY detection** (Q9). Rejected: fall back to memory when stdin is not a terminal; the same command would do two things
- **Only the picker writes memory** (Q13). Rejected: every run that names projects; a one-off path would retarget a cron job
- **`extract` only** (Q10). Rejected: the picker on `sessions` and `export-otlp`
- **`refresh` takes sources** (this design). Rejected: an extractor `sessions()` that accepts either a path or a directory name, which would make the argument mean two things
- **Failure handling unchanged.** `refresh` already carries on past a parser refusal and reports it (`pipeline.Failure`); a layout error still stops the run. Phase 1 Q3 described today's behaviour as "halt", which was wrong for schema refusals and right for layout errors. Nothing here changes either
- **`--tag` allowed at every scope** (Q5, by default). Rejected: refusing it without a project
- **Settings path is a parameter defaulting under `Path.home()`**; tests set `HOME`. Rejected: an `HP_SETTINGS` env var. Nothing needs one yet

## Out of scope

- The picker on `hp sessions` and `hp export-otlp` (Q10)
- Grouping by git remote (Q8, flagged as future). `base_project()` is the one place to replace
- Folding in the viewer's projects page or `project_predicate`. `base_project()` is written once so the viewer can adopt it; changing what a store query counts as a project is its own change
- The lossy `encode_project_path`: `hp extract ~/repos/mac_settings` fails today because hyphae replaces only `/`. Typed paths keep that bug; the picker sidesteps it. File it separately
- The layout error that stops `hp extract ~/repos/hyphae` today (`unknown file auto-mode-classifier-error.txt`). A separate parser fix; the implementer will hit it on a manual run and should not fold it in

## Open questions

- Whether argparse accepts a `nargs="*"` positional inside a mutually exclusive group alongside two flags on Python 3.13, or the check is written by hand. Settled by trying it in slice 1
- How questionary renders in the terminals in use (Cursor's, Terminal.app) with `use_search_filter=True`. Settled by the manual run in slice 4

## Amendments from the testing plan (2026-09-15)

Settled by the manager after `testing_plan.md` found them unspecified:

- `picker.pick()` splits into `choices()` and a pure `selected(answer) -> list[str] | Literal["all"]` that flattens group members and maps `EVERYTHING` to `"all"`; `pick` only runs the prompt and calls `selected`. questionary returns `None` on Ctrl-C: `selected(None)` and an empty answer both raise `SystemExit` with a message, and nothing is written
- `--last-picked` with nothing remembered raises `SystemExit` telling the person to run bare `hp extract` first
- Typed paths skip `discover()`, so their summary line is labelled with the path as typed
- `find_project_dirs()` raises `FileNotFoundError` on a missing root, as `find_sessions` does
- The settings path defaults to `Path.home() / store_path.STORE_DIR / SETTINGS_NAME`; it is not derived from `HP_DB`, which the suite pins
- Slice 1 also moves `cli._export_otlp` and the `tests/export/` callers onto `refresh(sources, ...)`
- **Only the picker walks the root** (audit fix 1, manager's decision; supersedes the call paths above). `--last-picked` resolves each remembered name to `projects_root / name`, prints its plan, skips a name not on disk, and reads no transcript before `refresh`; `--all-projects` is `find_project_dirs(root)` alone. Their summary lines are labelled by directory name; only the picker's rows carry the recorded `cwd`, and a typed path keeps the path as typed
- **`discover()` survives one refused transcript.** A `TranscriptSchemaError` while reading a directory's newest transcript for its `cwd` yields the row with `cwd=None` (labelled by name) and one warning naming the directory and the error, so a walk over ~250 mostly-scratch directories does not stop on one drifted record; nothing broader is caught, and the extract that follows refuses the session as before. The cli leaves moved to `tests/test_cli__extract.py`
