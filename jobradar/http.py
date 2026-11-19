"""The one HTTP client every connector uses.

Keeps us gentle on sources: at most `max_per_host` requests at once per host,
a pause between pages (connectors call `pause()`), a timeout, and one retry
on network errors and 5xx. A 429 (too many requests) gets up to three
retries, waiting as long as the source asks (Retry-After, up to a minute) or
5, 15 then 30 seconds, and that host gets an extra pause before every later
request in the same scan. Redirects are not followed: a job board that
redirects (BambooHR sends unknown companies to its homepage) is "not found".

Some hosts are one site: every company's Workday site (*.myworkdayjobs.com)
runs on Workday's servers, which count requests from our address across all
of them. They share one queue (one request at a time, `workday.min_interval_seconds`
apart), and when Workday still says 429 after the retries, the rest of its
boards are skipped until the next scan instead of asking again.

A bot-protection challenge (Cloudflare's `cf-mitigated: challenge`) means the
site doesn't want this automated traffic: no retries, no other user agent, and
that site's boards are skipped for the rest of the scan. We don't try to get
past such checks.
"""

from __future__ import annotations

import asyncio
from email.utils import parsedate_to_datetime
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

import httpx

from .config import Settings


class FetchError(Exception):
    """A source could not be read. The message is shown to the user."""


class NotFound(FetchError):
    """The board does not exist (404, or a redirect away from the feed)."""


# Hosts that are really one site, so they share limits.
_SITES = {".myworkdayjobs.com": "Workday", ".myworkdaysite.com": "Workday"}


def site_of(host: str) -> str:
    """The site a host belongs to: "Workday" for any company's Workday host, else the host."""
    for suffix, site in _SITES.items():
        if host.endswith(suffix):
            return site
    return host


def _challenged(response: httpx.Response) -> bool:
    """A bot-protection check rather than an answer (Cloudflare's managed challenge)."""
    return response.headers.get("cf-mitigated", "").lower() == "challenge"


class HttpClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self._client = httpx.AsyncClient(
            headers={"User-Agent": settings.user_agent, "Accept": "application/json"},
            timeout=settings.http.timeout_seconds,
            follow_redirects=False,
            transport=transport,
        )
        self._host_limits: dict[str, asyncio.Semaphore] = {}
        self._fallback_hosts: set[str] = set()  # hosts that rejected our honest user agent
        self._slow_hosts: set[str] = set()  # sites that answered 429: pause before each request
        self._blocked: dict[str, str] = {}  # sites skipped for the rest of the scan, and why
        self._next_at: dict[str, float] = {}  # sites with a minimum interval: earliest next request

    async def __aenter__(self) -> HttpClient:
        return self

    async def __aexit__(self, *exc) -> None:
        await self._client.aclose()

    async def pause(self, seconds: float | None = None) -> None:
        delay = self.settings.http.page_delay_seconds if seconds is None else seconds
        if delay > 0:
            await asyncio.sleep(delay)

    async def get_json(self, url: str, params: dict | None = None, headers: dict | None = None) -> Any:
        return _json(await self.request("GET", url, params=params, headers=headers))

    async def post_json(self, url: str, body: dict) -> Any:
        return _json(await self.request("POST", url, json=body))

    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        host = urlsplit(url).netloc
        site = site_of(host)
        if site in self._blocked:
            raise FetchError(self._blocked[site])
        interval = self.settings.workday.min_interval_seconds if site == "Workday" else 0
        size = 1 if site == "Workday" else self.settings.http.max_per_host
        limit = self._host_limits.setdefault(site, asyncio.Semaphore(size))
        async with limit:
            if interval:
                wait = self._next_at.get(site, 0) - asyncio.get_running_loop().time()
                if wait > 0:
                    await asyncio.sleep(wait)
            if site in self._slow_hosts:
                await self.pause(self.settings.http.rate_limited_delay_seconds)
            response = await self._send(method, url, host, site, **kwargs)
            if interval:
                self._next_at[site] = asyncio.get_running_loop().time() + interval
            if _challenged(response):
                self._blocked[site] = (f"blocked by {site}'s bot protection (Cloudflare challenge): "
                                       "skipped until the next scan; it clears when we ask less often")
                raise FetchError(self._blocked[site])
            if response.status_code == 429:
                # Still too many after the retries: stop asking this scan.
                self._blocked[site] = f"rate limited (429): {site} asked us to slow down; its boards wait until the next scan"
            if response.status_code == 403 and host not in self._fallback_hosts:
                # Some sources block unknown agents; try once with a browser one.
                self._fallback_hosts.add(host)
                response = await self._send(method, url, host, site, **kwargs)
                if response.status_code == 403:
                    self._fallback_hosts.discard(host)
        return _check(response)

    async def get_text(self, url: str, params: dict | None = None) -> str:
        """An HTML page, following redirects (careers pages often redirect)."""
        response = await self.request("GET", url, params=params, headers={"Accept": "text/html"},
                                      follow_redirects=True)
        return response.text

    async def _send(self, method: str, url: str, host: str, site: str, **kwargs) -> httpx.Response:
        headers = dict(kwargs.pop("headers", None) or {})
        if host in self._fallback_hosts:
            headers["User-Agent"] = self.settings.http.fallback_user_agent
        failures = rate_limits = 0
        while True:
            try:
                response = await self._client.request(method, url, headers=headers, **kwargs)
            except httpx.TimeoutException as exc:
                failures += 1
                if failures == 2:
                    raise FetchError(f"timed out after {self.settings.http.timeout_seconds}s") from exc
            except httpx.TransportError as exc:
                failures += 1
                if failures == 2:
                    raise FetchError(f"network error: {exc}") from exc
            else:
                if _challenged(response):
                    return response  # a bot check, not a busy server: never retried
                if response.status_code == 429:
                    # Too many requests: slow down for this host, wait, try again (3 times).
                    self._slow_hosts.add(site)
                    rate_limits += 1
                    if rate_limits > 3:
                        return response
                    await self.pause(_retry_after(response) or
                                     self.settings.http.rate_limit_wait_seconds * (1, 3, 6)[rate_limits - 1])
                    continue
                if response.status_code < 500:
                    return response
                failures += 1
                if failures == 2:
                    return response
            await self.pause(max(self.settings.http.page_delay_seconds * 4, 0))


def _retry_after(response: httpx.Response) -> float | None:
    """How long a 429 asks us to wait (Retry-After: seconds or a date), at most a minute."""
    value = response.headers.get("retry-after", "").strip()
    if not value:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            seconds = (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds()
        except (TypeError, ValueError):
            return None
    return min(max(seconds, 0), 60)


def _check(response: httpx.Response) -> httpx.Response:
    status = response.status_code
    if 200 <= status < 300:
        return response
    if status in (301, 302, 303, 307, 308):
        target = response.headers.get("location", "?")
        raise NotFound(f"redirected to {target} (board not found)")
    if status == 404:
        raise NotFound("not found (404): check the slug")
    if status == 422:
        raise NotFound("rejected (422): for Workday, check the site name in the URL")
    if status == 429:
        raise FetchError("rate limited (429): try again later")
    raise FetchError(f"HTTP {status}")


def _json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError as exc:
        raise FetchError("response was not JSON") from exc
