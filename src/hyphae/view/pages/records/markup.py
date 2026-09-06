"""The records page's markup: the typed record row, the page of them, and one record."""

import htpy

from hyphae.view.components import Html, citation, layout
from hyphae.view.nodes import thread_url
from hyphae.view.pages.records.models import RecordRow, RecordsPage
from hyphae.view.text import format as fmt


def records_page(*, page: RecordsPage, dev: bool) -> Html:
    """One page of a thread's raw transcript — where a report's citation lands.

    `page.opened` names the one row that arrives open, or None where the row a citation named
    is too wide to open unasked (`bounds.OPENED_RECORD_CHARS`).
    """
    return layout.page(
        tab_title=f"{page.source} records — hyphae",
        scripts=None,
        main=htpy.section(id="records")[
            [
                htpy.h1["Raw records"],
                htpy.p(".numbers")[
                    [
                        htpy.a(href=f"/session/{page.session_id}")[page.session_id],
                        htpy.span(data_field="source")[page.source],
                        htpy.span[
                            [
                                htpy.span(data_field="matched")[fmt.count(page.matched)],
                                " record(s) from here",
                            ]
                        ],
                    ]
                ],
                htpy.ol(".records")[
                    [
                        _record(
                            row=row,
                            thread=thread_url(page.session_id, page.source),
                            opened=page.opened,
                        )
                        for row in page.rows
                    ]
                ],
                htpy.p(".more", data_more_records=page.after)[
                    htpy.a(
                        href=f"{thread_url(page.session_id, page.source)}/records"
                        f"?after={page.after}&size={page.size}"
                    )[htpy.span(data_field="count")[f"+{fmt.count(page.more)} more"]]
                ]
                if page.after is not None
                else None,
            ]
        ],
        footer=citation.footer(citations=page.citations),
        dev=dev,
    )


def _record(*, row: RecordRow, thread: str, opened: int | None) -> Html:
    """One record's row, and the fetch that brings the whole of it.

    The whole record on first open, one request per record: a page of them whole is the one
    payload nothing here bounds. One row is the exception — the one the route picked as
    `opened`, the record a citation named — which arrives open and fetches itself as the page
    loads. Still a fetch and not inlined: the page stays bounded, and what is unbounded stays
    one record at a time.
    """
    # The anchor is the line number, which is what a citation carries: `#L42` lands here.
    return htpy.li(id=f"L{row.line_no}", data_record=row.line_no)[
        [
            htpy.span(".line")[row.line_no],
            # Spaces, one per gap: the row is no flex line and only `.line` carries a margin
            # (`view/static/pages.css`), so these are what hold the five values apart.
            " ",
            htpy.span(".type", data_field="type")[row.type],
            " ",
            htpy.span(data_field="timestamp")[fmt.clock(row.timestamp)],
            " ",
            htpy.span[[htpy.span(data_field="raw_chars")[fmt.count(row.raw_chars)], " chars"]],
            " ",
            htpy.code(data_field="raw_head")[row.raw_head],
            htpy.details(
                ".whole",
                open=row.line_no == opened,
                data_open_record=row.line_no,
                hx_get=f"/fragment/record{thread}/line/{row.line_no}",
                hx_trigger="load" if row.line_no == opened else "toggle once",
                hx_target="find .value",
            )[[htpy.summary["whole record"], htpy.div(".value")]],
        ]
    ]
