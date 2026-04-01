from abc import ABC, abstractmethod

PLATFORM_PSN = 0
PLATFORM_XBOX = 1
PLATFORM_STEAM = 2


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
    """Abstract base class for platform-specific achievement APIs.

    Subclass this and implement ``get_all_achievements`` to add support
    for a new platform.  The filtered helpers (``get_unlocked_achievements``
    and ``get_locked_achievements``) work automatically once
    ``get_all_achievements`` is provided.
    """

    @abstractmethod
    def get_all_achievements(self) -> list[Achievement]:
        """Return every achievement for the configured game/player."""
        ...

    def get_unlocked_achievements(self) -> list[Achievement]:
        """Return only achievements the player has unlocked."""
        return [a for a in self.get_all_achievements() if a.unlocked]

    def get_locked_achievements(self) -> list[Achievement]:
        """Return only achievements the player has *not* unlocked."""
        return [a for a in self.get_all_achievements() if not a.unlocked]
