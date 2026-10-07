import logging

from libreleaf.errors import ApiError
from libreleaf.models import BookIdentity, ComparisonResult, ProviderStatus, StoreSearchLink
from libreleaf.providers.base import PriceProvider

LOGGER = logging.getLogger(__name__)


class PriceComparisonService:
    """Run independent providers and preserve partial results when one source fails."""

    def __init__(self, providers: list[PriceProvider]) -> None:
        self._providers = providers

    def close(self) -> None:
        for provider in self._providers:
            provider.close()

    def compare(
        self,
        isbn13: str,
        market: str,
        postcode: str | None = None,
        book: BookIdentity | None = None,
        store_searches: tuple[StoreSearchLink, ...] = (),
    ) -> ComparisonResult:
        offers = []
        statuses: list[ProviderStatus] = []
        for provider in self._providers:
            status = provider.status(market)
            if market not in provider.markets:
                continue
            if not status.configured:
                statuses.append(status)
                continue
            try:
                provider_offers = provider.find_offers(isbn13, market, postcode, book)
            except ApiError as error:
                LOGGER.warning("%s failed: %s", provider.name, error)
                statuses.append(
                    ProviderStatus(provider.name, provider.markets, True, f"source error: {error}")
                )
                continue
            offers.extend(provider_offers)
            suffix = " · zero-key scraper" if "zero-key" in status.reason else ""
            statuses.append(
                ProviderStatus(
                    provider.name,
                    provider.markets,
                    True,
                    f"{len(provider_offers)} matching offer(s){suffix}",
                )
            )
        offers.sort(
            key=lambda offer: (
                offer.currency,
                offer.total_minor is None,
                offer.total_minor or offer.item_price_minor,
            )
        )
        return ComparisonResult.create(
            isbn13,
            market,
            offers,
            statuses,
            book=book,
            store_searches=store_searches,
        )
