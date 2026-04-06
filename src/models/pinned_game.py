"""PinnedGame model representing a game pinned to a user's profile showcase."""

from . import db


class PinnedGame(db.Model):
    """Represents a game pinned to a user's profile showcase.

    Each row links a :class:`~src.models.user.User` to a
    :class:`~src.models.title.Title`.  All display data (name, image,
    etc.) is accessed through the ``title`` relationship rather than
    being denormalised into this table.

    Attributes:
        id: Primary key.
        user_id: Foreign key to ``users.id``.
        title_id: Foreign key to ``titles.id``.
    """

    __tablename__ = "pinned_games"

    id: int = db.Column(db.Integer, primary_key=True)
    user_id: int = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    title_id: int = db.Column(
        db.Integer, db.ForeignKey("titles.id"), nullable=False
    )

    user = db.relationship(
        "User", backref=db.backref("pinned_games", lazy="dynamic")
    )
    title = db.relationship(
        "Title", backref=db.backref("pinned_by", lazy="dynamic")
    )
