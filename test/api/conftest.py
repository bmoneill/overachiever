"""Shared test fixtures for the ``src.api`` test suite.

Provides a minimal Flask application wired to an in-memory SQLite
database so that tests touching the ORM (mainly ``sync.py``) can run
without any external infrastructure.  Also supplies an auto-use mock
for :func:`~src.helpers.image_cache.get_image_path` so that no real
network or filesystem I/O occurs during tests.
"""

from __future__ import annotations

from typing import Generator
from unittest.mock import patch

import pytest
from flask import Flask

from src.models import db as _db

# ------------------------------------------------------------------
# Flask application & database
# ------------------------------------------------------------------


@pytest.fixture(scope="session")
def app() -> Flask:
    """Create a minimal Flask application with an in-memory SQLite DB."""
    test_app = Flask(__name__)
    test_app.config["TESTING"] = True
    test_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    test_app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    test_app.config["SERVER_NAME"] = "localhost"
    test_app.secret_key = "testing-secret-key"

    _db.init_app(test_app)

    with test_app.app_context():
        _db.create_all()

    return test_app


@pytest.fixture()
def db_session(app: Flask) -> Generator:
    """Yield a database session inside an application context.

    Each test gets a clean slate — all tables are dropped and recreated
    before the test runs, and the session is removed afterwards.
    """
    with app.app_context():
        _db.create_all()
        yield _db.session
        _db.session.remove()
        _db.drop_all()


# ------------------------------------------------------------------
# Image-cache mock (auto-use so no test accidentally hits the network)
# ------------------------------------------------------------------


def _fake_get_image_path(url: str) -> str:
    """Return a deterministic fake image path for any URL."""
    return f"/static/img/{hash(url)}"


@pytest.fixture(autouse=True)
def mock_image_cache() -> Generator:
    """Patch ``get_image_path`` everywhere it is imported.

    The function is imported into several modules at load time, so we
    patch the *references* in those modules rather than the original
    definition.
    """
    targets = [
        "src.api.steam.get_image_path",
        "src.api.xbox.get_image_path",
        "src.api.sync.get_image_path",
        "src.helpers.image_cache.get_image_path",
    ]
    patches = [patch(t, side_effect=_fake_get_image_path) for t in targets]
    mocks = [p.start() for p in patches]
    yield mocks
    for p in patches:
        p.stop()


# ------------------------------------------------------------------
# Convenience helpers available to all test modules
# ------------------------------------------------------------------


@pytest.fixture()
def mock_steam_api_key() -> Generator:
    """Ensure ``STEAM_API_KEY`` is set for the duration of a test."""
    with patch("src.api.steam.STEAM_API_KEY", "fake-steam-key"):
        yield


@pytest.fixture()
def mock_openxbl_api_key() -> Generator:
    """Ensure ``OPENXBL_API_KEY`` is set for the duration of a test."""
    with patch("src.api.xbox.OPENXBL_API_KEY", "fake-openxbl-key"):
        yield
