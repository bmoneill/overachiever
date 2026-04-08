"""Tests for :mod:`src.api.sync`.

Covers all twelve public and private functions in the synchronisation
layer:

* ``_upsert_title`` / ``_upsert_user_title`` — DB upsert helpers
* ``_sync_single_achievement`` — per-achievement upsert logic
* ``_fetch_steam_achievement_counts`` — batch Steam achievement counts
* ``_sync_xbox_games`` / ``_sync_steam_games`` — per-platform game-list sync
* ``sync_user_games`` — top-level game-sync orchestrator
* ``sync_title_achievements`` — per-title achievement sync
* ``load_title_achievements`` — DB loading helper
* ``_normalize_name`` — fuzzy name normalisation
* ``_build_steam_icon_lookup`` — Steam icon index builder
* ``resolve_xbox_icon_fallbacks`` — Xbox icon fallback resolver

All external HTTP calls are mocked.  Database tests use an in-memory
SQLite instance provided by the ``db_session`` fixture in ``conftest.py``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.api.achievement_api import AchievementAPIError, AchievementData
from src.api.sync import (
    _build_steam_icon_lookup,
    _fetch_steam_achievement_counts,
    _normalize_name,
    _sync_single_achievement,
    _sync_steam_games,
    _sync_xbox_games,
    _upsert_title,
    _upsert_user_title,
    load_title_achievements,
    resolve_xbox_icon_fallbacks,
    sync_title_achievements,
    sync_user_games,
)
from src.helpers.platform import PLATFORM_STEAM, PLATFORM_XBOX
from src.models import db as _db
from src.models.achievement import Achievement
from src.models.title import Title
from src.models.user import User
from src.models.user_achievement import UserAchievement
from src.models.user_title import UserTitle

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _create_user(
    db_session,
    username: str = "tester",
    email: str = "test@example.com",
    xuid: str | None = None,
    steam_id: str | None = None,
) -> User:
    """Insert and return a :class:`User` row."""
    user = User(
        username=username,
        email=email,
        password_hash="fakehash",
        xuid=xuid,
        steam_id=steam_id,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _create_title(
    db_session,
    platform: int = PLATFORM_XBOX,
    platform_title_id: str = "100",
    name: str = "Test Game",
    total_achievements: int = 0,
    media_type: str | None = None,
) -> Title:
    """Insert and return a :class:`Title` row."""
    title = Title(
        platform=platform,
        platform_title_id=platform_title_id,
        name=name,
        total_achievements=total_achievements,
        media_type=media_type,
    )
    db_session.add(title)
    db_session.flush()
    return title


def _create_achievement(
    db_session,
    title: Title,
    achievement_id: str = "ach_1",
    achievement_name: str = "Test Achievement",
    description: str | None = "A test achievement",
    image_url: str | None = None,
    gamerscore: int | None = None,
    rarity: float | None = None,
) -> Achievement:
    """Insert and return an :class:`Achievement` row."""
    ach = Achievement(
        achievement_id=achievement_id,
        title_id=title.id,
        achievement_name=achievement_name,
        description=description,
        image_url=image_url,
        gamerscore=gamerscore,
        rarity=rarity,
    )
    db_session.add(ach)
    db_session.flush()
    return ach


# ===================================================================
# _normalize_name
# ===================================================================


class TestNormalizeName:
    """Tests for :func:`_normalize_name`."""

    def test_lowercases(self) -> None:
        """Should lowercase the string."""
        assert _normalize_name("AbCdE") == "abcde"

    def test_strips_non_alnum(self) -> None:
        """Should strip everything that is not a-z or 0-9."""
        assert _normalize_name("Hello, World!") == "helloworld"

    def test_preserves_digits(self) -> None:
        """Digits should be preserved."""
        assert _normalize_name("Ach123") == "ach123"

    def test_empty_string(self) -> None:
        """An empty string should return an empty string."""
        assert _normalize_name("") == ""

    def test_all_special_characters(self) -> None:
        """A string with only special characters should return empty."""
        assert _normalize_name("!@#$%^&*()") == ""

    def test_spaces_removed(self) -> None:
        """Spaces should be stripped."""
        assert _normalize_name("First Blood") == "firstblood"

    def test_hyphens_and_underscores_removed(self) -> None:
        """Hyphens and underscores should be stripped."""
        assert _normalize_name("well-done_mate") == "welldonemate"

    def test_unicode_stripped(self) -> None:
        """Non-ASCII characters should be stripped."""
        assert _normalize_name("Über Cool™") == "bercool"


# ===================================================================
# _upsert_title
# ===================================================================


class TestUpsertTitle:
    """Tests for :func:`_upsert_title`."""

    def test_creates_new_title(self, db_session) -> None:
        """Should create a new ``Title`` row when none exists."""
        title = _upsert_title(
            platform=PLATFORM_XBOX,
            platform_title_id="12345",
            name="New Game",
            total_achievements=10,
        )
        db_session.commit()

        assert title.id is not None
        assert title.name == "New Game"
        assert title.platform == PLATFORM_XBOX
        assert title.platform_title_id == "12345"
        assert title.total_achievements == 10

    def test_returns_existing_title(self, db_session) -> None:
        """Should return the existing ``Title`` if one already exists for
        the same platform + platform_title_id combination."""
        existing = _create_title(
            db_session,
            platform=PLATFORM_STEAM,
            platform_title_id="440",
            name="Original Name",
        )
        db_session.commit()

        returned = _upsert_title(
            platform=PLATFORM_STEAM,
            platform_title_id="440",
            name="Updated Name",
        )
        db_session.commit()

        assert returned.id == existing.id
        # The upsert does NOT update the name on an existing title
        assert returned.name == "Original Name"

    def test_stores_media_type(self, db_session) -> None:
        """Should store the ``media_type`` on a new title."""
        title = _upsert_title(
            platform=PLATFORM_XBOX,
            platform_title_id="999",
            name="360 Game",
            media_type="Xbox360Game",
        )
        db_session.commit()

        assert title.media_type == "Xbox360Game"

    def test_none_media_type_stored_as_none(self, db_session) -> None:
        """Passing ``None`` for ``media_type`` should store ``None``."""
        title = _upsert_title(
            platform=PLATFORM_XBOX,
            platform_title_id="888",
            name="Unknown Type",
            media_type=None,
        )
        db_session.commit()

        assert title.media_type is None

    def test_different_platforms_different_titles(self, db_session) -> None:
        """The same ``platform_title_id`` on different platforms should
        create separate ``Title`` rows."""
        t1 = _upsert_title(
            platform=PLATFORM_XBOX,
            platform_title_id="100",
            name="Xbox Version",
        )
        t2 = _upsert_title(
            platform=PLATFORM_STEAM,
            platform_title_id="100",
            name="Steam Version",
        )
        db_session.commit()

        assert t1.id != t2.id
        assert t1.platform != t2.platform


# ===================================================================
# _upsert_user_title
# ===================================================================


class TestUpsertUserTitle:
    """Tests for :func:`_upsert_user_title`."""

    def test_creates_new_user_title(self, db_session) -> None:
        """Should create a new ``UserTitle`` row when none exists."""
        user = _create_user(db_session)
        title = _create_title(db_session)
        db_session.commit()

        ut = _upsert_user_title(
            user_id=user.id,
            title=title,
            current_achievements=5,
            progress_percentage=50,
            last_played="2024-06-01T00:00:00Z",
        )
        db_session.commit()

        assert ut.id is not None
        assert ut.user_id == user.id
        assert ut.title_id == title.id
        assert ut.current_achievements == 5
        assert ut.progress_percentage == 50
        assert ut.last_played == "2024-06-01T00:00:00Z"

    def test_updates_existing_user_title(self, db_session) -> None:
        """Should update an existing ``UserTitle`` rather than creating a
        duplicate."""
        user = _create_user(db_session)
        title = _create_title(db_session)
        db_session.commit()

        ut1 = _upsert_user_title(
            user_id=user.id,
            title=title,
            current_achievements=3,
            progress_percentage=30,
        )
        db_session.commit()

        ut2 = _upsert_user_title(
            user_id=user.id,
            title=title,
            current_achievements=8,
            progress_percentage=80,
            last_played="2024-07-01T00:00:00Z",
        )
        db_session.commit()

        assert ut1.id == ut2.id
        assert ut2.current_achievements == 8
        assert ut2.progress_percentage == 80
        assert ut2.last_played == "2024-07-01T00:00:00Z"

    def test_none_last_played_does_not_overwrite(self, db_session) -> None:
        """Passing ``None`` for ``last_played`` on update should not
        overwrite a previously stored value."""
        user = _create_user(db_session)
        title = _create_title(db_session)
        db_session.commit()

        _upsert_user_title(
            user_id=user.id,
            title=title,
            last_played="2024-01-01T00:00:00Z",
        )
        db_session.commit()

        ut = _upsert_user_title(
            user_id=user.id,
            title=title,
            last_played=None,
        )
        db_session.commit()

        # Because last_played was falsy, the original should be kept
        assert ut.last_played == "2024-01-01T00:00:00Z"


# ===================================================================
# _sync_single_achievement
# ===================================================================


class TestSyncSingleAchievement:
    """Tests for :func:`_sync_single_achievement`."""

    def test_creates_new_achievement_and_user_achievement(
        self, db_session
    ) -> None:
        """Should create both ``Achievement`` and ``UserAchievement`` rows
        for a newly encountered unlocked achievement."""
        user = _create_user(db_session)
        title = _create_title(db_session)
        db_session.commit()

        ach_data = AchievementData(
            platform_id=PLATFORM_XBOX,
            platform_title_id="100",
            achievement_id="ach_new",
            game_name="Test Game",
            achievement_name="New Achievement",
            description="Something new",
            gamerscore=10,
            rarity=50.0,
            unlocked=True,
            time_unlocked="2024-01-15T12:00:00Z",
        )

        _sync_single_achievement(
            db_title=title,
            platform_id=PLATFORM_XBOX,
            ach=ach_data,
            user_id=user.id,
        )
        db_session.commit()

        db_ach = Achievement.query.filter_by(achievement_id="ach_new").first()
        assert db_ach is not None
        assert db_ach.achievement_name == "New Achievement"
        assert db_ach.gamerscore == 10

        user_ach = UserAchievement.query.filter_by(
            user_id=user.id, achievement_id=db_ach.id
        ).first()
        assert user_ach is not None
        assert user_ach.time_unlocked == "2024-01-15T12:00:00Z"

    def test_creates_achievement_without_user_achievement_when_locked(
        self, db_session
    ) -> None:
        """A locked achievement should create an ``Achievement`` row but
        *not* a ``UserAchievement``."""
        user = _create_user(db_session)
        title = _create_title(db_session)
        db_session.commit()

        ach_data = AchievementData(
            platform_id=PLATFORM_XBOX,
            platform_title_id="100",
            achievement_id="ach_locked",
            achievement_name="Locked",
            unlocked=False,
        )

        _sync_single_achievement(
            db_title=title,
            platform_id=PLATFORM_XBOX,
            ach=ach_data,
            user_id=user.id,
        )
        db_session.commit()

        db_ach = Achievement.query.filter_by(
            achievement_id="ach_locked"
        ).first()
        assert db_ach is not None

        user_ach = UserAchievement.query.filter_by(
            user_id=user.id, achievement_id=db_ach.id
        ).first()
        assert user_ach is None

    def test_updates_existing_achievement(self, db_session) -> None:
        """Should update mutable fields on an existing ``Achievement`` row."""
        user = _create_user(db_session)
        title = _create_title(db_session)
        db_ach = _create_achievement(
            db_session,
            title,
            achievement_id="ach_upd",
            achievement_name="Old Name",
            description="Old desc",
            gamerscore=5,
        )
        db_session.commit()

        ach_data = AchievementData(
            platform_id=PLATFORM_XBOX,
            platform_title_id="100",
            achievement_id="ach_upd",
            achievement_name="New Name",
            description="New desc",
            gamerscore=20,
            rarity=75.0,
            unlocked=True,
            time_unlocked="2024-06-01T00:00:00Z",
        )

        _sync_single_achievement(
            db_title=title,
            platform_id=PLATFORM_XBOX,
            ach=ach_data,
            user_id=user.id,
        )
        db_session.commit()

        refreshed = _db.session.get(Achievement, db_ach.id)
        assert refreshed.achievement_name == "New Name"
        assert refreshed.description == "New desc"
        assert refreshed.gamerscore == 20
        assert refreshed.rarity == 75.0

    def test_removes_user_achievement_when_relocked(self, db_session) -> None:
        """If a previously unlocked achievement becomes locked, the
        ``UserAchievement`` row should be deleted."""
        user = _create_user(db_session)
        title = _create_title(db_session)
        db_ach = _create_achievement(
            db_session, title, achievement_id="ach_relock"
        )
        user_ach = UserAchievement(
            user_id=user.id,
            achievement_id=db_ach.id,
            time_unlocked="2024-01-01T00:00:00Z",
        )
        db_session.add(user_ach)
        db_session.commit()

        ach_data = AchievementData(
            platform_id=PLATFORM_XBOX,
            platform_title_id="100",
            achievement_id="ach_relock",
            achievement_name="Relocked",
            unlocked=False,
        )

        _sync_single_achievement(
            db_title=title,
            platform_id=PLATFORM_XBOX,
            ach=ach_data,
            user_id=user.id,
        )
        db_session.commit()

        remaining = UserAchievement.query.filter_by(
            user_id=user.id, achievement_id=db_ach.id
        ).first()
        assert remaining is None

    def test_does_not_overwrite_with_none_fields(self, db_session) -> None:
        """Fields that are ``None`` in the incoming data should not
        overwrite existing non-``None`` values."""
        user = _create_user(db_session)
        title = _create_title(db_session)
        _create_achievement(
            db_session,
            title,
            achievement_id="ach_partial",
            achievement_name="Existing",
            description="Existing desc",
            gamerscore=15,
            rarity=30.0,
            image_url="/static/img/existing.png",
        )
        db_session.commit()

        ach_data = AchievementData(
            platform_id=PLATFORM_XBOX,
            platform_title_id="100",
            achievement_id="ach_partial",
            achievement_name="Existing",
            description=None,
            gamerscore=None,
            rarity=None,
            image_url=None,
            unlocked=False,
        )

        _sync_single_achievement(
            db_title=title,
            platform_id=PLATFORM_XBOX,
            ach=ach_data,
            user_id=user.id,
        )
        db_session.commit()

        db_ach = Achievement.query.filter_by(
            achievement_id="ach_partial"
        ).first()
        # None values should NOT overwrite existing data
        assert db_ach.description == "Existing desc"
        assert db_ach.gamerscore == 15
        assert db_ach.rarity == 30.0
        assert db_ach.image_url == "/static/img/existing.png"


# ===================================================================
# _fetch_steam_achievement_counts
# ===================================================================


class TestFetchSteamAchievementCounts:
    """Tests for :func:`_fetch_steam_achievement_counts`."""

    @patch("src.api.sync.steam_get")
    def test_returns_counts(self, mock_get: MagicMock) -> None:
        """Should return a dict mapping appid -> (unlocked, total)."""
        mock_get.return_value = {
            "games": [
                {
                    "appid": 440,
                    "total_achievements": 520,
                    "achievements": [{"name": "a"}, {"name": "b"}],
                },
                {
                    "appid": 730,
                    "total_achievements": 167,
                    "achievements": [{"name": "x"}],
                },
            ]
        }

        result = _fetch_steam_achievement_counts("steam123", ["440", "730"])

        assert result["440"] == (2, 520)
        assert result["730"] == (1, 167)

    @patch("src.api.sync.steam_get")
    def test_batches_requests(self, mock_get: MagicMock) -> None:
        """Should batch appids into groups of 100."""
        mock_get.return_value = {"games": []}

        appids = [str(i) for i in range(250)]
        _fetch_steam_achievement_counts("steam123", appids)

        # 250 / 100 = 3 batches
        assert mock_get.call_count == 3

    @patch("src.api.sync.steam_get")
    def test_skips_failed_batches(self, mock_get: MagicMock) -> None:
        """Batches that raise ``AchievementAPIError`` should be skipped."""
        mock_get.side_effect = [
            AchievementAPIError("fail"),
            {
                "games": [
                    {
                        "appid": 200,
                        "total_achievements": 10,
                        "achievements": [],
                    }
                ]
            },
        ]

        appids = [str(i) for i in range(150)]
        result = _fetch_steam_achievement_counts("steam123", appids)

        assert "200" in result
        assert result["200"] == (0, 10)

    @patch("src.api.sync.steam_get")
    def test_empty_appids(self, mock_get: MagicMock) -> None:
        """An empty appids list should not make any API calls."""
        result = _fetch_steam_achievement_counts("steam123", [])

        assert result == {}
        mock_get.assert_not_called()

    @patch("src.api.sync.steam_get")
    def test_no_games_in_response(self, mock_get: MagicMock) -> None:
        """If the response has no ``games`` key the result should be empty."""
        mock_get.return_value = {}

        result = _fetch_steam_achievement_counts("steam123", ["440"])
        assert result == {}


# ===================================================================
# _sync_xbox_games
# ===================================================================


class TestSyncXboxGames:
    """Tests for :func:`_sync_xbox_games`."""

    @patch("src.api.sync.xbl_get")
    def test_creates_titles_and_user_titles(
        self, mock_get: MagicMock, db_session
    ) -> None:
        """Should upsert ``Title`` and ``UserTitle`` rows for each Xbox title."""
        mock_get.return_value = {
            "titles": [
                {
                    "titleId": 100,
                    "name": "Halo",
                    "displayImage": "https://img.example.com/halo.png",
                    "mediaItemType": "XboxOneGame",
                    "achievement": {
                        "totalAchievements": 50,
                        "currentAchievements": 20,
                        "progressPercentage": 40,
                    },
                    "titleHistory": {
                        "lastTimePlayed": "2024-06-15T20:00:00Z",
                    },
                },
            ]
        }
        user = _create_user(db_session, xuid="12345")
        db_session.commit()

        _sync_xbox_games(user)

        title = Title.query.filter_by(
            platform=PLATFORM_XBOX, platform_title_id="100"
        ).first()
        assert title is not None
        assert title.name == "Halo"
        assert title.total_achievements == 50

        ut = UserTitle.query.filter_by(
            user_id=user.id, title_id=title.id
        ).first()
        assert ut is not None
        assert ut.current_achievements == 20
        assert ut.progress_percentage == 40

    @patch("src.api.sync.xbl_get")
    def test_skips_when_no_xuid(self, mock_get: MagicMock, db_session) -> None:
        """Should return immediately when the user has no xuid."""
        user = _create_user(db_session, xuid=None)
        db_session.commit()

        _sync_xbox_games(user)

        mock_get.assert_not_called()

    @patch("src.api.sync.xbl_get")
    def test_skips_titles_without_id(
        self, mock_get: MagicMock, db_session
    ) -> None:
        """Titles with no ``titleId`` should be skipped silently."""
        mock_get.return_value = {
            "titles": [
                {
                    "name": "BadTitle",
                    "achievement": {},
                    "titleHistory": {},
                },
            ]
        }
        user = _create_user(db_session, xuid="12345")
        db_session.commit()

        _sync_xbox_games(user)

        assert Title.query.count() == 0


# ===================================================================
# _sync_steam_games
# ===================================================================


class TestSyncSteamGames:
    """Tests for :func:`_sync_steam_games`."""

    @patch("src.api.sync._fetch_steam_achievement_counts")
    @patch("src.api.sync.steam_get")
    def test_creates_titles_and_user_titles(
        self, mock_get: MagicMock, mock_counts: MagicMock, db_session
    ) -> None:
        """Should upsert ``Title`` and ``UserTitle`` rows for each Steam game."""
        mock_get.return_value = {
            "games": [
                {
                    "appid": 440,
                    "name": "Team Fortress 2",
                    "rtime_last_played": 1718000000,
                },
            ]
        }
        mock_counts.return_value = {"440": (100, 520)}

        user = _create_user(db_session, steam_id="76561198000000000")
        db_session.commit()

        _sync_steam_games(user)

        title = Title.query.filter_by(
            platform=PLATFORM_STEAM, platform_title_id="440"
        ).first()
        assert title is not None
        assert title.name == "Team Fortress 2"
        assert title.total_achievements == 520

        ut = UserTitle.query.filter_by(
            user_id=user.id, title_id=title.id
        ).first()
        assert ut is not None
        assert ut.current_achievements == 100
        assert ut.progress_percentage == 19  # round(100/520*100)

    @patch("src.api.sync.steam_get")
    def test_skips_when_no_steam_id(
        self, mock_get: MagicMock, db_session
    ) -> None:
        """Should return immediately when the user has no steam_id."""
        user = _create_user(db_session, steam_id=None)
        db_session.commit()

        _sync_steam_games(user)

        mock_get.assert_not_called()

    @patch("src.api.sync._fetch_steam_achievement_counts")
    @patch("src.api.sync.steam_get")
    def test_handles_zero_rtime_last_played(
        self, mock_get: MagicMock, mock_counts: MagicMock, db_session
    ) -> None:
        """A game with ``rtime_last_played=0`` should get an empty
        ``last_played``."""
        mock_get.return_value = {
            "games": [
                {"appid": 730, "name": "CS2", "rtime_last_played": 0},
            ]
        }
        mock_counts.return_value = {}

        user = _create_user(db_session, steam_id="76561198000000000")
        db_session.commit()

        _sync_steam_games(user)

        ut = UserTitle.query.first()
        assert ut is not None
        assert ut.last_played == ""

    @patch("src.api.sync._fetch_steam_achievement_counts")
    @patch("src.api.sync.steam_get")
    def test_handles_game_without_achievement_counts(
        self, mock_get: MagicMock, mock_counts: MagicMock, db_session
    ) -> None:
        """Games not in the achievement-count dict should have ``None``
        progress fields."""
        mock_get.return_value = {
            "games": [
                {"appid": 570, "name": "Dota 2", "rtime_last_played": 0},
            ]
        }
        mock_counts.return_value = {}

        user = _create_user(db_session, steam_id="76561198000000000")
        db_session.commit()

        _sync_steam_games(user)

        ut = UserTitle.query.first()
        assert ut is not None
        assert ut.current_achievements is None
        assert ut.progress_percentage is None


# ===================================================================
# sync_user_games
# ===================================================================


class TestSyncUserGames:
    """Tests for :func:`sync_user_games`."""

    @patch("src.api.sync._sync_steam_games")
    @patch("src.api.sync._sync_xbox_games")
    def test_calls_both_platforms(
        self,
        mock_xbox: MagicMock,
        mock_steam: MagicMock,
        db_session,
    ) -> None:
        """Should call both ``_sync_xbox_games`` and ``_sync_steam_games``
        when the user has both accounts linked."""
        user = _create_user(
            db_session, xuid="12345", steam_id="76561198000000000"
        )
        db_session.commit()

        errors = sync_user_games(user)

        mock_xbox.assert_called_once_with(user)
        mock_steam.assert_called_once_with(user)
        assert errors == []

    @patch("src.api.sync._sync_steam_games")
    @patch("src.api.sync._sync_xbox_games")
    def test_skips_xbox_when_no_xuid(
        self,
        mock_xbox: MagicMock,
        mock_steam: MagicMock,
        db_session,
    ) -> None:
        """Should skip Xbox sync when the user has no xuid."""
        user = _create_user(db_session, steam_id="76561198000000000")
        db_session.commit()

        sync_user_games(user)

        mock_xbox.assert_not_called()
        mock_steam.assert_called_once()

    @patch("src.api.sync._sync_steam_games")
    @patch("src.api.sync._sync_xbox_games")
    def test_skips_steam_when_no_steam_id(
        self,
        mock_xbox: MagicMock,
        mock_steam: MagicMock,
        db_session,
    ) -> None:
        """Should skip Steam sync when the user has no steam_id."""
        user = _create_user(db_session, xuid="12345")
        db_session.commit()

        sync_user_games(user)

        mock_xbox.assert_called_once()
        mock_steam.assert_not_called()

    @patch("src.api.sync._sync_steam_games")
    @patch("src.api.sync._sync_xbox_games")
    def test_collects_errors(
        self,
        mock_xbox: MagicMock,
        mock_steam: MagicMock,
        db_session,
    ) -> None:
        """Errors from individual platform syncs should be collected."""
        mock_xbox.side_effect = AchievementAPIError("Xbox down")
        mock_steam.side_effect = AchievementAPIError("Steam down")

        user = _create_user(
            db_session, xuid="12345", steam_id="76561198000000000"
        )
        db_session.commit()

        errors = sync_user_games(user)

        assert len(errors) == 2
        assert any("Xbox" in e for e in errors)
        assert any("Steam" in e for e in errors)

    @patch("src.api.sync._sync_steam_games")
    @patch("src.api.sync._sync_xbox_games")
    def test_updates_achievement_count(
        self,
        mock_xbox: MagicMock,
        mock_steam: MagicMock,
        db_session,
    ) -> None:
        """Should recompute the aggregate ``achievement_count`` on the user."""
        user = _create_user(
            db_session, xuid="12345", steam_id="76561198000000000"
        )
        title_a = _create_title(
            db_session, platform=PLATFORM_XBOX, platform_title_id="100"
        )
        title_b = _create_title(
            db_session, platform=PLATFORM_STEAM, platform_title_id="440"
        )

        ut_a = UserTitle(
            user_id=user.id,
            title_id=title_a.id,
            current_achievements=10,
        )
        ut_b = UserTitle(
            user_id=user.id,
            title_id=title_b.id,
            current_achievements=25,
        )
        db_session.add_all([ut_a, ut_b])
        db_session.commit()

        sync_user_games(user)

        assert user.achievement_count == 35


# ===================================================================
# sync_title_achievements
# ===================================================================


class TestSyncTitleAchievements:
    """Tests for :func:`sync_title_achievements`."""

    @patch("src.api.sync.SteamAchievementAPI")
    def test_syncs_steam_title(self, MockAPI: MagicMock, db_session) -> None:
        """Should fetch and persist Steam achievements for a title."""
        mock_api = MockAPI.return_value
        mock_api.get_user_achievements_for_title.return_value = [
            AchievementData(
                platform_id=PLATFORM_STEAM,
                platform_title_id="440",
                achievement_id="ach_s1",
                game_name="TF2",
                achievement_name="Play a Full Round",
                description="Complete one round.",
                unlocked=True,
                time_unlocked="2024-01-01T00:00:00Z",
            ),
        ]

        user = _create_user(db_session, steam_id="76561198000000000")
        db_session.commit()

        sync_title_achievements(user, PLATFORM_STEAM, "440")

        title = Title.query.filter_by(
            platform=PLATFORM_STEAM, platform_title_id="440"
        ).first()
        assert title is not None
        assert title.name == "TF2"

        db_ach = Achievement.query.filter_by(achievement_id="ach_s1").first()
        assert db_ach is not None
        assert db_ach.achievement_name == "Play a Full Round"

    @patch("src.api.sync.XboxAchievementAPI")
    def test_syncs_xbox_title(self, MockAPI: MagicMock, db_session) -> None:
        """Should fetch and persist Xbox achievements for a title."""
        mock_api = MockAPI.return_value
        mock_api.get_user_achievements_for_title.return_value = [
            AchievementData(
                platform_id=PLATFORM_XBOX,
                platform_title_id="100",
                achievement_id="ach_x1",
                game_name="Halo",
                achievement_name="Spartan",
                description="Finish the campaign.",
                gamerscore=50,
                unlocked=False,
            ),
        ]

        user = _create_user(db_session, xuid="12345")
        db_session.commit()

        sync_title_achievements(user, PLATFORM_XBOX, "100")

        title = Title.query.filter_by(
            platform=PLATFORM_XBOX, platform_title_id="100"
        ).first()
        assert title is not None

        db_ach = Achievement.query.filter_by(achievement_id="ach_x1").first()
        assert db_ach is not None

    def test_raises_for_unsupported_platform(self, db_session) -> None:
        """Should raise ``AchievementAPIError`` for unknown platform IDs."""
        user = _create_user(db_session)
        db_session.commit()

        with pytest.raises(AchievementAPIError, match="Unsupported platform"):
            sync_title_achievements(user, 99, "100")

    def test_raises_when_no_xbox_account(self, db_session) -> None:
        """Should raise when the user has no linked Xbox account."""
        user = _create_user(db_session, xuid=None)
        db_session.commit()

        with pytest.raises(AchievementAPIError, match="no linked Xbox"):
            sync_title_achievements(user, PLATFORM_XBOX, "100")

    def test_raises_when_no_steam_account(self, db_session) -> None:
        """Should raise when the user has no linked Steam account."""
        user = _create_user(db_session, steam_id=None)
        db_session.commit()

        with pytest.raises(AchievementAPIError, match="no linked Steam"):
            sync_title_achievements(user, PLATFORM_STEAM, "440")

    @patch("src.api.sync.SteamAchievementAPI")
    def test_empty_achievements_returns_early(
        self, MockAPI: MagicMock, db_session
    ) -> None:
        """When the API returns no achievements, no DB rows should be created."""
        mock_api = MockAPI.return_value
        mock_api.get_user_achievements_for_title.return_value = []

        user = _create_user(db_session, steam_id="76561198000000000")
        db_session.commit()

        sync_title_achievements(user, PLATFORM_STEAM, "440")

        assert Title.query.count() == 0
        assert Achievement.query.count() == 0

    @patch("src.api.sync.XboxAchievementAPI")
    def test_reads_media_type_from_existing_title(
        self, MockAPI: MagicMock, db_session
    ) -> None:
        """When ``media_type`` is not supplied, it should be read from
        an existing ``Title`` row if available."""
        _create_title(
            db_session,
            platform=PLATFORM_XBOX,
            platform_title_id="100",
            name="Halo",
            media_type="Xbox360Game",
        )
        user = _create_user(db_session, xuid="12345")
        db_session.commit()

        mock_api = MockAPI.return_value
        mock_api.get_user_achievements_for_title.return_value = [
            AchievementData(
                platform_id=PLATFORM_XBOX,
                platform_title_id="100",
                achievement_id="ach_x1",
                game_name="Halo",
                achievement_name="Spartan",
                unlocked=False,
            ),
        ]

        sync_title_achievements(user, PLATFORM_XBOX, "100")

        # Verify XboxAchievementAPI was called with the media_type read from DB
        MockAPI.assert_called_once()
        call_kwargs = MockAPI.call_args
        # media_type should be passed as a keyword argument
        assert "Xbox360Game" in str(call_kwargs)


# ===================================================================
# load_title_achievements
# ===================================================================


class TestLoadTitleAchievements:
    """Tests for :func:`load_title_achievements`."""

    def test_splits_into_unlocked_and_locked(self, db_session) -> None:
        """Should return ``(unlocked, locked)`` lists based on
        ``UserAchievement`` rows."""
        user = _create_user(db_session)
        title = _create_title(
            db_session,
            platform=PLATFORM_XBOX,
            platform_title_id="100",
        )
        ach_a = _create_achievement(
            db_session, title, achievement_id="a", achievement_name="A"
        )
        ach_b = _create_achievement(
            db_session, title, achievement_id="b", achievement_name="B"
        )
        ach_c = _create_achievement(
            db_session, title, achievement_id="c", achievement_name="C"
        )

        # User has unlocked A and C only
        db_session.add(
            UserAchievement(
                user_id=user.id,
                achievement_id=ach_a.id,
                time_unlocked="2024-01-01T00:00:00Z",
            )
        )
        db_session.add(
            UserAchievement(
                user_id=user.id,
                achievement_id=ach_c.id,
                time_unlocked="2024-02-01T00:00:00Z",
            )
        )
        db_session.commit()

        unlocked, locked = load_title_achievements(
            user.id, PLATFORM_XBOX, "100"
        )

        assert len(unlocked) == 2
        assert len(locked) == 1
        assert all(getattr(a, "unlocked", False) for a in unlocked)
        assert not getattr(locked[0], "unlocked", True)

    def test_sets_time_unlocked_attribute(self, db_session) -> None:
        """Unlocked achievements should carry a ``time_unlocked`` attribute."""
        user = _create_user(db_session)
        title = _create_title(
            db_session, platform=PLATFORM_XBOX, platform_title_id="100"
        )
        ach = _create_achievement(
            db_session, title, achievement_id="a", achievement_name="A"
        )
        db_session.add(
            UserAchievement(
                user_id=user.id,
                achievement_id=ach.id,
                time_unlocked="2024-06-15T00:00:00Z",
            )
        )
        db_session.commit()

        unlocked, _ = load_title_achievements(user.id, PLATFORM_XBOX, "100")

        assert len(unlocked) == 1
        assert getattr(unlocked[0], "time_unlocked") == "2024-06-15T00:00:00Z"

    def test_locked_have_none_time_unlocked(self, db_session) -> None:
        """Locked achievements should have ``time_unlocked=None``."""
        user = _create_user(db_session)
        title = _create_title(
            db_session, platform=PLATFORM_XBOX, platform_title_id="100"
        )
        _create_achievement(
            db_session, title, achievement_id="a", achievement_name="A"
        )
        db_session.commit()

        _, locked = load_title_achievements(user.id, PLATFORM_XBOX, "100")

        assert len(locked) == 1
        assert getattr(locked[0], "time_unlocked") is None

    def test_empty_title_returns_empty_lists(self, db_session) -> None:
        """A title with no achievements should return two empty lists."""
        user = _create_user(db_session)
        _create_title(
            db_session, platform=PLATFORM_XBOX, platform_title_id="100"
        )
        db_session.commit()

        unlocked, locked = load_title_achievements(
            user.id, PLATFORM_XBOX, "100"
        )

        assert unlocked == []
        assert locked == []

    @patch("src.api.sync.resolve_xbox_icon_fallbacks")
    def test_calls_icon_fallback_for_xbox(
        self, mock_resolve: MagicMock, db_session
    ) -> None:
        """For Xbox titles, ``resolve_xbox_icon_fallbacks`` should be called."""
        user = _create_user(db_session)
        title = _create_title(
            db_session, platform=PLATFORM_XBOX, platform_title_id="100"
        )
        _create_achievement(
            db_session, title, achievement_id="a", achievement_name="A"
        )
        db_session.commit()

        load_title_achievements(user.id, PLATFORM_XBOX, "100")

        mock_resolve.assert_called_once()

    @patch("src.api.sync.resolve_xbox_icon_fallbacks")
    def test_does_not_call_icon_fallback_for_steam(
        self, mock_resolve: MagicMock, db_session
    ) -> None:
        """For Steam titles, ``resolve_xbox_icon_fallbacks`` should NOT be called."""
        user = _create_user(db_session)
        title = _create_title(
            db_session, platform=PLATFORM_STEAM, platform_title_id="440"
        )
        _create_achievement(
            db_session, title, achievement_id="a", achievement_name="A"
        )
        db_session.commit()

        load_title_achievements(user.id, PLATFORM_STEAM, "440")

        mock_resolve.assert_not_called()


# ===================================================================
# _build_steam_icon_lookup
# ===================================================================


class TestBuildSteamIconLookup:
    """Tests for :func:`_build_steam_icon_lookup`."""

    def test_builds_lookup_from_steam_achievements(self, db_session) -> None:
        """Should index Steam achievements by normalized name."""
        title = _create_title(
            db_session,
            platform=PLATFORM_STEAM,
            platform_title_id="440",
            name="TF2",
        )
        _create_achievement(
            db_session,
            title,
            achievement_id="a",
            achievement_name="First Blood",
            image_url="/static/img/first_blood.png",
        )
        _create_achievement(
            db_session,
            title,
            achievement_id="b",
            achievement_name="Head Shot",
            image_url="/static/img/head_shot.png",
        )
        db_session.commit()

        lookup = _build_steam_icon_lookup()

        assert (
            lookup[_normalize_name("First Blood")]
            == "/static/img/first_blood.png"
        )
        assert (
            lookup[_normalize_name("Head Shot")] == "/static/img/head_shot.png"
        )

    def test_ignores_xbox_achievements(self, db_session) -> None:
        """Xbox achievements should not appear in the lookup."""
        title = _create_title(
            db_session,
            platform=PLATFORM_XBOX,
            platform_title_id="100",
            name="Halo",
        )
        _create_achievement(
            db_session,
            title,
            achievement_id="a",
            achievement_name="Xbox Only",
            image_url="/static/img/xbox.png",
        )
        db_session.commit()

        lookup = _build_steam_icon_lookup()

        assert _normalize_name("Xbox Only") not in lookup

    def test_ignores_achievements_without_image(self, db_session) -> None:
        """Achievements with ``None`` or empty image_url should be excluded."""
        title = _create_title(
            db_session,
            platform=PLATFORM_STEAM,
            platform_title_id="440",
        )
        _create_achievement(
            db_session,
            title,
            achievement_id="a",
            achievement_name="No Image",
            image_url=None,
        )
        _create_achievement(
            db_session,
            title,
            achievement_id="b",
            achievement_name="Empty Image",
            image_url="",
        )
        db_session.commit()

        lookup = _build_steam_icon_lookup()

        assert _normalize_name("No Image") not in lookup
        assert _normalize_name("Empty Image") not in lookup

    def test_first_occurrence_wins(self, db_session) -> None:
        """When multiple Steam achievements share the same normalized name,
        the first (by id) should win."""
        title = _create_title(
            db_session,
            platform=PLATFORM_STEAM,
            platform_title_id="440",
        )
        _create_achievement(
            db_session,
            title,
            achievement_id="a",
            achievement_name="Winner",
            image_url="/static/img/first.png",
        )
        _create_achievement(
            db_session,
            title,
            achievement_id="b",
            achievement_name="Winner",
            image_url="/static/img/second.png",
        )
        db_session.commit()

        lookup = _build_steam_icon_lookup()

        assert lookup[_normalize_name("Winner")] == "/static/img/first.png"

    def test_empty_database(self, db_session) -> None:
        """An empty database should return an empty lookup."""
        lookup = _build_steam_icon_lookup()
        assert lookup == {}


# ===================================================================
# resolve_xbox_icon_fallbacks
# ===================================================================


class TestResolveXboxIconFallbacks:
    """Tests for :func:`resolve_xbox_icon_fallbacks`."""

    @patch("src.api.sync._build_steam_icon_lookup")
    def test_fills_missing_xbox_icons(self, mock_lookup: MagicMock) -> None:
        """Xbox achievements missing an icon should receive a Steam fallback."""
        mock_lookup.return_value = {
            "firstblood": "/static/img/fb_steam.png",
        }

        class FakeAch:
            """Minimal object with the attributes ``resolve_xbox_icon_fallbacks``
            checks."""

            def __init__(self, platform_id, name, image_url):
                self.platform_id = platform_id
                self.achievement_name = name
                self.image_url = image_url

        xbox_ach = FakeAch(PLATFORM_XBOX, "First Blood", None)
        resolve_xbox_icon_fallbacks([xbox_ach])

        assert xbox_ach.image_url == "/static/img/fb_steam.png"

    @patch("src.api.sync._build_steam_icon_lookup")
    def test_leaves_existing_icons_alone(self, mock_lookup: MagicMock) -> None:
        """Xbox achievements that already have an icon should be untouched."""
        mock_lookup.return_value = {
            "firstblood": "/static/img/fb_steam.png",
        }

        class FakeAch:
            def __init__(self, platform_id, name, image_url):
                self.platform_id = platform_id
                self.achievement_name = name
                self.image_url = image_url

        xbox_ach = FakeAch(PLATFORM_XBOX, "First Blood", "/already/set.png")
        resolve_xbox_icon_fallbacks([xbox_ach])

        assert xbox_ach.image_url == "/already/set.png"

    @patch("src.api.sync._build_steam_icon_lookup")
    def test_ignores_non_xbox_achievements(
        self, mock_lookup: MagicMock
    ) -> None:
        """Non-Xbox achievements should be left untouched."""
        mock_lookup.return_value = {
            "firstblood": "/static/img/fb_steam.png",
        }

        class FakeAch:
            def __init__(self, platform_id, name, image_url):
                self.platform_id = platform_id
                self.achievement_name = name
                self.image_url = image_url

        steam_ach = FakeAch(PLATFORM_STEAM, "First Blood", None)
        resolve_xbox_icon_fallbacks([steam_ach])

        # Should NOT receive a fallback because it's not Xbox
        assert steam_ach.image_url is None

    @patch("src.api.sync._build_steam_icon_lookup")
    def test_no_match_leaves_none(self, mock_lookup: MagicMock) -> None:
        """If there is no Steam match, the icon should remain ``None``."""
        mock_lookup.return_value = {}

        class FakeAch:
            def __init__(self, platform_id, name, image_url):
                self.platform_id = platform_id
                self.achievement_name = name
                self.image_url = image_url

        xbox_ach = FakeAch(PLATFORM_XBOX, "Unique Name", None)
        resolve_xbox_icon_fallbacks([xbox_ach])

        assert xbox_ach.image_url is None

    def test_empty_list_is_noop(self) -> None:
        """Passing an empty list should not raise."""
        resolve_xbox_icon_fallbacks([])

    @patch("src.api.sync._build_steam_icon_lookup")
    def test_does_not_call_lookup_when_no_xbox_missing(
        self, mock_lookup: MagicMock
    ) -> None:
        """If no Xbox achievement needs an icon, the lookup should not be built."""

        class FakeAch:
            def __init__(self, platform_id, name, image_url):
                self.platform_id = platform_id
                self.achievement_name = name
                self.image_url = image_url

        # An Xbox achievement that already has an icon
        ach = FakeAch(PLATFORM_XBOX, "Test", "/some/icon.png")
        resolve_xbox_icon_fallbacks([ach])

        mock_lookup.assert_not_called()

    @patch("src.api.sync._build_steam_icon_lookup")
    def test_uses_name_alias(self, mock_lookup: MagicMock) -> None:
        """Objects using the ``name`` attribute (like ``AchievementData``)
        should also work."""
        mock_lookup.return_value = {
            "testname": "/static/img/test.png",
        }

        ach = AchievementData(
            platform_id=PLATFORM_XBOX,
            achievement_name="Test Name",
            image_url=None,
        )
        resolve_xbox_icon_fallbacks([ach])

        assert ach.image_url == "/static/img/test.png"
