"""A message delivered while a turn was running: who sent it, which turn it reached, and the
shapes that stop an extract rather than lose one."""

import pytest

from hyphae.extract.claude_code import ClaudeCodeExtractor
from hyphae.extract.errors import TranscriptSchemaError
from tests.conftest import SourceFactory


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
