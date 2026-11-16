"""Command-line entry: python cli.py https://example.com/sitemap.xml"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from collections import defaultdict
from pathlib import Path

from sitemap_core import (ARTICLE, TYPES, Entry, FetchConfig, Fetcher, Filter, Limits, extract,
                          sites_without_articles, write_csv, write_txt)
from sitemap_core.fetch import DEFAULT_USER_AGENT
from sitemap_core.messages import TRUNCATED_MESSAGES, error_text


def read_inputs(values: list[str]) -> list[str]:
    """Each value is a URL/domain, or a path to a text file with one per line."""
    inputs: list[str] = []
    for value in values:
        path = Path(value)
        if not value.lower().startswith(("http://", "https://")) and path.is_file():
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    inputs.append(line)
        else:
            inputs.append(value)
    return inputs


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    ap = argparse.ArgumentParser(description="Extract article URLs from XML sitemaps.")
    ap.add_argument("inputs", nargs="+", help="sitemap URLs, domains, or a .txt file with one per line")
    ap.add_argument("-o", "--output", help="output file (default: <site>_<date>.csv)")
    ap.add_argument("--format", choices=("csv", "txt"), default="csv")
    ap.add_argument("--all", action="store_true", help="keep every page type, not only articles")
    ap.add_argument("--types", help=f"comma-separated page types to keep: {','.join(TYPES)}")
    ap.add_argument("--include", action="append", default=[], help="URL must contain this (repeatable)")
    ap.add_argument("--exclude", action="append", default=[], help="URL must not contain this (repeatable)")
    ap.add_argument("--from", dest="date_from", default="", help="lastmod on or after YYYY-MM-DD")
    ap.add_argument("--to", dest="date_to", default="", help="lastmod on or before YYYY-MM-DD")
    ap.add_argument("--split", action="store_true", help="one file per site instead of one merged file")
    ap.add_argument("--lang", choices=("zh", "en"), default="zh")
    ap.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    ap.add_argument("--block-private", action="store_true", help="refuse internal/private addresses")
    args = ap.parse_args(argv)

    if args.all:
        types = None
    elif args.types:
        types = frozenset(t.strip() for t in args.types.split(",") if t.strip())
        unknown = types - set(TYPES)
        if unknown:
            ap.error(f"unknown type(s): {', '.join(sorted(unknown))}")
    else:
        types = frozenset({ARTICLE})

    inputs = read_inputs(args.inputs)
    entries: list[Entry] = []
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def on_entry(entry: Entry) -> None:
        entries.append(entry)
        counts[entry.site][entry.type] += 1

    fetcher = Fetcher(FetchConfig(allow_private=not args.block_private, user_agent=args.user_agent))
    try:
        progress = extract(inputs, fetcher, on_entry, Limits())
    finally:
        fetcher.close()

    fallback = sites_without_articles(counts) if types == frozenset({ARTICLE}) else frozenset()
    flt = Filter(types=types, include=tuple(args.include), exclude=tuple(args.exclude),
                 date_from=args.date_from, date_to=args.date_to, fallback_sites=fallback)
    kept = list(flt.apply(entries))

    zh = args.lang == "zh"
    for err in progress.errors:
        print(f"[!] {err['url']}: {error_text(err['code'], args.lang)}", file=sys.stderr)
    if progress.truncated:
        print(f"[!] {TRUNCATED_MESSAGES[args.lang].get(progress.truncated, progress.truncated)}", file=sys.stderr)
    for site in sorted(fallback):
        print((f"[i] {site}: 無法自動分辨文章，已列出全部網址" if zh
               else f"[i] {site}: could not tell articles apart; listing every URL"), file=sys.stderr)

    if not kept:
        print("沒有符合條件的網址" if zh else "No matching URLs", file=sys.stderr)
        return 1

    today = dt.date.today().isoformat()
    groups: dict[str, list[Entry]] = defaultdict(list)
    if args.split:
        for e in kept:
            groups[e.site].append(e)
    else:
        sites = {e.site for e in kept}
        name = next(iter(sites)) if len(sites) == 1 else "sitemap-urls"
        groups[name] = kept

    for name, rows in groups.items():
        if args.output and not args.split:
            path = Path(args.output)
        else:
            path = Path(f"{name}_{today}.{args.format}")
        if args.format == "csv":
            with path.open("w", encoding="utf-8-sig", newline="") as fh:
                write_csv(rows, fh, args.lang)
        else:
            with path.open("w", encoding="utf-8", newline="\n") as fh:
                write_txt(rows, fh)
        print(f"{len(rows)} {'個網址' if zh else 'URLs'} -> {path}")
    print((f"共抓取 {progress.sitemaps_done} 個 sitemap、{progress.urls} 個不重複網址" if zh
           else f"Fetched {progress.sitemaps_done} sitemaps, {progress.urls} unique URLs"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
