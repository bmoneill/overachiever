import requests
from bs4 import BeautifulSoup
from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from . import app
from .auth import get_user_by_username
from .db import get_db
from .api.achievement import AchievementAPIError
from .api.xbox import XboxAchievementAPI, xbl_get


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
                "INSERT INTO guides (url, title, description, platform_id, title_id, achievement_id, user_id) "
                "VALUES (?, ?, ?, ?, ?, NULL, ?)",
                (url, title, description, 1, title_id, current_user.id),
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
                "INSERT INTO guides (url, title, description, platform_id, title_id, achievement_id, user_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (url, title, description, 1, title_id, achievement_id, current_user.id),
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
