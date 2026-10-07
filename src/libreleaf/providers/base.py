from typing import Protocol

from libreleaf.models import BookIdentity, Offer, ProviderStatus


class PriceProvider(Protocol):
    name: str
    markets: tuple[str, ...]

    def status(self, market: str) -> ProviderStatus: ...

    def find_offers(
        self,
        isbn13: str,
        market: str,
        postcode: str | None,
        book: BookIdentity | None = None,
    ) -> list[Offer]: ...

    def close(self) -> None: ...
