"""Synchronization layer between external platform APIs and the local database.

This module provides high-level functions that routes call to:

1. **Sync** — fetch data from external platform APIs and upsert it into
   the local database (Titles, UserTitles, Achievements, UserAchievements).
2. **Load** — query the local database and return model instances ready
   for template rendering.

Routes should never touch raw API response dicts directly.  Instead they
call the ``sync_*`` helpers (wrapped in a ``try``/``except`` for
:class:`AchievementAPIError`) and then call the ``load_*`` helpers to
retrieve persisted data.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from flask import url_for

from ..helpers.image_cache import get_image_path
from ..helpers.platform import PLATFORM_STEAM, PLATFORM_XBOX, X360_MEDIA_TYPES
from ..models import db
from ..models.achievement import Achievement
from ..models.title import Title
from ..models.user_achievement import UserAchievement
from ..models.user_title import UserTitle
from ..models.xbox360icon import Xbox360Icon
from .achievement_api import AchievementAPIError, AchievementData
from .steam import SteamAchievementAPI, steam_get
from .xbox import XboxAchievementAPI, xbl_get

if TYPE_CHECKING:
    from ..models.user import User


# ---------------------------------------------------------------------------
# Internal upsert helpers
# ---------------------------------------------------------------------------


def _upsert_title(
    platform: int,
    platform_title_id: str,
    name: str,
    image_url: str | None = None,
    media_type: str | None = None,
    total_achievements: int = 0,
) -> Title:
    """Find or create a :class:`Title` row.

    Returns the (possibly new) ``Title`` instance.  The caller is
    responsible for committing the session.
    """
    db_title: Title | None = Title.query.filter_by(
        platform=platform,
        platform_title_id=str(platform_title_id),
    ).first()

    if db_title is None:
        db_title = Title(
            name=name,
            platform=platform,
            platform_title_id=str(platform_title_id),
            image_url=get_image_path(image_url) if image_url else None,
            media_type=media_type or None,
            total_achievements=total_achievements,
        )
        db.session.add(db_title)
        db.session.flush()

    return db_title


def _upsert_user_title(
    user_id: int,
    title: Title,
    current_achievements: int | None = None,
    progress_percentage: int | None = None,
    last_played: str | None = None,
) -> UserTitle:
    """Find or create a :class:`UserTitle` row.

    The total achievement count for a title is stored on the
    :class:`Title` model rather than here.

    Returns the (possibly new) ``UserTitle`` instance.  The caller is
    responsible for committing the session.
    """
    ut: UserTitle | None = UserTitle.query.filter_by(
        user_id=user_id,
        title_id=title.id,
    ).first()

    if ut is None:
        ut = UserTitle(
            user_id=user_id,
            title_id=title.id,
            current_achievements=current_achievements,
            progress_percentage=progress_percentage,
            last_played=last_played,
        )
        db.session.add(ut)
    else:
        ut.current_achievements = current_achievements
        ut.progress_percentage = progress_percentage
        if last_played:
            ut.last_played = last_played

    return ut


def _sync_single_achievement(
    db_title: Title,
    platform_id: int,
    ach: AchievementData,
    user_id: int,
    is_x360: bool = False,
) -> None:
    """Upsert one :class:`Achievement` and its :class:`UserAchievement`.

    The caller is responsible for committing the session.
    """
    db_ach: Achievement | None = Achievement.find_by_platform(
        platform_id,
        ach.platform_title_id,
        str(ach.achievement_id),
    )

    # Determine image URL (prefer local Xbox 360 icon override).
    image_url: str | None = ach.image_url
    if is_x360:
        try:
            title_id_int = int(ach.platform_title_id)
        except ValueError, TypeError:
            title_id_int = None
        if title_id_int is not None:
            icon = Xbox360Icon.query.filter_by(
                achievement_id=ach.achievement_id,
                title_id=title_id_int,
            ).first()
            if icon:
                image_url = url_for("static", filename=icon.url)

    if db_ach is None:
        db_ach = Achievement(
            achievement_id=str(ach.achievement_id),
            title_id=db_title.id,
            achievement_name=ach.achievement_name,
            description=ach.description or None,
            locked_description=ach.locked_description or None,
            gamerscore=ach.gamerscore,
            rarity=ach.rarity,
            image_url=image_url or None,
        )
        db.session.add(db_ach)
    else:
        db_ach.title_id = db_title.id
        db_ach.achievement_name = ach.achievement_name
        if ach.description:
            db_ach.description = ach.description
        if ach.locked_description:
            db_ach.locked_description = ach.locked_description
        if ach.gamerscore is not None:
            db_ach.gamerscore = ach.gamerscore
        if ach.rarity is not None:
            db_ach.rarity = ach.rarity
        if image_url:
            db_ach.image_url = image_url

    db.session.flush()

    # Upsert or remove UserAchievement
    unlocked: bool = getattr(ach, "unlocked", False)
    time_unlocked: str | None = getattr(ach, "time_unlocked", None)

    user_ach: UserAchievement | None = UserAchievement.query.filter_by(
        user_id=user_id,
        achievement_id=db_ach.id,
    ).first()

    if unlocked:
        if user_ach is None:
            user_ach = UserAchievement(
                user_id=user_id,
                achievement_id=db_ach.id,
                time_unlocked=time_unlocked,
            )
            db.session.add(user_ach)
        else:
            if time_unlocked:
                user_ach.time_unlocked = time_unlocked
    else:
        if user_ach is not None:
            db.session.delete(user_ach)


# ---------------------------------------------------------------------------
# Steam achievement-count batch helper (moved from routes)
# ---------------------------------------------------------------------------


def _fetch_steam_achievement_counts(
    steam_id: str,
    appids: list[str],
) -> dict[str, tuple[int, int]]:
    """Batch-fetch achievement counts for Steam games.

    Calls ``GetTopAchievementsForGames`` in batches and returns a dict
    mapping *appid* -> ``(unlocked, total)``.
    """
    counts: dict[str, tuple[int, int]] = {}
    batch_size = 100
    for start in range(0, len(appids), batch_size):
        batch = appids[start : start + batch_size]
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


# ---------------------------------------------------------------------------
# Per-platform game-list sync
# ---------------------------------------------------------------------------


def _sync_xbox_games(user: User) -> None:
    """Fetch Xbox game titles for *user* and upsert Title + UserTitle rows."""
    if not user.xuid:
        return

    content = xbl_get(f"/v2/titles/{user.xuid}")
    titles = content.get("titles", []) if isinstance(content, dict) else []

    for title in titles:
        ach_info = title.get("achievement") or {}
        hist = title.get("titleHistory") or {}

        platform_title_id = str(title.get("titleId", ""))
        if not platform_title_id:
            continue

        db_title = _upsert_title(
            platform=PLATFORM_XBOX,
            platform_title_id=platform_title_id,
            name=title.get("name", "Unknown"),
            image_url=title.get("displayImage", ""),
            media_type=title.get("mediaItemType", ""),
            total_achievements=ach_info.get("totalAchievements", 0),
        )

        _upsert_user_title(
            user_id=user.id,
            title=db_title,
            current_achievements=ach_info.get("currentAchievements", 0),
            progress_percentage=ach_info.get("progressPercentage", 0),
            last_played=hist.get("lastTimePlayed", ""),
        )

    db.session.commit()


def _sync_steam_games(user: User) -> None:
    """Fetch Steam game titles for *user* and upsert Title + UserTitle rows."""
    if not user.steam_id:
        return

    data = steam_get(
        "/IPlayerService/GetOwnedGames/v1",
        params={
            "steamid": user.steam_id,
            "include_played_free_games": "1",
            "include_appinfo": "1",
        },
    )
    steam_games = data.get("games", [])

    appids = [str(g["appid"]) for g in steam_games if g.get("appid")]
    ach_counts = _fetch_steam_achievement_counts(user.steam_id, appids)

    for game in steam_games:
        appid = str(game.get("appid", ""))
        if not appid:
            continue

        rtime = game.get("rtime_last_played", 0)
        last_played: str = ""
        if rtime:
            last_played = datetime.fromtimestamp(
                rtime, tz=timezone.utc
            ).isoformat()

        current: int | None = None
        total: int | None = None
        progress: int | None = None
        if appid in ach_counts:
            current, total = ach_counts[appid]
            progress = round(current / total * 100) if total > 0 else 0

        img = (
            f"https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg"
            if appid
            else ""
        )

        db_title = _upsert_title(
            platform=PLATFORM_STEAM,
            platform_title_id=appid,
            name=game.get("name", "Unknown Title"),
            image_url=img,
            total_achievements=total or 0,
        )

        _upsert_user_title(
            user_id=user.id,
            title=db_title,
            current_achievements=current,
            progress_percentage=progress,
            last_played=last_played,
        )

    db.session.commit()


# ---------------------------------------------------------------------------
# Public sync API
# ---------------------------------------------------------------------------


def sync_user_games(user: User) -> list[str]:
    """Sync game titles for all linked platforms.

    Fetches Xbox and/or Steam game lists and upserts :class:`Title` and
    :class:`UserTitle` rows.  Also updates the user's aggregate
    ``achievement_count``.

    Returns a list of human-readable error strings (one per failed
    platform).  An empty list means everything succeeded.
    """
    errors: list[str] = []

    if user.xuid:
        try:
            _sync_xbox_games(user)
        except AchievementAPIError as exc:
            errors.append(f"Xbox: {exc}")

    if user.steam_id:
        try:
            _sync_steam_games(user)
        except AchievementAPIError as exc:
            errors.append(f"Steam: {exc}")

    # Recompute aggregate achievement count from UserTitle rows.
    total = sum(
        ut.current_achievements or 0
        for ut in UserTitle.query.filter_by(user_id=user.id).all()
    )
    user.achievement_count = total
    db.session.commit()

    return errors


def sync_title_achievements(
    user: User,
    platform_id: int,
    platform_title_id: str,
    media_type: str = "",
) -> None:
    """Fetch achievements for a single title and sync them to the database.

    Calls the appropriate platform API, then upserts :class:`Title`,
    :class:`Achievement`, and :class:`UserAchievement` rows.

    Raises :class:`AchievementAPIError` if the API call fails so that the
    caller can flash an appropriate message and fall back to cached data.
    """
    # If media_type wasn't supplied, try to read it from an existing Title.
    if not media_type:
        existing = Title.find_by_platform(platform_id, platform_title_id)
        if existing and existing.media_type:
            media_type = existing.media_type

    # Fetch achievements from the platform API.
    achievements: list[AchievementData]
    if platform_id == PLATFORM_XBOX:
        if not user.xuid:
            raise AchievementAPIError("This user has no linked Xbox account.")
        api = XboxAchievementAPI(xuid=user.xuid, media_type=media_type)
        achievements = api.get_user_achievements_for_title(
            user.xuid, platform_title_id
        )
    elif platform_id == PLATFORM_STEAM:
        if not user.steam_id:
            raise AchievementAPIError("This user has no linked Steam account.")
        api = SteamAchievementAPI(steam_id=user.steam_id)
        achievements = api.get_user_achievements_for_title(
            user.steam_id, platform_title_id
        )
    else:
        raise AchievementAPIError(f"Unsupported platform: {platform_id}")

    if not achievements:
        return

    # Derive game name from the API response.
    game_name: str = ""
    for ach in achievements:
        if ach.game_name:
            game_name = ach.game_name
            break

    db_title = _upsert_title(
        platform=platform_id,
        platform_title_id=platform_title_id,
        name=game_name or "Unknown",
        media_type=media_type or None,
        total_achievements=len(achievements),
    )

    is_x360 = platform_id == PLATFORM_XBOX and media_type in X360_MEDIA_TYPES

    for ach in achievements:
        _sync_single_achievement(
            db_title=db_title,
            platform_id=platform_id,
            ach=ach,
            user_id=user.id,
            is_x360=is_x360,
        )

    db.session.commit()


# ---------------------------------------------------------------------------
# DB loading helpers
# ---------------------------------------------------------------------------


def load_title_achievements(
    user_id: int,
    platform_id: int,
    platform_title_id: str,
) -> tuple[list[Achievement], list[Achievement]]:
    """Load achievements from the database for one title.

    Returns ``(unlocked, locked)`` — two lists of :class:`Achievement`
    model instances.  Each instance has ad-hoc ``unlocked`` and
    ``time_unlocked`` attributes set so that templates can render them
    identically regardless of whether the data came from a fresh sync or
    an offline cache.

    Xbox achievements that are missing an icon will have the Steam
    icon-fallback logic applied automatically.
    """
    db_achievements = Title.find_by_platform(
        platform_id, platform_title_id
    ).achievements

    unlocked: list[Achievement] = []
    locked: list[Achievement] = []

    for db_ach in db_achievements:
        user_ach: UserAchievement | None = UserAchievement.query.filter_by(
            user_id=user_id,
            achievement_id=db_ach.id,
        ).first()

        is_unlocked = user_ach is not None
        db_ach.unlocked = is_unlocked  # type: ignore[attr-defined]
        db_ach.time_unlocked = (  # type: ignore[attr-defined]
            user_ach.time_unlocked if user_ach else None
        )

        if is_unlocked:
            unlocked.append(db_ach)
        else:
            locked.append(db_ach)

    # Apply Steam icon fallbacks for Xbox achievements missing images.
    if platform_id == PLATFORM_XBOX:
        resolve_xbox_icon_fallbacks(unlocked + locked)

    return unlocked, locked


# ---------------------------------------------------------------------------
# Xbox icon-fallback utilities  (moved from routes/_helpers.py)
# ---------------------------------------------------------------------------


def _normalize_name(name: str) -> str:
    """Normalize an achievement name for fuzzy matching.

    Lowercases, then strips everything that isn't a–z or 0–9.
    """
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _build_steam_icon_lookup() -> dict[str, str]:
    """Return a dict mapping normalized achievement name -> Steam image URL.

    Only Steam achievements that have a non-empty ``image_url`` are
    included.  When multiple Steam achievements share the same normalized
    name, the first one encountered wins (arbitrary but deterministic
    since the query is ordered by id).
    """
    steam_achievements = (
        Achievement.query.join(Title)
        .filter(Title.platform == PLATFORM_STEAM)
        .filter(Achievement.image_url.isnot(None))
        .filter(Achievement.image_url != "")
        .order_by(Achievement.id)
        .all()
    )

    lookup: dict[str, str] = {}
    for sa in steam_achievements:
        key = _normalize_name(sa.achievement_name)
        if key and key not in lookup:
            lookup[key] = sa.image_url
    return lookup


def resolve_xbox_icon_fallbacks(achievements: list) -> None:
    """Fill in missing Xbox achievement icons using Steam equivalents.

    Accepts a list of objects that each have ``platform_id`` and
    ``image_url`` attributes, plus either ``achievement_name`` (DB model)
    or ``name`` (API dataclass).

    Achievements that already have an ``image_url`` or that are not Xbox
    achievements are left untouched.
    """
    needs_icon = [
        a
        for a in achievements
        if getattr(a, "platform_id", None) == PLATFORM_XBOX
        and not getattr(a, "image_url", None)
    ]
    if not needs_icon:
        return

    lookup = _build_steam_icon_lookup()

    for a in needs_icon:
        raw_name = getattr(a, "achievement_name", None) or getattr(
            a, "name", ""
        )
        key = _normalize_name(raw_name)
        if key and key in lookup:
            a.image_url = lookup[key]
