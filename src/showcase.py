from flask import flash, redirect, request, url_for
from flask_login import current_user, login_required

from . import app
from .db import get_db

MAX_SHOWCASE_GAMES = 5
MAX_SHOWCASE_ACHIEVEMENTS = 5


@app.route("/showcase/add-game", methods=["POST"])
@login_required
def showcase_add_game():
    """Add a game to the current user's profile showcase."""
    platform_id = request.form.get("platform_id", "")
    title_id = request.form.get("title_id", "")
    game_name = request.form.get("game_name", "").strip()
    image_url = request.form.get("image_url", "").strip()
    current_achievements = request.form.get("current_achievements", 0, type=int)
    total_achievements = request.form.get("total_achievements", 0, type=int)
    redirect_url = request.form.get("redirect_url", url_for("my_games"))

    if not platform_id or not title_id or not game_name:
        flash("Missing game information.", "error")
        return redirect(redirect_url)

    db = get_db()

    count = db.execute(
        "SELECT COUNT(*) AS c FROM showcase_games WHERE user_id = ?",
        (current_user.id,),
    ).fetchone()["c"]

    if count >= MAX_SHOWCASE_GAMES:
        flash("You can only showcase up to 5 games.", "error")
        return redirect(redirect_url)

    existing = db.execute(
        "SELECT id FROM showcase_games "
        "WHERE user_id = ? AND platform_id = ? AND title_id = ?",
        (current_user.id, platform_id, title_id),
    ).fetchone()

    if existing:
        flash("This game is already in your showcase.", "error")
        return redirect(redirect_url)

    db.execute(
        "INSERT INTO showcase_games "
        "(user_id, platform_id, title_id, game_name, image_url, "
        "current_achievements, total_achievements) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            current_user.id,
            platform_id,
            title_id,
            game_name,
            image_url or None,
            current_achievements,
            total_achievements,
        ),
    )
    db.commit()
    flash("Game added to your showcase!", "success")
    return redirect(redirect_url)


@app.route("/showcase/remove-game", methods=["POST"])
@login_required
def showcase_remove_game():
    """Remove a game from the current user's profile showcase."""
    showcase_game_id = request.form.get("showcase_game_id", "")
    redirect_url = request.form.get("redirect_url", url_for("my_games"))

    if not showcase_game_id:
        flash("Missing game information.", "error")
        return redirect(redirect_url)

    db = get_db()
    db.execute(
        "DELETE FROM showcase_games WHERE id = ? AND user_id = ?",
        (showcase_game_id, current_user.id),
    )
    db.commit()
    flash("Game removed from your showcase.", "success")
    return redirect(redirect_url)


@app.route("/showcase/add-achievement", methods=["POST"])
@login_required
def showcase_add_achievement():
    """Add an achievement to the current user's profile showcase."""
    platform_id = request.form.get("platform_id", "")
    title_id = request.form.get("title_id", "")
    achievement_id = request.form.get("achievement_id", "")
    game_name = request.form.get("game_name", "").strip()
    achievement_name = request.form.get("achievement_name", "").strip()
    achievement_description = request.form.get("achievement_description", "").strip()
    image_url = request.form.get("image_url", "").strip()
    gamerscore = request.form.get("gamerscore", None, type=int)
    redirect_url = request.form.get("redirect_url", url_for("my_games"))

    if not platform_id or not title_id or not achievement_id or not achievement_name:
        flash("Missing achievement information.", "error")
        return redirect(redirect_url)

    db = get_db()

    count = db.execute(
        "SELECT COUNT(*) AS c FROM showcase_achievements WHERE user_id = ?",
        (current_user.id,),
    ).fetchone()["c"]

    if count >= MAX_SHOWCASE_ACHIEVEMENTS:
        flash("You can only showcase up to 5 achievements.", "error")
        return redirect(redirect_url)

    existing = db.execute(
        "SELECT id FROM showcase_achievements "
        "WHERE user_id = ? AND platform_id = ? AND title_id = ? AND achievement_id = ?",
        (current_user.id, platform_id, title_id, achievement_id),
    ).fetchone()

    if existing:
        flash("This achievement is already in your showcase.", "error")
        return redirect(redirect_url)

    db.execute(
        "INSERT INTO showcase_achievements "
        "(user_id, platform_id, title_id, achievement_id, game_name, "
        "achievement_name, achievement_description, image_url, gamerscore) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            current_user.id,
            platform_id,
            title_id,
            achievement_id,
            game_name or None,
            achievement_name,
            achievement_description or None,
            image_url or None,
            gamerscore,
        ),
    )
    db.commit()
    flash("Achievement added to your showcase!", "success")
    return redirect(redirect_url)


@app.route("/showcase/remove-achievement", methods=["POST"])
@login_required
def showcase_remove_achievement():
    """Remove an achievement from the current user's profile showcase."""
    showcase_achievement_id = request.form.get("showcase_achievement_id", "")
    redirect_url = request.form.get("redirect_url", url_for("my_games"))

    if not showcase_achievement_id:
        flash("Missing achievement information.", "error")
        return redirect(redirect_url)

    db = get_db()
    db.execute(
        "DELETE FROM showcase_achievements WHERE id = ? AND user_id = ?",
        (showcase_achievement_id, current_user.id),
    )
    db.commit()
    flash("Achievement removed from your showcase.", "success")
    return redirect(redirect_url)
