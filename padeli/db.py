"""SQLite connection and initialization helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import click
from flask import current_app, g
from flask.cli import with_appcontext


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        database_path = Path(current_app.config["DATABASE"])
        database_path.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(database_path, detect_types=sqlite3.PARSE_DECLTYPES, timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA busy_timeout = 5000")
    return g.db


def close_db(error=None) -> None:
    database = g.pop("db", None)
    if database is not None:
        database.close()


def init_db() -> None:
    database = get_db()
    schema_path = Path(__file__).with_name("schema.sql")
    database.executescript(schema_path.read_text(encoding="utf-8"))
    database.commit()


@click.command("init-db")
@with_appcontext
def init_db_command() -> None:
    """Create any missing Padeli Hyeti database tables."""
    init_db()
    click.echo("Padeli Hyeti database initialized.")


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
