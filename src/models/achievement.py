"""Achievement model storing canonical achievement definitions."""

from . import db


class Achievement(db.Model):
    """Canonical achievement definition synced from platform APIs.

    Each row represents a single achievement for a specific game on a
    specific platform.  The ``platform_title_id`` column holds the
    platform-native identifier (e.g. an Xbox title ID or a Steam app ID),
    while ``title_id`` is a foreign key linking to the local
    :class:`~src.models.title.Title` record.
    """

    __tablename__ = "achievements"

    id: int = db.Column(db.Integer, primary_key=True)
    platform_id: int = db.Column(db.Integer, nullable=False)
    platform_title_id: str = db.Column(db.String, nullable=False)
    achievement_id: str = db.Column(db.String, nullable=False)
    title_id: int | None = db.Column(
        db.Integer, db.ForeignKey("titles.id"), nullable=True
    )
    game_name: str = db.Column(db.String, nullable=False)
    achievement_name: str = db.Column(db.String, nullable=False)
    description: str | None = db.Column(db.Text, default=None)
    locked_description: str | None = db.Column(db.Text, default=None)
    gamerscore: int | None = db.Column(db.Integer, default=None)
    rarity: float | None = db.Column(db.Float, default=None)
    image_url: str | None = db.Column(db.String, default=None)

    title = db.relationship("Title", back_populates="achievements")

    __table_args__ = (
        db.UniqueConstraint(
            "platform_id",
            "platform_title_id",
            "achievement_id",
            name="uq_achievement_identity",
        ),
    )

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
