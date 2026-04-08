"""Logout route."""

from flask import redirect, url_for
from flask_login import login_required, logout_user

from .. import app


@app.route("/logout")
@login_required
def logout():
    """Logout the user."""
    logout_user()
    return redirect(url_for("login"))
