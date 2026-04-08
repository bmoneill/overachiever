"""Tests for :mod:`src.api.steam`.

Covers :func:`steam_get` (authenticated requests, error handling, response
unwrapping), :class:`SteamAchievementAPI` (schema fetching, user achievement
merging, caching, owned-games iteration), and :class:`SteamProfileAPI`
(vanity URL resolution, player summary fetching).

All HTTP calls are mocked — no real network traffic is produced.
"""

from __future__ import annotations

from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.api.achievement_api import AchievementAPIError, AchievementData
from src.api.profile import ProfileAPIError
from src.api.steam import (
    SteamAchievementAPI,
    SteamProfileAPI,
    steam_get,
)
from src.helpers.platform import PLATFORM_STEAM

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_fake_response(
    status_code: int = 200,
    json_data: dict | None = None,
) -> MagicMock:
    """Build a mock ``requests.Response``."""
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        http_error = requests.exceptions.HTTPError(response=resp)
        resp.raise_for_status.side_effect = http_error
    return resp


# ===================================================================
# steam_get tests
# ===================================================================


class TestSteamGet:
    """Tests for :func:`steam_get`."""

    def test_raises_when_api_key_missing(self) -> None:
        """Should raise ``AchievementAPIError`` when no API key is set."""
        with patch("src.api.steam.STEAM_API_KEY", None):
            with pytest.raises(AchievementAPIError, match="STEAM_API_KEY"):
                steam_get("/ISteamUser/GetPlayerSummaries/v0002")

    @patch("src.api.steam.make_request")
    def test_returns_unwrapped_response(
        self, mock_req: MagicMock, mock_steam_api_key: None
    ) -> None:
        """When the JSON body has a ``response`` key, it should be unwrapped."""
        mock_req.return_value = _make_fake_response(
            200, {"response": {"players": [{"personaname": "Bob"}]}}
        )
        result = steam_get("/ISteamUser/GetPlayerSummaries/v0002")
        assert result == {"players": [{"personaname": "Bob"}]}

    @patch("src.api.steam.make_request")
    def test_returns_raw_when_no_response_key(
        self, mock_req: MagicMock, mock_steam_api_key: None
    ) -> None:
        """When the JSON body lacks a ``response`` key, return it as-is."""
        mock_req.return_value = _make_fake_response(200, {"game": {}})
        result = steam_get("/ISteamUserStats/GetSchemaForGame/v2")
        assert result == {"game": {}}

    @patch("src.api.steam.make_request")
    def test_merges_params_with_api_key(
        self, mock_req: MagicMock, mock_steam_api_key: None
    ) -> None:
        """The API key should be merged into the params dict."""
        mock_req.return_value = _make_fake_response(200, {"response": {}})
        steam_get("/some/path", params={"appid": "440"})

        call_kwargs = mock_req.call_args
        sent_params = call_kwargs.kwargs.get("params") or call_kwargs[1].get(
            "params"
        )
        # make_request is called positionally:  make_request(url, params=...)
        # Let's just check the call args directly
        args, kwargs = mock_req.call_args
        assert "fake-steam-key" in str(args) or "fake-steam-key" in str(kwargs)

    @patch("src.api.steam.make_request")
    def test_raises_on_http_error_with_response(
        self, mock_req: MagicMock, mock_steam_api_key: None
    ) -> None:
        """Should wrap HTTP errors into ``AchievementAPIError``."""
        mock_req.return_value = _make_fake_response(403)
        with pytest.raises(AchievementAPIError, match="status 403"):
            steam_get("/some/path")

    @patch("src.api.steam.make_request")
    def test_raises_on_connection_error(
        self, mock_req: MagicMock, mock_steam_api_key: None
    ) -> None:
        """Should wrap connection errors into ``AchievementAPIError``."""
        mock_req.side_effect = requests.exceptions.ConnectionError("refused")
        with pytest.raises(AchievementAPIError, match="Failed to reach"):
            steam_get("/some/path")


# ===================================================================
# SteamAchievementAPI — schema / title achievements
# ===================================================================

# Sample responses used across tests

SCHEMA_RESPONSE = {
    "game": {
        "gameName": "Test Game",
        "availableGameStats": {
            "achievements": [
                {
                    "name": "ACH_01",
                    "displayName": "First Blood",
                    "description": "Get your first kill",
                    "hidden": 0,
                    "icon": "https://img.example.com/ach01.png",
                },
                {
                    "name": "ACH_02",
                    "displayName": "Secret Find",
                    "description": "Find the hidden room",
                    "hidden": 1,
                    "icon": "https://img.example.com/ach02.png",
                },
            ]
        },
    }
}

PLAYER_ACHIEVEMENTS_RESPONSE = {
    "playerstats": {
        "success": True,
        "gameName": "Test Game",
        "achievements": [
            {"apiname": "ACH_01", "achieved": 1, "unlocktime": 1700000000},
            {"apiname": "ACH_02", "achieved": 0, "unlocktime": 0},
        ],
    }
}

OWNED_GAMES_RESPONSE = {
    "games": [
        {"appid": 440},
        {"appid": 730},
    ]
}


class TestSteamAchievementAPITitleAchievements:
    """Tests for :meth:`SteamAchievementAPI.get_title_achievements`."""

    @patch("src.api.steam.steam_get")
    def test_returns_all_achievements_for_title(
        self, mock_get: MagicMock
    ) -> None:
        """Should return an ``AchievementData`` for every schema entry."""
        mock_get.return_value = SCHEMA_RESPONSE
        api = SteamAchievementAPI()

        result = api.get_title_achievements("440")

        assert len(result) == 2
        assert all(isinstance(a, AchievementData) for a in result)
        assert result[0].achievement_id == "ACH_01"
        assert result[1].achievement_id == "ACH_02"

    @patch("src.api.steam.steam_get")
    def test_all_marked_unlocked_false(self, mock_get: MagicMock) -> None:
        """Title-level achievements should all have ``unlocked=False``."""
        mock_get.return_value = SCHEMA_RESPONSE
        api = SteamAchievementAPI()

        result = api.get_title_achievements("440")

        assert all(not a.unlocked for a in result)
        assert all(a.time_unlocked is None for a in result)

    @patch("src.api.steam.steam_get")
    def test_hidden_achievement_description_cleared(
        self, mock_get: MagicMock
    ) -> None:
        """Hidden achievements should have empty description and a
        ``locked_description`` of ``"Hidden achievement."``."""
        mock_get.return_value = SCHEMA_RESPONSE
        api = SteamAchievementAPI()

        result = api.get_title_achievements("440")

        visible = result[0]
        hidden = result[1]

        assert visible.description == "Get your first kill"
        assert visible.locked_description == ""
        assert hidden.description == ""
        assert hidden.locked_description == "Hidden achievement."

    @patch("src.api.steam.steam_get")
    def test_platform_id_is_steam(self, mock_get: MagicMock) -> None:
        """All achievements should carry ``PLATFORM_STEAM``."""
        mock_get.return_value = SCHEMA_RESPONSE
        api = SteamAchievementAPI()

        result = api.get_title_achievements("440")

        assert all(a.platform_id == PLATFORM_STEAM for a in result)

    @patch("src.api.steam.steam_get")
    def test_caches_title_achievements(self, mock_get: MagicMock) -> None:
        """A second call for the same title should use the cache."""
        mock_get.return_value = SCHEMA_RESPONSE
        api = SteamAchievementAPI()

        first = api.get_title_achievements("440")
        second = api.get_title_achievements("440")

        assert first is second
        assert mock_get.call_count == 1

    @patch("src.api.steam.steam_get")
    def test_game_name_set_from_schema(self, mock_get: MagicMock) -> None:
        """``game_name`` on each achievement should come from the schema."""
        mock_get.return_value = SCHEMA_RESPONSE
        api = SteamAchievementAPI()

        result = api.get_title_achievements("440")

        assert all(a.game_name == "Test Game" for a in result)

    @patch("src.api.steam.steam_get")
    def test_empty_schema(self, mock_get: MagicMock) -> None:
        """A title with no achievements should return an empty list."""
        mock_get.return_value = {
            "game": {"gameName": "Empty", "availableGameStats": {}}
        }
        api = SteamAchievementAPI()

        result = api.get_title_achievements("999")
        assert result == []

    @patch("src.api.steam.steam_get")
    def test_image_url_processed(self, mock_get: MagicMock) -> None:
        """Image URLs should be passed through ``get_image_path``."""
        mock_get.return_value = SCHEMA_RESPONSE
        api = SteamAchievementAPI()

        result = api.get_title_achievements("440")

        # The mock_image_cache fixture replaces get_image_path with a
        # deterministic fake that returns /static/img/{hash(url)}.
        for ach in result:
            assert ach.image_url is not None
            assert "/static/img/" in ach.image_url


# ===================================================================
# SteamAchievementAPI — user achievements for a title
# ===================================================================


class TestSteamAchievementAPIUserTitle:
    """Tests for :meth:`SteamAchievementAPI.get_user_achievements_for_title`."""

    @patch("src.api.steam.steam_get")
    def test_merges_schema_and_player_data(self, mock_get: MagicMock) -> None:
        """Achievements should reflect the user's unlock status."""
        mock_get.side_effect = [SCHEMA_RESPONSE, PLAYER_ACHIEVEMENTS_RESPONSE]
        api = SteamAchievementAPI()

        result = api.get_user_achievements_for_title("12345", "440")

        unlocked = [a for a in result if a.unlocked]
        locked = [a for a in result if not a.unlocked]

        assert len(unlocked) == 1
        assert unlocked[0].achievement_id == "ACH_01"
        assert unlocked[0].time_unlocked is not None

        assert len(locked) == 1
        assert locked[0].achievement_id == "ACH_02"

    @patch("src.api.steam.steam_get")
    def test_hidden_unlocked_reveals_description(
        self, mock_get: MagicMock
    ) -> None:
        """A hidden achievement that is unlocked should show its real
        description rather than ``"Hidden achievement."``."""
        schema = {
            "game": {
                "gameName": "Game",
                "availableGameStats": {
                    "achievements": [
                        {
                            "name": "SECRET",
                            "displayName": "Secret",
                            "description": "You found it!",
                            "hidden": 1,
                            "icon": "",
                        },
                    ]
                },
            }
        }
        player = {
            "playerstats": {
                "success": True,
                "achievements": [
                    {"apiname": "SECRET", "achieved": 1, "unlocktime": 100},
                ],
            }
        }
        mock_get.side_effect = [schema, player]
        api = SteamAchievementAPI()

        result = api.get_user_achievements_for_title("uid", "440")
        assert result[0].description == "You found it!"
        assert result[0].locked_description == ""

    @patch("src.api.steam.steam_get")
    def test_hidden_locked_suppresses_description(
        self, mock_get: MagicMock
    ) -> None:
        """A hidden achievement that is still locked should suppress its
        real description."""
        schema = {
            "game": {
                "gameName": "Game",
                "availableGameStats": {
                    "achievements": [
                        {
                            "name": "SECRET",
                            "displayName": "Secret",
                            "description": "You found it!",
                            "hidden": 1,
                            "icon": "",
                        },
                    ]
                },
            }
        }
        player = {
            "playerstats": {
                "success": True,
                "achievements": [
                    {"apiname": "SECRET", "achieved": 0, "unlocktime": 0},
                ],
            }
        }
        mock_get.side_effect = [schema, player]
        api = SteamAchievementAPI()

        result = api.get_user_achievements_for_title("uid", "440")
        assert result[0].description == ""
        assert result[0].locked_description == "Hidden achievement."

    @patch("src.api.steam.steam_get")
    def test_time_unlocked_is_iso8601(self, mock_get: MagicMock) -> None:
        """Unlock timestamps should be converted to ISO 8601 strings."""
        mock_get.side_effect = [SCHEMA_RESPONSE, PLAYER_ACHIEVEMENTS_RESPONSE]
        api = SteamAchievementAPI()

        result = api.get_user_achievements_for_title("12345", "440")

        unlocked_ach = [a for a in result if a.unlocked][0]
        assert unlocked_ach.time_unlocked is not None
        # Should contain a 'T' separating date and time (ISO 8601)
        assert "T" in unlocked_ach.time_unlocked

    @patch("src.api.steam.steam_get")
    def test_zero_unlocktime_yields_none(self, mock_get: MagicMock) -> None:
        """An ``unlocktime`` of ``0`` should map to ``time_unlocked=None``."""
        schema = {
            "game": {
                "gameName": "G",
                "availableGameStats": {
                    "achievements": [
                        {
                            "name": "A",
                            "displayName": "A",
                            "description": "",
                            "hidden": 0,
                            "icon": "",
                        },
                    ]
                },
            }
        }
        player = {
            "playerstats": {
                "success": True,
                "achievements": [
                    {"apiname": "A", "achieved": 1, "unlocktime": 0}
                ],
            }
        }
        mock_get.side_effect = [schema, player]
        api = SteamAchievementAPI()

        result = api.get_user_achievements_for_title("u", "1")
        assert result[0].unlocked is True
        assert result[0].time_unlocked is None

    @patch("src.api.steam.steam_get")
    def test_caches_user_title_achievements(self, mock_get: MagicMock) -> None:
        """A second call for the same user+title pair should use cache."""
        mock_get.side_effect = [SCHEMA_RESPONSE, PLAYER_ACHIEVEMENTS_RESPONSE]
        api = SteamAchievementAPI()

        first = api.get_user_achievements_for_title("u1", "440")
        second = api.get_user_achievements_for_title("u1", "440")

        assert first is second
        # Schema + player = 2 calls; second invocation = 0 more
        assert mock_get.call_count == 2

    @patch("src.api.steam.steam_get")
    def test_player_stats_not_success(self, mock_get: MagicMock) -> None:
        """When ``playerstats.success`` is falsy, all should be locked."""
        mock_get.side_effect = [
            SCHEMA_RESPONSE,
            {"playerstats": {"success": False}},
        ]
        api = SteamAchievementAPI()

        result = api.get_user_achievements_for_title("u", "440")
        assert all(not a.unlocked for a in result)


# ===================================================================
# SteamAchievementAPI — get_user_achievements (all titles)
# ===================================================================


class TestSteamAchievementAPIUserAll:
    """Tests for :meth:`SteamAchievementAPI.get_user_achievements`."""

    @patch("src.api.steam.steam_get")
    def test_iterates_over_owned_games(self, mock_get: MagicMock) -> None:
        """Should call the API for each owned game."""
        mock_get.side_effect = [
            # GetOwnedGames
            OWNED_GAMES_RESPONSE,
            # GetSchemaForGame for appid 440
            SCHEMA_RESPONSE,
            # GetPlayerAchievements for appid 440
            PLAYER_ACHIEVEMENTS_RESPONSE,
            # GetSchemaForGame for appid 730
            {
                "game": {
                    "gameName": "CS2",
                    "availableGameStats": {
                        "achievements": [
                            {
                                "name": "WIN",
                                "displayName": "Winner",
                                "description": "Win a round",
                                "hidden": 0,
                                "icon": "",
                            }
                        ]
                    },
                }
            },
            # GetPlayerAchievements for appid 730
            {
                "playerstats": {
                    "success": True,
                    "achievements": [
                        {"apiname": "WIN", "achieved": 1, "unlocktime": 100}
                    ],
                }
            },
        ]
        api = SteamAchievementAPI()

        result = api.get_user_achievements("12345")

        # 2 from title 440 + 1 from title 730
        assert len(result) == 3

    @patch("src.api.steam.steam_get")
    def test_skips_titles_with_no_schema(self, mock_get: MagicMock) -> None:
        """Titles that raise ``AchievementAPIError`` should be skipped."""
        mock_get.side_effect = [
            {"games": [{"appid": 440}]},
            AchievementAPIError("No stats"),
        ]
        api = SteamAchievementAPI()

        result = api.get_user_achievements("12345")
        assert result == []

    @patch("src.api.steam.steam_get")
    def test_empty_game_list(self, mock_get: MagicMock) -> None:
        """A user with no games should return an empty list."""
        mock_get.return_value = {"games": []}
        api = SteamAchievementAPI()

        result = api.get_user_achievements("12345")
        assert result == []


# ===================================================================
# SteamAchievementAPI — inherited concrete methods
# ===================================================================


class TestSteamAchievementAPIInherited:
    """Test the inherited concrete methods from :class:`AchievementAPI`."""

    @patch("src.api.steam.steam_get")
    def test_get_achievement_found(self, mock_get: MagicMock) -> None:
        """``get_achievement`` should locate by achievement ID."""
        mock_get.return_value = SCHEMA_RESPONSE
        api = SteamAchievementAPI()

        result = api.get_achievement("440", "ACH_01")
        assert result.achievement_id == "ACH_01"
        assert result.achievement_name == "First Blood"

    @patch("src.api.steam.steam_get")
    def test_get_achievement_not_found(self, mock_get: MagicMock) -> None:
        """``get_achievement`` should raise for an unknown ID."""
        mock_get.return_value = SCHEMA_RESPONSE
        api = SteamAchievementAPI()

        with pytest.raises(AchievementAPIError, match="not found"):
            api.get_achievement("440", "NOPE")

    @patch("src.api.steam.steam_get")
    def test_get_user_achievement_found(self, mock_get: MagicMock) -> None:
        """``get_user_achievement`` should locate user-specific data."""
        mock_get.side_effect = [SCHEMA_RESPONSE, PLAYER_ACHIEVEMENTS_RESPONSE]
        api = SteamAchievementAPI()

        result = api.get_user_achievement("12345", "440", "ACH_01")
        assert result.achievement_id == "ACH_01"
        assert result.unlocked is True

    @patch("src.api.steam.steam_get")
    def test_get_user_achievement_not_found(self, mock_get: MagicMock) -> None:
        """``get_user_achievement`` should raise for an unknown ID."""
        mock_get.side_effect = [SCHEMA_RESPONSE, PLAYER_ACHIEVEMENTS_RESPONSE]
        api = SteamAchievementAPI()

        with pytest.raises(AchievementAPIError, match="not found"):
            api.get_user_achievement("12345", "440", "NOPE")


# ===================================================================
# SteamAchievementAPI — internal helpers
# ===================================================================


class TestSteamAchievementAPIInternals:
    """Tests for private helper methods."""

    @patch("src.api.steam.steam_get")
    def test_schema_cache_shared(self, mock_get: MagicMock) -> None:
        """``_fetch_title_schema`` should cache per title ID and be reused
        by both ``get_title_achievements`` and
        ``get_user_achievements_for_title``."""
        mock_get.side_effect = [
            SCHEMA_RESPONSE,
            PLAYER_ACHIEVEMENTS_RESPONSE,
        ]
        api = SteamAchievementAPI()

        # First: title achievements (fetches schema)
        api.get_title_achievements("440")
        # Second: user achievements (should reuse cached schema)
        api.get_user_achievements_for_title("u1", "440")

        # Only 2 calls: schema + player achievements (not 2 schema calls)
        assert mock_get.call_count == 2

    def test_constructor_defaults(self) -> None:
        """Default constructor should have ``None`` steam_id and empty caches."""
        api = SteamAchievementAPI()
        assert api.steam_id is None
        assert api._schema_cache == {}
        assert api._cache == {}
        assert api.game_name is None

    def test_constructor_with_steam_id(self) -> None:
        """Constructor should store the supplied steam_id."""
        api = SteamAchievementAPI(steam_id="76561198000000000")
        assert api.steam_id == "76561198000000000"


# ===================================================================
# SteamProfileAPI — resolve_vanity_url
# ===================================================================


class TestSteamProfileAPIVanity:
    """Tests for :meth:`SteamProfileAPI.resolve_vanity_url`."""

    @patch("src.api.steam.steam_get")
    def test_successful_resolution(self, mock_get: MagicMock) -> None:
        """Should return the Steam ID on success."""
        mock_get.return_value = {
            "success": 1,
            "steamid": "76561198000000000",
        }
        api = SteamProfileAPI()

        result = api.resolve_vanity_url("myvanity")
        assert result == "76561198000000000"

    @patch("src.api.steam.steam_get")
    def test_failed_resolution(self, mock_get: MagicMock) -> None:
        """Should raise ``ProfileAPIError`` when the name cannot be resolved."""
        mock_get.return_value = {"success": 42}
        api = SteamProfileAPI()

        with pytest.raises(ProfileAPIError, match="Could not resolve"):
            api.resolve_vanity_url("badname")

    @patch("src.api.steam.steam_get")
    def test_empty_steamid_raises(self, mock_get: MagicMock) -> None:
        """Should raise when the API returns success but an empty steamid."""
        mock_get.return_value = {"success": 1, "steamid": ""}
        api = SteamProfileAPI()

        with pytest.raises(ProfileAPIError, match="No Steam ID"):
            api.resolve_vanity_url("weirdcase")

    @patch("src.api.steam.steam_get")
    def test_api_error_wraps_into_profile_error(
        self, mock_get: MagicMock
    ) -> None:
        """``AchievementAPIError`` from ``steam_get`` should become
        ``ProfileAPIError``."""
        mock_get.side_effect = AchievementAPIError("boom")
        api = SteamProfileAPI()

        with pytest.raises(ProfileAPIError, match="Failed to resolve"):
            api.resolve_vanity_url("whatever")

    @patch("src.api.steam.steam_get")
    def test_strips_whitespace_from_steamid(self, mock_get: MagicMock) -> None:
        """Leading/trailing whitespace in the returned steamid should be stripped."""
        mock_get.return_value = {
            "success": 1,
            "steamid": "  76561198000000000  ",
        }
        api = SteamProfileAPI()
        result = api.resolve_vanity_url("spacey")
        assert result == "76561198000000000"


# ===================================================================
# SteamProfileAPI — get_user_profile
# ===================================================================


class TestSteamProfileAPIGetUserProfile:
    """Tests for :meth:`SteamProfileAPI.get_user_profile`."""

    @patch("src.api.steam.steam_get")
    def test_returns_profile(self, mock_get: MagicMock) -> None:
        """Should return a ``Profile`` with the correct fields."""
        mock_get.return_value = {
            "players": [
                {
                    "personaname": "GamerBob",
                    "avatarfull": "https://cdn.example.com/avatar.jpg",
                }
            ]
        }
        api = SteamProfileAPI()

        profile = api.get_user_profile("76561198000000000")

        assert profile.name == "GamerBob"
        assert profile.platform_id == PLATFORM_STEAM
        # image_url goes through get_image_path mock
        assert profile.image_url is not None

    @patch("src.api.steam.steam_get")
    def test_no_players_raises(self, mock_get: MagicMock) -> None:
        """Should raise ``ProfileAPIError`` when no player is found."""
        mock_get.return_value = {"players": []}
        api = SteamProfileAPI()

        with pytest.raises(ProfileAPIError, match="No Steam player"):
            api.get_user_profile("0000")

    @patch("src.api.steam.steam_get")
    def test_api_error_wraps_into_profile_error(
        self, mock_get: MagicMock
    ) -> None:
        """``AchievementAPIError`` from ``steam_get`` should become
        ``ProfileAPIError``."""
        mock_get.side_effect = AchievementAPIError("network error")
        api = SteamProfileAPI()

        with pytest.raises(ProfileAPIError, match="Failed to fetch"):
            api.get_user_profile("12345")

    @patch("src.api.steam.steam_get")
    def test_empty_avatar_url(self, mock_get: MagicMock) -> None:
        """An empty ``avatarfull`` should yield an empty ``image_url``."""
        mock_get.return_value = {
            "players": [{"personaname": "NoAvatar", "avatarfull": ""}]
        }
        api = SteamProfileAPI()

        profile = api.get_user_profile("12345")
        assert profile.name == "NoAvatar"
        # Empty avatar should not be passed to get_image_path
        assert profile.image_url == ""

    @patch("src.api.steam.steam_get")
    def test_missing_avatarfull_key(self, mock_get: MagicMock) -> None:
        """A missing ``avatarfull`` key should yield an empty ``image_url``."""
        mock_get.return_value = {"players": [{"personaname": "Minimal"}]}
        api = SteamProfileAPI()

        profile = api.get_user_profile("12345")
        assert profile.name == "Minimal"
        assert profile.image_url == ""
