from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class Book:
    """A discoverable work with one ISBN-13 candidate for edition comparison."""

    title: str
    authors: tuple[str, ...]
    isbn13: str | None
    first_publish_year: int | None
    languages: tuple[str, ...]
    subjects: tuple[str, ...]
    edition_count: int
    ebook_access: str
    cover_url: str | None
    information_url: str

    def to_record(self) -> dict[str, Any]:
        record = asdict(self)
        record["authors"] = list(self.authors)
        record["languages"] = list(self.languages)
        record["subjects"] = list(self.subjects)
        return record


@dataclass(frozen=True, slots=True)
class Offer:
    """A normalized retailer offer for one exact ISBN and market."""

    provider: str
    market: str
    external_id: str
    isbn13: str
    title: str
    book_format: str
    condition: str
    item_price_minor: int
    shipping_minor: int | None
    currency: str
    availability: str
    seller: str | None
    purchase_url: str
    observed_at: datetime

    @property
    def total_minor(self) -> int | None:
        if self.shipping_minor is None:
            return None
        return self.item_price_minor + self.shipping_minor

    def to_record(self) -> dict[str, Any]:
        record = asdict(self)
        record["item_price"] = format_money(self.item_price_minor)
        record["shipping"] = (
            format_money(self.shipping_minor) if self.shipping_minor is not None else None
        )
        record["known_total"] = (
            format_money(self.total_minor) if self.total_minor is not None else None
        )
        record["observed_at"] = self.observed_at.isoformat()
        del record["item_price_minor"]
        del record["shipping_minor"]
        return record


@dataclass(frozen=True, slots=True)
class ProviderStatus:
    name: str
    markets: tuple[str, ...]
    configured: bool
    reason: str


@dataclass(frozen=True, slots=True)
class BookIdentity:
    """Edition metadata resolved directly from an ISBN."""

    isbn13: str
    title: str
    authors: tuple[str, ...]
    publisher: str | None
    publish_date: str | None
    cover_url: str | None
    information_url: str


@dataclass(frozen=True, slots=True)
class StoreSearchLink:
    """A human-operated store search, deliberately not represented as a verified offer."""

    name: str
    market: str
    url: str


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    isbn13: str
    market: str
    offers: tuple[Offer, ...]
    provider_statuses: tuple[ProviderStatus, ...]
    compared_at: datetime
    book: BookIdentity | None = None
    store_searches: tuple[StoreSearchLink, ...] = ()

    @classmethod
    def create(
        cls,
        isbn13: str,
        market: str,
        offers: list[Offer],
        provider_statuses: list[ProviderStatus],
        book: BookIdentity | None = None,
        store_searches: tuple[StoreSearchLink, ...] = (),
    ) -> "ComparisonResult":
        return cls(
            isbn13=isbn13,
            market=market,
            offers=tuple(offers),
            provider_statuses=tuple(provider_statuses),
            compared_at=datetime.now(UTC),
            book=book,
            store_searches=store_searches,
        )


@dataclass(frozen=True, slots=True)
class DownloadLink:
    media_type: str
    url: str

    def to_record(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PublicDomainBook:
    """A Project Gutenberg catalog entry collected from its permitted OPDS feed."""

    gutenberg_id: str
    title: str
    authors: tuple[str, ...]
    languages: tuple[str, ...]
    summary: str | None
    published_at: str | None
    information_url: str
    cover_url: str | None
    downloads: tuple[DownloadLink, ...]

    def to_record(self) -> dict[str, Any]:
        record = asdict(self)
        record["authors"] = list(self.authors)
        record["languages"] = list(self.languages)
        record["downloads"] = [link.to_record() for link in self.downloads]
        return record


@dataclass(frozen=True, slots=True)
class HarvestPage:
    books: tuple[PublicDomainBook, ...]
    source_url: str
    next_url: str | None
    previous_url: str | None
    fetched_at: datetime


def decimal_to_minor(value: str | int | float | Decimal) -> int:
    """Convert a provider decimal amount to integer minor units without float drift."""

    amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(amount * 100)


def format_money(value: int) -> str:
    return f"{value // 100}.{value % 100:02d}"
