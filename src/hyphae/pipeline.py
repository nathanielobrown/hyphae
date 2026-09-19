"""The seams: what an extractor and an exporter owe each other, and the loop that drives them.

`refresh()` is the whole pipeline. The caller hands it the sessions an extractor discovered,
each with what it currently looks like; the loop asks the exporter what it already holds and
re-extracts only the difference. Everything about where sessions come from lives behind
`Extractor`; everything sink-specific behind `Exporter`.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import NamedTuple, Protocol

from hyphae.models.trace import SessionTrace


class ExtractionError(Exception):
    """An extractor refusing one session: the one class `refresh` catches.

    The loop records the session as failed and moves on. Anything else an extractor raises
    is the whole pass's problem and stops it.
    """


@dataclass(frozen=True)
class SessionSource:
    """One session as discovery found it, in the two things the pipeline itself reads.

    An extractor subclasses this to hand its own `extract()` whatever else it will need —
    where the files are, a row id, a URL. Nothing here interprets that, which is what keeps
    the origin-specific half behind `Extractor`.
    """

    id: str
    # Changes whenever any of the session's files does. Comparing it against the sink's
    # copy is the only thing that decides whether a session is re-extracted.
    fingerprint: str


class Extractor[SourceT: SessionSource](Protocol):
    """Turns recorded sessions into traces, from an agent's recordings or the store's rows.

    One implementation per origin. `SourceT` is the extractor's own `SessionSource`
    subclass: the extractor mints them from whatever it discovers by — a typed path, a
    directory, a store — and `extract()` is the only thing that reads what it added.
    Discovery is the extractor's own interface, not the loop's: `refresh()` takes the
    sources already minted.
    """

    def extract(self, source: SourceT) -> SessionTrace:
        """Read one session and build its trace."""
        ...


class Exporter(Protocol):
    """Writes traces into a sink. One implementation per sink."""

    def fingerprints(self) -> dict[str, str]:
        """Session id to the fingerprint the sink holds, for every session it holds.

        Sessions whose files are gone from disk stay in here: the sink is the archive.
        """
        ...

    def export(self, trace: SessionTrace, fingerprint: str) -> None:
        """Make the sink hold this session at this fingerprint, replacing what it held.

        All or nothing per session: returning means `fingerprints()` now reports this
        fingerprint, and raising means it still reports no new one, so the next run sends
        the session again. What a failure leaves in the sink is the sink's own business —
        the store rolls back to the old copy, an append-only backend keeps what landed.
        """
        ...


class Failure(NamedTuple):
    """One session the extractor refused, and what it said about it."""

    session_id: str
    # The refusal's own words, which name a model, a field and a line and quote no record
    # content (`extract/errors.py`) — so a caller may print it.
    error: str


class RefreshResult(NamedTuple):
    """What one pass changed, in session ids — enough for a caller to report or assert on."""

    extracted: list[str]
    skipped: list[str]
    failed: list[Failure]


def refresh[SourceT: SessionSource](
    sources: Iterable[SourceT], *, extractor: Extractor[SourceT], exporter: Exporter
) -> RefreshResult:
    """Bring the sink up to date with `sources`, the sessions the extractor discovered.

    Idempotent by construction: an unchanged session is skipped, and a changed one is sent
    whole — nothing here diffs a session against what the sink already holds. A session in
    the sink that is not among `sources` keeps its rows.

    A session the extractor refuses costs only itself: it lands in `failed` and the pass carries
    on. The export is all or nothing per session, so there is nothing half-written to undo.
    """
    held = exporter.fingerprints()
    extracted: list[str] = []
    skipped: list[str] = []
    failed: list[Failure] = []
    for source in sources:
        if held.get(source.id) == source.fingerprint:
            skipped.append(source.id)
            continue
        try:
            exporter.export(extractor.extract(source), source.fingerprint)
        except ExtractionError as error:
            # Only what the extractor refused for this session. Anything else — the sink
            # refusing to open, a session directory that cannot be read — is the whole pass's
            # problem and still stops it.
            failed.append(Failure(session_id=source.id, error=str(error)))
            continue
        extracted.append(source.id)
    return RefreshResult(extracted=extracted, skipped=skipped, failed=failed)
