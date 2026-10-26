import asyncio
from datetime import date

import httpx
import pytest

from jobradar.connectors._common import format_salary, html_to_text, iso_date, relative_date, workplace
from jobradar.http import FetchError, HttpClient, NotFound

from conftest import FakeSources, Seq

URL = "https://example.com/feed"


def get(settings, sources):
    async def go():
        async with HttpClient(settings, transport=sources.transport()) as client:
            return await client.get_json(URL)
    return asyncio.run(go())


def test_retries_once_on_server_error(settings):
    sources = FakeSources({("GET", URL): Seq([httpx.Response(503), {"ok": True}])})
    assert get(settings, sources) == {"ok": True}
    assert len(sources.requests) == 2


def test_gives_up_after_second_server_error(settings):
    sources = FakeSources({("GET", URL): httpx.Response(500)})
    with pytest.raises(FetchError, match="HTTP 500"):
        get(settings, sources)
    assert len(sources.requests) == 2


def test_no_retry_on_404(settings):
    sources = FakeSources()
    with pytest.raises(NotFound, match="404"):
        get(settings, sources)
    assert len(sources.requests) == 1


def test_invalid_json(settings):
    sources = FakeSources({("GET", URL): httpx.Response(200, text="<html>nope</html>")})
    with pytest.raises(FetchError, match="not JSON"):
        get(settings, sources)


def test_timeout_is_a_fetch_error(settings):
    sources = FakeSources({("GET", URL): httpx.ReadTimeout("slow")})
    with pytest.raises(FetchError, match="timed out"):
        get(settings, sources)


def test_rate_limited(settings):
    sources = FakeSources({("GET", URL): httpx.Response(429)})
    with pytest.raises(FetchError, match="429"):
        get(settings, sources)


def test_honest_user_agent_then_fallback_on_403(settings):
    settings.contact = "me@example.com"
    sources = FakeSources({("GET", URL): Seq([httpx.Response(403), {"ok": True}])})
    assert get(settings, sources) == {"ok": True}
    agents = [r.headers["user-agent"] for r in sources.requests]
    assert agents[0] == "job-radar/0.1 (personal use; me@example.com)"
    assert agents[1] == settings.http.fallback_user_agent


# --- helpers -------------------------------------------------------------------------

def test_html_to_text():
    text = html_to_text("<h2>About</h2><p>We build&nbsp;things.</p><ul><li>Python</li><li>SQL</li></ul>")
    assert text == "About\n\nWe build things.\n\n- Python\n\n- SQL"
    assert html_to_text("&lt;p&gt;Hi &amp;amp; bye&lt;/p&gt;", escaped=True) == "Hi & bye"
    assert html_to_text(None) is None


@pytest.mark.parametrize("value,expected", [
    ("2026-10-07T15:23:54-04:00", "2026-10-07"),
    ("2026-10-15 09:31:36 UTC", "2026-10-15"),
    ("2026-05-08", "2026-05-08"),
    (1787156115902, "2026-08-19"),
    (None, None), ("", None), ("soon", None),
])
def test_iso_date(value, expected):
    assert iso_date(value) == expected


@pytest.mark.parametrize("text,expected", [
    ("Posted Today", "2026-10-26"), ("Posted Yesterday", "2026-10-25"),
    ("Posted 2 Days Ago", "2026-10-24"), ("Posted 30+ Days Ago", None), (None, None),
])
def test_relative_date(text, expected):
    assert relative_date(text, date(2026, 10, 26)) == expected


def test_format_salary():
    assert format_salary(140000, 180000, "CAD", "per-year-salary") == "CA$140,000 – 180,000 / year"
    assert format_salary(25, None, "USD", "hour") == "US$25 / hour"
    assert format_salary(50000, 50000, "EUR") == "€50,000"
    assert format_salary(None, None, "CAD") is None


@pytest.mark.parametrize("value,remote,expected", [
    ("OnSite", None, "onsite"), ("hybrid", None, "hybrid"), ("REMOTE", None, "remote"),
    ("unspecified", None, "unknown"), (None, True, "remote"), ("On-site", None, "onsite"),
])
def test_workplace(value, remote, expected):
    assert workplace(value, remote) == expected
