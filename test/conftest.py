"""Shared test fixtures for the ``src.api`` test suite.

Provides a minimal Flask application wired to an in-memory SQLite
database so that tests touching the ORM (mainly ``sync.py``) can run
without any external infrastructure.  Also supplies an auto-use mock
for :func:`~src.helpers.image_cache.get_image_path` so that no real
network or filesystem I/O occurs during tests.
"""

from __future__ import annotations

import os
from typing import Generator
from unittest.mock import patch

import pytest
from flask import Flask
from werkzeug.security import generate_password_hash

from src.models import db as _db
from src.models.achievement import Achievement
from src.models.guide import Guide
from src.models.guide_rating import GuideRating
from src.models.pinned_achievement import PinnedAchievement
from src.models.pinned_game import PinnedGame
from src.models.title import Title
from src.models.user import User
from src.models.user_achievement import UserAchievement
from src.models.user_follow import UserFollow
from src.models.user_title import UserTitle
from src.models.xbox360icon import Xbox360Icon

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


@pytest.fixture()
def make_user(db_session):
    """Factory fixture that creates and persists a :class:`User`.

    Accepts keyword overrides for any column.  Provides sensible
    defaults so callers only need to specify the fields they care about.
    """

    _counter = 0

    def _factory(**overrides) -> User:
        nonlocal _counter
        _counter += 1
        defaults = {
            "username": f"user{_counter}",
            "email": f"user{_counter}@example.com",
            "password_hash": "fakehash",
        }
        defaults.update(overrides)
        user = User(**defaults)
        db_session.add(user)
        db_session.flush()
        return user

    return _factory


@pytest.fixture()
def make_title(db_session):
    """Factory fixture that creates and persists a :class:`Title`."""

    _counter = 0

    def _factory(**overrides) -> Title:
        nonlocal _counter
        _counter += 1
        defaults = {
            "name": f"Game {_counter}",
            "platform": 1,
            "platform_title_id": str(100 + _counter),
            "total_achievements": 10,
        }
        defaults.update(overrides)
        title = Title(**defaults)
        db_session.add(title)
        db_session.flush()
        return title

    return _factory


@pytest.fixture()
def make_achievement(db_session, make_title):
    """Factory fixture that creates and persists an :class:`Achievement`.

    Automatically creates a parent :class:`Title` when none is supplied.
    """

    _counter = 0

    def _factory(title: Title | None = None, **overrides) -> Achievement:
        nonlocal _counter
        _counter += 1
        if title is None:
            title = make_title()
        defaults = {
            "achievement_id": str(1000 + _counter),
            "title_id": title.id,
            "achievement_name": f"Achievement {_counter}",
        }
        defaults.update(overrides)
        achievement = Achievement(**defaults)
        db_session.add(achievement)
        db_session.flush()
        return achievement

    return _factory


@pytest.fixture()
def make_guide(db_session, make_user, make_achievement):
    """Factory fixture that creates and persists a :class:`Guide`."""

    _counter = 0

    def _factory(
        user: User | None = None,
        achievement: Achievement | None = None,
        **overrides,
    ) -> Guide:
        nonlocal _counter
        _counter += 1
        if user is None:
            user = make_user()
        if achievement is None:
            achievement = make_achievement()
        defaults = {
            "url": f"https://example.com/guide/{_counter}",
            "platform_id": 1,
            "title_id": str(achievement.title_id),
            "achievement_id": achievement.id,
            "user_id": user.id,
        }
        defaults.update(overrides)
        guide = Guide(**defaults)
        db_session.add(guide)
        db_session.flush()
        return guide

    return _factory


@pytest.fixture()
def make_guide_rating(db_session, make_user, make_guide):
    """Factory fixture that creates and persists a :class:`GuideRating`."""

    def _factory(
        guide: Guide | None = None,
        user: User | None = None,
        rating: bool = True,
        **overrides,
    ) -> GuideRating:
        if guide is None:
            guide = make_guide()
        if user is None:
            user = make_user()
        defaults = {
            "guide_id": guide.id,
            "user_id": user.id,
            "rating": rating,
        }
        defaults.update(overrides)
        gr = GuideRating(**defaults)
        db_session.add(gr)
        db_session.flush()
        return gr

    return _factory


@pytest.fixture()
def make_pinned_achievement(db_session, make_user, make_achievement):
    """Factory fixture for :class:`PinnedAchievement`."""

    def _factory(
        user: User | None = None,
        achievement: Achievement | None = None,
        **overrides,
    ) -> PinnedAchievement:
        if user is None:
            user = make_user()
        if achievement is None:
            achievement = make_achievement()
        defaults = {
            "user_id": user.id,
            "achievement_id": achievement.id,
        }
        defaults.update(overrides)
        pa = PinnedAchievement(**defaults)
        db_session.add(pa)
        db_session.flush()
        return pa

    return _factory


@pytest.fixture()
def make_pinned_game(db_session, make_user, make_title):
    """Factory fixture for :class:`PinnedGame`."""

    def _factory(
        user: User | None = None,
        title: Title | None = None,
        **overrides,
    ) -> PinnedGame:
        if user is None:
            user = make_user()
        if title is None:
            title = make_title()
        defaults = {
            "user_id": user.id,
            "title_id": title.id,
        }
        defaults.update(overrides)
        pg = PinnedGame(**defaults)
        db_session.add(pg)
        db_session.flush()
        return pg

    return _factory


@pytest.fixture()
def make_user_achievement(db_session, make_user, make_achievement):
    """Factory fixture for :class:`UserAchievement`."""

    def _factory(
        user: User | None = None,
        achievement: Achievement | None = None,
        **overrides,
    ) -> UserAchievement:
        if user is None:
            user = make_user()
        if achievement is None:
            achievement = make_achievement()
        defaults = {
            "user_id": user.id,
            "achievement_id": achievement.id,
        }
        defaults.update(overrides)
        ua = UserAchievement(**defaults)
        db_session.add(ua)
        db_session.flush()
        return ua

    return _factory


@pytest.fixture()
def make_user_follow(db_session, make_user):
    """Factory fixture for :class:`UserFollow`."""

    def _factory(
        follower: User | None = None,
        followed: User | None = None,
        **overrides,
    ) -> UserFollow:
        if follower is None:
            follower = make_user()
        if followed is None:
            followed = make_user()
        defaults = {
            "follower_id": follower.id,
            "followed_id": followed.id,
        }
        defaults.update(overrides)
        uf = UserFollow(**defaults)
        db_session.add(uf)
        db_session.flush()
        return uf

    return _factory


@pytest.fixture()
def make_user_title(db_session, make_user, make_title):
    """Factory fixture for :class:`UserTitle`."""

    def _factory(
        user: User | None = None,
        title: Title | None = None,
        **overrides,
    ) -> UserTitle:
        if user is None:
            user = make_user()
        if title is None:
            title = make_title()
        defaults = {
            "user_id": user.id,
            "title_id": title.id,
        }
        defaults.update(overrides)
        ut = UserTitle(**defaults)
        db_session.add(ut)
        db_session.flush()
        return ut

    return _factory


@pytest.fixture()
def make_xbox360icon(db_session):
    """Factory fixture for :class:`Xbox360Icon`."""

    _counter = 0

    def _factory(**overrides) -> Xbox360Icon:
        nonlocal _counter
        _counter += 1
        defaults = {
            "url": f"https://example.com/icon/{_counter}.png",
            "title_id": _counter,
            "achievement_id": _counter,
        }
        defaults.update(overrides)
        icon = Xbox360Icon(**defaults)
        db_session.add(icon)
        db_session.flush()
        return icon

    return _factory


@pytest.fixture()
def make_user(db_session):
    """Factory fixture that creates and persists a :class:`User`.

    Accepts keyword overrides for any column.  Provides sensible
    defaults so callers only need to specify the fields they care about.
    """

    _counter = 0

    def _factory(**overrides) -> User:
        nonlocal _counter
        _counter += 1
        defaults = {
            "username": f"user{_counter}",
            "email": f"user{_counter}@example.com",
            "password_hash": "fakehash",
        }
        defaults.update(overrides)
        user = User(**defaults)
        db_session.add(user)
        db_session.flush()
        return user

    return _factory


@pytest.fixture()
def make_title(db_session):
    """Factory fixture that creates and persists a :class:`Title`."""

    _counter = 0

    def _factory(**overrides) -> Title:
        nonlocal _counter
        _counter += 1
        defaults = {
            "name": f"Game {_counter}",
            "platform": 1,
            "platform_title_id": str(100 + _counter),
            "total_achievements": 10,
        }
        defaults.update(overrides)
        title = Title(**defaults)
        db_session.add(title)
        db_session.flush()
        return title

    return _factory


@pytest.fixture()
def make_achievement(db_session, make_title):
    """Factory fixture that creates and persists an :class:`Achievement`.

    Automatically creates a parent :class:`Title` when none is supplied.
    """

    _counter = 0

    def _factory(title: Title | None = None, **overrides) -> Achievement:
        nonlocal _counter
        _counter += 1
        if title is None:
            title = make_title()
        defaults = {
            "achievement_id": str(1000 + _counter),
            "title_id": title.id,
            "achievement_name": f"Achievement {_counter}",
        }
        defaults.update(overrides)
        achievement = Achievement(**defaults)
        db_session.add(achievement)
        db_session.flush()
        return achievement

    return _factory


@pytest.fixture()
def make_guide(db_session, make_user, make_achievement):
    """Factory fixture that creates and persists a :class:`Guide`."""

    _counter = 0

    def _factory(
        user: User | None = None,
        achievement: Achievement | None = None,
        **overrides,
    ) -> Guide:
        nonlocal _counter
        _counter += 1
        if user is None:
            user = make_user()
        if achievement is None:
            achievement = make_achievement()
        defaults = {
            "url": f"https://example.com/guide/{_counter}",
            "platform_id": 1,
            "title_id": str(achievement.title_id),
            "achievement_id": achievement.id,
            "user_id": user.id,
        }
        defaults.update(overrides)
        guide = Guide(**defaults)
        db_session.add(guide)
        db_session.flush()
        return guide

    return _factory


@pytest.fixture()
def make_guide_rating(db_session, make_user, make_guide):
    """Factory fixture that creates and persists a :class:`GuideRating`."""

    def _factory(
        guide: Guide | None = None,
        user: User | None = None,
        rating: bool = True,
        **overrides,
    ) -> GuideRating:
        if guide is None:
            guide = make_guide()
        if user is None:
            user = make_user()
        defaults = {
            "guide_id": guide.id,
            "user_id": user.id,
            "rating": rating,
        }
        defaults.update(overrides)
        gr = GuideRating(**defaults)
        db_session.add(gr)
        db_session.flush()
        return gr

    return _factory


@pytest.fixture()
def make_pinned_achievement(db_session, make_user, make_achievement):
    """Factory fixture for :class:`PinnedAchievement`."""

    def _factory(
        user: User | None = None,
        achievement: Achievement | None = None,
        **overrides,
    ) -> PinnedAchievement:
        if user is None:
            user = make_user()
        if achievement is None:
            achievement = make_achievement()
        defaults = {
            "user_id": user.id,
            "achievement_id": achievement.id,
        }
        defaults.update(overrides)
        pa = PinnedAchievement(**defaults)
        db_session.add(pa)
        db_session.flush()
        return pa

    return _factory


@pytest.fixture()
def make_pinned_game(db_session, make_user, make_title):
    """Factory fixture for :class:`PinnedGame`."""

    def _factory(
        user: User | None = None,
        title: Title | None = None,
        **overrides,
    ) -> PinnedGame:
        if user is None:
            user = make_user()
        if title is None:
            title = make_title()
        defaults = {
            "user_id": user.id,
            "title_id": title.id,
        }
        defaults.update(overrides)
        pg = PinnedGame(**defaults)
        db_session.add(pg)
        db_session.flush()
        return pg

    return _factory


@pytest.fixture()
def make_user_achievement(db_session, make_user, make_achievement):
    """Factory fixture for :class:`UserAchievement`."""

    def _factory(
        user: User | None = None,
        achievement: Achievement | None = None,
        **overrides,
    ) -> UserAchievement:
        if user is None:
            user = make_user()
        if achievement is None:
            achievement = make_achievement()
        defaults = {
            "user_id": user.id,
            "achievement_id": achievement.id,
        }
        defaults.update(overrides)
        ua = UserAchievement(**defaults)
        db_session.add(ua)
        db_session.flush()
        return ua

    return _factory


@pytest.fixture()
def make_user_follow(db_session, make_user):
    """Factory fixture for :class:`UserFollow`."""

    def _factory(
        follower: User | None = None,
        followed: User | None = None,
        **overrides,
    ) -> UserFollow:
        if follower is None:
            follower = make_user()
        if followed is None:
            followed = make_user()
        defaults = {
            "follower_id": follower.id,
            "followed_id": followed.id,
        }
        defaults.update(overrides)
        uf = UserFollow(**defaults)
        db_session.add(uf)
        db_session.flush()
        return uf

    return _factory


@pytest.fixture()
def make_user_title(db_session, make_user, make_title):
    """Factory fixture for :class:`UserTitle`."""

    def _factory(
        user: User | None = None,
        title: Title | None = None,
        **overrides,
    ) -> UserTitle:
        if user is None:
            user = make_user()
        if title is None:
            title = make_title()
        defaults = {
            "user_id": user.id,
            "title_id": title.id,
        }
        defaults.update(overrides)
        ut = UserTitle(**defaults)
        db_session.add(ut)
        db_session.flush()
        return ut

    return _factory


@pytest.fixture()
def make_xbox360icon(db_session):
    """Factory fixture for :class:`Xbox360Icon`."""

    _counter = 0

    def _factory(**overrides) -> Xbox360Icon:
        nonlocal _counter
        _counter += 1
        defaults = {
            "url": f"https://example.com/icon/{_counter}.png",
            "title_id": _counter,
            "achievement_id": _counter,
        }
        defaults.update(overrides)
        icon = Xbox360Icon(**defaults)
        db_session.add(icon)
        db_session.flush()
        return icon

    return _factory


# ------------------------------------------------------------------
# Route-testing fixtures
# ------------------------------------------------------------------

_SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")


@pytest.fixture(scope="session")
def route_app(app) -> Flask:
    """Extend the session-scoped test app with all route handlers.

    Copies every URL rule registered on ``src.app`` into the test app,
    configures Flask-Login, and points the Jinja2 template loader at
    ``src/templates`` so that ``render_template`` calls succeed.
    """
    from flask_login import LoginManager

    from src import app as src_app

    # Templates & static files live under src/
    app.template_folder = os.path.join(_SRC_DIR, "templates")
    app.static_folder = os.path.join(_SRC_DIR, "static")

    # Flask-Login
    lm = LoginManager()
    lm.init_app(app)
    lm.login_view = "login"
    lm.login_message = "Please log in to access this page."
    lm.login_message_category = "error"
    lm.session_protection = None  # disable for test convenience

    @lm.user_loader
    def _load_user(user_id: int):
        return _db.session.get(User, int(user_id))

    # Copy view functions from the real app to the test app.
    for rule in src_app.url_map.iter_rules():
        ep = rule.endpoint
        vf = src_app.view_functions.get(ep)
        if vf is None or ep == "static":
            continue
        methods = rule.methods - {"OPTIONS", "HEAD"}
        try:
            app.add_url_rule(
                rule.rule,
                endpoint=ep,
                view_func=vf,
                methods=methods or None,
            )
        except (AssertionError, ValueError):
            pass  # already registered

    return app


@pytest.fixture()
def client(route_app: Flask, db_session):
    """Flask test client backed by an in-memory DB with routes."""
    with route_app.test_client() as c:
        yield c


@pytest.fixture()
def auth_user(db_session, make_user) -> User:
    """A pre-created user with a known password (``testpass``)."""
    user = make_user(
        username="testuser",
        email="testuser@example.com",
        password_hash=generate_password_hash("testpass"),
    )
    db_session.commit()
    return user


@pytest.fixture()
def auth_client(route_app: Flask, db_session, auth_user):
    """Flask test client whose session belongs to :func:`auth_user`."""
    with route_app.test_client() as c:
        with c.session_transaction() as sess:
            sess["_user_id"] = str(auth_user.id)
            sess["_fresh"] = True
        # Stash the user for convenient access in tests.
        c._user = auth_user  # type: ignore[attr-defined]
        yield c
