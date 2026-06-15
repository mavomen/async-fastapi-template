"""Email service with Jinja2 template rendering."""

import logging
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from app.core.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger("app.email")

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "email"
env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))


class EmailService:
    """Send emails using templates. Currently simulates sending."""

    async def send_email(
        self,
        to_email: str,
        subject: str,
        template_name: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Render template and send email (simulated)."""
        template = env.get_template(template_name)
        html = template.render(context or {})
        logger.info("Email sent (simulated)", extra={"to": to_email, "subject": subject})
        logger.debug("Email body: %s", html)

    async def send_verification_email(self, to_email: str, token: str) -> None:
        verification_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
        await self.send_email(
            to_email,
            "Verify your email",
            "verification.html",
            {"verification_url": verification_url},
        )


email_service = EmailService()


@celery_app.task(bind=True, max_retries=5, default_retry_delay=60)  # type: ignore[untyped-decorator]
def send_email_with_retry(
    self: Any,
    to_email: str,
    subject: str,
    template_name: str,
    context: dict[str, Any] | None = None,
) -> None:
    """
    Celery task that sends an email with exponential backoff retry.
    Retries up to 5 times, doubling the delay each time.
    """
    try:
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(email_service.send_email(to_email, subject, template_name, context))
    except Exception as exc:
        logger.exception("Email send failed, retrying...")
        raise self.retry(exc=exc, countdown=2**self.request.retries * 60)
