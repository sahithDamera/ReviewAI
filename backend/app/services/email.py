import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class EmailSender(Protocol):
    async def send_verification(self, email: str, token: str) -> None: ...
    async def send_password_reset(self, email: str, token: str) -> None: ...


class ConsoleEmailSender:
    """Development sender; replace with a provider adapter in production."""

    async def send_verification(self, email: str, token: str) -> None:
        logger.warning("verification_email_queued recipient=%s token=%s", email, token)

    async def send_password_reset(self, email: str, token: str) -> None:
        logger.warning("password_reset_email_queued recipient=%s token=%s", email, token)
