import json
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from pathlib import Path

from libreleaf.models import Book, Offer, PublicDomainBook

SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    book_key TEXT PRIMARY KEY,
    isbn13 TEXT,
    title TEXT NOT NULL,
    authors_json TEXT NOT NULL,
    first_publish_year INTEGER,
    languages_json TEXT NOT NULL,
    subjects_json TEXT NOT NULL,
    edition_count INTEGER NOT NULL,
    ebook_access TEXT NOT NULL,
    cover_url TEXT,
    information_url TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS offer_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    market TEXT NOT NULL,
    external_id TEXT NOT NULL,
    isbn13 TEXT NOT NULL,
    title TEXT NOT NULL,
    book_format TEXT NOT NULL,
    condition TEXT NOT NULL,
    item_price_minor INTEGER NOT NULL CHECK (item_price_minor >= 0),
    shipping_minor INTEGER CHECK (shipping_minor >= 0),
    currency TEXT NOT NULL,
    availability TEXT NOT NULL,
    seller TEXT,
    purchase_url TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    UNIQUE(provider, market, external_id, observed_at)
);

CREATE INDEX IF NOT EXISTS idx_offer_history
ON offer_observations(isbn13, market, observed_at);

CREATE TABLE IF NOT EXISTS public_domain_books (
    gutenberg_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    authors_json TEXT NOT NULL,
    languages_json TEXT NOT NULL,
    summary TEXT,
    published_at TEXT,
    information_url TEXT NOT NULL,
    cover_url TEXT,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS public_domain_downloads (
    gutenberg_id TEXT NOT NULL,
    media_type TEXT NOT NULL,
    url TEXT NOT NULL,
    PRIMARY KEY(gutenberg_id, media_type, url),
    FOREIGN KEY(gutenberg_id) REFERENCES public_domain_books(gutenberg_id)
);
"""


class LibreLeafRepository:
    """SQLite cache and append-only price observation history."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def save_books(self, books: Iterable[Book]) -> int:
        rows = [_book_row(book) for book in books]
        with closing(self._connect()) as connection, connection:
            connection.executemany(
                """
                INSERT INTO books VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(book_key) DO UPDATE SET
                    isbn13=excluded.isbn13,
                    title=excluded.title,
                    authors_json=excluded.authors_json,
                    first_publish_year=excluded.first_publish_year,
                    languages_json=excluded.languages_json,
                    subjects_json=excluded.subjects_json,
                    edition_count=excluded.edition_count,
                    ebook_access=excluded.ebook_access,
                    cover_url=excluded.cover_url,
                    information_url=excluded.information_url
                """,
                rows,
            )
        return len(rows)

    def save_offers(self, offers: Iterable[Offer]) -> int:
        rows = [_offer_row(offer) for offer in offers]
        with closing(self._connect()) as connection, connection:
            connection.executemany(
                """
                INSERT OR IGNORE INTO offer_observations (
                    provider, market, external_id, isbn13, title, book_format, condition,
                    item_price_minor, shipping_minor, currency, availability, seller,
                    purchase_url, observed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def save_public_domain_books(self, books: Iterable[PublicDomainBook], fetched_at: str) -> int:
        items = list(books)
        with closing(self._connect()) as connection, connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executemany(
                """
                INSERT INTO public_domain_books VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(gutenberg_id) DO UPDATE SET
                    title=excluded.title,
                    authors_json=excluded.authors_json,
                    languages_json=excluded.languages_json,
                    summary=excluded.summary,
                    published_at=excluded.published_at,
                    information_url=excluded.information_url,
                    cover_url=excluded.cover_url,
                    fetched_at=excluded.fetched_at
                """,
                [_public_book_row(book, fetched_at) for book in items],
            )
            for book in items:
                connection.execute(
                    "DELETE FROM public_domain_downloads WHERE gutenberg_id = ?",
                    (book.gutenberg_id,),
                )
                connection.executemany(
                    "INSERT INTO public_domain_downloads VALUES (?, ?, ?)",
                    [(book.gutenberg_id, link.media_type, link.url) for link in book.downloads],
                )
        return len(items)

    def counts(self) -> tuple[int, int]:
        with closing(self._connect()) as connection:
            books = connection.execute("SELECT COUNT(*) FROM books").fetchone()[0]
            offers = connection.execute("SELECT COUNT(*) FROM offer_observations").fetchone()[0]
        return int(books), int(offers)

    def _connect(self) -> sqlite3.Connection:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._database_path)
        connection.executescript(SCHEMA)
        return connection


def _book_row(book: Book) -> tuple[object, ...]:
    key = book.isbn13 or book.information_url or book.title
    return (
        key,
        book.isbn13,
        book.title,
        json.dumps(book.authors, ensure_ascii=False),
        book.first_publish_year,
        json.dumps(book.languages, ensure_ascii=False),
        json.dumps(book.subjects, ensure_ascii=False),
        book.edition_count,
        book.ebook_access,
        book.cover_url,
        book.information_url,
    )


def _offer_row(offer: Offer) -> tuple[object, ...]:
    return (
        offer.provider,
        offer.market,
        offer.external_id,
        offer.isbn13,
        offer.title,
        offer.book_format,
        offer.condition,
        offer.item_price_minor,
        offer.shipping_minor,
        offer.currency,
        offer.availability,
        offer.seller,
        offer.purchase_url,
        offer.observed_at.isoformat(),
    )


def _public_book_row(book: PublicDomainBook, fetched_at: str) -> tuple[object, ...]:
    return (
        book.gutenberg_id,
        book.title,
        json.dumps(book.authors, ensure_ascii=False),
        json.dumps(book.languages, ensure_ascii=False),
        book.summary,
        book.published_at,
        book.information_url,
        book.cover_url,
        fetched_at,
    )
