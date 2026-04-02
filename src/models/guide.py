from . import db


class Guide(db.Model):
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
    def author(self):
        return self.user.username if self.user else None

    @property
    def game_name(self):
        return self.achievement.game_name if self.achievement else None

    @property
    def achievement_name(self):
        return self.achievement.achievement_name if self.achievement else None

    @property
    def achievement_description(self):
        return self.achievement.description if self.achievement else None
