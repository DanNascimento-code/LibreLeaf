import argparse
import logging
import sqlite3
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from libreleaf.comparison import PriceComparisonService
from libreleaf.config import Settings, normalize_market
from libreleaf.discovery import OpenLibraryDiscovery
from libreleaf.errors import ApiError, LibreLeafError
from libreleaf.exporters import export_records
from libreleaf.gutenberg import GutenbergHarvester
from libreleaf.isbn import normalize_isbn13
from libreleaf.models import ComparisonResult
from libreleaf.providers import (
    EstanteVirtualProvider,
    LibrosRefProvider,
    LivrariaDaVilaProvider,
    ThriftBooksProvider,
)
from libreleaf.providers.base import PriceProvider
from libreleaf.reports import (
    write_comparison_report,
    write_discovery_report,
    write_harvest_report,
)
from libreleaf.resolver import OpenLibraryISBNResolver
from libreleaf.storage import LibreLeafRepository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="libreleaf",
        description="Discover books and compare exact-edition prices from public store pages.",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="enable diagnostic logs")
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover = subparsers.add_parser("discover", help="find books through Open Library")
    discover.add_argument("query", help="title, author, subject, or keywords")
    discover.add_argument("--market", type=normalize_market, default="BR", metavar="BR|US|AR")
    discover.add_argument("--language", help="Open Library language code, such as por or eng")
    discover.add_argument("--limit", type=_bounded_limit, default=10)
    discover.add_argument("--html", type=Path, default=Path("data/discovery.html"))
    discover.add_argument("--json", type=Path)
    discover.add_argument("--csv", type=Path)
    discover.add_argument("--database", type=Path, default=Path("data/libreleaf.db"))

    compare = subparsers.add_parser("compare", help="compare retailer offers for one ISBN")
    compare.add_argument("isbn", help="ISBN-10 or ISBN-13 for an exact edition")
    compare.add_argument("--market", type=normalize_market, default="BR", metavar="BR|US|AR")
    compare.add_argument(
        "--postcode", help="delivery postcode/ZIP used when a provider supports it"
    )
    compare.add_argument(
        "--format",
        choices=("all", "paperback", "hardcover", "ebook", "unknown"),
        default="all",
    )
    compare.add_argument(
        "--condition", choices=("all", "new", "used", "refurbished", "unknown"), default="all"
    )
    compare.add_argument("--html", type=Path, default=Path("data/comparison.html"))
    compare.add_argument("--json", type=Path)
    compare.add_argument("--csv", type=Path)
    compare.add_argument("--database", type=Path, default=Path("data/libreleaf.db"))

    providers = subparsers.add_parser("providers", help="show price-source readiness")
    providers.add_argument("--market", type=normalize_market, default="BR", metavar="BR|US|AR")

    harvest = subparsers.add_parser("harvest", help="collect one Project Gutenberg OPDS feed page")
    harvest.add_argument("query", nargs="?", default="", help="catalog search terms")
    harvest.add_argument("--page-url", help="explicit next-page URL returned by a previous harvest")
    harvest.add_argument("--html", type=Path, default=Path("data/public-domain.html"))
    harvest.add_argument("--json", type=Path)
    harvest.add_argument("--csv", type=Path)
    harvest.add_argument("--database", type=Path, default=Path("data/libreleaf.db"))

    serve = subparsers.add_parser("serve", help="run the LibreLeaf web application")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=_port, default=8000)
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    settings = Settings.from_env()
    try:
        if args.command == "discover":
            return _run_discover(args, settings)
        if args.command == "compare":
            return _run_compare(args, settings)
        if args.command == "providers":
            return _run_providers(args.market, settings)
        if args.command == "harvest":
            return _run_harvest(args, settings)
        return _run_server(args, settings)
    except (LibreLeafError, OSError, sqlite3.Error, ValueError) as error:
        logging.getLogger(__name__).error("%s", error)
        return 1


def main() -> None:
    raise SystemExit(run())


def _run_discover(args: argparse.Namespace, settings: Settings) -> int:
    discovery = OpenLibraryDiscovery(settings)
    try:
        books = discovery.search(args.query, limit=args.limit, language=args.language)
    finally:
        discovery.close()
    stored = LibreLeafRepository(args.database).save_books(books)
    write_discovery_report(books, args.query, args.market, args.html)
    _optional_exports(books, args.json, args.csv)
    comparable = sum(book.isbn13 is not None for book in books)
    print(
        f"Found {len(books)} book(s); {comparable} have a validated ISBN-13. "
        f"Stored {stored}; report: {args.html}"
    )
    return 0


def _run_compare(args: argparse.Namespace, settings: Settings) -> int:
    isbn13 = normalize_isbn13(args.isbn)
    resolver = OpenLibraryISBNResolver(settings)
    try:
        try:
            book = resolver.resolve(isbn13)
        except ApiError as error:
            logging.getLogger(__name__).warning("ISBN metadata lookup failed: %s", error)
            book = None
    finally:
        resolver.close()
    service = PriceComparisonService(_providers(settings))
    try:
        result = service.compare(
            isbn13,
            args.market,
            args.postcode,
            book=book,
        )
    finally:
        service.close()
    result = _filter_result(result, args.format, args.condition)
    stored = LibreLeafRepository(args.database).save_offers(result.offers)
    write_comparison_report(result, args.html)
    _optional_exports(result.offers, args.json, args.csv)
    summary = f"Compared {isbn13}: {len(result.offers)} exact offer(s); stored {stored}"
    print(f"{summary}; report: {args.html}")
    if result.book:
        print(f"- Edition: {result.book.title} ({result.book.publisher or 'publisher unknown'})")
    else:
        print("- Edition: valid ISBN, but no catalog metadata was found")
    for status in result.provider_statuses:
        print(f"- {status.name}: {status.reason}")
    return 0


def _run_providers(market: str, settings: Settings) -> int:
    providers = _providers(settings)
    try:
        print(f"Provider readiness for {market}:")
        for provider in providers:
            if market not in provider.markets:
                continue
            status = provider.status(market)
            marker = "ready" if status.configured else "not configured"
            print(f"- {status.name}: {marker} ({status.reason})")
    finally:
        for provider in providers:
            provider.close()
    return 0


def _run_harvest(args: argparse.Namespace, settings: Settings) -> int:
    harvester = GutenbergHarvester(settings)
    try:
        page = harvester.search(args.query, page_url=args.page_url)
    finally:
        harvester.close()
    stored = LibreLeafRepository(args.database).save_public_domain_books(
        page.books, page.fetched_at.isoformat()
    )
    write_harvest_report(page.books, args.query, page.next_url, args.html)
    _optional_exports(page.books, args.json, args.csv)
    print(f"Harvested {len(page.books)} book(s); stored {stored}; report: {args.html}")
    if page.next_url:
        print(f"Next page (request explicitly): {page.next_url}")
    return 0


def _run_server(args: argparse.Namespace, settings: Settings) -> int:
    import uvicorn

    from libreleaf.web import create_app

    uvicorn.run(create_app(settings), host=args.host, port=args.port)
    return 0


def _providers(settings: Settings) -> list[PriceProvider]:
    return [
        EstanteVirtualProvider(settings),
        LivrariaDaVilaProvider(settings),
        ThriftBooksProvider(settings),
        LibrosRefProvider(settings),
    ]


def _optional_exports(items: object, json_path: Path | None, csv_path: Path | None) -> None:
    if json_path:
        export_records(items, json_path)  # type: ignore[arg-type]
    if csv_path:
        export_records(items, csv_path)  # type: ignore[arg-type]


def _filter_result(result: ComparisonResult, book_format: str, condition: str) -> ComparisonResult:
    offers = tuple(
        offer
        for offer in result.offers
        if (book_format == "all" or offer.book_format == book_format)
        and (condition == "all" or offer.condition == condition)
    )
    return replace(result, offers=offers)


def _bounded_limit(value: str) -> int:
    parsed = int(value)
    if not 1 <= parsed <= 100:
        raise argparse.ArgumentTypeError("must be between 1 and 100")
    return parsed


def _port(value: str) -> int:
    parsed = int(value)
    if not 1 <= parsed <= 65535:
        raise argparse.ArgumentTypeError("must be between 1 and 65535")
    return parsed
