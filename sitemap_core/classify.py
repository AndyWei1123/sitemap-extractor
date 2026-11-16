"""Decide what kind of page a URL is: article, page, product, taxonomy or other."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

ARTICLE, PAGE, PRODUCT, TAXONOMY, OTHER = "article", "page", "product", "taxonomy", "other"
TYPES = (ARTICLE, PAGE, PRODUCT, TAXONOMY, OTHER)

TYPE_LABELS = {
    "zh": {ARTICLE: "文章", PAGE: "一般頁面", PRODUCT: "商品", TAXONOMY: "分類與標籤", OTHER: "未分類"},
    "en": {ARTICLE: "article", PAGE: "page", PRODUCT: "product", TAXONOMY: "taxonomy", OTHER: "unclassified"},
}

# Checked in this order: "post_tag-sitemap.xml" must be taxonomy, "posts-page" must be page.
_NAME_RULES: tuple[tuple[str, frozenset[str]], ...] = (
    (TAXONOMY, frozenset({"category", "categories", "cat", "tag", "tags", "taxonomy", "taxonomies",
                          "author", "authors", "user", "users", "archive", "archives",
                          "collection", "collections"})),
    (PRODUCT, frozenset({"product", "products"})),
    (PAGE, frozenset({"page", "pages"})),
    (OTHER, frozenset({"attachment", "attachments", "image", "images", "video", "videos", "media"})),
    (ARTICLE, frozenset({"post", "posts", "article", "articles", "news", "blog", "blogs",
                         "story", "stories"})),
)

_TAXONOMY_SEGMENTS = frozenset({"category", "categories", "tag", "tags", "author", "authors"})
_PRODUCT_SEGMENTS = frozenset({"product", "products", "shop"})
_ARTICLE_SEGMENTS = frozenset({"blog", "blogs", "news", "article", "articles", "post", "posts",
                               "story", "stories"})
_FILE_EXT_RE = re.compile(r"\.(?:jpe?g|png|gif|webp|svg|avif|pdf|zip|mp4|mp3|docx?|xlsx?|pptx?)$", re.I)
_PAGINATION_RE = re.compile(r"/page/\d+/?$", re.I)
_DATE_PATH_RE = re.compile(r"/(?:19|20)\d{2}/(?:0?[1-9]|1[0-2])(?:/|$)")
_SITEMAP_PAGE_PARAM_RE = re.compile(r"\bpage=\d+", re.I)


def classify_sitemap_name(sitemap_url: str) -> str | None:
    """Guess the page type from a child sitemap's file name, e.g. post-sitemap.xml."""
    parts = urlsplit(sitemap_url)
    name = parts.path.rsplit("/", 1)[-1]
    query = _SITEMAP_PAGE_PARAM_RE.sub("", parts.query)
    tokens = set(re.split(r"[^a-z]+", f"{name} {query}".lower()))
    for page_type, words in _NAME_RULES:
        if tokens & words:
            return page_type
    return None


def classify_url_path(url: str) -> str:
    """Guess the page type from the URL itself. Returns OTHER when it cannot tell."""
    path = urlsplit(url).path
    if path in ("", "/"):
        return PAGE
    if _FILE_EXT_RE.search(path):
        return OTHER
    parts = [seg.lower() for seg in path.split("/") if seg]
    segments = set(parts)
    if segments & _TAXONOMY_SEGMENTS or _PAGINATION_RE.search(path):
        return TAXONOMY
    if segments & _PRODUCT_SEGMENTS:
        return PRODUCT if len(parts) > 1 else PAGE
    if _DATE_PATH_RE.search(path):
        return ARTICLE
    if segments & _ARTICLE_SEGMENTS:
        # "/blog/" alone is the listing page; "/blog/some-post/" is an article.
        return ARTICLE if len(parts) > 1 else PAGE
    return OTHER


def classify(url: str, source_type: str | None) -> str:
    """Layer 1: the child sitemap's name. Layer 2: the URL path."""
    return source_type if source_type is not None else classify_url_path(url)
