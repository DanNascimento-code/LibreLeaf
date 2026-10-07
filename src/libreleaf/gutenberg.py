import re
from datetime import UTC, datetime
from urllib.parse import urlencode, urljoin, urlsplit
from xml.etree import ElementTree

from libreleaf.config import Settings
from libreleaf.errors import ConfigurationError, LibreLeafError
from libreleaf.http import JsonHttpClient
from libreleaf.models import DownloadLink, HarvestPage, PublicDomainBook

BASE_URL = "https://www.gutenberg.org"
SEARCH_URL = f"{BASE_URL}/ebooks/search.opds/"
ATOM = "{http://www.w3.org/2005/Atom}"
ACQUISITION_RELS = {
    "http://opds-spec.org/acquisition",
    "http://opds-spec.org/acquisition/open-access",
}
IMAGE_RELS = {
    "http://opds-spec.org/image",
    "http://opds-spec.org/image/thumbnail",
}


class GutenbergHarvester:
    """Fetch one user-requested page from Project Gutenberg's permitted OPDS feed."""

    def __init__(self, settings: Settings, client: JsonHttpClient | None = None) -> None:
        if not settings.contact_email:
            raise ConfigurationError(
                "Project Gutenberg requires an identifying contact address; "
                "set LIBRELEAF_CONTACT_EMAIL"
            )
        self._owns_client = client is None
        self._client = client or JsonHttpClient(
            user_agent=f"LibreLeaf/0.4 (contact={settings.contact_email})",
            timeout=settings.timeout,
            max_retries=settings.max_retries,
            minimum_interval=2.0,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def search(self, query: str = "", *, page_url: str | None = None) -> HarvestPage:
        url = _validated_feed_url(page_url) if page_url else _search_url(query)
        xml, _headers = self._client.get_text(url)
        return parse_opds(xml, url)


def parse_opds(xml: str, source_url: str) -> HarvestPage:
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as error:
        raise LibreLeafError("Project Gutenberg returned malformed OPDS XML") from error
    books = tuple(_parse_entry(entry, source_url) for entry in root.findall(f"{ATOM}entry"))
    return HarvestPage(
        books=books,
        source_url=source_url,
        next_url=_feed_link(root, "next", source_url),
        previous_url=_feed_link(root, "previous", source_url),
        fetched_at=datetime.now(UTC),
    )


def _parse_entry(entry: ElementTree.Element, source_url: str) -> PublicDomainBook:
    entry_id = _text(entry.find(f"{ATOM}id"))
    gutenberg_id = (
        _last_number(entry_id) or _last_number(_entry_link(entry, "alternate")) or "unknown"
    )
    authors = tuple(
        name
        for author in entry.findall(f"{ATOM}author")
        if (name := _text(author.find(f"{ATOM}name")))
    )
    languages = tuple(
        term
        for category in entry.findall(f"{ATOM}category")
        if "language" in category.attrib.get("scheme", "") and (term := category.attrib.get("term"))
    )
    downloads = tuple(
        DownloadLink(link.attrib.get("type", "application/octet-stream"), urljoin(source_url, href))
        for link in entry.findall(f"{ATOM}link")
        if link.attrib.get("rel") in ACQUISITION_RELS and (href := link.attrib.get("href"))
    )
    cover = next(
        (
            urljoin(source_url, href)
            for link in entry.findall(f"{ATOM}link")
            if link.attrib.get("rel") in IMAGE_RELS and (href := link.attrib.get("href"))
        ),
        None,
    )
    information_url = _entry_link(entry, "alternate") or f"{BASE_URL}/ebooks/{gutenberg_id}"
    return PublicDomainBook(
        gutenberg_id=gutenberg_id,
        title=_text(entry.find(f"{ATOM}title")) or "Untitled",
        authors=authors,
        languages=languages,
        summary=_text(entry.find(f"{ATOM}summary")) or None,
        published_at=_text(entry.find(f"{ATOM}updated")) or None,
        information_url=urljoin(source_url, information_url),
        cover_url=cover,
        downloads=downloads,
    )


def _feed_link(root: ElementTree.Element, relation: str, source_url: str) -> str | None:
    for link in root.findall(f"{ATOM}link"):
        if link.attrib.get("rel") == relation and (href := link.attrib.get("href")):
            candidate = urljoin(source_url, href)
            return candidate if _is_allowed_feed_url(candidate) else None
    return None


def _entry_link(entry: ElementTree.Element, relation: str) -> str:
    for link in entry.findall(f"{ATOM}link"):
        if link.attrib.get("rel") == relation and link.attrib.get("href"):
            return str(link.attrib["href"])
    return ""


def _search_url(query: str) -> str:
    cleaned = " ".join(query.split())[:200]
    return f"{SEARCH_URL}?{urlencode({'query': cleaned})}" if cleaned else SEARCH_URL


def _validated_feed_url(url: str) -> str:
    if not _is_allowed_feed_url(url):
        raise LibreLeafError("Refusing a pagination URL outside Project Gutenberg's OPDS feed")
    return url


def _is_allowed_feed_url(url: str) -> bool:
    parsed = urlsplit(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname == "www.gutenberg.org"
        and parsed.path == "/ebooks/search.opds/"
    )


def _text(element: ElementTree.Element | None) -> str:
    return " ".join("".join(element.itertext()).split()) if element is not None else ""


def _last_number(value: str) -> str | None:
    matches = re.findall(r"\d+", value)
    return matches[-1] if matches else None
