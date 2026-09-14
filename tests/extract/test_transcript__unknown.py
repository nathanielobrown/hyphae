"""What `read_lines` does with a record the models do not describe: a crash, or a tally.

Three failures, one seam. A field whose *value* has the wrong shape is a validation error, and
the message it turns into is this package's promise to whoever reads a crash — a reader needs
that field, so it crashes in every mode. The other two are `Unknowns`' business and share its
two tiers: a *kind* neither registry names, which is archived verbatim, and a *field* no model
declares inside a kind we do read. The corpus leaf in `test_records.py` proves the models
describe the fixtures; these leaves prove the walks themselves — where they descend, where they
stop, and what they say when they find something. Everything goes through `read_lines`, where
validation and the walks meet in an extract, so no leaf here reaches past the seam the extractor
uses.

The driving fixtures are invented by necessity: a kind no registry names and a field no model
declares are, by construction, shapes no recorded session in this repository carries.
`tests/fixtures/invented/README.md` labels them, and their invented values are the tripwire
string, so every leaf here can assert that the value never reaches a message or a report. One
file per position a walk has to get right, because strict mode stops at the first thing it meets.
"""

from pathlib import Path

import pytest

from hyphae import settings
from hyphae.extract.claude_code import ClaudeCodeExtractor
from hyphae.extract.errors import TranscriptSchemaError
from hyphae.extract.records.shapes import ArchivedRecord
from hyphae.extract.records.unknown import Unknowns
from hyphae.extract.transcript import read_lines
from tests.conftest import FIXTURES

INVENTED = FIXTURES / "invented"
# One undeclared field each, at the four places the walk has to tell apart. Every file opens with
# a `mode` record, as every file in `invented/` does, so the offender is on line 2 — except in the
# nested fixture, where a clean record ahead of it keeps the reported line from being every
# file's line.
ENVELOPE = INVENTED / "invented-unknown-field.jsonl"
NESTED = INVENTED / "invented-unknown-nested-field.jsonl"
BLOCK = INVENTED / "invented-unknown-block-field.jsonl"
OPAQUE = INVENTED / "invented-unknown-opaque-field.jsonl"
OFFENDING_LINE = 2
NESTED_LINE = 3
# The same two positions, one level up: a record whose kind no registry names at all, at each of
# the two levels the envelope has. Both are on line 2, as everything invented here is.
UNKNOWN_TYPE = INVENTED / "invented-unknown-type.jsonl"
UNKNOWN_SUBTYPE = INVENTED / "invented-unknown-subtype.jsonl"
# The value every invented field in those fixtures carries. A crash message or a tally line that
# names it has leaked transcript content, which is the one failure mode worse than a wrong count.
TRIPWIRE = "SUPER-SECRET-PAYLOAD-9f2a"
# A recorded fixture whose every field the models declare — the negative control for `report()`.
CLEAN = FIXTURES / "model_only"
ZOO = FIXTURES / "registry_zoo"


# A record whose declared field carries the wrong shape: the second thing `read_lines` can raise.
WRONG_TYPE = INVENTED / "invented-wrong-field-type.jsonl"


def test_a_wrongly_typed_field_names_the_model_the_field_and_where_it_was() -> None:
    # The error contract, which is the whole reason validation happens at the seam rather than
    # wherever a reader first trips over the value. A person reading this crash has the record's
    # address and the field's, and nothing else: the value is transcript content, and one that
    # reached a log would be a privacy incident rather than a bad message.
    unknowns = Unknowns(strict=True)

    with pytest.raises(TranscriptSchemaError) as raised:
        read_lines(WRONG_TYPE, "wrong-type-session", unknowns)

    message = str(raised.value)
    assert "AssistantRecord" in message
    assert "wrong-type-session" in message
    assert str(OFFENDING_LINE) in message
    assert TRIPWIRE not in message
    # Both faults, in one message, joined: a record with two bad fields would otherwise be read
    # twice, once per crash, and the second fault only found after the first was fixed.
    assert "isSidechain: Input should be a valid boolean" in message, message
    assert "; message.usage.input_tokens: Input should be a valid integer" in message, message


def test_a_validation_message_carries_neither_the_value_nor_a_link_to_pydantic() -> None:
    # How the message stays clean: pydantic renders `input=` and a documentation URL by default,
    # and the first of those is the private half of the record. Turning both off is one call
    # argument, so this leaf is what says it was a decision.
    unknowns = Unknowns(strict=True)

    with pytest.raises(TranscriptSchemaError) as raised:
        read_lines(WRONG_TYPE, "wrong-type-session", unknowns)

    assert "input=" not in str(raised.value)
    assert "https://errors.pydantic.dev" not in str(raised.value)


@pytest.mark.parametrize(
    ("transcript", "kind"),
    [(UNKNOWN_TYPE, "telepathy"), (UNKNOWN_SUBTYPE, "system/quantum_flux")],
    ids=["a-record-type", "a-system-subtype"],
)
def test_strict_mode_stops_on_a_record_kind_no_registry_names(transcript: Path, kind: str) -> None:
    # The upper tier, where a person is looking: a kind neither registry names means Claude Code
    # writes a record shape we have never read, and the run stops at the line that proves it. The
    # kind is named at the level it was spelled — a bare `quantum_flux` would read as a top-level
    # type — and the rest of the message is the address, because a transcript is private.
    unknowns = Unknowns(strict=True)

    with pytest.raises(TranscriptSchemaError) as raised:
        read_lines(transcript, "unknown-kind-session", unknowns)

    message = str(raised.value)
    assert f"`{kind}`" in message
    assert "unknown-kind-session" in message
    assert str(OFFENDING_LINE) in message
    assert TRIPWIRE not in message


def test_a_kind_no_registry_names_is_archived_whole_rather_than_dropped() -> None:
    # What an extract does with it instead, and the reason this tier is not fatal: one bookkeeping
    # record Claude Code added yesterday used to end the session's extract, and every other user's
    # too. Now the record lands in the archive under the model that claims only the envelope, so
    # the session is extracted and the new kind is recoverable from the store the moment someone
    # writes its model.
    unknowns = Unknowns(strict=False)

    lines = read_lines(UNKNOWN_TYPE, "first-session", unknowns)

    # The whole file is kept, the unknown record among it, verbatim...
    assert [type(line.record) for line in lines] == [ArchivedRecord, ArchivedRecord]
    assert lines[OFFENDING_LINE - 1].record.type == "telepathy"
    assert lines[OFFENDING_LINE - 1].raw == UNKNOWN_TYPE.read_text().split("\n")[1]
    # ...and its own keys are the archive's, not undeclared fields: `ArchivedRecord` is opaque, so
    # the field walk stops at it rather than reporting every key of a kind nobody has read.
    assert unknowns.fields.report() == ""


def test_lax_mode_tallies_a_kind_once_at_the_level_it_was_spelled() -> None:
    # The news an extract prints, in the same shape the field tally prints: one entry per kind
    # however many records carried it, with where it was first seen and how many sessions have it.
    # A kind is spelled with its level, so a subtype and a type of the same name stay two entries.
    unknowns = Unknowns(strict=False)

    for session in ("first-session", "second-session"):
        for transcript in (UNKNOWN_TYPE, UNKNOWN_SUBTYPE):
            read_lines(transcript, session, unknowns)

    assert unknowns.kinds.report() == (
        f"system/quantum_flux: first in session first-session "
        f"line {OFFENDING_LINE}, 2 session(s)\n"
        f"telepathy: first in session first-session line {OFFENDING_LINE}, 2 session(s)"
    )
    assert TRIPWIRE not in unknowns.kinds.report()


def test_strict_mode_stops_on_a_field_no_model_declares() -> None:
    # Strict is what the suite runs under: an undeclared field means the models no longer describe
    # what Claude Code writes, and the run stops at the record that proves it. The message is the
    # whole address a person needs — which model, which field, which session, which line — and
    # nothing else, because everything else in a transcript is private.
    unknowns = Unknowns(strict=True)

    with pytest.raises(TranscriptSchemaError) as raised:
        read_lines(ENVELOPE, "unknown-field-session", unknowns)

    message = str(raised.value)
    assert "assistant.shimmerBudget" in message
    assert "unknown-field-session" in message
    assert str(OFFENDING_LINE) in message
    assert TRIPWIRE not in message


def test_the_walk_descends_into_the_models_nested_inside_a_record() -> None:
    # The leaf that makes the claim worth making. `usage` is where Claude Code adds fields most
    # often, and it is three models down from the record: a walk that only checked the envelope
    # would pass every other leaf here while proving nothing about the place fields actually
    # arrive. The reported path is the address, spelled the way the record spells it.
    unknowns = Unknowns(strict=True)

    with pytest.raises(TranscriptSchemaError) as raised:
        read_lines(NESTED, "unknown-field-session", unknowns)

    assert "assistant.message.usage.shimmer_tokens" in str(raised.value)
    assert str(NESTED_LINE) in str(raised.value)
    assert TRIPWIRE not in str(raised.value)


def test_the_walk_descends_into_every_block_of_a_content_list() -> None:
    # The position a list costs: `message.content` is a list of models, not a model, so a walk
    # that only followed fields would stop at the list and report nothing about the blocks —
    # silently, which is why this leaf exists rather than a mutation catching it. A block is
    # addressed by its kind rather than its index, the way the schema tables name it, because
    # two blocks of one kind are one claim.
    unknowns = Unknowns(strict=True)

    with pytest.raises(TranscriptSchemaError) as raised:
        read_lines(BLOCK, "unknown-field-session", unknowns)

    assert "assistant.message.content.thinking.shimmerTag" in str(raised.value)
    assert TRIPWIRE not in str(raised.value)


@pytest.mark.parametrize("strict", [True, False])
def test_the_walk_stops_at_a_tools_own_report(strict: bool) -> None:
    # The boundary the design buys with `OPAQUE`. A `toolUseResult` is written by whichever tool
    # ran, so its keys are an open set that Claude Code does not own and the models cannot claim.
    # The walk stops there in both modes: no crash under strict, no tally under lax. Without this,
    # the corpus leaf would be a demand that we describe every tool anyone ever writes.
    unknowns = Unknowns(strict=strict)

    read_lines(OPAQUE, "unknown-field-session", unknowns)

    assert unknowns.fields.report() == ""


def test_an_archived_kind_carries_whatever_it_likes() -> None:
    # The same stop, for the other opaque model. `ArchivedRecord` declares the envelope `raw_record`
    # writes and nothing else, so the 24k `attachment` records in the store — and the six thin
    # `system` subtypes — carry keys no model declares by construction. Strict mode has to walk
    # right past them, or the archive would stop every run.
    unknowns = Unknowns(strict=True)

    for transcript in sorted(ZOO.rglob("*.jsonl")):
        read_lines(transcript, transcript.stem, unknowns)

    assert unknowns.fields.report() == ""
    # And every kind in the zoo is one a registry names: an unregistered one raises above under
    # strict rather than reaching this line, which is the regression net registering a kind buys.
    assert unknowns.kinds.report() == ""


def test_lax_mode_tallies_one_entry_per_path_with_its_first_sighting() -> None:
    # What an extract does instead of crashing: a field Claude Code added yesterday is news, not a
    # reason to stop archiving. One entry per path however many records carried it, holding where
    # it was first seen and how many sessions have it — the two numbers that say whether it is a
    # new field rolling out or one session doing something odd.
    unknowns = Unknowns(strict=False)

    for session in ("first-session", "second-session"):
        for transcript in (ENVELOPE, NESTED, BLOCK, OPAQUE):
            read_lines(transcript, session, unknowns)

    # The report is what an extract prints, so pin the whole of it: one line per path, in path
    # order. Three paths, not four — the invented key inside `toolUseResult` is behind the opaque
    # stop. Every line says `first-session`, so the second read overwrote no first sighting; a
    # field's arrival date would otherwise drift to whenever the extractor last ran.
    assert unknowns.fields.report() == (
        f"assistant.message.content.thinking.shimmerTag: first in session first-session "
        f"line {OFFENDING_LINE}, 2 session(s)\n"
        f"assistant.message.usage.shimmer_tokens: first in session first-session "
        f"line {NESTED_LINE}, 2 session(s)\n"
        f"assistant.shimmerBudget: first in session first-session "
        f"line {OFFENDING_LINE}, 2 session(s)"
    )
    assert TRIPWIRE not in unknowns.fields.report()


def test_a_clean_transcript_reports_nothing() -> None:
    # The negative control, and what "the models are the schema" looks like when it holds: a
    # recorded session through the models leaves an empty report. Without this leaf, a walk that
    # silently found nothing anywhere would pass every assertion above.
    unknowns = Unknowns(strict=False)

    for transcript in sorted(CLEAN.rglob("*.jsonl")):
        read_lines(transcript, transcript.stem, unknowns)

    assert unknowns.fields.report() == ""


def test_the_suite_runs_strict_however_it_was_started() -> None:
    # What makes every leaf above worth anything in the tier that does not write them: the
    # extractor asks `settings.UNIT_TESTING` for its mode, and `pytest-env` sets the variable for
    # every pytest invocation from `pyproject.toml`. Run this leaf on its own with a bare
    # `uv run pytest` — it is red if the variable is set anywhere else, such as the test task,
    # which would leave a developer running one file walking in lax mode and proving nothing.
    assert settings.UNIT_TESTING is True


def test_each_extractor_run_tallies_on_its_own() -> None:
    # Whose tallies they are. One `Unknowns` per extractor, exposed so the CLI can print it after
    # a refresh: the count of sessions carrying a field only means something if it counts one
    # run's sessions, and a tally shared between two runs would carry the last one's news.
    first, second = ClaudeCodeExtractor(), ClaudeCodeExtractor()

    assert first.unknowns is not second.unknowns
    # And a test run's extractor is strict, which is what makes the corpus leaf a gate rather
    # than a report nobody reads.
    assert first.unknowns.strict is settings.UNIT_TESTING
