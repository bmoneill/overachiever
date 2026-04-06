"""
Guide model for the OverAchiever application, representing an achievement guide.
"""

from . import db


class Guide(db.Model):
    """
    Guide model for the OverAchiever application, representing an achievement guide.
    """
    __tablename__ = "guides"

    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String, nullable=False)
    title = db.Column(db.String, default=None)
    description = db.Column(db.Text, default=None)
    platform_id = db.Column(db.Integer, nullable=False)
    title_id = db.Column(db.String, nullable=False)
    achievement_id = db.Column(
        db.Integer, db.ForeignKey("achievements.id"), default=None
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), default=None)
    created_at = db.Column(db.String, server_default=db.func.current_timestamp())

    achievement = db.relationship("Achievement", backref=db.backref("guides", lazy="dynamic"))
    user = db.relationship("User", backref=db.backref("guides", lazy="dynamic"))

    # Convenience properties so templates can use guide.author, guide.game_name, etc.
    @property
    def author(self) -> str | None:
        """
        Returns the username of the guide's author, or None if the guide has no user.
        """
        return self.user.username if self.user else None

    @property
    def game_name(self) -> str | None:
        """
        Returns the name of the game the guide is for by traversing the achievement's
        associated title, or None if the guide has no achievement or title.
        """
        return self.achievement.title.name if self.achievement and self.achievement.title else None

    @property
    def achievement_name(self) -> str | None:
        """
        Returns the name of the achievement the guide is for, or None if the guide has no
        achievement.
        """
        return self.achievement.achievement_name if self.achievement else None

    @property
    def achievement_description(self) -> str | None:
        """
        Returns the description of the achievement the guide is for, or None if the guide has no
        achievement.
        """
        return self.achievement.description if self.achievement else None
