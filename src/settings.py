from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from . import app
from .db import get_db
from .api.xbox import XboxProfileAPI
from .api.steam import SteamProfileAPI
from .api.profile import ProfileAPIError


@app.route("/settings")
@login_required
def settings():
    """User settings page with linked platform accounts."""
    xbox_profile = None
    if current_user.xuid:
        try:
            api = XboxProfileAPI()
            xbox_profile = api.get_user_profile(current_user.xuid)
        except ProfileAPIError:
            # If we can't fetch the profile, just show XUID
            pass

    steam_profile = None
    if current_user.steam_id:
        try:
            api = SteamProfileAPI()
            steam_profile = api.get_user_profile(current_user.steam_id)
        except ProfileAPIError:
            # If we can't fetch the profile, just show Steam ID
            pass

    return render_template(
        "settings.html",
        xbox_profile=xbox_profile,
        steam_profile=steam_profile,
    )


@app.route("/settings/xbox/link", methods=["POST"])
@login_required
def xbox_link():
    """Link an Xbox account by manually entering a XUID."""
    xuid = request.form.get("xuid", "").strip()
    if not xuid:
        flash("Please enter a valid XUID.", "error")
        return redirect(url_for("settings"))

    if current_user.xuid:
        flash("Your Xbox account is already linked.", "error")
        return redirect(url_for("settings"))

    if not xuid.isdigit():
        flash("XUID must be a numeric value.", "error")
        return redirect(url_for("settings"))

    # Check if this XUID is already linked to another account
    db = get_db()
    existing = db.execute(
        "SELECT id, username FROM users WHERE xuid = ? AND id != ?",
        (xuid, current_user.id),
    ).fetchone()
    if existing:
        flash("This Xbox account is already linked to another user.", "error")
        return redirect(url_for("settings"))

    # Store the XUID
    db.execute("UPDATE users SET xuid = ? WHERE id = ?", (xuid, current_user.id))
    db.commit()

    flash("Xbox account linked successfully!", "success")
    return redirect(url_for("settings"))


@app.route("/settings/xbox/unlink", methods=["POST"])
@login_required
def xbox_unlink():
    """Unlink the user's Xbox account (set XUID to NULL)."""
    db = get_db()
    db.execute("UPDATE users SET xuid = NULL WHERE id = ?", (current_user.id,))
    db.commit()
    flash("Xbox account unlinked.", "success")
    return redirect(url_for("settings"))


@app.route("/settings/steam/link", methods=["POST"])
@login_required
def steam_link():
    """Link a Steam account by resolving a vanity username to a Steam ID."""
    vanity = request.form.get("vanity_url", "").strip()
    if not vanity:
        flash("Please enter a Steam vanity username.", "error")
        return redirect(url_for("settings"))

    if current_user.steam_id:
        flash("Your Steam account is already linked.", "error")
        return redirect(url_for("settings"))

    # Resolve vanity URL to Steam ID
    try:
        api = SteamProfileAPI()
        steam_id = api.resolve_vanity_url(vanity)
    except ProfileAPIError as exc:
        flash(f"Could not resolve Steam username: {exc}", "error")
        return redirect(url_for("settings"))

    # Check if this Steam ID is already linked to another account
    db = get_db()
    existing = db.execute(
        "SELECT id, username FROM users WHERE steam_id = ? AND id != ?",
        (steam_id, current_user.id),
    ).fetchone()
    if existing:
        flash("This Steam account is already linked to another user.", "error")
        return redirect(url_for("settings"))

    # Store the Steam ID
    db.execute("UPDATE users SET steam_id = ? WHERE id = ?", (steam_id, current_user.id))
    db.commit()

    flash("Steam account linked successfully!", "success")
    return redirect(url_for("settings"))


@app.route("/settings/steam/unlink", methods=["POST"])
@login_required
def steam_unlink():
    """Unlink the user's Steam account (set steam_id to NULL)."""
    db = get_db()
    db.execute("UPDATE users SET steam_id = NULL WHERE id = ?", (current_user.id,))
    db.commit()
    flash("Steam account unlinked.", "success")
    return redirect(url_for("settings"))
