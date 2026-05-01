"""
Routes for email verification.

Handles three concerns:
- Consuming a verification token from a link in an email.
- Showing the "check your inbox" holding page after registration.
- Resending a verification email for users whose token has expired.
"""

from __future__ import annotations

from flask import flash, redirect, render_template, request, session, url_for

from .. import app
from ..helpers.email import send_verification_email
from ..models import db
from ..models.email_verification_token import EmailVerificationToken
from ..models.user import User


@app.route("/verify-email/<string:token>")
def verify_email(token: str):
    """
    Verify a user's email address using the token from their verification email.

    Looks up the token, checks it has not expired, marks the associated user's
    email as verified, deletes the token, and redirects to the login page with
    a success message.

    :param token: The URL-safe verification token from the email link.
    """
    record: EmailVerificationToken | None = (
        EmailVerificationToken.query.filter_by(token=token).first()
    )

    if record is None or record.is_expired:
        if record is not None:
            db.session.delete(record)
            db.session.commit()
        flash(
            "This verification link is invalid or has expired. "
            "Please request a new one.",
            "error",
        )
        return redirect(url_for("login"))

    user: User | None = db.session.get(User, record.user_id)
    if user is None:
        db.session.delete(record)
        db.session.commit()
        flash("User not found.", "error")
        return redirect(url_for("login"))

    user.email_verified = True
    db.session.delete(record)
    session.pop("pending_verification_user_id", None)
    db.session.commit()

    flash("Your email has been verified! You can now log in.", "success")
    return redirect(url_for("login"))


@app.route("/verify-email-sent")
def verify_email_sent():
    """
    Render the 'check your inbox' page shown after registration.

    The pending user's email address is fetched from the session so it can
    be displayed in the template.  If no pending user is found the visitor is
    redirected to the login page.
    """
    user_id: int | None = session.get("pending_verification_user_id")
    if not user_id:
        return redirect(url_for("login"))

    user: User | None = db.session.get(User, user_id)
    if user is None or user.email_verified:
        session.pop("pending_verification_user_id", None)
        return redirect(url_for("login"))

    return render_template("verify_email_sent.html", email=user.email)


@app.route("/resend-verification", methods=["POST"])
def resend_verification():
    """
    Resend a verification email to the user stored in the session.

    Generates a fresh token (revoking any existing one), sends the email,
    and redirects back to the 'check your inbox' page.
    """
    user_id: int | None = session.get("pending_verification_user_id")
    if not user_id:
        flash(
            "No pending verification found. Please register or log in.",
            "error",
        )
        return redirect(url_for("login"))

    user: User | None = db.session.get(User, user_id)
    if user is None or user.email_verified:
        session.pop("pending_verification_user_id", None)
        return redirect(url_for("login"))

    token_record = EmailVerificationToken.create_for_user(user.id)
    db.session.commit()

    verify_url = url_for(
        "verify_email", token=token_record.token, _external=True
    )

    try:
        send_verification_email(user.email, user.username, verify_url)
        flash(
            "A new verification email has been sent. Please check your inbox.",
            "success",
        )
    except Exception:
        flash(
            "Failed to send verification email. Please try again later.",
            "error",
        )

    return redirect(url_for("verify_email_sent"))
