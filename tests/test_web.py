import asyncio
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

import libreleaf.web as web
from libreleaf.config import Settings
from libreleaf.models import (
    Book,
    BookIdentity,
    ComparisonResult,
    DownloadLink,
    HarvestPage,
    Offer,
    ProviderStatus,
    PublicDomainBook,
    StoreSearchLink,
)


def sample_book() -> Book:
    return Book(
        title="Dom Casmurro",
        authors=("Machado de Assis",),
        isbn13="9788500507007",
        first_publish_year=1900,
        languages=("por",),
        subjects=("Brazilian fiction",),
        edition_count=20,
        ebook_access="borrowable",
        cover_url="https://covers.example/dom.jpg",
        information_url="https://openlibrary.org/works/OL1W",
    )


def sample_offer() -> Offer:
    return Offer(
        provider="Store",
        market="BR",
        external_id="store-1",
        isbn13="9780132350884",
        title="Clean Code Paperback",
        book_format="paperback",
        condition="new",
        item_price_minor=10000,
        shipping_minor=0,
        currency="BRL",
        availability="active",
        seller="Books",
        purchase_url="https://store.example/book",
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def sample_page() -> HarvestPage:
    book = PublicDomainBook(
        gutenberg_id="11",
        title="Alice's Adventures in Wonderland",
        authors=("Carroll, Lewis",),
        languages=("en",),
        summary="A curious child follows a rabbit.",
        published_at="2026-01-01T00:00:00Z",
        information_url="https://www.gutenberg.org/ebooks/11",
        cover_url=None,
        downloads=(DownloadLink("application/epub+zip", "https://example.test/alice.epub"),),
    )
    return HarvestPage(
        books=(book,),
        source_url="https://www.gutenberg.org/ebooks/search.opds/?query=alice",
        next_url="https://www.gutenberg.org/ebooks/search.opds/?start_index=26",
        previous_url=None,
        fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FastAPI:
    monkeypatch.setattr(web, "DATABASE_PATH", tmp_path / "web.db")

    class Discovery:
        def __init__(self, settings: Settings) -> None:
            pass

        def search(self, query: str, *, limit: int, language: str | None) -> list[Book]:
            return [sample_book()]

        def close(self) -> None:
            pass

    class Comparison:
        def __init__(self, providers: object) -> None:
            pass

        def compare(
            self,
            isbn13: str,
            market: str,
            postcode: str | None,
            *,
            book: BookIdentity | None = None,
            store_searches: tuple[StoreSearchLink, ...] = (),
        ) -> ComparisonResult:
            return ComparisonResult.create(
                isbn13,
                market,
                [sample_offer()],
                [ProviderStatus("Store", (market,), True, "1 matching offer(s)")],
                book=book,
                store_searches=store_searches,
            )

        def close(self) -> None:
            pass

    class Harvester:
        def __init__(self, settings: Settings) -> None:
            pass

        def search(self, query: str, *, page_url: str | None = None) -> HarvestPage:
            return sample_page()

        def close(self) -> None:
            pass

    class Resolver:
        def __init__(self, settings: Settings) -> None:
            pass

        def resolve(self, isbn13: str) -> BookIdentity:
            return BookIdentity(
                isbn13=isbn13,
                title="Clean Code",
                authors=("Robert C. Martin",),
                publisher="Prentice Hall",
                publish_date="2008",
                cover_url=None,
                information_url="https://openlibrary.org/isbn/9780132350884",
            )

        def resolve_title(self, title: str, *, language: str | None = None) -> BookIdentity:
            return BookIdentity(
                isbn13="9780132350884",
                title="Clean Code",
                authors=("Robert C. Martin",),
                publisher="Prentice Hall",
                publish_date="2008",
                cover_url=None,
                information_url="https://openlibrary.org/isbn/9780132350884",
            )

        def close(self) -> None:
            pass

    monkeypatch.setattr(web, "OpenLibraryDiscovery", Discovery)
    monkeypatch.setattr(web, "PriceComparisonService", Comparison)
    monkeypatch.setattr(web, "GutenbergHarvester", Harvester)
    monkeypatch.setattr(web, "OpenLibraryISBNResolver", Resolver)
    monkeypatch.setattr(web, "_providers", lambda settings: [])
    app = web.create_app(Settings(contact_email="reader@example.com"))
    return app


def test_home_architecture_health_and_security_headers(client: FastAPI) -> None:
    home = _get(client, "/")
    assert home.status_code == 200
    assert "Find the book" in home.text
    assert 'action="http://testserver/compare"' in home.text
    assert "ISBN preferred · or book title" in home.text
    assert "Why ISBN?" in home.text
    assert "Find and compare" in home.text
    assert '<html lang="en" data-theme="dark">' in home.text
    assert "/static/theme.js" in home.text
    assert "Switch color theme" in home.text
    assert "frame-ancestors 'none'" in home.headers["content-security-policy"]
    assert "From a search to the right edition" in _get(client, "/architecture").text
    assert "credentials" not in home.text.lower()
    assert _get(client, "/api/health").json()["status"] == "ok"


def test_discovery_route_renders_normalized_book(client: FastAPI) -> None:
    empty = _get(client, "/discover")
    assert empty.status_code == 200
    response = _get(client, "/discover?q=Machado&market=BR&language=por")
    assert response.status_code == 200
    assert "Dom Casmurro" in response.text
    assert "9788500507007" in response.text


def test_comparison_route_validates_and_renders_offer(client: FastAPI) -> None:
    response = _get(client, "/compare?isbn=9780132350884&market=BR&postcode=01001-000")
    assert response.status_code == 200
    assert "R$ 100.00" in response.text
    assert "Clean Code" in response.text
    assert "Store" in response.text
    assert "Search other bookstores" not in response.text
    assert "Automatic sources" not in response.text
    assert "Credentials needed" not in response.text
    assert "LIBRELEAF_" not in response.text
    invalid = _get(client, "/compare?isbn=bad&market=XX")
    assert invalid.status_code == 200
    assert "Invalid ISBN" in invalid.text


def test_language_switcher_persists_portuguese_and_spanish(client: FastAPI) -> None:
    async def request() -> tuple[httpx.Response, httpx.Response]:
        transport = httpx.ASGITransport(app=client)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver", follow_redirects=True
        ) as browser:
            portuguese = await browser.get("/language/pt-BR?next=/")
            spanish = await browser.get("/language/es-419?next=/compare")
            return portuguese, spanish

    portuguese, spanish = asyncio.run(request())
    assert '<html lang="pt-BR"' in portuguese.text
    assert "Encontre o livro" in portuguese.text
    assert '<html lang="es-419"' in spanish.text
    assert "Encuentra la edición" in spanish.text
    assert 'aria-current="true">ES</a>' in spanish.text


def test_comparison_route_resolves_title_before_comparing(client: FastAPI) -> None:
    response = _get(client, "/compare?q=Clean%20Code&market=BR")
    assert response.status_code == 200
    assert "Title matched to" in response.text
    assert "9780132350884" in response.text
    assert "Clean Code" in response.text
    assert "R$ 100.00" in response.text


def test_free_books_renders_explicit_next_page(client: FastAPI) -> None:
    assert _get(client, "/free-books").status_code == 200
    response = _get(client, "/free-books?q=alice")
    assert response.status_code == 200
    assert "Alice&#39;s Adventures" in response.text
    assert "Show more books" in response.text


def test_provider_api_uses_safe_market_default(client: FastAPI) -> None:
    response = _get(client, "/api/providers?market=XX")
    assert response.status_code == 200
    assert response.json() == {"market": "BR", "providers": []}


def _get(app: FastAPI, url: str) -> httpx.Response:
    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(url)

    return asyncio.run(request())
