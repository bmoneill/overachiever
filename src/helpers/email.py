"""
Email sending helper using the MailTrap API.

Configuration is driven entirely by environment variables:

Required
--------
MAILTRAP_API_KEY
    Your API token from https://mailtrap.io/api-tokens.

Optional
--------
MAILTRAP_SENDER_EMAIL
    The ``From`` address (default: ``noreply@overachiever.app``).
MAILTRAP_SENDER_NAME
    The ``From`` display name (default: ``OverAchiever``).
MAILTRAP_USE_SANDBOX
    Set to ``true`` / ``1`` / ``yes`` to route mail through the MailTrap
    Email Sandbox instead of sending for real (default: ``false``).
MAILTRAP_INBOX_ID
    Required when ``MAILTRAP_USE_SANDBOX`` is enabled.  The numeric inbox
    ID shown in your MailTrap sandbox settings.
"""

from __future__ import annotations

import os

import mailtrap as mt

_SENDER_EMAIL: str = os.environ.get(
    "MAILTRAP_SENDER_EMAIL", "noreply@overachiever.app"
)
_SENDER_NAME: str = os.environ.get("MAILTRAP_SENDER_NAME", "OverAchiever")


def _get_client() -> mt.MailtrapClient:
    """
    Build a :class:`mailtrap.MailtrapClient` from environment variables.

    :raises KeyError: If ``MAILTRAP_API_KEY`` is not set.
    :return: A configured MailtrapClient instance.
    """
    api_key = os.environ["MAILTRAP_API_KEY"]
    use_sandbox = os.environ.get("MAILTRAP_USE_SANDBOX", "false").lower() in (
        "true",
        "1",
        "yes",
    )
    inbox_id: str | None = os.environ.get("MAILTRAP_INBOX_ID") or None

    return mt.MailtrapClient(
        token=api_key,
        sandbox=use_sandbox,
        inbox_id=inbox_id,
    )


def send_verification_email(
    to_address: str, username: str, verify_url: str
) -> None:
    """
    Send an email-verification message via MailTrap.

    :param to_address: The recipient's email address.
    :param username: The recipient's username, used in the greeting.
    :param verify_url: The full verification URL the user must click.
    :raises KeyError: If ``MAILTRAP_API_KEY`` is not configured.
    :raises Exception: Re-raises any error from the MailTrap client.
    """
    client = _get_client()

    text_body = (
        f"Hi {username},\n\n"
        "Thanks for signing up for OverAchiever!\n\n"
        "Please verify your email address by visiting the link below:\n\n"
        f"  {verify_url}\n\n"
        "This link expires in 24 hours.\n\n"
        "If you didn't create an account, you can safely ignore this email.\n\n"
        "— The OverAchiever Team"
    )

    html_body = f"""<!doctype html>
<html>
  <body style="font-family: sans-serif; max-width: 560px; margin: auto;
               padding: 2rem; color: #cdd6f4; background: #1e1e2e;">
    <h2 style="color: #cba6f7;">Welcome to OverAchiever, {username}!</h2>
    <p>Thanks for signing up. Click the button below to verify your
       email address and activate your account.</p>
    <p style="text-align: center; margin: 2rem 0;">
      <a href="{verify_url}"
         style="background: #cba6f7; color: #1e1e2e; padding: 0.75rem 1.5rem;
                border-radius: 6px; text-decoration: none; font-weight: bold;">
        Verify my email
      </a>
    </p>
    <p style="font-size: 0.85rem; color: #a6adc8;">
      Or copy this link into your browser:<br>
      <a href="{verify_url}" style="color: #89b4fa;">{verify_url}</a>
    </p>
    <p style="font-size: 0.85rem; color: #a6adc8;">
      This link expires in 24 hours. If you didn't sign up, you can
      safely ignore this email.
    </p>
  </body>
</html>"""

    mail = mt.Mail(
        sender=mt.Address(email=_SENDER_EMAIL, name=_SENDER_NAME),
        to=[mt.Address(email=to_address, name=username)],
        subject="Verify your OverAchiever email address",
        text=text_body,
        html=html_body,
    )

    client.send(mail)
