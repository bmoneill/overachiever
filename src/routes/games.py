"""Game and achievement routes.

Every route follows a **sync-then-query** pattern:

1. Call a function in :mod:`src.api.sync` to pull fresh data from the
   external platform API and persist it to the local database.
2. Query the database for the data the template needs.

No raw API response dicts are touched inside this module.
"""

import requests

from bs4 import BeautifulSoup
from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from .. import app
from ._helpers import get_user_by_username, PLATFORM_SLUG_TO_ID
from ..models import db
from ..models.achievement import Achievement as AchievementModel
from ..models.title import Title
from ..models.user_title import UserTitle
from ..models.pinned_game import PinnedGame
from ..models.pinned_achievement import PinnedAchievement
from ..models.guide import Guide
from ..api.achievement_api import AchievementAPIError
from ..api.sync import (
    sync_user_games,
    sync_title_achievements,
    load_title_achievements,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fetch_url_metadata(url: str) -> tuple[str | None, str | None]:
    """Fetch the title and description from a URL's HTML meta tags."""
    title = None
    description = None
    try:
        resp = requests.get(
            url, timeout=10, headers={"User-Agent": "Overachiever/1.0"}
        )
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


def _get_title_or_fallback(
    platform_id: int,
    platform_title_id: str,
) -> Title | None:
    """Look up a :class:`Title` by platform and platform-specific ID."""
    return Title.query.filter_by(
        platform=platform_id,
        platform_title_id=str(platform_title_id),
    ).first()


# ---------------------------------------------------------------------------
# Game list route
# ---------------------------------------------------------------------------

@app.route("/games/<username>")
def games(username: str):
    """Show the list of games a player owns across all linked platforms."""
    target_user = get_user_by_username(username)
    if target_user is None:
        flash("User not found.", "error")
        return redirect(url_for("my_games"))

    # 1. Sync from external APIs → DB
    errors = sync_user_games(target_user)
    for error in errors:
        flash(error, "error")

    # 2. Query DB
    user_titles = (
        UserTitle.query
        .filter_by(user_id=target_user.id)
        .join(Title)
        .all()
    )

    return render_template(
        "games.html",
        all_games=user_titles,
        username=target_user.username,
    )


# ---------------------------------------------------------------------------
# Achievement routes
# ---------------------------------------------------------------------------

@app.route("/games/<username>/<platform>/<title_id>")
def game_achievements(username: str, platform: str, title_id: str):
    """Show unlocked and locked achievements for a specific game."""
    target_user = get_user_by_username(username)
    if target_user is None:
        flash("User not found.", "error")
        return redirect(url_for("my_games"))

    if platform not in PLATFORM_SLUG_TO_ID:
        flash("Invalid platform.", "error")
        return redirect(url_for("games", username=username))

    platform_id = PLATFORM_SLUG_TO_ID[platform]
    media_type = request.args.get("media_type", "")

    # 1. Sync from API → DB (errors are non-fatal; we fall back to cache)
    try:
        sync_title_achievements(
            target_user, platform_id, title_id, media_type=media_type,
        )
    except AchievementAPIError as exc:
        flash(f"API unavailable ({exc}). Showing cached data.", "error")

    # 2. Query DB
    unlocked, locked = load_title_achievements(
        target_user.id, platform_id, title_id,
    )

    db_title = _get_title_or_fallback(platform_id, title_id)
    game_name = (
        db_title.name
        if db_title
        else request.args.get("game_name", f"Title: {title_id}")
    )
    game_image_url = (
        (db_title.image_url if db_title else None)
        or request.args.get("game_image_url", "")
    )

    # Showcase helpers (all DB queries)
    is_own_page = (
        current_user.is_authenticated and current_user.id == target_user.id
    )

    game_is_pinned = False
    pinned_game_count = 0
    pinned_achievement_ids: set[str] = set()
    pinned_achievement_count = 0

    if is_own_page:
        pinned_game_count = PinnedGame.query.filter_by(
            user_id=current_user.id,
        ).count()

        if db_title:
            game_is_pinned = (
                PinnedGame.query.filter_by(
                    user_id=current_user.id,
                    title_id=db_title.id,
                ).first()
                is not None
            )

        pinned_achievement_count = PinnedAchievement.query.filter_by(
            user_id=current_user.id,
        ).count()

        pinned_rows = (
            PinnedAchievement.query
            .join(
                AchievementModel,
                PinnedAchievement.achievement_id == AchievementModel.id,
            )
            .join(Title, AchievementModel.title_id == Title.id)
            .filter(
                PinnedAchievement.user_id == current_user.id,
                Title.platform == platform_id,
                Title.platform_title_id == str(title_id),
            )
            .all()
        )
        pinned_achievement_ids = {
            str(row.achievement.achievement_id) for row in pinned_rows
        }

    return render_template(
        "game_achievements.html",
        unlocked=unlocked,
        locked=locked,
        game_name=game_name,
        username=target_user.username,
        title_id=title_id,
        platform=platform,
        platform_id=platform_id,
        media_type=media_type,
        game_image_url=game_image_url,
        is_own_page=is_own_page,
        game_is_pinned=game_is_pinned,
        pinned_game_count=pinned_game_count,
        pinned_achievement_ids=pinned_achievement_ids,
        pinned_achievement_count=pinned_achievement_count,
    )


# ---------------------------------------------------------------------------
# Guide routes
# ---------------------------------------------------------------------------

@app.route(
    "/games/<username>/<platform>/<title_id>/guides",
    methods=["GET", "POST"],
)
def game_guides(username: str, platform: str, title_id: str):
    """Show and submit guides for a game (not tied to a specific achievement)."""
    target_user = get_user_by_username(username)
    if target_user is None:
        flash("User not found.", "error")
        return redirect(url_for("my_games"))

    if platform not in PLATFORM_SLUG_TO_ID:
        flash("Invalid platform.", "error")
        return redirect(url_for("games", username=username))

    platform_id = PLATFORM_SLUG_TO_ID[platform]
    media_type = request.args.get("media_type", "")

    # Resolve game name from DB, fall back to query param
    db_title = _get_title_or_fallback(platform_id, title_id)
    game_name = (
        db_title.name
        if db_title
        else request.args.get("game_name", f"Title ID: {title_id}")
    )

    if request.method == "POST":
        url = request.form.get("url", "").strip()
        if not url:
            flash("Please provide a URL.", "error")
        else:
            title, description = fetch_url_metadata(url)
            guide = Guide(
                url=url,
                title=title,
                description=description,
                platform_id=platform_id,
                title_id=title_id,
                achievement_id=None,
                user_id=current_user.id,
            )
            db.session.add(guide)
            db.session.commit()
            flash("Guide submitted!", "success")
        return redirect(
            url_for(
                "game_guides",
                username=username,
                platform=platform,
                title_id=title_id,
                game_name=game_name,
                media_type=media_type,
            )
        )

    guides = (
        Guide.query
        .filter_by(platform_id=platform_id, title_id=title_id)
        .filter(Guide.achievement_id.is_(None))
        .all()
    )

    return render_template(
        "game_guides.html",
        guides=guides,
        game_name=game_name,
        username=username,
        title_id=title_id,
        platform=platform,
        media_type=media_type,
    )


@app.route(
    "/games/<username>/<platform>/<title_id>/achievement/<achievement_id>/guides",
    methods=["GET", "POST"],
)
def achievement_guides(
    username: str,
    platform: str,
    title_id: str,
    achievement_id: str,
):
    """Show and submit guides for a specific achievement."""
    target_user = get_user_by_username(username)
    if target_user is None:
        flash("User not found.", "error")
        return redirect(url_for("my_games"))

    if platform not in PLATFORM_SLUG_TO_ID:
        flash("Invalid platform.", "error")
        return redirect(url_for("games", username=username))

    platform_id = PLATFORM_SLUG_TO_ID[platform]
    media_type = request.args.get("media_type", "")

    # Resolve names from DB, falling back to query params
    db_title = _get_title_or_fallback(platform_id, title_id)
    game_name = (
        db_title.name
        if db_title
        else request.args.get("game_name", f"Title ID: {title_id}")
    )

    achievement_name = request.args.get(
        "achievement_name", f"Achievement ID: {achievement_id}"
    )
    achievement_description = request.args.get("achievement_description", "")

    # Use DB achievement data for better names when available
    db_ach_existing = (
        AchievementModel.query
        .join(Title)
        .filter(
            Title.platform == platform_id,
            Title.platform_title_id == str(title_id),
            AchievementModel.achievement_id == str(achievement_id),
        )
        .first()
    )
    if db_ach_existing:
        achievement_name = (
            db_ach_existing.achievement_name or achievement_name
        )
        achievement_description = (
            db_ach_existing.description or achievement_description
        )

    if request.method == "POST":
        url = request.form.get("url", "").strip()
        if not url:
            flash("Please provide a URL.", "error")
        else:
            title, description = fetch_url_metadata(url)

            # Ensure an Achievement record exists
            db_ach = (
                AchievementModel.query
                .join(Title)
                .filter(
                    Title.platform == platform_id,
                    Title.platform_title_id == str(title_id),
                    AchievementModel.achievement_id == str(achievement_id),
                )
                .first()
            )

            if db_ach is None:
                # Ensure a Title row exists
                if db_title is None:
                    db_title = Title(
                        name=game_name,
                        platform=platform_id,
                        platform_title_id=str(title_id),
                    )
                    db.session.add(db_title)
                    db.session.flush()

                db_ach = AchievementModel(
                    achievement_id=str(achievement_id),
                    title_id=db_title.id,
                    achievement_name=achievement_name,
                    description=achievement_description or None,
                )
                db.session.add(db_ach)
                db.session.flush()

            ach_pk = db_ach.id

            existing = Guide.query.filter_by(
                url=url, achievement_id=ach_pk
            ).first()

            if existing:
                flash(
                    "A guide with that URL has already been submitted "
                    "for this achievement.",
                    "error",
                )
            else:
                guide = Guide(
                    url=url,
                    title=title,
                    description=description,
                    platform_id=platform_id,
                    title_id=title_id,
                    achievement_id=ach_pk,
                    user_id=current_user.id,
                )
                db.session.add(guide)
                db.session.commit()
                flash("Guide submitted!", "success")

        return redirect(
            url_for(
                "achievement_guides",
                username=username,
                platform=platform,
                title_id=title_id,
                achievement_id=achievement_id,
                game_name=game_name,
                achievement_name=achievement_name,
                achievement_description=achievement_description,
                media_type=media_type,
            )
        )

    # Look up the Achievement record to find linked guides
    db_ach = (
        AchievementModel.query
        .join(Title)
        .filter(
            Title.platform == platform_id,
            Title.platform_title_id == str(title_id),
            AchievementModel.achievement_id == str(achievement_id),
        )
        .first()
    )

    guides = (
        Guide.query.filter_by(achievement_id=db_ach.id).all()
        if db_ach
        else []
    )

    return render_template(
        "achievement_guides.html",
        guides=guides,
        game_name=game_name,
        achievement_name=achievement_name,
        username=username,
        title_id=title_id,
        achievement_id=achievement_id,
        platform=platform,
        media_type=media_type,
    )
