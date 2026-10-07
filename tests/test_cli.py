from datetime import UTC, datetime
from pathlib import Path

import pytest

import libreleaf.cli as cli
from libreleaf.cli import build_parser
from libreleaf.models import (
    Book,
    ComparisonResult,
    HarvestPage,
    Offer,
    ProviderStatus,
    PublicDomainBook,
)


def sample_book() -> Book:
    return Book(
        title="Clean Code",
        authors=("Robert C. Martin",),
        isbn13="9780132350884",
        first_publish_year=2008,
        languages=("eng",),
        subjects=(),
        edition_count=1,
        ebook_access="borrowable",
        cover_url=None,
        information_url="https://openlibrary.org/works/OL1W",
    )


def sample_offer() -> Offer:
    return Offer(
        provider="Store",
        market="BR",
        external_id="1",
        isbn13="9780132350884",
        title="Clean Code",
        book_format="paperback",
        condition="new",
        item_price_minor=10000,
        shipping_minor=0,
        currency="BRL",
        availability="active",
        seller=None,
        purchase_url="https://example.test",
        observed_at=datetime.now(UTC),
    )


def test_parser_commands_and_limits() -> None:
    args = build_parser().parse_args(["discover", "python"])
    assert (args.market, args.limit) == ("BR", 10)
    args = build_parser().parse_args(["compare", "9780132350884", "--market", "us"])
    assert args.market == "US"
    with pytest.raises(SystemExit):
        build_parser().parse_args(["discover", "x", "--limit", "101"])
    assert build_parser().parse_args(["serve", "--port", "8080"]).port == 8080
    with pytest.raises(SystemExit):
        build_parser().parse_args(["serve", "--port", "70000"])


def test_discover_command_writes_outputs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    class Discovery:
        def __init__(self, settings: object) -> None:
            pass

        def search(self, query: str, *, limit: int, language: str | None) -> list[Book]:
            return [sample_book()]

        def close(self) -> None:
            pass

    monkeypatch.setattr(cli, "OpenLibraryDiscovery", Discovery)
    html = tmp_path / "discover.html"
    json_path = tmp_path / "discover.json"
    database = tmp_path / "db.sqlite"
    code = cli.run(
        [
            "discover",
            "clean code",
            "--html",
            str(html),
            "--json",
            str(json_path),
            "--database",
            str(database),
        ]
    )
    assert code == 0
    assert html.exists() and json_path.exists() and database.exists()
    assert "validated ISBN-13" in capsys.readouterr().out


def test_compare_command_filters_and_reports_status(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = ComparisonResult(
        isbn13="9780132350884",
        market="BR",
        offers=(sample_offer(),),
        provider_statuses=(ProviderStatus("Store", ("BR",), True, "1 matching offer(s)"),),
        compared_at=datetime.now(UTC),
    )

    class Service:
        def __init__(self, providers: object) -> None:
            pass

        def compare(
            self,
            isbn13: str,
            market: str,
            postcode: str | None,
            **kwargs: object,
        ) -> ComparisonResult:
            return result

        def close(self) -> None:
            pass

    class Resolver:
        def __init__(self, settings: object) -> None:
            pass

        def resolve(self, isbn13: str) -> None:
            return None

        def close(self) -> None:
            pass

    monkeypatch.setattr(cli, "PriceComparisonService", Service)
    monkeypatch.setattr(cli, "OpenLibraryISBNResolver", Resolver)
    monkeypatch.setattr(cli, "_providers", lambda settings: [])
    html = tmp_path / "compare.html"
    code = cli.run(
        [
            "compare",
            "0132350882",
            "--condition",
            "new",
            "--html",
            str(html),
            "--database",
            str(tmp_path / "db.sqlite"),
        ]
    )
    assert code == 0
    assert html.exists()
    assert "Store: 1 matching offer(s)" in capsys.readouterr().out


def test_providers_command_and_invalid_isbn(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.run(["providers", "--market", "BR"]) == 0
    output = capsys.readouterr().out
    assert "Estante Virtual: ready" in output
    assert "Livraria da Vila: ready" in output
    assert cli.run(["compare", "bad-isbn"]) == 1


def test_filter_result_can_remove_offers() -> None:
    result = ComparisonResult.create(
        "9780132350884",
        "BR",
        [sample_offer()],
        [ProviderStatus("Store", ("BR",), True, "ready")],
    )
    assert cli._filter_result(result, "ebook", "all").offers == ()
    assert cli._filter_result(result, "all", "new").offers


def test_harvest_command_writes_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    public_book = PublicDomainBook(
        gutenberg_id="11",
        title="Alice",
        authors=("Carroll, Lewis",),
        languages=("en",),
        summary=None,
        published_at=None,
        information_url="https://www.gutenberg.org/ebooks/11",
        cover_url=None,
        downloads=(),
    )
    page = HarvestPage(
        books=(public_book,),
        source_url="https://www.gutenberg.org/ebooks/search.opds/?query=alice",
        next_url="https://www.gutenberg.org/ebooks/search.opds/?start_index=26",
        previous_url=None,
        fetched_at=datetime.now(UTC),
    )

    class Harvester:
        def __init__(self, settings: object) -> None:
            pass

        def search(self, query: str, *, page_url: str | None = None) -> HarvestPage:
            return page

        def close(self) -> None:
            pass

    monkeypatch.setattr(cli, "GutenbergHarvester", Harvester)
    monkeypatch.setenv("LIBRELEAF_CONTACT_EMAIL", "reader@example.com")
    html = tmp_path / "harvest.html"
    code = cli.run(
        [
            "harvest",
            "alice",
            "--html",
            str(html),
            "--database",
            str(tmp_path / "db.sqlite"),
        ]
    )
    assert code == 0 and html.exists()
    assert "Next page" in capsys.readouterr().out


def test_serve_command_invokes_uvicorn(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, int]] = []
    import uvicorn

    monkeypatch.setattr(uvicorn, "run", lambda app, host, port: calls.append((host, port)))
    monkeypatch.setattr("libreleaf.web.create_app", lambda settings: object())
    assert cli.run(["serve", "--host", "0.0.0.0", "--port", "9000"]) == 0
    assert calls == [("0.0.0.0", 9000)]
