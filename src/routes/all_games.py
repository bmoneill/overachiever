"""Routes for browsing all games and their achievements.

Provides two public endpoints:

* ``GET /games`` – lists every :class:`~src.models.title.Title` in the
  database together with guide and achievement counts.
* ``GET /games/<int:title_id>`` – shows all achievements for a single
  title, with per-achievement guide availability.
"""

from typing import Union

from flask import flash, redirect, render_template, url_for
from werkzeug.wrappers import Response

from .. import app
from ..helpers.platform import PLATFORM_XBOX, PLATFORM_ID_MAP
from ..api.sync import resolve_xbox_icon_fallbacks
from ..models.achievement import Achievement
from ..models.guide import Guide
from ..models.title import Title


# ---------------------------------------------------------------------------
# GET /games  –  list every title in the database
# ---------------------------------------------------------------------------


@app.route("/games")
def all_games() -> str:
    """Render a page listing every game title in the database.

    For each :class:`Title` the response includes:

    * The number of :class:`Guide` rows associated with the title
      (matched on ``platform_id`` and ``title_id``).
    * The number of :class:`Achievement` rows associated with the title.

    The resulting list is sorted alphabetically by game name and passed
    to the ``all_games.html`` template.

    Returns:
        Rendered HTML string.
    """

    titles: list[Title] = Title.query.all()

    games: list[dict[str, object]] = []
    for title in titles:
        guide_count: int = (
            Guide.query
            .filter_by(platform_id=title.platform, title_id=str(title.platform_title_id))
            .count()
        )

        achievement_count: int = (
            Achievement.query
            .filter_by(title_id=title.id)
            .count()
        )

        platform_slug: str = PLATFORM_ID_MAP.get(title.platform, "unknown")

        games.append(
            {
                "id": title.id,
                "name": title.name,
                "platform": title.platform,
                "platform_slug": platform_slug,
                "platform_title_id": title.platform_title_id,
                "image_url": title.image_url,
                "media_type": title.media_type,
                "guide_count": guide_count,
                "achievement_count": achievement_count,
            }
        )

    games.sort(key=lambda g: str(g["name"] or "").lower())

    return render_template("all_games.html", all_games=games)


# ---------------------------------------------------------------------------
# GET /games/<int:title_id>  –  achievements for a single title
# ---------------------------------------------------------------------------


@app.route("/games/<int:title_id>")
def all_game_achievements(title_id: int) -> Union[str, Response]:
    """Render all achievements for the title identified by *title_id*.

    If the :class:`Title` does not exist an error is flashed and the
    user is redirected to :func:`all_games`.

    For every :class:`Achievement` an ad-hoc ``guide_count`` attribute is
    attached so the template can indicate whether guides are available.
    When the title belongs to Xbox the standard icon-fallback logic is
    applied via :func:`resolve_xbox_icon_fallbacks`.

    Args:
        title_id: Primary-key ``id`` of the :class:`Title` to display.

    Returns:
        Rendered HTML string, or a redirect response on error.
    """

    title: Union[Title, None] = Title.query.get(title_id)

    if title is None:
        flash("Game not found.", "error")
        return redirect(url_for("all_games"))

    achievements: list[Achievement] = (
        Achievement.query
        .filter_by(title_id=title.id)
        .all()
    )

    # Xbox icon fallback ---------------------------------------------------
    if title.platform == PLATFORM_XBOX:
        resolve_xbox_icon_fallbacks(achievements)

    # Attach per-achievement guide counts ----------------------------------
    for achievement in achievements:
        achievement.guide_count = (  # type: ignore[attr-defined]
            Guide.query.filter_by(achievement_id=achievement.id).count()
        )

    platform_slug: str = PLATFORM_ID_MAP.get(title.platform, "unknown")

    return render_template(
        "all_game_achievements.html",
        achievements=achievements,
        game_name=title.name,
        title_id=title.id,
        platform_title_id=title.platform_title_id,
        platform=platform_slug,
        platform_id=title.platform,
        media_type=title.media_type,
        game_image_url=title.image_url,
    )
