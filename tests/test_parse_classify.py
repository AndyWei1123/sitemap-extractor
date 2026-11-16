from __future__ import annotations

import pytest
from conftest import index, urlset

from sitemap_core.classify import (ARTICLE, OTHER, PAGE, PRODUCT, TAXONOMY, classify, classify_sitemap_name,
                                   classify_url_path)
from sitemap_core.parse import NotSitemapError, parse_sitemap


def test_urlset_with_lastmod():
    parsed = parse_sitemap(urlset("https://example.com/a", "https://example.com/b"))
    assert parsed.kind == "urlset"
    assert parsed.entries == [("https://example.com/a", "2026-01-02"), ("https://example.com/b", "2026-01-02")]


def test_index():
    parsed = parse_sitemap(index("https://example.com/post-sitemap.xml"))
    assert parsed.kind == "index"
    assert parsed.entries == [("https://example.com/post-sitemap.xml", "")]


def test_no_namespace_bom_and_cdata():
    data = b"\xef\xbb\xbf  <urlset><url><loc><![CDATA[ https://example.com/a?x=1&y=2 ]]></loc></url></urlset>"
    assert parse_sitemap(data).entries == [("https://example.com/a?x=1&y=2", "")]


def test_broken_xml_is_recovered():
    data = b'<urlset><url><loc>https://example.com/a</loc></url><url><loc>https://example.com/b</loc>'
    assert [loc for loc, _ in parse_sitemap(data).entries] == ["https://example.com/a", "https://example.com/b"]


def test_unknown_root_falls_back_to_loc_matching():
    data = b"<garbage><loc>https://example.com/a</loc></garbage>"
    assert parse_sitemap(data).entries == [("https://example.com/a", "")]


def test_plain_text_sitemap():
    parsed = parse_sitemap(b"https://example.com/a\nhttps://example.com/b\n\n")
    assert parsed.kind == "urlset" and len(parsed.entries) == 2


def test_empty_urlset_is_valid():
    assert parse_sitemap(b"<urlset></urlset>").entries == []


@pytest.mark.parametrize("data", [
    b"<!doctype html><html><body>hello</body></html>",
    b"<html><head></head></html>",
    b"just some words, not a sitemap",
    b"",
])
def test_not_a_sitemap(data):
    with pytest.raises(NotSitemapError):
        parse_sitemap(data)


def test_external_entities_are_not_resolved():
    data = (b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]>'
            b"<urlset><url><loc>https://example.com/&e;</loc></url></urlset>")
    entries = parse_sitemap(data).entries
    assert all("root:" not in loc for loc, _ in entries)


@pytest.mark.parametrize("name,expected", [
    ("https://example.com/post-sitemap.xml", ARTICLE),
    ("https://example.com/post-sitemap2.xml", ARTICLE),
    ("https://example.com/wp-sitemap-posts-post-1.xml", ARTICLE),
    ("https://example.com/news-sitemap.xml", ARTICLE),
    ("https://example.com/sitemap_blogs_1.xml", ARTICLE),
    ("https://example.com/page-sitemap.xml", PAGE),
    ("https://example.com/wp-sitemap-posts-page-1.xml", PAGE),
    ("https://example.com/post_tag-sitemap.xml", TAXONOMY),
    ("https://example.com/category-sitemap.xml", TAXONOMY),
    ("https://example.com/wp-sitemap-taxonomies-category-1.xml", TAXONOMY),
    ("https://example.com/wp-sitemap-users-1.xml", TAXONOMY),
    ("https://example.com/product_cat-sitemap.xml", TAXONOMY),
    ("https://example.com/product-sitemap.xml", PRODUCT),
    ("https://example.com/sitemap_products_1.xml?from=1&to=9", PRODUCT),
    ("https://example.com/attachment-sitemap.xml", OTHER),
    ("https://example.com/sitemap.xml", None),
    ("https://example.com/sitemap.xml?page=2", None),
    ("https://example.com/homepage-sitemap.xml", None),
])
def test_classify_sitemap_name(name, expected):
    assert classify_sitemap_name(name) == expected


@pytest.mark.parametrize("url,expected", [
    ("https://example.com/", PAGE),
    ("https://example.com", PAGE),
    ("https://example.com/blog/", PAGE),
    ("https://example.com/blog/hello-world/", ARTICLE),
    ("https://example.com/2026/03/hello/", ARTICLE),
    ("https://example.com/category/news/", TAXONOMY),
    ("https://example.com/tag/x/", TAXONOMY),
    ("https://example.com/blog/page/2/", TAXONOMY),
    ("https://example.com/products/shoe", PRODUCT),
    ("https://example.com/files/report.pdf", OTHER),
    ("https://example.com/about-us/", OTHER),
])
def test_classify_url_path(url, expected):
    assert classify_url_path(url) == expected


def test_sitemap_name_wins_over_path():
    assert classify("https://example.com/about/", ARTICLE) == ARTICLE
    assert classify("https://example.com/blog/x/", None) == ARTICLE
