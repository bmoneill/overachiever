"""Unit tests for :class:`~src.models.user_achievement.UserAchievement`."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from src.models.user_achievement import UserAchievement


class TestUserAchievementCreation:
    """Tests for basic creation and column defaults."""

    def test_create_minimal(self, make_user_achievement):
        """A UserAchievement can be created with only required fields."""
        ua = make_user_achievement()

        assert ua.id is not None
        assert ua.user_id is not None
        assert ua.achievement_id is not None
        assert ua.time_unlocked is None

    def test_create_with_time_unlocked(
        self, make_user, make_achievement, make_user_achievement
    ):
        """``time_unlocked`` can be set at creation time."""
        user = make_user()
        achievement = make_achievement()
        ua = make_user_achievement(
            user=user,
            achievement=achievement,
            time_unlocked="2024-06-15T12:30:00Z",
        )

        assert ua.time_unlocked == "2024-06-15T12:30:00Z"

    def test_time_unlocked_defaults_to_none(self, make_user_achievement):
        """``time_unlocked`` should default to ``None``."""
        ua = make_user_achievement()

        assert ua.time_unlocked is None


class TestUserAchievementRelationships:
    """Tests for ORM relationships and back-references."""

    def test_user_relationship(self, make_user, make_user_achievement):
        """The ``user`` relationship resolves to the correct :class:`User`."""
        user = make_user(username="achiever")
        ua = make_user_achievement(user=user)

        assert ua.user is user
        assert ua.user.username == "achiever"

    def test_achievement_relationship(
        self, make_achievement, make_user_achievement
    ):
        """The ``achievement`` relationship resolves to the correct :class:`Achievement`."""
        achievement = make_achievement(achievement_name="Speed Run")
        ua = make_user_achievement(achievement=achievement)

        assert ua.achievement is achievement
        assert ua.achievement.achievement_name == "Speed Run"

    def test_user_backref(
        self, make_user, make_achievement, make_user_achievement
    ):
        """The ``user_achievements`` back-reference on :class:`User` is populated."""
        user = make_user()
        a1 = make_achievement()
        a2 = make_achievement()
        make_user_achievement(user=user, achievement=a1)
        make_user_achievement(user=user, achievement=a2)

        assert user.user_achievements.count() == 2

    def test_achievement_backref(
        self, make_user, make_achievement, make_user_achievement
    ):
        """The ``user_achievements`` back-reference on :class:`Achievement` is populated."""
        achievement = make_achievement()
        u1 = make_user()
        u2 = make_user()
        make_user_achievement(user=u1, achievement=achievement)
        make_user_achievement(user=u2, achievement=achievement)

        assert achievement.user_achievements.count() == 2


class TestUserAchievementConstraints:
    """Tests for unique constraints and nullable enforcement."""

    def test_unique_user_achievement_pair(
        self, db_session, make_user, make_achievement, make_user_achievement
    ):
        """Duplicate (user_id, achievement_id) pairs must raise an IntegrityError."""
        user = make_user()
        achievement = make_achievement()
        make_user_achievement(user=user, achievement=achievement)

        with pytest.raises(IntegrityError):
            make_user_achievement(user=user, achievement=achievement)

    def test_same_user_different_achievements(
        self, make_user, make_achievement, make_user_achievement
    ):
        """A user can unlock multiple distinct achievements."""
        user = make_user()
        a1 = make_achievement()
        a2 = make_achievement()
        ua1 = make_user_achievement(user=user, achievement=a1)
        ua2 = make_user_achievement(user=user, achievement=a2)

        assert ua1.id != ua2.id
        assert ua1.achievement_id != ua2.achievement_id

    def test_same_achievement_different_users(
        self, make_user, make_achievement, make_user_achievement
    ):
        """Different users can unlock the same achievement."""
        achievement = make_achievement()
        u1 = make_user()
        u2 = make_user()
        ua1 = make_user_achievement(user=u1, achievement=achievement)
        ua2 = make_user_achievement(user=u2, achievement=achievement)

        assert ua1.id != ua2.id
        assert ua1.user_id != ua2.user_id

    def test_user_id_not_nullable(self, db_session, make_achievement):
        """``user_id`` must not be null."""
        achievement = make_achievement()
        ua = UserAchievement(achievement_id=achievement.id)
        db_session.add(ua)

        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_achievement_id_not_nullable(self, db_session, make_user):
        """``achievement_id`` must not be null."""
        user = make_user()
        ua = UserAchievement(user_id=user.id)
        db_session.add(ua)

        with pytest.raises(IntegrityError):
            db_session.flush()


class TestUserAchievementTablename:
    """Verify the model's table metadata."""

    def test_tablename(self):
        """The ``__tablename__`` should be ``user_achievements``."""
        assert UserAchievement.__tablename__ == "user_achievements"
