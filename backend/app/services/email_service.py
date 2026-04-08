
from email.message import EmailMessage
import smtplib

from app.core.config import settings


def send_verification_email(to_email: str, token: str) -> None:
    verify_link = f"{settings.frontend_url}/verify-email?token={token}"

    msg = EmailMessage()
    msg["Subject"] = "dropoff: verify your email"
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.set_content(
        f"""Welcome to dropoff!

Open this link to verify your email:
{verify_link}

If you did not create this account, ignore this email.
"""
    )

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        smtp.send_message(msg)