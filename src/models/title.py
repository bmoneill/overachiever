"""Title model representing a game title on a specific platform."""

from . import db


class Title(db.Model):
    """A game title on a specific platform.

    Each title is uniquely identified by its platform and the
    platform-specific title ID (e.g. Xbox title ID or Steam app ID).

    Attributes:
        id: Primary key.
        name: Display name of the title / game.
        platform: Platform identifier (see :mod:`src.api.platform`).
        platform_title_id: The platform-specific title identifier string.
        image_url: Optional URL to the title's cover or header image.
        media_type: Platform-specific media type string
            (e.g. ``"Xbox360Game"``).  ``None`` when unknown.
        total_achievements: Total number of achievements defined for this
            title.  Populated during achievement sync.
    """

    __tablename__ = "titles"

    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(db.String, nullable=False)
    platform: int = db.Column(db.Integer, nullable=False)
    platform_title_id: str = db.Column(db.String, nullable=False)
    image_url: str | None = db.Column(db.String, nullable=True)
    media_type: str | None = db.Column(db.String, default=None)
    total_achievements: int = db.Column(db.Integer, default=0)

    achievements = db.relationship(
        "Achievement",
        back_populates="title",
        lazy="dynamic",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "platform",
            "platform_title_id",
            name="uq_title_platform_identity",
        ),
    )

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return (
            f"<Title id={self.id} name={self.name!r} "
            f"platform={self.platform} "
            f"platform_title_id={self.platform_title_id!r}>"
        )
