# Phase 5: close-out

Delete what earlier phases carried so their PRs stayed moves, rename what still names the driver, and bring the documents to the code. One PR, opened when the last phase 4 PR lands.

Back to [the overview](overview.md).

## Problem

Phase 2 kept `DuckDbExporter` and `StoreSource` under their old names so its PRs stayed moves. Phase 3 kept `store/pages.py` and its enums so phase 4 could delete them a member at a time. `TABLES` in the writer and the reader's row order say the same thing twice, as the refactor audit's S23 recorded. `docs/store.md`, `docs/viewer.md`, `docs/analysis.md`, `CONTEXT.md`, and the layout tree in `CLAUDE.md` describe paths phase by phase; this phase describes the whole.

## File-tree diff

```
src/hyphae/store/
  pages.py             deleted; `rg 'store.pages' src tests tools` must be empty first
  trace_store.py       ~ DuckDbExporter → TraceWriter; TABLES folded with the reader's row order into one registry both sides read
  trace_reader.py      ~ StoreSource → TraceReader; still an Extractor
docs/store.md          ~ a section "Who reads and writes": one repository per area, the writer, the reader, and the rule that only `store` imports the driver, citing `docs/layering.md`
docs/layering.md       ~ the prose beside the generated graph names the three final contracts
docs/viewer.md         ~ every read a page makes is a repository method; the Query page's citation comes from the repository
docs/analysis.md       ~ the library's path
CONTEXT.md             ~ Repository, Result model, Store handle; Library and Store point at the package
CLAUDE.md              ~ `mise run cogs` regenerates the layout tree from the package docstrings
pyproject.toml         ~ the final contract set, below
```

## Key contracts

The final linter configuration, matching the overview's architecture diagram:

```toml
[[tool.importlinter.contracts]]
name = "Layers"
type = "layers"
containers = ["hyphae"]
exhaustive = true
layers = [
  "cli",
  "view",
  "analyze | enrich | export",
  "store | extract",
  "pipeline",
  "models | projects | pricing | settings | store_path",
]

[[tool.importlinter.contracts]]
name = "Only the store speaks DuckDB"
type = "forbidden"
source_modules = ["hyphae.cli", "hyphae.view", "hyphae.analyze", "hyphae.enrich", "hyphae.export", "hyphae.extract", "hyphae.pipeline", "hyphae.models"]
forbidden_modules = ["duckdb"]

[[tool.importlinter.contracts]]
name = "The viewer reads through the store"
type = "forbidden"
source_modules = ["hyphae.view"]
forbidden_modules = ["hyphae.enrich", "hyphae.analyze", "hyphae.extract", "hyphae.export"]
```

Glossary entries to add, one line each in `CONTEXT.md`:

- **Repository**: one class in `store/` owning every read and write of one area's tables; a page or a pass asks it, never the connection.
- **Result model**: a `models/` type a repository returns: an entity, or a variant derived from one by inheritance, sized for the read.
- **Store handle**: the open store a request or a run holds, with one repository per area hung off it.

## Chosen test seam

A green test suite, plus `mise run lint-imports` with the three contracts and `mise run check` for the doc gates. `tests/test_scaffolding.py` or its equivalent pins the package list and the layout tree, and must name the two new packages.

## Slices

One PR, three commits: the deletions, the renames, the documents.

## Decisions

- **Renames last.** A rename in a move PR hides the move in the diff. They are held to the end so each earlier PR reads as one thing.
- **Fold the two registries into the writer's.** The reader rebuilds from `TABLES` already; the row order it keeps beside it is the duplicate.

## Out of scope

- A per-area rules file under `.claude/rules/` for the store. Worth writing once the repositories have settled, but not in this PR.
- Updating the Notion page that started this. It should point here once phase 0 lands.
