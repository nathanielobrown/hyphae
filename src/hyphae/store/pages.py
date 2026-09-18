"""What a page still reads as a raw row: the dict shape a store row crosses the store line in.

Every read a page makes runs through a repository on the `Store` a request holds
(`store/handle.py`), and comes back as a model. `Row` is what is left of the viewer's
row-reading: the shape the NavTree's builders (`view/builders.py`) and the ledger
(`view/nodes.py`) still take, which a page makes out of a model with `asdict`. It goes when
they take the models themselves (`plans/store-layering/phase-5-*.md`), and this module with it.
"""

from typing import Any

Row = dict[str, Any]
