"""
API routes for guide ratings (thumbs up / thumbs down).
"""

from __future__ import annotations

from flask import jsonify, request
from flask_login import current_user, login_required

from .. import app
from ..models import db
from ..models.guide import Guide
from ..models.guide_rating import GuideRating


@app.route("/api/guides/<int:guide_id>/rate", methods=["POST"])
@login_required
def rate_guide(guide_id: int):
    """
    Rate a guide with a thumbs up or thumbs down.

    Accepts a JSON body with a ``rating`` key (``true`` for thumbs up,
    ``false`` for thumbs down).  Toggle logic:

    * If the user has no existing vote → create one.
    * If the user's existing vote matches the submitted value → remove it
      (toggle off).
    * If the user's existing vote differs → update it.

    Returns JSON: ``{"up": int, "down": int, "user_vote": true|false|null}``.

    :param guide_id: Primary key of the guide to rate.
    :return: JSON response with updated rating counts and the user's current vote.
    """
    guide = db.session.get(Guide, guide_id)
    if guide is None:
        return jsonify({"error": "Guide not found."}), 404

    payload = request.get_json(silent=True) or {}
    if "rating" not in payload or not isinstance(payload["rating"], bool):
        return jsonify({"error": "Field 'rating' (boolean) is required."}), 400

    new_rating: bool = payload["rating"]
    user_id: int = current_user.id

    existing: GuideRating | None = GuideRating.query.filter_by(
        guide_id=guide_id, user_id=user_id
    ).first()

    if existing is None:
        # No prior vote — create one.
        db.session.add(
            GuideRating(guide_id=guide_id, user_id=user_id, rating=new_rating)
        )
    elif existing.rating == new_rating:
        # Same value — toggle off (remove vote).
        db.session.delete(existing)
    else:
        # Different value — update vote.
        existing.rating = new_rating

    db.session.commit()

    up, down = GuideRating.get_counts(guide_id)
    user_vote = GuideRating.get_user_vote(guide_id, user_id)

    return jsonify({"up": up, "down": down, "user_vote": user_vote})
