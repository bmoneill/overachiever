"""
Provides tools for interacting with the Xbox OpenXBL API.
"""

import os

import requests

from .achievement_api import AchievementAPI, AchievementAPIError, AchievementData
from ..helpers.platform import PLATFORM_XBOX
from ..helpers.image_cache import get_image_path
from .api_request import make_request
from .profile import Profile, ProfileAPI, ProfileAPIError

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
        "mediaAssets": [{"url": get_image_path(image_url)}] if image_url else [],
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
        resp = make_request(
            f"{OPENXBL_BASE_URL}{path}",
            headers=headers
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
    xuid : str, optional
        A default Xbox User ID used by methods that don't accept a
        ``user_id`` parameter (``get_title_achievements`` and
        ``get_achievement``).  The OpenXBL API always requires *some*
        user context, so these methods will raise
        :class:`AchievementAPIError` if no default XUID was provided.
    media_type : str, optional
        The media type string (e.g. ``"Xbox360Game"``).  Used to
        determine whether Xbox 360 normalisation is required.
    """

    def __init__(self, xuid: str | None = None, media_type: str = ""):
        self.xuid = xuid
        self.media_type = media_type
        self.is_x360 = media_type in X360_MEDIA_TYPES
        self._cache: dict[str, list[AchievementData]] = {}
        self.game_name: str | None = None

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------

    def _require_xuid(self) -> str:
        """Return ``self.xuid`` or raise if it was not set."""
        if not self.xuid:
            raise AchievementAPIError(
                "A default XUID is required for this operation. "
                "Pass xuid to the XboxAchievementAPI constructor."
            )
        return self.xuid

    def _fetch_raw_achievements(self, xuid: str, title_id: str) -> list[dict]:
        """Fetch raw achievement dicts from the OpenXBL API."""
        if self.is_x360:
            content = xbl_get(
                f"/v2/achievements/x360/{xuid}/title/{title_id}"
            )
            title_content = xbl_get(
                f"/v2/achievements/player/{xuid}/title/{title_id}"
            )
        else:
            content = xbl_get(
                f"/v2/achievements/player/{xuid}/{title_id}"
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

    def _build_achievements(
        self, xuid: str, title_id: str
    ) -> list[AchievementData]:
        """Fetch, parse, and cache achievements for a *user + title* pair."""
        cache_key = f"{xuid}:{title_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        raw_list = self._fetch_raw_achievements(xuid, title_id)

        achievements: list[AchievementData] = []
        for raw in raw_list:
            # Grab the game name from the first achievement that has one.
            if self.game_name is None:
                assocs = raw.get("titleAssociations", [])
                if assocs:
                    self.game_name = assocs[0].get("name")

            achievements.append(
                self._parse_achievement(raw, int(title_id))
            )

        # Fix up game_name for achievements parsed before it was discovered.
        if self.game_name:
            for a in achievements:
                if not a.game_name:
                    a.game_name = self.game_name

        self._cache[cache_key] = achievements
        return achievements

    def _parse_achievement(self, raw: dict, title_id: int) -> AchievementData:
        """Convert a single raw achievement dict into an ``AchievementData``."""
        media_assets = raw.get("mediaAssets") or []
        image_url = media_assets[0].get("url", "") if media_assets else ""
        if image_url:
            image_url = get_image_path(image_url)

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

        ach = AchievementData(
            platform_id=PLATFORM_XBOX,
            platform_title_id=str(title_id),
            achievement_id=str(raw.get("id", "")),
            game_name=self.game_name or "",
            achievement_name=raw.get("name", ""),
            description=raw.get("description", "") or None,
            locked_description=raw.get("lockedDescription", "") or None,
            gamerscore=gamerscore,
            rarity=rarity_pct,
            image_url=get_image_path(image_url) if image_url else None,
            unlocked=raw.get("progressState") == "Achieved",
            time_unlocked=time_unlocked,
        )
        return ach

    # -----------------------------------------------------------------
    # Public API  — AchievementAPI abstract interface
    # -----------------------------------------------------------------

    def get_user_achievements(self, user_id: str) -> list[AchievementData]:
        """Return every achievement across all of the user's titles.

        .. note::

           This issues one HTTP request per title the user owns and can
           therefore be *very* slow.  Prefer
           ``get_user_achievements_for_title`` when you already know the
           title ID.
        """
        content = xbl_get(f"/v2/titles/{user_id}")
        titles = content.get("titles", []) if isinstance(content, dict) else []

        all_achievements: list[AchievementData] = []
        for title in titles:
            tid = str(title.get("titleId", ""))
            if not tid:
                continue
            try:
                all_achievements.extend(self._build_achievements(user_id, tid))
            except AchievementAPIError:
                # Skip titles whose achievements can't be fetched.
                continue

        return all_achievements

    def get_title_achievements(self, title_id: str) -> list[AchievementData]:
        """Return every achievement defined for *title_id*.

        The OpenXBL API always requires a user context, so the default
        ``xuid`` supplied to the constructor is used here.  The returned
        achievements have ``unlocked`` set to ``False`` and
        ``time_unlocked`` cleared because they represent title-level
        definitions rather than any particular player's progress.
        """
        xuid = self._require_xuid()
        user_achievements = self._build_achievements(xuid, title_id)

        result: list[AchievementData] = []
        for a in user_achievements:
            ach = AchievementData(
                platform_id=a.platform_id,
                platform_title_id=a.platform_title_id,
                achievement_id=a.achievement_id,
                game_name=a.game_name,
                achievement_name=a.achievement_name,
                description=a.description,
                locked_description=a.locked_description,
                gamerscore=a.gamerscore,
                rarity=a.rarity,
                image_url=get_image_path(a.image_url) if a.image_url else None,
                unlocked=False,
                time_unlocked=None,
            )
            result.append(ach)
        return result

    def get_user_achievements_for_title(
        self, user_id: str, title_id: str
    ) -> list[AchievementData]:
        """Return user achievements for *title_id* (including progress)."""
        return self._build_achievements(user_id, title_id)

    def get_achievement(
        self, title_id: str, achievement_id: str
    ) -> AchievementData:
        """Return a single achievement definition by title and achievement ID.

        Raises :class:`AchievementAPIError` if not found.
        """
        for a in self.get_title_achievements(title_id):
            if str(a.achievement_id) == str(achievement_id):
                return a
        raise AchievementAPIError(
            f"Achievement {achievement_id} not found in title {title_id}."
        )

    def get_user_achievement(
        self, user_id: str, title_id: str, achievement_id: str
    ) -> AchievementData:
        """Return a single user achievement (with progress).

        Raises :class:`AchievementAPIError` if not found.
        """
        for a in self.get_user_achievements_for_title(user_id, title_id):
            if str(a.achievement_id) == str(achievement_id):
                return a
        raise AchievementAPIError(
            f"Achievement {achievement_id} not found for user {user_id} "
            f"in title {title_id}."
        )


class XboxProfileAPI(ProfileAPI):
    """Fetch Xbox user profiles from the OpenXBL API."""

    def get_xuid_from_gamertag(self, gamertag: str) -> str:
        gamertag = gamertag.strip()
        try:
            content = xbl_get(f"/v2/search/{gamertag}")
        except AchievementAPIError as exc:
            raise ProfileAPIError(
                f"Failed to fetch Xbox profile for gamertag {gamertag}: {exc}"
            ) from exc

        returned_profile = content["people"][0]
        if returned_profile["gamertag"] != gamertag:
            raise ProfileAPIError(
                f"Exact match not found. Make sure you entered the correct "
                f"gamertag, including capitalization."
            )
        return returned_profile["xuid"]


    def get_user_profile(self, user_id: str) -> Profile:
        """Return the Xbox profile for the given XUID.

        Raises :class:`ProfileAPIError` if the request fails or the
        response format is unexpected.
        """
        try:
            content = xbl_get(f"/v2/account/{user_id}")
        except AchievementAPIError as exc:
            raise ProfileAPIError(
                f"Failed to fetch Xbox profile for user {user_id}: {exc}"
            ) from exc

        try:
            settings = content["profileUsers"][0]["settings"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProfileAPIError(
                f"Unexpected response format when fetching Xbox profile "
                f"for user {user_id}."
            ) from exc

        settings_map = {s["id"]: s["value"] for s in settings}

        gamertag = settings_map.get("Gamertag")
        if not gamertag:
            raise ProfileAPIError(
                f"Gamertag not found in Xbox profile for user {user_id}."
            )

        avatar_url = settings_map.get("GameDisplayPicRaw", "")

        return Profile(
            platform_id=PLATFORM_XBOX,
            name=gamertag,
            image_url=get_image_path(avatar_url) if avatar_url else "",
        )
