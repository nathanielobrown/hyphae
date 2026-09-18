"""The node row models: every one built under the one row config, and the join a page reads.

`tests/models/test_listing.py` pins the config itself and the three refusals it buys; this
holds every model `store/nodes.py` builds to it, and the one record model beside them, so a
model declared without the config reds here rather than reading a drifted column as a page.
The values themselves are the store's: `tests/store/test_nodes.py` builds every model off
recorded rows.
"""

from typing import Any

import pytest
from pydantic import ValidationError

from hyphae.models.node import (
    CallHeader,
    CallRow,
    CompactionNumbers,
    CompactionRow,
    NodeNumbers,
    RunHeader,
    TimelineRow,
    ToolHeader,
    ToolNumbers,
    ToolRow,
    TurnHeader,
    TurnRecord,
    WholeValue,
)
from hyphae.models.row import ROW

ROW_MODELS = [
    TurnHeader,
    RunHeader,
    CallHeader,
    ToolHeader,
    WholeValue,
    CallRow,
    ToolRow,
    TimelineRow,
    CompactionRow,
    NodeNumbers,
    ToolNumbers,
    CompactionNumbers,
    TurnRecord,
]
# One row as `view_turn_records` answers it, by column name.
A_TURN_RECORD: dict[str, Any] = {"turn_id": "30aad8e5", "line_no": 12}


@pytest.mark.parametrize("model", ROW_MODELS, ids=lambda model: model.__name__)
def test_every_row_model_is_built_under_the_one_row_config(model: type) -> None:
    """A model a row builds is strict and forbids extras, so a column that drifts raises."""
    assert getattr(model, "__pydantic_config__") == ROW  # noqa: B009


def test_a_turn_records_line_number_of_another_type_is_refused() -> None:
    """`line_no` is the line a turn's page links down to: a float, even a whole one, is
    another column."""
    whole: dict[str, Any] = {**A_TURN_RECORD, "line_no": 12.0}
    with pytest.raises(ValidationError, match="int_type"):
        TurnRecord(**whole)
    assert TurnRecord(**A_TURN_RECORD).line_no == 12
