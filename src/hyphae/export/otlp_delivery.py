"""Getting shaped spans to a backend, knowing what landed, and counting what has not.

At-least-once with stable ids. A delivery row in the store records the fingerprint and the
mapper version a session shipped under, so re-running ships only what moved and a shaping
change re-ships the corpus (`docs/otlp-export.md`). A failed run re-sends the session whole
rather than diffing what got through — an append-only backend never dedupes.

What a session becomes on the way here is `export/otlp.py`; this module reads no session
row, only the spans that module made and the delivery ledger `store/delivery.py` keeps.
"""

import gzip
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from types import TracebackType

import httpx
from opentelemetry.proto.collector.trace.v1 import trace_service_pb2
from opentelemetry.proto.resource.v1 import resource_pb2
from opentelemetry.proto.trace.v1 import trace_pb2

from hyphae.export.otlp import (
    MAPPER_VERSION,
    METADATA_ONLY,
    Census,
    TextPolicy,
    census,
    session_resource,
    session_spans,
)
from hyphae.models.trace import SessionTrace
from hyphae.store.delivery import DeliveryLedger

# Spans per POST. The biggest canonical session is ~29K spans, so a backfill of it is ~15
# requests. A parameter rather than a constant so tests can bind it down and cross a real
# batch boundary on a recorded session.
DEFAULT_BATCH_SPANS = 2_000

# Spans per second, across a whole run. Prior art measured ~40% silent server-side loss with
# no limiter and none at this rate (issue #6); it puts the full corpus at ~16 minutes, which
# is a backfill's price for not losing two spans in five.
DEFAULT_RATE = 300.0

# Per request. A backend that has not answered by then is down, not slow.
DEFAULT_TIMEOUT = 30.0

# A 429 or a 5xx is the backend asking us to come back; anything else is our bug. Attempts
# include the first, and the wait doubles between them unless `Retry-After` says otherwise.
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.0

# What the environment holds for the base-case backend: any OTLP/HTTP endpoint.
GENERIC = "generic"
ENDPOINT_ENV = "OTLP_ENDPOINT"
HEADERS_ENV = "OTLP_HEADERS"


@dataclass(frozen=True)
class Backend:
    """Where spans go, and the name its delivery rows are recorded under.

    `headers` carries the key. It is never logged and never interpolated into an error —
    the crash paths are exactly where one gets published by accident.
    """

    name: str
    endpoint: str
    headers: dict[str, str] = field(default_factory=dict)


class ConfigurationError(Exception):
    """The environment does not say where to ship. Raised before anything is read."""


class BackendMismatchError(Exception):
    """A send was handed the ledger of another backend, so it would record the wrong name."""


class DeliveryError(Exception):
    """A batch never landed: the backend refused it, or stopped answering."""


class RejectedSpansError(Exception):
    """The backend took the request and kept only part of it — a mapper bug we need to see."""


@dataclass(frozen=True)
class BackendSpec:
    """A named backend: where it takes spans, and how its key travels.

    Endpoints and header names verified against prior art
    (`/Users/nob/repos/mac_settings/claude-otel/import_transcripts.py:114`).
    """

    endpoint: str
    # The environment variable holding the key, and the header it goes in *bare* — Logfire
    # refuses an `authorization: Bearer …`, and the failure is a 401 an hour into a backfill.
    key_env: str
    header: str


BACKENDS: dict[str, BackendSpec] = {
    "honeycomb": BackendSpec(
        endpoint="https://api.honeycomb.io/v1/traces",
        key_env="HONEYCOMB_API_KEY",
        header="x-honeycomb-team",
    ),
    "logfire": BackendSpec(
        endpoint="https://logfire-us.pydantic.dev/v1/traces",
        key_env="LOGFIRE_API_KEY",
        header="authorization",
    ),
}

# What `--backend` takes. Discovered from the registry, so adding an entry is one edit.
BACKEND_NAMES = (GENERIC, *BACKENDS)


def named_backend(name: str, environ: Mapping[str, str]) -> Backend:
    """Where `--backend <name>` ships, resolved from the environment.

    Validated here rather than at the first POST, so a misconfigured run refuses before it
    reads a session. `OTLP_ENDPOINT` overrides a named backend's endpoint — the way a run
    reaches a collector standing in front of the real thing.
    """
    if name == GENERIC:
        return generic_backend(environ)
    spec = BACKENDS[name]
    key = environ.get(spec.key_env, "").strip()
    if not key:
        raise ConfigurationError(f"{spec.key_env} is unset or empty. Set it in the environment")
    return Backend(
        name=name,
        endpoint=environ.get(ENDPOINT_ENV, "").strip() or spec.endpoint,
        headers={spec.header: key},
    )


def generic_backend(environ: Mapping[str, str]) -> Backend:
    """The base-case backend: any OTLP/HTTP endpoint, with optional headers.

    Validated here rather than at the first POST, so a misconfigured run refuses before it
    reads a session. `OTLP_HEADERS` is `name=value` pairs separated by commas.
    """
    endpoint = environ.get(ENDPOINT_ENV, "").strip()
    if not endpoint:
        raise ConfigurationError(f"{ENDPOINT_ENV} is unset or empty. Set it in the environment")
    return Backend(name=GENERIC, endpoint=endpoint, headers=_headers(environ.get(HEADERS_ENV, "")))


def _headers(value: str) -> dict[str, str]:
    pairs = [pair.strip() for pair in value.split(",") if pair.strip()]
    if any("=" not in pair for pair in pairs):
        raise ConfigurationError(f"{HEADERS_ENV} takes comma-separated name=value pairs")
    return dict(pair.split("=", 1) for pair in pairs)


class _Pacer:
    """A token bucket over spans, so a run cannot outrun what a backend will really keep.

    Waits through the injected clock rather than `time.sleep`, which is what lets a test
    assert the delay a send *asked* for instead of measuring one.
    """

    def __init__(
        self, rate: float, monotonic: Callable[[], float], sleep: Callable[[float], None]
    ) -> None:
        if rate <= 0:
            raise ConfigurationError(f"a rate of {rate} spans/s would never send anything")
        self.rate = rate
        self.monotonic = monotonic
        self.sleep = sleep
        self.ready = monotonic()

    def wait(self, spans: int) -> None:
        """Block until this many spans may leave, then charge them to the bucket."""
        now = self.monotonic()
        if now < self.ready:
            self.sleep(self.ready - now)
            now = self.ready
        self.ready = now + spans / self.rate


class OtlpCensus:
    """Counts what a send to one backend would ship, and ships nothing.

    The dry run's `Exporter`, driven by the same `refresh()` as a send: the ledger says what
    that backend already holds, so a census counts the remainder rather than the whole
    selection. It holds no `Backend`, so there is nowhere for one to send and no key to need.
    """

    def __init__(self, ledger: DeliveryLedger, *, text: TextPolicy) -> None:
        self.ledger = ledger
        # No default: the caller must choose, even though the policy moves attributes rather
        # than the span count — `session_spans` emits one span per live row whatever it is.
        self.text = text
        self.counts = Census(sessions=0, spans=0, compactions=0)

    def fingerprints(self) -> dict[str, str]:
        """What this backend holds, which is what the count leaves out."""
        return self.ledger.fingerprints(mapper_version=MAPPER_VERSION)

    def export(self, trace: SessionTrace, fingerprint: str) -> None:
        """Shape one session the way a send would, and count it instead of posting it.

        Breaks the `Exporter` protocol's post-condition that `fingerprints()` reports the
        fingerprint afterwards — this counts a session without recording it as held. Safe
        because `refresh()` reads `fingerprints()` once, before any `export()` call; a second
        `refresh()` over the same census would count the same sessions again.
        """
        self.counts += census([trace], self.text)


class OtlpExporter:
    """Ships each session's spans to one backend and records what the backend confirmed.

    The promise is at-least-once with stable ids: a session is sent whole or not at all, a
    failure records nothing and re-sends next run, and a backend that ignores span identity
    will hold duplicates. Nothing here diffs what already landed — that machinery was the
    prior importer's largest bug source.

    Reaches the store only through the `DeliveryLedger` it is handed, which is what a census
    reads instead of sending.
    """

    def __init__(
        self,
        backend: Backend,
        ledger: DeliveryLedger,
        *,
        service_name: str | None = None,
        text: TextPolicy = METADATA_ONLY,
        batch_spans: int = DEFAULT_BATCH_SPANS,
        rate: float = DEFAULT_RATE,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        # One name, spelled twice: recording under a backend this run never shipped to would
        # leave the real one permanently undelivered, and the store would say otherwise.
        if ledger.backend != backend.name:
            raise BackendMismatchError(
                f"a send to {backend.name} was handed the ledger of {ledger.backend}"
            )
        self.backend = backend
        self.ledger = ledger
        # None routes each session to a service named for its project directory.
        self.service_name = service_name
        # Transcript text stays home unless the caller opts it in.
        self.text = text
        self.batch_spans = batch_spans
        # Time is a seam: both the rate bucket and the retry backoff wait through these, so a
        # test asserts the delay a send *asked* for instead of waiting it out.
        self.sleep = sleep
        self.pacer = _Pacer(rate, monotonic, sleep)
        self.client = httpx.Client(timeout=timeout)
        # A send is the only thing that may grow the table: the census reads the same ledger
        # over a read-only connection, which could not run this.
        ledger.create()

    def __enter__(self) -> "OtlpExporter":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Closes the HTTP client. The store connection belongs to the caller."""
        self.client.close()

    def fingerprints(self) -> dict[str, str]:
        """What this backend holds, as far as delivery can tell."""
        return self.ledger.fingerprints(mapper_version=MAPPER_VERSION)

    def export(self, trace: SessionTrace, fingerprint: str) -> None:
        """Ship one session, and record it only once every batch came back confirmed."""
        spans = session_spans(trace, self.text)
        resource = session_resource(trace.session, self.service_name)
        sent = 0
        for index, batch in enumerate(_batches(spans, self.batch_spans)):
            self._post(trace.session.id, index, batch, resource)
            sent += len(batch)
        self.ledger.record(trace.session.id, fingerprint, sent, mapper_version=MAPPER_VERSION)

    def _post(
        self,
        session_id: str,
        index: int,
        batch: list[trace_pb2.Span],
        resource: resource_pb2.Resource,
    ) -> None:
        """Send one batch and read the answer, retrying only what the backend asked us to."""
        payload = trace_service_pb2.ExportTraceServiceRequest(
            resource_spans=[
                trace_pb2.ResourceSpans(
                    resource=resource, scope_spans=[trace_pb2.ScopeSpans(spans=batch)]
                )
            ]
        ).SerializeToString()
        # Compressed here rather than by httpx: the payload is protobuf, it is large, and a
        # fixed mtime keeps the same batch encoding to the same bytes.
        body = gzip.compress(payload, mtime=0)
        headers = {
            "Content-Type": "application/x-protobuf",
            "Content-Encoding": "gzip",
            **self.backend.headers,
        }
        for attempt in range(1, MAX_ATTEMPTS + 1):
            # Every attempt is charged, including a retry: what a backend throttles on is
            # what actually arrives, not what we meant to send once.
            self.pacer.wait(len(batch))
            response = self.client.post(self.backend.endpoint, content=body, headers=headers)
            if response.is_success:
                self._check_rejections(session_id, index, response.content)
                return
            retryable = response.status_code == 429 or response.status_code >= 500
            if not retryable or attempt == MAX_ATTEMPTS:
                raise DeliveryError(
                    f"{self.backend.name} answered {response.status_code} for session "
                    f"{session_id} batch {index} after {attempt} attempt(s). Nothing was "
                    f"recorded as delivered; the next run sends the session again."
                )
            self.sleep(_backoff(response.headers.get("Retry-After"), attempt))

    def _check_rejections(self, session_id: str, index: int, content: bytes) -> None:
        """Crash on a partial acceptance: the run is stuck here until the mapper changes.

        A deterministic rejection — an attribute cap, a timestamp the backend refuses —
        makes this session a poison pill: every run crashes at it and the sessions behind it
        stop shipping. That is the intended shape. It is a mapper bug, the fix is a mapper
        change, and the `MAPPER_VERSION` bump that comes with it re-sends everything.
        """
        reply = trace_service_pb2.ExportTraceServiceResponse()
        reply.ParseFromString(content)
        if not reply.partial_success.rejected_spans:
            return
        raise RejectedSpansError(
            f"{self.backend.name} rejected {reply.partial_success.rejected_spans} span(s) of "
            f"session {session_id} batch {index}: "
            f"{reply.partial_success.error_message or 'no reason given'}. Nothing was "
            f"recorded as delivered, and no flag skips it — fix the mapper and bump "
            f"MAPPER_VERSION."
        )


def _backoff(retry_after: str | None, attempt: int) -> float:
    """How long to wait before the next attempt, honoring the backend's own answer."""
    if retry_after is not None and retry_after.strip().isdigit():
        return float(retry_after)
    return BACKOFF_SECONDS * 2 ** (attempt - 1)


def _batches(spans: list[trace_pb2.Span], size: int) -> Iterator[list[trace_pb2.Span]]:
    """The spans in POST-sized runs. Sequential and built here, so there is no queue to
    overflow — the failure shape that lost 82.9% of the prior importer's spans."""
    for start in range(0, len(spans), size):
        yield spans[start : start + size]
