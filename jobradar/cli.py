"""Command line: `jobradar <command>`. Run `jobradar --help` for the list."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import db
from .config import load_settings
from .models import size_band
from .seed import SeedError, apply_seed, load_seed_file


def _open_db(args):
    settings = load_settings(args.root)
    path = Path(args.db) if args.db else settings.database
    return db.connect(path), path


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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
