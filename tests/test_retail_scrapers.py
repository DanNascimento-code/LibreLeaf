from typing import Any

from libreleaf.config import Settings
from libreleaf.models import BookIdentity
from libreleaf.providers.retail_scrapers import (
    LibrosRefProvider,
    LivrariaDaVilaProvider,
    ThriftBooksProvider,
)


class TextClient:
    def __init__(self, html: str) -> None:
        self.html = html
        self.calls: list[str] = []

    def get_text(
        self, url: str, *, params: Any = None, headers: Any = None
    ) -> tuple[str, dict[str, str]]:
        self.calls.append(url)
        return self.html, {}

    def close(self) -> None:
        pass


def identity(isbn: str, title: str = "Book") -> BookIdentity:
    return BookIdentity(isbn, title, ("Author",), None, None, None, "https://example.test")


def test_livraria_da_vila_reads_exact_product_jsonld() -> None:
    html = """
    <script type="application/ld+json">
    {"@type":"ItemList","itemListElement":[{"@type":"ListItem","item":{
      "@type":"Product","@id":"https://www.livrariadavila.com.br/book/p",
      "name":"A Book","mpn":"9780132350884","sku":"123",
      "offers":{"@type":"AggregateOffer","lowPrice":64.9,"priceCurrency":"BRL"}}}]}
    </script>
    """
    provider = LivrariaDaVilaProvider(Settings(), client=TextClient(html))  # type: ignore[arg-type]
    offers = provider.find_offers("9780132350884", "BR", None, identity("9780132350884"))
    assert [(offer.provider, offer.item_price_minor) for offer in offers] == [
        ("Livraria da Vila", 6490)
    ]


def test_thriftbooks_keeps_only_exact_isbn_offers() -> None:
    html = """
    <html><head><link rel="canonical" href="https://www.thriftbooks.com/w/book/1"></head>
    <body><script type="application/ld+json">
    {"@type":"Book","offers":{"@type":"Offer","gtin13":"9780132350884",
    "sku":"copy-1","price":5.59,"priceCurrency":"USD",
    "itemCondition":"http://schema.org/UsedCondition"}}
    </script><script type="application/ld+json">
    {"@type":"Book","offers":{"@type":"Offer","gtin13":"9781491950357",
    "sku":"wrong","price":1,"priceCurrency":"USD"}}
    </script></body></html>
    """
    provider = ThriftBooksProvider(Settings(), client=TextClient(html))  # type: ignore[arg-type]
    offers = provider.find_offers("9780132350884", "US", None, identity("9780132350884"))
    assert len(offers) == 1
    assert offers[0].condition == "used"
    assert offers[0].item_price_minor == 559


def test_argentine_store_parses_localized_price_and_exact_isbn() -> None:
    librosref_html = "<h1>Babel</h1><p>$ 49.900</p><p>ISBN: 9788419266286.</p>"
    book = identity("9788419266286", "Babel")
    librosref = LibrosRefProvider(
        Settings(),
        client=TextClient(librosref_html),  # type: ignore[arg-type]
    )
    assert librosref.find_offers(book.isbn13, "AR", None, book)[0].item_price_minor == 4_990_000
