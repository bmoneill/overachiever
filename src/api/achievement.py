from abc import ABC, abstractmethod

from .platform import PLATFORM_PSN, PLATFORM_XBOX, PLATFORM_STEAM

class Achievement:
    """Platform-agnostic representation of a single achievement."""

    def __init__(
        self,
        platform_id: int,
        achievement_id: int | str,
        title_id: int,
        name: str,
        description: str,
        image_url: str = "",
        unlocked: bool = False,
        locked_description: str = "",
        time_unlocked: str | None = None,
        gamerscore: int | None = None,
        rarity_percentage: float | None = None,
    ):
        self.platform_id = platform_id
        self.achievement_id = achievement_id
        self.title_id = title_id
        self.name = name
        self.description = description
        self.image_url = image_url
        self.unlocked = unlocked
        self.locked_description = locked_description
        self.time_unlocked = time_unlocked
        self.gamerscore = gamerscore
        self.rarity_percentage = rarity_percentage


class AchievementAPIError(Exception):
    """Raised when a platform API request fails."""

    pass


class AchievementAPI(ABC):
    """Abstract base class for platform-specific achievement APIs."""

    @abstractmethod
    def get_user_achievements(self, user_id: str) -> list[Achievement]:
        """Return every achievement for games the user has played or owns, regardless of progress."""
        ...

    @abstractmethod
    def get_title_achievements(self, title_id: str) -> list[Achievement]:
        """Return all achievements for the given title ID."""
        ...

    @abstractmethod
    def get_user_achievements_for_title(self, user_id: str, title_id: str) -> list[Achievement]:
        """Return user achievements for the given title ID (including progress)."""
        ...

    @abstractmethod
    def get_achievement(self, title_id: str, achievement_id: str) -> Achievement:
        """Return the achievement for the given title and achievement ID."""
        ...

    @abstractmethod
    def get_user_achievement(self, user_id: str, title_id: str, achievement_id: str) -> Achievement:
        """Return the user's achievement for the given title and achievement ID (including progress)."""
        ...


    def get_unlocked_user_achievements(self, user_id: str) -> list[Achievement]:
        """Return only achievements the player has unlocked across all titles."""
        return [a for a in self.get_user_achievements(user_id) if a.unlocked]

    def get_locked_user_achievements(self, user_id: str) -> list[Achievement]:
        """Return only achievements the player has *not* unlocked across all titles."""
        return [a for a in self.get_user_achievements(user_id) if not a.unlocked]

    def get_unlocked_title_achievements(self, user_id: str, title_id: str) -> list[Achievement]:
        """Return only achievements the player has unlocked for the given title."""
        return [a for a in self.get_user_achievements_for_title(user_id, title_id) if a.unlocked]

    def get_locked_title_achievements(self, user_id: str, title_id: str) -> list[Achievement]:
        """Return only achievements the player has *not* unlocked for the given title."""
        return [a for a in self.get_user_achievements_for_title(user_id, title_id) if not a.unlocked]
