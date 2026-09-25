"""What a turn or a run heard while it ran, as the enrichment prompt reads it.

Rows come from `interjection/`'s factory session, recorded with a message from every sender:
the person, another agent, and a background task, and from its relayed session, whose run
heard every sender as `user` records. Split from `test_prompts.py` by topic, for
the file budget.
"""

from pathlib import Path

from hyphae.enrich.levels import LEVELS, render
from hyphae.models.enrichment import Level
from hyphae.models.trace import Sender
from tests.conftest import RELAYED_RUN, SENDERS, SENDERS_RUN, enriching
from tests.enrich.conftest import AUDITOR_RUN, ORIGIN_RUN
from tests.enrich.items import run, turn
from tests.redaction import padded
from tests.view.plants import REWOUND, rewound

# The main turn a task's notice reached, and the one the person and a peer both spoke into.
NOTICED = "11b672e8"
SPOKEN_INTO = "bc846857"
# The widths a pass really cuts at: every leaf here reads a recorded length against them.
TURN_BUDGETS = LEVELS[Level.turn].budgets


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


def test_a_run_renders_what_its_instruction_heard_before_the_work(mutable_db: Path) -> None:
    """An agent run hears its coordinator and its own background tasks the way a main turn
    hears the person, under the instruction they arrived during."""
    # If the implementer run heard a task's notice, then its coordinator, then a second
    # notice, all while its one instruction ran — the second rewound, so its record is also
    # written before the first (synthetic, `tests/view/plants.py:rewound`)...
    with enriching(mutable_db) as store:
        store.connection.execute(*rewound(REWOUND))
        rendered = render(run(store, SENDERS_RUN))
    # ...then each follows the task, in the order of the lines the extractor read, each notice
    # whole because it came in under the width.
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


def test_a_run_renders_a_message_written_as_a_user_record_as_it_renders_a_queued_one(
    fixture_db: Path,
) -> None:
    """A message a run heard as a `user` record reads under the same heading a queued one
    would, without the lead line that named its sender."""
    # If a run heard a task, its coordinator, the person and a second task, each as a `user`
    # record rather than a queued command...
    with enriching(fixture_db) as store:
        rendered = render(run(store, RELAYED_RUN))
    # ...then each notice opens on its tag, as a queued notice does, and every other message
    # keeps the advice Claude Code wrote beneath it.
    assert rendered == (
        "# Agent run: implementer\n"
        "\n"
        "## Task\n"
        "[redacted]\n"
        "\n"
        "## Mid-turn notice from a background task\n"
        "<task-notification>\n"
        "<task-id>b7wvq7981</task-id>\n"
        "<tool-use-id>toolu_01NgyUbKksrk5HLMwKUihbAR</tool-use-id>\n"
        f"<output-file>{padded(110)}</output-file>\n"
        "<status>completed</status>\n"
        f"<summary>{padded(83)}</summary>\n"
        "</task-notification>\n"
        "\n"
        "## Mid-turn message from another agent\n"
        "[redacted]\n"
        "\n"
        "Address this before completing your current task.\n"
        "\n"
        "## Mid-turn message from the person\n"
        "[redacted]\n"
        "\n"
        "This is how Claude Code surfaces messages the user sends mid-turn — within the running"
        " turn, often alongside the next tool result, rather than as a separate conversation"
        " turn. Address the message above as you continue this turn.\n"
        "\n"
        # The second task's event and finish came in one message, and each notice is capped on
        # its own, so both arrive whole and the finish keeps its status.
        "## Mid-turn notice from a background task\n"
        "<task-notification>\n"
        "<task-id>b0nigvf8u</task-id>\n"
        f"<summary>{padded(46)}</summary>\n"
        f"<event>{padded(82)}</event>\n"
        "If this event is something the user would act on now, send a PushNotification."
        " Routine or benign output doesn't need one.\n"
        "</task-notification>\n"
        "\n"
        "<task-notification>\n"
        "<task-id>b0nigvf8u</task-id>\n"
        "<tool-use-id>toolu_01KrTz8b6UDEFA6wBfCmrs16</tool-use-id>\n"
        f"<output-file>{padded(110)}</output-file>\n"
        "<status>completed</status>\n"
        f"<summary>{padded(52)}</summary>\n"
        "</task-notification>\n"
        "\n"
        "## Response\n"
        '- Agent (input 84 chars, result 10 chars) {"subagent_type": "[redacted]", '
        '"description": "[redacted]", "prompt": "[redacted]"}\n'
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


def test_each_notice_a_message_batches_keeps_how_its_task_ended(mutable_db: Path) -> None:
    """A message batching several notices is cut notice by notice, so every task keeps its
    status however many arrived together."""
    # If the recorded 839-character notice arrived three times in one message — synthetic: the
    # recorded batches are redacted short enough to arrive whole...
    with enriching(mutable_db) as store:
        store.connection.execute(
            "UPDATE interjections SET text = text || '\n\n' || text || '\n\n' || text"
            " WHERE session_id = ? AND sender = ?",
            [SENDERS, Sender.TASK.value],
        )
        rendered = render(turn(store, SENDERS, NOTICED))
    section = rendered.split("## Mid-turn notice from a background task\n")[1]
    notices = section.split("\n\n## ")[0].split("\n\n")
    # ...then each of the three is cut to 400 as a lone notice is, its status inside and its
    # result outside.
    assert [len(notice) for notice in notices] == [TURN_BUDGETS.task_notice] * 3
    for notice in notices:
        assert notice.startswith("<task-notification>")
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


def test_a_replayed_message_renders_only_under_the_run_that_heard_it(mutable_db: Path) -> None:
    """A fork that copied the auditor's turn copied the notice it heard, and the copy is not
    the fork's to describe, any more than the turn is (`test_prompts.py`)."""
    # If `fork_origin/`'s auditor heard a task's notice, and its fork replayed that turn...
    with enriching(mutable_db) as store:
        auditor = render(run(store, AUDITOR_RUN))
        fork = render(run(store, ORIGIN_RUN))
        # ...and — synthetic: a recorded copy only sits under a copied turn — the person's
        # message into a live turn is marked a copy...
        store.connection.execute(
            "UPDATE interjections SET replayed = true"
            " WHERE session_id = ? AND starts_with(turn_id, ?) AND sender = ?",
            [SENDERS, SPOKEN_INTO, Sender.PERSON.value],
        )
        spoken_into = render(turn(store, SENDERS, SPOKEN_INTO))
    # ...then the auditor renders it under its task, and the fork renders no message at all...
    assert auditor.startswith(
        "# Agent run: auditor\n\n## Task\n[redacted]\n\n## Mid-turn notice from a background task\n"
    )
    assert "Mid-turn" not in fork
    # ...and the live turn keeps the peer's message and drops the copied one: the filter is
    # on the message, not only on the turn it belongs to.
    assert "## Mid-turn message from the person" not in spoken_into
    assert "## Mid-turn message from another agent\n[redacted]" in spoken_into
