"""What one read binds: the keys it is about, the surface's widths, and the reader's sizes.

`library.bind` is the seam every read fills its statement through, so these leaves are about
the mapping it hands back rather than about rows: the same keys and values the routes used to
spell by hand, in the same order, because that mapping is what the citation under the page
quotes (`view/citation.py`). Nothing here opens a connection — a read short of a parameter is
refused before the store is touched, which is the whole reason the function exists.

The shipped query files are the world here: the parameters a statement declares are read off
its own text (`store/library.py:parameters`), and the population is the catalog rather than a
query enum, so a statement cannot leave the sweep by leaving an enum. One leaf plants a `.sql`
of its own, and says so.
"""

from pathlib import Path

import pytest

from hyphae.analyze import manifest
from hyphae.models.citation import ParamValue
from hyphae.store import library
from hyphae.store.library import bind
from hyphae.view import bounds
from tests.conftest import MAIN, SLASH_TURN, SPINE
from tests.store.test_catalog import viewer_statements

# Every statement the viewer reads, at the surface its production read fills it from: spelled
# by hand, so a statement that ships under `view_` with no entry here is a red rather than a
# guess. A statement that binds no width is listed at the surface of the page it serves, and
# the sweep proves it takes nothing from it.
SURFACES: dict[str, bounds.Widths] = {
    "view_call_header": bounds.EXPANSION_WIDTHS,
    "view_call_text": bounds.HEADER_WIDTHS,
    "view_call_thinking": bounds.HEADER_WIDTHS,
    "view_call_tools": bounds.LOG_WIDTHS,
    "view_compactions": bounds.NAV_TREE_WIDTHS,
    "view_described_sessions": bounds.LIST_WIDTHS,
    "view_enrichment": bounds.ENRICHMENT_WIDTHS,
    "view_nav_tree_calls": bounds.NAV_TREE_WIDTHS,
    "view_nav_tree_tools": bounds.NAV_TREE_WIDTHS,
    "view_nav_tree_turns": bounds.NAV_TREE_WIDTHS,
    "view_numbers": bounds.POPOVER_WIDTHS,
    "view_numbers_compaction": bounds.POPOVER_WIDTHS,
    "view_numbers_tool": bounds.POPOVER_WIDTHS,
    "view_offload": bounds.RECORDS_WIDTHS,
    "view_project_rollups": bounds.PROJECTS_WIDTHS,
    "view_projects": bounds.LIST_WIDTHS,
    "view_record": bounds.RECORDS_WIDTHS,
    "view_records": bounds.RECORDS_WIDTHS,
    "view_run_brief": bounds.HEADER_WIDTHS,
    "view_run_description": bounds.HEADER_WIDTHS,
    "view_run_friction": bounds.HEADER_WIDTHS,
    "view_run_header": bounds.EXPANSION_WIDTHS,
    "view_run_prompt": bounds.HEADER_WIDTHS,
    "view_run_result": bounds.HEADER_WIDTHS,
    "run_timeline": bounds.NAV_TREE_WIDTHS,
    "view_runs": bounds.NAV_TREE_WIDTHS,
    "view_session_description": bounds.HEADER_WIDTHS,
    "view_session_errors": bounds.ERRORS_WIDTHS,
    "view_session_friction": bounds.HEADER_WIDTHS,
    "view_session_header": bounds.HEADER_WIDTHS,
    "session_timeline": bounds.NAV_TREE_WIDTHS,
    "view_sessions": bounds.LIST_WIDTHS,
    "view_tool_command": bounds.HEADER_WIDTHS,
    "view_tool_header": bounds.EXPANSION_WIDTHS,
    "view_tool_input": bounds.HEADER_WIDTHS,
    "view_tool_result": bounds.HEADER_WIDTHS,
    "view_turn_calls": bounds.LOG_WIDTHS,
    "view_turn_command_args": bounds.HEADER_WIDTHS,
    "view_turn_description": bounds.HEADER_WIDTHS,
    "view_turn_friction": bounds.HEADER_WIDTHS,
    "view_turn_header": bounds.EXPANSION_WIDTHS,
    "view_turn_interjections": bounds.INTERJECTIONS_WIDTHS,
    "view_turn_prompt": bounds.HEADER_WIDTHS,
    "view_turn_records": bounds.RECORDS_WIDTHS,
}
# The sizes a read takes when the URL asked for none.
NO_SIZES: dict[str, ParamValue] = {}


def test_every_viewer_statement_has_a_surface_here_and_nothing_else_does() -> None:
    """The sweep below runs over the catalog, so the map is held to it from both sides."""
    assert set(SURFACES) == viewer_statements()


@pytest.mark.parametrize("name", sorted(SURFACES))
def test_every_statement_binds_exactly_the_parameters_it_declares(name: str) -> None:
    """One read per viewer statement, filled from its surface and placeholder keys: nothing
    short, nothing over, every name the file declares.

    The declared list is read off the statement (`store/library.py:parameters`) and off
    nothing else — not the manifest's production defaults, which are `hp query`'s and belong
    to no page. Whatever the surface does not carry goes in as a key; the value is a
    placeholder because `bind` checks names and hands a value through as it came.
    """
    declared = library.parameters(library.statement(name))
    widths = SURFACES[name]._asdict()
    keys = {parameter: 1 for parameter in declared if parameter not in widths}
    filled = bind(name, widths, NO_SIZES, **keys)
    assert sorted(filled) == sorted(declared)


@pytest.mark.parametrize(
    ("name", "keys"),
    [
        ("session_timeline", {"session_id": SPINE}),
        ("run_timeline", {"session_id": SPINE, "source": MAIN}),
    ],
    ids=["session_timeline", "run_timeline"],
)
def test_a_timeline_read_at_the_log_runs_at_the_width_hp_query_defaults_to(
    name: str, keys: dict[str, str]
) -> None:
    """The two library queries a page shares with `hp query`, bound at the children log.

    They are the only bound statements with a production default (`analyze/manifest.py`):
    `bind` never reads it, filling `log_chars` off the surface instead, and the log's width
    is the same constant the default cites — so the log and a bare `hp query` print one row.
    """
    filled = bind(name, bounds.LOG_WIDTHS._asdict(), NO_SIZES, **keys)
    assert filled["log_chars"] == manifest.describe(name).params["log_chars"].default


def test_a_filled_read_binds_what_the_route_used_to_spell_by_hand() -> None:
    """The turn header, bound from its keys, its surface and the reader's `?detail=`.

    Every other leaf here is downstream of this one: what the page runs at, what the footer
    quotes and what a reader pastes back into `hp query` are all this mapping. The order is
    part of it — a citation is written key by key in the order the mapping holds them — so the
    three groups come back in the order a read spells them: keys, widths, sizes.
    """
    hand = {
        "session_id": SPINE,
        "source": MAIN,
        "turn_id": SLASH_TURN,
        "head_chars": bounds.HEADER_WIDTHS.head_chars,
        "detail_chars": bounds.DETAIL.default,
    }
    filled = bind(
        "view_turn_header",
        bounds.HEADER_WIDTHS._asdict(),
        {"detail_chars": bounds.DETAIL.default},
        session_id=SPINE,
        source=MAIN,
        turn_id=SLASH_TURN,
    )
    assert filled == hand
    assert list(filled) == list(hand)


def test_a_parameter_neither_the_keys_nor_the_widths_carry_is_refused_by_name() -> None:
    """A read whose surface is short a width crashes, naming the statement and the parameter.

    DuckDB refuses the same read — a named parameter it never got is an error there too — but
    it names neither the surface nor which of the two halves should have carried the number,
    and it only says so once a connection has been opened and the statement handed over.

    The session header cuts three strings and caps a list; the popover declares two of them
    and no `head_chars`, so binding one against the other is the mistake this catches: a
    surface used for a read that is not its own. Nothing is keyed either, so two names are
    short at once and the message lists them — the read that has to be fixed usually owes
    more than one.
    """
    with pytest.raises(
        ValueError, match=r"^view_session_header binds session_id, head_chars, which no key"
    ):
        bind("view_session_header", bounds.POPOVER_WIDTHS._asdict(), NO_SIZES)


def test_a_key_that_is_also_a_width_is_refused_rather_than_overriding_it() -> None:
    """A read cannot bind a width of its own: a second width is a second surface.

    Silent overriding is what the profiles exist to end — a page that passed its own
    `head_chars` would run at a width nothing in `bounds.py` declares, and the citation under
    it would be the only place that number appears. The refusal names the field, so the fix is
    to declare the surface rather than to keep the argument. Two of them are passed, so the
    refusal has to name both rather than stop at the first.
    """
    with pytest.raises(
        ValueError, match=r"^view_turn_header takes chip_chars, head_chars from its widths"
    ):
        bind(
            "view_turn_header",
            bounds.HEADER_WIDTHS._asdict(),
            {"detail_chars": bounds.DETAIL.default},
            session_id=SPINE,
            source=MAIN,
            turn_id=SLASH_TURN,
            head_chars=10,
            chip_chars=10,
        )


def test_a_key_that_is_also_a_size_is_refused_rather_than_being_shadowed_by_it() -> None:
    """The third collision, refused like the other two: a size the read also spells as a key.

    A size is what a reader asked the page for and a key is what the read is about, so a
    parameter arriving as both is two answers to one question — and the URL's would win, being
    written second into the mapping. Silently: the citation would quote the reader's number
    while the call site went on saying the read binds its own.

    `detail_chars` is the collision that can happen, because it is the one size a node page
    passes and no surface declares — the width arms above never see it. Two collide here so
    the refusal is seen to name every one, in order.
    """
    with pytest.raises(
        ValueError, match=r"^view_turn_header is passed detail_chars, log_size twice"
    ):
        bind(
            "view_turn_header",
            bounds.HEADER_WIDTHS._asdict(),
            {"detail_chars": bounds.DETAIL.default, "log_size": bounds.LOG.default},
            session_id=SPINE,
            source=MAIN,
            turn_id=SLASH_TURN,
            detail_chars=10,
            log_size=5,
        )


def test_a_key_the_statement_does_not_bind_is_refused_before_a_connection_is_opened(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A key no statement binds is a mistake at the call, not a binding error at the store.

    The query is planted — invented, and deliberately a shape no shipped file has: one
    parameter, and that one a width — because what this holds is the arm that reads the
    statement rather than any page. The records browser's own surface fills it, and the two
    keys beside it belong to no column the statement mentions, so the refusal lists both.

    No `duckdb` import and no store path is in reach of this test, which is the claim: the
    refusal happens while the mapping is being built.
    """
    monkeypatch.setattr(library, "QUERY_DIR", tmp_path)
    (tmp_path / "view_records.sql").write_text("SELECT $preview_chars AS preview_chars")
    with pytest.raises(ValueError, match=r"^view_records binds no session_id, source:"):
        bind(
            "view_records", bounds.RECORDS_WIDTHS._asdict(), NO_SIZES, session_id=SPINE, source=MAIN
        )
