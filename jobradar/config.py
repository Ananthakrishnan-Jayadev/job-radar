"""Settings from config.toml, overridden by config.local.toml when present."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_FILE = "config.toml"
LOCAL_CONFIG_FILE = "config.local.toml"


@dataclass
class HttpSettings:
    user_agent: str = "job-radar/0.1 (personal use; {contact})"
    fallback_user_agent: str = "Mozilla/5.0"
    timeout_seconds: float = 20
    max_per_host: int = 2
    page_delay_seconds: float = 0.5


@dataclass
class WorkdaySettings:
    max_list: int = 400
    max_details_per_scan: int = 60
    delay_seconds: float = 1.0


@dataclass
class AdzunaSettings:
    app_id: str = ""
    app_key: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.app_id and self.app_key)


@dataclass
class Settings:
    root: Path
    database: Path
    contact: str = ""
    http: HttpSettings = field(default_factory=HttpSettings)
    workday: WorkdaySettings = field(default_factory=WorkdaySettings)
    smartrecruiters_max_age_days: int = 180
    adzuna: AdzunaSettings = field(default_factory=AdzunaSettings)

    @property
    def user_agent(self) -> str:
        contact = self.contact or "no contact set"
        return self.http.user_agent.replace("{contact}", contact)


def _read(path: Path) -> dict:
    if not path.is_file():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def _merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def _pick(cls, data: dict):
    """Build a settings dataclass from the keys it knows; ignore the rest."""
    known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
    return cls(**known)


def load_settings(root: Path | str | None = None) -> Settings:
    """Load settings for the project folder *root* (default: current folder)."""
    root = Path(root) if root is not None else Path.cwd()
    data = _merge(_read(root / CONFIG_FILE), _read(root / LOCAL_CONFIG_FILE))
    general = data.get("general", {})

    database = Path(general.get("database", "data/jobradar.db"))
    if not database.is_absolute():
        database = root / database

    return Settings(
        root=root,
        database=database,
        contact=general.get("contact", ""),
        http=_pick(HttpSettings, data.get("http", {})),
        workday=_pick(WorkdaySettings, data.get("workday", {})),
        smartrecruiters_max_age_days=data.get("smartrecruiters", {}).get("max_age_days", 180),
        adzuna=_pick(AdzunaSettings, data.get("adzuna", {})),
    )
