import os
import sqlite3

from flask import g

_APP_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE = os.environ.get(
    "DATABASE",
    os.path.join(_APP_DIR, "..", "overachiever.db"),
)


def get_db():
    """Open a database connection scoped to the current request."""
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(exception):
    """Close the database connection at the end of a request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create the tables if they don't exist."""
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            xuid TEXT DEFAULT NULL,
            steam_id TEXT DEFAULT NULL,
            psn_id TEXT DEFAULT NULL
        );
        CREATE TABLE IF NOT EXISTS guides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            title TEXT,
            description TEXT,
            platform_id INTEGER NOT NULL,
            title_id INTEGER NOT NULL,
            achievement_id INTEGER DEFAULT NULL,
            user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS xbox360icons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            title_id INTEGER NOT NULL,
            achievement_id INTEGER NOT NULL
        );
        """
    )
    db.commit()
