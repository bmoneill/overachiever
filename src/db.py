"""
Initializes the database.
"""

import os

from .models import db

_APP_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE = os.environ.get(
    "DATABASE",
    os.path.join(_APP_DIR, "..", "overachiever.db"),
)


def init_app(app):
    """Configure SQLAlchemy on the Flask application and create tables."""
    app.config.setdefault(
        "SQLALCHEMY_DATABASE_URI",
        f"sqlite:///{os.path.abspath(DATABASE)}",
    )
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)

    db.init_app(app)

    with app.app_context():
        db.create_all()
