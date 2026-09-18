"""What the errors page and the error stepper read: one failed tool call of a session, thin.

Built by column name off the statement that answers it (`store/failures.py`), under
`row.ROW`, so a column the statement gains or loses raises at the read. `Failures` carries
beside the rows what the page prints under them: how many the cap left off, and the citation
a footer quotes.
"""

import datetime as dt
from typing import NamedTuple

from pydantic.dataclasses import dataclass

from hyphae.models.citation import Citation
from hyphae.models.row import ROW


@dataclass(frozen=True, config=ROW)
class Failure:
    """One failed tool call as the errors page lists it: a `view_session_errors` row.

    Thin, like a NavTree row: what names the node, not what describes it — each row leads to
    the tool call's own page.
    """

    # The thread it ran on and its id there: the key its page and the stepper are found by.
    source: str
    tool_call_id: str
    name: str
    # The `tool_fields` struct: every member a cut string, but `todos`, a count
    # (`store/macros.py`); what a title is composed out of (`view/text/tool_names.py`).
    fields: dict[str, str | int | None]
    # Constant true under the statement's filter, selected so every tool row reads alike.
    is_error: bool
    started_at: dt.datetime
    # How many the session failed in all, counted before the LIMIT bit, on every row alike.
    matched_rows: int


class Failures(NamedTuple):
    """One session's failures in the order they happened, and how many the cap left off."""

    rows: list[Failure]
    cut: int
    citation: Citation
