from datetime import UTC, datetime

from libreleaf.comparison import PriceComparisonService
from libreleaf.errors import ApiError
from libreleaf.models import BookIdentity, Offer, ProviderStatus


def make_offer(provider: str, price: int, shipping: int | None) -> Offer:
    return Offer(
        provider=provider,
        market="BR",
        external_id=provider,
        isbn13="9780132350884",
        title="Book",
        book_format="paperback",
        condition="new",
        item_price_minor=price,
        shipping_minor=shipping,
        currency="BRL",
        availability="active",
        seller=None,
        purchase_url="https://example.test",
        observed_at=datetime.now(UTC),
    )


class Provider:
    markets = ("BR",)

    def __init__(
        self,
        name: str,
        offers: list[Offer] | None = None,
        *,
        error: bool = False,
        configured: bool = True,
    ) -> None:
        self.name = name
        self.offers = offers or []
        self.error = error
        self.configured = configured
        self.closed = False

    def status(self, market: str) -> ProviderStatus:
        return ProviderStatus(
            self.name, self.markets, self.configured, "ready" if self.configured else "missing"
        )

    def find_offers(
        self,
        isbn13: str,
        market: str,
        postcode: str | None,
        book: BookIdentity | None = None,
    ) -> list[Offer]:
        if self.error:
            raise ApiError("temporary failure")
        return self.offers

    def close(self) -> None:
        self.closed = True


def test_comparison_is_partial_and_sorts_known_totals_first() -> None:
    unknown = make_offer("UnknownShipping", 5000, None)
    known = make_offer("KnownShipping", 5200, 0)
    failing = Provider("Failing", error=True)
    unavailable = Provider("Unavailable", configured=False)
    service = PriceComparisonService([Provider("Working", [unknown, known]), failing, unavailable])  # type: ignore[list-item]
    result = service.compare("9780132350884", "BR", "01000-000")
    assert [offer.provider for offer in result.offers] == ["KnownShipping", "UnknownShipping"]
    assert result.provider_statuses[0].reason == "2 matching offer(s)"
    assert "source error" in result.provider_statuses[1].reason
    assert result.provider_statuses[2].reason == "missing"
    service.close()
    assert failing.closed
