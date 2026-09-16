"""`hp extract`'s four scopes and what each prints: typed paths, `--all-projects`,
`--last-picked`, and the bare command's picker — over a fake projects root of fixture
transcripts, with `HOME` moved so the settings file lands under `tmp_path`.

Split from `test_cli.py`, which pins the parser surface; this file drives the extract itself.
"""

import datetime as dt
from pathlib import Path

import pytest

from hyphae import cli, settings, user_settings
from hyphae.extract import picker
from hyphae.extract.discover import ProjectDir, discover
from hyphae.projects import encode_project_path
from tests.conftest import MYCELIA, SPINE, stored_rows
from tests.extract.test_layout import copy_fixture, refused_transcript
from tests.test_cli import PROJECT


def plant(tmp_path: Path, projects: dict[Path, list[str]]) -> Path:
    """Lay out a projects root of fixture transcripts under `tmp_path`, one directory per
    project path, and hand back the root."""
    root = tmp_path / "projects"
    for project, fixtures in projects.items():
        for fixture in fixtures:
            copy_fixture(root / encode_project_path(project), fixture)
    return root


def run_extract(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], strict: bool, *arguments: str
) -> list[str]:
    """Run `hp extract` with `arguments` over the root `plant` laid out, and hand back what it
    printed.

    `strict` is what a test run has and an extract does not: the extractor reads it once, at
    construction, so setting it here is setting it for the run. `HOME` is `tmp_path`, so a
    settings file the run writes or reads is under it and nowhere real.
    """
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(settings, "UNIT_TESTING", strict)
        patch.setenv("HOME", str(tmp_path))
        cli.main(
            "extract",
            *arguments,
            "--projects-root",
            str(tmp_path / "projects"),
            "--db",
            str(tmp_path / "traces.duckdb"),
        )
    return capsys.readouterr().out.splitlines()


def extracted(
    tmp_path: Path,
    projects: dict[Path, list[str]],
    capsys: pytest.CaptureFixture[str],
    strict: bool,
    *tags: str,
) -> list[str]:
    """`hp extract` over typed paths: `projects` maps each path the command is typed with to
    the fixtures its directory holds, typed in the order given. Each of `tags` is one
    `--tag KEY=VALUE` argument, spelled the way a caller types it."""
    plant(tmp_path, projects)
    return run_extract(
        tmp_path,
        capsys,
        strict,
        *[str(project) for project in projects],
        *[argument for tag in tags for argument in ("--tag", tag)],
    )


def settings_file(tmp_path: Path) -> Path:
    """Where a run under `run_extract` keeps its settings: `HOME` is `tmp_path`."""
    return tmp_path / ".hyphae" / "settings.json"


# The two-project root every scope leaf runs over: the deepest recorded session under the
# mycelia directory, and the one clean fixture recorded under another `cwd` — invented content,
# placed the way Claude Code places a project.
TWO_PROJECTS = {Path(MYCELIA): [SPINE], Path("/invented/project"): ["invented-no-cache-creation"]}
INVENTED = "invented-no-cache-creation"
MYCELIA_DIR = encode_project_path(Path(MYCELIA))
INVENTED_DIR = encode_project_path(Path("/invented/project"))


@pytest.mark.parametrize(
    "arguments",
    [
        (str(PROJECT), "--all-projects"),
        (str(PROJECT), "--last-picked"),
        ("--all-projects", "--last-picked"),
    ],
)
def test_a_typed_path_and_a_scope_flag_refuse_each_other(arguments: tuple[str, ...]) -> None:
    """A path, `--all-projects` and `--last-picked` each name the whole scope, so a mix is
    refused before anything runs."""
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["extract", *arguments])


def test_two_typed_paths_extract_both_directories(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`hp extract` takes several paths and reports each directory on its own line.

    The second project is the one clean fixture recorded under another `cwd`: invented
    content, but placed the way Claude Code places a project.
    """
    # If two paths are typed, each with one session under its directory...
    printed = extracted(tmp_path, TWO_PROJECTS, capsys, strict=True)

    # ...then the store holds both sessions...
    assert stored_rows(tmp_path / "traces.duckdb", "SELECT id FROM sessions ORDER BY id") == [
        (SPINE,),
        (INVENTED,),
    ]
    # ...each directory got its own summary, labelled with the path as typed...
    assert printed == [
        f"{MYCELIA}: 1 session(s) extracted, 0 unchanged",
        "/invented/project: 1 session(s) extracted, 0 unchanged",
    ]
    # ...and nothing was remembered: a typed path is a one-off, not a choice.
    assert not settings_file(tmp_path).exists()


def test_all_projects_extracts_every_directory_under_the_root(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`hp extract --all-projects` runs every directory, tags every session, and remembers
    nothing."""
    # If the root holds two project directories and the run is tagged...
    plant(tmp_path, TWO_PROJECTS)
    printed = run_extract(tmp_path, capsys, True, "--all-projects", "--tag", "batch=b1")

    # ...then both sessions are in the store, each with the tag...
    assert stored_rows(
        tmp_path / "traces.duckdb",
        "SELECT session_id, key, value FROM session_tags ORDER BY session_id",
    ) == [(SPINE, "batch", "b1"), (INVENTED, "batch", "b1")]
    # ...each directory is summarised under its name, by name: nothing was read before the
    # extract, so there is no `cwd` to label it with...
    assert printed == [
        f"{MYCELIA_DIR}: 1 session(s) extracted, 0 unchanged",
        f"{INVENTED_DIR}: 1 session(s) extracted, 0 unchanged",
    ]
    # ...and no choice was remembered.
    assert not settings_file(tmp_path).exists()


def test_last_picked_prints_the_remembered_rows_and_skips_a_vanished_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`hp extract --last-picked` says what it is about to run, marks a remembered directory
    that is no longer on disk as skipped, and runs the rest."""
    # If the last pick named the mycelia directory and one that has since been pruned...
    plant(tmp_path, TWO_PROJECTS)
    user_settings.write({"extract": {"projects": [MYCELIA_DIR, "-gone"]}}, settings_file(tmp_path))
    printed = run_extract(tmp_path, capsys, True, "--last-picked")

    # ...then the plan names both up front, one of them skipped, and only mycelia is summarised,
    # by name — the remembered names are resolved to directories without a walk of the root...
    assert printed == [
        "Extracting 1 of 2 remembered project(s):",
        f"  {MYCELIA_DIR}",
        f"  -gone  skipped: no longer under {tmp_path / 'projects'}",
        f"{MYCELIA_DIR}: 1 session(s) extracted, 0 unchanged",
    ]
    # ...and the store holds the mycelia session and not the other directory's.
    assert stored_rows(tmp_path / "traces.duckdb", "SELECT id FROM sessions") == [(SPINE,)]


def test_last_picked_reads_no_transcript_of_a_directory_it_was_not_asked_for(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--last-picked` is the cron path: a scratch directory beside the remembered one is
    never opened, so a transcript the parser would refuse there costs it nothing."""
    # If a scratch directory the last pick never named holds a transcript refused on its first
    # record (an invented bend of a real record: `refused_transcript`)...
    root = plant(tmp_path, TWO_PROJECTS)
    refused_transcript(root / "-Users-nob-scratch")
    user_settings.write({"extract": {"projects": [MYCELIA_DIR]}}, settings_file(tmp_path))
    printed = run_extract(tmp_path, capsys, True, "--last-picked")
    # ...then the run says nothing of it — no refusal line, no skipped line — and extracts mycelia.
    assert printed == [
        "Extracting 1 of 1 remembered project(s):",
        f"  {MYCELIA_DIR}",
        f"{MYCELIA_DIR}: 1 session(s) extracted, 0 unchanged",
    ]
    assert stored_rows(tmp_path / "traces.duckdb", "SELECT id FROM sessions") == [(SPINE,)]


def test_last_picked_with_everything_remembered_runs_every_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A remembered "all" is the whole root, whatever directories it holds today."""
    plant(tmp_path, TWO_PROJECTS)
    user_settings.write({"extract": {"projects": "all"}}, settings_file(tmp_path))
    printed = run_extract(tmp_path, capsys, True, "--last-picked")
    # The plan line counts the directories the root holds now, then each is summarised by name.
    assert printed == [
        "Extracting every project, as last picked: 2 directories",
        f"{MYCELIA_DIR}: 1 session(s) extracted, 0 unchanged",
        f"{INVENTED_DIR}: 1 session(s) extracted, 0 unchanged",
    ]
    assert stored_rows(tmp_path / "traces.duckdb", "SELECT id FROM sessions ORDER BY id") == [
        (SPINE,),
        (INVENTED,),
    ]


def test_last_picked_with_nothing_remembered_names_the_bare_command(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """On a machine where nothing was ever picked, `--last-picked` says how to pick."""
    plant(tmp_path, TWO_PROJECTS)
    assert not settings_file(tmp_path).exists()
    with pytest.raises(SystemExit, match="hp extract"):
        run_extract(tmp_path, capsys, True, "--last-picked")


def fake_pick(
    patch: pytest.MonkeyPatch, answer: list[str] | str | BaseException
) -> list[tuple[list[ProjectDir], list[str] | str]]:
    """Stand in for the picker: record what it was handed, and confirm `answer` — or raise
    it, the way a Ctrl-C or an empty confirm ends the prompt."""
    calls: list[tuple[list[ProjectDir], list[str] | str]] = []

    def pick(rows: list[ProjectDir], remembered: list[str] | str) -> list[str] | str:
        calls.append((rows, remembered))
        if isinstance(answer, BaseException):
            raise answer
        return answer

    patch.setattr(picker, "pick", pick)
    return calls


def test_the_bare_command_runs_the_picker_and_remembers_what_it_confirmed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A bare `hp extract` offers every discovered directory with the last pick checked,
    extracts what is confirmed, and replaces the memory with that choice."""
    # If the last pick named the mycelia directory and one since pruned — beside a setting
    # some other command keeps (invented) — and the picker confirms mycelia alone...
    plant(tmp_path, TWO_PROJECTS)
    user_settings.write(
        {"extract": {"projects": [MYCELIA_DIR, "-gone"]}, "other": {"kept": True}},
        settings_file(tmp_path),
    )
    with pytest.MonkeyPatch.context() as patch:
        calls = fake_pick(patch, [MYCELIA_DIR])
        printed = run_extract(tmp_path, capsys, True)
    # ...then the picker was handed every discovered row and the remembered names as written...
    rows = discover(tmp_path / "projects", now=dt.datetime.now(tz=dt.UTC))
    assert calls == [(rows, [MYCELIA_DIR, "-gone"])]
    # ...the confirmed directory was extracted and no other, labelled with where it ran...
    assert printed == [f"{MYCELIA}: 1 session(s) extracted, 0 unchanged"]
    assert stored_rows(tmp_path / "traces.duckdb", "SELECT id FROM sessions") == [(SPINE,)]
    # ...and the memory is the confirmed set, the pruned name gone, the other command's untouched.
    assert user_settings.read(settings_file(tmp_path)) == {
        "extract": {"projects": [MYCELIA_DIR]},
        "other": {"kept": True},
    }


def test_the_bare_command_with_everything_picked_runs_every_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """On a machine with no pick yet, the picker opens with nothing checked; confirming
    Everything extracts the whole root and remembers the word, not the list."""
    plant(tmp_path, TWO_PROJECTS)
    with pytest.MonkeyPatch.context() as patch:
        calls = fake_pick(patch, "all")
        run_extract(tmp_path, capsys, True)
    assert [remembered for _, remembered in calls] == [[]]
    assert stored_rows(tmp_path / "traces.duckdb", "SELECT id FROM sessions ORDER BY id") == [
        (SPINE,),
        (INVENTED,),
    ]
    assert user_settings.read(settings_file(tmp_path)) == {"extract": {"projects": "all"}}


def test_a_picker_that_exits_writes_nothing_and_extracts_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A prompt ended without a choice leaves the store and the memory as they were."""
    plant(tmp_path, TWO_PROJECTS)
    with pytest.MonkeyPatch.context() as patch:
        fake_pick(patch, SystemExit("Nothing picked"))
        with pytest.raises(SystemExit, match="Nothing picked"):
            run_extract(tmp_path, capsys, True)
    assert not (tmp_path / "traces.duckdb").exists()
    assert not settings_file(tmp_path).exists()


def test_a_refusal_in_the_first_directory_does_not_stop_the_second(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One directory's unreadable session leaves the next directory extracted, and the run
    still exits nonzero naming it."""
    # If the first typed path holds a session the parser refuses and the second is clean...
    with pytest.raises(SystemExit) as refused:
        extracted(
            tmp_path,
            {Path("/invented/project"): ["invented-wrong-field-type"], Path(MYCELIA): [SPINE]},
            capsys,
            strict=False,
        )

    # ...then both directories were summarised, the refusal counted on its own line...
    printed = capsys.readouterr().out.splitlines()
    assert printed == [
        "/invented/project: 0 session(s) extracted, 0 unchanged, 1 refused",
        f"{MYCELIA}: 1 session(s) extracted, 0 unchanged",
    ]
    # ...the clean session landed...
    assert stored_rows(tmp_path / "traces.duckdb", "SELECT id FROM sessions") == [(SPINE,)]
    # ...and the exit names the refused session and nothing of what it held.
    message = str(refused.value)
    assert "invented-wrong-field-type" in message and "AssistantRecord" in message
    assert "SUPER-SECRET-PAYLOAD-9f2a" not in message


def test_the_tags_typed_at_the_flag_reach_the_store(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`hp extract --tag` stamps its pairs on every session that extract wrote.

    The one leaf that runs the whole path — argparse, the extractor, the exporter — so a flag
    parsed into a namespace nothing reads fails here rather than passing every unit above.
    The pairs are invented, and honestly so: a tag is the caller's word about a run, and no
    transcript records one.
    """
    # If an extract is given two tags, one of whose values carries its own `=`...
    extracted(tmp_path, {Path(MYCELIA): [SPINE]}, capsys, True, "batch_id=b1", "note=a=b")

    # ...then the store holds a row per pair, under the session that extract wrote.
    assert stored_rows(
        tmp_path / "traces.duckdb", "SELECT session_id, key, value FROM session_tags ORDER BY key"
    ) == [(SPINE, "batch_id", "b1"), (SPINE, "note", "a=b")]


def test_an_extract_prints_the_fields_no_model_declares_under_its_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An extract tallies an undeclared field and keeps going; the suite is what crashes.

    A field Claude Code added yesterday is news, and the archive kept the record either way.
    The tally is how a person finds out, so it has to reach the terminal — one line per path,
    with where it was first seen — and it has to say nothing about what the field held.
    """
    # If an extract meets a record carrying a field no model declares, in an extract's own
    # lax mode...
    printed = extracted(tmp_path, {Path(MYCELIA): ["invented-unknown-field"]}, capsys, strict=False)

    # ...then the session is extracted, and the tally follows the summary rather than
    # replacing it.
    assert printed[0] == f"{MYCELIA}: 1 session(s) extracted, 0 unchanged"
    assert printed[1] == "Fields no model declares:"
    assert printed[2].startswith("assistant.shimmerBudget: first in session")
    # And the value the field held is transcript content, which never leaves the store.
    assert "SUPER-SECRET-PAYLOAD-9f2a" not in "\n".join(printed)
    # The run returned rather than exiting: `cli.main` raising `SystemExit` here would fail this
    # leaf, which is where the design's rejection of an exit-code flag is written down.


def test_an_extract_prints_the_record_kinds_no_registry_names(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An extract archives a record kind nobody has read, reports it, and still succeeds.

    The other half of the tally: a kind Claude Code added yesterday is news too, and the
    record went into the archive whole, so there is nothing for an operator to do but read
    the line. Its own header, because a kind and a field are two different pieces of work.
    """
    # If an extract meets a record whose type no registry names, in an extract's own lax mode...
    printed = extracted(tmp_path, {Path(MYCELIA): ["invented-unknown-type"]}, capsys, strict=False)

    # ...then the session lands and the kind is reported under the summary...
    assert printed[0] == f"{MYCELIA}: 1 session(s) extracted, 0 unchanged"
    assert printed[1] == "Record kinds no registry names:"
    assert printed[2].startswith("telepathy: first in session")
    # ...saying nothing about what the record held.
    assert "SUPER-SECRET-PAYLOAD-9f2a" not in "\n".join(printed)


def test_an_extract_names_the_sessions_it_could_not_read_and_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A session the parser refuses leaves the others extracted, and the command exits nonzero.

    The two halves an operator needs: the work that succeeded is in the store, and the run
    does not report success when part of the corpus never arrived. The reason comes with the
    session id, because the next step is a record model.
    """
    # If one session of a project cannot be parsed...
    with pytest.raises(SystemExit) as refused:
        extracted(
            tmp_path, {Path(MYCELIA): [SPINE, "invented-wrong-field-type"]}, capsys, strict=False
        )

    # ...then the summary counts what did land, and what did not...
    printed = capsys.readouterr().out.splitlines()
    assert printed[0] == f"{MYCELIA}: 1 session(s) extracted, 0 unchanged, 1 refused"
    # ...and the failure names the session and what the parser said about it, on the way out.
    message = str(refused.value)
    assert "invented-wrong-field-type" in message and "AssistantRecord" in message
    assert "SUPER-SECRET-PAYLOAD-9f2a" not in message


def test_an_extract_that_finds_nothing_undeclared_prints_only_its_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The negative control: silence is what "the models still describe it" looks like.

    Without this leaf a tally header printed unconditionally would pass the leaf above.
    """
    # If every field of every record is declared — a recorded fixture, under strict mode, so
    # the run would have crashed rather than tallied...
    printed = extracted(
        tmp_path, {Path(MYCELIA): ["invented-no-cache-creation"]}, capsys, strict=True
    )

    # ...then the summary is the whole output.
    assert printed == [f"{MYCELIA}: 1 session(s) extracted, 0 unchanged"]
