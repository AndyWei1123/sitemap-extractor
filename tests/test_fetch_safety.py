from __future__ import annotations

import gzip

import pytest
from conftest import make_fetcher, urlset

from sitemap_core.fetch import FetchError, gunzip_limited
from sitemap_core.safety import UnsafeURLError, check_url, is_public_ip

BODY = urlset("https://example.com/a")


def test_gzip_file_is_decompressed():
    f = make_fetcher({"https://example.com/sitemap.xml.gz": gzip.compress(BODY)})
    assert f.fetch("https://example.com/sitemap.xml.gz") == BODY


def test_gz_name_with_plain_content():
    f = make_fetcher({"https://example.com/sitemap.xml.gz": BODY})
    assert f.fetch("https://example.com/sitemap.xml.gz") == BODY


def test_xml_name_with_gzip_content():
    f = make_fetcher({"https://example.com/sitemap.xml": gzip.compress(BODY)})
    assert f.fetch("https://example.com/sitemap.xml") == BODY


def test_size_limit_on_download():
    f = make_fetcher({"https://example.com/big.xml": b"x" * 5000}, max_bytes=1000)
    with pytest.raises(FetchError) as exc:
        f.fetch("https://example.com/big.xml")
    assert exc.value.code == "too_large"


def test_gzip_bomb_is_stopped():
    bomb = gzip.compress(b"0" * 5_000_000)
    assert len(bomb) < 10_000
    f = make_fetcher({"https://example.com/bomb.xml.gz": bomb}, max_bytes=100_000)
    with pytest.raises(FetchError) as exc:
        f.fetch("https://example.com/bomb.xml.gz")
    assert exc.value.code == "too_large"


def test_gunzip_multi_member_and_corrupt():
    assert gunzip_limited(gzip.compress(b"ab") + gzip.compress(b"cd"), 100) == b"abcd"
    with pytest.raises(FetchError) as exc:
        gunzip_limited(b"\x1f\x8bnot really gzip", 100)
    assert exc.value.code == "bad_gzip"


def test_retries_then_succeeds():
    answers = iter([(503, b""), (503, b""), (200, BODY)])
    calls: list[str] = []
    f = make_fetcher({"https://example.com/s.xml": lambda: next(answers)}, calls)
    assert f.fetch("https://example.com/s.xml") == BODY
    assert len(calls) == 3


def test_gives_up_after_three_retries():
    calls: list[str] = []
    f = make_fetcher({"https://example.com/s.xml": (429, b"")}, calls)
    with pytest.raises(FetchError) as exc:
        f.fetch("https://example.com/s.xml")
    assert exc.value.code == "http_429"
    assert len(calls) == 4


def test_blocked_is_not_retried():
    calls: list[str] = []
    f = make_fetcher({"https://example.com/s.xml": (403, b"")}, calls)
    with pytest.raises(FetchError) as exc:
        f.fetch("https://example.com/s.xml")
    assert exc.value.code == "blocked"
    assert len(calls) == 1


def test_redirect_is_followed():
    f = make_fetcher({
        "https://example.com/old.xml": (301, b"", {"location": "/new.xml"}),
        "https://example.com/new.xml": BODY,
    })
    assert f.fetch("https://example.com/old.xml") == BODY


def test_redirect_loop_stops():
    f = make_fetcher({"https://example.com/a.xml": (302, b"", {"location": "/a.xml"})})
    with pytest.raises(FetchError) as exc:
        f.fetch("https://example.com/a.xml")
    assert exc.value.code == "too_many_redirects"


def test_redirect_to_internal_address_is_blocked(public_dns):
    calls: list[str] = []
    f = make_fetcher({
        "https://example.com/s.xml": (302, b"", {"location": "http://169.254.169.254/latest/meta-data/"}),
        "http://169.254.169.254/latest/meta-data/": b"secret",
    }, calls, allow_private=False, restrict_ports=True)
    with pytest.raises(FetchError) as exc:
        f.fetch("https://example.com/s.xml")
    assert exc.value.code == "unsafe_url"
    assert calls == ["https://example.com/s.xml"]


@pytest.mark.parametrize("ip,public", [
    ("93.184.216.34", True), ("2606:2800:220:1:248:1893:25c8:1946", True),
    ("127.0.0.1", False), ("10.0.0.5", False), ("172.16.3.4", False), ("192.168.1.1", False),
    ("169.254.169.254", False), ("0.0.0.0", False), ("100.64.0.1", False),
    ("::1", False), ("fe80::1", False), ("fd00::1", False), ("::ffff:10.0.0.1", False),
    ("224.0.0.1", False), ("not-an-ip", False),
])
def test_is_public_ip(ip, public):
    assert is_public_ip(ip) is public


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/sitemap.xml",
    "http://localhost/sitemap.xml",
    "http://10.1.2.3/sitemap.xml",
    "http://[::1]/sitemap.xml",
    "http://169.254.169.254/latest/meta-data/",
    "http://2130706433/sitemap.xml",
    "http://0x7f.0.0.1/sitemap.xml",
    "https://example.com:8080/sitemap.xml",
    "https://example.com:22/",
    "ftp://example.com/sitemap.xml",
    "file:///etc/passwd",
    "https://user:pass@example.com/sitemap.xml",
    "https:///sitemap.xml",
])
def test_public_mode_rejects(url):
    with pytest.raises(UnsafeURLError):
        check_url(url, allow_private=False, restrict_ports=True)


def test_hostname_resolving_to_private_is_rejected(public_dns):
    public_dns["evil.example"] = ["93.184.216.34", "10.0.0.7"]
    with pytest.raises(UnsafeURLError):
        check_url("https://evil.example/sitemap.xml", allow_private=False, restrict_ports=True)
    check_url("https://good.example/sitemap.xml", allow_private=False, restrict_ports=True)


def test_local_mode_allows_localhost():
    check_url("http://localhost:8080/sitemap.xml", allow_private=True, restrict_ports=False)
