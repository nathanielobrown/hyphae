"""What a node page's read hands its markup: the node, where it sits, and what hangs under it.

Neutral by design (`plans/deepen-viewer-reads/design.md`): no request, no response, no element
and no raw store row. The row types the four groups are made of are declared beside the
components that print them — a NavTree row, a log row, the facts — because a node page is one
document assembled from many reads, and each of those reads already names its own row.
"""

from collections.abc import Mapping, Sequence
from typing import NamedTuple

from hyphae.view.citation import Cited
from hyphae.view.components.parts import Pager
from hyphae.view.detail import Detail, EnrichmentLines
from hyphae.view.enrichment import Enrichment
from hyphae.view.failures import Step as Failures
from hyphae.view.nodes import Node
from hyphae.view.pages.node.columns import Shape
from hyphae.view.pages.node.markup.body import Facts
from hyphae.view.pages.node.markup.logs import Logged
from hyphae.view.pages.node.markup.nav_tree import NavTreeRow, PresetChoice
from hyphae.view.pages.node.walk import Step as Walked


class Trail(NamedTuple):
    """The way out of the session, above the nodes inside it.

    Neither step is a node, so neither carries a node's marks or a knob suffix — a click on
    either leaves the session. `project_url` is nothing where the store holds no path to filter
    the list by, and the project then prints without a link.
    """

    list_url: str
    project_dir: str | None
    project_url: str | None


class Said(NamedTuple):
    """What a pass wrote about the node, and the way to the whole of each line it wrote.

    One value rather than two: a pane that had the words without the links, or the links
    without the words, is not a state `view/detail.py` can produce.
    """

    enrichment: Enrichment
    lines: EnrichmentLines


class Archived(NamedTuple):
    """The bytes behind the node: the thread's transcript, and the line it was read from."""

    thread_url: str
    line_no: int | None


class Nav(NamedTuple):
    """The NavTree side: the preset control, the one open path, and the thread it was read for.

    Not `nav_tree.NavTree`, which is what building the tree produced: this is the half of it a
    page draws, and the preset control and the thread are the page's own.
    """

    choices: Sequence[PresetChoice]
    rows: Sequence[NavTreeRow]
    thread: str


class Body(NamedTuple):
    """The node read whole: its own fields, what a pass said about it, its fat values, its bytes.

    What the pane would still show if the session around it were gone — everything else the
    page carries is about where the node sits.
    """

    facts: Facts
    said: Said | None
    details: Sequence[Detail]
    archived: Archived


class Steps(NamedTuple):
    """Where reading in order goes: the node before this one on its level, and the one after."""

    previous: Walked | None
    next: Walked | None


class Bearings(NamedTuple):
    """Where the node sits, and every way off it that is not a step down into a child.

    Three ways out, and going down is the NavTree's: back out of the session along the crumb
    chain, along the level with the walk, and across to another failure with the stepper.
    """

    trail: Trail
    chain: Sequence[Node]
    walked: Steps
    # How many tool calls the session failed, which is what the way into the errors page says.
    tool_errors: int | None
    # The failures either side of this node, where the pane is standing on one.
    failures: Failures | None


class Children(NamedTuple):
    """One page of the node's children, as the log under the body reads them.

    `total` is the level's own size rather than the page's: the heading counts the level, and
    the pager under it is cut from the same number.
    """

    shape: Shape
    rows: Sequence[Logged]
    total: int
    pager: Pager | None


class NodePage(NamedTuple):
    """One node of a session read whole: everything the page draws, and what it ran to get it.

    `selection` is the one value every part reads — it names the tab, heads the crumb chain and
    titles the body — so it stands apart from the four groups around it. `suffix` is what every
    href on the page carries, so a click serves the URL it displays.
    """

    selection: Node
    nav: Nav
    body: Body
    bearings: Bearings
    children: Children
    citations: Mapping[str, Cited]
    suffix: str
