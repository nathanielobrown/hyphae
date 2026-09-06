"""What a node page holds per kind, read against `Kind` itself rather than a list beside it.

A node page's per-kind variation lives in two tables total over `Kind`: `kinds.KINDS` says what
one kind's page reads, lists and previews, and `nav_tree.LEVELS` what hangs under it in each
preset. The type checker closes a match over an enum but not a dict, so these leaves are what
closes them — a kind added without a row is red here rather than a `KeyError` halfway down the
first page that renders it.

Nothing here reads the store: what the cells *do* is swept by the pages that spend them
(`test_nav_tree__presets.py`, `test_node.py`), and re-asserting it here would be a second copy
of one fact. What is only true by convention is what these leaves hold.
"""

from inspect import signature

from hyphae.view.enrichment import Descriptions
from hyphae.view.nodes import Kind, Preset, Ref
from hyphae.view.pages.node.columns import COLUMNS, Shape
from hyphae.view.pages.node.kinds import KINDS
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


def test_every_kind_of_node_says_what_its_page_reads_and_what_a_log_lists_it_in() -> None:
    """`KINDS` is total over `Kind`, and the cells one route reads together agree with each other.

    Eight routes each spelled their own header read, trail, log, details and 404; the row is
    where that lives now, and a row half filled is a page that renders and then raises. The
    cells below are the pairs a caller reads as one: `routes/expansions.py` guards on
    `listed_as` and then reads `titled` behind it, and `browser.py` reads `counts` only
    where a log listed the level.
    """
    assert set(KINDS) == set(Kind)
    for kind, spec in KINDS.items():
        assert callable(spec.header), kind
        # A kind with no children reads no log and counts none; a kind with children reads a
        # log, and counts them wherever an expansion of it is served — a bucket is never
        # expanded, and its count is the corpus's rather than a header column's.
        assert (spec.log is None) == (spec.under is Shape.NONE), kind
        assert (spec.counts is None) == (spec.under is Shape.NONE or spec.listed_as is None), kind
        # An expansion is served for exactly the kinds a children log lists, and it is named
        # from its own header: one guard in the route answers for both cells.
        assert (spec.listed_as is None) == (spec.titled is None), kind
        assert spec.listed_as is None or spec.listed_as in COLUMNS, kind
        # The trail is what `nav_tree.ancestry` is seeded with, innermost last, so the node
        # itself ends it — a trail that stopped at the parent would open the path to the wrong
        # row and select nothing.
        at = Ref(kind, "main", "node")
        trail = spec.trail(at, {"turn_id": None, "api_call_id": "call"})
        assert trail[-1] == at, kind
        assert all(isinstance(step, Ref) for step in trail), kind
        # And nothing a pass never wrote about is read as though it had: over a store no pass
        # reached, every describable kind answers None rather than raising.
        assert spec.describe is None or spec.describe(Descriptions(), at) is None, kind
    # Each 404 says which kind was asked for. Eight routes spelled eight sentences, and two
    # kinds sharing one would tell a reader the wrong thing about which URL was wrong.
    assert len({spec.missing for spec in KINDS.values()}) == len(KINDS)
    # One kind per shape of log, which is what lets an expansion work its span out from the
    # child alone (`routes/expansions.py`).
    lists = {spec.listed_as: kind for kind, spec in KINDS.items() if spec.listed_as is not None}
    assert len(lists) == sum(1 for spec in KINDS.values() if spec.listed_as is not None)
    # An expansion lists its level instead of counting it only where the level below opens
    # nothing further, so the accordion stops at one: the api call alone, whose tool calls end
    # the tree. Spelled in the table rather than derived, and this is what holds the two together.
    for kind, spec in KINDS.items():
        if spec.opens:
            assert KINDS[lists[spec.under]].under is Shape.NONE, kind
