"""Your details for filling in applications, from profile.local.toml.

The file is git-ignored (the repository is public); profile.example.toml
shows its shape. Empty values mean "leave that question for me".
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

PROFILE_FILE = "profile.local.toml"
EXAMPLE_FILE = "profile.example.toml"
REQUIRED = ("first_name", "last_name", "email", "phone")


class ProfileError(Exception):
    """The profile is missing or can't be read; the message says how to fix it."""


def _flag(value) -> bool | None:
    """true / false, "yes" / "no", or None when left empty."""
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in ("yes", "y", "true"):
        return True
    if text in ("no", "n", "false"):
        return False
    return None


@dataclass
class Profile:
    first_name: str = ""
    last_name: str = ""
    preferred_name: str = ""
    email: str = ""
    phone: str = ""
    city: str = ""
    province: str = ""
    country: str = ""
    linkedin: str = ""
    github: str = ""
    website: str = ""
    pronouns: str = ""
    authorized_canada: bool | None = None
    authorized_us: bool | None = None
    needs_sponsorship: bool | None = None
    willing_to_relocate: bool | None = None
    notice: str = ""
    salary_expectation: str = ""
    how_heard: str = ""
    answers: dict[str, str] = field(default_factory=dict)  # part of a question -> answer

    @property
    def missing(self) -> list[str]:
        """Required details that are empty."""
        return [name for name in REQUIRED if not getattr(self, name)]

    @property
    def location(self) -> str:
        return ", ".join(p for p in (self.city, self.province, self.country) if p)

    @classmethod
    def from_dict(cls, data: dict) -> Profile:
        you, work = data.get("you", {}), data.get("work", {})
        text = {k: str(v).strip() for k, v in {**you, **work}.items()
                if k in cls.__dataclass_fields__ and not isinstance(v, bool)}
        flags = {k: _flag(work.get(k)) for k in ("authorized_canada", "authorized_us", "needs_sponsorship",
                                                 "willing_to_relocate")}
        answers = {str(k).strip().lower(): str(v).strip() for k, v in data.get("answers", {}).items()
                   if str(k).strip() and str(v).strip()}
        return cls(**{**text, **flags, "answers": answers})


def load_profile(root: Path | str) -> Profile:
    path = Path(root) / PROFILE_FILE
    if not path.is_file():
        raise ProfileError(f"No {PROFILE_FILE} yet: copy {EXAMPLE_FILE} to {PROFILE_FILE} in the project folder "
                           "and fill in your details.")
    try:
        with path.open("rb") as f:
            return Profile.from_dict(tomllib.load(f))
    except tomllib.TOMLDecodeError as exc:
        raise ProfileError(f"{PROFILE_FILE} has a mistake: {exc}") from exc
