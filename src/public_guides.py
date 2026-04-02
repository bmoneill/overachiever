from flask import abort, render_template

from . import app
from .db import get_db
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
    db = get_db()
    games = db.execute(
        "SELECT g.platform_id, g.title_id, "
        "  (SELECT a.game_name FROM achievement_summaries a "
        "   WHERE a.platform_id = g.platform_id AND a.title_id = g.title_id "
        "   AND a.game_name IS NOT NULL LIMIT 1) as game_name, "
        "  COUNT(*) as guide_count "
        "FROM guides g "
        "GROUP BY g.platform_id, g.title_id "
        "HAVING game_name IS NOT NULL "
        "ORDER BY game_name"
    ).fetchall()

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

    db = get_db()

    game_guides = db.execute(
        "SELECT g.id, g.url, g.title, g.description, u.username AS author "
        "FROM guides g LEFT JOIN users u ON g.user_id = u.id "
        "WHERE g.platform_id = ? AND g.title_id = ? AND g.achievement_id IS NULL "
        "ORDER BY g.id",
        (platform_id, title_id),
    ).fetchall()

    achievement_rows = db.execute(
        "SELECT g.id, g.url, g.title, g.description, g.created_at, "
        "       a.achievement_id, a.achievement_name, a.achievement_description, "
        "       u.username AS author "
        "FROM guides g "
        "LEFT JOIN users u ON g.user_id = u.id "
        "JOIN achievement_summaries a ON g.achievement_id = a.id "
        "WHERE g.platform_id = ? AND g.title_id = ? AND g.achievement_id IS NOT NULL "
        "ORDER BY a.achievement_name, g.id",
        (platform_id, title_id),
    ).fetchall()

    achievement_groups: list[dict] = []
    current_key = None
    for row in achievement_rows:
        key = (row["achievement_id"], row["achievement_name"])
        if key != current_key:
            current_key = key
            achievement_groups.append({
                "achievement_id": row["achievement_id"],
                "achievement_name": row["achievement_name"],
                "achievement_description": row["achievement_description"],
                "guides": [],
            })
        achievement_groups[-1]["guides"].append(row)

    game_name_row = db.execute(
        "SELECT game_name FROM achievement_summaries "
        "WHERE platform_id = ? AND title_id = ? AND game_name IS NOT NULL LIMIT 1",
        (platform_id, title_id),
    ).fetchone()
    game_name = game_name_row["game_name"] if game_name_row else f"Title ID: {title_id}"

    return render_template(
        "public_game_guides.html",
        game_name=game_name,
        game_guides=game_guides,
        achievement_groups=achievement_groups,
        platform=platform,
        title_id=title_id,
    )
