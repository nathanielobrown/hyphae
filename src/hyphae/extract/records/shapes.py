"""Every record shape in one roster, and the dispatch from a raw record to its model.

The families live beside this module: `base` holds the mixin ladder, and `conversation`,
`attachments`, `system` and `bookkeeping` hold the models themselves. `ArchivedRecord` here takes
every registered kind no reader opens, and outside a test run every kind neither registry names.
"""

from typing import Any

from hyphae.extract.records.attachments import AttachmentRecord
from hyphae.extract.records.base import Record, SessionContext
from hyphae.extract.records.bookkeeping import (
    AgentNameRecord,
    AiTitleRecord,
    CustomTitleRecord,
    ForkContextRefRecord,
    PrLinkRecord,
)
from hyphae.extract.records.conversation import AssistantRecord, UserRecord
from hyphae.extract.records.registry import ArchiveRecordType, RecordType, SystemSubtype
from hyphae.extract.records.system import (
    CompactBoundaryRecord,
    LocalCommandRecord,
    ModelConsentFallbackRecord,
    SystemRecord,
    TurnDurationRecord,
)


class ArchivedRecord(SessionContext):
    """A kind the store keeps verbatim, whose own fields no reader opens.

    Every registered archive kind, and outside a test run every kind no registry names at all
    (`records/unknown.py`) — which is the same claim either way: the envelope, and nothing else.

    It extends `SessionContext` because the envelope is read off every kind that carries one:
    `raw_record` takes `uuid` and `timestamp`, and `session_of` takes `cwd`, `gitBranch`,
    `version` and `entrypoint` from the first record that has them, which for five of the
    3,647 threads in the store is a thin `system` subtype (scanned 2026-09-04). Past the envelope
    it claims nothing: the rest of its keys are the archive's, kept whole rather than described.
    It is outside `RECORD_MODELS`, so it prints no row in `docs/schema.md`.
    """

    OPAQUE = "archived verbatim; its fields are the archive's, not a claim"


# Every record model, in the order the tables name them.
RECORD_MODELS: tuple[type[Record], ...] = (
    UserRecord,
    AssistantRecord,
    AttachmentRecord,
    SystemRecord,
    TurnDurationRecord,
    CompactBoundaryRecord,
    LocalCommandRecord,
    ModelConsentFallbackRecord,
    CustomTitleRecord,
    AiTitleRecord,
    AgentNameRecord,
    PrLinkRecord,
    ForkContextRefRecord,
)


# Registered kinds `ArchivedRecord` takes, each with the reason nothing opens it. Every archive
# type is here by construction; a `system` subtype is here when it is too thin to model, which
# also says `SystemRecord` is the base of the four modelled subtypes and no longer a fallback.
ARCHIVED_UNREAD: dict[ArchiveRecordType | SystemSubtype, str] = {
    **dict.fromkeys(
        ArchiveRecordType, "archived verbatim and read by nothing, so there is no field to describe"
    ),
    SystemSubtype.AWAY_SUMMARY: "carries only the common system fields and a `content` string",
    SystemSubtype.INFORMATIONAL: "carries only the common system fields and a `content` string",
    SystemSubtype.SCHEDULED_TASK_FIRE: (
        "carries only the common system fields and a `content` string"
    ),
    SystemSubtype.API_ERROR: (
        "its retry fields are read by nothing, and one recorded error is thin evidence for them"
    ),
    SystemSubtype.AGENTS_KILLED: "carries only the common system fields",
    SystemSubtype.STOP_HOOK_SUMMARY: (
        "its hook fields are read by nothing, and one recorded summary is thin evidence for them"
    ),
}

# The archived kinds each branch of the dispatch may answer, kept apart because the two
# registries name two levels of one envelope and a member of either is just a string: without
# the split, `api_error` as a top-level type and `queue-operation` as a `system` subtype would both
# be archived, when a kind moving up or down the envelope is exactly the change to crash on.
_ARCHIVED_TYPES = frozenset(k.value for k in ARCHIVED_UNREAD if isinstance(k, ArchiveRecordType))
_ARCHIVED_SUBTYPES = frozenset(k.value for k in ARCHIVED_UNREAD if isinstance(k, SystemSubtype))

# What `model_for` dispatches on: the record type, and the subtype for the `system` records
# that carry fields of their own.
_TYPE_MODELS: dict[str, type[Record]] = {}
_SUBTYPE_MODELS: dict[str, type[Record]] = {}
for _model in RECORD_MODELS:
    _subtype = _model.SUBTYPE
    if _subtype is None:
        _TYPE_MODELS[_model.RECORD_TYPE.value] = _model
    else:
        _SUBTYPE_MODELS[_subtype.value] = _model


def kind_of(record: dict[str, Any]) -> str:
    """How a record's kind is spelled wherever one is named: its type, or `system/<subtype>`.

    The two registries name two levels of one envelope, so a subtype on its own would read as a
    type. One string, carrying the level it was found at.
    """
    kind = str(record.get("type", ""))
    if kind == RecordType.SYSTEM:
        return f"{kind}/{record.get('subtype', '')}"
    return kind


def model_for(record: dict[str, Any]) -> type[Record] | None:
    """The model describing one raw record, or `None` for a kind neither registry names.

    `None` is a schema change, not a record to skip: the caller archives it verbatim under
    `ArchivedRecord` and tallies the kind, or stops if a person is looking (`records/unknown.py`).
    Nothing is dropped either way, because a record we quietly skip is a wrong count months from
    now. A field a reader needs inside a kind we do read is the other tier, and still raises.
    """
    kind = record.get("type", "")
    if kind == RecordType.SYSTEM:
        subtype = record.get("subtype", "")
        modelled = _SUBTYPE_MODELS.get(subtype)
        if modelled is not None:
            return modelled
        return ArchivedRecord if subtype in _ARCHIVED_SUBTYPES else None
    modelled = _TYPE_MODELS.get(kind)
    if modelled is not None:
        return modelled
    return ArchivedRecord if kind in _ARCHIVED_TYPES else None
