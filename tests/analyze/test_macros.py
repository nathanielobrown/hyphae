"""What the shared macros answer, run against a real DuckDB rather than read as text.

The bounding macros are weighed in `tests/view/test_bounds.py`, which owns the cut protocol.
This module holds the ones whose contract is a value: what they answer for a key the table has,
for one it does not, and for NULL.
"""

from collections.abc import Generator
from pathlib import Path

import duckdb
import pytest

from hyphae.analyze import macros
from hyphae.extract.pricing import MODELS, SYNTHETIC_MODEL
from tests.conftest import (
    FIXTURE_TAG_KEY,
    FIXTURE_TAG_VALUE,
    TAGGED_SESSIONS,
    macro_connection,
)

# Every key the table sizes, then the three the macro must answer NULL for: the placeholder,
# which states no window; a model no table ever named; and NULL itself, which is what a thread
# with no answered call passes (`view_compactions.sql`).
SIZED = tuple(model for model, spec in MODELS.items() if spec.context_window is not None)
UNSIZED = (SYNTHETIC_MODEL, "claude-from-a-version-we-have-not-seen", None)


@pytest.fixture(scope="module")
def installed() -> duckdb.DuckDBPyConnection:
    """One in-memory connection carrying the macros, shared by every leaf here."""
    return macro_connection()


def test_context_window_answers_the_table_for_a_model_it_sizes(
    installed: duckdb.DuckDBPyConnection,
) -> None:
    """A model the price table sizes gets that window back, as a number a bar divides by."""
    # Every sized model in one statement, so a spelling the macro body mangles fails by name...
    answered = installed.execute(
        "SELECT model, context_window(model), typeof(context_window(model))"
        " FROM (SELECT unnest($models) AS model)",
        {"models": list(SIZED)},
    ).fetchall()
    assert [(model, window) for model, window, _ in answered] == [
        (model, MODELS[model].context_window) for model in SIZED
    ]
    # ...and the type is one the arithmetic downstream can divide, not a list or a struct.
    assert {kind for _, _, kind in answered} == {"INTEGER"}


@pytest.mark.parametrize("model", UNSIZED, ids=["placeholder", "unknown", "null"])
def test_context_window_answers_null_for_a_model_it_cannot_size(
    installed: duckdb.DuckDBPyConnection, model: str | None
) -> None:
    """A model with no window — placeholder, unknown, or none at all — is a bar left undrawn.

    The viewer reads a NULL window as "draw no bar" (`view_compactions.sql`), so a macro that
    answered a default here would invent a scale for a thread we cannot size.
    """
    answered = installed.execute("SELECT context_window($model)", {"model": model}).fetchone()
    assert answered == (None,)


@pytest.fixture
def tagged_store(corpus_db: Path) -> Generator[duckdb.DuckDBPyConnection]:
    """The fixture corpus, read-only, carrying the macros.

    The store is reached through a fixture of its own rather than by the leaf, which is what
    gets it built before the tier's clock patch: that patch replaces `datetime.datetime`, and
    DuckDB cannot bind a real one while it stands (`tests/analyze/conftest.py`).
    """
    with duckdb.connect(str(corpus_db), read_only=True) as connection:
        macros.install(connection)
        yield connection


def test_tagged_answers_the_sessions_carrying_one_pair(
    tagged_store: duckdb.DuckDBPyConnection,
) -> None:
    """`tagged(key, value)` is the session-id set a query joins on, and nothing wider.

    The one macro here that reads a stored table, so this leaf needs the corpus store the
    others do without. The pair is the one `tests/conftest.py:build_store` stamps, and it is
    invented: a tag is the caller's word about an extract, and no recording carries one.
    """
    # If the corpus holds two sessions stamped with one pair, among many stamped with none,
    # then the macro answers those two and no other...
    assert tagged_store.execute(
        "SELECT * FROM tagged($key, $value) ORDER BY session_id",
        {"key": FIXTURE_TAG_KEY, "value": FIXTURE_TAG_VALUE},
    ).fetchall() == sorted((session,) for session in TAGGED_SESSIONS)
    # ...a value nobody stamped, under a key somebody did, is not a near miss...
    assert (
        tagged_store.execute(
            "SELECT * FROM tagged($key, 'another-batch')", {"key": FIXTURE_TAG_KEY}
        ).fetchall()
        == []
    )
    # ...and an unknown pair is an empty relation rather than an error, which is an absence a
    # query can join on.
    assert tagged_store.execute("SELECT * FROM tagged('nope', 'nope')").fetchall() == []


def test_a_statement_calling_tagged_is_told_to_install_the_macros() -> None:
    """A query naming a macro carries the definitions a reader needs to re-run it.

    The viewer's query page prints `needed_by`'s answer above the statement, so a macro
    missing from `DEFINITIONS` would leave a reader a statement no connection of their own
    can run (`view/pages/query/read.py`).
    """
    assert macros.needed_by("SELECT * FROM tagged($key, $value)") == macros.SETUP
    assert "tagged(" in macros.SETUP
