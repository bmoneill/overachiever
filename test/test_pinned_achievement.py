"""Unit tests for :class:`~src.models.pinned_achievement.PinnedAchievement`."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from src.models.pinned_achievement import PinnedAchievement


class TestPinnedAchievementCreation:
    """Tests for basic creation and column defaults."""

    def test_create_pinned_achievement(
        self, db_session, make_pinned_achievement
    ):
        """A pinned achievement can be created with valid foreign keys."""
        pa = make_pinned_achievement()

        assert pa.id is not None
        assert pa.user_id is not None
        assert pa.achievement_id is not None

    def test_persisted_to_database(self, db_session, make_pinned_achievement):
        """The record is persisted and retrievable by primary key."""
        pa = make_pinned_achievement()
        db_session.commit()

        fetched = db_session.get(PinnedAchievement, pa.id)
        assert fetched is not None
        assert fetched.id == pa.id

    def test_tablename(self):
        """The model maps to the ``pinned_achievements`` table."""
        assert PinnedAchievement.__tablename__ == "pinned_achievements"


class TestPinnedAchievementRelationships:
    """Tests for the ``user`` and ``achievement`` relationships."""

    def test_user_relationship(
        self, db_session, make_user, make_pinned_achievement
    ):
        """The ``user`` relationship resolves to the correct :class:`User`."""
        user = make_user(username="pinner")
        pa = make_pinned_achievement(user=user)

        assert pa.user is not None
        assert pa.user.username == "pinner"

    def test_achievement_relationship(
        self, db_session, make_achievement, make_pinned_achievement
    ):
        """The ``achievement`` relationship resolves to the correct :class:`Achievement`."""
        ach = make_achievement(achievement_name="Secret Find")
        pa = make_pinned_achievement(achievement=ach)

        assert pa.achievement is not None
        assert pa.achievement.achievement_name == "Secret Find"

    def test_user_pinned_achievements_backref(
        self, db_session, make_user, make_achievement, make_pinned_achievement
    ):
        """Pinned achievements are accessible via ``user.pinned_achievements``."""
        user = make_user()
        ach1 = make_achievement()
        ach2 = make_achievement()
        make_pinned_achievement(user=user, achievement=ach1)
        make_pinned_achievement(user=user, achievement=ach2)
        db_session.commit()

        assert user.pinned_achievements.count() == 2

    def test_achievement_pinned_by_backref(
        self, db_session, make_user, make_achievement, make_pinned_achievement
    ):
        """Users who pinned an achievement are accessible via ``achievement.pinned_by``."""
        ach = make_achievement()
        user1 = make_user()
        user2 = make_user()
        make_pinned_achievement(user=user1, achievement=ach)
        make_pinned_achievement(user=user2, achievement=ach)
        db_session.commit()

        assert ach.pinned_by.count() == 2


class TestPinnedAchievementConstraints:
    """Tests for NOT NULL and foreign-key constraints."""

    def test_user_id_required(self, db_session, make_achievement):
        """Creating a pinned achievement without ``user_id`` raises an error."""
        ach = make_achievement()
        pa = PinnedAchievement(achievement_id=ach.id)
        db_session.add(pa)

        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_achievement_id_required(self, db_session, make_user):
        """Creating a pinned achievement without ``achievement_id`` raises an error."""
        user = make_user()
        pa = PinnedAchievement(user_id=user.id)
        db_session.add(pa)

        with pytest.raises(IntegrityError):
            db_session.flush()


class TestPinnedAchievementMultiplePins:
    """Tests for pinning multiple achievements per user."""

    def test_user_can_pin_multiple_achievements(
        self, db_session, make_user, make_achievement, make_pinned_achievement
    ):
        """A single user can pin several different achievements."""
        user = make_user()
        achievements = [make_achievement() for _ in range(3)]
        for ach in achievements:
            make_pinned_achievement(user=user, achievement=ach)
        db_session.commit()

        assert user.pinned_achievements.count() == 3

    def test_achievement_can_be_pinned_by_multiple_users(
        self, db_session, make_user, make_achievement, make_pinned_achievement
    ):
        """Multiple users can each pin the same achievement."""
        ach = make_achievement()
        users = [make_user() for _ in range(3)]
        for user in users:
            make_pinned_achievement(user=user, achievement=ach)
        db_session.commit()

        assert ach.pinned_by.count() == 3


class TestPinnedAchievementDeletion:
    """Tests for cascade / deletion behaviour."""

    def test_delete_pinned_achievement(
        self, db_session, make_pinned_achievement
    ):
        """A pinned achievement can be deleted without affecting the user or achievement."""
        pa = make_pinned_achievement()
        user = pa.user
        ach = pa.achievement
        db_session.commit()

        db_session.delete(pa)
        db_session.commit()

        # The user and achievement should still exist.
        assert db_session.get(type(user), user.id) is not None
        assert db_session.get(type(ach), ach.id) is not None
        assert db_session.get(PinnedAchievement, pa.id) is None
