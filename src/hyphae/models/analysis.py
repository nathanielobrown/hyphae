"""What `hp query` reads back from the store: one statement's answer whole, with its citation.

Raw rather than a row model: `hp query` prints whatever a library statement answered — a
header and a body — and names no column, so nothing here is built under `row.ROW`.
"""

from typing import Any, NamedTuple

from hyphae.models.citation import Citation


class Answered(NamedTuple):
    """One statement's answer: the columns as DuckDB reported them, the rows as tuples in the
    statement's order, and the citation naming every value it ran at — what scoped the corpus
    ahead of what the statement itself bound."""

    columns: tuple[str, ...]
    rows: list[tuple[Any, ...]]
    citation: Citation
