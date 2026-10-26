from pathlib import Path

import pytest

from jobradar import cli
from jobradar.config import load_settings
from jobradar.models import size_band
from jobradar.seed import SeedError, apply_seed, load_seed_file

ROOT = Path(__file__).resolve().parent.parent
SEED_FILE = ROOT / "seeds" / "companies.toml"


# --- seed --------------------------------------------------------------------------

def test_real_seed_file_loads():
    companies = load_seed_file(SEED_FILE)
    assert len(companies) >= 50
    names = {c["name"] for c in companies}
    assert {"Cohere", "Wealthsimple", "TD Bank", "Waabi"} <= names


def test_seed_twice_does_not_duplicate(conn):
    companies = load_seed_file(SEED_FILE)
    first = apply_seed(conn, companies)
    apply_seed(conn, companies)
    assert conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0] == first.companies
    assert conn.execute("SELECT COUNT(*) FROM boards").fetchone()[0] == first.boards


def test_seed_marks_possible_collisions_unconfirmed(conn):
    apply_seed(conn, load_seed_file(SEED_FILE))
    unconfirmed = {r[0] for r in conn.execute("SELECT slug_or_url FROM boards WHERE confirmed = 0")}
    assert {"maple", "float", "vector", "fable", "sonder", "rewind"} <= unconfirmed
    assert "cohere" not in unconfirmed


def test_seed_disabled_boards(conn):
    apply_seed(conn, load_seed_file(SEED_FILE))
    disabled = conn.execute(
        "SELECT system FROM boards WHERE enabled = 0 AND slug_or_url = 'hootsuite'"
    ).fetchall()
    assert [r[0] for r in disabled] == ["smartrecruiters"]


@pytest.mark.parametrize(
    "body,message",
    [
        ('[[company]]\nboards = []\n', "no name"),
        ('[[company]]\nname = "X"\nboards = [{ system = "taleo", slug = "x" }]\n', "unknown system"),
        ('[[company]]\nname = "X"\nboards = [{ system = "lever" }]\n', "no slug"),
        ('[[company]]\nname = "X"\nboards = [{ system = "workday", slug = "td" }]\n', "full careers-site URL"),
    ],
)
def test_seed_validation(tmp_path, body, message):
    path = tmp_path / "bad.toml"
    path.write_text(body)
    with pytest.raises(SeedError, match=message):
        load_seed_file(path)


# --- config ------------------------------------------------------------------------

def test_settings_defaults_without_files(tmp_path):
    settings = load_settings(tmp_path)
    assert settings.database == tmp_path / "data" / "jobradar.db"
    assert settings.workday.max_list == 400
    assert not settings.adzuna.configured
    assert "no contact set" in settings.user_agent


def test_local_config_overrides(tmp_path):
    (tmp_path / "config.toml").write_text('[general]\ndatabase = "x.db"\n[workday]\nmax_list = 100\n')
    (tmp_path / "config.local.toml").write_text(
        '[general]\ncontact = "me@example.com"\n[adzuna]\napp_id = "a"\napp_key = "b"\n'
    )
    settings = load_settings(tmp_path)
    assert settings.database == tmp_path / "x.db"
    assert settings.workday.max_list == 100
    assert settings.workday.delay_seconds == 1.0
    assert settings.adzuna.configured
    assert settings.user_agent == "job-radar/0.1 (personal use; me@example.com)"


def test_project_config_loads():
    settings = load_settings(ROOT)
    assert settings.http.max_per_host == 2


# --- models ------------------------------------------------------------------------

@pytest.mark.parametrize(
    "count,band",
    [(None, "unknown"), (0, "<50"), (49, "<50"), (50, "50-199"), (999, "200-999"),
     (1000, "1000-4999"), (5000, "5000+"), (90000, "5000+")],
)
def test_size_band(count, band):
    assert size_band(count) == band


# --- cli ---------------------------------------------------------------------------

def test_cli_init_seed_companies(tmp_path, capsys):
    db_path = str(tmp_path / "cli.db")
    assert cli.main(["--db", db_path, "init-db"]) == 0
    assert cli.main(["--db", db_path, "seed", "--file", str(SEED_FILE)]) == 0
    assert cli.main(["--db", db_path, "companies"]) == 0
    out = capsys.readouterr().out
    assert "schema version 4" in out
    assert "Cohere" in out and "ashby:cohere" in out


def test_cli_seed_missing_file(tmp_path, capsys):
    code = cli.main(["--db", str(tmp_path / "x.db"), "seed", "--file", str(tmp_path / "nope.toml")])
    assert code == 1
    assert "Could not read" in capsys.readouterr().err


def test_cli_companies_empty(tmp_path, capsys):
    assert cli.main(["--db", str(tmp_path / "x.db"), "companies"]) == 0
    assert "No companies yet" in capsys.readouterr().out
