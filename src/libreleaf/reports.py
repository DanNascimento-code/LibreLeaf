# ruff: noqa: E501

from html import escape
from pathlib import Path

from libreleaf.models import Book, ComparisonResult, Offer, PublicDomainBook

STYLE = """
:root{color-scheme:light;--ink:#17352d;--muted:#5f6f69;--leaf:#287a55;--pale:#eef7f1;
--line:#d8e5dd;--paper:#fffdf8;--amber:#fff1c7}*{box-sizing:border-box}body{margin:0;
font:16px/1.55 system-ui,-apple-system,Segoe UI,sans-serif;color:var(--ink);background:var(--paper)}
main{max-width:1100px;margin:auto;padding:48px 24px 80px}header{border-bottom:1px solid var(--line);
margin-bottom:32px;padding-bottom:20px}.eyebrow{text-transform:uppercase;letter-spacing:.13em;color:var(--leaf);
font-weight:700;font-size:.78rem}h1{font:700 clamp(2rem,5vw,4rem)/1.05 Georgia,serif;margin:.25rem 0}
h2{font:700 1.45rem/1.2 Georgia,serif}.lede,.meta{color:var(--muted)}.grid{display:grid;
grid-template-columns:repeat(auto-fit,minmax(245px,1fr));gap:18px}.card{border:1px solid var(--line);
border-radius:16px;padding:20px;background:white;box-shadow:0 8px 24px #17352d0a}.book{display:grid;
grid-template-columns:72px 1fr;gap:14px}.cover{width:72px;height:108px;object-fit:cover;background:var(--pale);
border-radius:5px}.tag{display:inline-block;background:var(--pale);border-radius:99px;padding:3px 9px;
margin:2px;font-size:.76rem}.price{font:700 1.55rem Georgia,serif}.unknown{background:var(--amber);
padding:8px 10px;border-radius:8px;font-size:.86rem}a{color:var(--leaf);font-weight:650}table{width:100%;
border-collapse:collapse;background:white}th,td{text-align:left;padding:12px;border-bottom:1px solid var(--line);
vertical-align:top}th{font-size:.78rem;text-transform:uppercase;letter-spacing:.06em}.status{margin-top:32px}
footer{margin-top:48px;color:var(--muted);font-size:.85rem}@media(max-width:720px){table{display:block;
overflow-x:auto}main{padding:28px 16px}}
"""


def write_discovery_report(books: list[Book], query: str, market: str, path: Path) -> None:
    cards = "".join(_book_card(book, market) for book in books)
    body = f"""
    <header><div class="eyebrow">LibreLeaf · Discover. Compare. Read.</div>
    <h1>Books for “{escape(query)}”</h1>
    <p class="lede">{len(books)} Open Library results · comparison market {escape(market)}</p></header>
    <section class="grid">{cards or "<p>No books found.</p>"}</section>
    <footer>Discovery metadata comes from Open Library. An ISBN identifies an edition; verify the
    desired format before comparing prices.</footer>"""
    _write_page("LibreLeaf discovery", body, path)


def write_comparison_report(result: ComparisonResult, path: Path) -> None:
    rows = "".join(_offer_row(offer) for offer in result.offers)
    statuses = "".join(
        f"<li><strong>{escape(status.name)}</strong>: {escape(status.reason)}</li>"
        for status in result.provider_statuses
    )
    identity = (
        f"<h2>{escape(result.book.title)}</h2>"
        f"<p>{escape(', '.join(result.book.authors) or 'Author unknown')} · "
        f"{escape(result.book.publisher or 'Publisher unknown')} · "
        f"{escape(result.book.publish_date or 'Date unknown')}</p>"
        f'<p><a href="{escape(result.book.information_url)}">Catalog record</a></p>'
        if result.book
        else "<p>Valid ISBN, but no Open Library edition record was found.</p>"
    )
    searches = "".join(
        f'<li><a href="{escape(link.url)}">Search {escape(link.name)}</a> '
        "(unverified store result)</li>"
        for link in result.store_searches
    )
    body = f"""
    <header><div class="eyebrow">LibreLeaf · Price comparison</div>
    <h1>ISBN {escape(result.isbn13)}</h1>
    <p class="lede">Market {escape(result.market)} · checked
    {escape(result.compared_at.astimezone().strftime("%Y-%m-%d %H:%M %Z"))}</p></header>
    <p class="unknown">A known total is shown only when the provider reports shipping. Compare
    format and condition before deciding; prices may change at checkout.</p>
    <section class="card">{identity}</section>
    <table><thead><tr><th>Seller</th><th>Edition</th><th>Item</th><th>Shipping</th>
    <th>Known total</th><th>Availability</th><th>Link</th></tr></thead>
    <tbody>{rows or '<tr><td colspan="7">No exact-ISBN offers were returned.</td></tr>'}</tbody></table>
    <section class="status"><h2>Provider status</h2><ul>{statuses}</ul></section>
    <section class="status"><h2>Manual store searches</h2><ul>{searches}</ul>
    <p class="meta">These links are not verified prices. Confirm the exact ISBN on the store.</p></section>
    <footer>LibreLeaf compares exact ISBN matches from authorized APIs. It does not bypass storefront
    protections, and “no result” does not mean a book is unavailable everywhere.</footer>"""
    _write_page(f"LibreLeaf comparison {result.isbn13}", body, path)


def write_harvest_report(
    books: tuple[PublicDomainBook, ...], query: str, next_url: str | None, path: Path
) -> None:
    cards = "".join(_public_domain_card(book) for book in books)
    pagination = (
        "A next feed page is available. Request it explicitly with --page-url; LibreLeaf does not "
        "auto-crawl it."
        if next_url
        else "No next feed page was provided."
    )
    body = f"""
    <header><div class="eyebrow">LibreLeaf · Ethical feed harvester</div>
    <h1>Public-domain books for “{escape(query or "recent catalog")}”</h1>
    <p class="lede">{len(books)} Project Gutenberg OPDS entries · one user-requested page</p></header>
    <p class="unknown">{escape(pagination)}</p>
    <section class="grid">{cards or "<p>No books found.</p>"}</section>
    <footer>Catalog metadata comes from Project Gutenberg's machine-readable OPDS feed. Check the
    copyright law that applies where you live before downloading or redistributing a title.</footer>"""
    _write_page("LibreLeaf public-domain harvest", body, path)


def _book_card(book: Book, market: str) -> str:
    cover = (
        f'<img class="cover" src="{escape(book.cover_url)}" alt="">'
        if book.cover_url
        else '<div class="cover"></div>'
    )
    authors = ", ".join(book.authors) or "Unknown author"
    compare = (
        f"<code>libreleaf compare {book.isbn13} --market {market}</code>"
        if book.isbn13
        else "No validated ISBN-13 in this result"
    )
    link = (
        f'<a href="{escape(book.information_url)}">Open Library</a>' if book.information_url else ""
    )
    return f"""<article class="card book">{cover}<div><h2>{escape(book.title)}</h2>
    <p class="meta">{escape(authors)} · {book.first_publish_year or "Year unknown"}</p>
    <span class="tag">{escape(book.ebook_access)}</span><span class="tag">{book.edition_count} editions</span>
    <p>{escape(compare)}</p>{link}</div></article>"""


def _offer_row(offer: Offer) -> str:
    shipping = (
        _money(offer.shipping_minor, offer.currency)
        if offer.shipping_minor is not None
        else "Unknown"
    )
    total = (
        _money(offer.total_minor, offer.currency)
        if offer.total_minor is not None
        else "Not calculated"
    )
    seller = f"<br><small>{escape(offer.seller)}</small>" if offer.seller else ""
    return f"""<tr><td><strong>{escape(offer.provider)}</strong>{seller}</td>
    <td>{escape(offer.book_format)}<br><small>{escape(offer.condition)}</small></td>
    <td class="price">{_money(offer.item_price_minor, offer.currency)}</td>
    <td>{shipping}</td><td><strong>{total}</strong></td><td>{escape(offer.availability)}</td>
    <td><a href="{escape(offer.purchase_url)}">View offer</a></td></tr>"""


def _public_domain_card(book: PublicDomainBook) -> str:
    cover = (
        f'<img class="cover" src="{escape(book.cover_url)}" alt="">'
        if book.cover_url
        else '<div class="cover"></div>'
    )
    authors = ", ".join(book.authors) or "Unknown author"
    downloads = "".join(
        f'<a class="tag" href="{escape(link.url)}">{escape(_format_label(link.media_type))}</a>'
        for link in book.downloads[:4]
    )
    return f"""<article class="card book">{cover}<div><h2>{escape(book.title)}</h2>
    <p class="meta">{escape(authors)} · Gutenberg #{escape(book.gutenberg_id)}</p>
    <p>{escape(book.summary or "")}</p><p>{downloads}</p>
    <a href="{escape(book.information_url)}">Catalog record</a></div></article>"""


def _format_label(media_type: str) -> str:
    lowered = media_type.lower()
    if "epub" in lowered:
        return "EPUB"
    if "html" in lowered:
        return "HTML"
    if "plain" in lowered or "text" in lowered:
        return "Text"
    return media_type.split(";")[0].split("/")[-1].upper()


def _money(value: int | None, currency: str) -> str:
    if value is None:
        return "—"
    symbol = {"BRL": "R$", "USD": "$"}.get(currency, currency)
    return f"{escape(symbol)} {value / 100:,.2f}"


def _write_page(title: str, body: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{escape(title)}</title><style>{STYLE}</style></head><body><main>{body}</main></body></html>"""
    temporary = path.with_suffix(".html.tmp")
    try:
        temporary.write_text(document, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
