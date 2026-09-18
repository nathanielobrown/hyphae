"""The enrichment vocabulary: what gets described, the closed words it is described in, where
each level's rows live, the versions this build writes them under, the row a store holds — an
`Enrichment` and the `Stamp` it was written under — and the row a page reads back, cut.

`Level` names the three things that get an enrichment row. `Category` and `Outcome` are the
taxonomy every level is written in — closed and code-resident on purpose: `GROUP BY category`
only means something over a fixed set, and the code that validates a model's answer is the
code a reviewer reads. A member added here is a taxonomy change — bump `TAXONOMY_VERSION`
with it, which makes every existing row stale without invalidating it, so the viewer can
render version-N rows while version-N+1 backfills.

Here rather than in `enrich` because a reader with no prompt in hand — the viewer judging a
row `stale`, the store writing one — needs the words, the table, today's versions and the
row's shape, and neither `view` nor the store imports `enrich`. The prompts stay there
(`enrich/levels.py:LEVELS`), as do the staleness rule (`enrich/stamp.py`) and the validator
that turns an answer into an `Enrichment` (`enrich/validation.py`).
"""

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass, fields
from enum import StrEnum
from typing import NamedTuple

from pydantic.dataclasses import dataclass as row_model

from hyphae.models.citation import Citation
from hyphae.models.row import ROW


class Level(StrEnum):
    """The three things that get an enrichment row, each with its own table and prompt."""

    turn = "turn"
    agent_run = "agent_run"
    session = "session"


class Category(StrEnum):
    """What kind of work an item was. One member per kind of session, turn, or agent run."""

    design = "design"
    implement = "implement"
    fix_bug = "fix_bug"
    refactor = "refactor"
    test = "test"
    debug = "debug"
    review = "review"
    analyze = "analyze"
    document = "document"
    configure = "configure"
    vcs_ops = "vcs_ops"
    explore = "explore"
    chat = "chat"
    other = "other"


class Outcome(StrEnum):
    """How the item ended, as the transcript shows it — not whether the work was good."""

    completed = "completed"
    partial = "partial"
    failed = "failed"
    abandoned = "abandoned"
    unclear = "unclear"


# What each member means, in one line. Data rather than comments because the prompt is
# written from these: a definition the classifier never sees is a definition that drifts.
# Every member needs an entry — nothing here may be defaulted or skipped.
CATEGORY_DEFINITIONS: dict[Category, str] = {
    Category.design: "Deciding how something should work, before it is built.",
    Category.implement: "Building something that did not exist.",
    Category.fix_bug: "Making broken behaviour correct, with the fix already known.",
    Category.refactor: "Changing structure without changing behaviour.",
    Category.test: "Writing or fixing tests, and running suites.",
    Category.debug: (
        "Hunting the cause of a failure that already happened — reproducing, instrumenting, "
        "bisecting. Not searching a change for defects it might have."
    ),
    Category.review: (
        "Judging a change someone else made — reading it, probing it, testing it for defects."
    ),
    Category.analyze: "Answering a question from data or code — measurement, census, findings.",
    Category.document: "Writing prose: docs, comments, commit messages, reports.",
    Category.configure: "Tooling, dependencies, CI, environment, editor and agent settings.",
    Category.vcs_ops: "Branches, commits, rebases, PRs, merges — version control as the work.",
    Category.explore: "Finding out what is there, with no change intended yet.",
    Category.chat: "Conversation that drives no work: a question, an aside, an interruption.",
    Category.other: "Fits none of the above. A growing share here says the taxonomy needs work.",
}

OUTCOME_DEFINITIONS: dict[Outcome, str] = {
    Outcome.completed: "What was asked was done.",
    Outcome.partial: "Some of what was asked landed; the rest did not.",
    Outcome.failed: "It was attempted and did not work.",
    Outcome.abandoned: "Dropped before an answer — interrupted, or redirected onto something else.",
    Outcome.unclear: "The records do not say how it ended.",
}


# Bumped whenever a member above changes meaning, arrives, or leaves. Rows record the
# version they were written under, so a bump re-enriches rather than corrupting a mixed set.
TAXONOMY_VERSION = 2


@dataclass(frozen=True)
class LevelRows:
    """Where one level's rows live, and the prompt version this build writes them under.

    The half of a level a reader or writer needs with no prompt in hand. The prompt itself,
    its budgets and its render are `enrich/levels.py:LEVELS`, keyed by the same `Level`.
    """

    # Covers what a row's input hash cannot see: the level's instructions and output schema
    # in `enrich/prompts.py`. Bump it with them and the level re-enriches; its parents follow
    # through the hash.
    prompt_version: int
    table: str
    # The enrichment table's primary key columns, in order.
    keys: tuple[str, ...]
    # The view holding the rows enrichment describes, and the columns matching `keys`.
    base: str
    base_keys: tuple[str, ...]


# Closed set, in the order a pass describes the levels: a level here with no table in
# `store/enrichment.py`'s DDL cannot be written, and a table there with no level here would never
# be swept.
ROWS: dict[Level, LevelRows] = {
    Level.agent_run: LevelRows(
        prompt_version=4,
        table="agent_run_enrichments",
        keys=("session_id", "agent_run_id"),
        base="live_agent_runs",
        base_keys=("session_id", "id"),
    ),
    Level.turn: LevelRows(
        prompt_version=4,
        table="turn_enrichments",
        keys=("session_id", "source", "turn_id"),
        # `live_turns`, not `turns`: a fork's replay of another transcript's turn is a copy,
        # and the turn it copied is enriched under the transcript that ran it.
        base="live_turns",
        base_keys=("session_id", "source", "id"),
    ),
    Level.session: LevelRows(
        prompt_version=4,
        table="session_enrichments",
        keys=("session_id",),
        # `describable_sessions`, not `sessions`: a row for a session the pass will never
        # refresh again is a zombie by the same definition as one whose session is gone, and
        # 45 such rows are already on disk from before the gate existed.
        base="describable_sessions",
        base_keys=("session_id",),
    ),
}


@dataclass(frozen=True)
class Versions:
    """The half of the stamp the code decides.

    A pass adds the hash and the model; a reader with no pass in hand can still judge a row
    against this half. Passed rather than read, so a test bumps a version by handing over a
    different value instead of patching the declaration.
    """

    prompt: Mapping[Level, int]
    taxonomy: int

    @classmethod
    def current(cls) -> "Versions":
        """What the declarations say today — the whole of what `hp enrich` runs under."""
        return cls(
            prompt={level: rows.prompt_version for level, rows in ROWS.items()},
            taxonomy=TAXONOMY_VERSION,
        )

    def moved_past(self, level: Level, *, prompt_version: int, taxonomy_version: int) -> bool:
        """Whether this build has moved past a row's versions.

        Two of the four axes: the hash needs a render and the model needs a pass, so a reader
        holding only a stored row gets the verdict those two can support and no more.
        """
        return prompt_version != self.prompt[level] or taxonomy_version != self.taxonomy


@dataclass(frozen=True)
class Enrichment:
    """One accepted model answer about one item."""

    # One or two sentences saying what the item did.
    description: str
    category: Category
    outcome: Outcome
    # One line naming visible struggle — retries, errors, backtracking. None when the
    # records show none, which is the common case.
    friction: str | None


@dataclass(frozen=True)
class Stamp:
    """What a row was written under. A row is current when its stamp equals today's."""

    # sha256 of the rendered prompt content — not of the instructions, which
    # `prompt_version` covers.
    input_hash: str
    prompt_version: int
    taxonomy_version: int
    model: str


# The stamp's columns, in field order. A writer binds `astuple(stamp)` against this and a
# reader unpacks `Stamp(*row)` from it, so the two cannot drift from the fields above.
COLUMNS: tuple[str, ...] = tuple(field.name for field in fields(Stamp))


@row_model(frozen=True, config=ROW)
class DescribedItem:
    """One item as a pass described it, cut for a page: a `view_enrichment` row.

    Built by column name off the statement (`store/enrichment.py:described`), under `row.ROW`,
    so a column the statement gains or loses raises at the read.
    """

    # Which level's table the row came from, as the statement spells it — the `Level` value.
    # A string rather than the enum because the row config is strict, and strict mode reads
    # a value into an enum only from a member.
    level: str
    # The turn, run or session the row is about: the level's last key column.
    item_id: str
    # The head, one character past the width — the cut-and-mark protocol every fat value
    # rides (`view/text/format.py:cut`) — beside how long the whole runs.
    description: str
    description_chars: int
    category: str
    outcome: str
    # None where the model saw no friction, which is most items.
    friction: str | None
    friction_chars: int | None
    # Which model wrote the row and when, and the two versions it was written under: what a
    # page judges `stale` from, and what its provenance line prints.
    model: str
    enriched_at: dt.datetime
    prompt_version: int
    taxonomy_version: int


class Described(NamedTuple):
    """What a pass wrote about one session at every level, and the read that answered it."""

    rows: list[DescribedItem]
    citation: Citation
