from abc import ABC, abstractmethod

from app.config import settings


class EmailSender(ABC):
    @abstractmethod
    async def send_verification_mail(
        self, to: str, verification_token: str
    ) -> None: ...


class FastApiMailSender(EmailSender):
    def __init__(self) -> None:

        from fastapi_mail import ConnectionConfig, FastMail  # noqa: PLC0415

        self._mail = FastMail(
            ConnectionConfig(
                MAIL_USERNAME=settings.mail_username,
                MAIL_PASSWORD=settings.mail_password,
                MAIL_FROM=settings.mail_from,
                MAIL_PORT=settings.mail_port,
                MAIL_SERVER=settings.mail_server,
                MAIL_SSL_TLS=settings.mail_ssl_tls,
                MAIL_STARTTLS=settings.mail_starttls,
                SUPPRESS_SEND=settings.suppress_send,
            )
        )

    async def send_verification_mail(self, to: str, verification_token: str) -> None:
        from fastapi_mail import MessageSchema, MessageType  # noqa: PLC0415

        verify_url = (
            f"{settings.server_url}{settings.api_prefix}"
            f"/auth/verify?token={verification_token}"
        )

        body = f"""
            <p>
                Please verify your email by clicking on:
                <a href="{verify_url}">Verify email</a>
            </p>
            <p>
                If you did not request this, please ignore this email.
            </p>
        """

        await self._mail.send_message(
            MessageSchema(
                subject="Verify your email",
                recipients=[to],
                body=body,
                subtype=MessageType.html,
            )
        )

    async def send_password_reset_mail(self, to: str, reset_token: str) -> None:
        from fastapi_mail import MessageSchema, MessageType  # noqa: PLC0415

        reset_url = (
            f"{settings.server_url}{settings.api_prefix}"
            f"/auth/reset-password?token={reset_token}"
        )

        body = f"""
            <p>
                Please reset your password by clicking on:
                <a href="{reset_url}">Reset password</a>
            </p>
            <p>
                If you did not request this, please ignore this email.
            </p>
        """

        await self._mail.send_message(
            MessageSchema(
                subject="Reset your password",
                recipients=[to],
                body=body,
                subtype=MessageType.html,
            )
        )
