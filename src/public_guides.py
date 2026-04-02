from sqlalchemy import func
from flask import abort, render_template

from . import app
from .models.achievement import Achievement
from .models.guide import Guide
from .api.platform import PLATFORM_XBOX, PLATFORM_STEAM

PLATFORM_ID_TO_SLUG = {
    PLATFORM_XBOX: "xbox",
    PLATFORM_STEAM: "steam",
}

PLATFORM_SLUG_TO_ID = {
    "xbox": PLATFORM_XBOX,
    "steam": PLATFORM_STEAM,
}


@app.route("/guides")
def public_guides_index():
    # Get guide counts grouped by (platform_id, title_id)
    guide_groups = (
        Guide.query
        .with_entities(Guide.platform_id, Guide.title_id, func.count().label("guide_count"))
        .group_by(Guide.platform_id, Guide.title_id)
        .all()
    )

    games = []
    for row in guide_groups:
        ach = (
            Achievement.query
            .filter_by(platform_id=row.platform_id, title_id=str(row.title_id))
            .filter(Achievement.game_name.isnot(None))
            .first()
        )
        if ach:
            games.append({
                "platform_id": row.platform_id,
                "title_id": row.title_id,
                "game_name": ach.game_name,
                "guide_count": row.guide_count,
            })
    games.sort(key=lambda g: g["game_name"])

    return render_template(
        "public_guides_index.html",
        games=games,
        platform_slugs=PLATFORM_ID_TO_SLUG,
    )


@app.route("/guides/<platform>/<title_id>")
def public_game_guides(platform, title_id):
    if platform not in PLATFORM_SLUG_TO_ID:
        abort(404)

    platform_id = PLATFORM_SLUG_TO_ID[platform]

    game_guides = (
        Guide.query
        .filter_by(platform_id=platform_id, title_id=title_id)
        .filter(Guide.achievement_id.is_(None))
        .order_by(Guide.id)
        .all()
    )

    achievement_guides = (
        Guide.query
        .filter_by(platform_id=platform_id, title_id=title_id)
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
            achievement_groups.append({
                "achievement_id": ach.achievement_id,
                "achievement_name": ach.achievement_name,
                "achievement_description": ach.description,
                "guides": [],
            })
        achievement_groups[-1]["guides"].append(guide)

    # Look up the game name from the first matching achievement record.
    ach_row = (
        Achievement.query
        .filter_by(platform_id=platform_id, title_id=str(title_id))
        .filter(Achievement.game_name.isnot(None))
        .first()
    )
    game_name = ach_row.game_name if ach_row else f"Title ID: {title_id}"

    return render_template(
        "public_game_guides.html",
        game_name=game_name,
        game_guides=game_guides,
        achievement_groups=achievement_groups,
        platform=platform,
        title_id=title_id,
    )
