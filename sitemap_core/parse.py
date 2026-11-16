"""Parse sitemap bodies: XML urlsets, sitemap indexes and plain-text sitemaps."""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

from lxml import etree

LOC_RE = re.compile(rb"<(?:\w+:)?loc\b[^>]*>\s*(?:<!\[CDATA\[)?\s*(.*?)\s*(?:\]\]>)?\s*</(?:\w+:)?loc\s*>",
                    re.IGNORECASE | re.DOTALL)
BOM = b"\xef\xbb\xbf"


class NotSitemapError(ValueError):
    """The content is not a sitemap."""


@dataclass
class Parsed:
    kind: str  # "index" or "urlset"
    entries: list[tuple[str, str]] = field(default_factory=list)  # (loc, lastmod)


def _local(tag) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1].lower()


def _clean_loc(value: str | None) -> str:
    loc = (value or "").strip()
    return loc if loc.lower().startswith(("http://", "https://")) else ""


def _parse_text(data: bytes) -> Parsed:
    lines = [ln.strip() for ln in data.decode("utf-8", errors="replace").splitlines()]
    lines = [ln for ln in lines if ln]
    urls = [ln for ln in lines if _clean_loc(ln) and " " not in ln]
    if not urls or len(urls) * 2 < len(lines):
        raise NotSitemapError("not a sitemap")
    return Parsed("urlset", [(u, "") for u in urls])


def _parse_regex(data: bytes) -> Parsed:
    locs = []
    for raw in LOC_RE.findall(data):
        loc = _clean_loc(html.unescape(raw.decode("utf-8", errors="replace")))
        if loc:
            locs.append((loc, ""))
    if not locs:
        raise NotSitemapError("not a sitemap")
    kind = "index" if b"<sitemapindex" in data[:4000].lower() else "urlset"
    return Parsed(kind, locs)


def parse_sitemap(data: bytes) -> Parsed:
    """Parse sitemap bytes. Raises NotSitemapError when the content is something else."""
    data = data.lstrip()
    if data.startswith(BOM):
        data = data[len(BOM):].lstrip()
    if not data:
        raise NotSitemapError("empty response")
    if not data.startswith(b"<"):
        return _parse_text(data)

    parser = etree.XMLParser(recover=True, resolve_entities=False, no_network=True,
                             remove_comments=True, remove_pis=True)
    try:
        root = etree.fromstring(data, parser)
    except (etree.XMLSyntaxError, ValueError):
        root = None
    if root is None:
        return _parse_regex(data)

    name = _local(root.tag)
    if name == "html":
        raise NotSitemapError("this is a web page, not a sitemap")
    if name not in ("sitemapindex", "urlset"):
        return _parse_regex(data)

    item_tag = "sitemap" if name == "sitemapindex" else "url"
    entries: list[tuple[str, str]] = []
    for item in root:
        if _local(item.tag) != item_tag:
            continue
        loc, lastmod = "", ""
        for child in item:
            child_name = _local(child.tag)
            if child_name == "loc" and not loc:
                loc = _clean_loc(child.text)
            elif child_name == "lastmod" and not lastmod:
                lastmod = (child.text or "").strip()
        if loc:
            entries.append((loc, lastmod))
    if not entries:
        # Badly broken XML can lose its structure in recovery; fall back to text matching.
        try:
            return _parse_regex(data)
        except NotSitemapError:
            pass  # a valid but empty sitemap
    return Parsed("index" if name == "sitemapindex" else "urlset", entries)
