"""The projects landing at `/`: every project the store holds sessions for.

Three dependencies and an adapter, which is the shape a full document takes
(`plans/deepen-viewer-reads/design.md`): the read opens the store and closes it, the markup
turns what it found into elements with nothing open, and the endpoint knows only the viewer
and the finished page. FastAPI resolves each once per request, so a route that wanted the
model as well as the markup would pay for no second read.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from hyphae.view.components import Html
from hyphae.view.deps import ViewerDep
from hyphae.view.pages.projects import markup, read
from hyphae.view.pages.projects.models import ProjectsPage

router = APIRouter()


def projects_read(viewer: ViewerDep) -> ProjectsPage:
    """The landing page read whole, and the store closed behind it."""
    return read.projects(viewer.db)


ProjectsRead = Annotated[ProjectsPage, Depends(projects_read)]


def projects_markup(page: ProjectsRead, viewer: ViewerDep) -> Html:
    """That read, rendered."""
    return markup.projects_page(page=page, dev=viewer.dev)


ProjectsMarkup = Annotated[Html, Depends(projects_markup)]


@router.get("/")
def projects_page(page: ProjectsMarkup, viewer: ViewerDep) -> Response:
    """Every project the store holds sessions for, most recently active first."""
    return viewer.html(page)
