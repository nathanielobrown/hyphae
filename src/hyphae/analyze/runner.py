"""Runs one library query against the trace store and hands back its rows and its citation.

The store is opened read-only, and every value the caller supplies reaches DuckDB as a bound
parameter — nothing is interpolated into SQL. The runner resolves the request — which
statement, at which bindings, over which project — and `store.analysis` runs it: a corpus
query reads the relations `scope` built from `--project` (`src/hyphae/store/analysis.py`).
"""

import datetime as dt
from collections.abc import Mapping
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

from hyphae.analyze import manifest
from hyphae.models.analysis import Answered
from hyphae.models.citation import ParamValue
from hyphae.store import library
from hyphae.store.handle import open_store
from hyphae.store.library import NoDefault, ParamType, QueryError, Scope
from hyphae.store.schema import SchemaVersionError
from hyphae.store.trace_store import CLI_WAIT, StoreLocked


@dataclass(frozen=True)
class Result:
    """One query's answer, and the line a report copies to show what produced it."""

    answer: Answered
    # Sessions with no `project_dir`; None for a keyed query, which asks about one session.
    unplaceable_sessions: int | None

    @property
    def citation(self) -> str:
        """Query file and resolved bindings, as a SQL comment: the claim's query."""
        return library.citation(*self.answer.citation)


def run(
    db: Path,
    name: str,
    *,
    project: Path | None,
    since: dt.date | None,
    as_of: dt.date,
    params: Mapping[str, str],
) -> Result:
    """Bind one library query and run it read-only against the store at `db`.

    `params` are raw `k=v` strings; each is parsed to the type its manifest entry declares.
    Raises `QueryError` for anything the library cannot account for — an unknown query, an
    undeclared parameter, a required one left unbound, `--project` where it is needed or
    where it means nothing.
    """
    query = manifest.describe(name)
    bindings = _resolve(name, query.params, params)
    corpus = query.scope is Scope.CORPUS
    if corpus and project is None:
        raise QueryError(f"{name} counts across sessions: it needs --project")
    if not corpus and (project is not None or since is not None):
        raise QueryError(
            f"{name} is keyed to one session: --project and --since mean nothing to it"
        )

    # The store's one opener, which checks the version and builds the views this code reads.
    # Its refusals are translated here rather than let through: everything `hp query` reports
    # arrives as a `QueryError`, whichever part of the request it came from.
    opened = ExitStack()
    try:
        store = opened.enter_context(open_store(db, read_only=True, wait=CLI_WAIT))
    except (FileNotFoundError, SchemaVersionError, StoreLocked) as error:
        raise QueryError(str(error)) from error
    with opened:
        unplaceable = None
        if corpus:
            # Narrowing for the type checker; `corpus and project is None` raised above.
            assert project is not None  # noqa: S101
            unplaceable = store.analysis.scope(project=project, since=since, as_of=as_of)
        return Result(store.analysis.run(name, bindings), unplaceable)


def _resolve(
    name: str, declared: Mapping[str, library.Param], given: Mapping[str, str]
) -> dict[str, ParamValue]:
    """Parse what the caller passed, fill in the production defaults, refuse the rest."""
    unknown = set(given) - set(declared)
    if unknown:
        raise QueryError(f"{name} declares no parameter named {', '.join(sorted(unknown))}")
    resolved: dict[str, ParamValue] = {}
    missing = []
    for parameter, spec in declared.items():
        if parameter in given:
            resolved[parameter] = _parse(parameter, spec.type, given[parameter])
        elif isinstance(spec.default, NoDefault):
            missing.append(parameter)
        else:
            resolved[parameter] = spec.default
    if missing:
        raise QueryError(
            f"{name} has no default for {', '.join(missing)}: "
            f"bind each with --param {missing[0]}=<value>"
        )
    return resolved


def _parse(parameter: str, type_: ParamType, text: str) -> ParamValue:
    try:
        match type_:
            case ParamType.TEXT:
                return text
            case ParamType.INTEGER:
                return int(text)
            case ParamType.DATE:
                return dt.date.fromisoformat(text)
            case _:
                # A type this function has no arm for. Falling off the end of a match hands
                # back None, which DuckDB binds as SQL NULL and the citation reports as
                # bound — a wrong answer with nothing marking it, so a fourth type stops here.
                raise QueryError(f"--param {parameter}: nothing binds a {type_} parameter")
    except ValueError as error:
        raise QueryError(f"--param {parameter}={text} is not a {type_}: {error}") from error
