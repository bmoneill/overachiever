"""Shared route helpers and constants."""

import os

from .. import login_manager
from ..models import db
from ..models.user import User
from ..api.platform import PLATFORM_XBOX, PLATFORM_STEAM

PLATFORM_ID_TO_SLUG = {
    PLATFORM_XBOX: "xbox",
    PLATFORM_STEAM: "steam",
}

PLATFORM_SLUG_TO_ID = {
    "xbox": PLATFORM_XBOX,
    "steam": PLATFORM_STEAM,
}

ALLOW_REGISTRATION = os.environ.get("ALLOW_REGISTRATION", "true").lower() not in (
    "false",
    "0",
    "no",
)


@login_manager.user_loader
def load_user(user_id: int):
    """Load a user by primary key for Flask-Login."""
    return db.session.get(User, int(user_id))


def get_user_by_username(username: str) -> User | None:
    """Look up a user by username. Returns a User or None."""
    return User.query.filter_by(username=username).first()
