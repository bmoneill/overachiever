"""
Provides tools for interacting with external APIs.
"""

from .achievement_api import (
    Achievement,
    AchievementAPI,
    AchievementAPIError,
)

from .platform import PLATFORM_PSN, PLATFORM_STEAM, PLATFORM_XBOX

__all__ = [
    "Achievement",
    "AchievementAPI",
    "AchievementAPIError",
    "PLATFORM_PSN",
    "PLATFORM_STEAM",
    "PLATFORM_XBOX",
]
