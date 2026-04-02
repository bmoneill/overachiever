from . import db


class ShowcaseGame(db.Model):
    __tablename__ = "showcase_games"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    platform_id = db.Column(db.Integer, nullable=False)
    title_id = db.Column(db.String, nullable=False)
    game_name = db.Column(db.String, nullable=False)
    image_url = db.Column(db.String, default=None)
    current_achievements = db.Column(db.Integer, default=0)
    total_achievements = db.Column(db.Integer, default=0)

    user = db.relationship("User", backref=db.backref("showcase_games", lazy="dynamic"))
