"""
GuideRating model representing a user's rating of a guide.
"""

from . import db


class GuideRating(db.Model):
    """
    Represents a user's rating of a guide.
    """

    __tablename__ = "guide_rating"

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
