# LinkedIn Project - LibreLeaf

## Project name

LibreLeaf - Ethical Book Price Web Scraper

## Short description

LibreLeaf is an ethical web scraper and focused crawler that identifies books by ISBN and compares
verified prices from public bookstore pages across Brazil, the United States, and Argentina. I built
the complete product using Python, FastAPI, Beautiful Soup, HTTPX, Jinja, SQLite, a multilingual user
interface, resilient request handling, exact-edition validation, automated tests, and a production
deployment on Vercel.

## Full project description

I developed LibreLeaf to solve a subtle price-comparison problem: books with the same title are not
necessarily the same product. Different translations, formats, revisions, and editions can have
different ISBNs and significantly different prices.

The application accepts an ISBN - the preferred input - or a book title. It resolves a specific
edition, collects public offers from supported bookstores, verifies the ISBN found in the returned
product data, normalizes monetary values, and presents comparable results without treating unknown
shipping costs as free.

The scraping pipeline uses a descriptive user agent, request pacing, timeouts, retries, controlled
discovery paths, and partial-failure handling. It does not bypass authentication, CAPTCHAs, paywalls,
or blocked search routes. The frontend supports English, Brazilian Portuguese, and Latin American
Spanish, with a literary dark-mode design as the default.

LibreLeaf is more than a standalone scraping script. It includes a reusable provider architecture,
a FastAPI web application, a command-line interface, normalized domain models, SQLite observation
history, report exports, internationalization, automated tests, and a serverless production setup.

## Key outcomes

- Built a real HTML and JSON-LD scraping pipeline for public bookstore pages.
- Prevented invalid price comparisons through exact ISBN and edition validation.
- Added request pacing, retries, timeouts, source attribution, and partial-failure handling.
- Created a responsive interface in English, Portuguese, and Spanish.
- Reached 51 automated tests and approximately 89% statement coverage.
- Deployed the production application on Vercel.

## Skills

Python, FastAPI, Web Scraping, Web Crawling, Beautiful Soup, HTTPX, Jinja2, HTML, CSS, SQLite,
Pytest, Data Validation, Data Modeling, Internationalization, REST APIs, Serverless Deployment,
Vercel, Git, and GitHub

## Project URL

https://libreleaf-books.vercel.app

## Source code

https://github.com/DanNascimento-code/LibreLeaf

## Suggested LinkedIn post

I built LibreLeaf, an ethical web scraper for exact-edition book price comparison.

The main challenge was not simply extracting prices. A book title can represent multiple
translations, formats, revisions, and editions, which means a title-only comparison can produce
misleading results.

LibreLeaf solves this by using ISBN-level validation. It accepts an ISBN or book title, resolves one
specific edition, checks store results against that ISBN, and normalizes real public prices without
hiding unknown shipping costs.

Technical highlights:

- Python, FastAPI, Beautiful Soup, HTTPX, Jinja, and SQLite
- Real HTML and JSON-LD extraction from public bookstore pages
- Exact ISBN and edition validation
- Controlled crawling with pacing, retries, timeouts, and partial-failure handling
- English, Portuguese, and Spanish user interface
- 51 automated tests and approximately 89% statement coverage
- Production deployment on Vercel

Live application: https://libreleaf-books.vercel.app

Source code: https://github.com/DanNascimento-code/LibreLeaf

#Python #WebScraping #WebCrawling #FastAPI #BeautifulSoup #BackendDevelopment #DataEngineering
#SoftwareEngineering #OpenSource
