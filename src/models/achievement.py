"""Achievement model storing canonical achievement definitions."""

from __future__ import annotations

from . import db
from ..api.platform import PLATFORM_STEAM, PLATFORM_XBOX

_PLATFORM_SLUG_MAP: dict[int, str] = {
    PLATFORM_XBOX: "xbox",
    PLATFORM_STEAM: "steam",
}


class Achievement(db.Model):
    """Canonical achievement definition synced from platform APIs.

    Each row represents a single achievement for a specific game on a
    specific platform.  Platform-specific metadata (platform ID, native
    title ID, and game name) is accessed via the related
    :class:`~src.models.title.Title` record rather than stored directly
    on this model.
    """

    __tablename__ = "achievements"

    id: int = db.Column(db.Integer, primary_key=True)
    achievement_id: str = db.Column(db.String, nullable=False)
    title_id: int = db.Column(
        db.Integer, db.ForeignKey("titles.id"), nullable=False
    )
    achievement_name: str = db.Column(db.String, nullable=False)
    description: str | None = db.Column(db.Text, default=None)
    locked_description: str | None = db.Column(db.Text, default=None)
    gamerscore: int | None = db.Column(db.Integer, default=None)
    rarity: float | None = db.Column(db.Float, default=None)
    image_url: str | None = db.Column(db.String, default=None)

    title = db.relationship("Title", back_populates="achievements")

    __table_args__ = (
        db.UniqueConstraint(
            "title_id",
            "achievement_id",
            name="uq_achievement_identity",
        ),
    )

    # ------------------------------------------------------------------
    # Convenience properties proxying through the ``title`` relationship
    # ------------------------------------------------------------------

    @property
    def platform_id(self) -> int | None:
        """Return the platform integer from the related title."""
        if self.title is None:
            return None
        return self.title.platform

    @property
    def platform_title_id(self) -> str | None:
        """Return the platform-native title identifier from the related title."""
        if self.title is None:
            return None
        return self.title.platform_title_id

    @property
    def game_name(self) -> str | None:
        """Return the game name from the related title."""
        if self.title is None:
            return None
        return self.title.name

    @property
    def platform(self) -> str:
        """Return a human-readable platform slug (e.g. ``"xbox"``, ``"steam"``)."""
        pid = self.platform_id
        if pid is None:
            return "unknown"
        return _PLATFORM_SLUG_MAP.get(pid, "unknown")

    # ------------------------------------------------------------------
    # Template-friendly aliases
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
