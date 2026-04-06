from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from .. import app
from ._helpers import get_user_by_username, PLATFORM_ID_TO_SLUG
from ..models import db
from ..models.showcase_game import ShowcaseGame
from ..models.showcase_achievement import ShowcaseAchievement
from ..models.achievement import Achievement
from ..models.user_achievement import UserAchievement
from ..api.xbox import XboxProfileAPI
from ..api.steam import SteamProfileAPI
from ..api.profile import ProfileAPIError
from ..models.user_follow import UserFollow


@app.route("/profile/<username>")
def profile(username):
    """Public-facing user profile page."""
    target_user = get_user_by_username(username)
    if target_user is None:
        flash("User not found.", "error")
        return redirect(url_for("my_games"))

    xbox_profile = None
    steam_profile = None

    if target_user.display_gamertags:
        if target_user.xuid:
            try:
                api = XboxProfileAPI()
                xbox_profile = api.get_user_profile(target_user.xuid)
            except ProfileAPIError:
                pass

        if target_user.steam_id:
            try:
                api = SteamProfileAPI()
                steam_profile = api.get_user_profile(target_user.steam_id)
            except ProfileAPIError:
                pass

    is_own_profile = current_user.is_authenticated and current_user.id == target_user.id

    follower_count = UserFollow.query.filter_by(followed_id=target_user.id).count()
    following_count = UserFollow.query.filter_by(follower_id=target_user.id).count()
    is_following = False
    if current_user.is_authenticated and not is_own_profile:
        is_following = UserFollow.query.filter_by(follower_id=current_user.id, followed_id=target_user.id).first() is not None

    showcase_games = (
        ShowcaseGame.query
        .filter_by(user_id=target_user.id)
        .order_by(ShowcaseGame.id)
        .all()
    )

    recent_achievements = (
        UserAchievement.query
        .join(Achievement, UserAchievement.achievement_id == Achievement.id)
        .filter(UserAchievement.user_id == target_user.id)
        .order_by(UserAchievement.time_unlocked.desc())
        .limit(5)
        .all()
    )

    showcase_achievements = (
        ShowcaseAchievement.query
        .filter_by(user_id=target_user.id)
        .order_by(ShowcaseAchievement.id)
        .all()
    )

    achievement_count = target_user.achievement_count or 0

    return render_template(
        "profile.html",
        target_user=target_user,
        xbox_profile=xbox_profile,
        steam_profile=steam_profile,
        is_own_profile=is_own_profile,
        showcase_games=showcase_games,
        showcase_achievements=showcase_achievements,
        achievement_count=achievement_count,
        recent_achievements=recent_achievements,
        platform_slugs=PLATFORM_ID_TO_SLUG,
        follower_count=follower_count,
        following_count=following_count,
        is_following=is_following,
    )


@app.route("/profile/<username>/edit", methods=["GET", "POST"])
@login_required
def profile_edit(username):
    """Allow the authenticated user to edit their own profile."""
    target_user = get_user_by_username(username)
    if target_user is None:
        flash("User not found.", "error")
        return redirect(url_for("my_games"))

    if current_user.id != target_user.id:
        flash("You can only edit your own profile.", "error")
        return redirect(url_for("profile", username=username))

    if request.method == "POST":
        bio = request.form.get("bio", "").strip()
        display_gamertags = request.form.get("display_gamertags") == "on"

        current_user.bio = bio or None
        current_user.display_gamertags = display_gamertags
        db.session.commit()

        flash("Profile updated!", "success")
        return redirect(url_for("profile", username=username))

    return render_template(
        "profile_edit.html",
        target_user=target_user,
    )


@app.route("/profile/<username>/follow", methods=["POST"])
@login_required
def follow_user(username):
    target_user = get_user_by_username(username)
    if target_user is None:
        flash("User not found.", "error")
        return redirect(url_for("my_games"))

    if current_user.id == target_user.id:
        flash("You cannot follow yourself.", "error")
        return redirect(url_for("profile", username=username))

    existing = UserFollow.query.filter_by(
        follower_id=current_user.id, followed_id=target_user.id
    ).first()
    if not existing:
        follow = UserFollow(follower_id=current_user.id, followed_id=target_user.id)
        db.session.add(follow)
        db.session.commit()

    return redirect(url_for("profile", username=username))


@app.route("/profile/<username>/unfollow", methods=["POST"])
@login_required
def unfollow_user(username):
    target_user = get_user_by_username(username)
    if target_user is None:
        flash("User not found.", "error")
        return redirect(url_for("my_games"))

    existing = UserFollow.query.filter_by(
        follower_id=current_user.id, followed_id=target_user.id
    ).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()

    return redirect(url_for("profile", username=username))
