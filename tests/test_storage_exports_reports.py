import csv
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from libreleaf.exporters import export_records
from libreleaf.models import (
    Book,
    ComparisonResult,
    DownloadLink,
    Offer,
    ProviderStatus,
    PublicDomainBook,
)
from libreleaf.reports import (
    write_comparison_report,
    write_discovery_report,
    write_harvest_report,
)
from libreleaf.storage import LibreLeafRepository


def book() -> Book:
    return Book(
        title="Clean <Code>",
        authors=("Robert C. Martin",),
        isbn13="9780132350884",
        first_publish_year=2008,
        languages=("eng",),
        subjects=("Programming",),
        edition_count=12,
        ebook_access="borrowable",
        cover_url="https://example.test/cover.jpg",
        information_url="https://openlibrary.org/works/OL1W",
    )


def offer() -> Offer:
    return Offer(
        provider="Store",
        market="BR",
        external_id="1",
        isbn13="9780132350884",
        title="Clean Code",
        book_format="paperback",
        condition="new",
        item_price_minor=10000,
        shipping_minor=None,
        currency="BRL",
        availability="active",
        seller="Seller",
        purchase_url="https://example.test/buy?a=1&b=2",
        observed_at=datetime(2026, 10, 6, tzinfo=UTC),
    )


def public_book() -> PublicDomainBook:
    return PublicDomainBook(
        gutenberg_id="11",
        title="Alice",
        authors=("Carroll, Lewis",),
        languages=("en",),
        summary="A rabbit hole.",
        published_at="2026-01-01T00:00:00Z",
        information_url="https://www.gutenberg.org/ebooks/11",
        cover_url=None,
        downloads=(
            DownloadLink("application/epub+zip", "https://www.gutenberg.org/ebooks/11.epub3"),
            DownloadLink("text/plain", "https://www.gutenberg.org/files/11/11.txt"),
        ),
    )


def test_repository_upserts_books_and_preserves_observations(tmp_path: Path) -> None:
    repository = LibreLeafRepository(tmp_path / "libreleaf.db")
    repository.save_books([book()])
    repository.save_books([book()])
    repository.save_offers([offer()])
    repository.save_offers([offer()])
    repository.save_public_domain_books([public_book()], "2026-01-01T00:00:00+00:00")
    repository.save_public_domain_books([public_book()], "2026-01-02T00:00:00+00:00")
    assert repository.counts() == (1, 1)


def test_json_and_csv_exports_are_atomic(tmp_path: Path) -> None:
    json_path = tmp_path / "offers.json"
    csv_path = tmp_path / "offers.csv"
    assert export_records([offer()], json_path) == 1
    assert json.loads(json_path.read_text(encoding="utf-8"))[0]["item_price"] == "100.00"
    export_records([book()], csv_path)
    with csv_path.open(encoding="utf-8", newline="") as file:
        row = next(csv.DictReader(file))
    assert json.loads(row["authors"]) == ["Robert C. Martin"]
    with pytest.raises(ValueError, match=r"\.json or \.csv"):
        export_records([offer()], tmp_path / "bad.txt")
    assert not (tmp_path / "bad.txt.tmp").exists()


def test_empty_csv_export(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    export_records([], path)
    assert path.read_text(encoding="utf-8") == ""


def test_reports_escape_content_and_explain_unknown_shipping(tmp_path: Path) -> None:
    discovery = tmp_path / "discover.html"
    comparison = tmp_path / "compare.html"
    write_discovery_report([book()], "clean <code>", "BR", discovery)
    result = ComparisonResult(
        isbn13="9780132350884",
        market="BR",
        offers=(offer(),),
        provider_statuses=(ProviderStatus("Store", ("BR",), True, "1 matching offer(s)"),),
        compared_at=datetime(2026, 10, 6, tzinfo=UTC),
    )
    write_comparison_report(result, comparison)
    discovery_html = discovery.read_text(encoding="utf-8")
    comparison_html = comparison.read_text(encoding="utf-8")
    assert "Clean &lt;Code&gt;" in discovery_html
    assert "clean &lt;code&gt;" in discovery_html
    assert "Unknown" in comparison_html
    assert "a=1&amp;b=2" in comparison_html


def test_harvest_report_and_public_book_export(tmp_path: Path) -> None:
    path = tmp_path / "public-domain.html"
    write_harvest_report(
        (public_book(),),
        "alice <rabbit>",
        "https://www.gutenberg.org/ebooks/search.opds/?start_index=26",
        path,
    )
    html = path.read_text(encoding="utf-8")
    assert "alice &lt;rabbit&gt;" in html
    assert "does not auto-crawl" in html
    assert "EPUB" in html and "Text" in html
    record = public_book().to_record()
    assert record["downloads"][0]["media_type"] == "application/epub+zip"
