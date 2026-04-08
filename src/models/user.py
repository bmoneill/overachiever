"""
User model representing a registered user.
"""

from flask_login import UserMixin

from . import db


class User(UserMixin, db.Model):
    """
    Represents a registered user.
    """

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String, unique=True, nullable=False)
    email = db.Column(db.String, unique=True, nullable=False)
    bio = db.Column(db.Text, default=None)
    password_hash = db.Column(db.String, nullable=False)
    xuid = db.Column(db.String, default=None)
    steam_id = db.Column(db.String, default=None)
    psn_id = db.Column(db.String, default=None)
    display_gamertags = db.Column(db.Boolean, default=False)
    achievement_count = db.Column(db.Integer, default=0)
