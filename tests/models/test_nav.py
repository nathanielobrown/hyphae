"""The NavTree's row models: every one built under the one row config, and the two structs
that tell a NavTree turn's context bar from every other row's.

`tests/models/test_listing.py` pins the config and the refusals it buys; this holds every
model `store/nav.py` builds to it. The values are the store's: `tests/store/test_nav.py`
builds every model off recorded rows.
"""

import datetime as dt
from typing import Any

import pytest
from pydantic import ValidationError

from hyphae.models.nav import NavCallRow, NavToolRow, NavTurnRow, RunRow, TurnContext
from hyphae.models.row import ROW

ROW_MODELS = [NavTurnRow, NavCallRow, NavToolRow, RunRow]
# One row as `view_nav_tree_turns` answers it on the spine's first turn, by column name: the
# thread's first turn takes the whole fill as what it added, over the base the session opened
# on.
A_NAV_TURN: dict[str, Any] = {
    "turn_index": 0,
    "turn_id": "30aad8e5",
    "prompt": "hello",
    "command_name": None,
    "command_args": None,
    "started_at": dt.datetime(2025, 8, 12, 10, tzinfo=dt.UTC),
    "cost_usd": 0.0123,
    "unpriced_api_calls": 0,
    "context": {"fill": 12000, "added": 12000, "base": 3000, "window": 200000},
}


@pytest.mark.parametrize("model", ROW_MODELS, ids=lambda model: model.__name__)
def test_every_nav_row_model_is_built_under_the_one_row_config(model: type) -> None:
    """A model a NavTree row builds is strict and forbids extras, so a column that drifts raises."""
    assert getattr(model, "__pydantic_config__") == ROW  # noqa: B009


def test_a_nav_turns_context_carries_the_base_the_session_opened_on() -> None:
    """A NavTree turn's context bar draws a band no other row has — what stood before the
    thread's first turn — so its struct is the wider one, and a bar without it is refused."""
    # The row builds with the four-member struct...
    assert NavTurnRow(**A_NAV_TURN).context == TurnContext(
        fill=12000, added=12000, base=3000, window=200000
    )
    # ...while a struct missing the base is a statement that drifted, not a bar to draw.
    without_base: dict[str, Any] = {
        **A_NAV_TURN,
        "context": {k: v for k, v in A_NAV_TURN["context"].items() if k != "base"},
    }
    with pytest.raises(ValidationError, match="base"):
        NavTurnRow(**without_base)
