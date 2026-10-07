import json
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from bs4 import BeautifulSoup

from libreleaf.config import Settings
from libreleaf.http import JsonHttpClient
from libreleaf.models import BookIdentity, Offer, ProviderStatus, decimal_to_minor


class _HtmlProvider:
    markets: tuple[str, ...]

    def __init__(self, settings: Settings, client: JsonHttpClient | None = None) -> None:
        contact = settings.contact_email or "contact-not-configured"
        self._owns_client = client is None
        self._client = client or JsonHttpClient(
            user_agent=f"LibreLeafBot/0.5.0 (exact-ISBN price comparison; {contact})",
            timeout=settings.timeout,
            max_retries=settings.max_retries,
            minimum_interval=1.5,
        )

    def status(self, market: str) -> ProviderStatus:
        configured = market in self.markets
        return ProviderStatus(
            self.name,
            self.markets,
            configured,
            "public exact-ISBN price scraper ready" if configured else "market not supported",
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _get(self, url: str, language: str) -> tuple[str, str]:
        html, _headers = self._client.get_text(
            url,
            headers={"Accept": "text/html", "Accept-Language": language},
        )
        return html, url


class LivrariaDaVilaProvider(_HtmlProvider):
    name = "Livraria da Vila"
    markets = ("BR",)
    _origin = "https://www.livrariadavila.com.br"

    def find_offers(
        self,
        isbn13: str,
        market: str,
        postcode: str | None,
        book: BookIdentity | None = None,
    ) -> list[Offer]:
        if market != "BR":
            return []
        search_url = f"{self._origin}/{quote(isbn13)}"
        html, _url = self._get(search_url, "pt-BR,pt;q=0.9")
        soup = BeautifulSoup(html, "html.parser")
        for product in _jsonld_products(soup):
            if str(product.get("mpn", "")) != isbn13:
                continue
            offers = product.get("offers")
            if not isinstance(offers, dict):
                continue
            amount = offers.get("lowPrice") or offers.get("price")
            currency = str(offers.get("priceCurrency") or "BRL")
            purchase_url = str(product.get("@id") or search_url)
            if amount is None or not purchase_url.startswith(self._origin):
                continue
            return [
                _offer(
                    provider=self.name,
                    market=market,
                    external_id=str(product.get("sku") or isbn13),
                    isbn13=isbn13,
                    title=str(product.get("name") or (book.title if book else isbn13)),
                    price=amount,
                    currency=currency,
                    condition="new",
                    book_format="unknown",
                    seller="Livraria da Vila",
                    purchase_url=purchase_url,
                )
            ]
        return []


class ThriftBooksProvider(_HtmlProvider):
    name = "ThriftBooks"
    markets = ("US",)
    _origin = "https://www.thriftbooks.com"

    def find_offers(
        self,
        isbn13: str,
        market: str,
        postcode: str | None,
        book: BookIdentity | None = None,
    ) -> list[Offer]:
        if market != "US":
            return []
        search_url = f"{self._origin}/browse/?b.search={quote(isbn13)}"
        html, _url = self._get(search_url, "en-US,en;q=0.9")
        soup = BeautifulSoup(html, "html.parser")
        title = _page_title(soup, book, isbn13)
        results: list[Offer] = []
        seen: set[str] = set()
        for product in _jsonld_products(soup):
            raw_offers = product.get("offers")
            offer_items = raw_offers if isinstance(raw_offers, list) else [raw_offers]
            for raw_offer in offer_items:
                if not isinstance(raw_offer, dict) or str(raw_offer.get("gtin13", "")) != isbn13:
                    continue
                sku = str(raw_offer.get("sku") or "")
                amount = raw_offer.get("price")
                if not sku or sku in seen or amount is None:
                    continue
                seen.add(sku)
                condition_url = str(raw_offer.get("itemCondition") or "").casefold()
                condition = "used" if "used" in condition_url else "new"
                results.append(
                    _offer(
                        provider=self.name,
                        market=market,
                        external_id=sku,
                        isbn13=isbn13,
                        title=title,
                        price=amount,
                        currency=str(raw_offer.get("priceCurrency") or "USD"),
                        condition=condition,
                        book_format="unknown",
                        seller="ThriftBooks",
                        purchase_url=str(soup.find("link", rel="canonical").get("href"))
                        if soup.find("link", rel="canonical")
                        else search_url,
                    )
                )
        return results


class LibrosRefProvider(_HtmlProvider):
    name = "LibrosRef"
    markets = ("AR",)
    _origin = "https://librosref.com"
    _price = re.compile(r"\$\s*([0-9.]+(?:,[0-9]{2})?)")

    def find_offers(
        self,
        isbn13: str,
        market: str,
        postcode: str | None,
        book: BookIdentity | None = None,
    ) -> list[Offer]:
        if market != "AR":
            return []
        url = f"{self._origin}/productos/{quote(isbn13)}/"
        html, _url = self._get(url, "es-AR,es;q=0.9")
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
        if not re.search(rf"ISBN\s*:\s*{re.escape(isbn13)}", text, re.IGNORECASE):
            return []
        match = self._price.search(text)
        if not match:
            return []
        return [
            _offer(
                provider=self.name,
                market=market,
                external_id=isbn13,
                isbn13=isbn13,
                title=_page_title(soup, book, isbn13),
                price=_localized_decimal(match.group(1)),
                currency="ARS",
                condition="new",
                book_format="unknown",
                seller="Librería LibrosRef",
                purchase_url=url,
            )
        ]


def _jsonld_products(soup: BeautifulSoup) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.string or script.get_text())
        except (json.JSONDecodeError, TypeError):
            continue
        _collect_products(payload, products)
    return products


def _collect_products(payload: Any, products: list[dict[str, Any]]) -> None:
    if isinstance(payload, list):
        for item in payload:
            _collect_products(item, products)
        return
    if not isinstance(payload, dict):
        return
    item_type = payload.get("@type")
    if item_type in {"Product", "Book"} or (
        isinstance(item_type, list) and {"Product", "Book"}.intersection(item_type)
    ):
        products.append(payload)
    for key in ("item", "itemListElement", "@graph"):
        if key in payload:
            _collect_products(payload[key], products)


def _page_title(soup: BeautifulSoup, book: BookIdentity | None, isbn13: str) -> str:
    heading = soup.find("h1")
    if heading:
        title = heading.get_text(" ", strip=True)
        if title and isbn13 not in title:
            return title
    if book:
        return book.title
    return f"ISBN {isbn13}"


def _localized_decimal(raw: str) -> str:
    return raw.replace(".", "").replace(",", ".")


def _offer(
    *,
    provider: str,
    market: str,
    external_id: str,
    isbn13: str,
    title: str,
    price: object,
    currency: str,
    condition: str,
    book_format: str,
    seller: str,
    purchase_url: str,
) -> Offer:
    return Offer(
        provider=provider,
        market=market,
        external_id=external_id,
        isbn13=isbn13,
        title=title,
        book_format=book_format,
        condition=condition,
        item_price_minor=decimal_to_minor(str(price)),
        shipping_minor=None,
        currency=currency,
        availability="listed; verify stock",
        seller=seller,
        purchase_url=purchase_url,
        observed_at=datetime.now(UTC),
    )
