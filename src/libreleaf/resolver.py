import unicodedata
from typing import Any

from libreleaf.config import Settings
from libreleaf.http import JsonHttpClient
from libreleaf.isbn import first_valid_isbn13
from libreleaf.models import BookIdentity


class OpenLibraryISBNResolver:
    """Resolve either an ISBN or a title to one explicit book edition."""

    _url = "https://openlibrary.org/api/books"
    _search_url = "https://openlibrary.org/search.json"
    _search_fields = ",".join(
        (
            "key",
            "title",
            "author_name",
            "isbn",
            "cover_i",
            "first_publish_year",
            "editions",
            "editions.key",
            "editions.title",
            "editions.author_name",
            "editions.isbn",
            "editions.publisher",
            "editions.publish_date",
            "editions.cover_i",
        )
    )

    def __init__(self, settings: Settings, client: JsonHttpClient | None = None) -> None:
        contact = f"; contact={settings.contact_email}" if settings.contact_email else ""
        self._owns_client = client is None
        self._client = client or JsonHttpClient(
            user_agent=f"LibreLeaf/0.4 (ISBN resolver{contact})",
            timeout=settings.timeout,
            max_retries=settings.max_retries,
            minimum_interval=1.0,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def resolve(self, isbn13: str) -> BookIdentity | None:
        key = f"ISBN:{isbn13}"
        payload = self._client.get(
            self._url,
            params={"bibkeys": key, "jscmd": "data", "format": "json"},
        )
        raw = payload.get(key)
        if not isinstance(raw, dict):
            return None

        authors = _names(raw.get("authors"))
        publishers = _names(raw.get("publishers"))
        cover = raw.get("cover")
        cover_url = (
            str(cover.get("medium")) if isinstance(cover, dict) and cover.get("medium") else None
        )
        information_url = str(raw.get("url") or f"https://openlibrary.org/isbn/{isbn13}")
        if information_url.startswith("http://openlibrary.org"):
            information_url = information_url.replace("http://", "https://", 1)

        return BookIdentity(
            isbn13=isbn13,
            title=_clean_text(raw.get("title") or "Untitled edition"),
            authors=authors,
            publisher=publishers[0] if publishers else None,
            publish_date=_clean_text(raw.get("publish_date")) if raw.get("publish_date") else None,
            cover_url=cover_url,
            information_url=information_url,
        )

    def resolve_title(self, title: str, *, language: str | None = None) -> BookIdentity | None:
        """Select the most relevant ISBN-bearing edition for a title search."""

        params: dict[str, str | int] = {
            "title": title,
            "fields": self._search_fields,
            "limit": 5,
        }
        if language:
            params["lang"] = language
        payload = self._client.get(self._search_url, params=params)
        documents = payload.get("docs", [])
        if not isinstance(documents, list):
            return None

        for document in documents:
            if not isinstance(document, dict):
                continue
            identity = _identity_from_search_document(document)
            if identity is not None:
                return identity
        return None


def _names(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(
        _clean_text(item["name"]) for item in value if isinstance(item, dict) and item.get("name")
    )


def _identity_from_search_document(document: dict[str, Any]) -> BookIdentity | None:
    work_authors = _strings(document.get("author_name"))
    editions = document.get("editions", {})
    edition_documents = editions.get("docs", []) if isinstance(editions, dict) else []
    if isinstance(edition_documents, list):
        for edition in edition_documents:
            if not isinstance(edition, dict):
                continue
            identity = _identity_from_edition(edition, work_authors)
            if identity is not None:
                return identity

    isbn13 = first_valid_isbn13(list(_strings(document.get("isbn"))))
    if isbn13 is None:
        return None
    cover_id = document.get("cover_i")
    year = document.get("first_publish_year")
    return BookIdentity(
        isbn13=isbn13,
        title=_clean_text(document.get("title") or "Untitled edition"),
        authors=work_authors,
        publisher=None,
        publish_date=str(year) if year is not None else None,
        cover_url=_cover_url(cover_id),
        information_url=f"https://openlibrary.org/isbn/{isbn13}",
    )


def _identity_from_edition(
    edition: dict[str, Any], work_authors: tuple[str, ...]
) -> BookIdentity | None:
    isbn13 = first_valid_isbn13(list(_strings(edition.get("isbn"))))
    if isbn13 is None:
        return None
    key = str(edition.get("key") or "")
    publishers = _strings(edition.get("publisher"))
    publish_dates = _strings(edition.get("publish_date"))
    return BookIdentity(
        isbn13=isbn13,
        title=_clean_text(edition.get("title") or "Untitled edition"),
        authors=_strings(edition.get("author_name")) or work_authors,
        publisher=publishers[0] if publishers else None,
        publish_date=publish_dates[0] if publish_dates else None,
        cover_url=_cover_url(edition.get("cover_i")),
        information_url=(
            f"https://openlibrary.org{key}"
            if key.startswith("/books/")
            else f"https://openlibrary.org/isbn/{isbn13}"
        ),
    )


def _strings(value: Any) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(_clean_text(item) for item in value if item is not None and str(item).strip())
    if value is None or not str(value).strip():
        return ()
    return (_clean_text(value),)


def _cover_url(value: Any) -> str | None:
    try:
        cover_id = int(value)
    except (TypeError, ValueError):
        return None
    return f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"


def _clean_text(value: Any) -> str:
    return "".join(
        character for character in str(value) if unicodedata.category(character) not in {"Cc", "Cf"}
    ).strip()
