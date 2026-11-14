"""Loading settings from a .env file (justchess.envfile)."""

from __future__ import annotations

import logging

from justchess import envfile


def test_values_comments_quotes_and_export_are_parsed(tmp_path):
    f = tmp_path / ".env"
    f.write_text(
        "# comment\n"
        "\n"
        "JUSTCHESS_VAPID_KEY_FILE=/home/x/.config/justchess/vapid.pem\n"
        "export JUSTCHESS_DB = 'other.sqlite3'\n"
        'JUSTCHESS_VAPID_SUBJECT="mailto:me@example.com"\n',
        encoding="utf-8",
    )
    env: dict[str, str] = {}
    applied = envfile.load(f, env)
    assert env == {
        "JUSTCHESS_VAPID_KEY_FILE": "/home/x/.config/justchess/vapid.pem",
        "JUSTCHESS_DB": "other.sqlite3",
        "JUSTCHESS_VAPID_SUBJECT": "mailto:me@example.com",
    }
    assert sorted(applied) == sorted(env)


def test_the_real_environment_wins_over_the_file(tmp_path):
    f = tmp_path / ".env"
    f.write_text("JUSTCHESS_DB=from-file.sqlite3\nJUSTCHESS_ORIGIN=https://x.example\n"
                 "DATABASE_URL=postgresql://file.invalid/db\n", encoding="utf-8")
    env = {"JUSTCHESS_DB": "from-shell.sqlite3", "DATABASE_URL": "postgresql://shell.invalid/db"}
    applied = envfile.load(f, env)
    assert env["JUSTCHESS_DB"] == "from-shell.sqlite3"
    assert env["JUSTCHESS_ORIGIN"] == "https://x.example"
    assert env["DATABASE_URL"] == "postgresql://shell.invalid/db"
    assert applied == ["JUSTCHESS_ORIGIN"]


def test_a_missing_file_is_not_an_error(tmp_path):
    env: dict[str, str] = {}
    assert envfile.load(tmp_path / "absent.env", env) == []
    assert env == {}


def test_malformed_lines_are_skipped_and_logged_without_values(tmp_path, caplog):
    f = tmp_path / ".env"
    f.write_text("not a setting\n1BAD=secret-value\nGOOD=yes\n", encoding="utf-8")
    env: dict[str, str] = {}
    with caplog.at_level(logging.WARNING, logger="justchess.envfile"):
        envfile.load(f, env)
    assert env == {"GOOD": "yes"}
    assert "line 1" in caplog.text and "line 2" in caplog.text
    assert "secret-value" not in caplog.text


def test_the_example_file_only_names_settings_the_app_reads():
    values, bad = envfile.parse((envfile.PROJECT_ROOT / ".env.example").read_text(encoding="utf-8"))
    assert bad == []
    assert set(values) <= {
        "JUSTCHESS_VAPID_KEY_FILE", "JUSTCHESS_VAPID_PRIVATE_KEY", "JUSTCHESS_VAPID_SUBJECT",
        "JUSTCHESS_PUSH_HOSTS", "JUSTCHESS_DB", "JUSTCHESS_ORIGIN", "JUSTCHESS_LESSONS_DIR",
        "JUSTCHESS_PUZZLES_DIR", "STOCKFISH_AUTO_INSTALL", "JUSTCHESS_TRUSTED_PROXIES",
        "JUSTCHESS_GAMEPLAY_FILE", "DATABASE_URL",
    }


def test_the_example_file_documents_the_trusted_proxies_setting_commented_and_empty():
    """P2 U3 BR3.2: JUSTCHESS_TRUSTED_PROXIES is documented in .env.example, commented out with no value."""
    lines = (envfile.PROJECT_ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    assert "# JUSTCHESS_TRUSTED_PROXIES=" in lines
    values, _ = envfile.parse("\n".join(lines))
    assert "JUSTCHESS_TRUSTED_PROXIES" not in values, "off by default: the example sets nothing"
