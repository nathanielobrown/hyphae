"""The session list at `/sessions`: what a request may ask of it, and the page that answers.

Which sort and filter keys the list offers, what a query-string value has to parse as, and the
graph those choices compose: the parameters are checked into a `ListParams`, the read turns
that into a page and closes the store, and the markup dependency mints the links and the form
around both. The SQL is `view/store.py`'s, beside every other page's composition; this module
hands the read a key out of a closed dictionary and a value already parsed, which is what makes
a key outside them a 400 here rather than a fragment of SQL there.
"""

import datetime as dt
from collections.abc import Mapping
from typing import Annotated, assert_never

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from hyphae.analyze import queries
from hyphae.analyze.queries import ParamValue
from hyphae.view import bounds
from hyphae.view.components import Html
from hyphae.view.deps import ViewerDep
from hyphae.view.links import DEFAULT_DIRECTION, DEFAULT_SORT, LIST_URL, list_url
from hyphae.view.pages.sessions import markup, read
from hyphae.view.pages.sessions.markup import Control
from hyphae.view.pages.sessions.models import ListParams, SessionsPage
from hyphae.view.store import DIRECTIONS, FILTERS, SORTS

router = APIRouter()


# The HTML input a filter's type gets on the form. One map rather than a field per filter.
CONTROLS: dict[queries.ParamType, str] = {
    queries.ParamType.TEXT: "text",
    queries.ParamType.DATE: "date",
    queries.ParamType.INTEGER: "number",
}


# The same two as `aria-sort` spells them. ARIA defines the tokens and `asc` is not one of
# them, so a heading marked with the query string's own word announces no order at all.
ARIA_SORT: dict[str, str] = {"asc": "ascending", "desc": "descending"}


# Every query-string key the session list reads: the filters, plus what orders and pages them.
LIST_KEYS = frozenset(FILTERS) | {"sort", "direction", "page", "size"}


def narrowing(params: Mapping[str, str]) -> dict[str, ParamValue]:
    """The filters one request asked for, each parsed as the type its predicate binds.

    A key outside `LIST_KEYS` is a 400 rather than a no-op: FastAPI ignores what it was not
    declared with, so a mistyped filter would otherwise show the whole corpus and look like
    an answer. An empty value is not a filter — the list's form submits every field, so a
    blank one has to mean "not filtering".
    """
    if not params.keys() <= LIST_KEYS:
        raise HTTPException(400, f"The list takes {', '.join(sorted(LIST_KEYS))}.")
    return {key: _as_bound(key, given) for key in FILTERS if (given := params.get(key))}


def _as_bound(key: str, text: str) -> ParamValue:
    """One filter's query-string text as the value DuckDB binds, or a 400."""
    kind = FILTERS[key].type
    try:
        match kind:
            case queries.ParamType.TEXT:
                return text
            case queries.ParamType.INTEGER:
                return int(text)
            case queries.ParamType.DATE:
                return dt.date.fromisoformat(text)
            case _:
                assert_never(kind)
    except ValueError as error:
        raise HTTPException(400, f"The list's {key} takes {kind} values.") from error


def list_params(
    request: Request,
    sort: str = DEFAULT_SORT,
    direction: str = DEFAULT_DIRECTION,
    page: int = 1,
    size: int = bounds.SESSIONS.default,
) -> ListParams:
    """Everything the URL asked of the list, checked before anything opens the store."""
    if sort not in SORTS or direction not in DIRECTIONS:
        raise HTTPException(
            400,
            f"Sort by one of {', '.join(SORTS)}, in direction {' or '.join(DIRECTIONS)}.",
        )
    if page < 1 or not 1 <= size <= bounds.SESSIONS.ceiling:
        raise HTTPException(
            400, f"Ask for page 1 or later, at a size between 1 and {bounds.SESSIONS.ceiling}."
        )
    return ListParams(
        sort=sort,
        direction=direction,
        page=page,
        size=size,
        filters=narrowing(request.query_params),
        # What the URL said, kept as text: the links have to reproduce the request, and the
        # form has to come back filled in with what was typed into it.
        given={key: request.query_params.get(key, "") for key in FILTERS},
    )


ListAsk = Annotated[ListParams, Depends(list_params)]


def sessions_read(ask: ListAsk, viewer: ViewerDep) -> SessionsPage:
    """That ask read whole, and the store closed behind it."""
    return read.sessions(viewer.db, ask)


SessionsRead = Annotated[SessionsPage, Depends(sessions_read)]


def sessions_markup(ask: ListAsk, page: SessionsRead, viewer: ViewerDep) -> Html:
    """That read, rendered under the sort, form and pager the ask composes."""
    # A header link flips the direction of the column already sorted by, and opens any
    # other column at the direction that puts its largest values first. Re-sorting starts
    # from the first page: page 4 of one order says nothing about page 4 of another.
    flipped = "asc" if ask.direction == "desc" else "desc"
    links = {
        key: list_url(
            key, flipped if key == ask.sort else DEFAULT_DIRECTION, 1, ask.size, ask.given
        )
        for key in SORTS
    }
    return markup.sessions_page(
        page=page,
        # One heading per sortable column, in `SORTS` order, each carrying the link that
        # re-sorts by it.
        headings=[markup.Heading(key, label, links[key]) for key, label in SORTS.items()],
        sort=ask.sort,
        direction=ask.direction,
        # The same ordering in ARIA's vocabulary, for the heading that marks it: the form and
        # the links carry the query string's word, the mark carries ARIA's.
        aria_direction=ARIA_SORT[ask.direction],
        # One input per filter, in `FILTERS` order, carrying what this request asked.
        controls=[
            Control(key, CONTROLS[spec.type], ask.given[key]) for key, spec in FILTERS.items()
        ],
        pages=markup.Pages(
            first=(ask.page - 1) * ask.size + 1,
            shown=len(page.rows),
            previous=list_url(ask.sort, ask.direction, ask.page - 1, ask.size, ask.given)
            if ask.page > 1
            else None,
            next=list_url(ask.sort, ask.direction, ask.page + 1, ask.size, ask.given)
            if page.more
            else None,
        ),
        dev=viewer.dev,
    )


SessionsMarkup = Annotated[Html, Depends(sessions_markup)]


@router.get(LIST_URL)
def session_list(page: SessionsMarkup, viewer: ViewerDep) -> Response:
    """One page of sessions, under the filter, sort and size the URL carries."""
    return viewer.html(page)
