"""The records and offload row models: built under the one row config, and what it refuses.

`tests/models/test_listing.py` pins the config itself and the three refusals it buys; this
holds the two models `store/records.py` and `store/offloads.py` build to it, and pins one
refusal apiece on the column each page reads first. The values themselves are the store's:
`tests/store/test_records.py` and `test_offloads.py` build every model off recorded rows.
"""

from typing import Any

import pytest
from pydantic import ValidationError

from hyphae.models.citation import Citation
from hyphae.models.record import Offload, Record
from hyphae.models.row import ROW

# One row as `view_records` answers it, and one as `view_offload` does, by column name.
A_RECORD: dict[str, Any] = {
    "line_no": 1,
    "uuid": None,
    "type": "mode",
    "timestamp": None,
    "raw_chars": 87,
    "raw_head": '{"type": "mode"}',
    "matched_rows": 47,
}
AN_OFFLOAD: dict[str, Any] = {
    "name": "bosvr1kjx.txt",
    "lossy_decode": False,
    "size_bytes": 161,
    "content_chars": 159,
    "chunk": "[redacted]",
}
CITED = Citation("view_offload", {"session_id": "s", "name": "bosvr1kjx.txt"})


@pytest.mark.parametrize("model", [Record, Offload], ids=lambda model: model.__name__)
def test_every_row_model_is_built_under_the_one_row_config(model: type) -> None:
    """A model a row builds is strict and forbids extras, so a column that drifts raises."""
    assert getattr(model, "__pydantic_config__") == ROW  # noqa: B009


def test_a_record_line_number_of_another_type_is_refused() -> None:
    """`line_no` is the cursor a page resumes at: a float, even a whole one, is another column."""
    whole: dict[str, Any] = {**A_RECORD, "line_no": 1.0}
    with pytest.raises(ValidationError, match="int_type"):
        Record(**whole)
    assert Record(**A_RECORD).line_no == 1


def test_an_offload_column_the_model_lacks_is_refused() -> None:
    """A statement that gained a column fails where it is read, not on a page that never
    printed it — the content whole would be the one to fear."""
    gained: dict[str, Any] = {**AN_OFFLOAD, "content": "..."}
    with pytest.raises(ValidationError, match="unexpected_keyword_argument"):
        Offload(citation=CITED, **gained)
    assert Offload(citation=CITED, **AN_OFFLOAD).chunk == "[redacted]"
