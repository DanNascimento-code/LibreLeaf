import os
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from libreleaf.comparison import PriceComparisonService
from libreleaf.config import Settings, normalize_market
from libreleaf.discovery import OpenLibraryDiscovery
from libreleaf.errors import ConfigurationError, InvalidIsbnError, LibreLeafError
from libreleaf.gutenberg import GutenbergHarvester
from libreleaf.i18n import DEFAULT_MARKETS, normalize_language, translator
from libreleaf.isbn import normalize_isbn13
from libreleaf.models import BookIdentity, ProviderStatus
from libreleaf.providers import (
    EstanteVirtualProvider,
    LibrosRefProvider,
    LivrariaDaVilaProvider,
    ThriftBooksProvider,
)
from libreleaf.providers.base import PriceProvider
from libreleaf.resolver import OpenLibraryISBNResolver
from libreleaf.storage import LibreLeafRepository

PACKAGE_ROOT = Path(__file__).parent
TEMPLATE_ROOT = PACKAGE_ROOT / "templates"
STATIC_ROOT = PACKAGE_ROOT / "static"
DATABASE_PATH = Path("/tmp/libreleaf.db") if os.getenv("VERCEL") else Path("data/libreleaf.db")


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or Settings.from_env()
    app = FastAPI(
        title="LibreLeaf",
        summary="Ethical book discovery, feed harvesting, and price comparison",
        version="0.5.0",
    )
    templates = Jinja2Templates(directory=TEMPLATE_ROOT)
    templates.env.globals["money"] = _money
    app.mount("/static", StaticFiles(directory=STATIC_ROOT), name="static")
    app.state.settings = runtime_settings

    def render(request: Request, name: str, context: dict[str, Any]) -> HTMLResponse:
        language = _request_language(request)
        return templates.TemplateResponse(
            request=request,
            name=name,
            context={
                "lang": language,
                "t": translator(language),
                "default_market": DEFAULT_MARKETS[language],
                **context,
            },
        )

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Any):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' https: data:; style-src 'self'; "
            "script-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
        )
        return response

    @app.get("/", response_class=HTMLResponse, name="home")
    def home(request: Request) -> HTMLResponse:
        return render(request, "index.html", {})

    @app.get("/language/{code}", name="set_language")
    def set_language(code: str, next: str = Query("/", max_length=500)) -> RedirectResponse:
        language = normalize_language(code)
        destination = next if next.startswith("/") and not next.startswith("//") else "/"
        response = RedirectResponse(destination, status_code=303)
        response.set_cookie(
            "libreleaf_language",
            language,
            max_age=31_536_000,
            httponly=True,
            samesite="lax",
        )
        return response

    @app.get("/discover", response_class=HTMLResponse, name="discover")
    def discover(
        request: Request,
        q: str = Query("", max_length=200),
        market: str = Query("", max_length=2),
        language: str = Query("", max_length=8),
        limit: int = Query(12, ge=1, le=40),
    ) -> HTMLResponse:
        books = []
        error = None
        normalized_market = _safe_market(market or DEFAULT_MARKETS[_request_language(request)])
        if q.strip():
            client = OpenLibraryDiscovery(runtime_settings)
            try:
                books = client.search(q.strip(), limit=limit, language=language.strip() or None)
                LibreLeafRepository(DATABASE_PATH).save_books(books)
            except LibreLeafError as caught:
                error = _public_error(caught, _request_language(request))
            finally:
                client.close()
        return render(
            request,
            "discover.html",
            {
                "books": books,
                "query": q,
                "market": normalized_market,
                "language": language,
                "error": error,
            },
        )

    @app.get("/compare", response_class=HTMLResponse, name="compare")
    def compare(
        request: Request,
        q: str = Query("", max_length=200),
        isbn: str = Query("", max_length=32),
        market: str = Query("", max_length=2),
        postcode: str = Query("", max_length=16),
    ) -> HTMLResponse:
        result = None
        error = None
        resolution = None
        language = _request_language(request)
        normalized_market = _safe_market(market or DEFAULT_MARKETS[language])
        query = q.strip() or isbn.strip()
        legacy_isbn_query = bool(isbn.strip() and not q.strip())
        if query:
            providers = _providers(runtime_settings)
            service = PriceComparisonService(providers)
            try:
                resolver = OpenLibraryISBNResolver(runtime_settings)
                try:
                    if legacy_isbn_query or _looks_like_isbn(query):
                        isbn13 = normalize_isbn13(query)
                        book = resolver.resolve(isbn13)
                        resolution = "ISBN"
                    else:
                        market_isbn = None
                        if normalized_market == "BR":
                            estante = next(
                                (
                                    provider
                                    for provider in providers
                                    if isinstance(provider, EstanteVirtualProvider)
                                ),
                                None,
                            )
                            if estante is not None:
                                market_isbn = estante.resolve_title_isbn(query)
                        book = resolver.resolve(market_isbn) if market_isbn else None
                        if market_isbn and book is None:
                            book = BookIdentity(
                                isbn13=market_isbn,
                                title=query,
                                authors=(),
                                publisher=None,
                                publish_date=None,
                                cover_url=None,
                                information_url=f"https://openlibrary.org/isbn/{market_isbn}",
                            )
                        if book is None:
                            book = resolver.resolve_title(
                                query,
                                language={"BR": "pt", "US": "en", "AR": "es"}[normalized_market],
                            )
                        if book is None:
                            raise LibreLeafError(
                                "No ISBN-bearing edition was found for that title. "
                                "Try adding the author or edition to the search."
                            )
                        isbn13 = book.isbn13
                        resolution = "title"
                finally:
                    resolver.close()
                result = service.compare(
                    isbn13,
                    normalized_market,
                    postcode.strip() or None,
                    book=book,
                )
                LibreLeafRepository(DATABASE_PATH).save_offers(result.offers)
            except LibreLeafError as caught:
                error = _public_error(caught, language)
            finally:
                service.close()
        return render(
            request,
            "compare.html",
            {
                "result": result,
                "query": query,
                "resolution": resolution,
                "market": normalized_market,
                "postcode": postcode,
                "error": error,
            },
        )

    @app.get("/free-books", response_class=HTMLResponse, name="free_books")
    def free_books(
        request: Request,
        q: str = Query("", max_length=200),
        page_url: str = Query("", max_length=1000),
    ) -> HTMLResponse:
        page = None
        error = None
        if q.strip() or page_url.strip():
            try:
                harvester = GutenbergHarvester(runtime_settings)
                try:
                    page = harvester.search(q.strip(), page_url=page_url.strip() or None)
                finally:
                    harvester.close()
                LibreLeafRepository(DATABASE_PATH).save_public_domain_books(
                    page.books, page.fetched_at.isoformat()
                )
            except LibreLeafError as caught:
                error = _public_error(caught, _request_language(request))
        return render(
            request,
            "free_books.html",
            {
                "page": page,
                "query": q,
                "error": error,
                "contact_ready": bool(runtime_settings.contact_email),
            },
        )

    @app.get("/architecture", response_class=HTMLResponse, name="architecture")
    def architecture(request: Request) -> HTMLResponse:
        return render(request, "architecture.html", {})

    @app.get("/api/health", response_class=JSONResponse)
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "libreleaf", "version": "0.5.0"}

    @app.get("/api/providers", response_class=JSONResponse)
    def provider_api(market: str = Query("BR", max_length=2)) -> dict[str, Any]:
        normalized = _safe_market(market)
        statuses = [
            status
            for status in _provider_statuses(runtime_settings)
            if normalized in status.markets
        ]
        return {
            "market": normalized,
            "providers": [
                {"name": item.name, "configured": item.configured, "reason": item.reason}
                for item in statuses
            ],
        }

    return app


def main() -> None:
    import uvicorn

    uvicorn.run("libreleaf.web:create_app", factory=True, host="127.0.0.1", port=8000)


def _providers(settings: Settings) -> list[PriceProvider]:
    return [
        EstanteVirtualProvider(settings),
        LivrariaDaVilaProvider(settings),
        ThriftBooksProvider(settings),
        LibrosRefProvider(settings),
    ]


def _provider_statuses(settings: Settings):  # type: ignore[no-untyped-def]
    providers = _providers(settings)
    try:
        statuses: list[ProviderStatus] = []
        for provider in providers:
            for market in provider.markets:
                status = provider.status(market)
                statuses.append(
                    ProviderStatus(
                        name=status.name,
                        markets=(market,),
                        configured=status.configured,
                        reason=status.reason,
                    )
                )
        return statuses
    finally:
        for provider in providers:
            provider.close()


def _safe_market(value: str) -> str:
    try:
        return normalize_market(value)
    except ValueError:
        return "BR"


def _looks_like_isbn(value: str) -> bool:
    compact = re.sub(r"[^0-9Xx]", "", value)
    return len(compact) in {10, 13} and bool(re.fullmatch(r"[0-9Xx\-\s]+", value))


def _request_language(request: Request) -> str:
    return normalize_language(request.cookies.get("libreleaf_language"))


def _public_error(error: LibreLeafError, language: str = "en") -> str:
    t = translator(language)
    if isinstance(error, InvalidIsbnError):
        return str(error)
    if isinstance(error, ConfigurationError):
        return t("This feature is temporarily unavailable. Please try again later.")
    return t("We couldn't complete this search right now. Please try again.")


def _money(value: int | None, currency: str, language: str = "en") -> str:
    if value is None:
        return translator(language)("Unknown")
    symbol = {"BRL": "R$", "USD": "$", "ARS": "AR$"}.get(currency, currency)
    amount = f"{value / 100:,.2f}"
    if language in {"pt-BR", "es-419"}:
        amount = amount.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{symbol} {amount}"


app = create_app()
