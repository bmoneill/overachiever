"""Login route."""

from flask import flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user
from werkzeug.security import check_password_hash

from .. import app
from ._helpers import ALLOW_REGISTRATION, get_user_by_username


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Render the login page and handle login form submission.

    Blocks login for accounts whose email address has not yet been verified
    and offers a link to resend the verification email.
    """
    if current_user.is_authenticated:
        return redirect(url_for("my_games"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Please fill in all fields.", "error")
            return redirect(url_for("login"))

        user = get_user_by_username(username)
        if user is None or not check_password_hash(
            user.password_hash, password
        ):
            flash("Invalid username or password.", "error")
            return redirect(url_for("login"))

        if not user.email_verified:
            # Store the user in the session so the resend page can pick it up.
            session["pending_verification_user_id"] = user.id
            flash(
                "Please verify your email address before logging in. "
                "Check your inbox or request a new verification email.",
                "error",
            )
            return redirect(url_for("verify_email_sent"))

        login_user(user)
        next_page = request.args.get("next")
        return redirect(next_page or url_for("my_games"))

    return render_template("login.html", allow_registration=ALLOW_REGISTRATION)
