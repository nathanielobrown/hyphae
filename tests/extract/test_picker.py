"""The rows a bare `hp extract` offers, which of them open checked, and what a confirm means.

`choices()` and `selected()` are pure, so nothing here drives prompt_toolkit: the rows are
`ProjectDir`s built by hand from real recorded working directories.
"""

from pathlib import Path
from typing import Literal

import pytest
from questionary import Choice

from hyphae.extract.discover import ProjectDir
from hyphae.extract.picker import EVERYTHING, choices, selected
from hyphae.projects import encode_project_path
from tests.conftest import MYCELIA

# The mycelia checkout and a worktree cut under it: two directories that share a base, as
# `spine/`'s borrowed `wk-triage` records show. Counts invented; paths as recorded.
MYCELIA_DIR = encode_project_path(Path(MYCELIA))
WK_TRIAGE = Path(MYCELIA) / ".claude" / "worktrees" / "wk-triage"
WK_TRIAGE_DIR = encode_project_path(WK_TRIAGE)
# `invented-truncated-tail`'s `/repo`, which is its own base, and busier this week than mycelia
# so that discovery's order — not the label's — decides the rows; and a directory whose newest
# transcript records no `cwd`, as `fork_byref/`'s does — the name is invented, and its counts
# would place it above `/repo` if the picker sorted on counts alone.
NO_CWD_DIR = "-Users-nob-scratch"
ROWS = [
    ProjectDir("-repo", Path("/gone/-repo"), Path("/repo"), Path("/repo"), 5, 3),
    ProjectDir(MYCELIA_DIR, Path("/gone") / MYCELIA_DIR, Path(MYCELIA), Path(MYCELIA), 3, 2),
    ProjectDir(WK_TRIAGE_DIR, Path("/gone") / WK_TRIAGE_DIR, WK_TRIAGE, Path(MYCELIA), 1, 0),
    ProjectDir(NO_CWD_DIR, Path("/gone") / NO_CWD_DIR, None, None, 2, 1),
]


def fields(choice: Choice) -> tuple[object, object, object]:
    """What a row shows, what a confirm returns for it, and whether it opens checked —
    `Choice` compares by identity, so the tests compare these."""
    return (choice.title, choice.value, choice.checked)


def test_everything_leads_and_a_shared_base_folds_into_one_row() -> None:
    """The picker opens with an Everything row, then one row per repository with its
    directories' counts summed, then the directories that record no working directory."""
    assert [fields(choice) for choice in choices(ROWS, [])] == [
        # The Everything row first, over every directory...
        ("Everything  4 directories, 11 session(s)", EVERYTHING, False),
        # ...then a base nobody else shares standing alone under its own path, first because
        # it is the busiest this week...
        ("/repo  5 session(s), 3 this week", ["-repo"], False),
        # ...then the mycelia checkout and its worktree as one row, counts summed, the
        # worktree counted as one more directory...
        (
            f"{MYCELIA}  4 session(s), 2 this week, +1 directories",
            [MYCELIA_DIR, WK_TRIAGE_DIR],
            False,
        ),
        # ...and a directory with no `cwd` last whatever its counts, under its own name.
        (f"{NO_CWD_DIR}  2 session(s), 1 this week", [NO_CWD_DIR], False),
    ]


def checked(remembered: list[str] | Literal["all"]) -> list[object]:
    """The values of the rows that open checked when `remembered` was picked last time."""
    return [choice.value for choice in choices(ROWS, remembered) if choice.checked]


def test_a_grouped_row_opens_checked_when_any_member_was_picked() -> None:
    """Remembering the worktree's directory checks the repository row it folded into."""
    assert checked([WK_TRIAGE_DIR]) == [[MYCELIA_DIR, WK_TRIAGE_DIR]]


def test_remembered_everything_checks_only_the_everything_row() -> None:
    """A last pick of "all" reopens with Everything checked and no repository row checked."""
    assert checked(EVERYTHING) == [EVERYTHING]


def test_a_remembered_name_no_longer_on_disk_checks_nothing() -> None:
    """A directory Claude Code pruned since the last pick is neither checked nor an error."""
    assert checked(["-gone"]) == []


def test_a_confirm_flattens_the_picked_rows_to_directory_names() -> None:
    """Confirming rows yields every directory behind them; confirming Everything yields
    the word for every directory, whatever else was checked."""
    assert selected([[MYCELIA_DIR, WK_TRIAGE_DIR], ["-repo"]]) == [
        MYCELIA_DIR,
        WK_TRIAGE_DIR,
        "-repo",
    ]
    assert selected([["-repo"], EVERYTHING]) == EVERYTHING


@pytest.mark.parametrize("answer", [[], None], ids=["nothing checked", "ctrl-c"])
def test_a_confirm_with_nothing_chosen_exits_with_a_message(
    answer: list[object] | None,
) -> None:
    """Confirming an empty selection, or quitting the prompt, ends the run saying so."""
    with pytest.raises(SystemExit, match="Nothing picked"):
        selected(answer)
