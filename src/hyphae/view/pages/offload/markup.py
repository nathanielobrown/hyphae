"""The offload page's markup: the typed file, and the chunk of it this page serves."""

from urllib.parse import quote

import htpy

from hyphae.view.components import Html, citation, layout
from hyphae.view.pages.offload.models import OffloadPage
from hyphae.view.text import format as fmt


def offload_page(*, page: OffloadPage, dev: bool) -> Html:
    """One chunk of a tool result Claude Code wrote to a file beside the transcript.

    `page.after` is where the next chunk starts, or None where this one reached the end.
    """
    return layout.page(
        tab_title=f"{page.file.name} — hyphae",
        scripts=None,
        main=htpy.section(id="offload", data_offload=page.file.name)[
            [
                htpy.h1(data_field="name")[page.file.name],
                htpy.p(".numbers")[
                    [
                        htpy.a(href=f"/session/{page.session_id}")[page.session_id],
                        htpy.span[
                            [
                                htpy.span(data_field="size_bytes")[fmt.count(page.file.size_bytes)],
                                " bytes on disk",
                            ]
                        ],
                        htpy.span[
                            [
                                htpy.span(data_field="content_chars")[
                                    fmt.count(page.file.content_chars)
                                ],
                                " chars stored",
                            ]
                        ],
                        # Only when it happened: the extractor could not decode the file as
                        # text and replaced what it could not read, so what is shown here is
                        # not what the tool wrote.
                        htpy.span(data_field="lossy_decode")["some bytes did not decode as text"]
                        if page.file.lossy_decode
                        else None,
                    ]
                ],
                htpy.pre(data_field="content")[page.file.chunk],
                htpy.p(".more", data_more_offload=page.after)[
                    htpy.a(
                        href=f"/session/{page.session_id}/offload/{quote(page.file.name, safe='/')}"
                        f"?after={page.after}&size={page.size}"
                    )[f"next {fmt.count(page.size)} chars"]
                ]
                if page.after is not None
                else None,
            ]
        ],
        footer=citation.footer(citations=page.citations),
        dev=dev,
    )
