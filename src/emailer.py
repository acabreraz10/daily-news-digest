"""
Email Sender
Sends formatted emails via Outlook/Office 365 SMTP.
"""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def get_email_config() -> dict:
    """
    Load email configuration from environment variables.

    Required env vars:
        EMAIL_SENDER: The sender email address (your Outlook address)
        EMAIL_PASSWORD: App password or account password
        EMAIL_RECIPIENT: The recipient email address (can be same as sender)

    Optional env vars:
        SMTP_SERVER: Override SMTP server (default: smtp.office365.com)
        SMTP_PORT: Override SMTP port (default: 587)

    Returns:
        Dictionary with email configuration.

    Raises:
        ValueError: If required environment variables are not set.
    """
    sender = os.environ.get("EMAIL_SENDER")
    password = os.environ.get("EMAIL_PASSWORD")
    recipient = os.environ.get("EMAIL_RECIPIENT")

    if not sender or not password or not recipient:
        missing = []
        if not sender:
            missing.append("EMAIL_SENDER")
        if not password:
            missing.append("EMAIL_PASSWORD")
        if not recipient:
            missing.append("EMAIL_RECIPIENT")
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}. "
            f"Set these in your .env file or GitHub secrets."
        )

    return {
        "sender": sender,
        "password": password,
        "recipient": recipient,
        "smtp_server": os.environ.get("SMTP_SERVER", "smtp.office365.com"),
        "smtp_port": int(os.environ.get("SMTP_PORT", "587")),
    }


def send_email(
    subject: str,
    html_body: str,
    plain_text_body: str = "",
) -> bool:
    """
    Send an email via SMTP (Office 365 / Outlook).

    Args:
        subject: Email subject line.
        html_body: HTML content of the email.
        plain_text_body: Plain text fallback content.

    Returns:
        True if email was sent successfully, False otherwise.
    """
    try:
        config = get_email_config()
    except ValueError as e:
        logger.error(f"Email config error: {e}")
        return False

    # Build MIME message
    msg = MIMEMultipart("alternative")
    msg["From"] = config["sender"]
    msg["To"] = config["recipient"]
    msg["Subject"] = subject

    # Attach plain text fallback first, then HTML (email clients prefer last)
    if plain_text_body:
        msg.attach(MIMEText(plain_text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        logger.info(
            f"Connecting to {config['smtp_server']}:{config['smtp_port']}..."
        )

        with smtplib.SMTP(config["smtp_server"], config["smtp_port"]) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(config["sender"], config["password"])
            server.sendmail(
                config["sender"],
                config["recipient"],
                msg.as_string(),
            )

        logger.info(f"Email sent successfully: '{subject}' -> {config['recipient']}")
        return True

    except smtplib.SMTPAuthenticationError as e:
        logger.error(
            f"SMTP authentication failed. Check your EMAIL_PASSWORD. "
            f"For Outlook, you may need an App Password. Error: {e}"
        )
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error sending email: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending email: {e}")
        return False
