"""The row-built models: one config, and what it refuses.

A repository builds each of these by column name, `Model(**row)`, so the model is the contract
a statement is held to. What is pinned here is the config every one carries — strict, no
extras — and the three refusals it buys: a column of the wrong type, a column the model lacks,
and a column the row lacks. The values themselves are the store's, and
`tests/store/test_sessions.py` builds every model off recorded rows.
"""

from dataclasses import fields
from typing import Any

import pytest
from pydantic import ValidationError

from hyphae.models.citation import Citation
from hyphae.models.listing import (
    DescribedSessionRollup,
    Project,
    ProjectRollup,
    SessionDescription,
    SessionFigures,
    SessionHeader,
    SessionRollup,
)
from hyphae.models.node import WholeValue
from hyphae.models.row import ROW

# Every model a repository builds off a row, and the one node value 4.0 built the same way.
ROW_MODELS = [
    SessionRollup,
    SessionDescription,
    DescribedSessionRollup,
    Project,
    ProjectRollup,
    SessionHeader,
    WholeValue,
]
# One row as a statement answers it: a dict by column name, typed the way a store row is.
A_PROJECT: dict[str, Any] = {"project_dir": "/repo", "sessions": 1}


@pytest.mark.parametrize("model", ROW_MODELS, ids=lambda model: model.__name__)
def test_every_row_model_is_built_under_the_one_row_config(model: type) -> None:
    """A model a row builds is strict and forbids extras, so a column that drifts raises."""
    assert getattr(model, "__pydantic_config__") == ROW  # noqa: B009


def test_the_row_config_is_strict_and_forbids_extras() -> None:
    """Strict, so lax mode cannot rewrite a value on its way in; extras forbidden, so a column
    the model does not name raises rather than vanishing."""
    assert ROW == {"strict": True, "extra": "forbid"}


def test_a_column_of_another_type_is_refused() -> None:
    """`sessions` is an integer count: a float, even a whole one, is another column."""
    whole: dict[str, Any] = {**A_PROJECT, "sessions": 1.0}
    with pytest.raises(ValidationError, match="int_type"):
        Project(**whole)
    # ...where lax mode would have read `1.0` as `1` and printed the same page.
    assert Project(**A_PROJECT) == Project("/repo", 1)


def test_a_column_the_model_lacks_is_refused() -> None:
    """A statement that gained a column fails where it is read, not on a page that never
    printed it."""
    gained: dict[str, Any] = {**A_PROJECT, "turns": 3}
    with pytest.raises(ValidationError, match="unexpected_keyword_argument"):
        Project(**gained)


def test_a_column_the_row_lacks_is_refused() -> None:
    """A statement that lost a column fails the same way."""
    lost: dict[str, Any] = {"project_dir": "/repo"}
    with pytest.raises(ValidationError, match="missing"):
        Project(**lost)


def test_a_whole_value_is_built_the_same_way() -> None:
    """The node value 4.0 built by column name carries the same config, so a fetch whose
    statement drifts raises too."""
    cited = Citation("view_turn_prompt", {"session_id": "s", "turn_id": "t"})
    row: dict[str, Any] = {"value": "hello"}
    assert WholeValue(citation=cited, **row) == WholeValue("hello", cited, None)
    gained: dict[str, Any] = {**row, "prompt": "hello"}
    with pytest.raises(ValidationError, match="unexpected_keyword_argument"):
        WholeValue(citation=cited, **gained)


def test_a_described_rollup_is_a_rollup_and_a_description() -> None:
    """The listing's joined row narrows by `isinstance`: a described row is both halves, and the
    join adds no column of its own."""
    assert issubclass(DescribedSessionRollup, SessionRollup)
    assert issubclass(DescribedSessionRollup, SessionDescription)
    named = {field.name for field in fields(DescribedSessionRollup)}
    assert named == {field.name for field in fields(SessionRollup)} | {
        field.name for field in fields(SessionDescription)
    }


def test_the_list_row_and_the_header_share_one_session() -> None:
    """A session's identity, counts, tokens, cost and durations are one set of fields, derived
    by the list row and the header rather than copied: each adds only what its surface prints."""
    assert issubclass(SessionRollup, SessionFigures)
    assert issubclass(SessionHeader, SessionFigures)
    shared = {field.name for field in fields(SessionFigures)}
    assert {field.name for field in fields(SessionRollup)} - shared == {
        "agent_types",
        "agent_types_cut",
    }
    assert {field.name for field in fields(SessionHeader)} - shared == {
        "project_filter",
        "git_branch",
        "version",
        "entrypoint",
        "ended_at",
        "pr_urls",
        "pr_urls_cut",
        "context",
        "citation",
    }
