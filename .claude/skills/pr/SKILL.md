---
name: pr
description: Open a reviewable PR end to end — docs synced into the same PR, fact sheet, composer, gh pr create. Invoke when a task should finish as a PR; the session opening the PR runs it.
---

# PR

Open a reviewable PR by the procedure below and the full guide in `docs/pull-requests.md` (imported below). Take the commands from the guide rather than habit.

## Procedure

1. **Shape the branch**: Work on one branch per task off `origin/main` in a worktree. Keep history linear by rebasing. Shape changes into atomic commits. Verify that `mise run check` passes locally.
2. **Sync documentation**: Dispatch the `doc-writer` subagent (`.claude/agents/doc-writer.md`) to run doc-sync and commit documentation updates into the branch.
3. **Get the fact sheet written**: The handoff `pr-facts-<topic>` (`docs/handoffs.md` names the file) comes from the final `git diff <base>...HEAD` and test output, never from the plan. `<base>` is `origin/main`, or the parent layer's branch for an upper stack layer. Follow [fact_sheet.md](fact_sheet.md).
   - If an `auditor` reviews the branch, its accepting pass writes the fact sheet. Put the tier, the feedback wanted, the user's decisions, and the implementer's report verbatim in the audit brief.
   - Otherwise write it yourself; you did the work.
4. **Compose the description**: Run the Gemini composer headless through pi with [composer.md](composer.md), naming the fact sheet, the diff base, and the `pr-body-<topic>` handoff to write:

   ```bash
   timeout 900 pi -p --model openrouter/google/gemini-3.8-flash --append-system-prompt .claude/skills/pr/composer.md "<instruction naming the fact sheet, diff base and output paths>" < /dev/null
   ```

   Keep the `< /dev/null`: without it, `pi -p` waits on input forever.
5. **Review the body**: Review `pr-body-<topic>` for factual errors only, not style. Check it against the fact sheet and cut anything the fact sheet does not support. Check that prose fits the tier word budget (Light ~75, Standard ~300, Deep ~500), that empty sections are omitted, and that no session data reached it.
6. **Validate diagrams**: If the body contains Mermaid blocks, run `mise run diagram-check <file>`.
7. **Submit**: Push the branch once (`git push -u origin <topic>`), then open the PR:

   ```bash
   gh pr create --title "<emoji> <statement>" --body-file <file>
   ```

   For a viewer page change, run `save chromatic sync --wait` after the push so the `save story` images fill in.
8. **Recompose on substantial change**: Recompose when scope changes, a design point changes, a new known issue appears, or a stack layer changes. Update the fact sheet first. Update the PR with `gh pr edit --body-file <file>`. Small review fixes do not trigger recomposition.
9. **Stacked PRs**: Manage stacks only through `gh stack` (v0.1 or later). Never point a PR at another branch by hand. Target 100–400 code lines per PR; split above 500 lines. Commit review fixes in the owning layer, then run `gh stack rebase --upstack` and `gh stack push`.

@../../../docs/pull-requests.md
