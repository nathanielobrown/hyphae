"""A message delivered while a turn was running: who sent it, which turn it reached, and the
shapes that stop an extract rather than lose one."""

import json
from datetime import UTC, datetime

import pytest

from hyphae.extract.claude_code import ClaudeCodeExtractor
from hyphae.extract.errors import TranscriptSchemaError
from hyphae.models.trace import MAIN_SOURCE, Interjection, Sender
from tests.conftest import FIXTURES, INTERJECTION, SourceFactory


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
