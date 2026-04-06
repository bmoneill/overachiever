"""
Represents a user's achievement progress.
"""

from . import db


class UserAchievement(db.Model):
    """
    Represents a user's achievement progress.
    """
    __tablename__ = "user_achievements"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    achievement_id = db.Column(
        db.Integer, db.ForeignKey("achievements.id"), nullable=False
    )
    time_unlocked = db.Column(db.String, default=None)

    user = db.relationship("User", backref=db.backref("user_achievements", lazy="dynamic"))
    achievement = db.relationship("Achievement",
        backref=db.backref("user_achievements", lazy="dynamic"))

    __table_args__ = (
        db.UniqueConstraint(
            "user_id", "achievement_id", name="uq_user_achievement"
        ),
    )
