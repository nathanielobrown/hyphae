"""Planted shapes the recorded corpus holds too few of, as statements a `planter` runs.

A plain module rather than the conftest: the store's reads, a page's markup and the node page's
byte budget each plant the same shape, and those leaves live in three directories.
"""

from tests.conftest import SENDERS
from tests.view.conftest import Statement

# The task's notice the agent run in `interjection/af7e1907` heard first
# (`tests/view/scenarios.py:INTERJECTED_TURN`): every planted message copies it, record and all.
HEARD_TEMPLATE = "82fd7a6b-8d3a-48a0-8f8e-03155431f1b7"
# Past every line a fixture transcript holds, so a planted message is read after the recorded
# ones of its turn.
PLANTED_LINES = 100_000


def heard(count: int, text: str) -> tuple[Statement, ...]:
    """Every live turn hears `count` more messages, each `text`, after the ones it recorded.

    Invented: no recorded turn heard more than the section shows (the canonical store's busiest
    heard 41, all from tasks). Each message is the template cloned into the turn under an id of
    its own, `planted-<turn>-<n>`, zero-padded so id order is planted order, with a record at a
    line of its own — the section reads the line, and the records page shows it.
    """
    return (
        (
            "INSERT INTO interjections"
            " SELECT 'planted-' || t.id || '-' || lpad(n::VARCHAR, 4, '0'), t.session_id,"
            " t.source, t.id, i.timestamp, i.sender, ?, false"
            " FROM interjections i, live_turns t, range(1, ? + 1) r(n)"
            " WHERE i.session_id = ? AND i.id = ?",
            [text, count, SENDERS, HEARD_TEMPLATE],
        ),
        (
            "INSERT INTO raw_records"
            " SELECT p.session_id, p.source,"
            " ? + row_number() OVER (PARTITION BY p.session_id, p.source ORDER BY p.id),"
            " p.id, r.timestamp, r.type, r.raw"
            " FROM interjections p, raw_records r"
            " WHERE p.id LIKE 'planted-%' AND r.session_id = ? AND r.uuid = ?",
            [PLANTED_LINES, SENDERS, HEARD_TEMPLATE],
        ),
    )


# The agent run's second notice, at line 6 of its transcript: last of the three it heard.
REWOUND = "057236c4-540e-4422-ada0-8df8be93943a"


def rewound(uuid: str) -> Statement:
    """`uuid`'s record is also written at line 0, before every line its thread recorded.

    Invented: no fixture holds a rewound message, and a rewind rewrites a record under the
    uuid it already used (`extract/transcript.py:resolve_duplicates`), so the uuid sits on two
    lines and the extractor read the last.
    """
    return (
        "INSERT INTO raw_records SELECT session_id, source, 0, uuid, timestamp, type, raw"
        " FROM raw_records WHERE session_id = ? AND uuid = ?",
        [SENDERS, uuid],
    )
