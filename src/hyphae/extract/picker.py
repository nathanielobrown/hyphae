"""The multi-select a bare `hp extract` opens over every project Claude Code has recorded.

One row per repository (`ProjectDir.base`), with the directories under it folded in and their
counts summed; an Everything row above them; the directories that record no working directory
below. `choices()` and `selected()` are pure, so the tests drive them; `pick()` alone runs
the prompt.
"""

from collections import defaultdict
from typing import Final, Literal, NamedTuple

import questionary

from hyphae.extract.discover import ProjectDir

# The settings value, and the Everything row's value, for every directory under the root.
EVERYTHING: Final = "all"


def choices(
    rows: list[ProjectDir], remembered: list[str] | Literal["all"]
) -> list[questionary.Choice]:
    """The Everything row, then one row per base project, then the rows with no base.

    A row's value is the directory names behind it, so a confirm flattens to what
    `settings.json` stores. A row opens checked when any directory behind it is remembered;
    only Everything is checked when `"all"` is.
    """
    by_base: dict[str, list[ProjectDir]] = defaultdict(list)
    alone: list[ProjectDir] = []
    for row in rows:
        if row.base is None:
            alone.append(row)
        else:
            by_base[str(row.base)].append(row)
    folds = [_Fold(label, members) for label, members in by_base.items()]
    folds += [_Fold(row.label, [row]) for row in alone]
    # Grouped rows first, each block in discovery's order: recent, then sessions, then label.
    folds.sort(key=lambda fold: (fold.ungrouped, -fold.recent, -fold.sessions, fold.label))
    remembered_names = set() if remembered == EVERYTHING else set(remembered)
    everything = questionary.Choice(
        f"Everything  {len(rows)} directories, {sum(row.sessions for row in rows)} session(s)",
        value=EVERYTHING,
        checked=remembered == EVERYTHING,
    )
    return [everything] + [
        questionary.Choice(
            fold.title,
            value=[row.name for row in fold.members],
            checked=any(row.name in remembered_names for row in fold.members),
        )
        for fold in folds
    ]


class _Fold(NamedTuple):
    """The directories one picker row stands for: a base project's, or one with no base."""

    label: str
    members: list[ProjectDir]

    @property
    def ungrouped(self) -> bool:
        return self.members[0].base is None

    @property
    def sessions(self) -> int:
        return sum(row.sessions for row in self.members)

    @property
    def recent(self) -> int:
        return sum(row.recent for row in self.members)

    @property
    def title(self) -> str:
        title = f"{self.label}  {self.sessions} session(s), {self.recent} this week"
        if len(self.members) > 1:
            title += f", +{len(self.members) - 1} directories"
        return title


def selected(answer: list[list[str] | Literal["all"]] | None) -> list[str] | Literal["all"]:
    """What a confirm means: every directory name behind the checked rows, or `"all"`.

    questionary answers `None` to Ctrl-C; that and an empty confirm end the run with a
    message, so nothing is written or extracted. The values are the ones `choices` built,
    so anything else here is a bug that should crash rather than be dropped.
    """
    if not answer:
        raise SystemExit("Nothing picked: nothing extracted, and the last pick stands")
    if EVERYTHING in answer:
        return EVERYTHING
    return [name for names in answer for name in names]


def pick(
    rows: list[ProjectDir], remembered: list[str] | Literal["all"]
) -> list[str] | Literal["all"]:
    """Run the checkbox over `rows` and return what was confirmed, as `selected` reads it."""
    answer = questionary.checkbox(
        "Projects to extract",
        choices=choices(rows, remembered),
        use_search_filter=True,
        # questionary refuses the filter while j/k move the cursor: a typed j would be both.
        use_jk_keys=False,
    ).ask()
    return selected(answer)
