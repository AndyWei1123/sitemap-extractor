"""Polite, bounded HTTP fetching for sitemap files."""
from __future__ import annotations

import threading
import time
import zlib
from contextlib import contextmanager
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

from .safety import UnsafeURLError, check_url, is_public_ip

DEFAULT_USER_AGENT = "SitemapExtractor/0.1 (+https://github.com/AndyWei1123/sitemap-extractor)"
GZIP_MAGIC = b"\x1f\x8b"
RETRY_STATUSES = {429, 500, 502, 503, 504}


class FetchError(Exception):
    """A fetch failed. `code` is a stable machine-readable reason."""

    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code
        self.message = message or code


@dataclass
class FetchConfig:
    allow_private: bool = True       # False on the public deployment
    restrict_ports: bool = False     # True on the public deployment (80/443 only)
    max_bytes: int = 50 * 1024 * 1024
    timeout: float = 20.0
    retries: int = 3
    backoff: float = 1.0
    max_redirects: int = 5
    per_host_concurrency: int = 2
    per_host_interval: float = 0.25  # 2 connections x 0.5 s each
    user_agent: str = DEFAULT_USER_AGENT


class _HostState:
    def __init__(self, concurrency: int):
        self.sem = threading.Semaphore(concurrency)
        self.lock = threading.Lock()
        self.next_time = 0.0
        self.active = 0


class HostLimiter:
    """Caps concurrency and request rate per target host, across all jobs."""

    def __init__(self, concurrency: int, interval: float, sleep=time.sleep, clock=time.monotonic):
        self._concurrency = concurrency
        self._interval = interval
        self._sleep = sleep
        self._clock = clock
        self._hosts: dict[str, _HostState] = {}
        self._lock = threading.Lock()

    @contextmanager
    def slot(self, host: str):
        with self._lock:
            if len(self._hosts) > 2000:
                cutoff = self._clock() - 60
                for key in [k for k, s in self._hosts.items() if s.active == 0 and s.next_time < cutoff]:
                    del self._hosts[key]
            state = self._hosts.get(host)
            if state is None:
                state = self._hosts[host] = _HostState(self._concurrency)
            state.active += 1
        state.sem.acquire()
        try:
            with state.lock:
                now = self._clock()
                wait = state.next_time - now
                state.next_time = max(now, state.next_time) + self._interval
            if wait > 0:
                self._sleep(wait)
            yield
        finally:
            state.sem.release()
            with self._lock:
                state.active -= 1


def gunzip_limited(data: bytes, max_bytes: int) -> bytes:
    """Decompress gzip data, refusing to produce more than max_bytes (gzip-bomb guard)."""
    out = bytearray()
    remaining = data
    while remaining[:2] == GZIP_MAGIC:
        decomp = zlib.decompressobj(16 + zlib.MAX_WBITS)
        buf = remaining
        try:
            while buf and not decomp.eof:
                out += decomp.decompress(buf, max_bytes + 1 - len(out))
                if len(out) > max_bytes:
                    raise FetchError("too_large", "decompressed file exceeds the size limit")
                buf = decomp.unconsumed_tail
        except zlib.error as exc:
            if out:
                break  # truncated archive: keep what we have
            raise FetchError("bad_gzip", "the gzip data is corrupt") from exc
        if not decomp.eof:
            break
        remaining = decomp.unused_data
    return bytes(out)


class Fetcher:
    """Fetches URLs with redirect checks, size caps, retries and per-host politeness."""

    def __init__(self, config: FetchConfig | None = None, transport: httpx.BaseTransport | None = None,
                 sleep=time.sleep):
        self.config = config or FetchConfig()
        self._sleep = sleep
        self._client = httpx.Client(
            transport=transport,
            follow_redirects=False,
            timeout=httpx.Timeout(self.config.timeout),
            headers={"User-Agent": self.config.user_agent, "Accept": "application/xml,text/xml,text/plain,*/*"},
            trust_env=False,
        )
        self._limiter = HostLimiter(self.config.per_host_concurrency, self.config.per_host_interval, sleep=sleep)

    def close(self) -> None:
        self._client.close()

    def fetch(self, url: str, deadline: float | None = None) -> bytes:
        """Return the (decompressed) body of `url`, or raise FetchError."""
        cfg = self.config
        last: FetchError | None = None
        for attempt in range(cfg.retries + 1):
            if deadline is not None and time.monotonic() >= deadline:
                raise FetchError("deadline", "the time limit was reached")
            if attempt:
                self._sleep(cfg.backoff * (2 ** (attempt - 1)))
            try:
                return self._fetch_once(url)
            except FetchError as exc:
                last = exc
                if not getattr(exc, "retryable", False):
                    raise
        assert last is not None
        raise last

    def _fetch_once(self, url: str) -> bytes:
        cfg = self.config
        current = url
        for _ in range(cfg.max_redirects + 1):
            try:
                check_url(current, allow_private=cfg.allow_private, restrict_ports=cfg.restrict_ports)
            except UnsafeURLError as exc:
                raise FetchError("unsafe_url", str(exc)) from exc
            host = urlsplit(current).hostname or ""
            with self._limiter.slot(host):
                try:
                    with self._client.stream("GET", current) as resp:
                        self._check_peer(resp)
                        if resp.status_code in (301, 302, 303, 307, 308):
                            location = resp.headers.get("location")
                            if not location:
                                raise FetchError("http_error", f"redirect without Location ({resp.status_code})")
                            current = urljoin(current, location)
                            continue
                        self._raise_for_status(resp.status_code)
                        body = bytearray()
                        for chunk in resp.iter_bytes():
                            body += chunk
                            if len(body) > cfg.max_bytes:
                                raise FetchError("too_large", "file exceeds the size limit")
                except httpx.TimeoutException as exc:
                    raise _retryable(FetchError("timeout", "the request timed out")) from exc
                except httpx.HTTPError as exc:
                    raise _retryable(FetchError("network", f"network error: {type(exc).__name__}")) from exc
            data = bytes(body)
            if data[:2] == GZIP_MAGIC:
                data = gunzip_limited(data, cfg.max_bytes)
            return data
        raise FetchError("too_many_redirects", "too many redirects")

    def _check_peer(self, resp: httpx.Response) -> None:
        """Re-check the address we actually connected to (defends against DNS rebinding)."""
        if self.config.allow_private:
            return
        stream = resp.extensions.get("network_stream")
        if stream is None:
            return
        addr = stream.get_extra_info("server_addr")
        if addr and not is_public_ip(str(addr[0])):
            raise FetchError("unsafe_url", "connected to a non-public address")

    @staticmethod
    def _raise_for_status(status: int) -> None:
        if status == 200:
            return
        if status in RETRY_STATUSES:
            raise _retryable(FetchError(f"http_{status}", f"server answered {status}"))
        if status in (401, 403):
            raise FetchError("blocked", f"the site refused the request ({status})")
        if status in (404, 410):
            raise FetchError("not_found", f"not found ({status})")
        raise FetchError("http_error", f"server answered {status}")


def _retryable(exc: FetchError) -> FetchError:
    exc.retryable = True  # type: ignore[attr-defined]
    return exc
