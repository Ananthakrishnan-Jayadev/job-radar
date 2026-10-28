"""Decide whether a job title is one the user wants, from roles.toml.

Categories: software development, data engineering & analysis, AI development
& implementation (on by default), and "adjacent" (off by default). The rules
and their order are explained at the top of roles.toml.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
import tomllib
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ROLES_FILE = "roles.toml"
ADJACENT = "adjacent"


def fold(title: str) -> str:
    """Lowercase, no accents, punctuation as spaces, a space at each end."""
    text = unicodedata.normalize("NFKD", title)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return " " + re.sub(r"[^a-z0-9+#.]+", " ", text).strip() + " "


def _any(patterns: list[str]) -> re.Pattern | None:
    return re.compile("|".join(f"(?:{p})" for p in patterns)) if patterns else None


@dataclass
class Verdict:
    categories: list[str] = field(default_factory=list)  # empty: not wanted
    reason: str = ""  # why it's out, for "show me what was dropped"

    @property
    def wanted(self) -> bool:
        return bool(self.categories)


@dataclass
class RoleRules:
    labels: dict[str, str]
    enabled: set[str]
    include: dict[str, re.Pattern]
    exclude: re.Pattern | None
    soft: re.Pattern | None
    strong: re.Pattern | None
    ai_role: re.Pattern | None

    @classmethod
    def from_dict(cls, data: dict) -> RoleRules:
        categories = data.get("categories", {})
        rules = data.get("rules", {})
        return cls(
            labels={name: c.get("label", name) for name, c in categories.items()},
            enabled={name for name, c in categories.items() if c.get("enabled", True)},
            include={name: _any(c.get("include", [])) for name, c in categories.items() if c.get("include")},
            exclude=_any(rules.get("exclude", [])),
            soft=_any(rules.get("soft", [])),
            strong=_any(rules.get("strong", [])),
            ai_role=_any(rules.get("ai_role", [])),
        )

    def judge(self, title: str) -> Verdict:
        """All categories a title belongs to, enabled or not, and why it's out if it is."""
        t = fold(title)
        if self.exclude and (m := self.exclude.search(t)):
            return Verdict(reason=f"excluded: {m.group(0).strip()}")
        hits = [name for name, rx in self.include.items() if name != ADJACENT and rx.search(t)]
        if hits == ["ai"] and self.ai_role and not self.ai_role.search(t):
            return Verdict(reason="mentions AI but names no role")
        if hits:
            if self.soft and (m := self.soft.search(t)) and not (self.strong and self.strong.search(t)):
                return Verdict([ADJACENT], reason=f"adjacent: {m.group(0).strip()}")
            return Verdict(hits)
        if ADJACENT in self.include and self.include[ADJACENT].search(t):
            return Verdict([ADJACENT], reason="adjacent")
        return Verdict(reason="no matching role")

    def wanted(self, title: str) -> bool:
        """Is the title in an enabled category?"""
        return any(c in self.enabled for c in self.judge(title).categories)


def load_rules(path: Path | str) -> RoleRules:
    with Path(path).open("rb") as f:
        return RoleRules.from_dict(tomllib.load(f))


@lru_cache(maxsize=4)
def _cached_rules(path: str, digest: str) -> RoleRules:
    return load_rules(path)


def rules_for(root: str | Path) -> RoleRules | None:
    """The project's rules, or None when it has no roles.toml (keep every title).
    Re-read whenever the file changes."""
    path = Path(root) / ROLES_FILE
    if not path.is_file():
        return None
    return _cached_rules(str(path), _digest(path))


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sync_roles(conn: sqlite3.Connection, root: str | Path) -> int:
    """Store each job's role categories. Recomputes every job when roles.toml has
    changed since last time, otherwise only jobs not done yet. Returns jobs updated.

    Without a roles.toml, every job is marked unknown (NULL), which shows it.
    Then works out experience levels for newly wanted jobs (levels.py).
    """
    from .levels import sync_levels

    updated = _sync_role_columns(conn, root)
    sync_levels(conn)
    return updated


def _sync_role_columns(conn: sqlite3.Connection, root: str | Path) -> int:
    from . import db

    path = Path(root) / ROLES_FILE
    digest = _digest(path) if path.is_file() else ""
    changed = db.get_setting(conn, "roles_digest") != digest
    if not digest:
        if changed:
            with conn:
                conn.execute("UPDATE jobs SET role_categories = NULL, role_wanted = NULL")
            db.set_setting(conn, "roles_digest", digest)
        return 0
    rules = rules_for(root)
    sql = "SELECT id, title FROM jobs" + ("" if changed else " WHERE role_wanted IS NULL")
    rows = conn.execute(sql).fetchall()
    updates = []
    for job_id, title in rows:
        categories = rules.judge(title).categories
        wanted = any(c in rules.enabled for c in categories)
        updates.append(("," + ",".join(categories) + "," if categories else "", int(wanted), job_id))
    with conn:
        conn.executemany("UPDATE jobs SET role_categories = ?, role_wanted = ? WHERE id = ?", updates)
    if changed:
        db.set_setting(conn, "roles_digest", digest)
    return len(updates)
