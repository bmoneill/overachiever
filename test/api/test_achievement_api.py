"""Tests for :mod:`src.api.achievement_api`.

Covers the :class:`AchievementData` dataclass (default values, property
aliases) and the concrete helper methods on the :class:`AchievementAPI`
abstract base class via a lightweight dummy subclass.
"""

from __future__ import annotations

import pytest

from src.api.achievement_api import (
    AchievementAPI,
    AchievementAPIError,
    AchievementData,
)

# ------------------------------------------------------------------
# Dummy subclass that satisfies the ABC contract
# ------------------------------------------------------------------


class DummyAchievementAPI(AchievementAPI):
    """Minimal concrete implementation used by tests.

    Stores canned data that callers supply via the constructor so the
    abstract methods can return predictable results.
    """

    def __init__(
        self,
        user_achievements: list[AchievementData] | None = None,
        title_achievements: list[AchievementData] | None = None,
        user_title_achievements: list[AchievementData] | None = None,
    ) -> None:
        self._user_achievements = user_achievements or []
        self._title_achievements = title_achievements or []
        self._user_title_achievements = user_title_achievements or []

    def get_user_achievements(self, user_id: str) -> list[AchievementData]:
        """Return canned user achievements."""
        return self._user_achievements

    def get_title_achievements(self, title_id: str) -> list[AchievementData]:
        """Return canned title achievements."""
        return self._title_achievements

    def get_user_achievements_for_title(
        self, user_id: str, title_id: str
    ) -> list[AchievementData]:
        """Return canned user-title achievements."""
        return self._user_title_achievements


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

SAMPLE_ACHIEVEMENTS = [
    AchievementData(
        platform_id=1,
        platform_title_id="100",
        achievement_id="ach_1",
        game_name="Test Game",
        achievement_name="First Blood",
        description="Get your first kill",
        gamerscore=10,
        rarity=45.5,
        unlocked=True,
        time_unlocked="2024-01-15T12:00:00Z",
    ),
    AchievementData(
        platform_id=1,
        platform_title_id="100",
        achievement_id="ach_2",
        game_name="Test Game",
        achievement_name="Completionist",
        description="Unlock everything",
        gamerscore=50,
        rarity=2.3,
        unlocked=False,
    ),
    AchievementData(
        platform_id=1,
        platform_title_id="100",
        achievement_id="ach_3",
        game_name="Test Game",
        achievement_name="Explorer",
        description="Visit every area",
        gamerscore=25,
        rarity=18.0,
        unlocked=True,
        time_unlocked="2024-02-01T08:30:00Z",
    ),
]


# ===================================================================
# AchievementData tests
# ===================================================================


class TestAchievementData:
    """Tests for the :class:`AchievementData` dataclass."""

    def test_defaults(self) -> None:
        """All fields should have sensible defaults."""
        ach = AchievementData()
        assert ach.platform_id == 0
        assert ach.platform_title_id == ""
        assert ach.achievement_id == ""
        assert ach.game_name == ""
        assert ach.achievement_name == ""
        assert ach.description is None
        assert ach.locked_description is None
        assert ach.gamerscore is None
        assert ach.rarity is None
        assert ach.image_url is None
        assert ach.unlocked is False
        assert ach.time_unlocked is None

    def test_custom_values(self) -> None:
        """Fields accept explicit values."""
        ach = AchievementData(
            platform_id=2,
            platform_title_id="440",
            achievement_id="tf2_ach_1",
            game_name="Team Fortress 2",
            achievement_name="Head of the Class",
            description="Play a complete round with every class.",
            locked_description="Hidden achievement.",
            gamerscore=None,
            rarity=33.3,
            image_url="https://example.com/icon.png",
            unlocked=True,
            time_unlocked="2024-06-01T00:00:00Z",
        )
        assert ach.platform_id == 2
        assert ach.platform_title_id == "440"
        assert ach.achievement_name == "Head of the Class"
        assert ach.unlocked is True
        assert ach.time_unlocked == "2024-06-01T00:00:00Z"

    # -- Property aliases -------------------------------------------

    def test_name_property_reads_achievement_name(self) -> None:
        """``name`` should proxy ``achievement_name``."""
        ach = AchievementData(achievement_name="Test Name")
        assert ach.name == "Test Name"

    def test_name_setter_updates_achievement_name(self) -> None:
        """Setting ``name`` should update ``achievement_name``."""
        ach = AchievementData(achievement_name="Old")
        ach.name = "New"
        assert ach.achievement_name == "New"
        assert ach.name == "New"

    def test_rarity_percentage_reads_rarity(self) -> None:
        """``rarity_percentage`` should proxy ``rarity``."""
        ach = AchievementData(rarity=12.5)
        assert ach.rarity_percentage == 12.5

    def test_rarity_percentage_setter_updates_rarity(self) -> None:
        """Setting ``rarity_percentage`` should update ``rarity``."""
        ach = AchievementData(rarity=10.0)
        ach.rarity_percentage = 99.9
        assert ach.rarity == 99.9

    def test_rarity_percentage_none(self) -> None:
        """``rarity_percentage`` should return ``None`` when rarity is ``None``."""
        ach = AchievementData()
        assert ach.rarity_percentage is None
        ach.rarity_percentage = None
        assert ach.rarity is None


# ===================================================================
# AchievementAPI concrete-method tests (via DummyAchievementAPI)
# ===================================================================


class TestAchievementAPIGetAchievement:
    """Tests for :meth:`AchievementAPI.get_achievement`."""

    def test_found(self) -> None:
        """Should return the matching achievement by ID."""
        api = DummyAchievementAPI(title_achievements=SAMPLE_ACHIEVEMENTS)
        result = api.get_achievement("100", "ach_2")
        assert result.achievement_id == "ach_2"
        assert result.achievement_name == "Completionist"

    def test_not_found_raises(self) -> None:
        """Should raise ``AchievementAPIError`` when the ID is missing."""
        api = DummyAchievementAPI(title_achievements=SAMPLE_ACHIEVEMENTS)
        with pytest.raises(AchievementAPIError, match="not found"):
            api.get_achievement("100", "nonexistent")

    def test_string_coercion(self) -> None:
        """Integer achievement IDs should be coerced to string for comparison."""
        ach = AchievementData(achievement_id="42", achievement_name="Num")
        api = DummyAchievementAPI(title_achievements=[ach])
        result = api.get_achievement("100", 42)
        assert result.achievement_name == "Num"


class TestAchievementAPIGetUserAchievement:
    """Tests for :meth:`AchievementAPI.get_user_achievement`."""

    def test_found(self) -> None:
        """Should return the matching user achievement."""
        api = DummyAchievementAPI(user_title_achievements=SAMPLE_ACHIEVEMENTS)
        result = api.get_user_achievement("user1", "100", "ach_1")
        assert result.achievement_id == "ach_1"

    def test_not_found_raises(self) -> None:
        """Should raise ``AchievementAPIError`` for a missing achievement."""
        api = DummyAchievementAPI(user_title_achievements=SAMPLE_ACHIEVEMENTS)
        with pytest.raises(AchievementAPIError, match="not found"):
            api.get_user_achievement("user1", "100", "missing")


class TestAchievementAPIUnlockedLocked:
    """Tests for the unlocked / locked filtering helpers."""

    def test_get_unlocked_user_achievements(self) -> None:
        """Should return only achievements with ``unlocked=True``."""
        api = DummyAchievementAPI(user_achievements=SAMPLE_ACHIEVEMENTS)
        unlocked = api.get_unlocked_user_achievements("u1")
        assert len(unlocked) == 2
        assert all(a.unlocked for a in unlocked)

    def test_get_locked_user_achievements(self) -> None:
        """Should return only achievements with ``unlocked=False``."""
        api = DummyAchievementAPI(user_achievements=SAMPLE_ACHIEVEMENTS)
        locked = api.get_locked_user_achievements("u1")
        assert len(locked) == 1
        assert not locked[0].unlocked

    def test_get_unlocked_title_achievements(self) -> None:
        """Should filter by unlocked for a specific title."""
        api = DummyAchievementAPI(user_title_achievements=SAMPLE_ACHIEVEMENTS)
        result = api.get_unlocked_title_achievements("u1", "100")
        assert len(result) == 2
        ids = {a.achievement_id for a in result}
        assert ids == {"ach_1", "ach_3"}

    def test_get_locked_title_achievements(self) -> None:
        """Should filter by locked for a specific title."""
        api = DummyAchievementAPI(user_title_achievements=SAMPLE_ACHIEVEMENTS)
        result = api.get_locked_title_achievements("u1", "100")
        assert len(result) == 1
        assert result[0].achievement_id == "ach_2"

    def test_empty_list(self) -> None:
        """All filtering helpers should return empty lists for no data."""
        api = DummyAchievementAPI()
        assert api.get_unlocked_user_achievements("u1") == []
        assert api.get_locked_user_achievements("u1") == []
        assert api.get_unlocked_title_achievements("u1", "t") == []
        assert api.get_locked_title_achievements("u1", "t") == []


class TestAchievementAPIErrorException:
    """Tests for the :class:`AchievementAPIError` exception."""

    def test_is_exception(self) -> None:
        """Should be a subclass of ``Exception``."""
        assert issubclass(AchievementAPIError, Exception)

    def test_message(self) -> None:
        """Should carry the supplied message."""
        err = AchievementAPIError("something went wrong")
        assert str(err) == "something went wrong"
