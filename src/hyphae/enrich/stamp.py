"""The staleness rule: what an enrichment row was written under, and what makes it stale.

Four values decide it — the hash of the rendered content, the level's prompt version, the
taxonomy version, and the model that answered. `mint` stamps them and `stale` compares two
stamps. The `Stamp` itself and the two versions are declared in `models/enrichment.py`; the
versions arrive here as a `Versions`, whose `moved_past` judges the half of the rule a reader
with only a stored row can apply. One `Versions` feeds both, so a pass and a page cannot hold
two versions of the rule.
"""

import hashlib
from collections.abc import Mapping

from hyphae.models.enrichment import Level, Stamp, Versions


def input_hash(rendered: str) -> str:
    """The staleness hash: the rendered content and nothing else.

    Not the instructions and not the output schema — a level's `prompt_version` covers those,
    so an instruction edit does not have to pretend the content changed.
    """
    return hashlib.sha256(rendered.encode()).hexdigest()


def mint(versions: Versions, level: Level, rendered: str, model: str) -> Stamp:
    """What a row for `level` would be stamped now under `versions`, given its render and the
    answering model."""
    return Stamp(
        input_hash=input_hash(rendered),
        prompt_version=versions.prompt[level],
        taxonomy_version=versions.taxonomy,
        model=model,
    )


def stale(planned: Mapping[str, Stamp], held: Mapping[str, Stamp]) -> list[str]:
    """The planned keys whose held stamp is not the planned one, in planned order.

    No row counts as not the one, which is how a first pass finds work. Held keys nothing
    planned are not reported: a leftover row is the sweep's business.
    """
    return [key for key, stamp in planned.items() if held.get(key) != stamp]
