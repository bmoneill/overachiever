from abc import ABC, abstractmethod

class Profile:
    """Platform-agnostic representation of an external user profile."""

    def __init__(
        self,
        platform_id: int,
        name: str,
        image_url: str = "",
    ):
        self.platform_id = platform_id
        self.name = name
        self.image_url = image_url


class ProfileAPIError(Exception):
    """Raised when a platform API request fails."""

    pass


class ProfileAPI(ABC):
    """Abstract base class for platform-specific user profiles."""

    @abstractmethod
    def get_user_profile(self, user_id: str) -> Profile:
        """Return the user's profile."""
        ...
