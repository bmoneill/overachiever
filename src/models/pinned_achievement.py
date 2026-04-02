from . import db


class PinnedAchievement(db.Model):
    __tablename__ = "pinned_achievements"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    achievement_id = db.Column(
        db.Integer, db.ForeignKey("achievements.id"), nullable=False
    )

    user = db.relationship("User", backref=db.backref("pinned_achievements", lazy="dynamic"))
    achievement = db.relationship("Achievement", backref=db.backref("pinned_by", lazy="dynamic"))
