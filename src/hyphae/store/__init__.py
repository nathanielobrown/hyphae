"""The trace store: the schema, the writers that own every table in the DuckDB file, the
reader that rebuilds a session from its rows, the versioned SQL library and macros every query
reads through, the page reads a viewer request runs and the repositories that answer those
reads and `hp query` in models, and the `Store` handle that is the only way any other package
runs SQL."""
