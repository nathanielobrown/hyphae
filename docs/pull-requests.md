# Pull requests

Use this guide to open a PR that a reviewer can understand before reading the diff. Because AI writes much of this project's code, the PR must make the intent, design, and open questions clear to a human. Reviewer attention is the scarcest resource here.

This guide holds the rules for branches, stacks, visuals, CI and landing. Each part of writing a PR description is defined in one file beside the `pr` skill:

| What                                                  | Where                             |
| ----------------------------------------------------- | --------------------------------- |
| The steps to open a PR, and who writes the fact sheet | `.claude/skills/pr/SKILL.md`      |
| The fact sheet's format and how to write it           | `.claude/skills/pr/fact_sheet.md` |
| The description's layout, word budgets and style      | `.claude/skills/pr/composer.md`   |

## Mechanics

Plain `git` owns branches and commits, `gh stack` owns stacks, and `gh` owns PRs. Sessions are non-interactive, so don't use `-i` flags. `.claude/settings.json` defines the allowed `git` and `gh` commands.

- Create one branch per task from `origin/main` in a worktree under `.claude/worktrees/`; `tools/setup-worktree` provisions it. Keep commits small and atomic according to [the commit guide](commits.md).
- Maintain linear history. When `main` advances, rebase onto `origin/main`; never merge `main` into your branch. For a larger reshape before review, prefer `git reset --soft origin/main` and recommit the branch rather than splitting commits surgically.
- Push once when the branch is ready for review, to avoid CI runs during iteration. `mise run check` is the local gate.
- Mark a PR as a draft only when asking for review before the work is ready to land.
- Address review comments with commits in the layer that owns the change. Fixup commits are fine and need no autosquashing, because squash landing absorbs them.

The session that opens a PR follows the `pr` skill's steps, and `branch-merger` (`.claude/agents/branch-merger.md`) lands one when directed.

## Start the title with the change type

Start the title with emoji from the table in [the commit guide](commits.md), then a plain statement of the change. Multiple emoji are allowed when multiple would apply, but focus on what's important to convey. For example, documentation with a feature does not need the documentation emoji.

Because every PR lands by squash, the title becomes the commit subject on `main`, with GitHub appending ` (#N)`. The title itself carries no issue or PR number.

## Stacked PRs

Use GitHub native stacks through the `gh stack` extension (v0.1 or later). Graphite is not used. **Never point a PR at another branch by hand.** Only `gh stack` may create a PR whose base is not `main`.

- **Layer order**: Place an enabling refactor at the bottom, the core change next, and improvements noticed along the way on top. Never fold a refactor or noticed improvement into the core PR.
- **One concern per PR**: If you cannot state the change in one sentence, split it into two PRs. Each layer builds and passes tests independently, and ships its own tests.
- **Plan layers before writing code**: Map planned items to PR layers before coding. Agents stacking without a plan split refactors so no layer passes CI.
- **Size**: Aim for 100–400 lines of code changed per PR, and split above 500 lines. Count application code alone: tests, comments, docs, committed plans, generated files, and recorded fixtures do not count. A mechanical change (such as a rename across many files) may exceed the target if the description explains why.
- **Depth**: Keep stacks to 2–5 layers as soft guidance. More than five layers usually spans multiple stories; start a second stack instead.
- **Descriptions**: Each layer gets its own fact sheet and description, written against the layer below.
- **Review fixes**: After committing a fix in its layer, run `gh stack rebase --upstack` and `gh stack push`. Do not rebase or amend layers with plain git; gh-stack bug #193 duplicates commits into the layer above.
- **Agent commands**: Use non-interactive `gh stack` commands only (`view --json`, `submit --auto`, explicit branch names). Never run bare `modify`.
- **Starting and submitting**: Fast-forward local `main` to `origin/main` before `gh stack init`, which records local `main` as the stack's base. `gh stack submit` opens each PR with a generated title and body, so set each layer's real title and composed body afterwards with `gh pr edit <n> --title "<emoji> <statement>" --body-file <file>`.

## What makes a PR done

A completed PR satisfies three requirements at once:

1. **It works and is verified**: `mise run check` passes, and the description highlights unverified parts rather than reciting passing gates.
2. **Docs updated**: The owning docs are updated alongside the code ([the rule](documentation.md#update-documentation-with-the-code)).
3. **A reviewer can understand it without reading the diff first, and knows where their judgment is needed.**

If you open the PR before then, say what's missing at the top of the description.

The diff shows *what* changed; the description explains *why* and points to the decisions that need human judgment. Machines can verify much of a diff; don't make a reviewer hunt for the parts they can't. The description orients today's reviewer and is not an archive: deep rationale belongs in committed plans, docs, and code comments. Claude records the facts in a fact sheet and Gemini writes the prose, because Gemini's prose is easier to read.

## Visuals and hosting

Visuals clarify changes faster than raw diffs. The fact sheet lists each one, and the composer places it.

- **Required visuals**: A change to a viewer page requires a Chromatic before/after image of each changed page through `save`. New or changed flows, state machines, or data models require a Mermaid diagram. Performance or test-runtime changes require a before/after chart or table.
- **Hosting with `save`**: Host PR assets with the `save` CLI. `save <file>` (the same command as `save put`) uploads a file and prints a Markdown snippet: an inline image for images, a link otherwise. The bucket is public, so never `save` a screenshot or report drawn from a real trace store; the gallery renders only the redacted fixture corpus. Installation and credentials are in the save repo's README (/Users/nob/repos/save, to be published as nathanielobrown/save).

### Interactive explainers

Build an interactive HTML explainer when text and a single diagram cannot clearly convey the change. Deep-tier PRs usually warrant one; Standard PRs warrant one whenever a reviewer would otherwise need to run the code to understand the change. Good candidates:

- Stepping through a state machine or an algorithm's cases on real inputs.
- Sliding across a threshold or timeout to show its effect.
- Filtering a before-and-after table of recorded data.
- Clicking through a pipeline's stages to see each one's inputs and outputs.

Build rules:

- **Self-contained**: One HTML file with inline CSS and JavaScript (`save` warns on relative paths in a single file), or a directory uploaded with `save <dir> --entry index.html`.
- **Recorded or redacted data**: Use the redacted fixture corpus, never a real trace store or live session data, since anyone with the link can open it.
- **Checked in a browser**: It renders without console errors.
- **Kept as a handoff**: Save the source next to the fact sheet so a recompose can update and re-upload it.
- **Linked, not relied on**: Upload it with `save` and add the link to the fact sheet's Visuals with one line on what the reader can do there. The PR description must stand on its own without it.

### Chromatic snapshots of viewer pages

This project uses Playwright with Chromatic, not Storybook. On every PR, `.github/workflows/e2e.yml` archives and uploads each gallery page the browser tier visits ([the UI development guide](ui-development.md)). Chromatic assigns each snapshot a story ID, which keeps `save story` and `save chromatic sync` functional.

- **Story IDs:** IDs take the form `<spec file>-<describe title>-<test title>--snapshot-<n>`, in lowercase with dashes. The test sweep in `tests/e2e/specs/pages.spec.ts` uses the scenario `title` from `tests/e2e/routes.json`. For example, the Session list page is `pages-every-full-page-loads-with-nothing-in-the-console-session-list--snapshot-1`. Pass the full ID because there is no local Storybook index.
- **Before push:** Run `save story <story-id>`. It requires no login and outputs the image URL. The URL returns 404 until sync runs. GitHub's image proxy does not cache this 404, so the image resolves automatically once synced.
- **After push:** Run `save chromatic sync --wait`. This waits for the `e2e` workflow's Chromatic build to finish and populates every page's URL. If the build has a baseline, it saves `.before.png` and `.diff.png` beside each snapshot.
- **Setup:** The repository root `.save.toml` contains `chromatic_app_id`. Sync reads `CHROMATIC_PROJECT_TOKEN` from `.env`, which `tools/setup-worktree` copies into new worktrees. Run `save chromatic login` once per machine to authenticate via the browser; tokens refresh automatically.

## Make heavy use of diagrams

GitHub renders Mermaid code fences in PR descriptions. Use a diagram wherever it saves the reviewer from reconstructing flow, ordering, state, or structure from the diff. Skip it for a mechanical edit, one-line fix, pure rename, or config change. If an existing diagram answers the question, link it instead.

Draw flows, orderings and state transitions, not the diff or the file tree. Limit each diagram to one question; split diagrams that exceed 20 nodes or mix flow with static structure.

| Question                          | Diagram                       |
| --------------------------------- | ----------------------------- |
| What is the flow or pipeline?     | `flowchart`                   |
| In what order do components talk? | `sequenceDiagram`             |
| What is the lifecycle?            | `stateDiagram-v2`             |
| What is the data model?           | `classDiagram` or `erDiagram` |
| What did the refactor change?     | a before-and-after pair       |

Read [the Mermaid guide](mermaid-guide.md) before drawing. Put a lasting architecture diagram in the doc that owns the topic and link that doc from the PR. A diagram kept only in a PR body won't stay maintained.

## CI and checks

Two workflows answer every PR. `.github/workflows/check.yml` runs `mise run check` on Linux, which surfaces differences your machine hides: path casing, locale defaults, or pinned tool overrides. `.github/workflows/e2e.yml` runs the browser tier and uploads its pages to Chromatic. Local success is a prerequisite, not a guarantee.

Poll checks with `gh pr checks --watch`:

```bash
gh pr checks --watch
```

Do not wait for visual approvals. Chromatic's `UI Tests` check (and `UI Review`, if enabled) requires manual sign-off on page changes. When a page changed, these checks remain pending until approved, which causes `gh pr checks --watch` to hang.

In that case, watch the two workflow runs instead. They always run to completion. Retrieve their IDs:

```bash
gh run list --branch <branch> --json databaseId,workflowName
```

Then watch each run:

```bash
gh run watch <id> --exit-status
```

A PR with passing CI workflow runs is ready to review or merge, even if Chromatic checks remain pending.

## Landing

Land only when directed.

Every PR lands by squash. Use `gh stack merge <pr-number> --squash --yes` or the merge button for a stack, and the merge button or `gh pr merge <pr-number> --squash` for a single branch. Without `--yes`, `gh stack merge` opens an interactive wizard. In a native stack, merging a mid-stack PR also merges every PR below it in one operation, after which GitHub retargets the next layer to `main`.

Nothing on GitHub enforces green CI, by choice: this repository deliberately has no rulesets requiring checks, so a human may merge on red when necessary. An agent always waits for green CI, as described in [CI and checks](#ci-and-checks), on the target PR and every layer below it. It merges only when both workflows (`check`, `e2e`) pass, and never on a failing check.

### Repository settings

The repository carries these GitHub settings:

| Setting                       | Value      | Rationale                                                                             |
| ----------------------------- | ---------- | ------------------------------------------------------------------------------------- |
| `delete_branch_on_merge`      | `true`     | Prevents subsequent PRs from landing into dead base branches.                         |
| `allow_merge_commit`          | `false`    | Disables non-linear merge commits on `main`.                                          |
| `allow_rebase_merge`          | `false`    | Enforces squash merges so each layer is an atomic commit.                             |
| `squash_merge_commit_title`   | `PR_TITLE` | Sets the squash commit subject on `main` to the PR title plus GitHub's `(#N)` suffix. |
| `squash_merge_commit_message` | `BLANK`    | Leaves the commit message blank; rationale lives in the PR description.               |

### Preventing stranded PRs

When a PR targets a non-`main` branch and that parent branch merges, leaving the parent branch undeleted can strand child PRs: they land into the dead branch and never reach `main`.

To prevent stranding:

1. Keep `delete_branch_on_merge: true` so GitHub retargets open child PRs to `main` when their parent branch is deleted.
2. Never retarget or point PR bases to another branch manually; use `gh stack`.
3. When in doubt, list merged PRs whose base was not `main` and verify that their changes exist on `main`.
