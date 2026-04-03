from flask import redirect, url_for
from flask_login import current_user, login_required

from .. import app


@app.route("/my-games")
@login_required
def my_games():
    """Redirect to the current user's games page."""
    return redirect(url_for("games", username=current_user.username))
