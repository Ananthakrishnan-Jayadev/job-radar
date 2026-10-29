"""Open a Greenhouse application in a browser window and fill it in from a Plan.

Then it waits: you read the form, answer what's left, and press Submit
yourself (and solve a CAPTCHA if the form has one). It never submits. When
the form says thank you, the application counts as submitted; closing the
window first counts as not applied.

Playwright drives the browser: `.venv/bin/pip install playwright`, then its
Firefox goes inside the venv (BROWSERS below), not ~/.cache:
`PLAYWRIGHT_BROWSERS_PATH=.venv/ms-playwright .venv/bin/playwright install firefox`.
"""

from __future__ import annotations

import os
import re
import time
from collections.abc import Callable
from pathlib import Path

from .greenhouse import FILE, MULTI, SELECT, Plan, Step, Todo

BROWSERS = Path(__file__).resolve().parents[2] / ".venv" / "ms-playwright"
FORM_WAIT_MS = 25_000  # for the form to appear
FIELD_WAIT_MS = 3_000  # per field before giving up on it
WATCH_HOURS = 3  # stop watching an open window after this long
_THANKS = re.compile(r"thank you for (applying|your application)|application (has been )?"
                     r"(received|submitted)|we('ve| have) received your application", re.I)
_ATTACH = re.compile(r"^\s*attach", re.I)
_FORM_FIELD = "#first_name, input[name='first_name'], input[name='job_application[first_name]']"

Report = Callable[[dict], None]


class BrowserError(Exception):
    pass


def playwright_ready() -> str | None:
    """None when Playwright and its Firefox are installed, else how to install them."""
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(BROWSERS))
    try:
        import playwright  # noqa: F401
    except ImportError:
        return "Playwright isn't installed: run `.venv/bin/pip install playwright`, then install its Firefox (see README)."
    if not any(BROWSERS.glob("firefox-*")):
        return ("Playwright's Firefox isn't installed: run "
                "`PLAYWRIGHT_BROWSERS_PATH=.venv/ms-playwright .venv/bin/playwright install firefox`.")
    return None


def _form_frame(page):
    """The frame holding the application form (the page itself, or an embedded iframe)."""
    deadline = time.monotonic() + FORM_WAIT_MS / 1000
    while time.monotonic() < deadline:
        for frame in page.frames:
            try:
                if frame.locator(_FORM_FIELD).count():
                    return frame
            except Exception:  # noqa: BLE001 - a frame can go away while we look
                continue
        page.wait_for_timeout(500)
    return None


def _field(frame, step: Step):
    """The element for a step: by Greenhouse's id or name, else by its label."""
    name = step.name
    for selector in (f"[id='{name}']", f"[name='{name}']", f"[name='job_application[{name}]']"):
        loc = frame.locator(selector)
        if loc.count():
            return loc.first
    loc = frame.get_by_label(step.label, exact=False)
    return loc.first if loc.count() else None


def _file_input(frame, step: Step):
    """The file input for a step; the first one on the form is the résumé's."""
    name = step.name
    for selector in (f"input[type=file][id='{name}']", f"input[type=file][name='{name}']",
                     f"input[type=file][name='job_application[{name}]']", "input[type=file]"):
        loc = frame.locator(selector)
        if loc.count():
            return loc.first
    return None


def _shows(frame, text: str) -> bool:
    """Whether the form shows *text* (an attached file's name) within a few seconds."""
    try:
        frame.get_by_text(text, exact=False).first.wait_for(timeout=FIELD_WAIT_MS)
        return True
    except Exception:  # noqa: BLE001 - not there
        return False


def _attach(frame, step: Step) -> None:
    """Set the file on the form's file input, then check the form lists it. If it
    doesn't, go through the form's own Attach button, as a person would."""
    shown = Path(step.value).name
    el = _file_input(frame, step)
    if el is not None:
        el.set_input_files(step.value, timeout=FIELD_WAIT_MS)
        if _shows(frame, shown):
            return
    button = frame.get_by_role("button", name=_ATTACH)
    if not button.count():
        raise BrowserError("the form has no file field or Attach button")
    with frame.page.expect_file_chooser(timeout=FIELD_WAIT_MS) as chooser:
        button.first.click(timeout=FIELD_WAIT_MS)
    chooser.value.set_files(step.value)
    if not _shows(frame, shown):
        raise BrowserError("the form didn't show the file as attached")


def _phone_country(frame, country: str) -> bool:
    """The country beside the phone number ("Canada +1"), a dropdown of its own
    on Greenhouse's new form. False when the form has none."""
    box = frame.locator("[id='country']")
    if not box.count():
        box = frame.get_by_label("Country", exact=True)
    if not box.count():
        return False
    el, pick = box.first, re.compile(rf"^\s*{re.escape(country)}\b", re.I)
    if el.evaluate("e => e.tagName") == "SELECT":
        labels = el.evaluate("e => [...e.options].map(o => o.label)")
        choice = next((label for label in labels if pick.match(label)), None)
        if choice is None:
            raise BrowserError(f"no {country} among the choices")
        el.select_option(label=choice, timeout=FIELD_WAIT_MS)
        return True
    el.click(timeout=FIELD_WAIT_MS)
    el.fill(country, timeout=FIELD_WAIT_MS)
    frame.get_by_role("option", name=pick).first.click(timeout=FIELD_WAIT_MS)
    return True


def _fill(frame, step: Step) -> None:
    if step.kind == FILE:
        _attach(frame, step)
        return
    el = _field(frame, step)
    if el is None:
        raise BrowserError("field not found")
    if step.kind in (SELECT, MULTI):
        if el.evaluate("e => e.tagName") == "SELECT":
            el.select_option(label=step.value, timeout=FIELD_WAIT_MS)
            return
        # Greenhouse's new form: a searchable dropdown. Type, then pick the choice.
        el.click(timeout=FIELD_WAIT_MS)
        el.fill(step.value, timeout=FIELD_WAIT_MS)
        frame.get_by_role("option", name=step.value, exact=True).first.click(timeout=FIELD_WAIT_MS)
        return
    el.fill(step.value, timeout=FIELD_WAIT_MS)
    if step.name == "location":
        # An address search: take its first suggestion, if it offers one.
        try:
            frame.get_by_role("option").first.click(timeout=FIELD_WAIT_MS)
        except Exception:  # noqa: BLE001 - typed text alone is fine too
            pass


def _why(exc: Exception) -> str:
    """The first line of an error, short enough for the panel."""
    text = (str(exc).strip().splitlines() or [type(exc).__name__])[0]
    return text[:120]


def fill_and_watch(plan: Plan, report: Report, *, playwright_factory=None) -> str:
    """Fill the form, then watch until you submit or close it.
    Returns "submitted", "closed", or raises BrowserError."""
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(BROWSERS))
    if playwright_factory is None:
        from playwright.sync_api import sync_playwright as playwright_factory
    with playwright_factory() as p:
        browser = p.firefox.launch(headless=False)
        try:
            page = browser.new_page()
            report({"phase": "opening", "message": "Opening the application form…"})
            frame = None
            for url in dict.fromkeys(u for u in (plan.form_url, plan.job_url) if u):
                page.goto(url, wait_until="domcontentloaded")
                frame = _form_frame(page)
                if frame:
                    break
            if frame is None:
                raise BrowserError("The application form didn't appear. The posting may have closed, or the "
                                   "company takes applications elsewhere; the window shows what loaded.")
            filled, todo = [], list(plan.todo)
            if plan.phone_country:
                try:
                    if _phone_country(frame, plan.phone_country):
                        filled.append({"label": "Phone country", "check": False})
                except Exception as exc:  # noqa: BLE001 - one field must not stop the rest
                    todo.append(Todo("Phone country", True, f"pick {plan.phone_country} ({_why(exc)})"))
            for i, step in enumerate(plan.steps):
                report({"phase": "filling", "message": f"Filling in {i + 1} of {len(plan.steps)}…"})
                try:
                    _fill(frame, step)
                    filled.append({"label": step.label, "check": step.check})
                except Exception as exc:  # noqa: BLE001 - one field must not stop the rest
                    shown = Path(step.value).name if step.kind == FILE else step.value
                    todo.append(Todo(step.label, step.required,
                                     f"couldn't fill in {shown!r}, please do ({_why(exc)})"))
            report({"phase": "ready", "filled": filled,
                    "todo": [{"label": t.label, "required": t.required, "why": t.why} for t in todo],
                    "message": "Filled in. Check the form, answer what's left, then press Submit in the window."})
            return _watch(page)
        finally:
            try:
                browser.close()
            except Exception:  # noqa: BLE001 - already closed by you
                pass


def _watch(page) -> str:
    deadline = time.monotonic() + WATCH_HOURS * 3600
    while time.monotonic() < deadline:
        try:
            if page.is_closed():
                return "closed"
            for frame in page.frames:
                if "confirmation" in frame.url:
                    return "submitted"
                # Thanks on the page and the form gone: a line of thanks beside the form isn't enough.
                if frame.get_by_text(_THANKS).count() and not frame.locator(_FORM_FIELD).count():
                    return "submitted"
            page.wait_for_timeout(1000)
        except Exception:  # noqa: BLE001 - the window was closed under us
            return "closed"
    return "closed"
