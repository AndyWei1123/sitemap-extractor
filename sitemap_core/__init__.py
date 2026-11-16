"""Sitemap Extractor core: fetch sitemaps, expand indexes, classify and export URLs."""
from .classify import ARTICLE, OTHER, PAGE, PRODUCT, TAXONOMY, TYPE_LABELS, TYPES
from .export import Filter, write_csv, write_txt
from .extract import Entry, Limits, Progress, SourceInfo, extract, site_of
from .fetch import FetchConfig, FetchError, Fetcher

__version__ = "0.1.0"

__all__ = [
    "ARTICLE", "OTHER", "PAGE", "PRODUCT", "TAXONOMY", "TYPES", "TYPE_LABELS",
    "Entry", "FetchConfig", "FetchError", "Fetcher", "Filter", "Limits", "Progress",
    "SourceInfo", "extract", "site_of", "write_csv", "write_txt",
]


def sites_without_articles(type_counts_by_site: dict[str, dict[str, int]]) -> frozenset[str]:
    """Sites where nothing was recognised as an article; simple mode lists all their URLs."""
    return frozenset(site for site, counts in type_counts_by_site.items()
                     if sum(counts.values()) > 0 and counts.get(ARTICLE, 0) == 0)
