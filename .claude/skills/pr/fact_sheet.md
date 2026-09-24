# Pull request fact sheet

Claude fills in this fact sheet from the final `git diff <base>...HEAD` and test output, never from the initial plan. `<base>` is `origin/main`, or the parent layer's branch for an upper stack layer. When an auditor reviews the branch, its accepting pass writes the fact sheet; otherwise the session that did the work writes it.

The composer agent reads this file and the diff to draft the pull request description. It summarizes what changed from the diff itself, so don't restate the diff here. Everything else it writes comes from this file.

## Rules

- Use terse bullets. Do not polish or write prose.
- Omit any section or field that has nothing to say. Don't write "None" or leave placeholder text.
- Derive all technical claims, file paths, and snippets directly from the final diff and test execution.
- Never paste session data; use redacted output or a fixture path (`AGENTS.md`).
- Save as the handoff `pr-facts-<topic>`: `handoffs/handoff_<YYYY_MM_DD>_pr-facts-<topic>.md` (`docs/handoffs.md`).

---

### Tier and budget
- Tier: Light (~75 words) | Standard (~300 words) | Deep (~500 words), matching the blast radius in `AGENTS.md`: small and clear, medium, or foundation-shaping.

### Stack
- Stack goal: <1–2 sentences on overall stack goal if bottom PR; name bottom PR if upper layer; omit if not a stack>

### Why
- <author rationale and motivation; what changed comes from the diff>

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
