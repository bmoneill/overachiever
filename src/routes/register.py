"""Register route."""

from flask import flash, redirect, render_template, request, session, url_for
from flask_login import current_user
from werkzeug.security import generate_password_hash

from .. import app
from ..helpers.email import send_verification_email
from ..models import db
from ..models.email_verification_token import EmailVerificationToken
from ..models.user import User
from ._helpers import ALLOW_REGISTRATION


@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Render the registration form and handle new account creation.

    On successful submission the user account is created in an unverified
    state, a one-time verification token is generated, a verification email
    is dispatched via MailTrap, and the user is redirected to the
    'check your inbox' holding page.
    """
    if not ALLOW_REGISTRATION:
        flash("Registration is currently disabled.", "error")
        return redirect(url_for("login"))

    if current_user.is_authenticated:
        return redirect(url_for("my_games"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("Please fill in all fields.", "error")
            return redirect(url_for("register"))

        existing = User.query.filter(
            db.or_(User.username == username, User.email == email)
        ).first()
        if existing:
            flash("Username or email is already taken.", "error")
            return redirect(url_for("register"))

        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            email_verified=False,
        )
        db.session.add(new_user)
        # Flush to obtain new_user.id before committing.
        db.session.flush()

        token_record = EmailVerificationToken.create_for_user(new_user.id)
        db.session.commit()

        verify_url = url_for(
            "verify_email", token=token_record.token, _external=True
        )

        try:
            send_verification_email(email, username, verify_url)
        except Exception:
            # Don't block registration if the email send fails; the user can
            # request a resend from the holding page.
            flash(
                "Account created, but we couldn't send the verification "
                "email. You can request a new one below.",
                "warning",
            )

        session["pending_verification_user_id"] = new_user.id
        return redirect(url_for("verify_email_sent"))

    return render_template("register.html")
