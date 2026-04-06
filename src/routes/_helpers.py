import os
import re

from .. import login_manager
from ..models import db
from ..models.user import User
from ..models.achievement import Achievement as AchievementModel
from ..api.platform import PLATFORM_XBOX, PLATFORM_STEAM

PLATFORM_ID_TO_SLUG = {
    PLATFORM_XBOX: "xbox",
    PLATFORM_STEAM: "steam",
}

PLATFORM_SLUG_TO_ID = {
    "xbox": PLATFORM_XBOX,
    "steam": PLATFORM_STEAM,
}

ALLOW_REGISTRATION = os.environ.get("ALLOW_REGISTRATION", "true").lower() not in (
    "false",
    "0",
    "no",
)


@login_manager.user_loader
def load_user(user_id: int):
    return db.session.get(User, int(user_id))


def get_user_by_username(username: str) -> User | None:
    """Look up a user by username. Returns a User or None."""
    return User.query.filter_by(username=username).first()


def _normalize_name(name: str) -> str:
    """Normalize an achievement name for fuzzy matching.

    Lowercases, then strips everything that isn't a-z or 0-9.
    """
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _build_steam_icon_lookup() -> dict[str, str]:
    """Return a dict mapping normalized achievement name → Steam image URL.

    Only Steam achievements that have a non-empty ``image_url`` are
    included.  When multiple Steam achievements share the same normalized
    name, the first one encountered wins (arbitrary but deterministic
    since the query is ordered by id).
    """
    steam_achievements = (
        AchievementModel.query
        .filter_by(platform_id=PLATFORM_STEAM)
        .filter(AchievementModel.image_url.isnot(None))
        .filter(AchievementModel.image_url != "")
        .order_by(AchievementModel.id)
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
        a for a in achievements
        if getattr(a, "platform_id", None) == PLATFORM_XBOX
        and not getattr(a, "image_url", None)
    ]
    if not needs_icon:
        return

    lookup = _build_steam_icon_lookup()

    for a in needs_icon:
        # DB Achievement uses achievement_name; API Achievement uses name
        raw_name = getattr(a, "achievement_name", None) or getattr(a, "name", "")
        key = _normalize_name(raw_name)
        if key and key in lookup:
            a.image_url = lookup[key]
