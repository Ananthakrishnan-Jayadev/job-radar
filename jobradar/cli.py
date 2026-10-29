"""Command line: `jobradar <command>`. Run `jobradar --help` for the list."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import db, queries
from .config import load_settings
from .export import export_jobs
from .models import size_band
from .roles import sync_roles
from .scan import BoardOutcome, run_scan
from .seed import SeedError, apply_seed, load_seed_file


def _open_db(args):
    settings = load_settings(args.root)
    path = Path(args.db) if args.db else settings.database
    return db.connect(path), path


def _provinces(value: str | None) -> list[str] | None:
    return [p.strip().upper() for p in value.split(",") if p.strip()] if value else None


def cmd_init_db(args) -> int:
    conn, path = _open_db(args)
    print(f"Database ready at {path} (schema version {db.schema_version(conn)}).")
    return 0


def cmd_seed(args) -> int:
    seed_file = Path(args.file) if args.file else Path(args.root or ".") / "seeds" / "companies.toml"
    try:
        companies = load_seed_file(seed_file)
    except (OSError, SeedError) as exc:
        print(f"Could not read {seed_file}: {exc}", file=sys.stderr)
        return 1
    conn, _ = _open_db(args)
    result = apply_seed(conn, companies)
    total = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    print(f"Seeded {result.companies} companies and {result.boards} boards from {seed_file}. "
          f"{total} companies in the database.")
    return 0


def cmd_companies(args) -> int:
    conn, _ = _open_db(args)
    rows = db.list_companies(conn)
    if not rows:
        print("No companies yet. Run `jobradar seed`.")
        return 0
    width = max(len(r["name"]) for r in rows)
    print(f"{'Company':<{width}}  CA   Size       Status    Boards")
    for r in rows:
        print(f"{r['name']:<{width}}  {'yes' if r['canadian'] else 'no ':<3}  "
              f"{size_band(r['employee_count']):<9}  {r['status']:<8}  {r['boards'] or '-'}")
    print(f"\n{len(rows)} companies.")
    return 0


def _print_outcome(outcome: BoardOutcome) -> None:
    board = outcome.board
    name = f"{board.company_name} ({board.system})"
    if outcome.ok:
        line = (f"  ok    {name:<38} {outcome.jobs_canada:>4} in Canada of {outcome.total_open or 0:>5}"
                f"  +{outcome.jobs_new} new, {outcome.jobs_closed} closed  {outcome.ms / 1000:.1f}s")
        print(line)
        for warning in outcome.warnings:
            print(f"        note: {warning}")
    else:
        print(f"  FAIL  {name:<38} {outcome.error}")


def cmd_scan(args) -> int:
    settings = load_settings(args.root)
    conn, _ = _open_db(args)
    print("Scanning..." if not args.company else f"Scanning {args.company}...")
    summary = run_scan(conn, settings, company=args.company, progress=_print_outcome)
    if not summary.outcomes:
        print("No enabled boards to scan. Run `jobradar seed` first, or check the company name.")
        return 1
    stored = conn.execute("SELECT COUNT(*) FROM jobs WHERE closed_at IS NULL").fetchone()[0]
    print(f"\nDone: {summary.boards_ok} boards ok, {summary.boards_failed} failed. "
          f"{summary.jobs_new} new jobs, {summary.jobs_closed} closed. {stored} open Canadian jobs stored.")
    retired = summary.retired
    if retired.merged or retired.closed:
        print(f"Adzuna copies replaced by the company's own board: {retired.merged} merged "
              f"({retired.tracking_moved} with your tracking moved over), {retired.closed} no longer listed, closed.")
    return 0 if summary.boards_ok else 1


def cmd_add_job(args) -> int:
    import asyncio

    from . import manual
    from .http import HttpClient

    settings = load_settings(args.root)
    conn, _ = _open_db(args)
    try:
        if (found := manual.existing_job(conn, args.url)) is not None:
            print(f"Already stored as job {found}.")
            return 0

        async def go():
            async with HttpClient(settings) as client:
                return await manual.read_link(conn, client, args.url)
        draft = asyncio.run(go())
        given = {k: v for k, v in (("title", args.title), ("company", args.company), ("city", args.city),
                                   ("province", args.province)) if v}
        fields = {**{k: getattr(draft, k) for k in ("title", "company", "city", "province", "remote",
                                                     "description", "posted_at", "employment_type", "salary")},
                  **given, "remote": draft.remote or args.remote}
        if not given.get("company"):
            fields["company_id"] = draft.company_id
        job_id, _ = manual.save_job(conn, url=args.url, status=args.status, **fields)
    except manual.ManualJobError as exc:
        print(f"{exc}\nGive it with --title, --company, --province (or --remote), or add the job in the web app.",
              file=sys.stderr)
        return 1
    sync_roles(conn, settings.root)
    row = conn.execute("SELECT title, status FROM jobs WHERE id = ?", (job_id,)).fetchone()
    print(f"Added job {job_id}: {row['title']} ({row['status']}).")
    return 0


def cmd_apply(args) -> int:
    from . import resumes
    from .apply.browser import playwright_ready
    from .apply.greenhouse import ApplyError
    from .apply.run import apply_job, plan_application
    from .profile import ProfileError

    settings = load_settings(args.root)
    conn, path = _open_db(args)
    data_dir = path.parent
    if missing := playwright_ready():
        print(missing, file=sys.stderr)
        return 1
    name = args.resume
    if Path(name).is_file():  # a file elsewhere: keep a copy with the others
        name = resumes.save_resume(data_dir, Path(name).name, Path(name).read_bytes())
    try:
        plan = plan_application(conn, settings, args.job_id, name, data_dir)
    except (ApplyError, ProfileError, resumes.ResumeError) as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"Filling in the application for {plan.title} at {plan.company} with {name}...")

    def report(state: dict) -> None:
        if state.get("phase") == "ready":
            for f in state["filled"]:
                print(f"  filled: {f['label']}" + ("  (check this)" if f["check"] else ""))
            for t in state["todo"]:
                print(f"  for you: {t['label']}" + (" (required)" if t["required"] else "")
                      + (f" - {t['why']}" if t["why"] else ""))
            print("\nCheck the form in the browser window, answer what's left, then press Submit there.")

    outcome = apply_job(path, plan, name, report)
    print("Submitted: marked as Applied." if outcome == "submitted" else "Closed without submitting; nothing changed.")
    return 0


def cmd_backup(args) -> int:
    from .backup import BackupError, make_backup

    conn, path = _open_db(args)
    try:
        copy = make_backup(conn, Path(args.out) if args.out else path.parent, note=args.note or "")
    except BackupError as exc:
        print(f"Backup failed: {exc}", file=sys.stderr)
        return 1
    print(f"Backed up to {copy} ({copy.stat().st_size / 1_000_000:.1f} MB, checked).")
    return 0


def cmd_boards(args) -> int:
    conn, _ = _open_db(args)
    failing = queries.failing_boards(conn)
    if not failing:
        print(f"No board has failed its last {queries.FAILING_AFTER} scans.")
        return 0
    print(f"Boards that failed {queries.FAILING_AFTER} or more scans in a row:")
    for b in failing:
        print(f"  {b['company']} ({b['system']}:{b['slug_or_url']}): {b['failures']} in a row, "
              f"last worked {(b['last_ok_at'] or 'never')[:10]}. {b['last_error'] or ''}")
    print("\nSwitch them off or add the right board on each company's page in the web app.")
    return 0


def cmd_search(args) -> int:
    conn, _ = _open_db(args)
    sync_roles(conn, load_settings(args.root).root)
    query = " ".join(args.query) or None
    try:
        rows = queries.find_jobs(conn, query, provinces=_provinces(args.province),
                                 include_closed=args.include_closed, limit=args.limit, all_roles=args.all_roles)
    except Exception as exc:  # bad FTS syntax, e.g. an unclosed quote
        print(f"Search failed: {exc}", file=sys.stderr)
        return 1
    for r in rows:
        closed = "  [closed]" if r["closed_at"] else ""
        print(f"{r['title']}  |  {r['company']}  |  {queries.location_label(r['locations'])}"
              f"  |  {r['posted_at'] or 'date unknown'}{closed}")
        print(f"    {r['url']}")
    print(f"\n{len(rows)} jobs{' (limit reached)' if args.limit and len(rows) == args.limit else ''}.")
    return 0


def cmd_export(args) -> int:
    conn, _ = _open_db(args)
    sync_roles(conn, load_settings(args.root).root)
    count = export_jobs(conn, args.out, query=args.query, provinces=_provinces(args.province),
                        include_closed=args.include_closed, all_roles=args.all_roles)
    print(f"Wrote {count} jobs to {args.out}.")
    return 0


def cmd_serve(args) -> int:
    import shutil
    import subprocess

    import uvicorn

    from .web.app import STATIC_DIR, create_app

    settings = load_settings(args.root)
    db_path = Path(args.db) if args.db else settings.database
    watcher = None
    if args.dev:
        frontend = settings.root / "frontend"
        npm = shutil.which("npm")
        if npm is None or not (frontend / "node_modules").is_dir():
            print("--dev needs Node and the UI packages: cd frontend && npm install", file=sys.stderr)
            return 1
        # Rebuilds the UI into jobradar/web/static on every save; stops with the server.
        watcher = subprocess.Popen([npm, "run", "watch"], cwd=frontend)
    elif not (STATIC_DIR / "index.html").is_file():
        print("Note: the web UI isn't built yet (cd frontend && npm install && npm run build).")
    print(f"Job Radar on http://{args.host}:{args.port}  (Ctrl+C to stop)")
    try:
        uvicorn.run(create_app(settings, db_path), host=args.host, port=args.port, log_level="warning")
    finally:
        if watcher:
            watcher.terminate()
            watcher.wait(timeout=10)
    return 0


def cmd_enrich(args) -> int:
    from .enrich import run_enrich

    settings = load_settings(args.root)
    conn, _ = _open_db(args)
    print("Looking up company sizes on Wikidata...")
    summary = run_enrich(conn, settings, company=args.company)
    for line in summary.details:
        print(f"  {line}")
    print(f"\nLooked up {summary.looked_up} companies: {summary.from_wikidata} sizes from Wikidata, "
          f"{summary.suggested} suggestions to check on the company page, {summary.estimated} estimated.")
    return 0


def cmd_levels(args) -> int:
    from . import levels

    settings = load_settings(args.root)
    conn, _ = _open_db(args)
    sync_roles(conn, settings.root)  # also works out levels with the rules
    if args.ai:
        model = args.model or settings.ollama.model
        todo = len(levels.jobs_to_ask(conn))
        count = min(todo, args.limit) if args.limit else todo
        print(f"Asking {model} about {count} jobs missing a level or years"
              + (" (dry run: nothing is saved)" if args.dry_run else "") + "...")
        try:
            summary = levels.run_ask_ollama(conn, settings, model=model, limit=args.limit, dry_run=args.dry_run)
        except levels.LevelsError as exc:
            print(exc, file=sys.stderr)
            return 1
        for title, level, years in summary.answers:
            print(f"  {level or '?':7} {'' if years is None else f'{years}+ yrs':8} {title}")
        print(f"\n{summary.levels_found} levels and {summary.years_found} years found for jobs missing them, "
              f"{summary.failed} unusable answers.")
        if summary.stopped:
            print(f"Stopped early: {summary.stopped}")
    years = conn.execute("SELECT COUNT(*) FROM jobs WHERE closed_at IS NULL AND COALESCE(role_wanted, 1) = 1 "
                         "AND min_years IS NULL").fetchone()[0]
    counts = conn.execute(
        "SELECT COALESCE(experience_level, 'unknown') AS level, COUNT(*) FROM jobs "
        "WHERE closed_at IS NULL AND COALESCE(role_wanted, 1) = 1 GROUP BY 1").fetchall()
    by_level = dict(counts)
    print("\nOpen wanted jobs by level: " + ", ".join(
        f"{lv} {by_level.get(lv, 0)}" for lv in [*levels.LEVELS, levels.UNKNOWN_LEVEL]))
    print(f"No years of experience found: {years}.")
    left = len(levels.jobs_to_ask(conn))
    if left and not args.ai:
        print(f"{left} with a description miss a level or years; `jobradar levels --ai` asks Ollama about them.")
    return 0


def cmd_candidates(args) -> int:
    from . import candidates

    settings = load_settings(args.root)
    conn, _ = _open_db(args)
    if args.action == "refresh":
        s = candidates.refresh(conn, settings)
        print(f"stillhiring.today: {s.total} companies ({s.canadian} with a Canadian HQ), {s.new} new, "
              f"{s.gone} no longer listed. {s.linked} matched companies already on your list; "
              f"{s.sizes} sizes updated.")
        return 0
    rows = candidates.list_candidates(conn, scope="readable" if args.all else "canada")
    for r in rows:
        board = f"{r['detected_system']}:{r['detected_slug']}" if r["detected_system"] else "board not found yet"
        hq = ", ".join(p for p in (r["hq_city"], r["hq_province"], r["hq_country"]) if p)
        gone = "  [no longer listed]" if r["gone_at"] else ""
        print(f"{r['name']}  |  {hq}  |  {r['employees'] or '?'} employees  |  {board}{gone}")
    print(f"\n{len(rows)} candidates to review. Approve them in the web app (Candidates page).")
    return 0


def cmd_detect(args) -> int:
    import asyncio

    from .detect import detect_company
    from .http import HttpClient

    settings = load_settings(args.root)

    async def go():
        async with HttpClient(settings) as client:
            return await detect_company(client, settings, args.name, args.url, not args.global_company)

    found = asyncio.run(go())
    if not found:
        print("No job board found. Add one by hand on the company page.")
        return 1
    for d in found:
        print(f"{d.system}: {d.slug_or_url}  ({d.confidence}, {d.how}){'  ' + d.note if d.note else ''}")
    return 0


def cmd_import(args) -> int:
    from .importer import ImportError_, import_companies, parse_sheets, read_file

    try:
        companies = parse_sheets(read_file(args.file))
    except ImportError_ as exc:
        print(f"Could not import: {exc}", file=sys.stderr)
        return 1
    if not companies:
        print("No companies found. The file needs a 'Company' column, or lines like 'Name (11-50)'.")
        return 1
    conn, _ = _open_db(args)
    s = import_companies(conn, companies, source=Path(args.file).name, canadian=not args.not_canadian)
    print(f"Read {len(companies)} companies: {s.added} added, {s.updated} already on the list. "
          f"{s.with_link} have a careers link; {s.with_size} sizes set.")
    print("Next: `jobradar find-boards` to look for their job boards.")
    return 0


def cmd_find_boards(args) -> int:
    import asyncio

    from .detect import find_missing_boards

    settings = load_settings(args.root)
    conn, _ = _open_db(args)

    def progress(done: int, total: int) -> None:
        print(f"\r  {done} of {total} companies checked", end="", flush=True)

    print("Looking for job boards (careers pages first, then guesses from the name)...")
    s = asyncio.run(find_missing_boards(conn, settings, company=args.company, progress=progress))
    print()
    for line in s.details:
        print(f"  {line}")
    print(f"\nChecked {s.checked} companies without a job board: found {s.found} "
          f"({s.unconfirmed} guessed from the name; confirm those on each company's page).")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jobradar", description=__doc__)
    parser.add_argument("--root", help="project folder with config.toml (default: current folder)")
    parser.add_argument("--db", help="database file (default: from config.toml)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="create or upgrade the database").set_defaults(func=cmd_init_db)

    seed = sub.add_parser("seed", help="load the starting company list")
    seed.add_argument("--file", help="seed file (default: seeds/companies.toml)")
    seed.set_defaults(func=cmd_seed)

    sub.add_parser("companies", help="list companies and their boards").set_defaults(func=cmd_companies)

    scan = sub.add_parser("scan", help="fetch jobs from every enabled board")
    scan.add_argument("--company", help="scan only this company (by name)")
    scan.set_defaults(func=cmd_scan)

    province_help = "comma-separated province codes, REMOTE for Canada-wide remote (default: all of Canada)"
    search = sub.add_parser("search", help="search stored jobs")
    search.add_argument("query", nargs="*", help='words, "exact phrase", OR, prefix* (empty: newest jobs)')
    search.add_argument("--province", help=province_help)
    search.add_argument("--limit", type=int, default=25)
    search.add_argument("--include-closed", action="store_true")
    search.add_argument("--all-roles", action="store_true", help="include roles that roles.toml leaves out")
    search.set_defaults(func=cmd_search)

    export = sub.add_parser("export", help="write jobs to a CSV file")
    export.add_argument("--out", required=True, help="CSV file to write")
    export.add_argument("--query", help="full-text query, as for search")
    export.add_argument("--province", help=province_help)
    export.add_argument("--include-closed", action="store_true")
    export.add_argument("--all-roles", action="store_true", help="include roles that roles.toml leaves out")
    export.set_defaults(func=cmd_export)

    enrich = sub.add_parser("enrich", help="fill in company sizes (Wikidata, then estimates)")
    enrich.add_argument("--company", help="only this company (by name)")
    enrich.set_defaults(func=cmd_enrich)

    add = sub.add_parser("add-job", help="add one job by its link (for sites the app can't scan)")
    add.add_argument("url")
    add.add_argument("--status", default="saved", help="saved (default), applied, ...")
    add.add_argument("--title", help="used when the page doesn't say")
    add.add_argument("--company")
    add.add_argument("--city")
    add.add_argument("--province", help="code: ON, BC, QC...")
    add.add_argument("--remote", action="store_true", help="remote anywhere in Canada")
    add.set_defaults(func=cmd_add_job)

    ap = sub.add_parser("apply", help="fill in a Greenhouse application for you to check and submit")
    ap.add_argument("job_id", type=int, help="the job's number (in its page's address)")
    ap.add_argument("--resume", required=True, help="a saved résumé's name, or a file to use (and save)")
    ap.set_defaults(func=cmd_apply)

    bk = sub.add_parser("backup", help="copy the database to a dated file (safe while the app runs)")
    bk.add_argument("--out", help="folder for the copy (default: next to the database)")
    bk.add_argument("--note", help="a word or two added to the file name")
    bk.set_defaults(func=cmd_backup)

    sub.add_parser("failing-boards", help="boards that failed their last few scans").set_defaults(func=cmd_boards)

    lv = sub.add_parser("levels", help="experience levels of wanted jobs (rules, then Ollama with --ai)")
    lv.add_argument("--ai", action="store_true", help="ask Ollama about jobs the rules can't place")
    lv.add_argument("--model", help="Ollama model (default: [ollama] model in config.toml)")
    lv.add_argument("--limit", type=int, help="ask about at most this many jobs")
    lv.add_argument("--dry-run", action="store_true", help="print the answers without saving them")
    lv.set_defaults(func=cmd_levels)

    cands = sub.add_parser("candidates", help="companies suggested by stillhiring.today")
    cands.add_argument("action", choices=["refresh", "list"])
    cands.add_argument("--all", action="store_true", help="list: also non-Canadian companies with a readable board")
    cands.set_defaults(func=cmd_candidates)

    detect = sub.add_parser("detect", help="find which job board a company uses")
    detect.add_argument("name")
    detect.add_argument("--url", help="the company's careers page")
    detect.add_argument("--global-company", action="store_true", help="the company isn't Canadian")
    detect.set_defaults(func=cmd_detect)

    imp = sub.add_parser("import-companies", help="add companies from an .xlsx or .csv list")
    imp.add_argument("file")
    imp.add_argument("--not-canadian", action="store_true", help="the companies aren't Canadian")
    imp.set_defaults(func=cmd_import)

    find = sub.add_parser("find-boards", help="find job boards for companies that have none")
    find.add_argument("--company", help="only this company (by name)")
    find.set_defaults(func=cmd_find_boards)

    serve = sub.add_parser("serve", help="run the web app")
    serve.add_argument("--host", default="127.0.0.1", help="default 127.0.0.1 (this computer only)")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--dev", action="store_true", help="also rebuild the UI on every save (needs npm)")
    serve.set_defaults(func=cmd_serve)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
