# Pull requests

Use this guide to open a PR that a reviewer can understand before reading the diff. Because AI writes much of this project's code, the PR must make the intent, design, and open questions clear to a human. Reviewer attention is the scarcest resource here.

## Mechanics

Plain `git` owns branches and commits, `gh stack` owns stacks, and `gh` owns PRs. Sessions are non-interactive, so don't use `-i` flags. `.claude/settings.json` defines the allowed `git` and `gh` commands.

- Create one branch per task from `origin/main` in a worktree under `.claude/worktrees/`; `tools/setup-worktree` provisions it. Keep commits small and atomic according to [the commit guide](commits.md).
- Maintain linear history. When `main` advances, rebase onto `origin/main`; never merge `main` into your branch. For a larger reshape before review, prefer `git reset --soft origin/main` and recommit the branch rather than splitting commits surgically.
- Push once when the branch is ready for review, to avoid CI runs during iteration. `mise run check` is the local gate.
- Before writing the PR description, dispatch the `doc-writer` subagent (`.claude/agents/doc-writer.md`) to run doc-sync over the finished branch, and fold its edits into the branch. The docs belong in the same PR as the code ([the rule](documentation.md#update-documentation-with-the-code)).
- Open the PR with `gh pr create --title "<emoji> <statement>" --body-file <file>`. Mark it as a draft only when asking for review before the work is ready to land.
- Address review comments with commits in the owning layer. For stacks, run `gh stack rebase --upstack` and `gh stack push`. Fixup commits are fine and need no autosquashing, because squash landing absorbs them.
- Landing: see [Landing](#landing) below. Every PR lands by squash.

The `pr-submitter` agent (`.claude/agents/pr-submitter.md`) opens a PR by this flow, and `branch-merger` (`.claude/agents/branch-merger.md`) lands one when directed.

## Start the title with the change type

Start the title with emoji from the table in [the commit guide](commits.md), then a plain statement of the change. Multiple emoji are allowed when multiple would apply, but focus on what's important to convey. For example, documentation with a feature does not need the documentation emoji.

Because every PR lands by squash, the title becomes the commit subject on `main`, with GitHub appending ` (#N)`. The title itself carries no issue or PR number.

## Stacked PRs

Use GitHub native stacks through the `gh stack` extension (v0.1 or later). Graphite is not used. **Never point a PR at another branch by hand.** Only `gh stack` may create a PR whose base is not `main`.

- **Layer order**: Place an enabling refactor at the bottom, the core change next, and improvements noticed along the way on top. Never fold a refactor or noticed improvement into the core PR.
- **One concern per PR**: If you cannot state the change in one sentence, split it into two PRs. Each layer builds and passes tests independently, and ships its own tests.
- **Plan layers before writing code**: Map planned items to PR layers before coding. Agents stacking without a plan split refactors so no layer passes CI.
- **Size**: Aim for 100–400 lines of code changed per PR, and split above 500 lines. Count application code alone: tests, comments, docs, committed plans, generated files, and recorded fixtures do not count. A mechanical change (such as a rename across many files) may exceed the target if the description explains why.
- **Descriptions**: Write one fact sheet and one body per PR. The bottom PR carries the stack's goal in one or two sentences. Upper PRs name the bottom PR instead. Never write "part n of m"; GitHub displays the stack map natively.
- **Review fixes**: Commit fixes in the layer that owns the change, then run `gh stack rebase --upstack` and `gh stack push`. Do not rebase or amend layers with plain git; gh-stack bug #193 duplicates commits into the layer above.
- **Agent commands**: Use non-interactive `gh stack` commands only (`view --json`, `submit --auto`, explicit branch names). Never run bare `modify`.

## What makes a PR done

A completed PR satisfies three requirements at once:

1. **It works and is verified**: `mise run check` passes, and the description highlights unverified parts rather than reciting passing gates.
2. **Docs updated**: The owning docs are updated alongside the code ([the rule](documentation.md#update-documentation-with-the-code)).
3. **A reviewer can understand it without reading the diff first, and knows where their judgment is needed**: see [Writing PR descriptions](#writing-pr-descriptions).

If you open the PR before then, say what's missing at the top of the description.

## Writing PR descriptions

The diff shows *what* changed. The description explains *why* and points to decisions that need human judgment. Machines can verify much of a diff; don't make a reviewer hunt for the parts they can't.

A PR description orients today's reviewer; it is not a permanent archive. Deep rationale belongs in committed plans, docs, and code comments.

### Description authoring process

1. **The authoring agent (generally Claude) writes a fact sheet.** It writes the handoff `pr-facts-<topic>` ([handoffs](handoffs.md)) from the final `git diff origin/main...HEAD` and test output, not from the plan. Plans describe intent; the diff describes what actually happened. Follow `.claude/skills/pr/fact_sheet.md`.
2. **A Gemini agent composes the body from the fact sheet.** Run it headless through pi, naming the fact sheet and the `pr-body-<topic>` handoff to write:

   ```bash
   pi -p --model openrouter/google/gemini-3.8-flash --append-system-prompt .claude/skills/pr/composer.md "<instruction naming the fact sheet and output paths>"
   ```

   The composer's system prompt is `.claude/skills/pr/composer.md`. It may read the repo only to verify claims against the diff or quote code exactly, and must not introduce topics the fact sheet omits. It checks every claim in its draft against the diff before finishing. Gemini writes more readable prose than Claude.
3. **Fact review**: The submitting agent reviews the composed body for factual errors only, not style. It runs `mise run diagram-check <file>` if the body contains Mermaid, then opens the PR with `gh pr create --body-file <file>`.
4. **Recompose on substantial change**: Recompose when PR scope changes, a design point changes, a new known issue appears, or a stack gains or loses a layer. Small review fixes do not trigger recomposition. Update with `gh pr edit --body-file <file>`.

### Fact sheet fields

The composer's input is terse bullets with no polish. Use `.claude/skills/pr/fact_sheet.md` and omit any field with nothing to say:

- **Tier and budget**: Light, Standard, or Deep, matching the blast radius in `AGENTS.md`: small and clear, medium, or foundation-shaping.
- **Stack**: The bottom PR states the stack's goal in one or two sentences. Other PRs name the bottom PR instead.
- **Intent**: What changed and why, in the author's words.
- **Feedback wanted**: What kind of review the PR asks for.
- **Judgment points**: Risks, open decisions, and known issues, each with a file path, ordered by risk.
- **Design**: Points the diff does not make obvious, drawn from the `design-<topic>` handoff when there is one. Plan deviations go here, and only if there are any.
- **Visuals**: Each `save` output with one line describing what it shows.
- **Verification**: Evidence beyond standard green checks (commands with output excerpts), what went unverified (a `testing-plan-<topic>` handoff's uncovered leaves belong here), and any edits to tests, CI, or thresholds.
- **Links**: Plan, issue, and artifacts.
- **Emphasis**: Free-form notes to the composer, such as "the migration is what matters most".

### PR body layout and budgets

```
<what changed and why: 2–3 sentences, no heading>

## Needs your judgment
Opens with the kind of feedback wanted. Then known issues, open decisions and review
questions, each with its file, ordered by risk.

## How it works
One visual (diagram, screenshot, or save link) plus the design points the diff doesn't
make obvious. Plan deviations go here, and only if there are any.

## Verification
Only evidence beyond the standard green checks: manual runs, before/after output, what
went unverified, and any edit to tests, CI or thresholds.

<footer: links to plan, issue, artifacts>
```

- **Light PRs**: The opening paragraph only.
- **Empty sections**: Omit them entirely.
- **Word budgets for prose**: Light about 75 words, Standard about 300, Deep about 500. Code blocks, diagrams, and `<details>` blocks do not count against the budget.
- **Research rationale**: Stating the kind of feedback wanted was the single element most tied to merging (odds ratio 1.72, arXiv 2602.14611). Shorter, structured bodies correlate with faster review times.
- **Plan deviations**: Plan deviations go inside "How it works", only if there are any. Full plan audits belong in review reports, not in the PR body. Do not include file-by-file walkthroughs.

### Keep session data out of the description

A behavior change needs evidence: redacted command output that shows the behavior, or a pointer to a safe fixture. Never paste real session data; transcripts may contain source, credentials, or customer data (`AGENTS.md`).

### Avoid these pitfalls in descriptions

- File-by-file diff walkthroughs that explain syntax instead of intent.
- Treating all edits equally, which drowns critical judgment points in mechanical diff summaries.
- Describing the initial plan rather than what actually landed in the diff.
- Inserting placeholders into empty sections instead of omitting them.
- Redrawing the diff or file tree instead of visualizing flows, orderings, or state transitions.
- Concealing known defects or open choices inside the diff instead of stating them in "Needs your judgment".
- Pasting full test-gate outputs or writing an uninformative "ran tests". Report exceptions and non-green gates.
- Writing relative Markdown links; they 404 on github.com. Use full URLs or backticked paths.

## Visuals and hosting

Visuals clarify changes faster than raw diffs:

- **Required visuals**: A change to a viewer page requires a Chromatic before/after image of each changed page through `save`. New or changed flows, state machines, or data models require a Mermaid diagram. Performance or test-runtime changes require a before/after chart or table.
- **Visuals placement**: Images, simple diagrams, and tables go inline. Interactive HTML goes behind a link.
- **Hosting with `save`**: Host PR assets with the `save` CLI. `save <file>` (the same command as `save put`) uploads a file and prints a Markdown snippet: an inline image for images, a link otherwise. The bucket is public, so never `save` a screenshot or report drawn from a real trace store; the gallery renders only the redacted fixture corpus. Installation and credentials are in the save repo's README (/Users/nob/repos/save, to be published as nathanielobrown/save).

### Chromatic snapshots of viewer pages

This project uses Playwright with Chromatic, not Storybook. On every PR, `.github/workflows/e2e.yml` archives and uploads each gallery page the browser tier visits ([the UI development guide](ui-development.md)). Chromatic assigns each snapshot a story ID, which keeps `save story` and `save chromatic sync` functional.

- **Story IDs:** IDs take the form `<spec file>-<describe title>-<test title>--snapshot-<n>`, in lowercase with dashes. The test sweep in `tests/e2e/specs/pages.spec.ts` uses the scenario `title` from `tests/e2e/routes.json`. For example, the Session list page is `pages-every-full-page-loads-with-nothing-in-the-console-session-list--snapshot-1`. Pass the full ID because there is no local Storybook index.
- **Before push:** Run `save story <story-id>`. It requires no login and outputs the image URL. The URL returns 404 until sync runs. GitHub's image proxy does not cache this 404, so the image resolves automatically once synced.
- **After push:** Run `save chromatic sync --wait`. This waits for the `e2e` workflow's Chromatic build to finish and populates every page's URL. If the build has a baseline, it saves `.before.png` and `.diff.png` beside each snapshot.
- **Setup:** The repository root `.save.toml` contains `chromatic_app_id`. Sync reads `CHROMATIC_PROJECT_TOKEN` from `.env`, which `tools/setup-worktree` copies into new worktrees. Run `save chromatic login` once per machine to authenticate via the browser; tokens refresh automatically.

## Make heavy use of diagrams

GitHub renders Mermaid code fences in PR descriptions. Use a diagram wherever it saves the reviewer from reconstructing flow, ordering, state, or structure from the diff. Skip it for a mechanical edit, one-line fix, pure rename, or config change. If an existing diagram answers the question, link it instead.

Limit each diagram to one question; split diagrams that exceed 20 nodes or mix flow with static structure.

| Question                          | Diagram                       |
| --------------------------------- | ----------------------------- |
| What is the flow or pipeline?     | `flowchart`                   |
| In what order do components talk? | `sequenceDiagram`             |
| What is the lifecycle?            | `stateDiagram-v2`             |
| What is the data model?           | `classDiagram` or `erDiagram` |
| What did the refactor change?     | a before-and-after pair       |

Read [the Mermaid guide](mermaid-guide.md) before drawing. Put a lasting architecture diagram in the doc that owns the topic and link that doc from the PR. A diagram kept only in a PR body won't stay maintained.

Before opening a PR containing Mermaid, write the exact body to a file and run `mise run diagram-check <file>`. PR descriptions aren't committed, so no other local gate catches their Mermaid errors.

## Before you submit

- [ ] `mise run check` green locally, or the description names every failure
- [ ] History is linear on `origin/main`, each commit an atomic reviewable change
- [ ] If stacked: native `gh stack` used, layers planned, 100–400 code lines per PR
- [ ] Docs synced into this PR
- [ ] Fact sheet written from diff and test output (`pr-facts-<topic>`), following `.claude/skills/pr/fact_sheet.md`
- [ ] Description composed with Gemini Flash via `pi -p --model openrouter/google/gemini-3.8-flash --append-system-prompt .claude/skills/pr/composer.md ...`
- [ ] Body reviewed for diff accuracy; prose fits tier word budget (Light \~75, Standard \~300, Deep \~500)
- [ ] Empty sections omitted (no placeholders for unneeded sections)
- [ ] Every behavior change has safe evidence; no session data in the body
- [ ] Required visuals included; Mermaid blocks validated with `mise run diagram-check <file>`
- [ ] Opened with `gh pr create --body-file <file>`

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

Every PR lands by squash. Use `gh stack merge --squash` or the merge button for a stack, and the merge button or `gh pr merge --squash` for a single branch. In a native stack, merging a mid-stack PR also merges every PR below it in one operation, after which GitHub retargets the next layer to `main`.

Land only when directed.

### Waiting for green CI

Nothing on GitHub enforces green CI, by choice: this repository deliberately has no rulesets requiring checks, so a human may merge on red when necessary. However, an agent must always wait for green CI before landing:

- Watch the checks, as in [CI and checks](#ci-and-checks), on the target PR and every layer below it.
- Don't merge if any CI check fails.
- Ignore Chromatic's `UI Tests` and `UI Review`, which represent human sign-offs rather than automated test gates.

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
