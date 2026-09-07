"""The projects landing: one row per project the store holds sessions for.

A table of one row per thing, like the session list beside it — a typed row in, a `<tr>` out.
What a row prints is what its type carries (`models.py`), and where those values came from is
`read.py`'s business rather than this file's.
"""

import htpy

from hyphae.view.components import Html, citation, layout, parts
from hyphae.view.pages.projects.models import ProjectRow, ProjectsPage
from hyphae.view.text import cuts
from hyphae.view.text import format as fmt


def projects_page(*, page: ProjectsPage, dev: bool) -> Html:
    """Every project the store holds sessions for, most recently active first.

    The two trailing windows are headed with the days they were bound to, so a heading cannot
    say one thing while the column counts another — the footer cites the same numbers.
    """
    return layout.page(
        tab_title="Projects — hyphae",
        scripts=None,
        main=htpy.fragment[
            [
                htpy.h1["Projects"],
                htpy.table(id="projects")[
                    [
                        htpy.thead[
                            htpy.tr[
                                [
                                    htpy.th(scope="col")["Project"],
                                    # Set the way the cells under them are: a count is read
                                    # down its column.
                                    htpy.th(".number", scope="col")[f"{page.recent_days}d"],
                                    htpy.th(".number", scope="col")[f"{page.window_days}d"],
                                    htpy.th(".number", scope="col")["All time"],
                                    htpy.th(scope="col")["Last active"],
                                ]
                            ]
                        ],
                        htpy.tbody[[_project(row=row) for row in page.rows]],
                    ]
                ],
                # What the page left out, said rather than dropped: the store keeps every
                # project, and this one shows the most recently active.
                htpy.p(".more", data_more_projects=page.cut)[
                    f"+{fmt.count(page.cut)} more project(s)"
                ]
                if page.cut
                else None,
            ]
        ],
        footer=citation.footer(citations=page.citations),
        dev=dev,
    )


def _project(*, row: ProjectRow) -> Html:
    """One project's row: where its sessions read, its three windows, and its last activity."""
    return htpy.tr(data_project=row.project_dir or "")[
        [
            htpy.td(".path")[_project_name(row=row)],
            _window(
                sessions_field="recent_sessions",
                sessions=row.recent_sessions,
                cost_field="recent_cost",
                cost=row.recent_cost,
                unpriced=row.recent_unpriced,
            ),
            _window(
                sessions_field="window_sessions",
                sessions=row.window_sessions,
                cost_field="window_cost",
                cost=row.window_cost,
                unpriced=row.window_unpriced,
            ),
            _window(
                sessions_field="sessions",
                sessions=row.sessions,
                cost_field="cost_usd",
                cost=row.cost_usd,
                unpriced=row.unpriced_api_calls,
            ),
            htpy.td(".when")[
                parts.stacked(
                    field="ago",
                    primary=cuts.ago(row.last_active),
                    secondary_field="last_active",
                    secondary=fmt.when(row.last_active),
                    unit=None,
                    primary_mark=None,
                    secondary_mark=None,
                )
            ],
        ]
    ]


def _project_name(*, row: ProjectRow) -> Html:
    """The path, as a link where there is a list to open and as text where there is not.

    The link filters the list by the whole path, which is why a row whose path is longer than
    the head this page shows is text: a link carrying a cut path lands on nothing. The sessions
    naming no directory are text for a different reason — there is no project to open, and
    `?project=` matches no session at all.

    Cut like a session-list row's path, and for the same reason: the query hands back one
    character past the width, and a path too long to link is the one a reader most needs the
    mark on — the row it lands on is the one with no link to explain itself.
    """
    if row.link:
        return htpy.a(data_field="project_dir", href=row.link)[
            cuts.project_path(cuts.short(row.project_dir))
        ]
    shown = cuts.project_path(cuts.short(row.project_dir)) if row.project_dir else "(no project)"
    return htpy.span(data_field="project_dir")[shown]


def _window(
    *,
    sessions_field: str,
    sessions: int,
    cost_field: str,
    cost: float | None,
    unpriced: int | None,
) -> Html:
    """One window's cell: how many sessions it holds, over what they cost.

    The field names are the store's own column names rather than the column heading, so a test
    reads a window without matching the label the page prints over it.
    """
    return htpy.td(".number")[
        parts.stacked(
            field=sessions_field,
            primary=fmt.count(sessions),
            secondary_field=cost_field,
            secondary=fmt.money(cost),
            unit=None,
            primary_mark=None,
            secondary_mark=parts.unpriced(calls=unpriced),
        )
    ]
