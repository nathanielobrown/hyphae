"""What a turn or a run heard while it ran, as the enrichment prompt reads it.

Rows come from `interjection/`'s factory session, recorded with a message from every sender:
the person, another agent, and a background task. Split from `test_prompts.py` by topic, for
the file budget.
"""

from pathlib import Path

from hyphae.enrich.levels import LEVELS, render
from hyphae.models.enrichment import Level
from hyphae.models.trace import Sender
from tests.conftest import SENDERS, SENDERS_RUN, enriching
from tests.enrich.conftest import AUDITOR_RUN, ORIGIN_RUN
from tests.enrich.items import run, turn

# The main turn a task's notice reached, and the one the person and a peer both spoke into.
NOTICED = "11b672e8"
SPOKEN_INTO = "bc846857"
# The widths a pass really cuts at: every leaf here reads a recorded length against them.
TURN_BUDGETS = LEVELS[Level.turn].budgets


def padded(length: int) -> str:
    """A redacted leaf tag's text: `[redacted] ` repeated to the length it was recorded at."""
    return ("[redacted] " * (length // 11 + 1))[:length]


def test_a_turn_renders_what_it_heard_under_its_prompt_headed_by_who_sent_it(
    fixture_db: Path,
) -> None:
    """Each message a turn heard follows the prompt it amends, under a heading naming its
    sender, before the work the turn then did."""
    # If the person typed into a turn while it ran, and another session wrote into it after...
    with enriching(fixture_db) as store:
        spoken_into = render(turn(store, SENDERS, SPOKEN_INTO))
        noticed = turn(store, SENDERS, NOTICED)
    # ...then both follow the prompt, in the order the transcript holds them...
    assert spoken_into == (
        "# Main turn\n"
        "\n"
        "## Prompt\n"
        "[redacted]\n"
        "\n"
        "## Mid-turn message from the person\n"
        "[redacted]\n"
        "\n"
        "## Mid-turn message from another agent\n"
        "[redacted]\n"
        "\n"
        "## Ended: no model response"
    )
    # ...and a background task's notice follows a slash command's result the same way, cut
    # to its own width: the tags that say which task and how it ended, and not the payload.
    assert render(noticed) == (
        "# Main turn\n"
        "\n"
        "## Command\n"
        f"/manager {noticed.command_args}\n"
        "\n"
        "## Command result: not recorded\n"
        "\n"
        "## Mid-turn notice from a background task\n"
        "<task-notification>\n"
        "<task-id>ae673a7bd2fcb8755</task-id>\n"
        f"<output-file>{padded(116)}</output-file>\n"
        "<status>completed</status>\n"
        f"<summary>{padded(59)}</summary>\n"
        f"<note>{padded(75)}[+451 chars]\n"
        "\n"
        "## Response\n"
        '- Agent (input 101 chars, result 10 chars) {"subagent_type": "[redacted]", "model": '
        '"opus", "description": "[redacted]", "prompt": "[redacted]"}\n'
        "\n"
        "## Ended: tool_use"
    )


def test_a_run_renders_what_its_instruction_heard_before_the_work(fixture_db: Path) -> None:
    """An agent run hears its coordinator and its own background tasks the way a main turn
    hears the person, under the instruction they arrived during."""
    # If the implementer run heard a task's notice, then its coordinator, then a second
    # notice, all while its one instruction ran...
    with enriching(fixture_db) as store:
        rendered = render(run(store, SENDERS_RUN))
    # ...then each follows the task, in transcript order, each notice whole because it came
    # in under the width.
    assert rendered == (
        "# Agent run: implementer\n"
        "\n"
        "## Task\n"
        "[redacted]\n"
        "\n"
        "## Mid-turn notice from a background task\n"
        "<task-notification>\n"
        "<task-id>bxu6dww5e</task-id>\n"
        "<tool-use-id>toolu_0147R6wMU7RVP3eZXV2mbQc9</tool-use-id>\n"
        f"<output-file>{padded(108)}</output-file>\n"
        "<status>completed</status>\n"
        f"<summary>{padded(86)}</summary>\n"
        "</task-notification>\n"
        "\n"
        "## Mid-turn message from another agent\n"
        "[redacted]\n"
        "\n"
        "## Mid-turn notice from a background task\n"
        "<task-notification>\n"
        "<task-id>b0bcg9mv7</task-id>\n"
        "<tool-use-id>toolu_01FYu7UYEgcUoxHey3cNZS3K</tool-use-id>\n"
        f"<output-file>{padded(108)}</output-file>\n"
        "<status>completed</status>\n"
        f"<summary>{padded(71)}</summary>\n"
        "</task-notification>\n"
        "\n"
        "## Response\n"
        '- Bash (input 54 chars, result 10 chars, ERROR) {"command": "[redacted]", '
        '"description": "[redacted]"} | error tail: [redacted]\n'
        "\n"
        "## Response\n"
        "[redacted]\n"
        "\n"
        "## Ended: not recorded"
    )


def test_a_task_notice_keeps_how_the_task_ended_and_drops_what_it_returned(
    fixture_db: Path,
) -> None:
    """A task's notice is cut to 400 characters, which keeps its status and loses its result.

    A background task that failed or was killed leaves no other trace: the call that launched
    it answered at once, with no error.
    """
    # If a task's notice was recorded at 839 characters, its status closing at 227 and its
    # result opening at 517...
    with enriching(fixture_db) as store:
        rendered = render(turn(store, SENDERS, NOTICED))
    notice = rendered.split("## Mid-turn notice from a background task\n")[1].split("\n\n")[0]
    # ...then the render keeps 400 of them, the status inside and the result outside.
    assert len(notice) == TURN_BUDGETS.task_notice == 400
    assert "<status>completed</status>" in notice
    assert "<result>" not in notice


def test_a_message_is_capped_at_the_width_a_prompt_gets(mutable_db: Path) -> None:
    """What the person or another agent typed is capped where a prompt is, not where a task's
    notice is: it is an instruction, and may be as long as one."""
    # If the person's message is lengthened to 4,100 characters — synthetic: every recorded
    # one is redacted to ten — and the peer's to 1,000...
    with enriching(mutable_db) as store:
        for sender, length in ((Sender.PERSON, 4_100), (Sender.AGENT, 1_000)):
            store.connection.execute(
                "UPDATE interjections SET text = repeat('x', ?)"
                " WHERE session_id = ? AND sender = ?",
                [length, SENDERS, sender.value],
            )
        rendered = render(turn(store, SENDERS, SPOKEN_INTO))
    # ...then the person's is cut to the prompt's 4,000, and the peer's arrives whole.
    kept = TURN_BUDGETS.prompt - len("[+4100 chars]")
    assert rendered == (
        "# Main turn\n"
        "\n"
        "## Prompt\n"
        "[redacted]\n"
        "\n"
        "## Mid-turn message from the person\n"
        f"{'x' * kept}[+{4_100 - kept} chars]\n"
        "\n"
        "## Mid-turn message from another agent\n"
        f"{'x' * 1_000}\n"
        "\n"
        "## Ended: no model response"
    )


def test_a_replayed_message_renders_only_under_the_run_that_heard_it(fixture_db: Path) -> None:
    """A fork that copied the auditor's turn copied the notice it heard, and the copy is not
    the fork's to describe, any more than the turn is (`test_prompts.py`)."""
    # If `fork_origin/`'s auditor heard a task's notice, and its fork replayed that turn...
    with enriching(fixture_db) as store:
        auditor = render(run(store, AUDITOR_RUN))
        fork = render(run(store, ORIGIN_RUN))
    # ...then the auditor renders it under its task, and the fork renders no message at all.
    assert auditor.startswith(
        "# Agent run: auditor\n\n## Task\n[redacted]\n\n## Mid-turn notice from a background task\n"
    )
    assert "Mid-turn" not in fork
