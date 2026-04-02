from . import db


class ShowcaseAchievement(db.Model):
    __tablename__ = "showcase_achievements"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    platform_id = db.Column(db.Integer, nullable=False)
    title_id = db.Column(db.String, nullable=False)
    achievement_id = db.Column(db.String, nullable=False)
    game_name = db.Column(db.String, default=None)
    achievement_name = db.Column(db.String, nullable=False)
    achievement_description = db.Column(db.Text, default=None)
    image_url = db.Column(db.String, default=None)
    gamerscore = db.Column(db.Integer, default=None)

    user = db.relationship("User", backref=db.backref("showcase_achievements", lazy="dynamic"))
