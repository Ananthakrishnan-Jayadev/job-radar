import asyncio
import zipfile

import httpx
import pytest
from fastapi.testclient import TestClient

from jobradar import cli, db
from jobradar.detect import find_missing_boards
from jobradar.importer import ImportError_, import_companies, parse_sheets, read_file
from jobradar.web import app as web_app

from conftest import FakeSources

SHEET_NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
REL_NS = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'


def make_xlsx(path, sheets: dict[str, list[list[str]]]):
    """A minimal real .xlsx: inline strings, one worksheet per entry."""
    def col(i):
        return chr(65 + i)

    with zipfile.ZipFile(path, "w") as z:
        entries = "".join(f'<sheet name="{name}" sheetId="{i + 1}" r:id="rId{i + 1}"/>' for i, name in enumerate(sheets))
        z.writestr("xl/workbook.xml", f'<workbook {SHEET_NS} {REL_NS}><sheets>{entries}</sheets></workbook>')
        rels = "".join(f'<Relationship Id="rId{i + 1}" Target="worksheets/sheet{i + 1}.xml" Type="x"/>'
                       for i in range(len(sheets)))
        z.writestr("xl/_rels/workbook.xml.rels",
                   f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}</Relationships>')
        for i, rows in enumerate(sheets.values()):
            xml_rows = "".join(
                f'<row r="{r + 1}">' + "".join(
                    f'<c r="{col(c)}{r + 1}" t="inlineStr"><is><t>{v}</t></is></c>' for c, v in enumerate(row) if v
                ) + "</row>"
                for r, row in enumerate(rows)
            )
            z.writestr(f"xl/worksheets/sheet{i + 1}.xml", f"<worksheet {SHEET_NS}><sheetData>{xml_rows}</sheetData></worksheet>")


LIST = [
    ["Company", "Found link", "Official website / lookup", "Careers / jobs page", "LinkedIn jobs search"],
    ["Ada", "https://job-boards.greenhouse.io/ada18", "https://www.google.com/search?q=Ada", "https://www.google.com/search?q=Ada+careers",
     "https://www.linkedin.com/jobs/search/?keywords=Ada"],
    ["Cerebri AI", "https://www.cerebriai.com/careers", "https://www.cerebriai.com", "", ""],
    ["Nudge", "https://www.google.com/search?q=Nudge", "", "", ""],
    ["AutoServe", "", "", "", ""],
]
GROUPS = [
    ["TIER A: Two lists (2)"], ["A1. Alignment + AI quality (2)"], ["Ada (51-200)"], ["Cerebri AI (11-50)"],
    ["TIER B: One list only (2)"], ["B2. Hireability only (2)"], ["Nudge (11-50)"], ["AutoServe1 (1,001-5,000)"],
]


@pytest.fixture
def xlsx(tmp_path):
    path = tmp_path / "joblst.xlsx"
    make_xlsx(path, {"LIST": LIST, "Sheet1": GROUPS})
    return path


def test_parse_xlsx(xlsx):
    companies = {c.name: c for c in parse_sheets(read_file(xlsx))}
    assert set(companies) == {"Ada", "Cerebri AI", "Nudge", "AutoServe"}
    assert companies["Ada"].careers_url == "https://job-boards.greenhouse.io/ada18"
    assert companies["Cerebri AI"].careers_url == "https://www.cerebriai.com/careers"
    assert companies["Cerebri AI"].website == "https://www.cerebriai.com"
    assert companies["Nudge"].careers_url is None  # only search links
    assert (companies["Ada"].size_low, companies["Ada"].size_high, companies["Ada"].employee_count) == (51, 200, 125)
    assert companies["Ada"].groups == ["TIER A: Two lists", "A1. Alignment + AI quality"]
    assert companies["Nudge"].groups == ["TIER B: One list only", "B2. Hireability only"]
    assert companies["AutoServe"].employee_count == 3000  # "AutoServe1" merged in


def test_parse_csv(tmp_path):
    path = tmp_path / "list.csv"
    path.write_text("Company,Careers page,Employees\nLoopio,https://jobs.ashbyhq.com/loopio,298\nTinEye,,\n")
    companies = {c.name: c for c in parse_sheets(read_file(path))}
    assert companies["Loopio"].careers_url == "https://jobs.ashbyhq.com/loopio"
    assert companies["Loopio"].employee_count == 298
    assert companies["TinEye"].careers_url is None


def test_bad_files(tmp_path):
    with pytest.raises(ImportError_, match="doesn't exist"):
        read_file(tmp_path / "nope.xlsx")
    (tmp_path / "x.txt").write_text("hi")
    with pytest.raises(ImportError_, match=".xlsx or .csv"):
        read_file(tmp_path / "x.txt")
    (tmp_path / "broken.xlsx").write_text("not a zip")
    with pytest.raises(ImportError_, match="isn't a valid"):
        read_file(tmp_path / "broken.xlsx")


def test_import_adds_and_never_overwrites(conn, xlsx):
    existing = db.upsert_company(conn, "Ada", canadian=True)
    conn.execute("UPDATE companies SET careers_url = 'https://ada.cx/careers', employee_count = 180, "
                 "size_source = 'stillhiring', notes = 'met at a meetup' WHERE id = ?", (existing,))
    conn.commit()
    summary = import_companies(conn, parse_sheets(read_file(xlsx)), source="joblst.xlsx")
    assert (summary.added, summary.updated) == (3, 1)
    ada = conn.execute("SELECT * FROM companies WHERE id = ?", (existing,)).fetchone()
    assert ada["careers_url"] == "https://ada.cx/careers"  # kept
    assert (ada["employee_count"], ada["size_source"]) == (180, "stillhiring")  # better source kept
    assert ada["notes"] == "met at a meetup\nFrom joblst.xlsx: TIER A: Two lists / A1. Alignment + AI quality"
    nudge = conn.execute("SELECT * FROM companies WHERE name = 'Nudge'").fetchone()
    assert (nudge["employee_count"], nudge["size_source"], nudge["canadian"]) == (30, "imported", 1)
    # Importing again changes nothing (the note isn't repeated).
    import_companies(conn, parse_sheets(read_file(xlsx)), source="joblst.xlsx")
    assert conn.execute("SELECT notes FROM companies WHERE id = ?", (existing,)).fetchone()[0].count("joblst") == 1


def test_cli_import(tmp_path, xlsx, capsys):
    db_path = str(tmp_path / "cli.db")
    assert cli.main(["--db", db_path, "import-companies", str(xlsx)]) == 0
    assert "4 added" in capsys.readouterr().out
    assert cli.main(["--db", db_path, "import-companies", str(tmp_path / "missing.xlsx")]) == 1


# --- finding boards for companies without one ---------------------------------------------

def ashby_board(city="Toronto"):
    return {"jobs": [{"id": "1", "title": "Data Analyst", "isListed": True, "location": city,
                      "address": {"postalAddress": {"addressLocality": city, "addressRegion": "ON",
                                                    "addressCountry": "Canada"}}}]}


def test_find_missing_boards(conn, settings):
    ada = db.upsert_company(conn, "Ada", canadian=True)
    cerebri = db.upsert_company(conn, "Cerebri AI", canadian=True)
    nudge = db.upsert_company(conn, "Nudge", canadian=True)
    has_board = db.upsert_company(conn, "Done Co", canadian=True)
    db.upsert_board(conn, has_board, "lever", "done")
    conn.execute("UPDATE companies SET careers_url = 'https://job-boards.greenhouse.io/ada18' WHERE id = ?", (ada,))
    conn.execute("UPDATE companies SET careers_url = 'https://www.cerebriai.com/careers' WHERE id = ?", (cerebri,))
    conn.commit()
    sources = FakeSources({
        ("GET", "https://www.cerebriai.com/careers"): httpx.Response(200, text='<a href="https://jobs.lever.co/cerebri">Jobs</a>'),
        ("GET", "https://api.ashbyhq.com/posting-api/job-board/nudge"): ashby_board(),
    })
    seen = []
    summary = asyncio.run(find_missing_boards(conn, settings, transport=sources.transport(),
                                              progress=lambda d, t: seen.append((d, t))))
    assert (summary.checked, summary.found, summary.unconfirmed) == (3, 3, 1)
    boards = {r["company_id"]: (r["system"], r["slug_or_url"], r["confirmed"])
              for r in conn.execute("SELECT * FROM boards")}
    assert boards[ada] == ("greenhouse", "ada18", 1)  # from the link: confirmed
    assert boards[cerebri] == ("lever", "cerebri", 1)  # from the careers page: confirmed
    assert boards[nudge] == ("ashby", "nudge", 0)  # guessed: unconfirmed
    assert seen[-1] == (3, 3)
    assert not [r for r in sources.requests if "done" in str(r.url)]  # companies with a board are skipped


def test_find_boards_none_found(conn, settings):
    db.upsert_company(conn, "Nobody Inc", canadian=True)
    summary = asyncio.run(find_missing_boards(conn, settings, transport=FakeSources().transport()))
    assert (summary.found, summary.details) == (0, ["Nobody Inc: no job board found"])


def test_find_boards_endpoint(settings, tmp_path):
    conn = db.connect(tmp_path / "w.db")
    db.upsert_company(conn, "Nudge", canadian=True)
    conn.close()
    sources = FakeSources({("GET", "https://api.ashbyhq.com/posting-api/job-board/nudge"): ashby_board()})
    client = TestClient(web_app.create_app(settings, tmp_path / "w.db", transport=sources.transport()))
    assert client.post("/api/find-boards").status_code == 202
    client.app.state.tasks.wait(10)
    assert "found 1" in client.get("/api/tasks/current").json()["result"]
