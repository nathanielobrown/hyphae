-- The messages delivered while one turn was running: the interjections section of a
-- turn's node page. A turn of a person's is quiet — the canonical store's busiest holds 3 a
-- person or another agent wrote — but a task's notices are not, and one turn has heard 41 of
-- them, so the section is capped like the header's lists rather than paged: the first
-- `$interjections` and a count of the rest.
-- In the order the transcript holds them, which is the order the model read them in and the
-- order the extractor filed them into turns by (`extract/parse.py`). A timestamp is
-- not that order: a queued message carries the moment it was typed, which can fall inside the
-- turn before. The line is the one the extractor read the row from — the last of a rewound
-- uuid's copies (`extract/transcript.py:resolve_duplicates`) — and the id breaks a tie, so
-- a cut means the same rows on every read.
-- `$interjection_chars` is what a row shows of the message; the whole of it is the record, a
-- click away on the thread's records page at `line_no`. Replayed copies are a fork's, and the
-- page reads the live rows.
WITH lines AS (
    SELECT r.uuid, max(r.line_no) AS line_no
    FROM raw_records r
    WHERE r.session_id = $session_id
      AND r.source = $source
    GROUP BY r.uuid
)
SELECT
    i.id,
    i.sender,
    i.timestamp,
    cut(i.text, $interjection_chars) AS text,
    l.line_no,
    -- How many the turn heard in all, counted before the LIMIT bites, so a section that shows
    -- the first `$interjections` can say how many it left rather than reading as the whole.
    count(*) OVER () AS matched_rows
FROM live_interjections i
JOIN lines l ON l.uuid = i.id
WHERE i.session_id = $session_id
  AND i.source = $source
  AND i.turn_id = $turn_id
ORDER BY l.line_no, i.id
LIMIT $interjections;
