from flask import flash, redirect, request, url_for
from flask_login import current_user, login_required

from . import app
from .models import db
from .models.showcase_game import ShowcaseGame
from .models.showcase_achievement import ShowcaseAchievement

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

    count = ShowcaseGame.query.filter_by(user_id=current_user.id).count()

    if count >= MAX_SHOWCASE_GAMES:
        flash("You can only showcase up to 5 games.", "error")
        return redirect(redirect_url)

    existing = ShowcaseGame.query.filter_by(
        user_id=current_user.id, platform_id=platform_id, title_id=title_id
    ).first()

    if existing:
        flash("This game is already in your showcase.", "error")
        return redirect(redirect_url)

    game = ShowcaseGame(
        user_id=current_user.id,
        platform_id=platform_id,
        title_id=title_id,
        game_name=game_name,
        image_url=image_url or None,
        current_achievements=current_achievements,
        total_achievements=total_achievements,
    )
    db.session.add(game)
    db.session.commit()
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

    ShowcaseGame.query.filter_by(
        id=showcase_game_id, user_id=current_user.id
    ).delete()
    db.session.commit()
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

    count = ShowcaseAchievement.query.filter_by(user_id=current_user.id).count()

    if count >= MAX_SHOWCASE_ACHIEVEMENTS:
        flash("You can only showcase up to 5 achievements.", "error")
        return redirect(redirect_url)

    existing = ShowcaseAchievement.query.filter_by(
        user_id=current_user.id,
        platform_id=platform_id,
        title_id=title_id,
        achievement_id=achievement_id,
    ).first()

    if existing:
        flash("This achievement is already in your showcase.", "error")
        return redirect(redirect_url)

    sa = ShowcaseAchievement(
        user_id=current_user.id,
        platform_id=platform_id,
        title_id=title_id,
        achievement_id=achievement_id,
        game_name=game_name or None,
        achievement_name=achievement_name,
        achievement_description=achievement_description or None,
        image_url=image_url or None,
        gamerscore=gamerscore,
    )
    db.session.add(sa)
    db.session.commit()
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

    ShowcaseAchievement.query.filter_by(
        id=showcase_achievement_id, user_id=current_user.id
    ).delete()
    db.session.commit()
    flash("Achievement removed from your showcase.", "success")
    return redirect(redirect_url)
