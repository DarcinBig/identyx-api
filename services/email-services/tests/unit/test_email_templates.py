"""Unit tests for email-service templates, URLs and SMTP delegation."""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import get_settings
from app.schemas.email import (
    SendEmailChangeEmailRequest,
    SendNewLoginEmailRequest,
    SendVerificationEmailRequest,
)
from app.services.email_service import EmailService

settings = get_settings()


def _svc():
    return EmailService()


class TestVerificationEmail:
    @pytest.mark.asyncio
    async def test_success_sends_to_email_with_token_in_url(self):
        with patch("app.services.email_service.send_email", new=AsyncMock(return_value=True)) as send:
            result = await _svc().send_verification_email(
                SendVerificationEmailRequest(
                    email="user@example.com",
                    username="user",
                    verification_token="tok.abc",
                )
            )
        assert result.sent is True
        assert result.email == "user@example.com"
        send.assert_awaited_once()
        kwargs = send.await_args.kwargs
        to_email, subject, html_content = kwargs["to_email"], kwargs["subject"], kwargs["html_content"]
        assert to_email == "user@example.com"
        assert "Verify your email" in subject
        assert f"{settings.app_base_url}/v1/auth/verify-email?token=tok.abc" in html_content
        assert "user" in html_content

    @pytest.mark.asyncio
    async def test_smtp_failure_returns_sent_false(self):
        with patch("app.services.email_service.send_email", new=AsyncMock(return_value=False)):
            result = await _svc().send_verification_email(
                SendVerificationEmailRequest(
                    email="user@example.com",
                    username="user",
                    verification_token="tok.abc",
                )
            )
        assert result.sent is False
        assert "Failed" in result.message


class TestNewLoginEmail:
    @pytest.mark.asyncio
    async def test_includes_geolocated_location(self):
        with patch("app.services.email_service.send_email", new=AsyncMock(return_value=True)) as send:
            result = await _svc().send_new_login_email(
                SendNewLoginEmailRequest(
                    email="user@example.com",
                    username="user",
                    device_info="Chrome on Linux",
                    client_ip="8.8.8.8",
                    login_time="2026-08-10T12:00:00",
                    location="Paris, France",
                )
            )
        assert result.sent is True
        kwargs = send.await_args.kwargs
        subject, html_content = kwargs["subject"], kwargs["html_content"]
        assert "New login" in subject
        assert "Paris, France" in html_content
        assert "8.8.8.8" in html_content


class TestEmailChangeEmail:
    @pytest.mark.asyncio
    async def test_token_url_points_to_confirm_email_change(self):
        with patch("app.services.email_service.send_email", new=AsyncMock(return_value=True)) as send:
            await _svc().send_email_change_email(
                SendEmailChangeEmailRequest(
                    email="new@example.com",
                    username="user",
                    email_change_token="tok.change",
                )
            )
        kwargs = send.await_args.kwargs
        subject, html_content = kwargs["subject"], kwargs["html_content"]
        assert "Confirm your new email address" in subject
        assert f"{settings.app_base_url}/v1/auth/confirm-email-change?token=tok.change" in html_content


class TestTemplateRender:
    """All email templates must render without Jinja errors."""

    @pytest.mark.asyncio
    async def test_all_templates_render(self):
        send = AsyncMock(return_value=True)
        with patch("app.services.email_service.send_email", send):
            await _svc().send_verification_email(
                SendVerificationEmailRequest(email="a@b.com", username="u", verification_token="t")
            )
            await _svc().send_new_login_email(
                SendNewLoginEmailRequest(
                    email="a@b.com", username="u", device_info="d", client_ip="1.2.3.4",
                    login_time="t", location="loc",
                )
            )
            await _svc().send_email_change_email(
                SendEmailChangeEmailRequest(email="a@b.com", username="u", email_change_token="t")
            )
        assert send.await_count == 3
