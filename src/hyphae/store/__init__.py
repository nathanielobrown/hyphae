"""The trace store: the schema, the writers that own every table in the DuckDB file, the
reader that rebuilds a session from its rows, and the versioned SQL library and macros every
query reads through."""
