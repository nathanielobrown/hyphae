"""The one config every model a store row builds is declared under.

A repository builds a model by column name, `Model(**row)`, and the model is what the
statement is held to: strict, so lax mode cannot rewrite a value on its way in — `0` would
become `0.0` and print the same page — and no extras, so a column the statement gained raises
where it is read rather than vanishing.
"""

from pydantic import ConfigDict

ROW = ConfigDict(strict=True, extra="forbid")
