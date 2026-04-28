"""Guides route."""

from __future__ import annotations

from typing import Any

from flask import render_template
from flask_login import current_user
from sqlalchemy import func

from .. import app
from ..helpers.platform import PLATFORM_ID_MAP
from ..models.achievement import Achievement
from ..models.guide import Guide
from ..models.guide_rating import GuideRating
from ..models.title import Title
from ._helpers import get_platform_or_abort


@app.route("/guides")
def public_guides_index():
    """Public guides index."""
    # Get guide counts grouped by (platform_id, title_id)
    guide_groups = (
        Guide.query.with_entities(
            Guide.platform_id, Guide.title_id, func.count().label("guide_count")
        )
        .group_by(Guide.platform_id, Guide.title_id)
        .all()
    )

    games = []
    for row in guide_groups:
        title = Title.find_by_platform(row.platform_id, str(row.title_id))
        if title:
            games.append(
                {
                    "platform_id": row.platform_id,
                    "title_id": row.title_id,
                    "game_name": title.name,
                    "guide_count": row.guide_count,
                }
            )
    games.sort(key=lambda g: g["game_name"])

    return render_template(
        "public_guides_index.html",
        games=games,
        platform_slugs=PLATFORM_ID_MAP,
    )


def _build_guide_ratings(
    guides: list[Any], user_id: int | None
) -> dict[int, dict[str, Any]]:
    """
    Build a mapping of guide_id to rating counts and the current user's vote.

    :param guides: List of Guide objects to compute ratings for.
    :param user_id: ID of the currently authenticated user, or None.
    :return: Dict mapping guide_id to {"up": int, "down": int, "user_vote": bool | None}.
    """
    if not guides:
        return {}

    guide_ids = [g.id for g in guides]

    # Fetch all ratings for the relevant guides in a single query.
    all_ratings = GuideRating.query.filter(
        GuideRating.guide_id.in_(guide_ids)
    ).all()

    counts: dict[int, dict[str, Any]] = {
        gid: {"up": 0, "down": 0, "user_vote": None} for gid in guide_ids
    }
    for r in all_ratings:
        if r.rating:
            counts[r.guide_id]["up"] += 1
        else:
            counts[r.guide_id]["down"] += 1
        if user_id is not None and r.user_id == user_id:
            counts[r.guide_id]["user_vote"] = r.rating

    return counts


@app.route("/guides/<platform>/<title_id>")
def public_game_guides(platform, title_id):
    """Public game guides."""
    platform_id = get_platform_or_abort(platform)

    game_guides = (
        Guide.query.filter_by(platform_id=platform_id, title_id=title_id)
        .filter(Guide.achievement_id.is_(None))
        .order_by(Guide.id)
        .all()
    )

    achievement_guides = (
        Guide.query.filter_by(platform_id=platform_id, title_id=title_id)
        .filter(Guide.achievement_id.isnot(None))
        .join(Guide.achievement)
        .order_by(Achievement.achievement_name, Guide.id)
        .all()
    )

    achievement_groups: list[dict] = []
    current_key = None
    for guide in achievement_guides:
        ach = guide.achievement
        key = (ach.achievement_id, ach.achievement_name)
        if key != current_key:
            current_key = key
            achievement_groups.append(
                {
                    "achievement_id": ach.achievement_id,
                    "achievement_name": ach.achievement_name,
                    "achievement_description": ach.description,
                    "guides": [],
                }
            )
        achievement_groups[-1]["guides"].append(guide)

    # Look up the game name from the Title model.
    title_row = Title.find_by_platform(platform_id, title_id)
    game_name = title_row.name if title_row else f"Title ID: {title_id}"

    # Compute rating counts and current user's vote for every guide on the page.
    all_guides = game_guides + achievement_guides
    user_id = current_user.id if current_user.is_authenticated else None
    guide_ratings = _build_guide_ratings(all_guides, user_id)

    return render_template(
        "public_game_guides.html",
        game_name=game_name,
        game_guides=game_guides,
        achievement_groups=achievement_groups,
        platform=platform,
        title_id=title_id,
        guide_ratings=guide_ratings,
        is_authenticated=current_user.is_authenticated,
    )
