"""Unit tests for the :class:`~src.models.user.User` model."""

from __future__ import annotations

from src.models.user import User


class TestUserCreation:
    """Tests for basic User instantiation and column defaults."""

    def test_create_user_with_required_fields(self, make_user):
        """A user created with only required fields should persist."""
        user = make_user(
            username="alice",
            email="alice@example.com",
            password_hash="hash123",
        )

        assert user.id is not None
        assert user.username == "alice"
        assert user.email == "alice@example.com"
        assert user.password_hash == "hash123"

    def test_default_bio_is_none(self, make_user):
        """The ``bio`` column should default to ``None``."""
        user = make_user()
        assert user.bio is None

    def test_default_xuid_is_none(self, make_user):
        """The ``xuid`` column should default to ``None``."""
        user = make_user()
        assert user.xuid is None

    def test_default_steam_id_is_none(self, make_user):
        """The ``steam_id`` column should default to ``None``."""
        user = make_user()
        assert user.steam_id is None

    def test_default_psn_id_is_none(self, make_user):
        """The ``psn_id`` column should default to ``None``."""
        user = make_user()
        assert user.psn_id is None

    def test_default_display_gamertags_is_false(self, make_user):
        """The ``display_gamertags`` flag should default to ``False``."""
        user = make_user()
        assert user.display_gamertags is False

    def test_default_achievement_count_is_zero(self, make_user):
        """The ``achievement_count`` column should default to ``0``."""
        user = make_user()
        assert user.achievement_count == 0


class TestUserOptionalFields:
    """Tests for setting optional / non-default fields."""

    def test_set_bio(self, make_user):
        """Setting ``bio`` should persist the value."""
        user = make_user(bio="Hello world")
        assert user.bio == "Hello world"

    def test_set_xuid(self, make_user):
        """Setting ``xuid`` should persist the value."""
        user = make_user(xuid="123456789")
        assert user.xuid == "123456789"

    def test_set_steam_id(self, make_user):
        """Setting ``steam_id`` should persist the value."""
        user = make_user(steam_id="STEAM_0:1:12345")
        assert user.steam_id == "STEAM_0:1:12345"

    def test_set_psn_id(self, make_user):
        """Setting ``psn_id`` should persist the value."""
        user = make_user(psn_id="CoolGamer99")
        assert user.psn_id == "CoolGamer99"

    def test_set_display_gamertags(self, make_user):
        """Setting ``display_gamertags`` to ``True`` should persist."""
        user = make_user(display_gamertags=True)
        assert user.display_gamertags is True

    def test_set_achievement_count(self, make_user):
        """Setting an explicit ``achievement_count`` should persist."""
        user = make_user(achievement_count=42)
        assert user.achievement_count == 42


class TestUserMixin:
    """Tests verifying Flask-Login's :class:`UserMixin` integration."""

    def test_is_active(self, make_user):
        """``UserMixin`` should mark the user as active by default."""
        user = make_user()
        assert user.is_active is True

    def test_is_authenticated(self, make_user):
        """``UserMixin`` should mark the user as authenticated."""
        user = make_user()
        assert user.is_authenticated is True

    def test_is_anonymous(self, make_user):
        """``UserMixin`` should mark the user as non-anonymous."""
        user = make_user()
        assert user.is_anonymous is False

    def test_get_id(self, make_user):
        """``get_id()`` should return the string representation of the PK."""
        user = make_user()
        assert user.get_id() == str(user.id)


class TestUserUniqueness:
    """Tests for unique constraints on ``username`` and ``email``."""

    def test_duplicate_username_raises(self, db_session, make_user):
        """Inserting two users with the same username should raise."""
        make_user(username="dupe", email="a@example.com")
        import sqlalchemy

        try:
            make_user(username="dupe", email="b@example.com")
            db_session.commit()
            raise AssertionError("Expected IntegrityError was not raised")
        except sqlalchemy.exc.IntegrityError:
            db_session.rollback()

    def test_duplicate_email_raises(self, db_session, make_user):
        """Inserting two users with the same email should raise."""
        make_user(username="user_a", email="same@example.com")
        import sqlalchemy

        try:
            make_user(username="user_b", email="same@example.com")
            db_session.commit()
            raise AssertionError("Expected IntegrityError was not raised")
        except sqlalchemy.exc.IntegrityError:
            db_session.rollback()


class TestUserTablename:
    """Tests for the table name."""

    def test_tablename(self):
        """The ``__tablename__`` should be ``'users'``."""
        assert User.__tablename__ == "users"
