-- Every corpus session carrying one `KEY=VALUE` tag, with the counts a reader ranks on.
-- The library's example of `tagged`: a tag says which batch of runs a session belongs to or
-- which experiment it answers, and the pair is the caller's own — hyphae reserves no key and
-- reads no meaning out of one (`docs/store.md`).
-- The tag set is filtered through `project_sessions` and valued through `corpus_rollups`
-- rather than counted off `session_tags` alone: an extract stamps every session it wrote,
-- resumed ones included, so a batch valued without the corpus views would bill a resumed
-- session for work its ancestor already holds.
SELECT
    p.session_id,
    r.started_at,
    p.in_window,
    r.turns,
    r.api_calls,
    r.tool_calls,
    r.agent_runs,
    r.compactions,
    round(r.cost_usd, 4) AS cost_usd,
    r.unpriced_api_calls
FROM tagged($key, $value) t
JOIN project_sessions p ON p.session_id = t.session_id
JOIN corpus_rollups r ON r.session_id = p.session_id
ORDER BY r.started_at, p.session_id;
