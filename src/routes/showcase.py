"""Showcase routes for pinning games and achievements to a user's profile.

These routes let users pin (and unpin) games and achievements to their
public profile showcase.  The underlying storage uses the normalised
:class:`~src.models.pinned_game.PinnedGame` and
:class:`~src.models.pinned_achievement.PinnedAchievement` models, which
hold foreign-key references rather than denormalised copies of data.
"""

from flask import flash, redirect, request, url_for
from flask_login import current_user, login_required

from .. import app
from ..models import db
from ..models.achievement import Achievement
from ..models.pinned_achievement import PinnedAchievement
from ..models.pinned_game import PinnedGame
from ..models.title import Title

MAX_PINNED_GAMES = 5
MAX_PINNED_ACHIEVEMENTS = 5


@app.route("/showcase/add-game", methods=["POST"])
@login_required
def showcase_add_game():
    """Add a game to the current user's profile showcase."""
    platform_id = request.form.get("platform_id", "")
    title_id = request.form.get("title_id", "")
    redirect_url = request.form.get("redirect_url", url_for("my_games"))

    if not platform_id or not title_id:
        flash("Missing game information.", "error")
        return redirect(redirect_url)

    db_title = Title.find_by_platform(
        int(platform_id),
        str(title_id),
    )

    if db_title is None:
        flash("Game not found in the database.", "error")
        return redirect(redirect_url)

    count = PinnedGame.query.filter_by(user_id=current_user.id).count()

    if count >= MAX_PINNED_GAMES:
        flash("You can only showcase up to 5 games.", "error")
        return redirect(redirect_url)

    existing = PinnedGame.query.filter_by(
        user_id=current_user.id, title_id=db_title.id
    ).first()

    if existing:
        flash("This game is already in your showcase.", "error")
        return redirect(redirect_url)

    pinned = PinnedGame(
        user_id=current_user.id,
        title_id=db_title.id,
    )
    db.session.add(pinned)
    db.session.commit()
    flash("Game added to your showcase!", "success")
    return redirect(redirect_url)


@app.route("/showcase/remove-game", methods=["POST"])
@login_required
def showcase_remove_game():
    """Remove a game from the current user's profile showcase."""
    pinned_game_id = request.form.get("pinned_game_id", "")
    redirect_url = request.form.get("redirect_url", url_for("my_games"))

    if not pinned_game_id:
        flash("Missing game information.", "error")
        return redirect(redirect_url)

    PinnedGame.query.filter_by(
        id=pinned_game_id, user_id=current_user.id
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
    redirect_url = request.form.get("redirect_url", url_for("my_games"))

    if not platform_id or not title_id or not achievement_id:
        flash("Missing achievement information.", "error")
        return redirect(redirect_url)

    db_achievement = Achievement.find_by_platform(
        int(platform_id),
        int(title_id),
        str(achievement_id),
    )

    if db_achievement is None:
        flash("Achievement not found in the database.", "error")
        return redirect(redirect_url)

    count = PinnedAchievement.query.filter_by(user_id=current_user.id).count()

    if count >= MAX_PINNED_ACHIEVEMENTS:
        flash("You can only showcase up to 5 achievements.", "error")
        return redirect(redirect_url)

    existing = PinnedAchievement.query.filter_by(
        user_id=current_user.id,
        achievement_id=db_achievement.id,
    ).first()

    if existing:
        flash("This achievement is already in your showcase.", "error")
        return redirect(redirect_url)

    pinned = PinnedAchievement(
        user_id=current_user.id,
        achievement_id=db_achievement.id,
    )
    db.session.add(pinned)
    db.session.commit()
    flash("Achievement added to your showcase!", "success")
    return redirect(redirect_url)


@app.route("/showcase/remove-achievement", methods=["POST"])
@login_required
def showcase_remove_achievement():
    """Remove an achievement from the current user's profile showcase."""
    pinned_achievement_id = request.form.get("pinned_achievement_id", "")
    redirect_url = request.form.get("redirect_url", url_for("my_games"))

    if not pinned_achievement_id:
        flash("Missing achievement information.", "error")
        return redirect(redirect_url)

    PinnedAchievement.query.filter_by(
        id=pinned_achievement_id, user_id=current_user.id
    ).delete()
    db.session.commit()
    flash("Achievement removed from your showcase.", "success")
    return redirect(redirect_url)
