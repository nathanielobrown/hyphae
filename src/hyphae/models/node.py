"""What a node's reads hand back across the store line, each with the statement that read it.

The values here are what a page renders; the rows they are built from stay in the store. A
read builds one by column name — `WholeValue(citation=…, **row)` — so a statement answering
a column the model lacks raises where it is read and not on a reader's page.
"""

from dataclasses import dataclass

from hyphae.models.citation import Citation


@dataclass(frozen=True)
class WholeValue:
    """One fat value of a node, whole: the rest of what a pane previewed at its width."""

    # None is a row the store holds with nothing under it — a `Read` has no command, a turn
    # no prompt — which the fetch that serves it turns into its 404.
    value: str | None
    citation: Citation
    # The suffix of the file a `Read` returned, which decides how the value is marked up
    # (`view/detail.py:syntax_of`). Only the named-file statement selects it; None elsewhere.
    result_type: str | None = None
