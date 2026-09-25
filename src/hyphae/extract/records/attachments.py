"""The `attachment` record: context Claude Code slipped into the conversation beside a turn.

One model covers every attachment kind. Its `attachment` object is a `QueuedCommand` when it
carries a message delivered mid-turn, and an undescribed dict for the other kinds, which no
reader opens.
"""

from typing import Annotated, Any, Literal

from pydantic import Discriminator, Field, Tag

from hyphae.extract.records.base import SessionContext
from hyphae.extract.records.blocks import Kinded
from hyphae.extract.records.evidence import ATTACHMENT_CENSUS, INTERJECTION, Cited, Described
from hyphae.extract.records.registry import ContentBlock, RecordType

# What the peer-only keys below have in common: 9 queued commands and 43 `user` records carry
# them, so no fixture holds one.
_PEER_EVIDENCE = Cited(scan=ATTACHMENT_CENSUS, note="peer messages only")


class Origin(Described):
    """Who sent a message: the person, or another session speaking through Claude Code."""

    kind: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "The sender, as `human`, `coordinator` or `peer` on a queued command. A `user` "
                "record also writes `task-notification` (3,949 records) and "
                "`auto-continuation` (1)"
            ),
        ),
        Cited(INTERJECTION, "2.1.220", note="`human`, on a prompt and on a queued command"),
    ]
    body: Annotated[
        str | None,
        Field(
            default=None,
            description="What the peer sent. It is part of the text the message delivered",
        ),
        _PEER_EVIDENCE,
    ]
    from_: Annotated[
        str | None,
        Field(
            default=None,
            alias="from",
            description=("The peer's address: an agent name, an agent id, or a `uds:` socket path"),
        ),
        _PEER_EVIDENCE,
    ]
    name: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "The peer's display name. It usually repeats `from`; 3 `user` records omit it"
            ),
        ),
        _PEER_EVIDENCE,
    ]
    senderTaskId: Annotated[
        str | None,
        Field(default=None, description="The id of the task the peer was running"),
        _PEER_EVIDENCE,
    ]
    fromMode: Annotated[
        str | None,
        Field(
            default=None,
            description="A mode the peer ran in. All three recorded values are `bypass`",
        ),
        Cited(scan=ATTACHMENT_CENSUS, note="only `2.1.259` writes it"),
    ]
    hopChain: Annotated[
        list[str] | None,
        Field(
            default=None,
            description="The relays a message passed through. One queued command carries it",
        ),
        Cited(scan=ATTACHMENT_CENSUS, note="only `2.1.259` writes it"),
    ]
    msg_id: Annotated[
        str | None,
        Field(default=None, description="The message's own id, a uuid"),
        Cited(scan=ATTACHMENT_CENSUS, note="only `2.1.259` writes it"),
    ]
    verifiedPeerPid: Annotated[
        int | None,
        Field(default=None, description="The process id Claude Code confirmed the peer runs as"),
        Cited(scan=ATTACHMENT_CENSUS, note="only `2.1.259` writes it"),
    ]
    handback: Annotated[
        bool | None,
        Field(
            default=None,
            description=(
                "A flag recorded once, as true, on a `user` record. What it changes is unrecorded"
            ),
        ),
        Cited(scan=ATTACHMENT_CENSUS, note="only `2.1.280` writes it"),
    ]


# A queued prompt written in block form: the list a message's own `content` would hold.
class PromptText(Kinded):
    """Prose in a block-form queued prompt."""

    BLOCK = ContentBlock.TEXT
    EVIDENCE = (Cited(INTERJECTION, "2.1.221"),)

    type: Annotated[
        Literal[ContentBlock.TEXT],
        Field(description="The block kind, which dispatches the block to the model below"),
    ]
    text: Annotated[
        str | None,
        Field(default=None, description="What the person typed beside the picture"),
        Cited(INTERJECTION, "2.1.221"),
    ]


class PromptImage(Kinded):
    """A picture pasted into a queued prompt."""

    BLOCK = ContentBlock.IMAGE
    EVIDENCE = (Cited(INTERJECTION, "2.1.221", note="its `data` redacted"),)

    type: Annotated[
        Literal[ContentBlock.IMAGE],
        Field(description="The block kind, which dispatches the block to the model below"),
    ]
    source: Annotated[
        dict[str, Any] | None,
        Field(
            default=None,
            description=(
                "The picture itself, as a `type`, a `media_type` and base64 `data`. Nothing has "
                "opened it"
            ),
        ),
        Cited(INTERJECTION, "2.1.221", note="its `data` redacted"),
    ]


class QueuedCommand(Described):
    """A message delivered while a turn was running: typed by the person, sent by another
    session, or a background task's completion notice."""

    type: Annotated[
        Literal["queued_command"],
        Field(description="The attachment kind"),
        Cited(INTERJECTION, "2.1.220"),
    ]
    prompt: Annotated[
        str | list[Annotated[PromptText | PromptImage, Field(discriminator="type")]],
        Field(
            description=(
                "The message whole. One corpus prompt is a list of blocks, a `text` beside an "
                "`image`; every other is a string"
            ),
        ),
        Cited(INTERJECTION, "2.1.220"),
    ]
    commandMode: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "`prompt` for a message someone typed, `task-notification` for a task's notice. "
                "A coordinator's message omits it"
            ),
        ),
        Cited(INTERJECTION, "2.1.220", note="both values"),
    ]
    timestamp: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "When the message was queued. Every fixture record repeats it as its own "
                "timestamp, even a notice written 48 seconds later, in the next turn. Omitted "
                "where `commandMode` is"
            ),
        ),
        Cited(INTERJECTION, "2.1.220"),
        Cited(INTERJECTION, "2.1.267", note="the notice that waited"),
    ]
    origin: Annotated[
        Origin | None,
        Field(
            default=None,
            description="Who sent it. A task's notice carries none, since `commandMode` says so",
        ),
        Cited(INTERJECTION, "2.1.220"),
    ]
    source_uuid: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "A uuid on 56 of 1,227 queued commands that matches no record of its session, "
                "so what it names is unknown"
            ),
        ),
        Cited(scan=ATTACHMENT_CENSUS, note="`2.1.206`–`2.1.280`"),
        Cited(INTERJECTION, "2.1.263"),
    ]
    isMeta: Annotated[
        bool | None,
        Field(
            default=None,
            description=(
                "Always true where present, on 35 queued commands, nearly all a coordinator's or "
                "a peer's. What it changes is unrecorded"
            ),
        ),
        Cited(scan=ATTACHMENT_CENSUS),
        Cited(INTERJECTION, "2.1.259", note="a coordinator's and a peer's"),
    ]
    imagePasteIds: Annotated[
        list[int] | None,
        Field(default=None, description="The images pasted into the message, by id"),
        Cited(INTERJECTION, "2.1.221"),
    ]


def _attachment_kind(value: Any) -> str:
    """Which arm validates an `attachment`: `QueuedCommand` for its kind, a dict for the rest.

    Choosing by kind before validating is what makes a malformed queued command raise rather
    than slip into the dict arm the way a smart union would let it.
    """
    kind = value.get("type") if isinstance(value, dict) else getattr(value, "type", None)
    return "queued_command" if kind == "queued_command" else "other"


# One rendering of the attachment: the text Claude Code showed the model.
_RENDERED = (
    "What Claude Code showed the model for the attachment, as a list of `content` objects. "
    "Nothing has opened it. Claude Code added it in `2.1.259`"
)


class AttachmentRecord(SessionContext):
    """Context Claude Code attached to the conversation: a file, a reminder, a queued message."""

    RECORD_TYPE = RecordType.ATTACHMENT

    attachment: Annotated[
        Annotated[QueuedCommand, Tag("queued_command")] | Annotated[dict[str, Any], Tag("other")],
        Discriminator(_attachment_kind),
        Field(
            description=(
                "What was attached, dispatched on its `type`. Only a `queued_command` is "
                "modelled; the other kinds are kept whole and read by nothing"
            ),
        ),
        Cited(INTERJECTION, "2.1.220", note="a queued command and an `output_style`"),
    ]
    rendered: Annotated[
        list[dict[str, Any]] | None,
        Field(default=None, description=_RENDERED),
        Cited(scan=ATTACHMENT_CENSUS, note="48,753 records"),
        Cited(INTERJECTION, "2.1.259"),
        Cited(INTERJECTION, "2.1.220", absent=True),
    ]
    renderedInHumanTurn: Annotated[
        list[dict[str, Any]] | None,
        Field(
            default=None,
            description=(
                "The same, as shown inside the person's turn. Only queued commands carry it. "
                "Nothing has opened it"
            ),
        ),
        Cited(scan=ATTACHMENT_CENSUS, note="749 records, from `2.1.259`"),
        Cited(INTERJECTION, "2.1.259", note="task notices only"),
        Cited(INTERJECTION, "2.1.220", absent=True),
    ]
