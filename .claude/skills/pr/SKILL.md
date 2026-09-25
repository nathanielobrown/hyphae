---
name: pr
description: Open a reviewable PR end to end — docs synced into the same PR, fact sheet, composer, gh pr create. Invoke when a task should finish as a PR; the session opening the PR runs it.
---

# PR

Open a reviewable PR with the procedure below. The rules it relies on are in `docs/pull-requests.md` (imported below); take the commands from there rather than habit.

## Procedure

1. **Shape the branch**: Follow [Mechanics](../../../docs/pull-requests.md#mechanics), and [Stacked PRs](../../../docs/pull-requests.md#stacked-prs) for a stack.
2. **Sync documentation**: Dispatch the `doc-writer` subagent (`.claude/agents/doc-writer.md`) to run doc-sync and commit documentation updates into the branch.
3. **Get the fact sheet written** following [fact_sheet.md](fact_sheet.md). Only a session that knows the work firsthand writes it; an agent that knows the work only from a brief loses the rationale and the judgment calls.
   - If an `auditor` reviews the branch, its accepting pass writes the fact sheet. Put the tier, the feedback wanted, the user's decisions, and the implementer's report verbatim in the audit brief.
   - Otherwise write it yourself; you did the work.
4. **Compose the description**: Run the Gemini composer headless through pi with [composer.md](composer.md), naming the fact sheet, the diff base, and the `pr-body-<topic>` handoff to write:

   ```bash
   timeout 1800 pi -p --model openrouter/google/gemini-3.8-flash --append-system-prompt .claude/skills/pr/composer.md "<instruction naming the fact sheet, diff base and output paths>" < /dev/null
   ```

   Keep the `< /dev/null`: without it, `pi -p` waits on input forever.
5. **Review the body** for factual errors only, not style. Check it against the fact sheet and cut anything the fact sheet does not support, including any session data. If the errors are more than trivial, fix the fact sheet and recompose. A body a little over its word budget is fine. If the composer reports one more than a quarter over, tell the user in your report; don't trim it yourself.
6. **Validate diagrams**: If the body contains Mermaid blocks, run `mise run diagram-check <file>`. PR bodies are not in git, so this is their only check before GitHub renders them.
7. **Submit**: Push the branch once (`git push -u origin <topic>`), then open the PR:

   ```bash
   gh pr create --title "<emoji> <statement>" --body-file <file>
   ```

   For a stack, follow [Starting and submitting](../../../docs/pull-requests.md#stacked-prs) instead. For a viewer page change, run `save chromatic sync --wait` after the push so the `save story` images fill in ([Chromatic snapshots](../../../docs/pull-requests.md#chromatic-snapshots-of-viewer-pages)).
8. **Recompose on substantial change**: Recompose when scope changes, a design point changes, a new known issue appears, or a stack layer changes. Update the fact sheet first, then rerun step 4 and update the PR with `gh pr edit --body-file <file>`. Small review fixes do not trigger recomposition.

@../../../docs/pull-requests.md
