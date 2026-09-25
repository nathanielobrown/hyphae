"""The messages a turn heard while it ran, listed under its pane's own values.

A turn's page lists what was delivered into it mid-turn — a person's message, another agent's,
a task's notice — in the order the model read them: who sent each, when, the start of it, and
the line of the transcript holding the rest. Every other kind of node draws no section.
"""

import duckdb
import pytest
from fastapi.testclient import TestClient

from hyphae.view import bounds
from hyphae.view.app import build_app
from hyphae.view.text.format import ELLIPSIS
from tests.conftest import (
    INTERJECTION,
    MAIN,
    RELAYED,
    RELAYED_RUN,
    SENDERS,
    SENDERS_RUN,
    SLASH_TURN,
    SPINE,
)
from tests.view.conftest import Planter, fields, inside, marked_up, one, values
from tests.view.plants import heard
from tests.view.scenarios import INTERJECTED_TURN

HEARD_URL = f"/session/{SENDERS}/thread/{SENDERS_RUN}/turn/{INTERJECTED_TURN}"
CHARS = bounds.INTERJECTIONS_WIDTHS.interjection_chars
CAP = bounds.INTERJECTIONS_WIDTHS.interjections


@pytest.mark.parametrize(
    ("session", "source", "turn", "heard"),
    [
        # A run's turn heard a task's notice, its coordinator, then a second notice, each as a
        # queued command...
        (
            SENDERS,
            SENDERS_RUN,
            INTERJECTED_TURN,
            [
                ("82fd7a6b-8d3a-48a0-8f8e-03155431f1b7", "task", "10:33:04"),
                ("fbfb2868-7ea4-40de-b485-2ad619cb0a22", "agent", "10:40:22"),
                ("057236c4-540e-4422-ada0-8df8be93943a", "task", "10:41:23"),
            ],
        ),
        # ...and another's heard a task, its coordinator, the person and a second task, each
        # as a `user` record under a lead line naming the sender.
        (
            RELAYED,
            RELAYED_RUN,
            "d48b3cc4-5b03-4e41-b0f7-a813718dbb97",
            [
                ("c4fa6668-27bc-4a26-84f4-d70ab9ea80ab", "task", "19:16:38"),
                ("63f2e609-c1cf-4603-acae-2c720f49520c", "agent", "19:18:10"),
                ("28f67c95-2183-4e7f-8e2a-8d5a709c9fff", "person", "19:25:00"),
                ("1bcc625c-8915-4240-b18a-27a44c7a986a", "task", "19:32:22"),
            ],
        ),
    ],
    ids=["queued", "relayed"],
)
def test_a_turn_lists_what_it_heard_between_its_values_and_its_calls(
    client: TestClient,
    store: duckdb.DuckDBPyConnection,
    session: str,
    source: str,
    turn: str,
    heard: list[tuple[str, str, str]],
) -> None:
    """Each row of what a run's turn heard says who and when, carries the message whole, and
    links the line it was read from — and the page cites the read."""
    page = client.get(f"/session/{session}/thread/{source}/turn/{turn}").text
    # The section sits under the turn's own values and above the log of its api calls...
    assert page.index('data-body="turn"') < page.index('class="interjections"')
    assert page.index('class="interjections"') < page.index("data-child=")
    # ...counts what it heard, and lists it in transcript order...
    keys = values(page, "data-interjection")
    assert keys == [key for key, _, _ in heard]
    assert fields(page, "class", "interjections")["interjections"] == str(len(heard))
    for key, sender, at in heard:
        # ...each row whole: the message as the store holds it, which none ran past the width
        # of — the notices' leaf tags are redacted to the lengths they were recorded at...
        text, line_no = one(
            store,
            "SELECT i.text, max(r.line_no) FROM interjections i JOIN raw_records r"
            " ON r.session_id = i.session_id AND r.source = i.source AND r.uuid = i.id"
            " WHERE i.session_id = ? AND i.source = ? AND i.id = ? GROUP BY i.text",
            [session, source, key],
        )
        assert len(text) < CHARS
        assert fields(page, "data-interjection", key) == {
            "sender": sender,
            "at": at,
            "line": f"line {line_no}",
            "text": text.strip(),
        }
        # ...and its link opens the records page on the line holding the whole record.
        (href,) = inside(page, "data-interjection", key, "href")
        records = client.get(href).text
        assert href.endswith(f"#L{line_no}")
        assert values(records, "data-record")[0] == str(line_no)
    # Nothing was left off, so nothing says so, and the footer cites the read at the keys and
    # widths it bound.
    assert 'data-field="dropped"' not in page
    assert fields(page, "id", "citation")["view_turn_interjections"] == (
        f"-- queries/view_turn_interjections.sql session_id={session} source={source}"
        f" turn_id={turn} interjection_chars={CHARS} interjections={CAP}"
    )


def test_a_turn_that_heard_more_than_the_section_shows_says_how_many_it_left_off(
    plant: Planter,
) -> None:
    """Past the cap the section lists the first messages it heard and counts the rest, and a
    message longer than the section prints is cut and marked where it stopped."""
    # If every turn heard nine more messages, each a tag past the section's width...
    text = "<status>" + "x" * CHARS
    with TestClient(build_app(plant(*heard(CAP + 1, text)))) as planted:
        page = planted.get(HEARD_URL).text
    # ...the turn lists as many as the section holds, counts the twelve it heard...
    listed = values(page, "data-interjection")
    assert len(listed) == CAP
    section = fields(page, "class", "interjections")
    assert section["interjections"] == "12"
    # ...and says what it left: every one it heard, less what it listed.
    assert section["dropped"] == str(12 - CAP)
    # A planted message stops at the width with the mark after it, and the tag in it is text
    # the page printed rather than an element it opened.
    planted_key = listed[-1]
    cut = fields(page, "data-interjection", planted_key)["text"]
    assert cut == (text[:CHARS] + ELLIPSIS).strip()
    assert marked_up(page, "data-interjection", planted_key, "text").startswith("&lt;status&gt;")


def test_a_node_that_heard_nothing_draws_no_section(client: TestClient) -> None:
    """A turn nobody spoke into, and every kind that is not a turn, carry no section at all
    rather than an empty one — though the turn asked, and cites the read that answered none."""
    quiet = client.get(f"/session/{SPINE}/thread/{MAIN}/turn/{SLASH_TURN}").text
    assert 'class="interjections"' not in quiet
    assert "view_turn_interjections" in fields(quiet, "id", "citation")
    for url in (f"/session/{SENDERS}", f"/session/{SENDERS}/run/{SENDERS_RUN}"):
        page = client.get(url).text
        assert 'class="interjections"' not in page, url
        assert "view_turn_interjections" not in fields(page, "id", "citation"), url


def test_a_message_before_the_first_prompt_is_on_no_turn_but_on_the_records_page(
    client: TestClient, store: duckdb.DuckDBPyConnection
) -> None:
    """The notice `interjection/` recorded before its session's first prompt belongs to no
    turn, so no turn's page lists it; the thread's records page still holds its line."""
    early = "36b2e375"
    (key, line_no) = one(
        store,
        "SELECT i.id, r.line_no FROM interjections i JOIN raw_records r"
        " ON r.session_id = i.session_id AND r.source = i.source AND r.uuid = i.id"
        " WHERE i.session_id = ? AND i.id LIKE ? AND i.turn_id IS NULL",
        [INTERJECTION, f"{early}%"],
    )
    turns = store.execute(
        "SELECT id FROM turns WHERE session_id = ? AND source = ?", [INTERJECTION, MAIN]
    ).fetchall()
    assert len(turns) == 3
    for (turn_id,) in turns:
        page = client.get(f"/session/{INTERJECTION}/thread/{MAIN}/turn/{turn_id}").text
        assert key not in values(page, "data-interjection"), turn_id
    records = client.get(f"/session/{INTERJECTION}/thread/{MAIN}/records").text
    assert str(line_no) in values(records, "data-record")
