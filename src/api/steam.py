"""
Provides tools for interacting with the Steam Web API.
"""

import os
from datetime import datetime, timezone

import requests

from ..helpers.image_cache import get_image_path
from ..helpers.platform import PLATFORM_STEAM
from .achievement_api import (
    AchievementAPI,
    AchievementAPIError,
    AchievementData,
)
from .api_request import make_request
from .profile import Profile, ProfileAPI, ProfileAPIError

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
        resp = make_request(f"{STEAM_API_BASE_URL}{path}", params=all_params)
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
        self._cache: dict[str, list[AchievementData]] = {}
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

    def _fetch_user_player_achievements(
        self, user_id: str, title_id: str
    ) -> dict[str, dict]:
        """Return a mapping of *apiname* → achievement dict for one title.

        Uses ``ISteamUserStats/GetPlayerAchievements`` which provides
        ``unlocktime`` for every achievement.  Returns **all**
        achievements (both unlocked and locked) keyed by their internal
        API name.
        """
        data = steam_get(
            "/ISteamUserStats/GetPlayerAchievements/v0001",
            params={
                "steamid": user_id,
                "appid": title_id,
            },
        )

        playerstats = data.get("playerstats", {})
        if not playerstats.get("success"):
            return {}

        # The endpoint also returns the game name — use it if we
        # haven't resolved one yet.
        game_name = playerstats.get("gameName")
        if game_name and self.game_name is None:
            self.game_name = game_name

        result: dict[str, dict] = {}
        for ach in playerstats.get("achievements", []):
            apiname = ach.get("apiname", "")
            if apiname:
                result[apiname] = ach
        return result

    def _build_title_achievements(self, title_id: str) -> list[AchievementData]:
        """Fetch and cache all achievement definitions for a title.

        Every achievement is returned with ``unlocked=False`` since
        there is no user context.  Hidden achievements have their
        description cleared and ``locked_description`` set instead.
        """
        cache_key = f"title:{title_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        schema = self._fetch_title_schema(title_id)

        achievements: list[AchievementData] = []
        for raw in schema:
            hidden = raw.get("hidden", 0) in (1, True)
            ach = AchievementData(
                platform_id=PLATFORM_STEAM,
                platform_title_id=str(title_id),
                achievement_id=raw.get("name", ""),
                game_name=self.game_name or "",
                achievement_name=raw.get("displayName", ""),
                description="" if hidden else raw.get("description", ""),
                image_url=raw.get("icon", "") or None,
                locked_description="Hidden achievement." if hidden else "",
                unlocked=False,
                time_unlocked=None,
            )
            if ach.image_url:
                ach.image_url = get_image_path(ach.image_url)
            achievements.append(ach)

        self._cache[cache_key] = achievements
        return achievements

    def _build_user_achievements_for_title(
        self, user_id: str, title_id: str
    ) -> list[AchievementData]:
        """Merge title schema with user unlock data and cache the result.

        Uses ``ISteamUserStats/GetPlayerAchievements`` to obtain unlock
        status and timestamps, matched against the schema by *apiname*.

        Hidden achievements that are still locked have their description
        replaced with ``"Hidden achievement."``.  Once unlocked the real
        description is revealed.
        """
        cache_key = f"user:{user_id}:title:{title_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        schema = self._fetch_title_schema(title_id)
        user_map = self._fetch_user_player_achievements(user_id, title_id)

        achievements: list[AchievementData] = []
        for raw in schema:
            api_name = raw.get("name", "")
            display_name = raw.get("displayName", "")
            ua = user_map.get(api_name)
            hidden = raw.get("hidden", 0) in (1, True)
            is_unlocked = ua is not None and ua.get("achieved", 0) == 1

            # Convert the Unix timestamp to an ISO 8601 string so the
            # template can render it the same way as Xbox unlock times.
            time_unlocked: str | None = None
            if is_unlocked and ua:
                unlock_ts = ua.get("unlocktime", 0)
                if unlock_ts:
                    time_unlocked = datetime.fromtimestamp(
                        unlock_ts, tz=timezone.utc
                    ).isoformat()

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

            ach = AchievementData(
                platform_id=PLATFORM_STEAM,
                platform_title_id=str(title_id),
                achievement_id=api_name,
                game_name=self.game_name or "",
                achievement_name=display_name,
                description=description,
                image_url=raw.get("icon", "") or None,
                locked_description=locked_description,
                unlocked=is_unlocked,
                time_unlocked=time_unlocked,
            )
            if ach.image_url:
                ach.image_url = get_image_path(ach.image_url)
            achievements.append(ach)

        self._cache[cache_key] = achievements
        return achievements

    # -----------------------------------------------------------------
    # Public API — AchievementAPI abstract interface
    # -----------------------------------------------------------------

    def get_user_achievements(self, user_id: str) -> list[AchievementData]:
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

        all_achievements: list[AchievementData] = []
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

    def get_title_achievements(self, title_id: str) -> list[AchievementData]:
        """Return every achievement defined for *title_id*.

        No user context is needed — all achievements are returned with
        ``unlocked`` set to ``False``.
        """
        return self._build_title_achievements(title_id)

    def get_user_achievements_for_title(
        self, user_id: str, title_id: str
    ) -> list[AchievementData]:
        """Return all achievements for *title_id* merged with the user's
        unlock progress.
        """
        return self._build_user_achievements_for_title(user_id, title_id)


class SteamProfileAPI(ProfileAPI):
    """Fetch Steam user profiles from the Steam Web API."""

    def resolve_vanity_url(self, vanity_name: str) -> str:
        """Resolve a Steam vanity URL name to a 64-bit Steam ID.

        Raises :class:`ProfileAPIError` if the name cannot be resolved.
        """
        try:
            data = steam_get(
                "/ISteamUser/ResolveVanityURL/v0001",
                params={"vanityurl": vanity_name},
            )
        except AchievementAPIError as exc:
            raise ProfileAPIError(
                f"Failed to resolve Steam vanity URL '{vanity_name}': {exc}"
            ) from exc

        if data.get("success") != 1:
            raise ProfileAPIError(
                f"Could not resolve Steam vanity URL '{vanity_name}'. "
                "Check that the username is correct."
            )

        steam_id = data.get("steamid", "").strip()
        if not steam_id:
            raise ProfileAPIError(
                f"No Steam ID returned for vanity URL '{vanity_name}'."
            )

        return steam_id

    def get_user_profile(self, user_id: str) -> Profile:
        """Return the Steam profile for the given 64-bit Steam ID.

        Raises :class:`ProfileAPIError` if the request fails or the
        player is not found.
        """
        try:
            data = steam_get(
                "/ISteamUser/GetPlayerSummaries/v0002",
                params={"steamids": user_id},
            )
        except AchievementAPIError as exc:
            raise ProfileAPIError(
                f"Failed to fetch Steam profile for user {user_id}: {exc}"
            ) from exc

        players = data.get("players", [])
        if not players:
            raise ProfileAPIError(f"No Steam player found for ID {user_id}.")

        player = players[0]
        persona_name = player.get("personaname", "")
        avatar_url = player.get("avatarfull", "")
        if avatar_url:
            avatar_url = get_image_path(avatar_url)

        return Profile(
            platform_id=PLATFORM_STEAM,
            name=persona_name,
            image_url=avatar_url,
        )
