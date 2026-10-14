"""Resolver safety net.

If the operating system's resolver cannot answer for a host (a flaky home router or a broken
corporate DNS), ask public resolvers before giving up. Installed once at start-up; answers that
the system resolver gives are never changed.
"""
from __future__ import annotations

import socket
import threading

import dns.exception
import dns.resolver

_original = socket.getaddrinfo
_cache: dict[str, list[str]] = {}
_lock = threading.Lock()
_resolver = dns.resolver.Resolver(configure=False)
_resolver.nameservers = ["1.1.1.1", "8.8.8.8", "9.9.9.9"]
_resolver.lifetime = 4.0
_resolver.rotate = True


def _public(host: str) -> list[str]:
    with _lock:
        if host in _cache:
            return _cache[host]
    addrs: list[str] = []
    for rtype in ("A", "AAAA"):
        try:
            addrs += [r.to_text() for r in _resolver.resolve(host, rtype)]
        except dns.exception.DNSException:
            continue
    with _lock:
        _cache[host] = addrs
    return addrs


def getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):  # noqa: A002 - mirrors socket.getaddrinfo
    try:
        return _original(host, port, family, type, proto, flags)
    except socket.gaierror:
        if not isinstance(host, str) or not host or host.replace(".", "").isdigit():
            raise
        out = []
        for ip in _public(host):
            try:
                out += _original(ip, port, family, type, proto, flags | socket.AI_NUMERICHOST)
            except socket.gaierror:
                continue
        if not out:
            raise
        return out


def install() -> None:
    socket.getaddrinfo = getaddrinfo
