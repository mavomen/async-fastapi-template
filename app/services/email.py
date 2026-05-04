"""Email service with Jinja2 template rendering."""

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from app.core.config import settings

logger = logging.getLogger("app.email")

# Template directory relative to this file
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "email"
env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))


class EmailService:
    """Send emails using templates. Currently simulates sending."""

    async def send_email(
        self,
        to_email: str,
        subject: str,
        template_name: str,
        context: dict | None = None,
    ) -> None:
        """Render template and send (or simulate)."""
        template = env.get_template(template_name)
        html = template.render(context or {})
        # In production, integrate with SMTP (e.g., aiomail, aiosmtplib)
        logger.info("Email sent (simulated)", extra={"to": to_email, "subject": subject})
        logger.debug("Email body: %s", html)

    async def send_verification_email(self, to_email: str, token: str) -> None:
        """Send email with verification link."""
        verification_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
        await self.send_email(
            to_email,
            "Verify your email",
            "verification.html",
            {"verification_url": verification_url},
        )


# Singleton instance for dependency injection
email_service = EmailService()
