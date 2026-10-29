"""Résumés kept for applications, in data/resumes/ (git-ignored)."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

KINDS = (".pdf", ".docx", ".doc")
MAX_BYTES = 10_000_000  # Greenhouse's limit is about the same


class ResumeError(ValueError):
    pass


def folder(data_dir: Path | str) -> Path:
    return Path(data_dir) / "resumes"


def list_resumes(data_dir: Path | str) -> list[dict]:
    """Saved résumés, newest first."""
    found = [p for p in folder(data_dir).glob("*") if p.is_file() and p.suffix.lower() in KINDS]
    found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [{"name": p.name, "size": p.stat().st_size,
             "saved_at": datetime.fromtimestamp(p.stat().st_mtime, UTC).replace(microsecond=0).isoformat()}
            for p in found]


def save_resume(data_dir: Path | str, filename: str, content: bytes) -> str:
    """Store an uploaded résumé under a safe name; never overwrites. Returns the name."""
    stem, suffix = Path(filename or "").stem, Path(filename or "").suffix.lower()
    if suffix not in KINDS:
        raise ResumeError("A résumé must be a PDF or Word file (.pdf, .docx, .doc).")
    if not content:
        raise ResumeError("That file is empty.")
    if len(content) > MAX_BYTES:
        raise ResumeError("That file is over 10 MB; job sites won't take it.")
    stem = re.sub(r"[^\w.-]+", "-", stem).strip("-.") or "resume"
    target = folder(data_dir)
    target.mkdir(parents=True, exist_ok=True)
    path, n = target / f"{stem}{suffix}", 2
    while path.exists():
        path, n = target / f"{stem}-{n}{suffix}", n + 1
    path.write_bytes(content)
    return path.name


def resume_path(data_dir: Path | str, name: str) -> Path:
    """The file for a saved résumé's name; refuses anything outside the folder."""
    path = folder(data_dir) / Path(name).name
    if Path(name).name != name or not path.is_file() or path.suffix.lower() not in KINDS:
        raise ResumeError(f"No saved résumé called {name!r}.")
    return path
