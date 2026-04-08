from flask import render_template, request

from .. import app
from ..models.user import User


@app.route("/search")
def user_search():
    """Search for users by Overachiever username."""
    q = request.args.get("q", "").strip()
    results = []
    if q:
        results = (
            User.query.filter(User.username.ilike(f"%{q}%"))
            .order_by(User.username)
            .limit(20)
            .all()
        )
    return render_template("search_results.html", query=q, results=results)
