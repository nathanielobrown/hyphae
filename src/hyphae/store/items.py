"""The items a pass renders: every enrichable turn, agent run and session, read out of the trace
tables with what its prompt shows, and the item each one's description is embedded in.

`EnrichmentRepository` hands these out (`store/enrichment.py`), so a pass asks the handle's
`enrichment` property and never names this module; they are the only reads of it that touch
the telemetry rather than the enrichment tables.
"""

from dataclasses import dataclass
from typing import Any

import duckdb

from hyphae.models.enrichment import Level
from hyphae.models.items import (
    AgentRunItem,
    ApiCallRow,
    HeardRow,
    Item,
    RunSection,
    SessionChild,
    SessionItem,
    ToolCallRow,
    TurnItem,
    item_key,
)
from hyphae.models.trace import MAIN_SOURCE, Sender
from hyphae.projects import project_predicate


def _source_clause(alias: str, *, main: bool) -> str:
    """The main transcript's rows, or every agent run's — the two families a `source` has."""
    return f"{alias}.source {'=' if main else '<>'} '{MAIN_SOURCE}'"


# The tag Claude Code wraps a slash command's own output in, and the pattern that reads a
# body out of it. `(?s)` is load-bearing: without it a multi-line body matches nothing and
# extracts as the empty string, which is a state of its own.
_STDOUT_TAG = "local-command-stdout"
_STDOUT_BODY = f"(?s)<{_STDOUT_TAG}>(.*)</{_STDOUT_TAG}>"


# Where a project-scoped query narrows to one repository. `ItemReader._select`
# writes the clause here and binds what it needs; nothing else may write either half.
_PROJECT_SCOPE = "{project}"


@dataclass(frozen=True)
class RunLink:
    """One agent run against whatever spawned it, as the records name it."""

    session_id: str
    run_id: str
    # The run whose transcript holds the spawning call, named either way the records name it.
    parent_run: str | None
    # The main turn holding the spawning call, when no run does. None alongside `parent_run`
    # means nothing in the session embeds this run, and the session carries it directly.
    parent_turn: str | None


class ItemReader:
    """Reads enrichable items off one open connection, a level at a time or all their links.

    A plain class rather than a dataclass: mutmut skips every decorated class.
    """

    def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
        self.connection = connection

    def _select(self, sql: str, project: str | None, *extra: object) -> list[tuple[Any, ...]]:
        """Run one project-scoped read: every row, with `_PROJECT_SCOPE` narrowed and bound.

        The clause and the parameters it binds cannot be written apart here, which is the
        point: a query carrying the clause with nothing bound raises, but one carrying the
        parameters with no clause answers about the whole corpus under a project's name — and
        nothing downstream can tell that answer from the right one.

        `extra` binds after the scope's parameters, so the mark stands before any other `?`.
        """
        if _PROJECT_SCOPE not in sql:
            raise ValueError(f"a project-scoped query must mark its scope with {_PROJECT_SCOPE}")
        clause = f" AND {project_predicate('s.project_dir')}" if project is not None else ""
        # The predicate holds two placeholders, and binds the same path in both.
        scope = [project, project] if project is not None else []
        return self.connection.execute(
            sql.replace(_PROJECT_SCOPE, clause), [*scope, *extra]
        ).fetchall()

    def turn_items(self, project: str | None = None) -> list[TurnItem]:
        """Every enrichable main turn, each carrying the api and tool calls it drove.

        `project` filters by the analyzed repository's resolved path, taking its worktrees
        with it (`sessions.project_predicate`); None takes every session in the store.
        """
        turns = self._select(
            f"""SELECT t.session_id, t.source, t.id, t."index", t.prompt,
                       t.command_name, t.command_args
                FROM live_turns t JOIN sessions s ON s.id = t.session_id
                WHERE {_source_clause("t", main=True)}{_PROJECT_SCOPE}
                ORDER BY t.session_id, t."index" """,
            project,
        )
        calls = self._api_calls(main=True, project=project)
        results = self._command_results(project=project)
        heard = self._heard(main=True, project=project)
        by_turn: dict[tuple[str, str, str], list[ApiCallRow]] = {}
        for (session_id, source), sequence in calls.items():
            for turn_id, row in sequence:
                if turn_id is not None:
                    by_turn.setdefault((session_id, source, turn_id), []).append(row)
        return [
            TurnItem(
                session_id=session_id,
                source=source,
                turn_id=turn_id,
                index=index,
                prompt=prompt,
                command_name=command_name,
                command_args=command_args,
                command_result=results.get((session_id, source, turn_id)),
                heard=tuple(heard.get((session_id, source, turn_id), ())),
                api_calls=tuple(by_turn.get((session_id, source, turn_id), ())),
            )
            for session_id, source, turn_id, index, prompt, command_name, command_args in turns
        ]

    def _command_results(self, *, project: str | None) -> dict[tuple[str, str, str], str]:
        """What the CLI printed for each command turn, keyed by session, source and turn.

        A turn absent from the mapping had no such record archived, which is a different
        state from one whose record printed nothing — `render_turn` says which. A record
        this build cannot classify raises rather than reading as either.
        """
        results: dict[tuple[str, str, str], str] = {}
        for session_id, source, turn_id, line_no, body, readable in self._select(
            f"""WITH carriers AS (
                    SELECT r.session_id, r.source, t.id AS turn_id, r.line_no,
                           -- The two recorded carriers: a `user` record holds the output in
                           -- its message, a `system`/`local_command` one at the top level.
                           -- Both are plain strings in every recorded case. A list-shaped
                           -- `message.content` would extract as the serialised array, so a
                           -- tag quoted inside it would match and pass the guard below.
                           coalesce(json_extract_string(r.raw, '$.message.content'),
                                    json_extract_string(r.raw, '$.content')) AS carrier
                    FROM raw_records r
                    JOIN live_turns t
                      ON t.session_id = r.session_id AND t.source = r.source
                     AND t.id = json_extract_string(r.raw, '$.parentUuid')
                    JOIN sessions s ON s.id = r.session_id
                    WHERE r.raw LIKE '%<{_STDOUT_TAG}>%'
                      AND t.command_name IS NOT NULL
                      AND {_source_clause("t", main=True)}{_PROJECT_SCOPE}
                )
                SELECT session_id, source, turn_id, line_no,
                       regexp_extract(carrier, ?, 1) AS body,
                       -- Tells "no match" from "matched nothing": without it an unreadable
                       -- record extracts as '', which is the printed-nothing state.
                       coalesce(regexp_matches(carrier, ?), false) AS readable
                FROM carriers
                ORDER BY session_id, source, turn_id, line_no""",
            project,
            _STDOUT_BODY,
            _STDOUT_BODY,
        ):
            if not readable:
                raise ValueError(
                    f"session {session_id} source {source} line {line_no} archives a command "
                    f"result in a shape this build cannot read: no <{_STDOUT_TAG}> in either "
                    "carrier field. Claude Code changed the record shape — record it and "
                    "teach the reader before enriching again."
                )
            key = (session_id, source, turn_id)
            # Ordered by line, so a turn answered over several records reads in sequence.
            results[key] = f"{results[key]}\n{body}" if key in results else body
        return results

    def run_items(self, project: str | None = None) -> list[AgentRunItem]:
        """Every agent run, each as the sequence of instructions and work its transcript holds.

        A run's api calls that belong to no turn of its own come first, as one continuation
        section: they are a fork's work on a conversation another transcript opened, and the
        turn its records replay is that other transcript's, not this run's.
        """
        runs = self._select(
            f"""SELECT r.session_id, r.id, r.agent_type
                FROM live_agent_runs r JOIN sessions s ON s.id = r.session_id
                WHERE true{_PROJECT_SCOPE} ORDER BY r.session_id, r.id""",
            project,
        )
        turns: dict[tuple[str, str], list[tuple[str, str]]] = {}
        for session_id, source, turn_id, prompt in self._select(
            f"""SELECT t.session_id, t.source, t.id, t.prompt
                FROM live_turns t JOIN sessions s ON s.id = t.session_id
                WHERE {_source_clause("t", main=False)}{_PROJECT_SCOPE}
                ORDER BY t.session_id, t.source, t."index" """,
            project,
        ):
            turns.setdefault((session_id, source), []).append((turn_id, prompt))
        calls = self._api_calls(main=False, project=project)
        heard = self._heard(main=False, project=project)
        items: list[AgentRunItem] = []
        for session_id, run_id, agent_type in runs:
            local = turns.get((session_id, run_id), [])
            local_ids = {turn_id for turn_id, _ in local}
            sequence = calls.get((session_id, run_id), [])
            continuation = [row for turn_id, row in sequence if turn_id not in local_ids]
            by_turn: dict[str, list[ApiCallRow]] = {}
            for turn_id, row in sequence:
                if turn_id is not None and turn_id in local_ids:
                    by_turn.setdefault(turn_id, []).append(row)
            sections = (
                [RunSection(prompt=None, heard=(), api_calls=tuple(continuation))]
                if continuation
                else []
            )
            sections += [
                RunSection(
                    prompt=prompt,
                    heard=tuple(heard.get((session_id, run_id, turn_id), ())),
                    api_calls=tuple(by_turn.get(turn_id, ())),
                )
                for turn_id, prompt in local
            ]
            if not sections:
                # No turn and no api call: nothing to describe, and no recorded run is in
                # this state (2,459 scanned). Crash rather than buy a description of nothing.
                raise ValueError(f"agent run {session_id}/{run_id} holds no turn and no api call")
            items.append(
                AgentRunItem(
                    session_id=session_id,
                    agent_run_id=run_id,
                    agent_type=agent_type,
                    sections=tuple(sections),
                )
            )
        return items

    def _heard(
        self, *, main: bool, project: str | None
    ) -> dict[tuple[str, str, str], list[HeardRow]]:
        """What each turn of the selected sources heard while it ran, keyed by session, source
        and turn, in the order its transcript holds them — the line the extractor read each
        from, since a queued message's timestamp can fall inside the turn before."""
        heard: dict[tuple[str, str, str], list[HeardRow]] = {}
        for session_id, source, turn_id, sender, text in self._select(
            f"""SELECT i.session_id, i.source, i.turn_id, i.sender, i.text
                FROM live_interjections i
                JOIN raw_records r
                  ON r.session_id = i.session_id AND r.source = i.source AND r.uuid = i.id
                JOIN sessions s ON s.id = i.session_id
                WHERE i.turn_id IS NOT NULL AND {_source_clause("i", main=main)}{_PROJECT_SCOPE}
                -- A rewound uuid has several lines; the extractor read the last.
                GROUP BY i.session_id, i.source, i.turn_id, i.sender, i.text, i.id
                ORDER BY i.session_id, i.source, max(r.line_no), i.id""",
            project,
        ):
            row = HeardRow(sender=Sender(sender), text=text)
            heard.setdefault((session_id, source, turn_id), []).append(row)
        return heard

    def _api_calls(
        self, *, main: bool, project: str | None
    ) -> dict[tuple[str, str], list[tuple[str | None, ApiCallRow]]]:
        """Every api call of the selected sources, in order, with its tool calls attached.

        Keyed by session and source, each call paired with the turn it belongs to — which is
        None for a call no turn opened. Read in two queries and joined here rather than in
        SQL: a row per tool call would repeat every call's text once per tool.
        """
        spawned = self._spawned_descriptions()
        tools: dict[tuple[str, str, str], list[ToolCallRow]] = {}
        for (
            session_id,
            source,
            api_call_id,
            tool_call_id,
            name,
            tool_input,
            result,
            is_error,
            incomplete,
        ) in self._select(
            f"""SELECT c.session_id, c.source, c.api_call_id, c.id, c.name, c.input, c.result,
                       c.is_error, c.incomplete
                FROM live_tool_calls c
                JOIN live_api_calls a
                  ON a.session_id = c.session_id AND a.source = c.source
                 AND a.id = c.api_call_id
                JOIN sessions s ON s.id = c.session_id
                WHERE {_source_clause("c", main=main)}{_PROJECT_SCOPE}
                ORDER BY c.session_id, c.source, c."index" """,
            project,
        ):
            tools.setdefault((session_id, source, api_call_id), []).append(
                ToolCallRow(
                    name=name,
                    input=tool_input,
                    result=result,
                    is_error=is_error,
                    incomplete=incomplete,
                    spawned=spawned.get((session_id, source, tool_call_id)),
                )
            )
        calls: dict[tuple[str, str], list[tuple[str | None, ApiCallRow]]] = {}
        for session_id, source, turn_id, api_call_id, text, stop_reason in self._select(
            f"""SELECT a.session_id, a.source, a.turn_id, a.id, a.text, a.stop_reason
                FROM live_api_calls a JOIN sessions s ON s.id = a.session_id
                WHERE {_source_clause("a", main=main)}{_PROJECT_SCOPE}
                ORDER BY a.session_id, a.source, a."index" """,
            project,
        ):
            calls.setdefault((session_id, source), []).append(
                (
                    turn_id,
                    ApiCallRow(
                        text=text,
                        stop_reason=stop_reason,
                        tool_calls=tuple(tools.get((session_id, source, api_call_id), ())),
                    ),
                )
            )
        return calls

    def _spawned_descriptions(self) -> dict[tuple[str, str, str], str]:
        """What each spawning tool call's run was described as, for the calls that have one.

        Keyed by the *call*, so a tool line can carry its child's description. A call
        recorded inside the very run it spawned is left out: forking replays the spawning
        call into the fork's own transcript, and a run embedding itself is a cycle.
        """
        return {
            (session_id, source, tool_call_id): description
            for session_id, source, tool_call_id, description in self.connection.execute(
                """SELECT c.session_id, c.source, c.id, e.description
                   FROM live_tool_calls c
                   JOIN live_agent_runs r
                     ON r.session_id = c.session_id AND r.tool_use_id = c.id
                   JOIN agent_run_enrichments e
                     ON e.session_id = r.session_id AND e.agent_run_id = r.id
                   WHERE c.source <> r.id"""
            ).fetchall()
        }

    def session_items(self, project: str | None = None) -> list[SessionItem]:
        """Every session worth describing, with what it cost and what its children did.

        `describable_sessions` decides which those are: 102 of 575 recorded sessions hold no
        main turn and no agent run, and 45 more drove no api call under the turns they hold.
        """
        children = self._session_children(project)
        return [
            SessionItem(
                session_id=session_id,
                title=title,
                git_branch=git_branch,
                wall_ms=wall_ms,
                active_ms=active_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read_tokens,
                cache_creation_tokens=cache_creation_tokens,
                cost_usd=cost_usd,
                children=tuple(children.get(session_id, ())),
            )
            for (
                session_id,
                title,
                git_branch,
                wall_ms,
                active_ms,
                input_tokens,
                output_tokens,
                cache_read_tokens,
                cache_creation_tokens,
                cost_usd,
            ) in self._select(
                f"""SELECT r.session_id, s.title, s.git_branch, r.wall_ms, r.active_ms,
                           r.input_tokens, r.output_tokens, r.cache_read_tokens,
                           r.cache_creation_tokens, r.cost_usd
                    FROM describable_sessions r JOIN sessions s ON s.id = r.session_id
                    WHERE true{_PROJECT_SCOPE}
                    ORDER BY r.session_id""",
                project,
            )
        ]

    def _session_children(self, project: str | None) -> dict[str, list[SessionChild]]:
        """What each session did directly, in the order it started doing it.

        Its main turns, plus the runs nothing in the session embeds — everything else reaches
        the session through the turn or the run whose prompt carries its description.
        """
        direct = {
            (link.session_id, link.run_id)
            for link in self._run_links(project)
            if link.parent_run is None and link.parent_turn is None
        }
        rows = [
            (session_id, started_at, SessionChild(Level.turn, None, *enrichment))
            for session_id, started_at, *enrichment in self._select(
                f"""SELECT t.session_id, t.started_at, e.description, e.category, e.outcome
                    FROM live_turns t JOIN sessions s ON s.id = t.session_id
                    LEFT JOIN turn_enrichments e
                      ON e.session_id = t.session_id AND e.source = t.source AND e.turn_id = t.id
                    WHERE {_source_clause("t", main=True)}{_PROJECT_SCOPE}""",
                project,
            )
        ]
        rows += [
            (session_id, started_at, SessionChild(Level.agent_run, agent_type, *enrichment))
            for session_id, run_id, agent_type, started_at, *enrichment in self._select(
                f"""SELECT r.session_id, r.id, r.agent_type, r.started_at,
                           e.description, e.category, e.outcome
                    FROM live_agent_runs r JOIN sessions s ON s.id = r.session_id
                    LEFT JOIN agent_run_enrichments e
                      ON e.session_id = r.session_id AND e.agent_run_id = r.id
                    WHERE true{_PROJECT_SCOPE}""",
                project,
            )
            if (session_id, run_id) in direct
        ]
        children: dict[str, list[SessionChild]] = {}
        for session_id, _, child in sorted(rows, key=lambda row: (row[1] is None, row[1])):
            children.setdefault(session_id, []).append(child)
        return children

    def items(self, level: Level, project: str | None = None) -> list[Item]:
        """Every enrichable item of one level. The enricher's one door into the store.

        `turn_items`, `run_items` and `session_items` are public because the tests read one
        level directly.
        """
        match level:
            case Level.turn:
                return list(self.turn_items(project))
            case Level.agent_run:
                return list(self.run_items(project))
            case Level.session:
                return list(self.session_items(project))

    def _run_links(self, project: str | None) -> list[RunLink]:
        """Each agent run against whatever spawned it, by both rules the records offer.

        `parent_agent_id` where the records name one, and otherwise the transcript holding the
        spawning tool call. Both are needed: 112 of 2,459 recorded runs name no parent agent
        yet were spawned from inside another run, and either rule alone strands them.

        Ordering cannot be right for a tree with a gap in it, so a run naming a parent run the
        store does not hold crashes here rather than being treated as a root.
        """
        rows = self._select(
            f"""SELECT r.session_id, r.id, r.parent_agent_id, c.source, a.turn_id
                FROM live_agent_runs r
                JOIN sessions s ON s.id = r.session_id
                -- The spawning call, excluding the copy of itself a fork's own transcript
                -- holds: a run is not its own parent.
                LEFT JOIN live_tool_calls c
                  ON c.session_id = r.session_id AND c.id = r.tool_use_id AND c.source <> r.id
                LEFT JOIN live_api_calls a
                  ON a.session_id = c.session_id AND a.source = c.source
                 AND a.id = c.api_call_id
                WHERE true{_PROJECT_SCOPE}""",
            project,
        )
        held = {(session_id, run_id) for session_id, run_id, *_ in rows}
        links: list[RunLink] = []
        for session_id, run_id, parent_agent_id, source, turn_id in rows:
            run = parent_agent_id or (source if source not in (None, MAIN_SOURCE) else None)
            if run is not None and (session_id, run) not in held:
                raise ValueError(
                    f"agent run {session_id}/{run_id} names parent run {run}, which the store"
                    f" does not hold — re-extract the session before enriching it"
                )
            links.append(
                RunLink(
                    session_id=session_id,
                    run_id=run_id,
                    parent_run=run,
                    parent_turn=turn_id if run is None else None,
                )
            )
        return links

    def item_parents(self, project: str | None = None) -> dict[str, str | None]:
        """Each item's key against the key of the item whose prompt embeds its description.

        A run's parent is the agent that spawned it, or the main turn that did, or — when
        nothing in the session embeds it — the session itself. A main turn's parent is always
        its session. Sessions are not here: nothing embeds a session, so they are the roots
        every chain ends at.

        A run's `tool_use_id` alone would not do: 9 recorded runs were spawned by a
        main-transcript call belonging to no turn, and reading those as embedded by nothing
        *and* claimed by nothing would drop them out of every render there is.
        """
        parents: dict[str, str | None] = {}
        for link in self._run_links(project):
            if link.parent_run is not None:
                parent = item_key(Level.agent_run, link.session_id, link.parent_run)
            elif link.parent_turn is not None:
                parent = item_key(Level.turn, link.session_id, MAIN_SOURCE, link.parent_turn)
            else:
                parent = item_key(Level.session, link.session_id)
            parents[item_key(Level.agent_run, link.session_id, link.run_id)] = parent
        for session_id, turn_id in self._select(
            f"""SELECT t.session_id, t.id FROM live_turns t JOIN sessions s ON s.id = t.session_id
                WHERE {_source_clause("t", main=True)}{_PROJECT_SCOPE}""",
            project,
        ):
            parents[item_key(Level.turn, session_id, MAIN_SOURCE, turn_id)] = item_key(
                Level.session, session_id
            )
        return parents
