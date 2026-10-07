import re

from libreleaf.errors import InvalidIsbnError


def normalize_isbn13(raw: str) -> str:
    """Return a validated ISBN-13, converting a valid ISBN-10 when needed."""

    compact = re.sub(r"[^0-9Xx]", "", raw)
    if len(compact) == 10:
        if not _valid_isbn10(compact):
            raise InvalidIsbnError(f"Invalid ISBN-10 checksum: {raw}")
        compact = _isbn10_to_13(compact)
    if len(compact) != 13 or not compact.isdigit() or not _valid_isbn13(compact):
        raise InvalidIsbnError(f"Invalid ISBN-13: {raw}")
    return compact


def first_valid_isbn13(values: list[str]) -> str | None:
    for value in values:
        try:
            return normalize_isbn13(value)
        except InvalidIsbnError:
            continue
    return None


def _valid_isbn10(value: str) -> bool:
    if not re.fullmatch(r"\d{9}[\dXx]", value):
        return False
    total = sum((10 - index) * int(char) for index, char in enumerate(value[:9]))
    check = 10 if value[-1].upper() == "X" else int(value[-1])
    return (total + check) % 11 == 0


def _valid_isbn13(value: str) -> bool:
    total = sum(int(char) * (1 if index % 2 == 0 else 3) for index, char in enumerate(value))
    return total % 10 == 0


def _isbn10_to_13(value: str) -> str:
    prefix = f"978{value[:9]}"
    subtotal = sum(int(char) * (1 if index % 2 == 0 else 3) for index, char in enumerate(prefix))
    return f"{prefix}{(-subtotal) % 10}"
