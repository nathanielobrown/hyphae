"""`NodeRepository.interjections`: the messages one turn heard while it ran.

Driven against the corpus store as `tests/store/test_nodes.py` is: a turn's messages arrive in
the order its transcript holds them, cut to the section's width and counted before the cap, and
a replayed copy never reaches the page. Split from the other node reads by topic, for the file
budget.
"""

import datetime as dt
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from hyphae.models.citation import Citation
from hyphae.models.node import InterjectionRow
from hyphae.models.trace import Sender
from hyphae.store import library
from hyphae.store.handle import Store, open_store
from hyphae.store.nodes import NodeRepository
from hyphae.view import bounds
from tests.conftest import (
    FORK_ORIGIN,
    MAIN,
    NO_WAIT,
    SENDERS,
    SENDERS_RUN,
    SLASH_TURN,
    SPINE,
)
from tests.store.test_sessions import rows_of
from tests.view.conftest import MISSING, planter
from tests.view.plants import PLANTED_LINES, heard
from tests.view.scenarios import INTERJECTED_TURN

# One expensive store, built once per worker: every leaf here reads the enriched corpus.
pytestmark = pytest.mark.xdist_group("corpus_store")

WIDTHS = bounds.INTERJECTIONS_WIDTHS._asdict()
CHARS = bounds.INTERJECTIONS_WIDTHS.interjection_chars
CAP = bounds.INTERJECTIONS_WIDTHS.interjections
HEARD = {"session_id": SENDERS, "source": SENDERS_RUN, "turn_id": INTERJECTED_TURN}


@pytest.fixture
def store(enriched_db: Path) -> Iterator[Store]:
    with open_store(enriched_db, read_only=True, wait=NO_WAIT) as opened:
        yield opened


@pytest.fixture
def repository(store: Store) -> NodeRepository:
    return store.nodes


def at(clock: str) -> dt.datetime:
    """A recorded instant of 2026-09-07, the day the agent run heard its three messages."""
    return dt.datetime.fromisoformat(f"2026-09-07T{clock}+00:00")


def test_a_turn_hears_its_messages_in_transcript_order_cut_to_the_sections_width(
    store: Store, repository: NodeRepository
) -> None:
    """The agent run's one turn heard a task's notice, then its coordinator, then a second
    notice — each at the line its record sits on, cited with the keys and widths it bound."""
    answer = repository.interjections(**HEARD, widths=WIDTHS)
    # The notices' text is redacted leaf tags; what the row owes the page is the length the
    # width left it, and both came in under it, so they are whole.
    texts = [row.text for row in answer.rows]
    assert [len(text) for text in texts] == [396, 10, 381]
    assert answer.rows == [
        InterjectionRow(
            id="82fd7a6b-8d3a-48a0-8f8e-03155431f1b7",
            sender=Sender.TASK,
            timestamp=at("10:33:04.281"),
            text=texts[0],
            line_no=4,
            matched_rows=3,
        ),
        # ...the coordinator's message, which Claude Code queued with no time of its own and
        # so carries the moment it landed...
        InterjectionRow(
            id="fbfb2868-7ea4-40de-b485-2ad619cb0a22",
            sender=Sender.AGENT,
            timestamp=at("10:40:22.817"),
            text="[redacted]",
            line_no=5,
            matched_rows=3,
        ),
        InterjectionRow(
            id="057236c4-540e-4422-ada0-8df8be93943a",
            sender=Sender.TASK,
            timestamp=at("10:41:23.244"),
            text=texts[2],
            line_no=6,
            matched_rows=3,
        ),
    ]
    assert answer.total == 3
    bindings = {**HEARD, **WIDTHS}
    assert answer.citation == Citation("view_turn_interjections", bindings)
    assert list(answer.citation.bindings) == list(
        library.bind("view_turn_interjections", WIDTHS, {}, **HEARD)
    )


def test_a_turn_that_heard_more_than_the_section_shows_counts_the_rest(
    enriched_db: Path, tmp_path: Path
) -> None:
    """Past the cap the section shows the first messages in transcript order and counts every
    one — the recorded three first, then the planted ones by line — each cut a character past
    the width so the page can mark it."""
    # If every turn hears nine more messages, each longer than the section prints...
    planted = planter(enriched_db, tmp_path)(*heard(CAP + 1, "x" * (CHARS + 5)))
    with open_store(planted, read_only=True, wait=NO_WAIT) as store:
        answer = store.nodes.interjections(**HEARD, widths=WIDTHS)
    # ...the agent run's turn shows its three, then the first five planted by line...
    assert [row.line_no for row in answer.rows] == [
        4,
        5,
        6,
        *range(PLANTED_LINES + 1, PLANTED_LINES + 6),
    ]
    assert [row.id for row in answer.rows[3:]] == [
        f"planted-{INTERJECTED_TURN}-{n:04d}" for n in range(1, 6)
    ]
    # ...counts the twelve it heard, which is what leaves four for the section to say...
    assert answer.total == 12
    assert library.dropped(answer.rows) == 12 - CAP
    # ...and cuts each planted one a character past the width.
    assert {len(row.text) for row in answer.rows[3:]} == {CHARS + 1}


def test_a_turn_that_heard_nothing_and_a_turn_never_held_read_empty(
    repository: NodeRepository,
) -> None:
    """A turn nobody spoke into and an id the store never held both answer no rows and a count
    of nothing, so the page draws no section rather than an empty one."""
    quiet = repository.interjections(
        session_id=SPINE, source=MAIN, turn_id=SLASH_TURN, widths=WIDTHS
    )
    missing = repository.interjections(**{**HEARD, "turn_id": MISSING}, widths=WIDTHS)
    for answer in (quiet, missing):
        assert (answer.rows, answer.total) == ([], 0)


def test_a_replayed_message_never_reaches_the_turn_that_copied_it(
    store: Store, repository: NodeRepository
) -> None:
    """The fork in `fork_origin/` copied the auditor's notice with the prefix it replayed: the
    store keeps both rows, and only the auditor's turn lists one."""
    copies = rows_of(
        store,
        "SELECT source, turn_id, replayed FROM interjections WHERE session_id = $session_id"
        " ORDER BY replayed",
        {"session_id": FORK_ORIGIN},
    )
    assert [(row["source"], row["replayed"]) for row in copies] == [
        ("acbc29008a04b9702", False),
        ("a61a059e3610e6fb4", True),
    ]
    heard_by = {
        row["source"]: repository.interjections(
            session_id=FORK_ORIGIN, source=row["source"], turn_id=row["turn_id"], widths=WIDTHS
        ).total
        for row in copies
    }
    assert heard_by == {"acbc29008a04b9702": 1, "a61a059e3610e6fb4": 0}


def test_a_keyword_left_off_or_a_width_the_statement_lacks_is_refused(
    repository: NodeRepository,
) -> None:
    """The keys and the widths are keywords the statement declares, held by Python and by the
    binder in its own words."""
    interjections: Callable[..., Any] = repository.interjections
    with pytest.raises(TypeError, match="missing"):
        interjections(**HEARD)
    with pytest.raises(TypeError, match="positional"):
        interjections(*HEARD.values(), WIDTHS)
    with pytest.raises(ValueError, match="binds interjection_chars"):
        repository.interjections(**HEARD, widths=bounds.LOG_WIDTHS._asdict())
