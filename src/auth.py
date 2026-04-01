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
        self, id: int, username: str, email: str, password_hash: str, xuid: str, steam_id: str | None, psn_id: str | None
    ):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.xuid = xuid
        self.steam_id = steam_id
        self.psn_id = psn_id


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
    )


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("my_games"))
    return redirect(url_for("login"))


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
