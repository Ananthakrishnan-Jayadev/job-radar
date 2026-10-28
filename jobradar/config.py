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


DEFAULT_SEARCH_TERMS = ["data", "machine learning", "artificial intelligence", "analyst", "analytics"]


@dataclass
class WorkdaySettings:
    max_list: int = 400
    max_details_per_scan: int = 60
    delay_seconds: float = 1.0
    # Used for big Workday boards until saved searches exist (phase 3).
    search_terms: list[str] = field(default_factory=lambda: list(DEFAULT_SEARCH_TERMS))


@dataclass
class AdzunaSettings:
    app_id: str = ""
    app_key: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.app_id and self.app_key)


@dataclass
class OllamaSettings:
    """A local Ollama server, asked about job levels only when you run it."""
    url: str = "http://localhost:11434"
    model: str = "gemma4:31b-cloud"
    timeout_seconds: float = 180
    max_chars: int = 6000  # of each description sent


@dataclass
class Settings:
    root: Path
    database: Path
    contact: str = ""
    http: HttpSettings = field(default_factory=HttpSettings)
    workday: WorkdaySettings = field(default_factory=WorkdaySettings)
    smartrecruiters_max_age_days: int = 180
    details_per_board: int = 60  # detail pages fetched per board per scan
    adzuna: AdzunaSettings = field(default_factory=AdzunaSettings)
    ollama: OllamaSettings = field(default_factory=OllamaSettings)

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
        details_per_board=data.get("details", {}).get("max_per_board", 60),
        adzuna=_pick(AdzunaSettings, data.get("adzuna", {})),
        ollama=_pick(OllamaSettings, data.get("ollama", {})),
    )
