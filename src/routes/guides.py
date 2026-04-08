"""Guides route."""

from flask import render_template
from sqlalchemy import func

from .. import app
from ..helpers.platform import PLATFORM_ID_MAP
from ..models.achievement import Achievement
from ..models.guide import Guide
from ..models.title import Title
from ._helpers import get_platform_or_abort


@app.route("/guides")
def public_guides_index():
    """Public guides index."""
    # Get guide counts grouped by (platform_id, title_id)
    guide_groups = (
        Guide.query.with_entities(
            Guide.platform_id, Guide.title_id, func.count.label("guide_count")
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

    return render_template(
        "public_game_guides.html",
        game_name=game_name,
        game_guides=game_guides,
        achievement_groups=achievement_groups,
        platform=platform,
        title_id=title_id,
    )
