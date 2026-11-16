from __future__ import annotations

import io

from conftest import index, make_fetcher, urlset

from sitemap_core import ARTICLE, PAGE, Entry, Filter, Limits, extract, sites_without_articles, write_csv, write_txt
from sitemap_core.export import safe_cell

E = "https://example.com"


def run(routes, inputs, limits=None, calls=None):
    entries: list[Entry] = []
    progress = extract(inputs, make_fetcher(routes, calls), entries.append, limits)
    return entries, progress


def test_index_is_expanded_and_classified():
    routes = {
        f"{E}/sitemap_index.xml": index(f"{E}/post-sitemap.xml", f"{E}/page-sitemap.xml", f"{E}/category-sitemap.xml"),
        f"{E}/post-sitemap.xml": urlset(f"{E}/hello/", f"{E}/world/"),
        f"{E}/page-sitemap.xml": urlset(f"{E}/about/"),
        f"{E}/category-sitemap.xml": urlset(f"{E}/category/news/"),
    }
    entries, progress = run(routes, [f"{E}/sitemap_index.xml"])
    assert {(e.url, e.type) for e in entries} == {
        (f"{E}/hello/", "article"), (f"{E}/world/", "article"),
        (f"{E}/about/", "page"), (f"{E}/category/news/", "taxonomy"),
    }
    assert progress.sitemaps_done == 4 and progress.urls == 4 and not progress.errors
    assert all(e.site == "example.com" and e.lastmod == "2026-01-02" for e in entries)
    assert {s.url: s.count for s in progress.sources}[f"{E}/post-sitemap.xml"] == 2


def test_nested_index_and_duplicates():
    routes = {
        f"{E}/a.xml": index(f"{E}/b.xml", f"{E}/c.xml"),
        f"{E}/b.xml": index(f"{E}/c.xml", f"{E}/d.xml"),
        f"{E}/c.xml": urlset(f"{E}/1", f"{E}/2"),
        f"{E}/d.xml": urlset(f"{E}/2", f"{E}/3"),
    }
    calls: list[str] = []
    entries, _ = run(routes, [f"{E}/a.xml"], calls=calls)
    assert sorted(e.url for e in entries) == [f"{E}/1", f"{E}/2", f"{E}/3"]
    assert calls.count(f"{E}/c.xml") == 1


def test_index_loop_terminates():
    routes = {f"{E}/a.xml": index(f"{E}/b.xml"), f"{E}/b.xml": index(f"{E}/a.xml", f"{E}/c.xml"),
              f"{E}/c.xml": urlset(f"{E}/1")}
    entries, progress = run(routes, [f"{E}/a.xml"])
    assert [e.url for e in entries] == [f"{E}/1"]
    assert progress.sitemaps_done == 3


def test_depth_limit():
    routes = {f"{E}/{i}.xml": index(f"{E}/{i + 1}.xml") for i in range(10)}
    _, progress = run(routes, [f"{E}/0.xml"], Limits(max_depth=3))
    assert [e["code"] for e in progress.errors] == ["too_deep"]
    assert progress.sitemaps_done == 4


def test_failed_child_is_reported_and_others_continue():
    routes = {f"{E}/a.xml": index(f"{E}/ok.xml", f"{E}/gone.xml", f"{E}/blocked.xml"),
              f"{E}/ok.xml": urlset(f"{E}/1"), f"{E}/blocked.xml": (403, b"")}
    entries, progress = run(routes, [f"{E}/a.xml"])
    assert [e.url for e in entries] == [f"{E}/1"]
    assert {e["url"]: e["code"] for e in progress.errors} == {f"{E}/gone.xml": "not_found", f"{E}/blocked.xml": "blocked"}


def test_domain_input_uses_robots_txt():
    routes = {f"{E}/robots.txt": b"User-agent: *\nDisallow:\nSitemap: https://example.com/custom-map.xml\n",
              f"{E}/custom-map.xml": urlset(f"{E}/blog/x/")}
    entries, _ = run(routes, ["example.com"])
    assert [(e.url, e.type) for e in entries] == [(f"{E}/blog/x/", "article")]


def test_domain_input_tries_usual_paths():
    calls: list[str] = []
    routes = {f"{E}/sitemap_index.xml": index(f"{E}/post-sitemap.xml"), f"{E}/post-sitemap.xml": urlset(f"{E}/x/")}
    entries, progress = run(routes, ["https://example.com/"], calls=calls)
    assert [e.url for e in entries] == [f"{E}/x/"]
    assert calls.count(f"{E}/sitemap_index.xml") == 1 and not progress.errors


def test_web_page_input_falls_back_to_discovery():
    routes = {f"{E}/blog/": b"<!doctype html><html></html>", f"{E}/sitemap.xml": urlset(f"{E}/blog/x/")}
    entries, progress = run(routes, [f"{E}/blog/"])
    assert [e.url for e in entries] == [f"{E}/blog/x/"] and not progress.errors


def test_no_sitemap_anywhere():
    entries, progress = run({}, ["example.com"])
    assert not entries and [e["code"] for e in progress.errors] == ["no_sitemap"]


def test_max_urls_truncates():
    routes = {f"{E}/s.xml": urlset(*[f"{E}/{i}" for i in range(50)])}
    entries, progress = run(routes, [f"{E}/s.xml"], Limits(max_urls=20))
    assert len(entries) == 20 and progress.truncated == "max_urls"


def test_max_inputs():
    routes = {f"{E}/{i}.xml": urlset(f"{E}/p{i}") for i in range(5)}
    entries, progress = run(routes, [f"{E}/{i}.xml" for i in range(5)], Limits(max_inputs=2))
    assert len(entries) == 2 and progress.errors[0]["code"] == "too_many_inputs"


def test_several_sites_are_labelled():
    routes = {"https://a.example/sitemap.xml": urlset("https://a.example/blog/1/"),
              "https://www.b.example/sitemap.xml": urlset("https://www.b.example/blog/2/")}
    entries, _ = run(routes, ["https://a.example/sitemap.xml", "https://www.b.example/sitemap.xml"])
    assert [e.site for e in entries] == ["a.example", "b.example"]


def entry(url, type_=ARTICLE, site="example.com", lastmod="2026-03-05T10:00:00+00:00", source="s1"):
    return Entry(site, url, lastmod, source, type_)


def test_filter_types_keywords_dates_sources():
    rows = [entry(f"{E}/blog/a"), entry(f"{E}/blog/TAG/b"), entry(f"{E}/about", PAGE),
            entry(f"{E}/blog/old", lastmod="2020-01-01"), entry(f"{E}/blog/nodate", lastmod=""),
            entry(f"{E}/blog/other-source", source="s2")]
    assert len(list(Filter().apply(rows))) == 5
    assert len(list(Filter(types=None).apply(rows))) == 6
    assert [e.url for e in Filter(include=("/about", "old")).apply(rows)] == [f"{E}/blog/old"]
    assert f"{E}/blog/TAG/b" not in [e.url for e in Filter(exclude=("/tag/",)).apply(rows)]
    dated = [e.url for e in Filter(date_from="2026-01-01", date_to="2026-12-31").apply(rows)]
    assert f"{E}/blog/old" not in dated and f"{E}/blog/nodate" not in dated and f"{E}/blog/a" in dated
    assert f"{E}/blog/other-source" not in [e.url for e in Filter(skip_sources=frozenset({"s2"})).apply(rows)]


def test_fallback_lists_everything_for_sites_without_articles():
    counts = {"a.example": {"other": 3, "page": 1}, "b.example": {"article": 2, "page": 5}, "c.example": {}}
    fallback = sites_without_articles(counts)
    assert fallback == frozenset({"a.example"})
    rows = [entry("https://a.example/x", "other", site="a.example"), entry("https://b.example/y", PAGE, site="b.example")]
    assert [e.site for e in Filter(fallback_sites=fallback).apply(rows)] == ["a.example"]


def test_csv_output_and_formula_injection():
    assert safe_cell("=HYPERLINK(1)") == "'=HYPERLINK(1)"
    assert safe_cell("+1") == "'+1" and safe_cell("-1") == "'-1" and safe_cell("@x") == "'@x"
    assert safe_cell("https://example.com/") == "https://example.com/"
    out = io.StringIO()
    n = write_csv([entry(f"{E}/a,b"), entry(f"{E}/c", lastmod="=cmd|' /C calc'!A0")], out, "zh")
    lines = out.getvalue().split("\r\n")
    assert n == 2
    assert lines[0] == "site,url,lastmod,source_sitemap,type"
    assert lines[1] == 'example.com,"https://example.com/a,b",2026-03-05T10:00:00+00:00,s1,文章'
    assert ",'=cmd|" in lines[2]


def test_txt_output():
    out = io.StringIO()
    assert write_txt([entry(f"{E}/a"), entry(f"{E}/b")], out) == 2
    assert out.getvalue() == f"{E}/a\n{E}/b\n"
