"""The item models: what a pass describes, built strictly, and what they refuse.

`tests/models/test_listing.py` pins the row config itself; this holds the models
`store/items.py` builds to it. The values themselves are the store's:
`tests/store/test_enrichment.py` builds every item off recorded rows.
"""

from dataclasses import asdict
from typing import Any

import pytest
from pydantic import ValidationError

from hyphae.models.items import (
    AgentRunItem,
    ApiCallRow,
    RunSection,
    SessionChild,
    SessionItem,
    ToolCallRow,
    TurnItem,
)
from hyphae.models.row import ROW
from tests.enrich.conftest import session_item

# Every model the store selects an item, or a part of one, into.
ITEM_MODELS = [
    ToolCallRow,
    ApiCallRow,
    RunSection,
    SessionChild,
    TurnItem,
    AgentRunItem,
    SessionItem,
]


@pytest.mark.parametrize("model", ITEM_MODELS, ids=lambda model: model.__name__)
def test_every_item_model_is_built_under_the_one_row_config(model: type) -> None:
    """An item the store selects is strict and forbids extras, so a column that drifts raises
    at the read rather than reaching a prompt as text."""
    assert getattr(model, "__pydantic_config__") == ROW  # noqa: B009


def test_a_count_that_arrives_as_text_is_refused() -> None:
    """A token count is an integer: text, even a numeral, is another column."""
    whole: dict[str, Any] = {**asdict(session_item("s-1")), "input_tokens": "12"}
    with pytest.raises(ValidationError, match="int_type"):
        SessionItem(**whole)
    # ...where lax mode would have read `"12"` as 12 and rendered the same prompt.
    counted: dict[str, Any] = {**whole, "input_tokens": 12}
    assert SessionItem(**counted).input_tokens == 12


def test_a_field_the_model_lacks_is_refused() -> None:
    """A column the store gained fails where the item is built, not in a prompt that never
    rendered it."""
    gained: dict[str, Any] = {**asdict(session_item("s-1")), "duration_ms": 3}
    with pytest.raises(ValidationError, match="unexpected_keyword_argument"):
        SessionItem(**gained)
