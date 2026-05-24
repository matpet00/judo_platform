import asyncio
import smtplib
from email.message import EmailMessage

from app.config import settings


def _smtp_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_from)


async def send_email(to_addresses: list[str], subject: str, body: str) -> None:
    if not _smtp_configured():
        raise RuntimeError(
            "SMTP is not configured. Set SMTP_HOST, SMTP_FROM, and optionally "
            "SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_USE_TLS in the environment.",
        )

    def _send_sync() -> None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from or ""
        msg["To"] = ", ".join(to_addresses)
        msg.set_content(body)

        host = settings.smtp_host or ""
        port = settings.smtp_port
        use_tls = settings.smtp_use_tls

        if use_tls:
            with smtplib.SMTP(host, port, timeout=30) as smtp:
                smtp.starttls()
                if settings.smtp_user and settings.smtp_password:
                    smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as smtp:
                if settings.smtp_user and settings.smtp_password:
                    smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.send_message(msg)

    await asyncio.to_thread(_send_sync)
