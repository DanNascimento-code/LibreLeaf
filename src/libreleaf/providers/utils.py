from collections.abc import Iterable
from typing import Any

from libreleaf.errors import InvalidIsbnError
from libreleaf.isbn import normalize_isbn13


def contains_isbn(payload: Any, isbn13: str) -> bool:
    """Check nested provider identifier data for the exact ISBN-13."""

    for value in nested_strings(payload):
        try:
            if normalize_isbn13(value) == isbn13:
                return True
        except InvalidIsbnError:
            continue
    return False


def nested_strings(payload: Any) -> Iterable[str]:
    if isinstance(payload, str):
        yield payload
    elif isinstance(payload, dict):
        for value in payload.values():
            yield from nested_strings(value)
    elif isinstance(payload, list | tuple):
        for value in payload:
            yield from nested_strings(value)


def infer_book_format(title: str, fallback: str = "unknown") -> str:
    lowered = title.casefold()
    if any(word in lowered for word in ("kindle", "ebook", "e-book")):
        return "ebook"
    if any(word in lowered for word in ("hardcover", "hardback", "capa dura")):
        return "hardcover"
    if any(word in lowered for word in ("paperback", "softcover", "brochura")):
        return "paperback"
    return fallback


def get_path(payload: Any, *names: str, default: Any = None) -> Any:
    current = payload
    for name in names:
        if not isinstance(current, dict):
            return default
        current = current.get(name)
    return default if current is None else current
