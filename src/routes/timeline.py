from collections import OrderedDict
from datetime import datetime

from flask import render_template
from flask_login import current_user, login_required

from .. import app
from ..models.user_follow import UserFollow
from ..models.user_achievement import UserAchievement
from ..models.achievement import Achievement
from ..models.user import User
from ._helpers import PLATFORM_ID_TO_SLUG
from ..api.sync import resolve_xbox_icon_fallbacks


@app.route("/timeline")
@login_required
def timeline():
    """Show a timeline of achievements from users the current user follows."""
    followed_ids = [
        f.followed_id
        for f in UserFollow.query.filter_by(follower_id=current_user.id).all()
    ]

    if not followed_ids:
        return render_template(
            "timeline.html",
            grouped_timeline=[],
            platform_slugs=PLATFORM_ID_TO_SLUG,
        )

    # Fetch recent achievements from followed users
    results = (
        UserAchievement.query
        .join(Achievement, UserAchievement.achievement_id == Achievement.id)
        .join(User, UserAchievement.user_id == User.id)
        .filter(UserAchievement.user_id.in_(followed_ids))
        .filter(UserAchievement.time_unlocked.isnot(None))
        .order_by(UserAchievement.time_unlocked.desc())
        .limit(200)
        .all()
    )

    # Fill in missing Xbox achievement icons using Steam equivalents.
    resolve_xbox_icon_fallbacks([ua.achievement for ua in results])

    # Group by (user, day)
    grouped = OrderedDict()
    for ua in results:
        day = _parse_day(ua.time_unlocked)
        key = (ua.user_id, day)
        if key not in grouped:
            grouped[key] = {
                "user": ua.user,
                "day": day,
                "achievements": [],
            }
        grouped[key]["achievements"].append(ua)

    return render_template(
        "timeline.html",
        grouped_timeline=list(grouped.values()),
        platform_slugs=PLATFORM_ID_TO_SLUG,
    )


def _parse_day(time_str):
    """Extract a display-friendly date string from the stored timestamp."""
    if not time_str:
        return "Unknown date"
    try:
        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        return dt.strftime("%B %d, %Y")
    except (ValueError, AttributeError):
        # Fall back to raw string truncated to date portion
        return time_str[:10] if len(time_str) >= 10 else time_str
