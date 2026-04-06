from . import db


class Achievement(db.Model):
    __tablename__ = "achievements"

    id = db.Column(db.Integer, primary_key=True)
    platform_id = db.Column(db.Integer, nullable=False)
    title_id = db.Column(db.String, nullable=False)
    achievement_id = db.Column(db.String, nullable=False)
    game_name = db.Column(db.String, nullable=False)
    achievement_name = db.Column(db.String, nullable=False)
    description = db.Column(db.Text, default=None)
    locked_description = db.Column(db.Text, default=None)
    gamerscore = db.Column(db.Integer, default=None)
    rarity = db.Column(db.Float, default=None)
    image_url = db.Column(db.String, default=None)

    __table_args__ = (
        db.UniqueConstraint(
            "platform_id", "title_id", "achievement_id",
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
