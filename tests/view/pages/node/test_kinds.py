"""What a node page holds per kind, read against `Kind` itself rather than a list beside it.

A node page's per-kind variation lives in tables total over `Kind`: `nav_tree.LEVELS` says what
hangs under a kind in each preset. The type checker closes a match over an enum but not a dict,
so these leaves are what closes them — a kind added without a row is red here rather than a
`KeyError` halfway down the first page that renders it.

Nothing here reads the store: what the cells *do* is swept by the pages that spend them
(`test_nav_tree__presets.py`, `test_node.py`), and re-asserting it here would be a second copy
of one fact. What is only true by convention is what these leaves hold.
"""

from inspect import signature

from hyphae.view.nodes import Kind, Preset
from hyphae.view.pages.node.nav_tree import LEVELS


def test_every_kind_of_node_says_what_hangs_under_it_in_every_preset() -> None:
    """`LEVELS` is total over `Kind`, and every preset of every row names a builder.

    The NavTree opens whatever the path reaches, so a kind with no row is a page that renders
    and then raises halfway down. Totality used to be held by a comment over 24
    `(Kind, Preset)` cells; the assertion is against `Kind` itself, so a kind added to the enum
    reddens this leaf and says which one is missing.

    The signature is asserted because it is the whole reason the seven adapters could go: a
    builder is picked by kind and reads its ids off the `Ref`, so a caller holding a ref can
    read a level without rendering the node it hangs under. A cell that took unpacked ids
    would need an adapter again, and the adapter is where a kind gets forgotten.
    """
    assert set(LEVELS) == set(Kind)
    for kind, under in LEVELS.items():
        for preset in Preset:
            builder = under.under(preset)
            assert callable(builder), (kind, preset)
            assert list(signature(builder).parameters) == ["connection", "corpus", "at"], (
                kind,
                preset,
            )
