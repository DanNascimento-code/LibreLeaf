# LinkedIn project fields - LibreLeaf

## Project name

LibreLeaf - Ethical Book Price Web Scraper

## Short description

LibreLeaf is an ethical web scraper and focused crawler that identifies books by ISBN and compares
verified prices from public bookstore pages in Brazil, the United States, and Argentina. I built the
complete product with Python, FastAPI, Beautiful Soup, Jinja, SQLite, multilingual UI, resilient HTTP
handling, exact-edition validation, automated tests, and production deployment on Vercel.

## Longer description

I developed LibreLeaf to solve a subtle price-comparison problem: books with the same title are not
necessarily the same product. Different translations, formats, revisions, and editions can have
completely different ISBNs and prices.

The application accepts an ISBN - the preferred input - or a book title. It resolves one exact
edition, collects public offers from supported bookstores, verifies the ISBN in the returned product
data, normalizes monetary values, and presents comparable results without treating unknown shipping
as free.

The scraper uses descriptive user-agent identification, request pacing, timeouts, retries, controlled
discovery paths, and partial-failure handling. It does not bypass authentication, CAPTCHAs, paywalls,
or blocked search routes. The frontend supports English, Brazilian Portuguese, and Latin American
Spanish, with dark mode as the default.

## Skills

Python, FastAPI, Web Scraping, Web Crawling, Beautiful Soup, HTTPX, Jinja2, HTML, CSS, SQLite,
Pytest, Data Validation, REST APIs, Internationalization, Vercel, Git, GitHub

## Project URL

https://libreleaf-books.vercel.app

## Source code

https://github.com/DanNascimento-code/LibreLeaf

## Suggested LinkedIn post

I built LibreLeaf, an ethical web scraper for exact-edition book price comparison.

The main challenge was not simply extracting prices. A title can represent multiple translations,
formats, and revisions, so comparing results safely requires ISBN-level validation. LibreLeaf accepts
an ISBN or title, resolves one edition, verifies store results against that ISBN, and normalizes real
public prices without hiding unknown shipping costs.

Highlights:

- Python, FastAPI, Beautiful Soup, HTTPX, Jinja, and SQLite
- Real HTML and JSON-LD extraction from public bookstore pages
- Controlled crawling, pacing, retries, and partial-failure handling
- English, Portuguese, and Spanish interface
- 51 automated tests and approximately 89% statement coverage
- Production deployment on Vercel

Live app: https://libreleaf-books.vercel.app

Source: https://github.com/DanNascimento-code/LibreLeaf

#Python #WebScraping #FastAPI #BeautifulSoup #BackendDevelopment #DataEngineering #OpenSource
