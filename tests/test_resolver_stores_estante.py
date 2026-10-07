from typing import Any

from libreleaf.config import Settings
from libreleaf.models import BookIdentity
from libreleaf.providers.estante_virtual import EstanteVirtualProvider
from libreleaf.resolver import OpenLibraryISBNResolver

ISBN = "9780132350884"


class JsonClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def get(self, url: str, *, params: Any = None) -> dict[str, Any]:
        return self.payload

    def close(self) -> None:
        pass


class TextClient:
    def __init__(self, pages: list[str]) -> None:
        self.pages = list(pages)
        self.calls: list[str] = []

    def get_text(
        self, url: str, *, params: Any = None, headers: Any = None
    ) -> tuple[str, dict[str, str]]:
        self.calls.append(url)
        return self.pages.pop(0), {}

    def close(self) -> None:
        pass


def identity() -> BookIdentity:
    return BookIdentity(
        isbn13=ISBN,
        title="Clean Code",
        authors=("Robert C. Martin",),
        publisher="Prentice Hall",
        publish_date="2008",
        cover_url=None,
        information_url="https://openlibrary.org/books/OL1M/Clean_Code",
    )


def test_open_library_resolves_isbn_without_retailer_credentials() -> None:
    payload = {
        f"ISBN:{ISBN}": {
            "title": "Clean Code",
            "authors": [{"name": "Robert C. Martin"}],
            "publishers": [{"name": "Prentice Hall"}],
            "publish_date": "2008",
            "url": "http://openlibrary.org/books/OL1M/Clean_Code",
            "cover": {"medium": "https://covers.example/clean.jpg"},
        }
    }
    resolver = OpenLibraryISBNResolver(Settings(), client=JsonClient(payload))  # type: ignore[arg-type]
    book = resolver.resolve(ISBN)
    assert book is not None
    assert book.title == "Clean Code"
    assert book.authors == ("Robert C. Martin",)
    assert book.information_url.startswith("https://")


def test_open_library_returns_none_for_unknown_isbn() -> None:
    resolver = OpenLibraryISBNResolver(Settings(), client=JsonClient({}))  # type: ignore[arg-type]
    assert resolver.resolve(ISBN) is None


def test_open_library_resolves_title_to_best_isbn_bearing_edition() -> None:
    payload = {
        "docs": [
            {
                "title": "Clean Code",
                "author_name": ["Robert C. Martin"],
                "editions": {
                    "docs": [
                        {
                            "key": "/books/OL1M",
                            "title": "\u0098Clean \u009cCode",
                            "isbn": [ISBN],
                            "publisher": ["Prentice Hall"],
                            "publish_date": ["2008"],
                            "cover_i": 123,
                        }
                    ]
                },
            }
        ]
    }
    resolver = OpenLibraryISBNResolver(Settings(), client=JsonClient(payload))  # type: ignore[arg-type]
    book = resolver.resolve_title("Clean Code", language="en")
    assert book is not None
    assert book.isbn13 == ISBN
    assert book.title == "Clean Code"
    assert book.authors == ("Robert C. Martin",)
    assert book.publisher == "Prentice Hall"
    assert book.information_url == "https://openlibrary.org/books/OL1M"


def test_open_library_title_without_isbn_returns_none() -> None:
    resolver = OpenLibraryISBNResolver(
        Settings(), client=JsonClient({"docs": [{"title": "Unknown"}]})
    )  # type: ignore[arg-type]
    assert resolver.resolve_title("Unknown") is None


def test_estante_virtual_accepts_only_exact_isbn_and_parses_starting_prices() -> None:
    search = """
    <article class="product-item"><a href="/livro/clean-code-ABC"><h2>Clean Code</h2></a></article>
    """
    detail = """
    <main><h1>Clean Code</h1><p>ISBN: 9780132350884</p>
    <p>Usados A partir de R$ 20,00 + Frete</p>
    <p>Novos A partir de R$ 32,50 + Frete</p></main>
    """
    client = TextClient([search, detail])
    provider = EstanteVirtualProvider(Settings(), client=client)  # type: ignore[arg-type]
    offers = provider.find_offers(ISBN, "BR", None, identity())
    assert [(offer.condition, offer.item_price_minor) for offer in offers] == [
        ("used", 2000),
        ("new", 3250),
    ]
    assert all(offer.shipping_minor is None for offer in offers)
    assert provider.status("BR").configured


def test_estante_virtual_title_search_discovers_and_reuses_listed_isbn() -> None:
    search = """
    <article class="product-item"><a href="/livro/clean-code-ABC"><h2>Clean Code</h2></a></article>
    """
    detail = """
    <main><h1>Clean Code</h1><p>ISBN: 9780132350884</p>
    <p>Usados A partir de R$ 20,00 + Frete</p></main>
    """
    client = TextClient([search, detail])
    provider = EstanteVirtualProvider(Settings(), client=client)  # type: ignore[arg-type]
    assert provider.resolve_title_isbn("Clean Code") == ISBN
    offers = provider.find_offers(ISBN, "BR", None, identity())
    assert len(client.calls) == 2
    assert offers[0].item_price_minor == 2000


def test_estante_virtual_rejects_similar_title_with_different_isbn() -> None:
    search = """
    <article class="product-item"><a href="/livro/clean-code-ABC"><h2>Clean Code</h2></a></article>
    """
    detail = (
        "<main><h1>Clean Code</h1><p>ISBN: 9781491950357</p>"
        "<p>Novos A partir de R$ 10,00</p></main>"
    )
    provider = EstanteVirtualProvider(Settings(), client=TextClient([search, detail]))  # type: ignore[arg-type]
    assert provider.find_offers(ISBN, "BR", None, identity()) == []
