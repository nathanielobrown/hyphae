"""The analysis layer: the production defaults and the runner that binds and cites a library query.

Read-only by construction — the store is opened read-only and no query file writes. The
process these queries serve is `plans/mycelia-analysis/design.md`.
"""
