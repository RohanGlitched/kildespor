"""Polite, bounded HTTP client.

- only http(s); hosts that resolve to private, loopback or link-local addresses are refused
- robots.txt is read once per host and obeyed for our user agent
- one request at a time per host, a global concurrency cap, timeouts and a body size cap
- every response is returned with its final URL, redirect chain, status and content hash
"""
from __future__ import annotations

import asyncio
import zipfile
import gzip
import ipaddress
import socket
import time
import urllib.robotparser
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx

from .util import sha256_bytes, utc_now

USER_AGENT = "KildesporBot/1.0 (+https://github.com/RohanGlitched/kildespor; company research for the Builderr Signalpost challenge)"
MAX_BODY = 3_000_000
# public APIs that are built for parallel clients; every other host gets one request at a time
HOST_LIMITS = {"data.brreg.no": 8, "stottetiltak-registerinfo-api.app.brreg.no": 4, "api.ted.europa.eu": 2, "api.finanstilsynet.no": 6, "www.fagfolkguiden.no": 3, "pam-stilling-feed.nav.no": 12, "query.wikidata.org": 2, "w2.brreg.no": 2,
               "www.youtube.com": 4, "news.google.com": 2}
TIMEOUT = httpx.Timeout(10.0, connect=5.0)


@dataclass
class Fetched:
    url: str
    final_url: str
    status: int
    retrieved_at: str
    content_type: str = ""
    body: bytes = b""
    sha256: str = ""
    redirects: list[str] = field(default_factory=list)
    error: str = ""
    blocked: str = ""
    elapsed_ms: int = 0

    @property
    def ok(self) -> bool:
        return not self.error and not self.blocked and 200 <= self.status < 300

    def text(self) -> str:
        if not self.body:
            return ""
        enc = "utf-8"
        ct = self.content_type.lower()
        if "charset=" in ct:
            enc = ct.split("charset=")[-1].split(";")[0].strip() or "utf-8"
        try:
            return self.body.decode(enc, errors="replace")
        except LookupError:
            return self.body.decode("utf-8", errors="replace")


class Stats:
    def __init__(self) -> None:
        self.requests = 0
        self.bytes = 0
        self.latencies: list[int] = []
        self.by_source: dict[str, int] = {}

    def add(self, source: str, f: Fetched) -> None:
        self.requests += 1
        self.bytes += len(f.body)
        self.latencies.append(f.elapsed_ms)
        self.by_source[source] = self.by_source.get(source, 0) + 1


def _private(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False  # unresolvable: the request itself will fail
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return True
    return False


class Client:
    def __init__(self, concurrency: int = 48, snapshot_dir: Path | None = None) -> None:
        self.client = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT, "Accept-Language": "nb-NO,nb;q=0.9,no;q=0.8,en;q=0.6"},
            timeout=TIMEOUT,
            follow_redirects=False,
            limits=httpx.Limits(max_connections=concurrency * 2, max_keepalive_connections=concurrency),
            http2=False,
            verify=True,
        )
        self.sem = asyncio.Semaphore(concurrency)
        self.host_locks: dict[str, asyncio.Semaphore] = {}
        self.robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self.robots_locks: dict[str, asyncio.Lock] = {}
        self.private_cache: dict[str, bool] = {}
        self.stats = Stats()
        self.snapshot_dir = snapshot_dir
        self.archive: zipfile.ZipFile | None = None
        self.archived: set[str] = set()
        if snapshot_dir:
            snapshot_dir.parent.mkdir(parents=True, exist_ok=True)
            path = snapshot_dir.with_suffix(".zip")
            if path.exists():
                with zipfile.ZipFile(path) as z:
                    self.archived = {n.split(".")[0] for n in z.namelist()}
            self.archive = zipfile.ZipFile(path, "a", compression=zipfile.ZIP_DEFLATED, compresslevel=6)
        self.no_snapshot_sources = {"robots", "nav_jobs_index"}

    def save_snapshot(self, f: "Fetched") -> None:
        if self.archive is not None and f.ok and f.body and f.sha256 not in self.archived:
            self.archived.add(f.sha256)
            self.archive.writestr(f"{f.sha256}.raw", f.body)

    async def close(self) -> None:
        await self.client.aclose()
        if self.archive is not None:
            self.archive.close()

    def _lock(self, host: str) -> asyncio.Semaphore:
        if host not in self.host_locks:
            self.host_locks[host] = asyncio.Semaphore(HOST_LIMITS.get(host, 1))
        return self.host_locks[host]

    async def _is_private(self, host: str) -> bool:
        if host not in self.private_cache:
            self.private_cache[host] = await asyncio.to_thread(_private, host)
        return self.private_cache[host]

    async def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self.robots_locks:
            self.robots_locks[origin] = asyncio.Lock()
        async with self.robots_locks[origin]:
            if origin not in self.robots:
                rp: urllib.robotparser.RobotFileParser | None = urllib.robotparser.RobotFileParser()
                f = await self._raw("robots", origin + "/robots.txt", max_body=500_000, check_robots=False)
                if f.ok and "text" in (f.content_type or "text/plain"):
                    rp.parse(f.text().splitlines())
                elif f.status in (401, 403):
                    rp.parse(["User-agent: *", "Disallow: /"])
                else:
                    rp = None  # no robots file: allowed
                self.robots[origin] = rp
        rp = self.robots[origin]
        return True if rp is None else rp.can_fetch(USER_AGENT, url)

    async def get(self, source: str, url: str, *, max_body: int = MAX_BODY, headers: dict | None = None,
                  check_robots: bool = True, max_redirects: int = 5, retries: int = 0, timeout: float | None = None) -> Fetched:
        for attempt in range(retries + 1):
            f = await self._raw(source, url, max_body=max_body, headers=headers, check_robots=check_robots,
                                max_redirects=max_redirects, timeout=timeout)
            if f.ok or f.blocked or (f.status and f.status < 500 and f.status != 429) or attempt == retries:
                return f
            await asyncio.sleep((6.0 if f.status == 429 else 1.0) * (attempt + 1))
        return f

    async def post(self, source: str, url: str, body: bytes, *, headers: dict | None = None, retries: int = 1) -> Fetched:
        """POST to a public API (no robots check: API endpoints, not pages). Same safety and stats as GET."""
        start = time.monotonic()
        host = (urlsplit(url).hostname or "").lower()
        if urlsplit(url).scheme != "https" or await self._is_private(host):
            return Fetched(url, url, 0, utc_now(), blocked="private_address")
        f = Fetched(url, url, 0, utc_now(), error="not_sent")
        for attempt in range(retries + 1):
            async with self._lock(host), self.sem:
                try:
                    resp = await self.client.post(url, content=body, headers=headers, timeout=httpx.Timeout(90.0, connect=10.0))
                    data = resp.content[:MAX_BODY]
                    f = Fetched(url, str(resp.url), resp.status_code, utc_now(), resp.headers.get("content-type", ""), data,
                                sha256_bytes(data), elapsed_ms=int((time.monotonic() - start) * 1000))
                except (httpx.HTTPError, OSError, ValueError) as exc:
                    f = Fetched(url, url, 0, utc_now(), error=type(exc).__name__, elapsed_ms=int((time.monotonic() - start) * 1000))
            self.stats.add(source, f)
            self.save_snapshot(f)
            if f.ok or (f.status and f.status < 500 and f.status != 429):
                break
            wait = 1.0 * (attempt + 1)
            if f.status == 429:
                try:
                    wait = min(60.0, float(resp.headers.get("retry-after") or 10 * (attempt + 1)))
                except (ValueError, NameError):
                    wait = 10.0 * (attempt + 1)
            await asyncio.sleep(wait)
        return f

    async def _raw(self, source: str, url: str, *, max_body: int = MAX_BODY, headers: dict | None = None,
                   check_robots: bool = True, max_redirects: int = 5, timeout: float | None = None) -> Fetched:
        start = time.monotonic()
        chain: list[str] = []
        current = url
        for _ in range(max_redirects + 1):
            parts = urlsplit(current)
            if parts.scheme not in ("http", "https") or not parts.hostname:
                return Fetched(url, current, 0, utc_now(), error="unsupported_url", redirects=chain)
            host = parts.hostname.lower()
            if await self._is_private(host):
                return Fetched(url, current, 0, utc_now(), blocked="private_address", redirects=chain)
            if check_robots and not await self.allowed(current):
                return Fetched(url, current, 0, utc_now(), blocked="robots", redirects=chain)
            async with self._lock(host), self.sem:
                try:
                    async with self.client.stream("GET", current, headers=headers,
                                                  timeout=httpx.Timeout(timeout, connect=8.0) if timeout else TIMEOUT) as resp:
                        body = b""
                        if resp.status_code in (301, 302, 303, 307, 308) and resp.headers.get("location"):
                            chain.append(current)
                            current = urljoin(current, resp.headers["location"])
                            continue
                        async for chunk in resp.aiter_bytes():
                            body += chunk
                            if len(body) > max_body:
                                body = body[:max_body]
                                break
                        f = Fetched(url, str(resp.url), resp.status_code, utc_now(),
                                    resp.headers.get("content-type", ""), body, sha256_bytes(body), chain,
                                    elapsed_ms=int((time.monotonic() - start) * 1000))
                except (httpx.HTTPError, OSError, ValueError) as exc:
                    f = Fetched(url, current, 0, utc_now(), error=type(exc).__name__, redirects=chain,
                                elapsed_ms=int((time.monotonic() - start) * 1000))
            self.stats.add(source, f)
            if source not in self.no_snapshot_sources:
                self.save_snapshot(f)
            return f
        return Fetched(url, current, 0, utc_now(), error="too_many_redirects", redirects=chain)
