from datetime import UTC, datetime

import pytest

from libreleaf.config import Settings, normalize_market
from libreleaf.errors import InvalidIsbnError
from libreleaf.isbn import first_valid_isbn13, normalize_isbn13
from libreleaf.models import Offer, decimal_to_minor


def test_isbn_normalization_and_conversion() -> None:
    assert normalize_isbn13("978-0-13-235088-4") == "9780132350884"
    assert normalize_isbn13("0-13-235088-2") == "9780132350884"
    assert first_valid_isbn13(["bad", "9780132350884"]) == "9780132350884"
    assert first_valid_isbn13(["bad"]) is None


@pytest.mark.parametrize("value", ["9780132350885", "0132350883", "123", "abcdefghij"])
def test_invalid_isbn_is_rejected(value: str) -> None:
    with pytest.raises(InvalidIsbnError):
        normalize_isbn13(value)


def test_offer_money_is_exact_and_shipping_controls_total() -> None:
    offer = Offer(
        provider="Example",
        market="BR",
        external_id="1",
        isbn13="9780132350884",
        title="Clean Code",
        book_format="paperback",
        condition="new",
        item_price_minor=decimal_to_minor("141.905"),
        shipping_minor=1240,
        currency="BRL",
        availability="active",
        seller=None,
        purchase_url="https://example.test",
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert offer.item_price_minor == 14191
    assert offer.total_minor == 15431
    assert offer.to_record()["known_total"] == "154.31"
    assert offer.to_record()["observed_at"] == "2026-01-01T00:00:00+00:00"


def test_unknown_shipping_means_unknown_total() -> None:
    base = dict(
        provider="Example",
        market="US",
        external_id="1",
        isbn13="9780132350884",
        title="Book",
        book_format="unknown",
        condition="unknown",
        item_price_minor=100,
        shipping_minor=None,
        currency="USD",
        availability="active",
        seller=None,
        purchase_url="",
        observed_at=datetime.now(UTC),
    )
    offer = Offer(**base)
    assert offer.total_minor is None
    assert offer.to_record()["shipping"] is None


def test_settings_load_environment_and_market(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIBRELEAF_CONTACT_EMAIL", " reader@example.com ")
    settings = Settings.from_env()
    assert settings.contact_email == "reader@example.com"
    assert normalize_market("br") == "BR"
    with pytest.raises(ValueError, match="Unsupported market"):
        normalize_market("CA")
