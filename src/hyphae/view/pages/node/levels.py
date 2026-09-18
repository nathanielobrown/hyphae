"""One request's level reads, each repository call run once however many readers want its rows.

The NavTree opens the path down to the selection, and the walk beside the pane then reads those
same levels again to find what stands next to it — on a node five deep that is a quarter of the
page's query time, spent twice. A `Levels` is held by the request's `Corpus` and dies with it,
so nothing memoized here outlives the store it was read over.
"""

from collections.abc import Callable, Mapping
from typing import Any

# What a read is answered by: the repository method, bound to the store it reads over, and
# every argument it was called with, a mapping frozen to its sorted items so two spellings of
# one question are one key. The store is in the key through the method — a bound method is
# equal to another on the same repository — and a `Levels` belongs to one request anyway.
Asked = tuple[Callable[..., object], tuple[object, ...], tuple[tuple[str, object], ...]]


def _frozen(value: object) -> object:
    """A value as a key: a mapping by its sorted items, anything else as it is."""
    if isinstance(value, Mapping):
        return tuple(sorted(value.items()))
    return value


class Levels:
    """The store reads one node page has already made, keyed by what it asked.

    Both readers get one answer rather than a copy of it, which holds because a level is read
    and never written — every caller turns the rows into nodes and leaves them alone.
    """

    def __init__(self) -> None:
        self.asked: dict[Asked, Any] = {}

    def read[**P, T](self, method: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        """One repository read, run once per question this request asks of it."""
        key: Asked = (
            method,
            tuple(_frozen(arg) for arg in args),
            tuple(sorted((name, _frozen(arg)) for name, arg in kwargs.items())),
        )
        if key not in self.asked:
            self.asked[key] = method(*args, **kwargs)
        return self.asked[key]
