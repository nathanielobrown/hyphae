"""Every URL the node page answers, gathered into one router.

Four modules carry routes, by what the reader asked for: a whole page, a child opened in
place, the numbers behind a NavTree row, and the rest of a cut value — an enrichment line
being one of those, declared in the registry like every other Detail. `knobs` carries none: it
is the dependency a page and an expansion take their URL through, which parses the four knobs a
node URL may name and refuses the rest.

What a route answers with is read behind it, framework-free — `browser` for a whole document,
`fragments` for the small fetches under one. A route decides a status and builds a response,
and that is all it decides.
"""

from fastapi import APIRouter

from hyphae.view.pages.node.routes import details, expansions, pages, popovers

# Extended rather than `include_router`, for the reason `view/app.py` extends this one.
router = APIRouter()
for part in (pages, expansions, popovers, details):
    router.routes.extend(part.router.routes)
