"""UserTitle model tracking per-user game title progress."""

from . import db
from ..api.platform import PLATFORM_XBOX, PLATFORM_STEAM

_PLATFORM_SLUGS: dict[int, str] = {
    PLATFORM_XBOX: "xbox",
    PLATFORM_STEAM: "steam",
}


class UserTitle(db.Model):
    """Per-user record for a game title, tracking progress and play history.

    Each row links a :class:`~src.models.user.User` to a
    :class:`~src.models.title.Title` and stores user-specific data such
    as achievement progress and the last-played timestamp.

    The total number of achievements for a title is stored on the
    :class:`~src.models.title.Title` model itself and exposed here via
    the :pyattr:`total_achievements` proxy property.

    Convenience properties proxy through to the related ``Title`` so
    that templates can access game metadata directly (e.g.
    ``user_title.name``, ``user_title.platform``).

    Attributes:
        id: Primary key.
        user_id: Foreign key to ``users.id``.
        title_id: Foreign key to ``titles.id``.
        current_achievements: Number of achievements the user has unlocked
            for this title.  ``None`` when achievement data is unavailable.
        progress_percentage: Completion percentage (0–100).  ``None`` when
            achievement data is unavailable.
        last_played: ISO-8601 timestamp of the user's last play session,
            or an empty string / ``None`` if unknown.
    """

    __tablename__ = "user_titles"

    id: int = db.Column(db.Integer, primary_key=True)
    user_id: int = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    title_id: int = db.Column(
        db.Integer, db.ForeignKey("titles.id"), nullable=False
    )
    current_achievements: int | None = db.Column(db.Integer, default=None)
    progress_percentage: int | None = db.Column(db.Integer, default=None)
    last_played: str | None = db.Column(db.String, default=None)

    user = db.relationship(
        "User",
        backref=db.backref("user_titles", lazy="dynamic"),
    )
    title = db.relationship(
        "Title",
        backref=db.backref("user_titles", lazy="dynamic"),
    )

    __table_args__ = (
        db.UniqueConstraint("user_id", "title_id", name="uq_user_title"),
    )

    # ------------------------------------------------------------------
    # Template-compatible convenience properties
    # ------------------------------------------------------------------

    @property
    def total_achievements(self) -> int:
        """Total achievement count, proxied from the related Title."""
        return self.title.total_achievements

    @property
    def platform(self) -> str:
        """Platform slug for URL generation (e.g. ``'xbox'``, ``'steam'``)."""
        return _PLATFORM_SLUGS.get(self.title.platform, "unknown")

    @property
    def platform_title_id(self) -> str:
        """Platform-specific title identifier string."""
        return self.title.platform_title_id

    @property
    def name(self) -> str:
        """Title display name."""
        return self.title.name

    @property
    def image_url(self) -> str | None:
        """Title cover / header image URL."""
        return self.title.image_url

    @property
    def media_type(self) -> str:
        """Platform media-type string (e.g. ``'Xbox360Game'``)."""
        return self.title.media_type or ""

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return (
            f"<UserTitle user_id={self.user_id} "
            f"title={self.title.name!r} "
            f"progress={self.current_achievements}/{self.total_achievements}>"
        )
