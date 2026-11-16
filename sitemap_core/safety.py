"""URL safety checks: keep the fetcher away from internal addresses (SSRF guard)."""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit


class UnsafeURLError(ValueError):
    """The URL is not allowed to be fetched."""


def is_public_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    # IPv4-mapped IPv6 (::ffff:10.0.0.1) must be judged as the IPv4 address it wraps.
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    return addr.is_global and not addr.is_multicast


def resolve_host(host: str) -> list[str]:
    infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return sorted({info[4][0] for info in infos})


def check_url(url: str, *, allow_private: bool, restrict_ports: bool) -> None:
    """Raise UnsafeURLError unless `url` may be fetched.

    allow_private=False rejects every host that resolves to a non-public address.
    restrict_ports=True only allows the default ports 80 and 443.
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise UnsafeURLError("only http and https URLs are allowed")
    host = parts.hostname
    if not host:
        raise UnsafeURLError("the URL has no host")
    if parts.username or parts.password:
        raise UnsafeURLError("URLs with credentials are not allowed")
    try:
        port = parts.port
    except ValueError as exc:
        raise UnsafeURLError("invalid port") from exc
    if restrict_ports and port not in (None, 80, 443):
        raise UnsafeURLError("only ports 80 and 443 are allowed")
    if allow_private:
        return
    try:
        ips = resolve_host(host)
    except OSError as exc:
        raise UnsafeURLError(f"cannot resolve host: {host}") from exc
    if not ips:
        raise UnsafeURLError(f"cannot resolve host: {host}")
    for ip in ips:
        if not is_public_ip(ip):
            raise UnsafeURLError("the host resolves to a non-public address")
