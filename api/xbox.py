import os

import requests

from .achievement import (
    PLATFORM_XBOX,
    Achievement,
    AchievementAPI,
    AchievementAPIError,
)

OPENXBL_API_KEY = os.environ.get("OPENXBL_API_KEY")
OPENXBL_BASE_URL = "https://api.xbl.io"

X360_MEDIA_TYPES = {"Xbox360Game", "XboxArcadeGame"}


def _normalize_x360_achievement(a: dict) -> dict:
    """Convert an Xbox 360 achievement dict into the modern schema so the
    template can render both formats identically.
    """
    image_url = a.get("imageResolved") or ""
    gamerscore = a.get("gamerscore")

    normalized = {
        "id": a.get("id", ""),
        "name": a.get("name", ""),
        "description": a.get("description", ""),
        "lockedDescription": a.get("lockedDescription", ""),
        "progressState": "Achieved" if a.get("unlocked") else "NotStarted",
        "mediaAssets": [{"url": image_url}] if image_url else [],
        "rewards": ([{"value": str(gamerscore)}] if gamerscore is not None else []),
        "progression": {},
        "unlocked": a.get("unlocked", False),
        "titleAssociations": a.get("titleAssociations", []),
        "rarity": a.get("rarity"),
    }

    time_unlocked = a.get("timeUnlocked")
    if time_unlocked:
        normalized["progression"]["timeUnlocked"] = time_unlocked

    return normalized


def xbl_get(path: str) -> dict:
    """Make an authenticated GET request to the OpenXBL API.

    Returns the unwrapped ``"content"`` payload on success.
    Raises :class:`AchievementAPIError` on failure.
    """
    if not OPENXBL_API_KEY:
        raise AchievementAPIError(
            "OPENXBL_API_KEY is not set. Please add it to your .env file."
        )

    headers = {
        "X-Authorization": OPENXBL_API_KEY,
        "Accept": "application/json",
    }

    try:
        resp = requests.get(
            f"{OPENXBL_BASE_URL}{path}",
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as exc:
        if hasattr(exc, "response") and exc.response is not None:
            raise AchievementAPIError(
                f"OpenXBL returned status {exc.response.status_code}. "
                "Check that the XUID is correct."
            ) from exc
        raise AchievementAPIError(f"Failed to reach OpenXBL: {exc}") from exc

    # The OpenXBL API wraps responses in {"content": ..., "code": ...}.
    # Unwrap if present, otherwise return the raw data.
    if isinstance(data, dict) and "content" in data:
        return data["content"]
    return data


class XboxAchievementAPI(AchievementAPI):
    """Fetch Xbox achievements from the OpenXBL API.

    Parameters
    ----------
    xuid : str
        The Xbox User ID.
    title_id : str
        The game's title ID on Xbox.
    media_type : str, optional
        The media type string (e.g. ``"Xbox360Game"``).  Used to determine
        whether Xbox 360 normalisation is required.
    """

    def __init__(self, xuid: str, title_id: str, media_type: str = ""):
        self.xuid = xuid
        self.title_id = title_id
        self.media_type = media_type
        self.is_x360 = media_type in X360_MEDIA_TYPES
        self._achievements: list[Achievement] | None = None
        self.game_name: str | None = None

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------

    def _fetch_raw_achievements(self) -> list[dict]:
        """Fetch raw achievement dicts from the OpenXBL API."""
        if self.is_x360:
            content = xbl_get(
                f"/v2/achievements/x360/{self.xuid}/title/{self.title_id}"
            )
            title_content = xbl_get(
                f"/v2/achievements/player/{self.xuid}/title/{self.title_id}"
            )
        else:
            content = xbl_get(
                f"/v2/achievements/player/{self.xuid}/{self.title_id}"
            )
            title_content = {}

        raw = (
            content.get("achievements", [])
            if isinstance(content, dict)
            else []
        )

        if self.is_x360:
            player = [_normalize_x360_achievement(a) for a in raw]
            title = [
                _normalize_x360_achievement(a)
                for a in title_content.get("achievements", [])
            ]
            player_ids = {a["id"] for a in player}
            raw = player + [a for a in title if a["id"] not in player_ids]

        return raw

    @staticmethod
    def _parse_achievement(raw: dict, title_id: int) -> Achievement:
        """Convert a single raw achievement dict into an ``Achievement``."""
        media_assets = raw.get("mediaAssets") or []
        image_url = media_assets[0].get("url", "") if media_assets else ""

        rewards = raw.get("rewards") or []
        try:
            gamerscore = int(rewards[0]["value"]) if rewards else None
        except (ValueError, KeyError, IndexError):
            gamerscore = None

        rarity = raw.get("rarity")
        rarity_pct = None
        if isinstance(rarity, dict):
            rarity_pct = rarity.get("currentPercentage")

        progression = raw.get("progression") or {}
        time_unlocked = progression.get("timeUnlocked")

        return Achievement(
            platform_id=PLATFORM_XBOX,
            achievement_id=raw.get("id", ""),
            title_id=title_id,
            name=raw.get("name", ""),
            description=raw.get("description", ""),
            image_url=image_url,
            unlocked=raw.get("progressState") == "Achieved",
            locked_description=raw.get("lockedDescription", ""),
            time_unlocked=time_unlocked,
            gamerscore=gamerscore,
            rarity_percentage=rarity_pct,
        )

    # -----------------------------------------------------------------
    # Public API (AchievementAPI interface)
    # -----------------------------------------------------------------

    def get_all_achievements(self) -> list[Achievement]:
        """Return every achievement for the configured game/player.

        Results are cached after the first call so that
        ``get_unlocked_achievements`` and ``get_locked_achievements``
        (which delegate here) don't trigger additional HTTP requests.
        """
        if self._achievements is not None:
            return self._achievements

        raw_list = self._fetch_raw_achievements()

        achievements: list[Achievement] = []
        for raw in raw_list:
            # Grab the game name from the first achievement that has one.
            if self.game_name is None:
                assocs = raw.get("titleAssociations", [])
                if assocs:
                    self.game_name = assocs[0].get("name")

            achievements.append(
                self._parse_achievement(raw, int(self.title_id))
            )

        self._achievements = achievements
        return self._achievements
