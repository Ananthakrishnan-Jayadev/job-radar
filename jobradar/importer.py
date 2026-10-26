"""Import a company list from a spreadsheet (.xlsx or .csv) the user made.

What it understands, in any sheet:
- A table with a header row naming a company column ("Company", "Name").
  In each row, the first real web link (not a Google or LinkedIn search) is
  taken as the careers page; a "website" column as the website. A "size" or
  "employees" column gives the head count or a range ("51-200").
- A grouped list: lines like "Xello (51-200)" under headings like
  "TIER A: Two lists (40)". The range becomes the company size and the
  headings go into the company's notes.

.xlsx files are read with the standard library (they are zipped XML), so no
spreadsheet package is needed.
"""

from __future__ import annotations

import csv
import re
import sqlite3
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from . import db
from .candidates import norm_name
from .enrich import apply_size

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_SEARCH_LINKS = re.compile(r"google\.[a-z.]+/search|bing\.com/search|duckduckgo\.com|linkedin\.com/(jobs/search|company/)")
_RANGE = re.compile(r"^(.*\S)\s*\(\s*(\d[\d,]*)\s*(?:-|–|to)\s*(\d[\d,]*)\s*\)\s*$")
_PLUS = re.compile(r"^(.*\S)\s*\(\s*(\d[\d,]*)\s*\+\s*\)\s*$")
_HEADING = re.compile(r"^(.*\S)\s*\(\s*\d+\s*\)\s*$")  # "TIER A: Two lists (40)": a count, not a size


class ImportError_(ValueError):
    """The file can't be read as a company list."""


@dataclass
class ImportedCompany:
    name: str
    careers_url: str | None = None
    website: str | None = None
    size_low: int | None = None
    size_high: int | None = None
    groups: list[str] = field(default_factory=list)

    @property
    def employee_count(self) -> int | None:
        """One number for a range: its middle (a 51-200 company counts as 125)."""
        if self.size_low is None:
            return None
        if self.size_high is None:
            return self.size_low
        return (self.size_low + self.size_high) // 2


# --- reading files ------------------------------------------------------------------

def read_xlsx(path: Path) -> dict[str, list[list[str]]]:
    """{sheet name: rows of cell text}. Formulas give their cached value."""
    try:
        book = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise ImportError_(f"{path.name} isn't a valid .xlsx file") from exc
    with book:
        names = book.namelist()
        shared = []
        if "xl/sharedStrings.xml" in names:
            for si in ET.fromstring(book.read("xl/sharedStrings.xml")).findall(f"{_NS}si"):
                shared.append("".join(t.text or "" for t in si.iter(f"{_NS}t")))
        rels = {}
        if "xl/_rels/workbook.xml.rels" in names:
            for rel in ET.fromstring(book.read("xl/_rels/workbook.xml.rels")):
                rels[rel.get("Id")] = rel.get("Target")
        sheets: dict[str, list[list[str]]] = {}
        workbook = ET.fromstring(book.read("xl/workbook.xml"))
        for sheet in workbook.iter(f"{_NS}sheet"):
            target = rels.get(sheet.get(f"{_REL}id"), "")
            member = "xl/" + target.lstrip("/").removeprefix("xl/")
            if member not in names:
                continue
            rows = []
            for row in ET.fromstring(book.read(member)).iter(f"{_NS}row"):
                cells: dict[int, str] = {}
                for c in row.findall(f"{_NS}c"):
                    column = _column_index(c.get("r", "A1"))
                    value = c.find(f"{_NS}v")
                    inline = c.find(f"{_NS}is")
                    if c.get("t") == "s" and value is not None:
                        cells[column] = shared[int(value.text)]
                    elif inline is not None:
                        cells[column] = "".join(t.text or "" for t in inline.iter(f"{_NS}t"))
                    elif value is not None and value.text is not None:
                        cells[column] = value.text
                if cells:
                    rows.append([cells.get(i, "").strip() for i in range(max(cells) + 1)])
            sheets[sheet.get("name", member)] = rows
    return sheets


def _column_index(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref).group(0)
    index = 0
    for ch in letters:
        index = index * 26 + ord(ch) - 64
    return index - 1


def read_csv(path: Path) -> dict[str, list[list[str]]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return {path.stem: [[c.strip() for c in row] for row in csv.reader(f) if any(c.strip() for c in row)]}


def read_file(path: Path | str) -> dict[str, list[list[str]]]:
    path = Path(path)
    if not path.is_file():
        raise ImportError_(f"{path} doesn't exist")
    if path.suffix.lower() == ".xlsx":
        return read_xlsx(path)
    if path.suffix.lower() == ".csv":
        return read_csv(path)
    raise ImportError_("use an .xlsx or .csv file")


# --- understanding the sheets ----------------------------------------------------------

def _real_link(value: str) -> str | None:
    value = value.strip()
    if value.startswith(("http://", "https://")) and not _SEARCH_LINKS.search(value):
        return value
    return None


def _size(value: str) -> tuple[int | None, int | None]:
    numbers = [int(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", value)]
    if not numbers:
        return None, None
    return numbers[0], (numbers[1] if len(numbers) > 1 else None)


def parse_sheets(sheets: dict[str, list[list[str]]]) -> list[ImportedCompany]:
    found: dict[str, ImportedCompany] = {}

    def get(name: str) -> ImportedCompany:
        key = norm_name(name)
        if key not in found:
            # "AutoServe1" in one sheet and "AutoServe" in another are the same company.
            key = next((k for k in found if k == key.rstrip("0123456789")), key)
        return found.setdefault(key, ImportedCompany(name=name))

    for rows in sheets.values():
        if not rows:
            continue
        header = [h.lower() for h in rows[0]]
        name_col = next((i for i, h in enumerate(header) if h in ("company", "company name", "name", "employer")), None)
        if name_col is not None:
            website_col = next((i for i, h in enumerate(header) if "website" in h), None)
            careers_cols = [i for i, h in enumerate(header) if "career" in h or "jobs page" in h]
            size_col = next((i for i, h in enumerate(header) if "size" in h or "employees" in h), None)
            for row in rows[1:]:
                if name_col >= len(row) or not row[name_col]:
                    continue
                company = get(row[name_col])
                links = [(i, _real_link(v)) for i, v in enumerate(row) if i != name_col]
                links = [(i, url) for i, url in links if url]
                preferred = [url for i, url in links if i in careers_cols]
                others = [url for i, url in links if i != website_col]
                company.careers_url = company.careers_url or (preferred or others or [None])[0]
                if website_col is not None and website_col < len(row):
                    company.website = company.website or _real_link(row[website_col])
                if size_col is not None and size_col < len(row) and row[size_col]:
                    company.size_low, company.size_high = _size(row[size_col])
            continue
        # A grouped list: headings and "Name (11-50)" lines in the first column.
        headings: list[str] = []
        for row in rows:
            text = row[0] if row else ""
            if not text:
                continue
            ranged, plus, heading = _RANGE.match(text), _PLUS.match(text), _HEADING.match(text)
            if ranged or plus:
                match = ranged or plus
                company = get(match.group(1))
                company.size_low = int(match.group(2).replace(",", ""))
                company.size_high = int(ranged.group(3).replace(",", "")) if ranged else None
                company.groups = list(headings)
            elif heading:
                label = heading.group(1)
                # "TIER B: ..." starts a new top level; "B1. ..." is under it.
                headings = [label] if label.upper().startswith("TIER") else headings[:1] + [label]
    return list(found.values())


# --- storing ------------------------------------------------------------------------

@dataclass
class ImportSummary:
    added: int = 0
    updated: int = 0
    with_link: int = 0
    with_size: int = 0
    names: list[str] = field(default_factory=list)


def import_companies(conn: sqlite3.Connection, companies: list[ImportedCompany], *, source: str,
                     canadian: bool = True) -> ImportSummary:
    """Add new companies and fill gaps on existing ones; never overwrite what's there."""
    summary = ImportSummary()
    existing = {norm_name(r["name"]): r["id"] for r in conn.execute("SELECT id, name FROM companies")}
    for item in companies:
        company_id = existing.get(norm_name(item.name))
        if company_id is None:
            company_id = db.upsert_company(conn, item.name, canadian=canadian)
            existing[norm_name(item.name)] = company_id
            summary.added += 1
            summary.names.append(item.name)
        else:
            summary.updated += 1
        note = f"From {source}" + (f": {' / '.join(item.groups)}" if item.groups else "")
        with conn:
            conn.execute(
                """UPDATE companies SET careers_url = COALESCE(careers_url, ?), website = COALESCE(website, ?),
                          notes = CASE WHEN instr(notes, ?) > 0 THEN notes
                                       WHEN notes = '' THEN ? ELSE notes || char(10) || ? END
                   WHERE id = ?""",
                (item.careers_url, item.website, note, note, note, company_id),
            )
        summary.with_link += item.careers_url is not None
        if apply_size(conn, company_id, item.employee_count, "imported"):
            summary.with_size += 1
    return summary
