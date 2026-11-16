"""Walk sitemaps (expanding indexes) and emit classified, de-duplicated URL entries."""
from __future__ import annotations

import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import urlsplit

from .classify import classify, classify_sitemap_name
from .fetch import FetchError, Fetcher
from .parse import NotSitemapError, Parsed, parse_sitemap

CANDIDATE_PATHS = ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml")
ROBOTS_SITEMAP_RE = re.compile(r"^\s*sitemap\s*:\s*(\S+)", re.IGNORECASE | re.MULTILINE)
BATCH = 8


@dataclass
class Limits:
    max_inputs: int = 200
    max_urls: int = 5_000_000
    max_seconds: float | None = None
    max_depth: int = 5
    max_sitemaps: int = 20_000


@dataclass
class Entry:
    site: str
    url: str
    lastmod: str
    source: str
    type: str


@dataclass
class SourceInfo:
    url: str
    site: str
    count: int
    type: str | None  # type guessed from the sitemap's name, None when unknown


@dataclass
class Progress:
    sitemaps_done: int = 0
    sitemaps_total: int = 0
    urls: int = 0
    errors: list[dict] = field(default_factory=list)
    sources: list[SourceInfo] = field(default_factory=list)
    truncated: str | None = None  # "max_urls", "deadline", "max_sitemaps" or None
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add_error(self, url: str, code: str, message: str) -> None:
        with self.lock:
            self.errors.append({"url": url, "code": code, "message": message})


def normalize_input(raw: str) -> str:
    """Turn user input into a URL: 'example.com' -> 'https://example.com'."""
    value = raw.strip()
    if not value:
        return ""
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", value):
        value = "https://" + value
    return value


def site_of(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def _is_root(url: str) -> bool:
    parts = urlsplit(url)
    return parts.path in ("", "/") and not parts.query


class _Run:
    def __init__(self, fetcher: Fetcher, limits: Limits, on_entry: Callable[[Entry], None],
                 progress: Progress, cancel: threading.Event | None):
        self.fetcher = fetcher
        self.limits = limits
        self.on_entry = on_entry
        self.progress = progress
        self.cancel = cancel
        self.deadline = time.monotonic() + limits.max_seconds if limits.max_seconds else None
        self.seen_sitemaps: set[str] = set()
        self.seen_urls: set[str] = set()
        self.cache: dict[str, Parsed] = {}

    def stopped(self) -> bool:
        if self.progress.truncated:
            return True
        if self.cancel is not None and self.cancel.is_set():
            self.progress.truncated = "cancelled"
        elif self.deadline is not None and time.monotonic() >= self.deadline:
            self.progress.truncated = "deadline"
        return self.progress.truncated is not None

    def load(self, url: str) -> Parsed:
        cached = self.cache.pop(url, None)
        if cached is not None:
            return cached
        return parse_sitemap(self.fetcher.fetch(url, deadline=self.deadline))

    def try_load(self, url: str) -> Parsed | Exception:
        try:
            return self.load(url)
        except (FetchError, NotSitemapError) as exc:
            return exc

    def discover(self, any_url: str) -> list[str]:
        """Find sitemap URLs for a site: robots.txt first, then the usual paths."""
        origin = _origin(any_url)
        try:
            robots = self.fetcher.fetch(origin + "/robots.txt", deadline=self.deadline)
            found = [u for u in ROBOTS_SITEMAP_RE.findall(robots.decode("utf-8", errors="replace"))
                     if u.lower().startswith(("http://", "https://"))]
            if found:
                return list(dict.fromkeys(found))
        except FetchError:
            pass
        for path in CANDIDATE_PATHS:
            candidate = origin + path
            if candidate in self.seen_sitemaps:
                continue
            result = self.try_load(candidate)
            if isinstance(result, Parsed):
                self.cache[candidate] = result
                return [candidate]
        return []

    def record_failure(self, url: str, exc: Exception) -> None:
        if isinstance(exc, FetchError):
            self.progress.add_error(url, exc.code, exc.message)
        else:
            self.progress.add_error(url, "not_sitemap", str(exc))

    def run_input(self, raw: str) -> None:
        start = normalize_input(raw)
        if not start:
            return
        site = site_of(start)
        if not site:
            self.progress.add_error(raw, "bad_input", "not a valid URL")
            return

        tried_discovery = False
        if _is_root(start):
            tried_discovery = True
            level = self.discover(start)
            if not level:
                self.progress.add_error(start, "no_sitemap", "no sitemap found for this site")
                return
        else:
            level = [start]

        depth = 0
        with ThreadPoolExecutor(max_workers=2) as pool:
            while level and not self.stopped():
                level = [u for u in dict.fromkeys(level) if u not in self.seen_sitemaps]
                self.seen_sitemaps.update(level)
                with self.progress.lock:
                    self.progress.sitemaps_total += len(level)
                next_level: list[str] = []
                for i in range(0, len(level), BATCH):
                    if self.stopped():
                        break
                    batch = level[i:i + BATCH]
                    for url, result in zip(batch, pool.map(self.try_load, batch)):
                        with self.progress.lock:
                            self.progress.sitemaps_done += 1
                        if isinstance(result, Exception):
                            if (depth == 0 and not tried_discovery
                                    and isinstance(result, NotSitemapError)):
                                tried_discovery = True
                                found = self.discover(url)
                                if found:
                                    next_level.extend(found)
                                    continue
                            self.record_failure(url, result)
                            continue
                        if result.kind == "index":
                            if depth + 1 > self.limits.max_depth:
                                self.progress.add_error(url, "too_deep", "sitemap index nesting is too deep")
                                continue
                            next_level.extend(loc for loc, _ in result.entries)
                        else:
                            self.emit(site, url, result)
                level = next_level
                depth += 1
                if len(self.seen_sitemaps) + len(level) > self.limits.max_sitemaps:
                    self.progress.truncated = "max_sitemaps"

    def emit(self, site: str, source: str, parsed: Parsed) -> None:
        source_type = classify_sitemap_name(source)
        count = 0
        for loc, lastmod in parsed.entries:
            if loc in self.seen_urls:
                continue
            if len(self.seen_urls) >= self.limits.max_urls:
                self.progress.truncated = "max_urls"
                break
            self.seen_urls.add(loc)
            self.on_entry(Entry(site, loc, lastmod, source, classify(loc, source_type)))
            count += 1
        with self.progress.lock:
            self.progress.urls = len(self.seen_urls)
            self.progress.sources.append(SourceInfo(source, site, count, source_type))


def extract(inputs: list[str], fetcher: Fetcher, on_entry: Callable[[Entry], None],
            limits: Limits | None = None, progress: Progress | None = None,
            cancel: threading.Event | None = None) -> Progress:
    """Extract every URL reachable from the given sitemap URLs or domains.

    `on_entry` is called once per unique URL. Returns the Progress with counts and errors.
    """
    limits = limits or Limits()
    progress = progress or Progress()
    run = _Run(fetcher, limits, on_entry, progress, cancel)
    cleaned = [raw for raw in dict.fromkeys(s.strip() for s in inputs) if raw]
    if len(cleaned) > limits.max_inputs:
        progress.add_error("", "too_many_inputs", f"at most {limits.max_inputs} inputs are allowed")
        cleaned = cleaned[:limits.max_inputs]
    for raw in cleaned:
        if run.stopped():
            break
        run.run_input(raw)
    return progress
