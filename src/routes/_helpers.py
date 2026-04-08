"""Shared route helpers and constants."""

import os

from .. import login_manager
from ..models import db
from ..models.user import User
from flask import abort, flash, redirect, url_for
from ..helpers.platform import PLATFORM_NAME_MAP

ALLOW_REGISTRATION = os.environ.get("ALLOW_REGISTRATION", "true").lower() not in (
    "false",
    "0",
    "no",
)

def get_platform_or_abort(platform: str, redirect_to: str = "my_games") -> int:
    """Return the platform with the given name, or abort with a 404 if not found."""
    if platform not in PLATFORM_NAME_MAP:
        flash("Platform not found.", "error")
        abort(redirect(url_for(redirect_to)))
    return PLATFORM_NAME_MAP[platform]

def get_user_or_abort(username: str, redirect_to: str = "my_games") -> User:
    """Return the user with the given username, or abort with a 404 if not found."""
    user = get_user_by_username(username)
    if user is None:
        flash("User not found.", "error")
        abort(redirect(url_for(redirect_to)))
    return user


@login_manager.user_loader
def load_user(user_id: int):
    """Load a user by primary key for Flask-Login."""
    return db.session.get(User, int(user_id))


def get_user_by_username(username: str) -> User | None:
    """Look up a user by username. Returns a User or None."""
    return User.query.filter_by(username=username).first()
