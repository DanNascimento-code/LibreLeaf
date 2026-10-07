import re
import unicodedata
from datetime import UTC, datetime
from difflib import SequenceMatcher
from urllib.parse import quote, urljoin, urlparse

from bs4 import BeautifulSoup

from libreleaf.config import Settings
from libreleaf.errors import InvalidIsbnError
from libreleaf.http import JsonHttpClient
from libreleaf.isbn import normalize_isbn13
from libreleaf.models import BookIdentity, Offer, ProviderStatus, decimal_to_minor

ISBN_PATTERN = re.compile(r"ISBN:\s*([0-9Xx-]{10,17})", re.IGNORECASE)
PRICE_PATTERN = re.compile(
    r"(Usados|Novos)\s+A partir de\s+R\$\s*([0-9.]+,[0-9]{2})",
    re.IGNORECASE,
)


class EstanteVirtualProvider:
    """Narrow, paced HTML scraper that accepts only product pages with the exact ISBN."""

    name = "Estante Virtual"
    markets = ("BR",)
    _origin = "https://www.estantevirtual.com.br"

    def __init__(self, settings: Settings, client: JsonHttpClient | None = None) -> None:
        contact = settings.contact_email or "contact-not-configured"
        self._owns_client = client is None
        self._detail_cache: dict[str, tuple[str, str]] = {}
        self._client = client or JsonHttpClient(
            user_agent=f"LibreLeafBot/0.4 (exact-ISBN comparison; {contact})",
            timeout=settings.timeout,
            max_retries=settings.max_retries,
            minimum_interval=1.5,
        )

    def status(self, market: str) -> ProviderStatus:
        configured = market in self.markets
        reason = "zero-key exact-ISBN scraper ready" if configured else "Brazil only"
        return ProviderStatus(self.name, self.markets, configured, reason)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def find_offers(
        self,
        isbn13: str,
        market: str,
        postcode: str | None,
        book: BookIdentity | None = None,
    ) -> list[Offer]:
        if market != "BR":
            return []
        cached = self._detail_cache.pop(isbn13, None)
        if cached is not None:
            detail_html, candidate_url = cached
            return self._parse_detail(detail_html, candidate_url, isbn13, market)
        query = book.title if book else isbn13
        search_url = f"{self._origin}/busca/{quote(_slug(query))}"
        html, _headers = self._client.get_text(
            search_url,
            headers={"Accept": "text/html", "Accept-Language": "pt-BR,pt;q=0.9"},
        )
        candidates = self._candidate_urls(html, query)
        offers: list[Offer] = []
        for candidate_url in candidates[:4]:
            detail_html, _detail_headers = self._client.get_text(
                candidate_url,
                headers={"Accept": "text/html", "Accept-Language": "pt-BR,pt;q=0.9"},
            )
            offers.extend(self._parse_detail(detail_html, candidate_url, isbn13, market))
            if offers:
                break
        return offers

    def resolve_title_isbn(self, title: str) -> str | None:
        """Find an ISBN on a currently listed, title-matching product page."""

        search_url = f"{self._origin}/busca/{quote(_slug(title))}"
        html, _headers = self._client.get_text(
            search_url,
            headers={"Accept": "text/html", "Accept-Language": "pt-BR,pt;q=0.9"},
        )
        for candidate_url in self._candidate_urls(html, title)[:4]:
            detail_html, _detail_headers = self._client.get_text(
                candidate_url,
                headers={"Accept": "text/html", "Accept-Language": "pt-BR,pt;q=0.9"},
            )
            for raw_isbn in ISBN_PATTERN.findall(
                BeautifulSoup(detail_html, "html.parser").get_text(" ", strip=True)
            ):
                try:
                    isbn13 = normalize_isbn13(raw_isbn)
                except InvalidIsbnError:
                    continue
                self._detail_cache[isbn13] = (detail_html, candidate_url)
                return isbn13
        return None

    def _candidate_urls(self, html: str, expected_title: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        candidates: list[tuple[float, str]] = []
        seen: set[str] = set()
        for card in soup.select(".product-item"):
            heading = card.find("h2")
            link = card.find("a", href=True)
            if not heading or not link:
                continue
            url = urljoin(self._origin, str(link["href"]))
            parsed = urlparse(url)
            if parsed.scheme != "https" or parsed.netloc != "www.estantevirtual.com.br":
                continue
            score = SequenceMatcher(
                None, _comparable(heading.get_text()), _comparable(expected_title)
            ).ratio()
            if score < 0.58 or url in seen:
                continue
            seen.add(url)
            candidates.append((score, url))
        candidates.sort(reverse=True)
        return [url for _score, url in candidates]

    def _parse_detail(self, html: str, url: str, isbn13: str, market: str) -> list[Offer]:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
        identifiers = {re.sub(r"\D", "", match) for match in ISBN_PATTERN.findall(text)}
        if isbn13 not in identifiers:
            return []

        heading = soup.find("h1") or soup.find("h2")
        title = heading.get_text(" ", strip=True) if heading else f"ISBN {isbn13}"
        observed_at = datetime.now(UTC)
        external_id = url.rstrip("/").rsplit("/", 1)[-1]
        offers: list[Offer] = []
        for label, amount in PRICE_PATTERN.findall(text):
            condition = "used" if label.lower().startswith("usad") else "new"
            offers.append(
                Offer(
                    provider=self.name,
                    market=market,
                    external_id=f"{external_id}-{condition}",
                    isbn13=isbn13,
                    title=title,
                    book_format="unknown",
                    condition=condition,
                    item_price_minor=decimal_to_minor(amount.replace(".", "").replace(",", ".")),
                    shipping_minor=None,
                    currency="BRL",
                    availability="starting price; verify stock",
                    seller="Estante Virtual marketplace",
                    purchase_url=url,
                    observed_at=observed_at,
                )
            )
        return offers


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")


def _comparable(value: str) -> str:
    return _slug(value).replace("-", " ")
