"""Unit tests for security utilities."""

import pytest

from security.security_utils import (
    sanitize_input,
    detect_pii,
    has_pii,
    redact_pii,
    validate_input,
    hash_api_key,
    verify_api_key,
    generate_api_key,
)


class TestInputSanitization:
    """Test input sanitization."""

    def test_sanitize_basic_input(self) -> None:
        """Test sanitizing basic input."""
        result = sanitize_input("Hello World")
        assert result == "Hello World"

    def test_sanitize_special_chars(self) -> None:
        """Test removing special characters."""
        result = sanitize_input("Hello<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "alert" in result

    def test_sanitize_with_allowed_chars(self) -> None:
        """Test sanitization with allowed special chars."""
        result = sanitize_input("test@example.com", allow_special_chars=True)
        assert "@" in result
        assert "." in result


class TestPIIDetection:
    """Test PII detection."""

    def test_detect_email(self) -> None:
        """Test detecting email addresses."""
        text = "Contact me at john.doe@example.com"
        pii = detect_pii(text)

        assert len(pii["emails"]) == 1
        assert "john.doe@example.com" in pii["emails"]

    def test_detect_phone(self) -> None:
        """Test detecting phone numbers."""
        text = "Call me at 555-123-4567"
        pii = detect_pii(text)

        assert len(pii["phone_numbers"]) > 0

    def test_detect_ssn(self) -> None:
        """Test detecting SSN."""
        text = "My SSN is 123-45-6789"
        pii = detect_pii(text)

        assert len(pii["ssn"]) == 1

    def test_has_pii(self) -> None:
        """Test checking if text has PII."""
        text_with_pii = "Email: test@example.com"
        text_without_pii = "Hello world"

        assert has_pii(text_with_pii) is True
        assert has_pii(text_without_pii) is False

    def test_redact_pii(self) -> None:
        """Test redacting PII."""
        text = "Contact john.doe@example.com or call 555-123-4567"
        redacted = redact_pii(text)

        assert "john.doe@example.com" not in redacted
        assert "[EMAIL_REDACTED]" in redacted
        assert "[PHONE_REDACTED]" in redacted


class TestInputValidation:
    """Test input validation."""

    def test_validate_string_length(self) -> None:
        """Test validating string length."""
        valid, error = validate_input("short", max_length=10)
        assert valid is True
        assert error is None

        invalid, error = validate_input("very long string", max_length=5)
        assert invalid is False
        assert "maximum length" in error.lower()

    def test_validate_type(self) -> None:
        """Test validating input type."""
        valid, error = validate_input("test", allowed_types=[str])
        assert valid is True

        invalid, error = validate_input(123, allowed_types=[str])
        assert invalid is False

    def test_validate_required_fields(self) -> None:
        """Test validating required fields."""
        data = {"field1": "value1", "field2": "value2"}
        valid, error = validate_input(data, required_fields=["field1", "field2"])
        assert valid is True

        invalid_data = {"field1": "value1"}
        invalid, error = validate_input(invalid_data, required_fields=["field1", "field2"])
        assert invalid is False
        assert "missing required fields" in error.lower()


class TestAPIKeyManagement:
    """Test API key management."""

    def test_hash_api_key(self) -> None:
        """Test hashing API key."""
        api_key = "test-api-key-123"
        hashed = hash_api_key(api_key)

        assert hashed != api_key
        assert len(hashed) > len(api_key)

    def test_verify_api_key(self) -> None:
        """Test verifying API key."""
        api_key = "test-api-key-123"
        hashed = hash_api_key(api_key)

        assert verify_api_key(api_key, hashed) is True
        assert verify_api_key("wrong-key", hashed) is False

    def test_generate_api_key(self) -> None:
        """Test generating API key."""
        key1 = generate_api_key()
        key2 = generate_api_key()

        assert len(key1) > 0
        assert len(key2) > 0
        assert key1 != key2  # Should be unique

