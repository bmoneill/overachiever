"""Abstract base class for platform-specific achievement APIs.

Also defines the :class:`AchievementData` dataclass used as a
lightweight data-transfer object between API modules and the sync layer.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


class AchievementAPIError(Exception):
    """Raised when a platform API request fails."""

    pass


@dataclass
class AchievementData:
    """Platform-agnostic achievement data returned by API modules.

    This replaces the earlier pattern of constructing transient
    :class:`~src.models.achievement.Achievement` model instances in the
    API layer.  Because the ``Achievement`` model now derives
    ``platform_id``, ``platform_title_id``, and ``game_name`` from its
    ``title`` relationship (read-only properties), it can no longer be
    used as a mutable data container.

    Attributes:
        platform_id: Numeric platform identifier
            (see :mod:`src.api.platform`).
        platform_title_id: Platform-native title identifier string
            (e.g. Xbox title ID or Steam app ID).
        achievement_id: Platform-native achievement identifier string.
        game_name: Human-readable game / title name.
        achievement_name: Human-readable achievement name.
        description: Achievement description (may be empty for hidden
            achievements that are still locked).
        locked_description: Fallback description shown while the
            achievement is locked (e.g. ``"Hidden achievement."``).
        gamerscore: Gamerscore value (Xbox) or ``None``.
        rarity: Rarity / unlock percentage, or ``None``.
        image_url: URL to the achievement icon, or ``None``.
        unlocked: Whether the current user has unlocked this achievement.
        time_unlocked: ISO-8601 timestamp of when the achievement was
            unlocked, or ``None``.
    """

    platform_id: int = 0
    platform_title_id: str = ""
    achievement_id: str = ""
    game_name: str = ""
    achievement_name: str = ""
    description: str | None = None
    locked_description: str | None = None
    gamerscore: int | None = None
    rarity: float | None = None
    image_url: str | None = None
    unlocked: bool = False
    time_unlocked: str | None = None

    # ------------------------------------------------------------------
    # Template-friendly aliases (mirror the Achievement model interface)
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Alias for ``achievement_name``, used by templates."""
        return self.achievement_name

    @name.setter
    def name(self, value: str) -> None:
        self.achievement_name = value

    @property
    def rarity_percentage(self) -> float | None:
        """Alias for ``rarity``, used by templates."""
        return self.rarity

    @rarity_percentage.setter
    def rarity_percentage(self, value: float | None) -> None:
        self.rarity = value


class AchievementAPI(ABC):
    """Abstract base class for platform-specific achievement APIs."""

    @abstractmethod
    def get_user_achievements(self, user_id: str) -> list[AchievementData]:
        """Return every achievement for games the user has played or owns,
        regardless of progress."""
        ...

    @abstractmethod
    def get_title_achievements(self, title_id: str) -> list[AchievementData]:
        """Return all achievements for the given title ID."""
        ...

    @abstractmethod
    def get_user_achievements_for_title(
        self, user_id: str, title_id: str
    ) -> list[AchievementData]:
        """Return user achievements for the given title ID (including
        progress)."""
        ...

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
        """Return a single user achievement by title and achievement ID.

        Raises :class:`AchievementAPIError` if not found.
        """
        for a in self.get_user_achievements_for_title(user_id, title_id):
            if str(a.achievement_id) == str(achievement_id):
                return a
        raise AchievementAPIError(
            f"Achievement {achievement_id} not found for user {user_id} "
            f"in title {title_id}."
        )

    def get_unlocked_user_achievements(
        self, user_id: str
    ) -> list[AchievementData]:
        """Return only achievements the player has unlocked across all
        titles."""
        return [a for a in self.get_user_achievements(user_id) if a.unlocked]

    def get_locked_user_achievements(
        self, user_id: str
    ) -> list[AchievementData]:
        """Return only achievements the player has *not* unlocked across all
        titles."""
        return [
            a for a in self.get_user_achievements(user_id) if not a.unlocked
        ]

    def get_unlocked_title_achievements(
        self, user_id: str, title_id: str
    ) -> list[AchievementData]:
        """Return only achievements the player has unlocked for the given
        title."""
        return [
            a
            for a in self.get_user_achievements_for_title(user_id, title_id)
            if a.unlocked
        ]

    def get_locked_title_achievements(
        self, user_id: str, title_id: str
    ) -> list[AchievementData]:
        """Return only achievements the player has *not* unlocked for the
        given title."""
        return [
            a
            for a in self.get_user_achievements_for_title(user_id, title_id)
            if not a.unlocked
        ]
