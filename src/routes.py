import requests
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from . import app
from .auth import get_user_by_username
from .db import get_db
from .api.achievement import AchievementAPIError
from .api.platform import PLATFORM_XBOX, PLATFORM_STEAM
from .api.xbox import XboxAchievementAPI, xbl_get
from .api.steam import SteamAchievementAPI, steam_get


PLATFORM_SLUG_TO_ID = {
    "xbox": PLATFORM_XBOX,
    "steam": PLATFORM_STEAM,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fetch_url_metadata(url):
    """Fetch the title and description from a URL's HTML meta tags."""
    title = None
    description = None
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Overachiever/1.0"})
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


def _get_icon_url(achievement_id: int | str, title_id: int) -> str | None:
    """Look up a locally-cached Xbox 360 icon from the database."""
    db = get_db()
    cursor = db.execute(
        "SELECT url FROM xbox360icons WHERE achievement_id = ? AND title_id = ?",
        (achievement_id, title_id),
    )
    result = cursor.fetchone()
    return url_for("static", filename=result[0]) if result else None


def _normalize_xbox_titles(titles: list[dict]) -> list[dict]:
    """Normalize Xbox titles into common game-card dicts."""
    result = []
    for title in titles:
        ach = title.get("achievement") or {}
        hist = title.get("titleHistory") or {}
        result.append({
            "platform": "xbox",
            "title_id": str(title.get("titleId", "")),
            "name": title.get("name", "Unknown Title"),
            "image_url": title.get("displayImage", ""),
            "current_achievements": ach.get("currentAchievements", 0),
            "total_achievements": ach.get("totalAchievements", 0),
            "progress_percentage": ach.get("progressPercentage", 0),
            "last_played": hist.get("lastTimePlayed", ""),
            "media_type": title.get("mediaItemType", ""),
        })
    return result


def _fetch_steam_achievement_counts(
    steam_id: str, appids: list[str],
) -> dict[str, tuple[int, int]]:
    """Batch-fetch achievement counts for Steam games.

    Calls ``GetTopAchievementsForGames`` in batches and returns a dict
    mapping *appid* → ``(unlocked, total)``.
    """
    counts: dict[str, tuple[int, int]] = {}
    BATCH_SIZE = 100
    for start in range(0, len(appids), BATCH_SIZE):
        batch = appids[start : start + BATCH_SIZE]
        params: dict[str, str] = {
            "steamid": steam_id,
            "max_achievements": "10000",
        }
        for i, appid in enumerate(batch):
            params[f"appids[{i}]"] = appid
        try:
            data = steam_get(
                "/IPlayerService/GetTopAchievementsForGames/v1",
                params=params,
            )
            for game in data.get("games", []):
                aid = str(game.get("appid", ""))
                total = game.get("total_achievements", 0)
                unlocked = len(game.get("achievements", []))
                counts[aid] = (unlocked, total)
        except AchievementAPIError:
            continue
    return counts


def _normalize_steam_games(
    games: list[dict],
    ach_counts: dict[str, tuple[int, int]] | None = None,
) -> list[dict]:
    """Normalize Steam owned-games into common game-card dicts."""
    result = []
    for game in games:
        appid = game.get("appid", "")
        appid_str = str(appid)
        rtime = game.get("rtime_last_played", 0)
        last_played = ""
        if rtime:
            last_played = datetime.fromtimestamp(rtime, tz=timezone.utc).isoformat()

        current_achievements = None
        total_achievements = None
        progress_percentage = None
        if ach_counts and appid_str in ach_counts:
            current_achievements, total_achievements = ach_counts[appid_str]
            progress_percentage = (
                round(current_achievements / total_achievements * 100)
                if total_achievements > 0
                else 0
            )

        result.append({
            "platform": "steam",
            "title_id": appid_str,
            "name": game.get("name", "Unknown Title"),
            "image_url": (
                f"https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg"
                if appid else ""
            ),
            "current_achievements": current_achievements,
            "total_achievements": total_achievements,
            "progress_percentage": progress_percentage,
            "last_played": last_played,
            "media_type": "",
        })
    return result


# ---------------------------------------------------------------------------
# Game / Achievement routes
# ---------------------------------------------------------------------------


@app.route("/my-games")
@login_required
def my_games():
    """Redirect to the current user's games page."""
    return redirect(url_for("games", username=current_user.username))


@app.route("/games/<username>")
@login_required
def games(username):
    """Show the list of games a player owns across all linked platforms."""
    target_user = get_user_by_username(username)
    if target_user is None:
        flash("User not found.", "error")
        return redirect(url_for("my_games"))

    all_games: list[dict] = []

    # Fetch Xbox games
    if target_user.xuid:
        try:
            content = xbl_get(f"/v2/titles/{target_user.xuid}")
            titles = content.get("titles", []) if isinstance(content, dict) else []
            all_games.extend(_normalize_xbox_titles(titles))
        except AchievementAPIError as e:
            flash(f"Xbox: {e}", "error")

    # Fetch Steam games
    if target_user.steam_id:
        try:
            data = steam_get(
                "/IPlayerService/GetOwnedGames/v1",
                params={
                    "steamid": target_user.steam_id,
                    "include_played_free_games": "1",
                    "include_appinfo": "1",
                },
            )
            steam_games = data.get("games", [])
            appids = [str(g["appid"]) for g in steam_games if g.get("appid")]
            ach_counts = _fetch_steam_achievement_counts(
                target_user.steam_id, appids,
            )
            all_games.extend(_normalize_steam_games(steam_games, ach_counts))
        except AchievementAPIError as e:
            flash(f"Steam: {e}", "error")

    # Compute total achievement count across all platforms and persist it
    total_achievement_count = sum(
        g.get("current_achievements") or 0 for g in all_games
    )
    db = get_db()
    db.execute(
        "UPDATE users SET achievement_count = ? WHERE id = ?",
        (total_achievement_count, target_user.id),
    )
    db.commit()

    return render_template(
        "games.html",
        all_games=all_games,
        username=target_user.username,
    )


@app.route("/games/<username>/<platform>/<title_id>")
@login_required
def game_achievements(username, platform, title_id):
    """Show unlocked and locked achievements for a specific game."""
    target_user = get_user_by_username(username)
    if target_user is None:
        flash("User not found.", "error")
        return redirect(url_for("my_games"))

    if platform not in PLATFORM_SLUG_TO_ID:
        flash("Invalid platform.", "error")
        return redirect(url_for("games", username=username))

    media_type = request.args.get("media_type", "")

    try:
        if platform == "xbox":
            if not target_user.xuid:
                flash("This user has no linked Xbox account.", "error")
                return redirect(url_for("games", username=username))
            api = XboxAchievementAPI(xuid=target_user.xuid, media_type=media_type)
            unlocked = api.get_unlocked_title_achievements(target_user.xuid, title_id)
            locked = api.get_locked_title_achievements(target_user.xuid, title_id)
            game_name = api.game_name

            # Override with locally-cached Xbox 360 icons when available.
            if api.is_x360:
                for a in unlocked + locked:
                    icon = _get_icon_url(a.achievement_id, a.title_id)
                    if icon:
                        a.image_url = icon
        else:
            if not target_user.steam_id:
                flash("This user has no linked Steam account.", "error")
                return redirect(url_for("games", username=username))
            api = SteamAchievementAPI(steam_id=target_user.steam_id)
            unlocked = api.get_unlocked_title_achievements(target_user.steam_id, title_id)
            locked = api.get_locked_title_achievements(target_user.steam_id, title_id)
            game_name = api.game_name
    except AchievementAPIError as e:
        flash(str(e), "error")
        return redirect(url_for("games", username=username))

    if game_name is None:
        game_name = request.args.get("game_name", f"Title ID: {title_id}")

    platform_id = PLATFORM_SLUG_TO_ID[platform]
    game_image_url = request.args.get("game_image_url", "")
    is_own_page = current_user.is_authenticated and current_user.id == target_user.id

    game_in_showcase = False
    showcase_game_count = 0
    showcase_achievement_ids: set[str] = set()
    showcase_achievement_count = 0

    if is_own_page:
        db = get_db()
        showcase_game_count = db.execute(
            "SELECT COUNT(*) AS c FROM showcase_games WHERE user_id = ?",
            (current_user.id,),
        ).fetchone()["c"]
        game_in_showcase = db.execute(
            "SELECT id FROM showcase_games "
            "WHERE user_id = ? AND platform_id = ? AND title_id = ?",
            (current_user.id, platform_id, title_id),
        ).fetchone() is not None
        showcase_achievement_count = db.execute(
            "SELECT COUNT(*) AS c FROM showcase_achievements WHERE user_id = ?",
            (current_user.id,),
        ).fetchone()["c"]
        showcased_rows = db.execute(
            "SELECT achievement_id FROM showcase_achievements "
            "WHERE user_id = ? AND platform_id = ? AND title_id = ?",
            (current_user.id, platform_id, title_id),
        ).fetchall()
        showcase_achievement_ids = {str(row["achievement_id"]) for row in showcased_rows}

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
        game_in_showcase=game_in_showcase,
        showcase_game_count=showcase_game_count,
        showcase_achievement_ids=showcase_achievement_ids,
        showcase_achievement_count=showcase_achievement_count,
    )


@app.route("/games/<username>/<platform>/<title_id>/guides", methods=["GET", "POST"])
@login_required
def game_guides(username, platform, title_id):
    """Show and submit guides for a game (not tied to a specific achievement)."""
    target_user = get_user_by_username(username)
    if target_user is None:
        flash("User not found.", "error")
        return redirect(url_for("my_games"))

    if platform not in PLATFORM_SLUG_TO_ID:
        flash("Invalid platform.", "error")
        return redirect(url_for("games", username=username))

    platform_id = PLATFORM_SLUG_TO_ID[platform]
    game_name = request.args.get("game_name", f"Title ID: {title_id}")
    media_type = request.args.get("media_type", "")

    if request.method == "POST":
        url = request.form.get("url", "").strip()
        if not url:
            flash("Please provide a URL.", "error")
        else:
            title, description = fetch_url_metadata(url)
            db = get_db()
            db.execute(
                "INSERT INTO guides (url, title, description, platform_id, title_id, achievement_summary_id, user_id) "
                "VALUES (?, ?, ?, ?, ?, NULL, ?)",
                (url, title, description, platform_id, title_id, current_user.id),
            )
            db.commit()
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

    db = get_db()
    rows = db.execute(
        "SELECT g.id, g.url, g.title, g.description, g.title_id, g.achievement_summary_id, "
        "g.user_id, u.username AS author "
        "FROM guides g JOIN users u ON g.user_id = u.id "
        "WHERE g.platform_id = ? AND g.title_id = ? AND g.achievement_summary_id IS NULL",
        (platform_id, title_id),
    ).fetchall()

    guides = rows

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
@login_required
def achievement_guides(username, platform, title_id, achievement_id):
    """Show and submit guides for a specific achievement."""
    target_user = get_user_by_username(username)
    if target_user is None:
        flash("User not found.", "error")
        return redirect(url_for("my_games"))

    if platform not in PLATFORM_SLUG_TO_ID:
        flash("Invalid platform.", "error")
        return redirect(url_for("games", username=username))

    platform_id = PLATFORM_SLUG_TO_ID[platform]
    game_name = request.args.get("game_name", f"Title ID: {title_id}")
    media_type = request.args.get("media_type", "")
    achievement_name = request.args.get(
        "achievement_name", f"Achievement ID: {achievement_id}"
    )
    achievement_description = request.args.get("achievement_description", "")

    if request.method == "POST":
        url = request.form.get("url", "").strip()
        if not url:
            flash("Please provide a URL.", "error")
        else:
            title, description = fetch_url_metadata(url)
            db = get_db()

            # Ensure an achievement_summaries record exists for this achievement
            summary = db.execute(
                "SELECT id FROM achievement_summaries "
                "WHERE platform_id = ? AND title_id = ? AND achievement_id = ?",
                (platform_id, title_id, achievement_id),
            ).fetchone()

            if summary is None:
                cursor = db.execute(
                    "INSERT INTO achievement_summaries "
                    "(platform_id, title_id, achievement_id, game_name, achievement_name, achievement_description) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (platform_id, title_id, achievement_id, game_name, achievement_name, achievement_description),
                )
                achievement_summary_id = cursor.lastrowid
            else:
                achievement_summary_id = summary["id"]

            existing = db.execute(
                "SELECT id FROM guides WHERE url = ? AND achievement_summary_id = ?",
                (url, achievement_summary_id),
            ).fetchone()

            if existing:
                flash("A guide with that URL has already been submitted for this achievement.", "error")
            else:
                db.execute(
                    "INSERT INTO guides (url, title, description, platform_id, title_id, achievement_summary_id, user_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (url, title, description, platform_id, title_id, achievement_summary_id, current_user.id),
                )
                db.commit()
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

    db = get_db()

    summary = db.execute(
        "SELECT id FROM achievement_summaries "
        "WHERE platform_id = ? AND title_id = ? AND achievement_id = ?",
        (platform_id, title_id, achievement_id),
    ).fetchone()

    if summary:
        rows = db.execute(
            "SELECT g.id, g.url, g.title, g.description, g.title_id, g.achievement_summary_id, "
            "g.user_id, g.created_at, u.username AS author "
            "FROM guides g JOIN users u ON g.user_id = u.id "
            "WHERE g.achievement_summary_id = ?",
            (summary["id"],),
        ).fetchall()
    else:
        rows = []

    guides = rows

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
