"""The prompt half of each enrichment level, declared once per level.

A level is a prompt, a set of rows, and a reader that finds them. `LEVELS` holds the prompt
and the reader, so adding one is one entry here beside the renderer it names — rather than
an edit to a subject map, a budget constant, a render dispatch, a reader map and a round
order, none of which would complain about being forgotten. The rows half — the table, its
keys and the prompt version a row is stamped with — is `models/enrichment.py:ROWS`, keyed by
the same `Level`, because the viewer reads it and may not import this package.

The entries are written in round order: bottom-up, because every prompt embeds its children's
descriptions rather than their text.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from hyphae.enrich import prompts
from hyphae.enrich.prompts import Budgets
from hyphae.models.enrichment import Level
from hyphae.models.items import Item


@dataclass(frozen=True)
class LevelSpec:
    """One level's prompt: what it sends the model, and what reads the items it describes."""

    # What this level is looking at. The rest of the instructions is the same everywhere, so a
    # level reads differently only where it should.
    subject: str
    budgets: Budgets
    # This level's render, taking this level's item. The registry is keyed by level and an
    # item names its own level, so `render` cannot hand a renderer the wrong item.
    renderer: Callable[[Any, Budgets], str]
    # The `EnrichmentStore` method that reads this level's items. Named rather than bound: the
    # store imports this module, so a spec cannot hold one of its methods.
    reader: str
    # Instruction paragraphs this level alone carries, past the shared guidance.
    riders: tuple[str, ...] = ()


# Closed set: a level missing here gets no round at all.
LEVELS: dict[Level, LevelSpec] = {
    Level.agent_run: LevelSpec(
        subject=(
            "You are reading one run of a subagent: the task it was given, any later "
            "instructions, and what it did about them. Describe that run."
        ),
        # The same cap a main turn gets: a run holds the same kind of work, and 209 of 2,458
        # recorded runs reach it.
        budgets=Budgets(total=30_000),
        renderer=prompts.render_run,
        reader="run_items",
    ),
    Level.turn: LevelSpec(
        subject=(
            "You are reading one turn of a coding session: what the person asked for, and "
            "what the agent did about it. Describe that turn."
        ),
        budgets=Budgets(total=30_000),
        renderer=prompts.render_turn,
        reader="turn_items",
    ),
    Level.session: LevelSpec(
        subject=(
            "You are reading a summary of one coding session: what it cost, and a description "
            "of each thing it did, in order. Describe the session as a whole."
        ),
        # Smaller: a session carries one line per child rather than a transcript. Sessions
        # average 3.1 children and the longest recorded one has 92.
        budgets=Budgets(total=24_000),
        renderer=prompts.render_session,
        reader="session_items",
        riders=(prompts.RELAYING,),
    ),
}

# The levels a run describes, in the order it describes them — the order they are written in
# above. The agent runs are themselves split into rounds by parentage.
ROUND_ORDER = tuple(LEVELS)


def render(item: Item) -> str:
    """One item as its level's prompt, at that level's budgets.

    The enricher's one door into the renders. Take a `prompts.render_*` function directly to
    pass budgets, as the tests do.
    """
    spec = LEVELS[item.level]
    return spec.renderer(item, spec.budgets)


def instructions(level: Level) -> str:
    """The system prompt for one level. Versioned by `ROWS[level].prompt_version`, not by the
    hash."""
    spec = LEVELS[level]
    return prompts.instructions(spec.subject, *spec.riders)
