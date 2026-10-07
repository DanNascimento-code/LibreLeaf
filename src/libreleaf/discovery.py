from typing import Any

from libreleaf.config import Settings
from libreleaf.http import JsonHttpClient
from libreleaf.isbn import first_valid_isbn13
from libreleaf.models import Book

OPEN_LIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"
SEARCH_FIELDS = ",".join(
    (
        "key",
        "title",
        "author_name",
        "first_publish_year",
        "isbn",
        "edition_count",
        "language",
        "subject",
        "cover_i",
        "ebook_access",
    )
)


class OpenLibraryDiscovery:
    """Discover books through Open Library's documented Search API."""

    def __init__(self, settings: Settings, client: JsonHttpClient | None = None) -> None:
        contact = f"; contact={settings.contact_email}" if settings.contact_email else ""
        self._owns_client = client is None
        self._client = client or JsonHttpClient(
            user_agent=f"LibreLeaf/0.4 ({'identified' if contact else 'educational'}{contact})",
            timeout=settings.timeout,
            max_retries=settings.max_retries,
            minimum_interval=0.34 if settings.contact_email else 1.0,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def search(self, query: str, *, limit: int = 10, language: str | None = None) -> list[Book]:
        effective_query = f"({query}) AND language:{language}" if language else query
        payload = self._client.get(
            OPEN_LIBRARY_SEARCH_URL,
            params={"q": effective_query, "fields": SEARCH_FIELDS, "limit": limit},
        )
        docs = payload.get("docs", [])
        if not isinstance(docs, list):
            return []
        return [_parse_book(doc) for doc in docs if isinstance(doc, dict)]


def _parse_book(doc: dict[str, Any]) -> Book:
    key = str(doc.get("key", ""))
    cover_id = doc.get("cover_i")
    isbns = [str(value) for value in _as_list(doc.get("isbn"))]
    return Book(
        title=str(doc.get("title") or "Untitled"),
        authors=tuple(str(value) for value in _as_list(doc.get("author_name"))),
        isbn13=first_valid_isbn13(isbns),
        first_publish_year=_optional_int(doc.get("first_publish_year")),
        languages=tuple(str(value) for value in _as_list(doc.get("language"))[:8]),
        subjects=tuple(str(value) for value in _as_list(doc.get("subject"))[:12]),
        edition_count=_optional_int(doc.get("edition_count")) or 0,
        ebook_access=str(doc.get("ebook_access") or "unknown"),
        cover_url=(f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg" if cover_id else None),
        information_url=f"https://openlibrary.org{key}" if key.startswith("/") else "",
    )


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
