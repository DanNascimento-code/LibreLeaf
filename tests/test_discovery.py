from typing import Any

from libreleaf.config import Settings
from libreleaf.discovery import OpenLibraryDiscovery


class FakeClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.params: dict[str, Any] = {}
        self.closed = False

    def get(self, url: str, *, params: dict[str, Any]) -> dict[str, Any]:
        self.params = params
        return self.payload

    def close(self) -> None:
        self.closed = True


def test_open_library_discovery_normalizes_results() -> None:
    client = FakeClient(
        {
            "docs": [
                {
                    "key": "/works/OL1W",
                    "title": "Clean Code",
                    "author_name": ["Robert C. Martin"],
                    "first_publish_year": 2008,
                    "isbn": ["invalid", "9780132350884"],
                    "edition_count": 12,
                    "language": ["eng"],
                    "subject": ["Programming", "Craftsmanship"],
                    "cover_i": 123,
                    "ebook_access": "borrowable",
                }
            ]
        }
    )
    discovery = OpenLibraryDiscovery(Settings(), client=client)  # type: ignore[arg-type]
    books = discovery.search("clean code", limit=3, language="eng")

    assert books[0].isbn13 == "9780132350884"
    assert books[0].information_url == "https://openlibrary.org/works/OL1W"
    assert books[0].cover_url == "https://covers.openlibrary.org/b/id/123-M.jpg"
    assert client.params["q"] == "(clean code) AND language:eng"
    discovery.close()
    assert client.closed is False


def test_discovery_tolerates_missing_optional_fields() -> None:
    client = FakeClient({"docs": [{"title": "Minimal", "first_publish_year": "bad"}]})
    book = OpenLibraryDiscovery(Settings(), client=client).search("minimal")[0]  # type: ignore[arg-type]
    assert book.authors == ()
    assert book.first_publish_year is None
    assert book.isbn13 is None


def test_discovery_tolerates_malformed_docs() -> None:
    client = FakeClient({"docs": "not-a-list"})
    assert OpenLibraryDiscovery(Settings(), client=client).search("x") == []  # type: ignore[arg-type]
