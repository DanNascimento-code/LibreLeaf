import pytest

from libreleaf.config import Settings
from libreleaf.errors import ConfigurationError, LibreLeafError
from libreleaf.gutenberg import GutenbergHarvester, parse_opds

SOURCE = "https://www.gutenberg.org/ebooks/search.opds/?query=alice"
OPDS = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <id>urn:pg:catalog</id><title>Alice results</title>
  <link rel="next" href="/ebooks/search.opds/?start_index=26&amp;query=alice" />
  <link rel="previous" href="https://evil.example/feed" />
  <entry>
    <id>https://www.gutenberg.org/ebooks/11</id>
    <title>Alice's Adventures in Wonderland</title>
    <updated>2026-01-01T00:00:00Z</updated>
    <summary>A curious child follows a rabbit.</summary>
    <author><name>Carroll, Lewis</name></author>
    <category scheme="http://purl.org/dc/terms/language" term="en" />
    <link rel="alternate" href="/ebooks/11" type="text/html" />
    <link rel="http://opds-spec.org/image/thumbnail"
      href="/cache/epub/11/pg11.cover.small.jpg" type="image/jpeg" />
    <link rel="http://opds-spec.org/acquisition/open-access"
      href="/ebooks/11.epub3.images" type="application/epub+zip" />
    <link rel="http://opds-spec.org/acquisition" href="/files/11/11-0.txt" type="text/plain" />
  </entry>
  <entry><title>Minimal entry</title><link rel="alternate" href="/ebooks/22" /></entry>
</feed>"""


class FakeClient:
    def __init__(self, xml: str = OPDS) -> None:
        self.xml = xml
        self.urls: list[str] = []
        self.closed = False

    def get_text(self, url: str) -> tuple[str, dict[str, str]]:
        self.urls.append(url)
        return self.xml, {"etag": "fixture"}

    def close(self) -> None:
        self.closed = True


def test_parse_opds_extracts_books_downloads_and_safe_pagination() -> None:
    page = parse_opds(OPDS, SOURCE)
    book = page.books[0]
    assert book.gutenberg_id == "11"
    assert book.authors == ("Carroll, Lewis",)
    assert book.languages == ("en",)
    assert book.cover_url == "https://www.gutenberg.org/cache/epub/11/pg11.cover.small.jpg"
    assert [link.media_type for link in book.downloads] == ["application/epub+zip", "text/plain"]
    assert page.next_url == (
        "https://www.gutenberg.org/ebooks/search.opds/?start_index=26&query=alice"
    )
    assert page.previous_url is None
    assert page.books[1].gutenberg_id == "22"
    assert page.books[1].title == "Minimal entry"


def test_harvester_requires_contact_and_fetches_one_page() -> None:
    with pytest.raises(ConfigurationError, match="contact"):
        GutenbergHarvester(Settings())
    client = FakeClient()
    harvester = GutenbergHarvester(
        Settings(contact_email="reader@example.com"),
        client=client,  # type: ignore[arg-type]
    )
    page = harvester.search("  alice   rabbit  ")
    assert "query=alice+rabbit" in client.urls[0]
    assert len(page.books) == 2
    harvester.close()
    assert client.closed is False


def test_harvester_accepts_only_gutenberg_feed_pagination() -> None:
    client = FakeClient()
    harvester = GutenbergHarvester(
        Settings(contact_email="reader@example.com"),
        client=client,  # type: ignore[arg-type]
    )
    safe = "https://www.gutenberg.org/ebooks/search.opds/?start_index=26"
    assert harvester.search(page_url=safe).source_url == safe
    with pytest.raises(LibreLeafError, match="Refusing"):
        harvester.search(page_url="https://evil.example/steal")
    with pytest.raises(LibreLeafError, match="Refusing"):
        harvester.search(page_url="http://www.gutenberg.org/ebooks/search.opds/")


def test_malformed_opds_is_reported() -> None:
    with pytest.raises(LibreLeafError, match="malformed"):
        parse_opds("<feed>", SOURCE)
