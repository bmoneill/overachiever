import os

import requests

from .achievement import (
    PLATFORM_STEAM,
    Achievement,
    AchievementAPI,
    AchievementAPIError,
)

STEAM_API_KEY = os.environ.get("STEAM_API_KEY")
STEAM_API_BASE_URL = "https://api.steampowered.com"


def steam_get(path: str, params: dict | None = None) -> dict:
    """Make an authenticated GET request to the Steam Web API.

    The API key is appended automatically.  Any extra *params* are
    merged in.  Returns the parsed JSON body.  If the top-level object
    contains a ``"response"`` key it is automatically unwrapped.

    Raises :class:`AchievementAPIError` on failure.
    """
    if not STEAM_API_KEY:
        raise AchievementAPIError(
            "STEAM_API_KEY is not set. Please add it to your .env file."
        )

    all_params: dict = {"key": STEAM_API_KEY}
    if params:
        all_params.update(params)

    try:
        resp = requests.get(
            f"{STEAM_API_BASE_URL}{path}",
            params=all_params,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as exc:
        if hasattr(exc, "response") and exc.response is not None:
            raise AchievementAPIError(
                f"Steam API returned status {exc.response.status_code}."
            ) from exc
        raise AchievementAPIError(f"Failed to reach Steam API: {exc}") from exc

    if isinstance(data, dict) and "response" in data:
        return data["response"]
    return data


class SteamAchievementAPI(AchievementAPI):
    """Fetch Steam achievements from the Steam Web API.

    Parameters
    ----------
    steam_id : str, optional
        A default Steam ID (64-bit numeric string) used by
        ``get_user_achievements`` when no explicit ``user_id`` is
        required elsewhere.  Title-only methods do not need this.
    """

    def __init__(self, steam_id: str | None = None):
        self.steam_id = steam_id
        self._schema_cache: dict[str, list[dict]] = {}
        self._cache: dict[str, list[Achievement]] = {}
        self.game_name: str | None = None

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------

    def _fetch_title_schema(self, title_id: str) -> list[dict]:
        """Fetch raw achievement definitions via ``GetSchemaForGame``.

        Results are cached per *title_id* so that
        ``get_title_achievements`` and ``get_user_achievements_for_title``
        can share the same data without a redundant HTTP round-trip.
        """
        if title_id in self._schema_cache:
            return self._schema_cache[title_id]

        data = steam_get(
            "/ISteamUserStats/GetSchemaForGame/v2",
            params={"appid": title_id},
        )

        game = data.get("game", {})
        if self.game_name is None:
            self.game_name = game.get("gameName")

        stats = game.get("availableGameStats", {})
        schema = stats.get("achievements", [])

        self._schema_cache[title_id] = schema
        return schema

    def _fetch_user_unlocked(
        self, user_id: str, title_id: str
    ) -> list[dict]:
        """Return the user's *unlocked* achievements for one title.

        Uses ``GetTopAchievementsForGames`` with a high
        ``max_achievements`` cap so that every unlock is returned.
        """
        data = steam_get(
            "/IPlayerService/GetTopAchievementsForGames/v1",
            params={
                "steamid": user_id,
                "appids[0]": title_id,
                "max_achievements": "10000",
            },
        )

        games = data.get("games", [])
        if not games:
            return []
        return games[0].get("achievements", [])

    def _build_title_achievements(self, title_id: str) -> list[Achievement]:
        """Fetch and cache all achievement definitions for a title.

        Every achievement is returned with ``unlocked=False`` since
        there is no user context.  Hidden achievements have their
        description cleared and ``locked_description`` set instead.
        """
        cache_key = f"title:{title_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        schema = self._fetch_title_schema(title_id)

        achievements: list[Achievement] = []
        for raw in schema:
            hidden = raw.get("hidden", 0) in (1, True)
            achievements.append(
                Achievement(
                    platform_id=PLATFORM_STEAM,
                    achievement_id=raw.get("name", ""),
                    title_id=int(title_id),
                    name=raw.get("displayName", ""),
                    description="" if hidden else raw.get("description", ""),
                    image_url=raw.get("icon", ""),
                    unlocked=False,
                    locked_description="Hidden achievement." if hidden else "",
                )
            )

        self._cache[cache_key] = achievements
        return achievements

    def _build_user_achievements_for_title(
        self, user_id: str, title_id: str
    ) -> list[Achievement]:
        """Merge title schema with user unlock data and cache the result.

        Hidden achievements that are still locked have their description
        replaced with ``"Hidden achievement."``.  Once unlocked the real
        description is revealed.
        """
        cache_key = f"user:{user_id}:title:{title_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        schema = self._fetch_title_schema(title_id)
        unlocked_raw = self._fetch_user_unlocked(user_id, title_id)

        # The user endpoint uses the *display* name in the "name" field.
        unlocked_map: dict[str, dict] = {}
        for ua in unlocked_raw:
            unlocked_map[ua.get("name", "")] = ua

        achievements: list[Achievement] = []
        for raw in schema:
            display_name = raw.get("displayName", "")
            ua = unlocked_map.get(display_name)
            hidden = raw.get("hidden", 0) in (1, True)
            is_unlocked = ua is not None

            # Resolve rarity from the user unlock payload.
            rarity: float | None = None
            if ua:
                rarity_str = ua.get("player_percent_unlocked")
                if rarity_str:
                    try:
                        rarity = float(rarity_str)
                    except ValueError:
                        pass

            # For hidden achievements that are still locked, suppress
            # the real description so the template falls through to
            # locked_description (or the default "Secret achievement"
            # text).
            if hidden and not is_unlocked:
                description = ""
                locked_description = "Hidden achievement."
            else:
                description = raw.get("description", "")
                locked_description = ""

            achievements.append(
                Achievement(
                    platform_id=PLATFORM_STEAM,
                    achievement_id=raw.get("name", ""),
                    title_id=int(title_id),
                    name=display_name,
                    description=description,
                    image_url=raw.get("icon", ""),
                    unlocked=is_unlocked,
                    locked_description=locked_description,
                    rarity_percentage=rarity,
                )
            )

        self._cache[cache_key] = achievements
        return achievements

    # -----------------------------------------------------------------
    # Public API — AchievementAPI abstract interface
    # -----------------------------------------------------------------

    def get_user_achievements(self, user_id: str) -> list[Achievement]:
        """Return every achievement across all of the user's titles.

        .. note::

           This fetches the user's owned-games list and then queries
           each title individually, so it can be *very* slow.  Prefer
           ``get_user_achievements_for_title`` when you already know
           the app ID.
        """
        data = steam_get(
            "/IPlayerService/GetOwnedGames/v1",
            params={
                "steamid": user_id,
                "include_played_free_games": "1",
            },
        )

        games = data.get("games", [])

        all_achievements: list[Achievement] = []
        for game in games:
            appid = str(game.get("appid", ""))
            if not appid:
                continue
            try:
                all_achievements.extend(
                    self._build_user_achievements_for_title(user_id, appid)
                )
            except AchievementAPIError:
                # Some titles have no achievement schema; skip them.
                continue

        return all_achievements

    def get_title_achievements(self, title_id: str) -> list[Achievement]:
        """Return every achievement defined for *title_id*.

        No user context is needed — all achievements are returned with
        ``unlocked`` set to ``False``.
        """
        return self._build_title_achievements(title_id)

    def get_user_achievements_for_title(
        self, user_id: str, title_id: str
    ) -> list[Achievement]:
        """Return all achievements for *title_id* merged with the user's
        unlock progress.
        """
        return self._build_user_achievements_for_title(user_id, title_id)

    def get_achievement(
        self, title_id: str, achievement_id: str
    ) -> Achievement:
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
    ) -> Achievement:
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
