import smtplib
from email.message import EmailMessage

from app.core.config import settings


def send_email(
    *,
    to_email: str,
    subject: str,
    body: str,
) -> None:
    message = EmailMessage()
    message["From"] = settings.SMTP_FROM
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
        smtp.send_message(message)