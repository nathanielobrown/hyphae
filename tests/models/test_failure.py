"""The failure row model: built under the one row config, and what it refuses.

`tests/models/test_listing.py` pins the config itself; this holds the model
`store/failures.py` builds to it and pins one refusal on the column the stepper keys on. The
values themselves are the store's: `tests/store/test_failures.py` builds every model off
recorded rows.
"""

import datetime as dt
from typing import Any

import pytest
from pydantic import ValidationError

from hyphae.models.failure import Failure
from hyphae.models.row import ROW

# One row as `view_session_errors` answers it, by column name: the `tool_fields` struct
# beside the tool's name, and the count the statement carries on every row.
A_FAILURE: dict[str, Any] = {
    "source": "main",
    "tool_call_id": "srvtoolu_01KUMaS97sNkE7Z12UW4HMEp",
    "name": "advisor",
    "fields": {"path": None, "todos": None, "input_head": "{}"},
    "is_error": True,
    "started_at": dt.datetime(2026, 7, 6, 18, 19, 3, 233000, tzinfo=dt.UTC),
    "matched_rows": 1,
}


def test_the_failure_row_model_is_built_under_the_one_row_config() -> None:
    """A model a row builds is strict and forbids extras, so a column that drifts raises."""
    assert getattr(Failure, "__pydantic_config__") == ROW  # noqa: B009


def test_a_failure_whose_tool_call_id_is_not_text_is_refused() -> None:
    """`tool_call_id` is what the stepper keys a node on: another type is another column."""
    whole: dict[str, Any] = {**A_FAILURE, "tool_call_id": 7}
    with pytest.raises(ValidationError, match="string_type"):
        Failure(**whole)
    assert Failure(**A_FAILURE).tool_call_id == A_FAILURE["tool_call_id"]


def test_a_failure_column_the_model_lacks_is_refused() -> None:
    """A statement that gained a column fails where it is read, not on a page that never
    printed it."""
    gained: dict[str, Any] = {**A_FAILURE, "call_cost_usd": 0.1}
    with pytest.raises(ValidationError, match="unexpected_keyword_argument"):
        Failure(**gained)
