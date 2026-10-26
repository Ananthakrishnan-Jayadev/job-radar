import copy
import json
from pathlib import Path

import httpx
import pytest

from jobradar import db
from jobradar.config import load_settings

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_json(name: str):
    """The recorded response body of tests/fixtures/<name> (a fresh copy)."""
    return copy.deepcopy(json.loads((FIXTURES / name).read_text())["response"])


class Seq(list):
    """Replies given in turn, one per request (the last one repeats)."""


class FakeSources:
    """An httpx transport that answers from a table instead of the network.

    routes: {(method, url_prefix): reply}, where reply is a JSON body (200),
    an httpx.Response, an exception to raise, a callable(request) returning one
    of those, or Seq([...]) of them used in turn (the last one repeats).
    The longest matching prefix wins. Unmatched requests get a 404.
    """

    def __init__(self, routes: dict | None = None):
        self.routes = dict(routes or {})
        self.requests: list[httpx.Request] = []
        self._calls: dict = {}

    def add(self, method: str, prefix: str, reply) -> None:
        self.routes[(method, prefix)] = reply

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def bodies(self, method="POST"):
        return [json.loads(r.content) for r in self.requests if r.method == method and r.content]

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url)
        matches = [k for k in self.routes if k[0] == request.method and url.startswith(k[1])]
        if not matches:
            return httpx.Response(404, json={"error": "Not Found"})
        key = max(matches, key=lambda k: len(k[1]))
        reply = self.routes[key]
        if isinstance(reply, Seq):
            n = self._calls.get(key, 0)
            self._calls[key] = n + 1
            reply = reply[min(n, len(reply) - 1)]
        if callable(reply) and not isinstance(reply, type):
            reply = reply(request)
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, httpx.Response):
            return reply
        return httpx.Response(200, json=reply)


@pytest.fixture
def conn(tmp_path):
    connection = db.connect(tmp_path / "test.db")
    yield connection
    connection.close()


@pytest.fixture
def settings(tmp_path):
    """Default settings with every pause set to zero so tests run fast."""
    s = load_settings(tmp_path)
    s.http.page_delay_seconds = 0
    s.workday.delay_seconds = 0
    return s
