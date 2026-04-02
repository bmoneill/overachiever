import os

from flask import flash, redirect, render_template, request, url_for
from flask_login import (
    current_user,
    login_required,
    login_user,
    logout_user,
)
from werkzeug.security import check_password_hash, generate_password_hash

from . import app, login_manager
from .models import db
from .models.user import User
from .models.achievement import Achievement
from .models.guide import Guide
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
# Flask-Login helpers
# ---------------------------------------------------------------------------


@login_manager.user_loader
def load_user(user_id: int):
    return db.session.get(User, int(user_id))


def get_user_by_username(username: str) -> User | None:
    """Look up a user by username. Returns a User or None."""
    return User.query.filter_by(username=username).first()


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("my_games"))

    recent_guides = (
        Guide.query
        .order_by(Guide.created_at.desc())
        .limit(5)
        .all()
    )

    top_achievers = (
        User.query
        .filter(User.achievement_count > 0)
        .order_by(User.achievement_count.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "index.html",
        recent_guides=recent_guides,
        platform_slugs=PLATFORM_ID_TO_SLUG,
        top_achievers=top_achievers,
    )


@app.route("/search")
def user_search():
    """Search for users by Overachiever username."""
    q = request.args.get("q", "").strip()
    results = []
    if q:
        results = (
            User.query
            .filter(User.username.ilike(f"%{q}%"))
            .order_by(User.username)
            .limit(20)
            .all()
        )
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

        existing = User.query.filter(
            db.or_(User.username == username, User.email == email)
        ).first()
        if existing:
            flash("Username or email is already taken.", "error")
            return redirect(url_for("register"))

        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
        )
        db.session.add(new_user)
        db.session.commit()

        flash("Account created! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))
