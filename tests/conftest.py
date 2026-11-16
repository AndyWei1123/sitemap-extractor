from __future__ import annotations

import ipaddress
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sitemap_core import FetchConfig, Fetcher  # noqa: E402

NS = 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'


def urlset(*urls, lastmod="2026-01-02") -> bytes:
    items = "".join(f"<url><loc>{u}</loc><lastmod>{lastmod}</lastmod></url>" for u in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset {NS}>{items}</urlset>'.encode()


def index(*urls) -> bytes:
    items = "".join(f"<sitemap><loc>{u}</loc></sitemap>" for u in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?><sitemapindex {NS}>{items}</sitemapindex>'.encode()


def make_transport(routes: dict, calls: list | None = None) -> httpx.MockTransport:
    """routes maps a URL to bytes, (status, bytes), (status, bytes, headers) or a callable."""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if calls is not None:
            calls.append(url)
        value = routes.get(url)
        if callable(value):
            value = value()
        if value is None:
            return httpx.Response(404, content=b"not found")
        if isinstance(value, bytes):
            return httpx.Response(200, content=value)
        status, body, *rest = value
        return httpx.Response(status, content=body, headers=rest[0] if rest else None)

    return httpx.MockTransport(handler)


def make_fetcher(routes: dict, calls: list | None = None, **config) -> Fetcher:
    cfg = FetchConfig(per_host_interval=0, backoff=0, **config)
    return Fetcher(cfg, transport=make_transport(routes, calls), sleep=lambda _: None)


@pytest.fixture
def public_dns(monkeypatch):
    """Pretend every hostname resolves to a public address, unless listed in the returned dict."""
    table: dict[str, list[str]] = {}

    def fake_resolve(host: str) -> list[str]:
        try:
            ipaddress.ip_address(host)
            return [host]  # an IP literal resolves to itself, as real DNS lookups do
        except ValueError:
            return table.get(host, ["93.184.216.34"])

    monkeypatch.setattr("sitemap_core.safety.resolve_host", fake_resolve)
    return table
