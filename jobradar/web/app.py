"""FastAPI app: the JSON API under /api, and the built React UI for every other path.

Run with `jobradar serve`. The UI is built from frontend/ into ./static
(`npm run build`); until then, non-API paths show how to build it.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from urllib.parse import quote_plus

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from pydantic import BaseModel

from .. import candidates, db, enrich, queries, tracking
from ..boards import BoardError, normalize_board
from ..detect import Detected, detect_company
from ..http import FetchError, HttpClient
from ..config import Settings
from ..connectors import CONNECTORS
from ..export import jobs_csv
from ..locations import PROVINCE_NAMES
from ..models import COMPANY_STATUSES, JOB_STATUSES, SIZE_BANDS, UNKNOWN_SIZE, WORKPLACES, Location, size_band
from .scanner import ScanRunner
from .tasks import TaskRunner

STATIC_DIR = Path(__file__).parent / "static"

PROVINCES = [
    ("ON", "Ontario"), ("QC", "Quebec"), ("BC", "British Columbia"), ("AB", "Alberta"),
    ("MB", "Manitoba"), ("SK", "Saskatchewan"), ("NS", "Nova Scotia"), ("NB", "New Brunswick"),
    ("NL", "Newfoundland and Labrador"), ("PE", "Prince Edward Island"), ("YT", "Yukon"),
    ("NT", "Northwest Territories"), ("NU", "Nunavut"),
]
assert {code for code, _ in PROVINCES} <= set(PROVINCE_NAMES.values())

MAX_PAGE_SIZE = 200

NOT_BUILT = """<!doctype html><meta charset="utf-8"><title>Job Radar</title>
<body style="font-family:system-ui;max-width:40rem;margin:4rem auto;line-height:1.5">
<h1>Job Radar</h1><p>The API is running, but the web UI hasn't been built yet. In the project folder:</p>
<pre>cd frontend
npm install
npm run build</pre><p>Then reload this page.</p></body>"""


# --- request bodies (fields left out are not changed) ----------------------------------

class JobPatch(BaseModel):
    status: str | None = None
    notes: str | None = None
    applied_at: str | None = None


class CompanyPatch(BaseModel):
    status: str | None = None
    notes: str | None = None
    employee_count: int | None = None
    canadian: bool | None = None
    careers_url: str | None = None


class BoardIn(BaseModel):
    system: str
    slug_or_url: str


class CompanyIn(BaseModel):
    name: str
    canadian: bool = True
    careers_url: str | None = None
    board: BoardIn | None = None


class BoardPatch(BaseModel):
    enabled: bool | None = None
    confirmed: bool | None = None


class SavedSearchIn(BaseModel):
    name: str
    query: str = ""
    filters: dict = {}
    use_for_sources: bool = False


class SavedSearchPatch(BaseModel):
    name: str | None = None
    use_for_sources: bool | None = None


class ScanIn(BaseModel):
    company_id: int | None = None


class ApproveIn(BaseModel):
    system: str | None = None
    slug_or_url: str | None = None


class DetectIn(BaseModel):
    name: str
    careers_url: str | None = None
    canadian: bool = True


class EnrichIn(BaseModel):
    company_id: int | None = None


def _given(model: BaseModel) -> dict:
    """Only the fields the client actually sent (null included)."""
    return {name: getattr(model, name) for name in model.model_fields_set}


# --- serialization -----------------------------------------------------------------

def _location(loc: Location) -> dict:
    return {"label": loc.label(), "city": loc.city, "province": loc.province, "country": loc.country,
            "remote": loc.remote, "in_canada": loc.in_canada}


def _job_summary(row: dict) -> dict:
    return {
        "id": row["id"], "title": row["title"], "url": row["url"],
        "company_id": row["company_id"], "company": row["company"], "company_status": row["company_status"],
        "employee_count": row["employee_count"], "size_band": size_band(row["employee_count"]),
        "system": row["system"], "board_confirmed": bool(row["board_confirmed"]),
        "location": queries.location_label(row["locations"]),
        "provinces": queries.provinces_of(row["locations"]),
        "workplace": row["workplace"], "posted_at": row["posted_at"], "salary": row["salary_text"],
        "status": row["status"], "notes": row["notes"], "applied_at": row["applied_at"],
        "first_seen": row["first_seen"], "last_seen": row["last_seen"], "closed_at": row["closed_at"],
    }


def _company(row: dict) -> dict:
    return {
        "id": row["id"], "name": row["name"], "canadian": bool(row["canadian"]), "status": row["status"],
        "notes": row["notes"], "careers_url": row["careers_url"], "employee_count": row["employee_count"],
        "size_band": size_band(row["employee_count"]), "size_source": row["size_source"],
        "size_suggestion": json.loads(row["size_suggestion"]) if row["size_suggestion"] else None,
        "hq": ", ".join(p for p in (row["hq_city"], row["hq_province"], row["hq_country"]) if p) or None,
        "canada_open": row["canada_open"], "total_open": row["total_open"],
        "boards": [{
            "id": b["id"], "system": b["system"], "slug_or_url": b["slug_or_url"],
            "confirmed": bool(b["confirmed"]), "enabled": bool(b["enabled"]),
            "last_scanned_at": b["last_scanned_at"], "last_error": b["last_error"], "total_open": b["total_open"],
        } for b in row["boards"]],
    }


def _detected(d: Detected) -> dict:
    return {"system": d.system, "slug_or_url": d.slug_or_url, "how": d.how, "confidence": d.confidence,
            "note": d.note, "jobs_canada": d.jobs_canada, "jobs_total": d.jobs_total}


def _candidate(row: dict) -> dict:
    keys = ("id", "name", "tagline", "employees", "hq_country", "hq_province", "hq_city", "jobs_url",
            "detected_system", "detected_slug", "detect_note", "company_id", "company_name", "decision",
            "first_seen", "gone_at")
    return {k: row.get(k) for k in keys} | {"size_band": size_band(row.get("employees"))}


def linkedin_search_url(title: str, company: str) -> str:
    """A plain link to LinkedIn's job search (no automation; see docs/02)."""
    return f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(f'{title} {company}')}&location=Canada"


# --- filters from the query string -----------------------------------------------------

def _list(request: Request, name: str) -> list[str]:
    value = request.query_params.get(name, "")
    return [v.strip() for v in value.split(",") if v.strip()]


def _flag(request: Request, name: str) -> bool:
    return request.query_params.get(name, "").lower() in ("1", "true", "yes", "on")


def _int(request: Request, name: str, default: int | None = None) -> int | None:
    value = request.query_params.get(name)
    if value in (None, ""):
        return default
    try:
        return int(value)
    except ValueError:
        raise HTTPException(400, f"{name} must be a whole number") from None


def job_filter(request: Request) -> queries.JobFilter:
    return queries.JobFilter(
        query=request.query_params.get("q") or None,
        title_only=_flag(request, "title_only"),
        provinces=_list(request, "provinces"),
        size_bands=_list(request, "sizes"),
        company_ids=[int(v) for v in _list(request, "company") if v.isdigit()],
        statuses=_list(request, "status"),
        company_statuses=_list(request, "company_status"),
        include_ignored=_flag(request, "include_ignored"),
        posted_within_days=_int(request, "posted_within"),
        systems=_list(request, "systems"),
        workplaces=_list(request, "workplaces"),
        has_salary=_flag(request, "has_salary"),
        include_closed=_flag(request, "include_closed"),
        new_since=request.query_params.get("new_since") or None,
    )


# --- the app -------------------------------------------------------------------------

def create_app(settings: Settings, db_path: Path | None = None,
               transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    db_path = db_path or settings.database
    db.connect(db_path).close()  # create / migrate before the first request
    runner = ScanRunner(settings, db_path, transport=transport)
    tasks = TaskRunner()
    app = FastAPI(title="Job Radar", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.runner = runner
    app.state.tasks = tasks

    def detect(name: str, careers_url: str | None, canadian: bool) -> list[Detected]:
        async def go():
            async with HttpClient(settings, transport=transport) as client:
                return await detect_company(client, settings, name, careers_url, canadian)
        return asyncio.run(go())

    def get_conn() -> Iterator[sqlite3.Connection]:
        conn = db.connect(db_path)
        try:
            yield conn
        finally:
            conn.close()

    Conn = Depends(get_conn)

    @app.exception_handler(tracking.NotFoundError)
    async def _not_found(_, exc):
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.exception_handler(tracking.InvalidValue)
    async def _invalid(_, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(candidates.CandidateError)
    async def _bad_candidate(_, exc):
        status = 404 if isinstance(exc, candidates.CandidateNotFound) else 409
        return JSONResponse({"detail": str(exc)}, status_code=status)

    @app.exception_handler(BoardError)
    async def _bad_board(_, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    # meta

    @app.get("/api/meta")
    def meta(conn: sqlite3.Connection = Conn):
        open_jobs = queries.search_jobs(conn, queries.JobFilter(include_ignored=True), limit=0)[0]
        return {
            "provinces": [{"code": c, "name": n} for c, n in PROVINCES],
            "job_statuses": list(JOB_STATUSES),
            "company_statuses": list(COMPANY_STATUSES),
            "size_bands": [label for label, _, _ in SIZE_BANDS] + [UNKNOWN_SIZE],
            "systems": sorted(CONNECTORS),  # every system a board can use
            "systems_in_use": queries.systems_in_use(conn),  # the ones with jobs, for filtering
            "workplaces": list(WORKPLACES),
            "open_jobs": open_jobs,
            "companies": conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0],
        }

    @app.post("/api/visit")
    def visit(conn: sqlite3.Connection = Conn):
        return {"previous": tracking.record_visit(conn)}

    # jobs

    @app.get("/api/jobs")
    def list_jobs(request: Request, conn: sqlite3.Connection = Conn):
        f = job_filter(request)
        page = max(_int(request, "page", 1), 1)
        page_size = min(max(_int(request, "page_size", 50), 1), MAX_PAGE_SIZE)
        try:
            total, rows = queries.search_jobs(
                conn, f, sort=request.query_params.get("sort") or None,
                descending=request.query_params.get("order", "desc") != "asc",
                limit=page_size, offset=(page - 1) * page_size,
            )
        except sqlite3.OperationalError as exc:
            raise HTTPException(400, f"search syntax: {exc}") from exc
        return {"total": total, "page": page, "page_size": page_size, "items": [_job_summary(r) for r in rows]}

    @app.get("/api/jobs/provinces")
    def province_counts(request: Request, conn: sqlite3.Connection = Conn):
        try:
            return queries.province_counts(conn, job_filter(request))
        except sqlite3.OperationalError as exc:
            raise HTTPException(400, f"search syntax: {exc}") from exc

    @app.get("/api/jobs.csv")
    def export_csv(request: Request, conn: sqlite3.Connection = Conn):
        try:
            text = jobs_csv(conn, job_filter(request), sort=request.query_params.get("sort") or None)
        except sqlite3.OperationalError as exc:
            raise HTTPException(400, f"search syntax: {exc}") from exc
        name = f"jobradar-{date.today().isoformat()}.csv"
        return Response(text, media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: int, conn: sqlite3.Connection = Conn):
        row = conn.execute(
            """
            SELECT j.*, c.id AS company_id, c.name AS company, c.employee_count, c.status AS company_status,
                   c.careers_url, b.system, b.confirmed AS board_confirmed
            FROM jobs j JOIN boards b ON b.id = j.board_id JOIN companies c ON c.id = b.company_id
            WHERE j.id = ?
            """,
            (job_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(404, f"job {job_id} not found")
        job = dict(row)
        queries.attach_locations(conn, [job])
        return {
            **_job_summary(job),
            "department": job["department"], "employment_type": job["employment_type"],
            "description": job["description"], "status_changed_at": job["status_changed_at"],
            "locations": [_location(l) for l in job["locations"]],
            "events": tracking.job_events(conn, job_id),
            "links": {"job": job["url"], "careers": job["careers_url"],
                      "linkedin": linkedin_search_url(job["title"], job["company"])},
        }

    @app.patch("/api/jobs/{job_id}")
    def patch_job(job_id: int, body: JobPatch, conn: sqlite3.Connection = Conn):
        return tracking.update_job(conn, job_id, **_given(body))

    # companies and boards

    @app.get("/api/companies")
    def companies(request: Request, conn: sqlite3.Connection = Conn):
        rows = queries.list_companies(conn, query=request.query_params.get("q"),
                                      size_bands=_list(request, "sizes"), statuses=_list(request, "status"))
        return [_company(r) for r in rows]

    @app.get("/api/companies/{company_id}")
    def company(company_id: int, conn: sqlite3.Connection = Conn):
        rows = queries.list_companies(conn, company_id=company_id)
        if not rows:
            raise HTTPException(404, f"company {company_id} not found")
        return _company(rows[0])

    @app.post("/api/companies", status_code=201)
    def add_company(body: CompanyIn, conn: sqlite3.Connection = Conn):
        name = body.name.strip()
        if not name:
            raise HTTPException(400, "a company needs a name")
        if conn.execute("SELECT 1 FROM companies WHERE name = ?", (name,)).fetchone():
            raise HTTPException(409, f"{name} is already in the list")
        slug = normalize_board(body.board.system, body.board.slug_or_url) if body.board else None
        company_id = db.upsert_company(conn, name, canadian=body.canadian, careers_url=body.careers_url or None)
        if body.board:
            db.upsert_board(conn, company_id, body.board.system, slug, confirmed=True)
        return _company(queries.list_companies(conn, company_id=company_id)[0])

    @app.patch("/api/companies/{company_id}")
    def patch_company(company_id: int, body: CompanyPatch, conn: sqlite3.Connection = Conn):
        tracking.update_company(conn, company_id, **_given(body))
        return _company(queries.list_companies(conn, company_id=company_id)[0])

    @app.post("/api/companies/{company_id}/boards", status_code=201)
    def add_board(company_id: int, body: BoardIn, conn: sqlite3.Connection = Conn):
        if conn.execute("SELECT 1 FROM companies WHERE id = ?", (company_id,)).fetchone() is None:
            raise HTTPException(404, f"company {company_id} not found")
        slug = normalize_board(body.system, body.slug_or_url)
        owner = conn.execute("SELECT company_id FROM boards WHERE system = ? AND slug_or_url = ?",
                             (body.system, slug)).fetchone()
        if owner and owner[0] != company_id:
            raise HTTPException(409, "that board already belongs to another company")
        db.upsert_board(conn, company_id, body.system, slug, confirmed=True, enabled=True)
        return _company(queries.list_companies(conn, company_id=company_id)[0])

    @app.patch("/api/boards/{board_id}")
    def patch_board(board_id: int, body: BoardPatch, conn: sqlite3.Connection = Conn):
        tracking.update_board(conn, board_id, **_given(body))
        return dict(conn.execute("SELECT * FROM boards WHERE id = ?", (board_id,)).fetchone())

    @app.post("/api/companies/{company_id}/accept-size")
    def accept_size(company_id: int, conn: sqlite3.Connection = Conn):
        if not enrich.accept_suggestion(conn, company_id):
            raise HTTPException(409, "there is no size suggestion to accept, or a better size is already set")
        return _company(queries.list_companies(conn, company_id=company_id)[0])

    @app.post("/api/detect")
    def detect_board(body: DetectIn):
        """Which job board a company uses, from its careers link or its name."""
        return [_detected(d) for d in detect(body.name, body.careers_url, body.canadian)]

    # company sizes

    @app.post("/api/enrich", status_code=202)
    def start_enrich(body: EnrichIn | None = None, conn: sqlite3.Connection = Conn):
        if body and body.company_id is not None:
            row = conn.execute("SELECT name FROM companies WHERE id = ?", (body.company_id,)).fetchone()
            if row is None:
                raise HTTPException(404, f"company {body.company_id} not found")
            summary = enrich.run_enrich(conn, settings, company=row["name"], transport=transport)
            return {"result": "; ".join(summary.details) or "No size found on Wikidata."}

        def work(progress) -> str:
            own = db.connect(db_path)
            try:
                s = enrich.run_enrich(own, settings, transport=transport, progress=progress)
            finally:
                own.close()
            return (f"Looked up {s.looked_up} companies: {s.from_wikidata} sizes from Wikidata, "
                    f"{s.suggested} suggestions to check, {s.estimated} estimated.")

        if not tasks.start("sizes", work):
            raise HTTPException(409, "another task is already running")
        return tasks.state()

    @app.get("/api/tasks/current")
    def current_task():
        return tasks.state()

    # candidates (companies suggested by outside lists)

    @app.get("/api/candidates")
    def list_candidates(request: Request, conn: sqlite3.Connection = Conn):
        rows = candidates.list_candidates(
            conn, decision=request.query_params.get("decision", "pending"),
            scope=request.query_params.get("scope", "canada"), query=request.query_params.get("q"))
        return {"refreshed_at": db.get_setting(conn, "stillhiring_refreshed_at"),
                "items": [_candidate(r) for r in rows]}

    @app.post("/api/candidates/refresh")
    def refresh_candidates(conn: sqlite3.Connection = Conn):
        try:
            s = candidates.refresh(conn, settings, transport=transport)
        except FetchError as exc:
            raise HTTPException(502, f"stillhiring.today couldn't be read: {exc}") from exc
        return {"total": s.total, "new": s.new, "gone": s.gone, "canadian": s.canadian,
                "linked": s.linked, "sizes": s.sizes}

    @app.post("/api/candidates/{listing_id}/approve")
    def approve_candidate(listing_id: int, body: ApproveIn | None = None, conn: sqlite3.Connection = Conn):
        body = body or ApproveIn()
        company_id = candidates.approve(conn, listing_id, body.system, body.slug_or_url)
        return {"company_id": company_id}

    @app.post("/api/candidates/{listing_id}/reject")
    def reject_candidate(listing_id: int, conn: sqlite3.Connection = Conn):
        candidates.decide(conn, listing_id, "rejected")
        return {"ok": True}

    @app.post("/api/candidates/{listing_id}/restore")
    def restore_candidate(listing_id: int, conn: sqlite3.Connection = Conn):
        candidates.decide(conn, listing_id, "pending")
        return {"ok": True}

    @app.post("/api/candidates/{listing_id}/detect")
    def detect_candidate(listing_id: int, conn: sqlite3.Connection = Conn):
        row = conn.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()
        if row is None:
            raise HTTPException(404, f"candidate {listing_id} not found")
        found = detect(row["name"], row["jobs_url"], row["hq_country"] == "CA")
        best = found[0] if found else None
        candidates.set_detected(conn, listing_id, best.system if best else None, best.slug_or_url if best else None,
                                best.note if best else "No job board found; add one by hand.")
        return {"options": [_detected(d) for d in found]}

    @app.post("/api/candidates/detect-all", status_code=202)
    def detect_all(conn: sqlite3.Connection = Conn):
        todo = [dict(r) for r in conn.execute(
            "SELECT id, name, jobs_url, hq_country FROM listings WHERE decision = 'pending' AND hq_country = 'CA' "
            "AND detected_system IS NULL AND detect_note IS NULL AND gone_at IS NULL")]

        def work(progress) -> str:
            own = db.connect(db_path)
            found = 0
            try:
                for i, row in enumerate(todo, start=1):
                    hits = detect(row["name"], row["jobs_url"], True)
                    best = hits[0] if hits else None
                    found += best is not None
                    candidates.set_detected(own, row["id"], best.system if best else None,
                                            best.slug_or_url if best else None,
                                            best.note if best else "No job board found; add one by hand.")
                    progress(i, len(todo))
            finally:
                own.close()
            return f"Found job boards for {found} of {len(todo)} companies."

        if not tasks.start("boards", work):
            raise HTTPException(409, "another task is already running")
        return tasks.state()

    # saved searches

    @app.get("/api/saved-searches")
    def saved_searches(conn: sqlite3.Connection = Conn):
        return tracking.list_saved_searches(conn)

    @app.post("/api/saved-searches", status_code=201)
    def save_search(body: SavedSearchIn, conn: sqlite3.Connection = Conn):
        search_id = tracking.save_search(conn, body.name, body.query, body.filters, body.use_for_sources)
        return next(s for s in tracking.list_saved_searches(conn) if s["id"] == search_id)

    @app.patch("/api/saved-searches/{search_id}")
    def patch_search(search_id: int, body: SavedSearchPatch, conn: sqlite3.Connection = Conn):
        tracking.update_saved_search(conn, search_id, **_given(body))
        return next(s for s in tracking.list_saved_searches(conn) if s["id"] == search_id)

    @app.delete("/api/saved-searches/{search_id}", status_code=204)
    def delete_search(search_id: int, conn: sqlite3.Connection = Conn):
        tracking.delete_saved_search(conn, search_id)
        return Response(status_code=204)

    # scans

    @app.post("/api/scans", status_code=202)
    def start_scan(body: ScanIn | None = None, conn: sqlite3.Connection = Conn):
        company = None
        if body and body.company_id is not None:
            row = conn.execute("SELECT name FROM companies WHERE id = ?", (body.company_id,)).fetchone()
            if row is None:
                raise HTTPException(404, f"company {body.company_id} not found")
            company = row["name"]
        if not runner.start(company):
            raise HTTPException(409, "a scan is already running")
        return runner.state()

    @app.get("/api/scans/current")
    def current_scan():
        return runner.state()

    @app.get("/api/scans")
    def scans(conn: sqlite3.Connection = Conn):
        return queries.scan_history(conn)

    @app.get("/api/scans/{scan_id}")
    def scan_detail(scan_id: int, conn: sqlite3.Connection = Conn):
        row = conn.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
        if row is None:
            raise HTTPException(404, f"scan {scan_id} not found")
        return {"scan": dict(row), "results": queries.scan_results(conn, scan_id)}

    # the UI: real files from static/, index.html for every other path

    @app.get("/api/{rest:path}", include_in_schema=False)
    def api_not_found(rest: str):
        raise HTTPException(404, f"no API endpoint /api/{rest}")

    @app.get("/{path:path}", include_in_schema=False)
    def ui(path: str):
        index = STATIC_DIR / "index.html"
        if not index.is_file():
            return HTMLResponse(NOT_BUILT)
        target = (STATIC_DIR / path).resolve()
        if path and target.is_file() and STATIC_DIR.resolve() in target.parents:
            return FileResponse(target)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return app
