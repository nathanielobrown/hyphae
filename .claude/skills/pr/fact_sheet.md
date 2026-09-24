# Pull request fact sheet

The fact sheet is a verbose draft of the pull request. Claude generates it from the final `git diff <base>...HEAD` and test output, never from the initial plan. Use `origin/main` for `<base>`, or the parent layer's branch for an upper stack layer. If an auditor reviews the branch, its accepting pass writes the fact sheet; otherwise, the session that implemented the changes writes it.

The composer agent rewrites this file into the final PR description. It cuts and formats, but does not research. Because it reads little beyond this file, any detail omitted here will be missing from the PR.

## Rules

- **Prioritize completeness over polish.** Use rough sentences or bullets. The composer handles phrasing and cuts.
- **Drop empty sections.** If a field has nothing to say, omit it entirely. Do not write "None" or keep placeholder text.
- **Ground claims in artifacts.** Derive all technical statements, file paths, and snippets directly from the final diff and test execution. Copy identifiers and paths character-for-character so the composer can quote them safely.
- **Never paste session data.** Use redacted output or a fixture path (`AGENTS.md`).
- **Follow naming conventions.** Save as the handoff `pr-facts-<topic>`: `handoffs/handoff_<YYYY_MM_DD>_pr-facts-<topic>.md` (`docs/handoffs.md`).

---

### Tier and budget
- Tier: Light (~75 words) | Standard (~300 words) | Deep (~500 words), matching the blast radius in `AGENTS.md`: small and clear, medium, or foundation-shaping.

### Stack
- Stack goal: <1–2 sentences on overall stack goal if bottom PR; name bottom PR if upper layer; omit if not a stack>

### What changed
- Headline: <one sentence: what this PR's net diff does, as you'd tell the reviewer>
- Changes: <the main changes grouped by purpose, with their key paths; not a file-by-file walk>
- Background: <context a reader might mistake for this PR's work: earlier layers or PRs, behavior that already exists, things that never existed on the base>

### Why
- <author rationale and motivation>

### Feedback wanted
- Review focus: <specific areas, questions, or architectural decisions requiring reviewer attention>

### Judgment points
- <path/to/file>: <risk, open decision, or known issue; order items by highest risk first>

### Design
- Design points: <architectural choices or subtleties not obvious from the diff alone; draw on the `design-<topic>` handoff if there is one>
- Plan deviations: <deviations from initial plan or design, if any>

### Visuals
- <`save` command output (`save <file>` or `save story <story-id>`) or a Mermaid block: one line describing what it shows>
- <interactive explainer: its `save` link and one line on what the reader can do there>

### Verification
- Checks executed: <commands run and output excerpts beyond standard green checks>
- Unverified areas: <code paths or scenarios not exercised, including a `testing-plan-<topic>` handoff's uncovered leaves>
- Test or CI edits: <any modifications to tests, CI configuration, or thresholds>

### Links
- Plan: <path or URL>
- Issue: <path or URL>
- Artifacts: <path or URL>

### Emphasis
- <free-form instructions to the composer, e.g. "focus on the API migration; keep the refactor brief">
