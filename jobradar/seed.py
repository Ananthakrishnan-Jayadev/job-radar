"""Load the starting company list (seeds/companies.toml) into the database."""

from __future__ import annotations

import sqlite3
import tomllib
from dataclasses import dataclass
from pathlib import Path

from . import db
from .models import SYSTEMS


class SeedError(ValueError):
    """The seed file is malformed."""


@dataclass
class SeedResult:
    companies: int = 0
    boards: int = 0


def load_seed_file(path: Path | str) -> list[dict]:
    """Read and validate a seed file. Returns its [[company]] entries."""
    with Path(path).open("rb") as f:
        data = tomllib.load(f)
    companies = data.get("company", [])
    for i, company in enumerate(companies, start=1):
        name = company.get("name")
        if not name or not isinstance(name, str):
            raise SeedError(f"company #{i} has no name")
        for board in company.get("boards", []):
            system, slug = board.get("system"), board.get("slug")
            if system not in SYSTEMS:
                raise SeedError(f"{name}: unknown system {system!r}")
            if not slug:
                raise SeedError(f"{name}: a {system} board has no slug")
            if system in ("workday", "successfactors") and not slug.startswith("https://"):
                raise SeedError(f"{name}: a {system} board needs the full careers-site URL")
    return companies


def apply_seed(conn: sqlite3.Connection, companies: list[dict]) -> SeedResult:
    """Add the companies and boards. Running it again adds nothing new."""
    result = SeedResult()
    for company in companies:
        company_id = db.upsert_company(
            conn,
            company["name"],
            canadian=company.get("canadian", False),
            careers_url=company.get("careers_url"),
        )
        result.companies += 1
        for board in company.get("boards", []):
            db.upsert_board(
                conn,
                company_id,
                board["system"],
                board["slug"],
                confirmed=board.get("confirmed", True),
                enabled=board.get("enabled"),
            )
            result.boards += 1
    return result
