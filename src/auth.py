import os
import sqlite3

from flask import flash, redirect, render_template, request, url_for
from flask_login import (
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from werkzeug.security import check_password_hash, generate_password_hash

from . import app, login_manager
from .db import get_db
from .api.platform import PLATFORM_XBOX, PLATFORM_STEAM

PLATFORM_ID_TO_SLUG = {
    PLATFORM_XBOX: "xbox",
    PLATFORM_STEAM: "steam",
}

ALLOW_REGISTRATION = os.environ.get("ALLOW_REGISTRATION", "true").lower() not in (
    "false",
    "0",
    "no",
)


# ---------------------------------------------------------------------------
# User model
# ---------------------------------------------------------------------------


class User(UserMixin):
    def __init__(
        self,
        id: int,
        username: str,
        email: str,
        password_hash: str,
        xuid: str,
        steam_id: str | None,
        psn_id: str | None,
        bio: str | None = None,
        display_gamertags: bool = False,
    ):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.xuid = xuid
        self.steam_id = steam_id
        self.psn_id = psn_id
        self.bio = bio
        self.display_gamertags = display_gamertags


# ---------------------------------------------------------------------------
# Flask-Login helpers
# ---------------------------------------------------------------------------


@login_manager.user_loader
def load_user(user_id: int):
    db: sqlite3.Connection = get_db()
    row: sqlite3.Row | None = db.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if row is None:
        return None
    return User(
        id=row["id"],
        username=row["username"],
        email=row["email"],
        password_hash=row["password_hash"],
        xuid=row["xuid"],
        steam_id=row["steam_id"],
        psn_id=row["psn_id"],
        bio=row["bio"],
        display_gamertags=bool(row["display_gamertags"]),
    )


def get_user_by_username(username: str) -> User | None:
    """Look up a user by username. Returns a User or None."""
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if row is None:
        return None
    return User(
        id=row["id"],
        username=row["username"],
        email=row["email"],
        password_hash=row["password_hash"],
        xuid=row["xuid"],
        steam_id=row["steam_id"],
        psn_id=row["psn_id"],
        bio=row["bio"],
        display_gamertags=bool(row["display_gamertags"]),
    )


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("my_games"))

    db = get_db()
    recent_guides = db.execute(
        "SELECT g.id, g.url, g.title, g.description, g.created_at, "
        "       g.platform_id, g.title_id, "
        "       a.game_name, a.achievement_name, "
        "       u.username AS author "
        "FROM guides g "
        "LEFT JOIN users u ON g.user_id = u.id "
        "LEFT JOIN achievement_summaries a ON g.achievement_summary_id = a.id "
        "ORDER BY g.created_at DESC "
        "LIMIT 5"
    ).fetchall()

    return render_template(
        "index.html",
        recent_guides=recent_guides,
        platform_slugs=PLATFORM_ID_TO_SLUG,
    )


@app.route("/search")
def user_search():
    """Search for users by Overachiever username."""
    q = request.args.get("q", "").strip()
    results = []
    if q:
        db = get_db()
        results = db.execute(
            "SELECT id, username, bio FROM users WHERE username LIKE ? ORDER BY username LIMIT 20",
            (f"%{q}%",),
        ).fetchall()
    return render_template("search_results.html", query=q, results=results)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("my_games"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Please fill in all fields.", "error")
            return redirect(url_for("login"))

        user = get_user_by_username(username)
        if user is None or not check_password_hash(user.password_hash, password):
            flash("Invalid username or password.", "error")
            return redirect(url_for("login"))

        login_user(user)
        next_page = request.args.get("next")
        return redirect(next_page or url_for("my_games"))

    return render_template("login.html", allow_registration=ALLOW_REGISTRATION)


@app.route("/register", methods=["GET", "POST"])
def register():
    if not ALLOW_REGISTRATION:
        flash("Registration is currently disabled.", "error")
        return redirect(url_for("login"))

    if current_user.is_authenticated:
        return redirect(url_for("my_games"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("Please fill in all fields.", "error")
            return redirect(url_for("register"))

        db = get_db()

        # Check for existing username or email
        existing = db.execute(
            "SELECT id FROM users WHERE username = ? OR email = ?",
            (username, email),
        ).fetchone()
        if existing:
            flash("Username or email is already taken.", "error")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)
        db.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, password_hash),
        )
        db.commit()

        flash("Account created! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))
