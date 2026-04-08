"""Tests for :mod:`src.api.xbox`.

Covers :func:`_normalize_x360_achievement` (Xbox 360 achievement dict
normalisation), :func:`xbl_get` (authenticated requests, error handling,
content unwrapping), :class:`XboxAchievementAPI` (achievement fetching,
caching, Xbox 360 normalisation, inherited concrete methods), and
:class:`XboxProfileAPI` (gamertag lookup, profile fetching).

All HTTP calls are mocked — no real network traffic is produced.
"""

from __future__ import annotations

from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.api.achievement_api import AchievementAPIError, AchievementData
from src.api.profile import ProfileAPIError
from src.api.xbox import (
    XboxAchievementAPI,
    XboxProfileAPI,
    _normalize_x360_achievement,
    xbl_get,
)
from src.helpers.platform import PLATFORM_XBOX

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


# ------------------------------------------------------------------
# Sample payloads reused across tests
# ------------------------------------------------------------------

SAMPLE_MODERN_ACHIEVEMENTS = {
    "achievements": [
        {
            "id": "1",
            "name": "First Blood",
            "description": "Get your first kill",
            "lockedDescription": "Keep playing.",
            "progressState": "Achieved",
            "mediaAssets": [{"url": "https://img.example.com/ach1.png"}],
            "rewards": [{"value": "10"}],
            "rarity": {"currentPercentage": 45.5},
            "progression": {"timeUnlocked": "2024-01-15T12:00:00Z"},
            "titleAssociations": [{"name": "Test Game"}],
        },
        {
            "id": "2",
            "name": "Completionist",
            "description": "Unlock everything",
            "lockedDescription": "You have more to do.",
            "progressState": "NotStarted",
            "mediaAssets": [{"url": "https://img.example.com/ach2.png"}],
            "rewards": [{"value": "50"}],
            "rarity": {"currentPercentage": 2.3},
            "progression": {},
            "titleAssociations": [{"name": "Test Game"}],
        },
    ]
}

SAMPLE_X360_RAW = {
    "achievements": [
        {
            "id": "10",
            "name": "Old School",
            "description": "Win a round on the classic map",
            "lockedDescription": "Hidden",
            "unlocked": True,
            "imageResolved": "https://img.example.com/x360_ach.png",
            "gamerscore": 20,
            "rarity": {"currentPercentage": 30.0},
            "titleAssociations": [{"name": "Retro Game"}],
            "timeUnlocked": "2010-05-01T00:00:00Z",
        },
        {
            "id": "11",
            "name": "Newcomer",
            "description": "Start the game",
            "lockedDescription": "",
            "unlocked": False,
            "imageResolved": "",
            "gamerscore": 5,
            "rarity": None,
            "titleAssociations": [{"name": "Retro Game"}],
        },
    ]
}

SAMPLE_TITLES_RESPONSE = {
    "titles": [
        {"titleId": 100},
        {"titleId": 200},
    ]
}

SAMPLE_ACCOUNT_RESPONSE = {
    "profileUsers": [
        {
            "settings": [
                {"id": "Gamertag", "value": "CoolGamer"},
                {
                    "id": "GameDisplayPicRaw",
                    "value": "https://img.example.com/avatar.png",
                },
            ]
        }
    ]
}


# ===================================================================
# _normalize_x360_achievement tests
# ===================================================================


class TestNormalizeX360Achievement:
    """Tests for :func:`_normalize_x360_achievement`."""

    def test_unlocked_achievement(self) -> None:
        """An unlocked Xbox 360 achievement should produce ``progressState='Achieved'``."""
        raw = SAMPLE_X360_RAW["achievements"][0]
        result = _normalize_x360_achievement(raw)

        assert result["id"] == "10"
        assert result["name"] == "Old School"
        assert result["description"] == "Win a round on the classic map"
        assert result["lockedDescription"] == "Hidden"
        assert result["progressState"] == "Achieved"
        assert result["unlocked"] is True

    def test_locked_achievement(self) -> None:
        """A locked Xbox 360 achievement should produce ``progressState='NotStarted'``."""
        raw = SAMPLE_X360_RAW["achievements"][1]
        result = _normalize_x360_achievement(raw)

        assert result["progressState"] == "NotStarted"
        assert result["unlocked"] is False

    def test_media_assets_from_image_resolved(self) -> None:
        """``imageResolved`` should map to a ``mediaAssets`` list with one entry."""
        raw = SAMPLE_X360_RAW["achievements"][0]
        result = _normalize_x360_achievement(raw)

        assert len(result["mediaAssets"]) == 1
        # The URL goes through get_image_path (mocked by conftest)
        assert "url" in result["mediaAssets"][0]

    def test_empty_image_resolved_yields_empty_media_assets(self) -> None:
        """An empty ``imageResolved`` should produce an empty ``mediaAssets`` list."""
        raw = SAMPLE_X360_RAW["achievements"][1]
        result = _normalize_x360_achievement(raw)
        assert result["mediaAssets"] == []

    def test_gamerscore_in_rewards(self) -> None:
        """``gamerscore`` should map to a ``rewards`` list with a string value."""
        raw = SAMPLE_X360_RAW["achievements"][0]
        result = _normalize_x360_achievement(raw)

        assert len(result["rewards"]) == 1
        assert result["rewards"][0]["value"] == "20"

    def test_none_gamerscore_yields_empty_rewards(self) -> None:
        """A ``None`` gamerscore should produce an empty ``rewards`` list."""
        raw = {
            "id": "99",
            "name": "No GS",
            "description": "",
            "lockedDescription": "",
            "unlocked": False,
            "imageResolved": "",
            "gamerscore": None,
            "titleAssociations": [],
        }
        result = _normalize_x360_achievement(raw)
        assert result["rewards"] == []

    def test_time_unlocked_in_progression(self) -> None:
        """``timeUnlocked`` should be placed inside ``progression``."""
        raw = SAMPLE_X360_RAW["achievements"][0]
        result = _normalize_x360_achievement(raw)

        assert result["progression"]["timeUnlocked"] == "2010-05-01T00:00:00Z"

    def test_no_time_unlocked_empty_progression(self) -> None:
        """When there is no ``timeUnlocked``, progression should be empty."""
        raw = SAMPLE_X360_RAW["achievements"][1]
        result = _normalize_x360_achievement(raw)
        assert result["progression"] == {}

    def test_rarity_passed_through(self) -> None:
        """``rarity`` should be passed through unchanged."""
        raw = SAMPLE_X360_RAW["achievements"][0]
        result = _normalize_x360_achievement(raw)
        assert result["rarity"] == {"currentPercentage": 30.0}

    def test_title_associations_passed_through(self) -> None:
        """``titleAssociations`` should be passed through unchanged."""
        raw = SAMPLE_X360_RAW["achievements"][0]
        result = _normalize_x360_achievement(raw)
        assert result["titleAssociations"] == [{"name": "Retro Game"}]

    def test_missing_optional_keys(self) -> None:
        """Missing optional keys should fall back to defaults."""
        raw = {"id": "1"}
        result = _normalize_x360_achievement(raw)

        assert result["id"] == "1"
        assert result["name"] == ""
        assert result["description"] == ""
        assert result["lockedDescription"] == ""
        assert result["progressState"] == "NotStarted"
        assert result["mediaAssets"] == []
        assert result["rewards"] == []
        assert result["progression"] == {}
        assert result["unlocked"] is False


# ===================================================================
# xbl_get tests
# ===================================================================


class TestXblGet:
    """Tests for :func:`xbl_get`."""

    def test_raises_when_api_key_missing(self) -> None:
        """Should raise ``AchievementAPIError`` when no API key is set."""
        with patch("src.api.xbox.OPENXBL_API_KEY", None):
            with pytest.raises(AchievementAPIError, match="OPENXBL_API_KEY"):
                xbl_get("/v2/titles/12345")

    @patch("src.api.xbox.make_request")
    def test_returns_unwrapped_content(
        self, mock_req: MagicMock, mock_openxbl_api_key: None
    ) -> None:
        """When the JSON body has a ``content`` key, it should be unwrapped."""
        mock_req.return_value = _make_fake_response(
            200,
            {"content": {"titles": [{"titleId": 1}]}, "code": 200},
        )
        result = xbl_get("/v2/titles/12345")
        assert result == {"titles": [{"titleId": 1}]}

    @patch("src.api.xbox.make_request")
    def test_returns_raw_when_no_content_key(
        self, mock_req: MagicMock, mock_openxbl_api_key: None
    ) -> None:
        """When the JSON body lacks a ``content`` key, return it as-is."""
        mock_req.return_value = _make_fake_response(200, {"achievements": []})
        result = xbl_get("/v2/achievements/player/xuid/title")
        assert result == {"achievements": []}

    @patch("src.api.xbox.make_request")
    def test_sends_auth_header(
        self, mock_req: MagicMock, mock_openxbl_api_key: None
    ) -> None:
        """The ``X-Authorization`` header should be present."""
        mock_req.return_value = _make_fake_response(200, {})
        xbl_get("/v2/something")

        _args, kwargs = mock_req.call_args
        # headers are passed positionally or as keyword
        call_str = str(mock_req.call_args)
        assert "X-Authorization" in call_str

    @patch("src.api.xbox.make_request")
    def test_raises_on_http_error_with_response(
        self, mock_req: MagicMock, mock_openxbl_api_key: None
    ) -> None:
        """Should wrap HTTP errors into ``AchievementAPIError``."""
        mock_req.return_value = _make_fake_response(401)
        with pytest.raises(AchievementAPIError, match="status 401"):
            xbl_get("/v2/bad")

    @patch("src.api.xbox.make_request")
    def test_raises_on_connection_error(
        self, mock_req: MagicMock, mock_openxbl_api_key: None
    ) -> None:
        """Should wrap connection errors into ``AchievementAPIError``."""
        mock_req.side_effect = requests.exceptions.ConnectionError("refused")
        with pytest.raises(AchievementAPIError, match="Failed to reach"):
            xbl_get("/v2/something")

    @patch("src.api.xbox.make_request")
    def test_returns_raw_for_non_dict(
        self, mock_req: MagicMock, mock_openxbl_api_key: None
    ) -> None:
        """If the JSON body is a list or other non-dict, return it as-is."""
        mock_req.return_value = _make_fake_response(200, [1, 2, 3])
        # json() returns a list, not a dict
        mock_req.return_value.json.return_value = [1, 2, 3]
        result = xbl_get("/v2/something")
        assert result == [1, 2, 3]


# ===================================================================
# XboxAchievementAPI — constructor and helpers
# ===================================================================


class TestXboxAchievementAPIConstructor:
    """Tests for :class:`XboxAchievementAPI` constructor and ``_require_xuid``."""

    def test_defaults(self) -> None:
        """Default constructor should have ``None`` xuid and empty caches."""
        api = XboxAchievementAPI()
        assert api.xuid is None
        assert api.media_type == ""
        assert api.is_x360 is False
        assert api._cache == {}
        assert api.game_name is None

    def test_with_xuid(self) -> None:
        """Constructor should store the supplied xuid."""
        api = XboxAchievementAPI(xuid="2535428000000000")
        assert api.xuid == "2535428000000000"

    def test_x360_media_type(self) -> None:
        """Setting ``media_type`` to an X360 type should set ``is_x360`` to True."""
        api = XboxAchievementAPI(media_type="Xbox360Game")
        assert api.is_x360 is True

    def test_xbox_arcade_game_media_type(self) -> None:
        """``XboxArcadeGame`` should also be treated as X360."""
        api = XboxAchievementAPI(media_type="XboxArcadeGame")
        assert api.is_x360 is True

    def test_modern_media_type(self) -> None:
        """A modern media type should not be treated as X360."""
        api = XboxAchievementAPI(media_type="XboxOneGame")
        assert api.is_x360 is False

    def test_require_xuid_raises_when_none(self) -> None:
        """``_require_xuid`` should raise when no xuid is set."""
        api = XboxAchievementAPI()
        with pytest.raises(AchievementAPIError, match="default XUID"):
            api._require_xuid()

    def test_require_xuid_returns_xuid(self) -> None:
        """``_require_xuid`` should return the xuid when set."""
        api = XboxAchievementAPI(xuid="12345")
        assert api._require_xuid() == "12345"


# ===================================================================
# XboxAchievementAPI — modern achievements
# ===================================================================


class TestXboxAchievementAPIModern:
    """Tests for modern Xbox achievements via :class:`XboxAchievementAPI`."""

    @patch("src.api.xbox.xbl_get")
    def test_get_user_achievements_for_title(self, mock_get: MagicMock) -> None:
        """Should return ``AchievementData`` objects for each achievement."""
        mock_get.return_value = SAMPLE_MODERN_ACHIEVEMENTS
        api = XboxAchievementAPI(xuid="12345")

        result = api.get_user_achievements_for_title("12345", "100")

        assert len(result) == 2
        assert all(isinstance(a, AchievementData) for a in result)
        assert result[0].achievement_id == "1"
        assert result[0].achievement_name == "First Blood"
        assert result[0].unlocked is True
        assert result[0].time_unlocked == "2024-01-15T12:00:00Z"

        assert result[1].achievement_id == "2"
        assert result[1].unlocked is False

    @patch("src.api.xbox.xbl_get")
    def test_platform_id_is_xbox(self, mock_get: MagicMock) -> None:
        """All achievements should carry ``PLATFORM_XBOX``."""
        mock_get.return_value = SAMPLE_MODERN_ACHIEVEMENTS
        api = XboxAchievementAPI(xuid="12345")

        result = api.get_user_achievements_for_title("12345", "100")
        assert all(a.platform_id == PLATFORM_XBOX for a in result)

    @patch("src.api.xbox.xbl_get")
    def test_gamerscore_parsed(self, mock_get: MagicMock) -> None:
        """Gamerscore should be parsed as an integer from the rewards list."""
        mock_get.return_value = SAMPLE_MODERN_ACHIEVEMENTS
        api = XboxAchievementAPI(xuid="12345")

        result = api.get_user_achievements_for_title("12345", "100")
        assert result[0].gamerscore == 10
        assert result[1].gamerscore == 50

    @patch("src.api.xbox.xbl_get")
    def test_rarity_parsed(self, mock_get: MagicMock) -> None:
        """Rarity percentage should be extracted from the rarity dict."""
        mock_get.return_value = SAMPLE_MODERN_ACHIEVEMENTS
        api = XboxAchievementAPI(xuid="12345")

        result = api.get_user_achievements_for_title("12345", "100")
        assert result[0].rarity == 45.5
        assert result[1].rarity == 2.3

    @patch("src.api.xbox.xbl_get")
    def test_game_name_from_title_associations(
        self, mock_get: MagicMock
    ) -> None:
        """``game_name`` should be derived from ``titleAssociations``."""
        mock_get.return_value = SAMPLE_MODERN_ACHIEVEMENTS
        api = XboxAchievementAPI(xuid="12345")

        result = api.get_user_achievements_for_title("12345", "100")
        assert all(a.game_name == "Test Game" for a in result)

    @patch("src.api.xbox.xbl_get")
    def test_image_url_processed(self, mock_get: MagicMock) -> None:
        """Image URLs should be passed through ``get_image_path``."""
        mock_get.return_value = SAMPLE_MODERN_ACHIEVEMENTS
        api = XboxAchievementAPI(xuid="12345")

        result = api.get_user_achievements_for_title("12345", "100")
        for ach in result:
            assert ach.image_url is not None
            assert "/static/img/" in ach.image_url

    @patch("src.api.xbox.xbl_get")
    def test_caches_user_title_achievements(self, mock_get: MagicMock) -> None:
        """A second call for the same user+title pair should use the cache."""
        mock_get.return_value = SAMPLE_MODERN_ACHIEVEMENTS
        api = XboxAchievementAPI(xuid="12345")

        first = api.get_user_achievements_for_title("12345", "100")
        second = api.get_user_achievements_for_title("12345", "100")

        assert first is second
        assert mock_get.call_count == 1

    @patch("src.api.xbox.xbl_get")
    def test_no_rewards_yields_none_gamerscore(
        self, mock_get: MagicMock
    ) -> None:
        """An achievement with no rewards should have ``gamerscore=None``."""
        mock_get.return_value = {
            "achievements": [
                {
                    "id": "99",
                    "name": "Freebie",
                    "description": "No GS",
                    "lockedDescription": "",
                    "progressState": "Achieved",
                    "mediaAssets": [],
                    "rewards": [],
                    "rarity": {},
                    "progression": {},
                    "titleAssociations": [{"name": "NoGS Game"}],
                }
            ]
        }
        api = XboxAchievementAPI(xuid="12345")

        result = api.get_user_achievements_for_title("12345", "100")
        assert result[0].gamerscore is None

    @patch("src.api.xbox.xbl_get")
    def test_no_media_assets_yields_none_image(
        self, mock_get: MagicMock
    ) -> None:
        """An achievement with no media assets should have ``image_url=None``."""
        mock_get.return_value = {
            "achievements": [
                {
                    "id": "99",
                    "name": "NoImg",
                    "description": "",
                    "lockedDescription": "",
                    "progressState": "NotStarted",
                    "mediaAssets": [],
                    "rewards": [],
                    "rarity": {},
                    "progression": {},
                    "titleAssociations": [{"name": "Game"}],
                }
            ]
        }
        api = XboxAchievementAPI(xuid="12345")

        result = api.get_user_achievements_for_title("12345", "100")
        assert result[0].image_url is None

    @patch("src.api.xbox.xbl_get")
    def test_empty_achievements_list(self, mock_get: MagicMock) -> None:
        """An empty achievements list should return an empty result."""
        mock_get.return_value = {"achievements": []}
        api = XboxAchievementAPI(xuid="12345")

        result = api.get_user_achievements_for_title("12345", "100")
        assert result == []

    @patch("src.api.xbox.xbl_get")
    def test_description_none_when_empty(self, mock_get: MagicMock) -> None:
        """An empty description string should become ``None``."""
        mock_get.return_value = {
            "achievements": [
                {
                    "id": "1",
                    "name": "Test",
                    "description": "",
                    "lockedDescription": "",
                    "progressState": "NotStarted",
                    "mediaAssets": [],
                    "rewards": [],
                    "progression": {},
                    "titleAssociations": [{"name": "G"}],
                }
            ]
        }
        api = XboxAchievementAPI(xuid="12345")

        result = api.get_user_achievements_for_title("12345", "100")
        assert result[0].description is None
        assert result[0].locked_description is None


# ===================================================================
# XboxAchievementAPI — Xbox 360 achievements
# ===================================================================


class TestXboxAchievementAPIX360:
    """Tests for Xbox 360 achievement normalisation and merging."""

    @patch("src.api.xbox.xbl_get")
    def test_x360_achievements_normalised(self, mock_get: MagicMock) -> None:
        """Xbox 360 achievements should be normalised into modern schema."""
        # x360 endpoint returns player achievements; second call returns title achievements
        mock_get.side_effect = [
            SAMPLE_X360_RAW,  # /v2/achievements/x360/{xuid}/title/{tid}
            {"achievements": []},  # /v2/achievements/player/{xuid}/title/{tid}
        ]
        api = XboxAchievementAPI(xuid="12345", media_type="Xbox360Game")

        result = api.get_user_achievements_for_title("12345", "100")

        assert len(result) == 2
        # First achievement should be unlocked
        assert result[0].unlocked is True
        assert result[0].achievement_name == "Old School"
        # Second should be locked
        assert result[1].unlocked is False
        assert result[1].achievement_name == "Newcomer"

    @patch("src.api.xbox.xbl_get")
    def test_x360_merges_player_and_title(self, mock_get: MagicMock) -> None:
        """Player achievements and title achievements should be merged
        without duplicates."""
        player_achievements = {
            "achievements": [
                {
                    "id": "10",
                    "name": "Shared",
                    "description": "Player version",
                    "lockedDescription": "",
                    "unlocked": True,
                    "imageResolved": "",
                    "gamerscore": 10,
                    "titleAssociations": [{"name": "MergeGame"}],
                    "timeUnlocked": "2010-01-01T00:00:00Z",
                },
            ]
        }
        title_achievements = {
            "achievements": [
                {
                    "id": "10",
                    "name": "Shared",
                    "description": "Title version",
                    "lockedDescription": "",
                    "unlocked": False,
                    "imageResolved": "",
                    "gamerscore": 10,
                    "titleAssociations": [{"name": "MergeGame"}],
                },
                {
                    "id": "20",
                    "name": "Title Only",
                    "description": "Extra",
                    "lockedDescription": "",
                    "unlocked": False,
                    "imageResolved": "",
                    "gamerscore": 5,
                    "titleAssociations": [{"name": "MergeGame"}],
                },
            ]
        }
        mock_get.side_effect = [player_achievements, title_achievements]
        api = XboxAchievementAPI(xuid="12345", media_type="Xbox360Game")

        result = api.get_user_achievements_for_title("12345", "100")

        # Should have 2: "Shared" (from player, not title dup) + "Title Only"
        assert len(result) == 2
        ids = {a.achievement_id for a in result}
        assert ids == {"10", "20"}

    @patch("src.api.xbox.xbl_get")
    def test_x360_gamerscore_parsed(self, mock_get: MagicMock) -> None:
        """X360 gamerscore should be extracted correctly after normalisation."""
        mock_get.side_effect = [
            SAMPLE_X360_RAW,
            {"achievements": []},
        ]
        api = XboxAchievementAPI(xuid="12345", media_type="Xbox360Game")

        result = api.get_user_achievements_for_title("12345", "100")
        assert result[0].gamerscore == 20
        assert result[1].gamerscore == 5


# ===================================================================
# XboxAchievementAPI — get_title_achievements
# ===================================================================


class TestXboxAchievementAPITitle:
    """Tests for :meth:`XboxAchievementAPI.get_title_achievements`."""

    @patch("src.api.xbox.xbl_get")
    def test_returns_all_locked(self, mock_get: MagicMock) -> None:
        """Title achievements should have ``unlocked=False`` and
        ``time_unlocked=None``."""
        mock_get.return_value = SAMPLE_MODERN_ACHIEVEMENTS
        api = XboxAchievementAPI(xuid="12345")

        result = api.get_title_achievements("100")

        assert all(not a.unlocked for a in result)
        assert all(a.time_unlocked is None for a in result)

    def test_raises_without_xuid(self) -> None:
        """Should raise when no default xuid was provided."""
        api = XboxAchievementAPI()
        with pytest.raises(AchievementAPIError, match="default XUID"):
            api.get_title_achievements("100")

    @patch("src.api.xbox.xbl_get")
    def test_preserves_achievement_data(self, mock_get: MagicMock) -> None:
        """Title achievements should preserve all metadata except unlock info."""
        mock_get.return_value = SAMPLE_MODERN_ACHIEVEMENTS
        api = XboxAchievementAPI(xuid="12345")

        result = api.get_title_achievements("100")

        assert result[0].achievement_id == "1"
        assert result[0].achievement_name == "First Blood"
        assert result[0].gamerscore == 10
        assert result[0].rarity == 45.5


# ===================================================================
# XboxAchievementAPI — get_user_achievements (all titles)
# ===================================================================


class TestXboxAchievementAPIUserAll:
    """Tests for :meth:`XboxAchievementAPI.get_user_achievements`."""

    @patch("src.api.xbox.xbl_get")
    def test_iterates_over_titles(self, mock_get: MagicMock) -> None:
        """Should fetch achievements for each title the user owns."""
        mock_get.side_effect = [
            SAMPLE_TITLES_RESPONSE,  # /v2/titles/{xuid}
            SAMPLE_MODERN_ACHIEVEMENTS,  # title 100
            SAMPLE_MODERN_ACHIEVEMENTS,  # title 200
        ]
        api = XboxAchievementAPI(xuid="12345")

        result = api.get_user_achievements("12345")

        # 2 achievements per title × 2 titles = 4
        assert len(result) == 4

    @patch("src.api.xbox.xbl_get")
    def test_skips_failing_titles(self, mock_get: MagicMock) -> None:
        """Titles that raise ``AchievementAPIError`` should be skipped."""
        mock_get.side_effect = [
            {"titles": [{"titleId": 100}]},
            AchievementAPIError("No data"),
        ]
        api = XboxAchievementAPI(xuid="12345")

        result = api.get_user_achievements("12345")
        assert result == []

    @patch("src.api.xbox.xbl_get")
    def test_empty_titles(self, mock_get: MagicMock) -> None:
        """A user with no titles should return an empty list."""
        mock_get.return_value = {"titles": []}
        api = XboxAchievementAPI(xuid="12345")

        result = api.get_user_achievements("12345")
        assert result == []

    @patch("src.api.xbox.xbl_get")
    def test_non_dict_content(self, mock_get: MagicMock) -> None:
        """If the titles endpoint returns a non-dict, no titles should be
        processed."""
        mock_get.return_value = []
        api = XboxAchievementAPI(xuid="12345")

        result = api.get_user_achievements("12345")
        assert result == []


# ===================================================================
# XboxAchievementAPI — inherited concrete methods
# ===================================================================


class TestXboxAchievementAPIInherited:
    """Test the inherited concrete methods from :class:`AchievementAPI`."""

    @patch("src.api.xbox.xbl_get")
    def test_get_achievement_found(self, mock_get: MagicMock) -> None:
        """``get_achievement`` should locate by achievement ID."""
        mock_get.return_value = SAMPLE_MODERN_ACHIEVEMENTS
        api = XboxAchievementAPI(xuid="12345")

        result = api.get_achievement("100", "1")
        assert result.achievement_name == "First Blood"

    @patch("src.api.xbox.xbl_get")
    def test_get_achievement_not_found(self, mock_get: MagicMock) -> None:
        """``get_achievement`` should raise for an unknown ID."""
        mock_get.return_value = SAMPLE_MODERN_ACHIEVEMENTS
        api = XboxAchievementAPI(xuid="12345")

        with pytest.raises(AchievementAPIError, match="not found"):
            api.get_achievement("100", "nonexistent")

    @patch("src.api.xbox.xbl_get")
    def test_get_user_achievement_found(self, mock_get: MagicMock) -> None:
        """``get_user_achievement`` should locate user-specific data."""
        mock_get.return_value = SAMPLE_MODERN_ACHIEVEMENTS
        api = XboxAchievementAPI(xuid="12345")

        result = api.get_user_achievement("12345", "100", "1")
        assert result.achievement_id == "1"
        assert result.unlocked is True

    @patch("src.api.xbox.xbl_get")
    def test_get_user_achievement_not_found(self, mock_get: MagicMock) -> None:
        """``get_user_achievement`` should raise for an unknown ID."""
        mock_get.return_value = SAMPLE_MODERN_ACHIEVEMENTS
        api = XboxAchievementAPI(xuid="12345")

        with pytest.raises(AchievementAPIError, match="not found"):
            api.get_user_achievement("12345", "100", "NOPE")

    @patch("src.api.xbox.xbl_get")
    def test_get_unlocked_user_achievements(self, mock_get: MagicMock) -> None:
        """``get_unlocked_user_achievements`` should filter correctly."""
        mock_get.side_effect = [
            {"titles": [{"titleId": 100}]},
            SAMPLE_MODERN_ACHIEVEMENTS,
        ]
        api = XboxAchievementAPI(xuid="12345")

        result = api.get_unlocked_user_achievements("12345")
        assert len(result) == 1
        assert result[0].unlocked is True

    @patch("src.api.xbox.xbl_get")
    def test_get_locked_user_achievements(self, mock_get: MagicMock) -> None:
        """``get_locked_user_achievements`` should filter correctly."""
        mock_get.side_effect = [
            {"titles": [{"titleId": 100}]},
            SAMPLE_MODERN_ACHIEVEMENTS,
        ]
        api = XboxAchievementAPI(xuid="12345")

        result = api.get_locked_user_achievements("12345")
        assert len(result) == 1
        assert result[0].unlocked is False

    @patch("src.api.xbox.xbl_get")
    def test_get_unlocked_title_achievements(self, mock_get: MagicMock) -> None:
        """``get_unlocked_title_achievements`` should filter by unlock status."""
        mock_get.return_value = SAMPLE_MODERN_ACHIEVEMENTS
        api = XboxAchievementAPI(xuid="12345")

        result = api.get_unlocked_title_achievements("12345", "100")
        assert len(result) == 1
        assert result[0].achievement_id == "1"

    @patch("src.api.xbox.xbl_get")
    def test_get_locked_title_achievements(self, mock_get: MagicMock) -> None:
        """``get_locked_title_achievements`` should filter by lock status."""
        mock_get.return_value = SAMPLE_MODERN_ACHIEVEMENTS
        api = XboxAchievementAPI(xuid="12345")

        result = api.get_locked_title_achievements("12345", "100")
        assert len(result) == 1
        assert result[0].achievement_id == "2"


# ===================================================================
# XboxProfileAPI — get_xuid_from_gamertag
# ===================================================================


class TestXboxProfileAPIGamertag:
    """Tests for :meth:`XboxProfileAPI.get_xuid_from_gamertag`."""

    @patch("src.api.xbox.xbl_get")
    def test_successful_lookup(self, mock_get: MagicMock) -> None:
        """Should return the XUID for an exact gamertag match."""
        mock_get.return_value = {
            "people": [{"gamertag": "CoolGamer", "xuid": "2535428000000000"}]
        }
        api = XboxProfileAPI()

        result = api.get_xuid_from_gamertag("CoolGamer")
        assert result == "2535428000000000"

    @patch("src.api.xbox.xbl_get")
    def test_strips_whitespace(self, mock_get: MagicMock) -> None:
        """Leading/trailing whitespace on the gamertag should be stripped."""
        mock_get.return_value = {
            "people": [{"gamertag": "CoolGamer", "xuid": "2535428000000000"}]
        }
        api = XboxProfileAPI()

        result = api.get_xuid_from_gamertag("  CoolGamer  ")
        assert result == "2535428000000000"

    @patch("src.api.xbox.xbl_get")
    def test_non_exact_match_raises(self, mock_get: MagicMock) -> None:
        """Should raise ``ProfileAPIError`` when the returned gamertag
        doesn't match exactly."""
        mock_get.return_value = {
            "people": [{"gamertag": "coolgamer", "xuid": "2535428000000000"}]
        }
        api = XboxProfileAPI()

        with pytest.raises(ProfileAPIError, match="Exact match not found"):
            api.get_xuid_from_gamertag("CoolGamer")

    @patch("src.api.xbox.xbl_get")
    def test_api_error_wraps_into_profile_error(
        self, mock_get: MagicMock
    ) -> None:
        """``AchievementAPIError`` from ``xbl_get`` should become
        ``ProfileAPIError``."""
        mock_get.side_effect = AchievementAPIError("network issue")
        api = XboxProfileAPI()

        with pytest.raises(ProfileAPIError, match="Failed to fetch"):
            api.get_xuid_from_gamertag("whoever")


# ===================================================================
# XboxProfileAPI — get_user_profile
# ===================================================================


class TestXboxProfileAPIGetUserProfile:
    """Tests for :meth:`XboxProfileAPI.get_user_profile`."""

    @patch("src.api.xbox.xbl_get")
    def test_returns_profile(self, mock_get: MagicMock) -> None:
        """Should return a ``Profile`` with the correct fields."""
        mock_get.return_value = SAMPLE_ACCOUNT_RESPONSE
        api = XboxProfileAPI()

        profile = api.get_user_profile("2535428000000000")

        assert profile.name == "CoolGamer"
        assert profile.platform_id == PLATFORM_XBOX
        assert profile.image_url is not None

    @patch("src.api.xbox.xbl_get")
    def test_api_error_wraps_into_profile_error(
        self, mock_get: MagicMock
    ) -> None:
        """``AchievementAPIError`` from ``xbl_get`` should become
        ``ProfileAPIError``."""
        mock_get.side_effect = AchievementAPIError("network error")
        api = XboxProfileAPI()

        with pytest.raises(ProfileAPIError, match="Failed to fetch"):
            api.get_user_profile("12345")

    @patch("src.api.xbox.xbl_get")
    def test_unexpected_format_raises(self, mock_get: MagicMock) -> None:
        """Unexpected response format should raise ``ProfileAPIError``."""
        mock_get.return_value = {"profileUsers": []}
        api = XboxProfileAPI()

        with pytest.raises(ProfileAPIError, match="Unexpected response"):
            api.get_user_profile("12345")

    @patch("src.api.xbox.xbl_get")
    def test_missing_gamertag_raises(self, mock_get: MagicMock) -> None:
        """A response without a ``Gamertag`` setting should raise."""
        mock_get.return_value = {
            "profileUsers": [
                {
                    "settings": [
                        {
                            "id": "GameDisplayPicRaw",
                            "value": "https://pic.example.com/a.png",
                        },
                    ]
                }
            ]
        }
        api = XboxProfileAPI()

        with pytest.raises(ProfileAPIError, match="Gamertag not found"):
            api.get_user_profile("12345")

    @patch("src.api.xbox.xbl_get")
    def test_missing_avatar_yields_empty_image_url(
        self, mock_get: MagicMock
    ) -> None:
        """A response without ``GameDisplayPicRaw`` should yield an empty
        ``image_url``."""
        mock_get.return_value = {
            "profileUsers": [
                {
                    "settings": [
                        {"id": "Gamertag", "value": "NoAvatar"},
                    ]
                }
            ]
        }
        api = XboxProfileAPI()

        profile = api.get_user_profile("12345")
        assert profile.name == "NoAvatar"
        assert profile.image_url == ""

    @patch("src.api.xbox.xbl_get")
    def test_empty_avatar_url_yields_empty_image_url(
        self, mock_get: MagicMock
    ) -> None:
        """An empty ``GameDisplayPicRaw`` value should yield an empty
        ``image_url``."""
        mock_get.return_value = {
            "profileUsers": [
                {
                    "settings": [
                        {"id": "Gamertag", "value": "Gamer"},
                        {"id": "GameDisplayPicRaw", "value": ""},
                    ]
                }
            ]
        }
        api = XboxProfileAPI()

        profile = api.get_user_profile("12345")
        assert profile.image_url == ""

    @patch("src.api.xbox.xbl_get")
    def test_profile_is_instance_check(self, mock_get: MagicMock) -> None:
        """The returned object should be a ``Profile`` instance."""
        mock_get.return_value = SAMPLE_ACCOUNT_RESPONSE
        api = XboxProfileAPI()

        from src.api.profile import Profile

        profile = api.get_user_profile("12345")
        assert isinstance(profile, Profile)
