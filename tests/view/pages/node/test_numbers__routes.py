"""What the three numbers routes answer when there is nothing, and what each one cites.

The numbers themselves are `test_numbers.py`, which these leaves borrow their two readers from.
Split off because a route's refusal is not a reading: what is checked here is the status, the
sentence and the citation line — the things a popover carries whatever its figures say.
"""

from fastapi.testclient import TestClient

from hyphae.view.nodes import NUMBERS_URL, Kind
from tests.conftest import ANCESTOR, DENSE_TOOL, FORK_ORIGIN, FORK_ORIGIN_RUN, MAIN, SPINE
from tests.view.conftest import MISSING, fields, values
from tests.view.pages.node.test_numbers import popped


def test_a_kind_with_no_numbers_is_a_route_that_answers_nothing(client: TestClient) -> None:
    """A bucket has nothing to print, so the route 404s rather than serving an empty popover.

    A bucket is a place rather than a node — it stands for no row of the store — so there is
    nothing to count under it. Every kind that does stand for a row now carries a popover, the
    compaction included: what it shows is `tests/view/pages/node/test_numbers__compaction.py`.
    """
    for path in (
        f"/session/{ANCESTOR}/thread/{MAIN}/{Kind.UNATTRIBUTED}/{MAIN}",
        f"/session/{ANCESTOR}/thread/{MAIN}/{Kind.UNATTACHED}/{ANCESTOR}",
    ):
        assert client.get(f"{NUMBERS_URL}{path}").status_code == 404


def test_a_numbers_route_for_a_node_that_is_not_there_refuses_in_that_kinds_words(
    client: TestClient,
) -> None:
    """A popover for an id the thread lacks says which kind it went looking for.

    Two kinds can be missing here and no others: a tool call and a compaction are read row by
    row, while every other kind's numbers query aggregates and answers a row for a node that is
    not there as readily as for one that is — which the popover prints as its dashes.

    The sentences are written out rather than read off `pages/node/kinds.py`: an oracle that
    imported the table would agree with whatever it said. They are the table's, though, which is
    what makes a stale link refuse in the same words wherever it pointed — the node's own page
    answers each of these too.
    """
    for kind, expected in (
        (Kind.TOOL, "No tool call with that id is in this thread."),
        (Kind.COMPACTION, "No compaction with that id is in this thread."),
    ):
        refused = client.get(f"{NUMBERS_URL}/session/{SPINE}/thread/{MAIN}/{kind}/{MISSING}")
        assert refused.status_code == 404
        assert fields(refused.text, "id", "error")["message"] == expected


def test_the_two_numbers_queries_cite_themselves_the_way_the_compaction_does(
    client: TestClient,
) -> None:
    """A node's popover and a tool call's each carry the query and the keys they were fetched by.

    A popover arrives on a page already served, so it cannot ride the footer the pages share:
    `tests/view/test_query.py` reads pages and skips every `/fragment/` route, and `test_app.py`
    sweeps the whole-value fetches. `test_numbers__compaction.py` holds the third numbers query;
    these are the other two.

    The widths ride the line because they are part of the answer — the statement cuts to the
    surface the popover named (`view/bounds.py`), so a line without them is one nobody can paste
    into `hp query` and get this box back.
    """
    assert values(popped(client, f"/session/{SPINE}"), "data-query") == [
        f"-- queries/view_numbers.sql session_id={SPINE} source={MAIN} node_id={SPINE}"
        f" kind={Kind.SESSION} model_chars=60"
    ]
    tool = f"/session/{FORK_ORIGIN}/thread/{FORK_ORIGIN_RUN}/{Kind.TOOL}/{DENSE_TOOL}"
    assert values(popped(client, tool), "data-query") == [
        f"-- queries/view_numbers_tool.sql session_id={FORK_ORIGIN} source={FORK_ORIGIN_RUN}"
        f" tool_call_id={DENSE_TOOL} item_chars=60 head_items=5"
    ]
