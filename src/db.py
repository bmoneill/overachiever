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
            bio TEXT DEFAULT NULL,
            password_hash TEXT NOT NULL,
            xuid TEXT DEFAULT NULL,
            steam_id TEXT DEFAULT NULL,
            psn_id TEXT DEFAULT NULL,
            display_gamertags BOOLEAN DEFAULT FALSE
        );
        CREATE TABLE IF NOT EXISTS achievement_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform_id INTEGER NOT NULL,
            title_id INTEGER NOT NULL,
            achievement_id INTEGER NOT NULL,
            game_name TEXT DEFAULT NULL,
            achievement_name TEXT DEFAULT NULL,
            achievement_description TEXT DEFAULT NULL
        );
        CREATE TABLE IF NOT EXISTS pinned_achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            achievement_summary_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (achievement_summary_id) REFERENCES achievement_summaries(id)
        );
        CREATE TABLE IF NOT EXISTS guides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            title TEXT,
            description TEXT,
            platform_id INTEGER NOT NULL,
            title_id INTEGER NOT NULL,
            achievement_summary_id INTEGER DEFAULT NULL,
            user_id INTEGER DEFAULT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (achievement_summary_id) REFERENCES achievement_summaries(id)
        );
        CREATE TABLE IF NOT EXISTS guide_rating (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guide_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            rating BOOLEAN NOT NULL, /* True = upvote, False = downvote */
            FOREIGN KEY (guide_id) REFERENCES guides(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS showcase_games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            platform_id INTEGER NOT NULL,
            title_id TEXT NOT NULL,
            game_name TEXT NOT NULL,
            image_url TEXT DEFAULT NULL,
            current_achievements INTEGER DEFAULT 0,
            total_achievements INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS showcase_achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            platform_id INTEGER NOT NULL,
            title_id TEXT NOT NULL,
            achievement_id TEXT NOT NULL,
            game_name TEXT DEFAULT NULL,
            achievement_name TEXT NOT NULL,
            achievement_description TEXT DEFAULT NULL,
            image_url TEXT DEFAULT NULL,
            gamerscore INTEGER DEFAULT NULL,
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
