"""The one HTTP client every connector uses.

Keeps us gentle on sources: at most `max_per_host` requests at once per host,
a pause between pages (connectors call `pause()`), a timeout, and one retry
on network errors, 429 and 5xx. Redirects are not followed: a job board that
redirects (BambooHR sends unknown companies to its homepage) is "not found".
"""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlsplit

import httpx

from .config import Settings


class FetchError(Exception):
    """A source could not be read. The message is shown to the user."""


class NotFound(FetchError):
    """The board does not exist (404, or a redirect away from the feed)."""


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

    async def __aenter__(self) -> HttpClient:
        return self

    async def __aexit__(self, *exc) -> None:
        await self._client.aclose()

    async def pause(self, seconds: float | None = None) -> None:
        delay = self.settings.http.page_delay_seconds if seconds is None else seconds
        if delay > 0:
            await asyncio.sleep(delay)

    async def get_json(self, url: str, params: dict | None = None) -> Any:
        return _json(await self.request("GET", url, params=params))

    async def post_json(self, url: str, body: dict) -> Any:
        return _json(await self.request("POST", url, json=body))

    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        host = urlsplit(url).netloc
        limit = self._host_limits.setdefault(host, asyncio.Semaphore(self.settings.http.max_per_host))
        async with limit:
            response = await self._send(method, url, host, **kwargs)
            if response.status_code == 403 and host not in self._fallback_hosts:
                # Some sources block unknown agents; try once with a browser one.
                self._fallback_hosts.add(host)
                response = await self._send(method, url, host, **kwargs)
                if response.status_code == 403:
                    self._fallback_hosts.discard(host)
        return _check(response)

    async def get_text(self, url: str, params: dict | None = None) -> str:
        """An HTML page, following redirects (careers pages often redirect)."""
        response = await self.request("GET", url, params=params, headers={"Accept": "text/html"},
                                      follow_redirects=True)
        return response.text

    async def _send(self, method: str, url: str, host: str, **kwargs) -> httpx.Response:
        headers = dict(kwargs.pop("headers", None) or {})
        if host in self._fallback_hosts:
            headers["User-Agent"] = self.settings.http.fallback_user_agent
        for attempt in (1, 2):
            try:
                response = await self._client.request(method, url, headers=headers, **kwargs)
            except httpx.TimeoutException as exc:
                if attempt == 2:
                    raise FetchError(f"timed out after {self.settings.http.timeout_seconds}s") from exc
            except httpx.TransportError as exc:
                if attempt == 2:
                    raise FetchError(f"network error: {exc}") from exc
            else:
                if attempt == 2 or (response.status_code != 429 and response.status_code < 500):
                    return response
            await self.pause(max(self.settings.http.page_delay_seconds * 4, 0))
        raise AssertionError("unreachable")


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
