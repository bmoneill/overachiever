import os
import sqlite3

import requests
from bs4 import BeautifulSoup
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

from api.achievement import AchievementAPIError
from api.xbox import XboxAchievementAPI, xbl_get

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)
app._static_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

DATABASE = os.environ.get(
    "DATABASE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "overachiever.db"),
)

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

with app.app_context():
    init_db()


def fetch_url_metadata(url):
    """Fetch the title and description from a URL's HTML meta tags."""
    title = None
    description = None
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Overachiever/1.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Title: prefer Open Graph, fall back to <title>
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()
        elif soup.title and soup.title.string:
            title = soup.title.string.strip()

        # Description: prefer Open Graph, fall back to <meta name="description">
        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content"):
            description = og_desc["content"].strip()
        else:
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc and meta_desc.get("content"):
                description = meta_desc["content"].strip()
    except Exception:
        pass
    return title, description


# ---------------------------------------------------------------------------
# Flask-Login setup
# ---------------------------------------------------------------------------

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "error"


class User(UserMixin):
    def __init__(
        self, id: int, username: str, email: str, password_hash: str, xuid: str
    ):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.xuid = xuid


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
    )


# ---------------------------------------------------------------------------
# Xbox 360 icon helper (depends on Flask context)
# ---------------------------------------------------------------------------


def _get_icon_url(achievement_id: int | str, title_id: int) -> str | None:
    """Look up a locally-cached Xbox 360 icon from the database."""
    db = get_db()
    cursor = db.execute(
        "SELECT url FROM xbox360icons WHERE achievement_id = ? AND title_id = ?",
        (achievement_id, title_id),
    )
    result = cursor.fetchone()
    return url_for("static", filename=result[0]) if result else None


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

    try:
        content = xbl_get(f"/v2/titles/{target_user.xuid}")
    except AchievementAPIError as e:
        flash(str(e), "error")
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

    media_type = request.args.get("media_type", "")

    try:
        api = XboxAchievementAPI(xuid=target_user.xuid, media_type=media_type)
        unlocked = api.get_unlocked_title_achievements(target_user.xuid, title_id)
        locked = api.get_locked_title_achievements(target_user.xuid, title_id)
        game_name = api.game_name
    except AchievementAPIError as e:
        flash(str(e), "error")
        return redirect(url_for("games", username=username))

    # Override with locally-cached Xbox 360 icons when available.
    if api.is_x360:
        for a in unlocked + locked:
            icon = _get_icon_url(a.achievement_id, a.title_id)
            if icon:
                a.image_url = icon

    if game_name is None:
        game_name = request.args.get("game_name", f"Title ID: {title_id}")

    return render_template(
        "game_achievements.html",
        unlocked=unlocked,
        locked=locked,
        game_name=game_name,
        xuid=target_user.xuid,
        username=target_user.username,
        title_id=title_id,
        media_type=media_type,
    )


@app.route("/games/<username>/<title_id>/guides", methods=["GET", "POST"])
@login_required
def game_guides(username, title_id):
    """Show and submit guides for a game (not tied to a specific achievement)."""
    target_user = get_user_by_username(username)
    if target_user is None:
        flash("User not found.", "error")
        return redirect(url_for("my_games"))

    game_name = request.args.get("game_name", f"Title ID: {title_id}")
    media_type = request.args.get("media_type", "")

    if request.method == "POST":
        url = request.form.get("url", "").strip()
        if not url:
            flash("Please provide a URL.", "error")
        else:
            title, description = fetch_url_metadata(url)
            db = get_db()
            db.execute(
                "INSERT INTO guides (url, title, description, title_id, achievement_id, user_id) "
                "VALUES (?, ?, ?, ?, NULL, ?)",
                (url, title, description, title_id, current_user.id),
            )
            db.commit()
            flash("Guide submitted!", "success")
        return redirect(
            url_for(
                "game_guides",
                username=username,
                title_id=title_id,
                game_name=game_name,
                media_type=media_type,
            )
        )

    db = get_db()
    rows = db.execute(
        "SELECT g.id, g.url, g.title, g.description, g.title_id, g.achievement_id, "
        "g.user_id, u.username AS author "
        "FROM guides g JOIN users u ON g.user_id = u.id "
        "WHERE g.title_id = ? AND g.achievement_id IS NULL",
        (title_id,),
    ).fetchall()

    guides = rows

    return render_template(
        "game_guides.html",
        guides=guides,
        game_name=game_name,
        username=username,
        title_id=title_id,
        media_type=media_type,
    )


@app.route(
    "/games/<username>/<title_id>/achievement/<achievement_id>/guides",
    methods=["GET", "POST"],
)
@login_required
def achievement_guides(username, title_id, achievement_id):
    """Show and submit guides for a specific achievement."""
    target_user = get_user_by_username(username)
    if target_user is None:
        flash("User not found.", "error")
        return redirect(url_for("my_games"))

    game_name = request.args.get("game_name", f"Title ID: {title_id}")
    media_type = request.args.get("media_type", "")
    achievement_name = request.args.get(
        "achievement_name", f"Achievement ID: {achievement_id}"
    )

    if request.method == "POST":
        url = request.form.get("url", "").strip()
        if not url:
            flash("Please provide a URL.", "error")
        else:
            title, description = fetch_url_metadata(url)
            db = get_db()
            db.execute(
                "INSERT INTO guides (url, title, description, title_id, achievement_id, user_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (url, title, description, title_id, achievement_id, current_user.id),
            )
            db.commit()
            flash("Guide submitted!", "success")
        return redirect(
            url_for(
                "achievement_guides",
                username=username,
                title_id=title_id,
                achievement_id=achievement_id,
                game_name=game_name,
                achievement_name=achievement_name,
                media_type=media_type,
            )
        )

    db = get_db()
    rows = db.execute(
        "SELECT g.id, g.url, g.title, g.description, g.title_id, g.achievement_id, "
        "g.user_id, u.username AS author "
        "FROM guides g JOIN users u ON g.user_id = u.id "
        "WHERE g.title_id = ? AND g.achievement_id = ?",
        (title_id, achievement_id),
    ).fetchall()

    guides = rows

    return render_template(
        "achievement_guides.html",
        guides=guides,
        game_name=game_name,
        achievement_name=achievement_name,
        username=username,
        title_id=title_id,
        achievement_id=achievement_id,
        media_type=media_type,
    )


if __name__ == "__main__":
    app.run(debug=True)
