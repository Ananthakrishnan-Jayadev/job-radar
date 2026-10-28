"""Backups (a checked dated copy, the reminder) and board health (failing streaks)."""

import sqlite3
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from jobradar import backup, cli, db, queries
from jobradar.models import Location, RawJob
from jobradar.web import app as web_app


def test_backup_is_a_valid_copy(conn, tmp_path):
    company = db.upsert_company(conn, "Acme", canadian=True)
    board = db.upsert_board(conn, company, "ashby", "acme")
    db.upsert_job(conn, board, RawJob("1", "Data Analyst", "u1", [Location("Toronto", "ON", "CA")]))
    path = backup.make_backup(conn, tmp_path / "copies", note="Before cleanup!")
    assert path.name.startswith("jobradar-backup-") and path.name.endswith("-before-cleanup.db")
    copy = sqlite3.connect(path)
    assert copy.execute("SELECT title FROM jobs").fetchone()[0] == "Data Analyst"
    assert copy.execute("PRAGMA user_version").fetchone()[0] == db.schema_version(conn)
    copy.close()
    # The copy opens in a fresh folder like the real thing.
    restored = db.connect(path)
    assert restored.execute("SELECT COUNT(*) FROM companies").fetchone()[0] == 1
    restored.close()


def test_backup_status_and_reminder(tmp_path):
    now = datetime(2026, 10, 28, 12, tzinfo=UTC)
    assert backup.backup_status(tmp_path, now)["remind"] is True  # none yet
    (tmp_path / "jobradar-backup-20261020-090000.db").touch()
    (tmp_path / "jobradar-backup-20261026-143342-before-x.db").touch()
    (tmp_path / "removed-companies-20261027-010534.db").touch()  # not a backup
    status = backup.backup_status(tmp_path, now)
    assert status["latest"] == "jobradar-backup-20261026-143342-before-x.db"
    assert (status["age_days"], status["remind"]) == (1, False)
    assert backup.backup_status(tmp_path, now + timedelta(days=7))["remind"] is True


def test_cli_backup(tmp_path, capsys):
    db_path = tmp_path / "cli.db"
    db.connect(db_path).close()
    assert cli.main(["--db", str(db_path), "backup", "--note", "test"]) == 0
    assert "checked" in capsys.readouterr().out
    assert len(list(tmp_path.glob("jobradar-backup-*-test.db"))) == 1


def _scan(conn, results):
    """One scan with {board id: ok} results."""
    with conn:
        scan = conn.execute("INSERT INTO scans (started_at) VALUES (?)", (db.now(),)).lastrowid
        for board, ok in results.items():
            conn.execute("INSERT INTO scan_results (scan_id, board_id, ok, error) VALUES (?, ?, ?, ?)",
                         (scan, board, int(ok), None if ok else "HTTP 404"))
            if not ok:
                conn.execute("UPDATE boards SET last_error = 'HTTP 404' WHERE id = ?", (board,))


def _boards(conn):
    a = db.upsert_board(conn, db.upsert_company(conn, "Acme", canadian=True), "ashby", "acme")
    b = db.upsert_board(conn, db.upsert_company(conn, "Beta", canadian=True), "lever", "beta")
    c = db.upsert_board(conn, db.upsert_company(conn, "Gamma", canadian=True), "greenhouse", "gamma")
    conn.commit()
    return a, b, c


def test_failing_boards_need_three_in_a_row(conn):
    a, b, c = _boards(conn)
    _scan(conn, {a: True, b: True, c: False})
    _scan(conn, {a: False, b: False, c: False})
    _scan(conn, {a: False, b: True, c: False})
    _scan(conn, {a: False, b: False, c: False})
    assert queries.failure_streaks(conn) == {a: 3, b: 1, c: 4}
    failing = queries.failing_boards(conn)
    assert [(f["company"], f["failures"]) for f in failing] == [("Gamma", 4), ("Acme", 3)]
    assert failing[1]["last_ok_at"] and failing[0]["last_ok_at"] is None  # Gamma never worked
    assert failing[0]["last_error"] == "HTTP 404"
    _scan(conn, {a: True})
    assert [f["company"] for f in queries.failing_boards(conn)] == ["Gamma"]  # Acme recovered


def test_switched_off_boards_are_not_flagged(conn):
    a, _, _ = _boards(conn)
    for _ in range(3):
        _scan(conn, {a: False})
    with conn:
        conn.execute("UPDATE boards SET enabled = 0 WHERE id = ?", (a,))
    assert queries.failing_boards(conn) == []


def test_api_backup_and_failing(conn, tmp_path, settings):
    a, _, _ = _boards(conn)
    for _ in range(3):
        _scan(conn, {a: False})
    client = TestClient(web_app.create_app(settings, db_path=tmp_path / "test.db"))
    assert client.get("/api/backup").json()["remind"] is True
    made = client.post("/api/backup")
    assert made.status_code == 201 and made.json()["remind"] is False
    failing = client.get("/api/boards/failing").json()
    assert failing["after"] == 3 and failing["boards"][0]["company"] == "Acme"
    acme = client.get(f"/api/companies/{failing['boards'][0]['company_id']}").json()
    assert acme["boards"][0]["failures"] == 3
