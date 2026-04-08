"""Unit tests for the :class:`GuideRating` model."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from src.models.guide_rating import GuideRating


class TestGuideRatingCreation:
    """Tests for basic GuideRating instantiation and persistence."""

    def test_create_positive_rating(
        self, db_session, make_guide_rating, make_guide, make_user
    ):
        """A positive (True) rating can be created and persisted."""
        guide = make_guide()
        user = make_user()
        gr = make_guide_rating(guide=guide, user=user, rating=True)

        assert gr.id is not None
        assert gr.guide_id == guide.id
        assert gr.user_id == user.id
        assert gr.rating is True

    def test_create_negative_rating(
        self, db_session, make_guide_rating, make_guide, make_user
    ):
        """A negative (False) rating can be created and persisted."""
        guide = make_guide()
        user = make_user()
        gr = make_guide_rating(guide=guide, user=user, rating=False)

        assert gr.id is not None
        assert gr.rating is False

    def test_rating_defaults_to_true_in_factory(
        self, db_session, make_guide_rating
    ):
        """The factory fixture defaults ``rating`` to True."""
        gr = make_guide_rating()
        assert gr.rating is True

    def test_guide_id_required(self, db_session, make_user):
        """``guide_id`` is non-nullable; omitting it raises an error."""
        user = make_user()
        gr = GuideRating(user_id=user.id, rating=True)
        db_session.add(gr)
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_user_id_required(self, db_session, make_guide):
        """``user_id`` is non-nullable; omitting it raises an error."""
        guide = make_guide()
        gr = GuideRating(guide_id=guide.id, rating=True)
        db_session.add(gr)
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_rating_required(self, db_session, make_user, make_guide):
        """``rating`` is non-nullable; omitting it raises an error."""
        user = make_user()
        guide = make_guide()
        gr = GuideRating(guide_id=guide.id, user_id=user.id)
        db_session.add(gr)
        with pytest.raises(IntegrityError):
            db_session.flush()


class TestGuideRatingRelationships:
    """Tests for GuideRating's ORM relationships."""

    def test_guide_relationship(
        self, db_session, make_guide_rating, make_guide, make_user
    ):
        """The ``guide`` relationship resolves to the correct Guide."""
        guide = make_guide()
        user = make_user()
        gr = make_guide_rating(guide=guide, user=user)

        assert gr.guide is not None
        assert gr.guide.id == guide.id
        assert gr.guide.url == guide.url

    def test_user_relationship(
        self, db_session, make_guide_rating, make_guide, make_user
    ):
        """The ``user`` relationship resolves to the correct User."""
        user = make_user(username="rater")
        guide = make_guide()
        gr = make_guide_rating(guide=guide, user=user)

        assert gr.user is not None
        assert gr.user.id == user.id
        assert gr.user.username == "rater"

    def test_guide_ratings_backref(
        self, db_session, make_guide_rating, make_guide, make_user
    ):
        """The Guide ``ratings`` dynamic back-reference contains the rating."""
        guide = make_guide()
        user = make_user()
        gr = make_guide_rating(guide=guide, user=user, rating=True)

        ratings = guide.ratings.all()
        assert len(ratings) == 1
        assert ratings[0].id == gr.id

    def test_user_guide_ratings_backref(
        self, db_session, make_guide_rating, make_guide, make_user
    ):
        """The User ``guide_ratings`` dynamic back-reference contains the rating."""
        user = make_user()
        guide = make_guide()
        gr = make_guide_rating(guide=guide, user=user)

        user_ratings = user.guide_ratings.all()
        assert len(user_ratings) == 1
        assert user_ratings[0].id == gr.id


class TestGuideRatingMultiple:
    """Tests for multiple ratings on a single guide."""

    def test_multiple_users_rate_same_guide(
        self, db_session, make_guide_rating, make_guide, make_user
    ):
        """Multiple users can rate the same guide."""
        guide = make_guide()
        user1 = make_user()
        user2 = make_user()

        gr1 = make_guide_rating(guide=guide, user=user1, rating=True)
        gr2 = make_guide_rating(guide=guide, user=user2, rating=False)

        ratings = guide.ratings.all()
        assert len(ratings) == 2

        rating_ids = {r.id for r in ratings}
        assert gr1.id in rating_ids
        assert gr2.id in rating_ids

    def test_user_rates_multiple_guides(
        self, db_session, make_guide_rating, make_guide, make_user
    ):
        """A single user can rate multiple different guides."""
        user = make_user()
        guide1 = make_guide()
        guide2 = make_guide()

        make_guide_rating(guide=guide1, user=user, rating=True)
        make_guide_rating(guide=guide2, user=user, rating=False)

        user_ratings = user.guide_ratings.all()
        assert len(user_ratings) == 2

    def test_count_positive_ratings(
        self, db_session, make_guide_rating, make_guide, make_user
    ):
        """Positive ratings on a guide can be filtered and counted."""
        guide = make_guide()
        user1 = make_user()
        user2 = make_user()
        user3 = make_user()

        make_guide_rating(guide=guide, user=user1, rating=True)
        make_guide_rating(guide=guide, user=user2, rating=True)
        make_guide_rating(guide=guide, user=user3, rating=False)

        positive = guide.ratings.filter_by(rating=True).count()
        negative = guide.ratings.filter_by(rating=False).count()

        assert positive == 2
        assert negative == 1


class TestGuideRatingTablename:
    """Tests for the model's table metadata."""

    def test_tablename(self):
        """The model uses the ``guide_rating`` table name."""
        assert GuideRating.__tablename__ == "guide_rating"
