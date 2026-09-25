"""A message delivered while a turn was running: who sent it, which turn it reached, and the
shapes that stop an extract rather than lose one."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from hyphae.extract.claude_code import ClaudeCodeExtractor
from hyphae.extract.errors import TranscriptSchemaError
from hyphae.models.trace import MAIN_SOURCE, Interjection, Sender
from tests.conftest import (
    FIXTURES,
    INTERJECTION,
    SENDERS,
    SENDERS_RUN,
    WAITED,
    SourceFactory,
)


def test_each_message_comes_out_whole_under_the_turn_it_landed_in(
    fixture_source: SourceFactory,
):
    """Every queued command becomes one interjection: who sent it, the turn open where it sits
    in the file, and its text in full."""
    trace = ClaudeCodeExtractor().extract(fixture_source("interjection", INTERJECTION))

    # The task's notice is kept verbatim, tags and all, so it is read off the fixture's first
    # line rather than retyped.
    notice = json.loads(
        (FIXTURES / "interjection" / f"{INTERJECTION}.jsonl").read_text().splitlines()[0]
    )["attachment"]["prompt"]
    assert trace.interjections == [
        # A background task finished before the session's first prompt, so its notice sits
        # under no turn and is still a row...
        Interjection(
            id="36b2e375-cb57-4179-9cf3-97c4763f77fd",
            session_id=INTERJECTION,
            source=MAIN_SOURCE,
            turn_id=None,
            timestamp=datetime(2026, 7, 27, 15, 19, 34, tzinfo=UTC),
            sender=Sender.TASK,
            text=notice,
            replayed=False,
        ),
        # ...the person typed into the second turn while it ran, and the message belongs to
        # that turn...
        Interjection(
            id="e678460b-f949-44b5-bc87-d666ecf3da9f",
            session_id=INTERJECTION,
            source=MAIN_SOURCE,
            turn_id="534bc0a5-5c7f-4522-a24e-f59d8c38e2d8",
            timestamp=datetime(2026, 7, 27, 15, 26, 31, 826000, tzinfo=UTC),
            sender=Sender.PERSON,
            text="[redacted]",
            replayed=False,
        ),
        # ...and a pasted picture with a line of text flattens to the text, a blank line, and
        # a stand-in for the picture.
        Interjection(
            id="f3a71b8a-fc01-470c-934c-74600a0e18a0",
            session_id=INTERJECTION,
            source=MAIN_SOURCE,
            turn_id="9e4d80b7-3cc4-46b6-86c6-234179bf5da2",
            timestamp=datetime(2026, 7, 27, 15, 30, 45, tzinfo=UTC),
            sender=Sender.PERSON,
            text="[redacted]\n\n[image]",
            replayed=False,
        ),
    ]


def test_every_sender_is_heard_on_main_and_inside_an_agent_run(fixture_source: SourceFactory):
    """A task, the person and another agent each reach a turn, and a run's own messages stay
    on its own thread."""
    trace = ClaudeCodeExtractor().extract(fixture_source("interjection", SENDERS))

    main, thread = [
        FIXTURES / "interjection" / path
        for path in (f"{SENDERS}.jsonl", f"{SENDERS}/subagents/agent-{SENDERS_RUN}.jsonl")
    ]
    assert trace.interjections == [
        # A task's notice lands in the first turn with its 839 characters whole: the cap is the
        # enrichment prompt's business, not the store's...
        Interjection(
            id="30f794f4-8007-408a-9d00-29bcacd245e0",
            session_id=SENDERS,
            source=MAIN_SOURCE,
            turn_id="11b672e8-dc44-4771-8d7a-610d029da5f4",
            timestamp=datetime(2026, 9, 7, 1, 56, 58, 844000, tzinfo=UTC),
            sender=Sender.TASK,
            text=recorded_prompt(main, "30f794f4-8007-408a-9d00-29bcacd245e0"),
            replayed=False,
        ),
        # ...the person types into the second turn...
        Interjection(
            id="4ddb7877-e9fc-4af2-808a-d923fac88547",
            session_id=SENDERS,
            source=MAIN_SOURCE,
            turn_id="bc846857-b679-41ce-996f-4ff1d319da0c",
            timestamp=datetime(2026, 9, 7, 13, 49, 52, 395000, tzinfo=UTC),
            sender=Sender.PERSON,
            text="[redacted]",
            replayed=False,
        ),
        # ...and another session writes into the same turn. Its mode is `prompt`, as the
        # person's is, so only `origin.kind` says it was not the person.
        Interjection(
            id="32e86765-01c6-406f-859f-8a8fa5c4d5f8",
            session_id=SENDERS,
            source=MAIN_SOURCE,
            turn_id="bc846857-b679-41ce-996f-4ff1d319da0c",
            timestamp=datetime(2026, 9, 7, 13, 49, 58, tzinfo=UTC),
            sender=Sender.AGENT,
            text="[redacted]",
            replayed=False,
        ),
        # The agent run hears from two tasks and, between them, its coordinator. The
        # coordinator's record carries no queued-at time of its own, so the envelope's is the
        # only one it has.
        Interjection(
            id="82fd7a6b-8d3a-48a0-8f8e-03155431f1b7",
            session_id=SENDERS,
            source=SENDERS_RUN,
            turn_id="a77c360d-c02d-45a8-89c9-5ded4c9c2f55",
            timestamp=datetime(2026, 9, 7, 10, 33, 4, 281000, tzinfo=UTC),
            sender=Sender.TASK,
            text=recorded_prompt(thread, "82fd7a6b-8d3a-48a0-8f8e-03155431f1b7"),
            replayed=False,
        ),
        Interjection(
            id="fbfb2868-7ea4-40de-b485-2ad619cb0a22",
            session_id=SENDERS,
            source=SENDERS_RUN,
            turn_id="a77c360d-c02d-45a8-89c9-5ded4c9c2f55",
            timestamp=datetime(2026, 9, 7, 10, 40, 22, 817000, tzinfo=UTC),
            sender=Sender.AGENT,
            text="[redacted]",
            replayed=False,
        ),
        Interjection(
            id="057236c4-540e-4422-ada0-8df8be93943a",
            session_id=SENDERS,
            source=SENDERS_RUN,
            turn_id="a77c360d-c02d-45a8-89c9-5ded4c9c2f55",
            timestamp=datetime(2026, 9, 7, 10, 41, 23, 244000, tzinfo=UTC),
            sender=Sender.TASK,
            text=recorded_prompt(thread, "057236c4-540e-4422-ada0-8df8be93943a"),
            replayed=False,
        ),
    ]


def test_a_message_belongs_to_the_turn_open_where_it_sits_not_when_it_was_stamped(
    fixture_source: SourceFactory,
):
    """A task finished during a `/compact`, and its notice waited in the queue until the next
    prompt's turn was running. The file puts it in that turn, and so does the row."""
    trace = ClaudeCodeExtractor().extract(fixture_source("interjection", WAITED))

    command, prompt = trace.turns
    (notice,) = trace.interjections
    # The stamp falls inside the command's turn, so a reader going by the clock would file it
    # there...
    assert command.started_at < notice.timestamp < prompt.started_at
    # ...but it was written after the prompt, and it belongs to the prompt's turn.
    assert notice.turn_id == prompt.id == "0365e7c5-d09a-44eb-9f95-b2595a57ba9f"


def recorded_prompt(transcript: Path, uuid: str) -> str:
    """The queued command's text as the fixture holds it, for a row that keeps it verbatim."""
    for line in transcript.read_text().splitlines():
        record = json.loads(line)
        if record.get("uuid") == uuid:
            return record["attachment"]["prompt"]
    raise AssertionError(f"{uuid} is not in {transcript}")


def test_a_malformed_queued_command_crashes_rather_than_riding_as_another_attachment(
    fixture_source: SourceFactory,
):
    """A mid-turn message whose shape we cannot read stops the run.

    INVENTED fixture — every recorded queued command validates (scanned 2026-09-25), so a
    malformed one has no recording. Every attachment kind but this one is kept as a dict, so a
    union left to pick its own arm would file the broken message there, and the turn would lose
    it without a word.
    """
    with pytest.raises(TranscriptSchemaError) as excinfo:
        ClaudeCodeExtractor().extract(fixture_source("invented", "invented-bad-queued-command"))

    message = str(excinfo.value)
    assert "AttachmentRecord" in message and "line 2" in message
    assert "attachment.queued_command.prompt" in message, message
    assert "SUPER-SECRET-PAYLOAD-9f2a" not in message


def test_a_sender_no_mapping_names_crashes_naming_the_value(fixture_source: SourceFactory):
    """A new kind of sender stops the session rather than filing its message under a guess.

    INVENTED fixture — every recorded queued command names `human`, `coordinator` or `peer`, or
    is a task's notice (scanned 2026-09-25), so an unknown sender has no recording.
    """
    with pytest.raises(TranscriptSchemaError) as excinfo:
        ClaudeCodeExtractor().extract(fixture_source("invented", "invented-unknown-sender"))

    # The whole message: where the record is and the value that was not understood, and not
    # a word of what the message said.
    assert str(excinfo.value) == (
        "Unknown interjection sender `telepath` in session invented-unknown-sender, line 2"
    )
