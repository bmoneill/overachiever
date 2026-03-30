import os
import sqlite3

import requests
from dotenv import load_dotenv
from flask import Flask, flash, g, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "overachiever.db")

OPENXBL_API_KEY = os.environ.get("OPENXBL_API_KEY")
OPENXBL_BASE_URL = "https://api.xbl.io"
ALLOW_REGISTRATION = os.environ.get("ALLOW_REGISTRATION", "true").lower() not in (
    "false",
    "0",
    "no",
)

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def get_db():
    """Open a database connection scoped to the current request."""
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create the users table if it doesn't exist."""
    db = get_db()
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            xuid TEXT NOT NULL
        )
        """
    )
    db.commit()


with app.app_context():
    init_db()

# ---------------------------------------------------------------------------
# Flask-Login setup
# ---------------------------------------------------------------------------

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "error"


class User(UserMixin):
    def __init__(self, id, username, email, password_hash, xuid):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.xuid = xuid


@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        return None
    return User(
        id=row["id"],
        username=row["username"],
        email=row["email"],
        password_hash=row["password_hash"],
        xuid=row["xuid"],
    )


def get_user_by_username(username):
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
    )


# ---------------------------------------------------------------------------
# OpenXBL API helper
# ---------------------------------------------------------------------------


def xbl_get(path):
    """Make an authenticated GET request to the OpenXBL API.

    Returns the unwrapped 'content' payload on success, or None on failure.
    On failure a flash message is set automatically.
    """
    if not OPENXBL_API_KEY:
        flash("OPENXBL_API_KEY is not set. Please add it to your .env file.", "error")
        return None

    headers = {
        "X-Authorization": OPENXBL_API_KEY,
        "Accept": "application/json",
    }

    try:
        resp = requests.get(
            f"{OPENXBL_BASE_URL}{path}",
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as exc:
        if hasattr(exc, "response") and exc.response is not None:
            flash(
                f"OpenXBL returned status {exc.response.status_code}. "
                "Check that the XUID is correct.",
                "error",
            )
        else:
            flash(f"Failed to reach OpenXBL: {exc}", "error")
        return None

    # The OpenXBL API wraps responses in {"content": ..., "code": ...}.
    # Unwrap if present, otherwise return the raw data.
    if isinstance(data, dict) and "content" in data:
        return data["content"]
    return data


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
        xuid = request.form.get("xuid", "").strip()

        if not username or not email or not password or not xuid:
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
            "INSERT INTO users (username, email, password_hash, xuid) VALUES (?, ?, ?, ?)",
            (username, email, password_hash, xuid),
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


# ---------------------------------------------------------------------------
# Game / Achievement routes
# ---------------------------------------------------------------------------


@app.route("/my-games")
@login_required
def my_games():
    """Redirect to the current user's games page."""
    return redirect(url_for("games", username=current_user.username))


@app.route("/games/<username>")
@login_required
def games(username):
    """Show the list of games a player owns with achievement counts."""
    target_user = get_user_by_username(username)
    if target_user is None:
        flash("User not found.", "error")
        return redirect(url_for("my_games"))

    content = xbl_get(f"/v2/titles/{target_user.xuid}")
    if content is None:
        return redirect(url_for("my_games"))

    titles = content.get("titles", []) if isinstance(content, dict) else []

    return render_template(
        "games.html",
        titles=titles,
        xuid=target_user.xuid,
        username=target_user.username,
    )


@app.route("/games/<username>/<title_id>")
@login_required
def game_achievements(username, title_id):
    """Show unlocked and locked achievements for a specific game."""
    target_user = get_user_by_username(username)
    if target_user is None:
        flash("User not found.", "error")
        return redirect(url_for("my_games"))

    content = xbl_get(f"/v2/achievements/player/{target_user.xuid}/{title_id}")
    if content is None:
        return redirect(url_for("games", username=username))

    # The response may be a dict with an "achievements" key, or a list directly.
    if isinstance(content, dict):
        achievements = content.get("achievements", [])
    elif isinstance(content, list):
        achievements = content
    else:
        achievements = []

    unlocked = []
    locked = []
    game_name = None

    for a in achievements:
        # Try to grab the game name from the first achievement's titleAssociations
        if game_name is None:
            assocs = a.get("titleAssociations", [])
            if assocs:
                game_name = assocs[0].get("name")

        if a.get("progressState") == "Achieved":
            unlocked.append(a)
        else:
            locked.append(a)

    if game_name is None:
        game_name = f"Title {title_id}"

    return render_template(
        "game_achievements.html",
        unlocked=unlocked,
        locked=locked,
        game_name=game_name,
        xuid=target_user.xuid,
        username=target_user.username,
        title_id=title_id,
    )


if __name__ == "__main__":
    app.run(debug=True)
