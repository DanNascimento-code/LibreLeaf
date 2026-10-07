<p align="center">
  <img src="output/images/libreleaf-linkedin-logo.png" alt="LibreLeaf open-book logo" width="180">
</p>

# LibreLeaf

**Discover. Compare. Read.**

[**Live demo**](https://libreleaf-books.vercel.app) ·
[**LinkedIn project story**](output/pdf/libreleaf-linkedin-story.pdf)

LibreLeaf is an **ethical web scraper and focused web crawler** for book discovery and price
comparison. A reader can
enter a title or ISBN; LibreLeaf identifies one exact edition and compares only public offers whose
ISBN and visible price can be verified. The interface is available in English, Brazilian Portuguese,
and Latin American Spanish.

This is a real scraping project: it requests public bookstore pages, parses HTML and JSON-LD,
extracts structured prices, validates exact ISBNs, follows only controlled discovery paths, and
normalizes offers into a shared data model. The active retail sources require no account, token, or
API key. LibreLeaf identifies itself, paces
requests, honors public access rules, and never bypasses authentication, CAPTCHAs, or bot protection.
A store is excluded if its necessary search path is disallowed or cannot reliably expose a price.

## Features

- Title-to-ISBN and ISBN-to-title resolution through Open Library.
- Exact-edition price comparison in Brazil, the United States, and Argentina.
- Real public-page scrapers for Estante Virtual, Livraria da Vila, ThriftBooks, and LibrosRef.
- Controlled crawling of explicitly requested catalog/search paths, with retry, pacing, validation,
  partial-failure handling, and no unrestricted site traversal.
- Book discovery and Project Gutenberg OPDS feed harvesting.
- English, Portuguese, and Spanish UI with persistent language and theme controls.
- Responsive FastAPI/Jinja frontend plus a command-line interface.
- ISBN checksum validation, normalized money, SQLite history, and HTML/JSON/CSV exports.
- Partial results when a source is unavailable; no fabricated or manually linked prices.

## Why ISBN matching matters

A title is not a product identifier. A work may have eBook, paperback, hardcover, translated,
revised, and used editions. LibreLeaf follows this pipeline:

```text
title or ISBN → exact edition → validated ISBN-13 → matching offers → price comparison
```

Shipping remains unknown unless a source explicitly supplies it. Unknown shipping is never treated
as free, and a cheaper but different edition is never silently substituted.

## Setup

Requirements: Python 3.11 or newer and [uv](https://docs.astral.sh/uv/).

```powershell
git clone <repository-url>
cd web_scraper
uv sync --locked
Copy-Item .env.example .env
```

No retailer credentials are needed. `LIBRELEAF_CONTACT_EMAIL` is only a responsible contact address
for public catalog traffic.

## Run the web app

```powershell
uv run libreleaf serve
```

Open `http://127.0.0.1:8000`. If port 8000 is occupied:

```powershell
uv run libreleaf serve --port 8001
```

The first-page form accepts a title, ISBN-10, or ISBN-13. Portuguese defaults to Brazil, English to
the United States, and Spanish to Argentina; readers can choose another market explicitly. JSON
health and source-readiness endpoints are available at `/api/health` and `/api/providers`.

## CLI examples

```powershell
uv run libreleaf compare 9786558380542 --market BR
uv run libreleaf compare 9780140328721 --market US
uv run libreleaf compare 9788419266286 --market AR
uv run libreleaf discover "Machado de Assis" --language por --market BR
uv run libreleaf harvest "Machado de Assis"
uv run libreleaf providers --market BR
```

Optional `--json` and `--csv` flags export normalized records. Reports and SQLite data are written
under `data/` by default.

## Source matrix

| Source | BR | US | AR | Credential | Role |
|---|:---:|:---:|:---:|---|---|
| Open Library | yes | yes | yes | optional contact email | edition metadata |
| Project Gutenberg | yes | yes | yes | contact email | public-domain OPDS catalog |
| Estante Virtual | yes | no | no | none | marketplace prices with exact-ISBN verification |
| Livraria da Vila | yes | no | no | none | bookstore price with exact-ISBN verification |
| ThriftBooks | no | yes | no | none | new and used exact-ISBN offers |
| LibrosRef | no | no | yes | none | Argentine bookstore price in ARS |

Coverage is deliberately conservative. Some major retailers require credentials, prohibit automated
search, or return bot challenges; they are not active sources. The app favors fewer verifiable prices
over decorative links that cannot participate in comparison.

## Architecture

```text
FastAPI web UI / CLI
├── discover → Open Library → normalized books → SQLite
├── harvest  → Gutenberg OPDS XML → books and downloads → SQLite
└── compare  → ISBN validation → edition resolution
                              → paced public bookstore scrapers
                              → exact ISBN + visible price verification
                              → sorted offers + observation history
```

Every price source implements the same provider interface. Store-specific HTML is converted at the
boundary into a shared `Offer` model, so sorting, storage, exports, reports, and tests remain
source-independent.

## Data integrity

- ISBN checksums are validated, and ISBN-10 is converted to ISBN-13.
- Offers are accepted only after the requested ISBN appears in product data.
- Money uses integer minor units (`6490` means `R$ 64.90`).
- Item price and shipping are separate; unknown shipping is not free shipping.
- Observations are timestamped and append-only.
- Currencies are not converted implicitly.
- One failed source does not erase successful results from another.

## Environment

| Variable | Purpose |
|---|---|
| `LIBRELEAF_CONTACT_EMAIL` | identifies responsible public-catalog traffic |

There are no retailer secrets. `.env` is still ignored because a personal contact address should not
be committed.

## Development

```powershell
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run pytest --cov --cov-report=term-missing
```

Tests use controlled JSON, XML, and HTML responses, ASGI requests, and fake HTTP transports. The
automated suite does not contact live stores.

## Ethical policy

1. Prefer documented feeds and public pages intended for product discovery.
2. Check access rules before adding a source.
3. Do not bypass authentication, CAPTCHAs, paywalls, or bot protection.
4. Identify the application, pace requests, and avoid repeated fetches.
5. Match exact editions before comparing prices.
6. Preserve attribution and link to the original offer.
7. Show unknown costs, observation times, and partial failures honestly.
8. Revalidate selectors and store terms before public deployment.

## References

- [Open Library APIs](https://openlibrary.org/developers/api)
- [Project Gutenberg robot policy](https://www.gutenberg.org/policy/robot_access.html)
- [Estante Virtual robots policy](https://www.estantevirtual.com.br/robots.txt)
- [Livraria da Vila](https://www.livrariadavila.com.br/)
- [ThriftBooks](https://www.thriftbooks.com/)
- [LibrosRef](https://librosref.com/)
