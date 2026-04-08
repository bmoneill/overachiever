"""
UserFollow model representing a user following another user.
"""

from datetime import datetime, timezone

from . import db


class UserFollow(db.Model):
    """
    Represents a user following another user.
    """

    __tablename__ = "user_follows"

    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    followed_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    created_at = db.Column(
        db.String,
        default=lambda: datetime.now(timezone.utc).isoformat(),
    )

    follower = db.relationship(
        "User",
        foreign_keys=[follower_id],
        backref=db.backref("following", lazy="dynamic"),
    )
    followed = db.relationship(
        "User",
        foreign_keys=[followed_id],
        backref=db.backref("followers", lazy="dynamic"),
    )

    __table_args__ = (
        db.UniqueConstraint(
            "follower_id", "followed_id", name="uq_user_follow"
        ),
    )
