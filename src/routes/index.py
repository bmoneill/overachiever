from flask import redirect, render_template, url_for
from flask_login import current_user

from .. import app
from ..models.guide import Guide
from ..models.user import User
from ..helpers.platform import PLATFORM_ID_MAP


@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("timeline"))

    recent_guides = (
        Guide.query
        .order_by(Guide.created_at.desc())
        .limit(5)
        .all()
    )

    top_achievers = (
        User.query
        .filter(User.achievement_count > 0)
        .order_by(User.achievement_count.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "index.html",
        recent_guides=recent_guides,
        platform_slugs=PLATFORM_ID_MAP,
        top_achievers=top_achievers,
    )
