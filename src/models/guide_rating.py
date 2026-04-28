"""
GuideRating model representing a user's rating of a guide.
"""

from __future__ import annotations

from . import db


class GuideRating(db.Model):
    """
    Represents a user's rating of a guide.

    ``rating`` is a boolean: ``True`` = thumbs up, ``False`` = thumbs down.
    Each user may have at most one rating per guide (enforced by the unique
    constraint on ``(guide_id, user_id)``).
    """

    __tablename__ = "guide_rating"
    __table_args__ = (
        db.UniqueConstraint("guide_id", "user_id", name="uq_guide_rating_user"),
    )

    id = db.Column(db.Integer, primary_key=True)
    guide_id = db.Column(db.Integer, db.ForeignKey("guides.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    rating = db.Column(db.Boolean, nullable=False)

    guide = db.relationship(
        "Guide", backref=db.backref("ratings", lazy="dynamic")
    )
    user = db.relationship(
        "User", backref=db.backref("guide_ratings", lazy="dynamic")
    )

    @classmethod
    def get_counts(cls, guide_id: int) -> tuple[int, int]:
        """
        Return ``(thumbs_up_count, thumbs_down_count)`` for the given guide.

        :param guide_id: Primary key of the guide.
        :return: A tuple ``(up, down)`` of integer counts.
        """
        rows = cls.query.filter_by(guide_id=guide_id).all()
        up = sum(1 for r in rows if r.rating is True)
        down = sum(1 for r in rows if r.rating is False)
        return up, down

    @classmethod
    def get_user_vote(cls, guide_id: int, user_id: int) -> bool | None:
        """
        Return the current user's vote for the given guide, or ``None`` if
        the user has not voted.

        :param guide_id: Primary key of the guide.
        :param user_id: Primary key of the user.
        :return: ``True`` (thumbs up), ``False`` (thumbs down), or ``None``.
        """
        row = cls.query.filter_by(guide_id=guide_id, user_id=user_id).first()
        return row.rating if row is not None else None
