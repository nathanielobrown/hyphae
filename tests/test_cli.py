"""The command line's own surface: what each subcommand takes, and what runs it.

Every other tier drives `cli.main` to reach the code under it, so the flags those tiers
happen to pass are covered and the rest are not. This is the file that pins the surface
whole — a flag renamed, a default moved, or a subcommand wired to the wrong handler.
"""

import datetime as dt
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from hyphae import cli, settings
from hyphae.enrich.client import DEFAULT_CONCURRENCY, DEFAULT_MODEL
from hyphae.export.otlp import DEFAULT_MAX_CHARS
from hyphae.export.otlp_delivery import DEFAULT_RATE, GENERIC
from hyphae.extract.layout import DEFAULT_PROJECTS_ROOT
from hyphae.projects import encode_project_path
from hyphae.store_path import HP_DB
from hyphae.view.app import PORT
from tests.conftest import FIXTURES, SPINE, stored_rows
from tests.extract.test_layout import make_projects_root

PROJECT = Path("repos/mycelia")

# The store every parser this file builds defaults to. `--db` resolves out of the environment
# now (`hyphae/store_path.py`), so a suite reading the ambient one would pass or fail with the
# machine it ran on; the fixture below names one instead. What it resolves *from* is
# `tests/test_store_path.py`.
PINNED_DB = Path("/pinned/traces.duckdb")


@pytest.fixture(autouse=True)
def pinned_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(HP_DB, str(PINNED_DB))


# The two zones furthest apart on the planet: UTC+14 and UTC-11, 25 hours from each other, so
# their local dates never agree. That is what lets the zone leaf below force a disagreement at
# any hour rather than waiting for the evenings when local time and UTC happen to differ.
AHEAD_OF_UTC = "Pacific/Kiritimati"
BEHIND_UTC = "Pacific/Midway"


def _utc_today() -> dt.date:
    """The store's own day, which is what `--as-of` defaults to — never the reader's local one."""
    return dt.datetime.now(dt.UTC).date()


@pytest.fixture
def local_zone(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[str], None]]:
    """Move the process's local zone for one test, and put the real one back afterwards.

    `time.tzset` copies `TZ` into the C library, which monkeypatch's environment restore does
    not reach on its own — so undo the variable first, then make the library re-read it.
    """

    def move(zone: str) -> None:
        monkeypatch.setenv("TZ", zone)
        time.tzset()

    yield move
    monkeypatch.undo()
    time.tzset()


# What each subcommand parses to when it is given nothing but the arguments it requires: the
# whole namespace, so a flag added with no leaf here shows up as a failure rather than as an
# untested one. A store subcommand takes `--project` as a filter over a corpus already
# extracted; a discovery one takes it positionally, because it is the corpus. A default the
# clock decides is the clock itself, read when the parser is built rather than when this
# module was imported — a date pinned at import time is wrong for the run that straddles
# midnight. Which clock it reads is pinned separately below.
SURFACES: dict[str, tuple[tuple[str, ...], dict[str, Any]]] = {
    "sessions": (
        (str(PROJECT),),
        {"project": PROJECT, "projects_root": DEFAULT_PROJECTS_ROOT},
    ),
    "extract": (
        (str(PROJECT),),
        {"project": PROJECT, "projects_root": DEFAULT_PROJECTS_ROOT, "db": PINNED_DB, "tag": []},
    ),
    "enrich": (
        (),
        {
            "db": PINNED_DB,
            "project": None,
            "model": DEFAULT_MODEL,
            "dry_run": False,
            "limit": None,
            "concurrency": DEFAULT_CONCURRENCY,
        },
    ),
    "export-otlp": (
        (str(PROJECT),),
        {
            "project": PROJECT,
            "db": PINNED_DB,
            "backend": GENERIC,
            "service_name": None,
            "rate": DEFAULT_RATE,
            "include_text": False,
            "max_chars": DEFAULT_MAX_CHARS,
            "dry_run": False,
        },
    ),
    "query": (
        ("agent_types",),
        {
            "name": "agent_types",
            "db": PINNED_DB,
            "project": None,
            "since": None,
            "as_of": _utc_today,
            "param": [],
            "csv": False,
            "list": False,
        },
    ),
    "view": ((), {"db": PINNED_DB, "port": PORT, "no_browser": False, "dev": False}),
}


@pytest.mark.parametrize("name", sorted(SURFACES))
def test_a_subcommand_parses_to_the_arguments_it_documents(name: str) -> None:
    """Every subcommand's flags and defaults are the ones the command line promises."""
    required, expected = SURFACES[name]
    # The clock is read either side of the build, so the namespace matches one of the two
    # whichever day the parser was built on.
    before = _read_clocks(expected)
    parsed = cli.build_parser().parse_args([name, *required])
    after = _read_clocks(expected)
    assert vars(parsed) in ({"command": name, **before}, {"command": name, **after})


def _read_clocks(expected: dict[str, Any]) -> dict[str, Any]:
    """The expected namespace with each clock-valued default read now."""
    return {key: value() if callable(value) else value for key, value in expected.items()}


def test_the_as_of_default_does_not_move_with_the_reader(
    local_zone: Callable[[str], None],
) -> None:
    """`--as-of` defaults to the same day wherever on the planet the reader's machine sits.

    The window `$as_of` opens is measured in UTC: the runner sets the connection's zone there
    so a corpus doesn't shift by a few hours with the reader (`analyze/runner.py`). A
    local-date default in a zone behind UTC would put the window's upper bound — `$as_of`
    plus a day, at UTC midnight — in the past, dropping the sessions just recorded.

    The surface table above pins which day, but it reads the clock the same way twice, so on
    its own it agrees with a local-date default every day the two spellings coincide. This
    leaf forces them apart at any hour: the two zones sit 25 hours from each other, so their
    local dates never agree, and a default reading the local clock cannot pass this line.
    """
    assert _parse_as_of(local_zone, AHEAD_OF_UTC) == _parse_as_of(local_zone, BEHIND_UTC)


def _parse_as_of(local_zone: Callable[[str], None], zone: str) -> dt.date:
    """What `hp query` defaults `--as-of` to with the machine sitting in `zone`."""
    local_zone(zone)
    return cli.build_parser().parse_args(["query", "agent_types"]).as_of


def test_every_subcommand_the_parser_exposes_is_pinned_above() -> None:
    """The surfaces are checked against the parser, so a seventh subcommand cannot arrive
    unpinned.

    Without this the table above is a list someone maintains rather than the whole surface.
    """
    assert set(cli.SUBCOMMANDS) == set(SURFACES)


def test_the_store_flag_is_one_flag_wherever_it_appears() -> None:
    """`--db` means the same path, typed the same way, in every subcommand that names a store.

    The default is pinned per subcommand above; what this adds is that the five share one
    declaration — same type, same flag — while `sessions` reads transcripts off disk and takes
    no store at all.
    """
    stores = {name for name, (_, options) in SURFACES.items() if "db" in options}
    assert stores == {"extract", "enrich", "export-otlp", "query", "view"}
    for name in sorted(stores):
        required, _ = SURFACES[name]
        parsed = cli.build_parser().parse_args([name, *required, "--db", "elsewhere.duckdb"])
        # A `Path`, not the string argparse hands back untyped.
        assert parsed.db == Path("elsewhere.duckdb"), name


def test_the_store_flag_tells_a_reader_which_archive_it_would_write(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`--help` prints the store the command would use, resolved — not the expression behind
    it.

    The archive lives outside every checkout now, so "where did my sessions go" has to be
    answerable from the command line itself. Printing it also pins that the default is read
    when the parser is built, which is what lets an environment set before the call decide it.
    """
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["extract", "--help"])
    assert str(PINNED_DB) in capsys.readouterr().out


def test_the_query_listing_runs_from_a_directory_with_no_store_under_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`hp query --list` answers from anywhere on the machine, leaving nothing behind.

    The old default was `data/traces.duckdb` under the working directory, so a command run
    outside a checkout addressed a store that did not exist — and one that wrote would have
    made a `data/` wherever it was standing.
    """
    monkeypatch.chdir(tmp_path)
    cli.main("query", "--list")
    assert "session_counts" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []


# Every flag that takes `KEY=VALUE` pairs: the subcommand, the argv that gets it as far as its
# own flags, and the destination the pairs land in. One parser helper serves them all, so the
# contract is pinned once and a new pair-flag joins by adding a row.
PAIR_FLAGS = [
    pytest.param("query", ["query", "agent_types"], "--param", "param", id="param"),
    pytest.param("extract", ["extract", str(PROJECT)], "--tag", "tag", id="tag"),
]


@pytest.mark.parametrize(("subcommand", "argv", "flag", "destination"), PAIR_FLAGS)
def test_a_pair_flag_splits_on_its_first_equals(
    subcommand: str,
    argv: list[str],
    flag: str,
    destination: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A pair flag takes `KEY=VALUE`, repeats, and refuses anything else at the flag.

    The pairs are the caller's own words — a query's bindings, an extract's tags — so a pair
    that does not parse has to stop the run: bound to the wrong name, a value produces a
    plausible answer and no signal.
    """
    # If pairs are given in order, each splitting once so a value keeps its own `=`...
    parsed = cli.build_parser().parse_args([*argv, flag, "first=abc", flag, "note=a=b"])
    # ...they parse to the pairs the run uses, in the order they were typed...
    assert getattr(parsed, destination) == [("first", "abc"), ("note", "a=b")]
    # ...while a pair with no `=`, or one naming nothing, is a parse error against the flag —
    # `dict()` over the split would have taken `=v` as a binding of the empty name.
    for broken in ["nokey", "=v"]:
        with pytest.raises(SystemExit):
            cli.build_parser().parse_args([*argv, flag, broken])
        # The refusal is the last line, under the usage argparse prints above it — and it
        # names the flag, the shape it wanted, and what it was handed instead.
        refusal = capsys.readouterr().err.splitlines()[-1]
        assert refusal == (
            f"hp {subcommand}: error: argument {flag}: takes KEY=VALUE, not {broken!r}"
        )


def test_the_sessions_command_lists_the_transcripts_it_found(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`hp sessions` prints a line per session: its id, its subagents, and its path.

    The subcommand that reads no store — it walks the projects root instead — so nothing else
    drives its handler and a rewiring of it would otherwise land silently.
    """
    # If a project's directory holds two sessions, one of which spawned a subagent...
    project = Path("/Users/nob/repos/mycelia")
    root = make_projects_root(tmp_path, project, ["a-first", "b-second"])
    directory = root / encode_project_path(project)
    (directory / "a-first" / "subagents").mkdir(parents=True)
    (directory / "a-first" / "subagents" / "agent-aaa.jsonl").write_text("")
    # ...then the listing names both, in discovery order, with the count of subagent
    # transcripts under each and the path a reader would open next.
    cli.main("sessions", str(project), "--projects-root", str(root))
    assert capsys.readouterr().out.splitlines() == [
        f"a-first\t1 subagent(s)\t{directory / 'a-first.jsonl'}",
        f"b-second\t0 subagent(s)\t{directory / 'b-second.jsonl'}",
    ]


def test_the_viewer_opens_a_browser_unless_the_run_says_not_to(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`hp view` serves the store it was given, and `--no-browser` is what suppresses
    the tab.

    The one flag on the command line whose value is inverted between the argument and the
    call, and the only subcommand whose handler nothing else drives.
    """
    served: list[tuple[Path, int, bool, bool]] = []
    monkeypatch.setattr(
        cli,
        "serve",
        lambda path, port, *, open_browser, dev: served.append((path, port, open_browser, dev)),
    )
    cli.main("view", "--db", "traces.duckdb", "--port", "9000")
    cli.main("view", "--no-browser")
    # ...and `--dev` is the second inverted-looking one: off unless it is typed, and the only
    # flag that changes what the pages carry rather than how the process starts.
    cli.main("view", "--dev")
    assert served == [
        (Path("traces.duckdb"), 9000, True, False),
        (PINNED_DB, PORT, False, False),
        (PINNED_DB, PORT, True, True),
    ]


def extracted(
    tmp_path: Path,
    fixture: str,
    capsys: pytest.CaptureFixture[str],
    strict: bool,
    *tags: str,
) -> list[str]:
    """Run `hp extract` over one fixture transcript, and hand back what it printed.

    `strict` is what a test run has and an extract does not: the extractor reads it once, at
    construction, so setting it here is setting it for the run. Each of `tags` is one
    `--tag KEY=VALUE` argument, spelled the way a caller types it.
    """
    project = Path("/Users/nob/repos/mycelia")
    root = make_projects_root(tmp_path, project, [fixture])
    source = next(FIXTURES.rglob(f"{fixture}.jsonl"))
    (root / encode_project_path(project) / f"{fixture}.jsonl").write_text(source.read_text())
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(settings, "UNIT_TESTING", strict)
        cli.main(
            "extract",
            str(project),
            "--projects-root",
            str(root),
            "--db",
            str(tmp_path / "traces.duckdb"),
            *[argument for tag in tags for argument in ("--tag", tag)],
        )
    return capsys.readouterr().out.splitlines()


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
    extracted(tmp_path, SPINE, capsys, True, "batch_id=b1", "note=a=b")

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
    printed = extracted(tmp_path, "invented-unknown-field", capsys, strict=False)

    # ...then the session is extracted, and the tally follows the summary rather than
    # replacing it.
    assert printed[0] == "1 session(s) extracted, 0 unchanged"
    assert printed[1] == "Fields no model declares:"
    assert printed[2].startswith("assistant.shimmerBudget: first in session")
    # And the value the field held is transcript content, which never leaves the store.
    assert "SUPER-SECRET-PAYLOAD-9f2a" not in "\n".join(printed)
    # The run returned rather than exiting: `cli.main` raising `SystemExit` here would fail this
    # leaf, which is where the design's rejection of an exit-code flag is written down.


def test_an_extract_that_finds_nothing_undeclared_prints_only_its_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The negative control: silence is what "the models still describe it" looks like.

    Without this leaf a tally header printed unconditionally would pass the leaf above.
    """
    # If every field of every record is declared — a recorded fixture, under strict mode, so
    # the run would have crashed rather than tallied...
    printed = extracted(tmp_path, "invented-no-cache-creation", capsys, strict=True)

    # ...then the summary is the whole output.
    assert printed == ["1 session(s) extracted, 0 unchanged"]
