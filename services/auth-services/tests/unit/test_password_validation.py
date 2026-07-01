"""Unit tests for password validation."""
import pytest


class TestPasswordValidation:
    """
    Tests password validation without touching the database.
    The private method or validation logic is tested directly.
    """
    @pytest.mark.parametrize("password, should_pass", [
        ("TestPassword@1", True),   # valid
        ("Valid@Password9", True),  # valid
        ("short", False),           # too short
        ("nouppercase1@", False),   # no uppercase
        ("NOLOWERCASE@", False),    # no lowercase
        ("NoSpecial1", False),      # no special character
        ("NoNumber", False),        # no number
        ("", False),                # empty
    ])
    def test_password_validation(self, password, should_pass):
        from pydantic import ValidationError

        from app.schemas.auth import RegisterRequest

        try:
            RegisterRequest(
                email="test@example.com",
                username="testuser",
                password=password,
            )
            assert should_pass, f"Password '{password}' should have failed."
        except ValidationError:
            assert not should_pass, f"Password '{password}' should have passed."