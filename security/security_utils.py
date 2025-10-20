"""Security utilities for OWASP compliance and data protection."""

import hashlib
import re
import secrets
from typing import Any, Dict, List, Optional

from passlib.context import CryptContext

from observability.logger import get_logger

logger = get_logger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def sanitize_input(input_str: str, allow_special_chars: bool = False) -> str:
    """
    Sanitize user input to prevent injection attacks.

    Args:
        input_str: Input string to sanitize
        allow_special_chars: Whether to allow special characters

    Returns:
        Sanitized string
    """
    if not allow_special_chars:
        # Remove all non-alphanumeric characters except spaces and hyphens
        sanitized = re.sub(r'[^\w\s-]', '', input_str)
    else:
        # Remove potentially dangerous characters
        dangerous_chars = ['<', '>', '"', "'", ';', '&', '|', '`', '$', '(', ')']
        sanitized = input_str
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '')

    # Trim whitespace
    sanitized = sanitized.strip()

    logger.debug("Input sanitized", original_length=len(input_str), sanitized_length=len(sanitized))

    return sanitized


def detect_pii(text: str) -> Dict[str, List[str]]:
    """
    Detect personally identifiable information (PII) in text.

    Args:
        text: Text to analyze

    Returns:
        Dict with detected PII types and values
    """
    pii_detected: Dict[str, List[str]] = {
        "emails": [],
        "phone_numbers": [],
        "ssn": [],
        "credit_cards": [],
        "ip_addresses": [],
    }

    # Email detection
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    pii_detected["emails"] = re.findall(email_pattern, text)

    # Phone number detection (US format)
    phone_pattern = r'\b(?:\+?1[-.]?)?\(?([0-9]{3})\)?[-.]?([0-9]{3})[-.]?([0-9]{4})\b'
    pii_detected["phone_numbers"] = [
        '-'.join(match) for match in re.findall(phone_pattern, text)
    ]

    # SSN detection (US format)
    ssn_pattern = r'\b\d{3}-\d{2}-\d{4}\b'
    pii_detected["ssn"] = re.findall(ssn_pattern, text)

    # Credit card detection (basic pattern)
    cc_pattern = r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'
    pii_detected["credit_cards"] = re.findall(cc_pattern, text)

    # IP address detection
    ip_pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
    pii_detected["ip_addresses"] = re.findall(ip_pattern, text)

    # Log if PII detected
    total_pii = sum(len(v) for v in pii_detected.values())
    if total_pii > 0:
        logger.warning("PII detected in text", pii_types=list(pii_detected.keys()), count=total_pii)

    return pii_detected


def has_pii(text: str) -> bool:
    """
    Check if text contains any PII.

    Args:
        text: Text to check

    Returns:
        True if PII detected, False otherwise
    """
    pii = detect_pii(text)
    return any(len(v) > 0 for v in pii.values())


def redact_pii(text: str) -> str:
    """
    Redact PII from text.

    Args:
        text: Text to redact

    Returns:
        Text with PII redacted
    """
    pii = detect_pii(text)

    redacted = text

    # Redact emails
    for email in pii["emails"]:
        redacted = redacted.replace(email, "[EMAIL_REDACTED]")

    # Redact phone numbers
    for phone in pii["phone_numbers"]:
        redacted = redacted.replace(phone, "[PHONE_REDACTED]")

    # Redact SSNs
    for ssn in pii["ssn"]:
        redacted = redacted.replace(ssn, "[SSN_REDACTED]")

    # Redact credit cards
    for cc in pii["credit_cards"]:
        redacted = redacted.replace(cc, "[CC_REDACTED]")

    # Redact IP addresses
    for ip in pii["ip_addresses"]:
        redacted = redacted.replace(ip, "[IP_REDACTED]")

    return redacted


def validate_input(
    input_data: Any,
    max_length: Optional[int] = None,
    allowed_types: Optional[List[type]] = None,
    required_fields: Optional[List[str]] = None,
) -> tuple[bool, Optional[str]]:
    """
    Validate input data against security constraints.

    Args:
        input_data: Data to validate
        max_length: Maximum length for string inputs
        allowed_types: List of allowed types
        required_fields: Required fields for dict inputs

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Type validation
    if allowed_types and type(input_data) not in allowed_types:
        return False, f"Invalid type: {type(input_data).__name__}"

    # String length validation
    if isinstance(input_data, str) and max_length:
        if len(input_data) > max_length:
            return False, f"Input exceeds maximum length of {max_length}"

    # Required fields validation for dicts
    if isinstance(input_data, dict) and required_fields:
        missing_fields = [field for field in required_fields if field not in input_data]
        if missing_fields:
            return False, f"Missing required fields: {', '.join(missing_fields)}"

    return True, None


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key for secure storage.

    Args:
        api_key: API key to hash

    Returns:
        Hashed API key
    """
    return pwd_context.hash(api_key)


def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    """
    Verify an API key against its hash.

    Args:
        plain_key: Plain text API key
        hashed_key: Hashed API key

    Returns:
        True if key matches, False otherwise
    """
    return pwd_context.verify(plain_key, hashed_key)


def generate_api_key(length: int = 32) -> str:
    """
    Generate a secure random API key.

    Args:
        length: Length of the API key

    Returns:
        Generated API key
    """
    return secrets.token_urlsafe(length)


def generate_salt() -> str:
    """
    Generate a cryptographic salt.

    Returns:
        Generated salt
    """
    return secrets.token_hex(16)


def hash_with_salt(data: str, salt: str) -> str:
    """
    Hash data with a salt.

    Args:
        data: Data to hash
        salt: Salt to use

    Returns:
        Hashed data
    """
    salted = f"{data}{salt}"
    return hashlib.sha256(salted.encode()).hexdigest()


# OWASP Compliance Checklist (as comments for reference)
"""
OWASP Top 10 Security Considerations:

1. Injection Prevention:
   - Use parameterized queries (implemented in DatabaseQueryTool)
   - Sanitize all user inputs (sanitize_input function)
   - Validate input types and lengths (validate_input function)

2. Broken Authentication:
   - Use strong password hashing (bcrypt via passlib)
   - Implement API key authentication (hash_api_key, verify_api_key)
   - Use secure random generation (secrets module)

3. Sensitive Data Exposure:
   - Detect and redact PII (detect_pii, redact_pii functions)
   - Use HTTPS in production (configured in deployment)
   - Store secrets securely (AWS Secrets Manager in production)

4. XML External Entities (XXE):
   - Not applicable (no XML processing in this template)

5. Broken Access Control:
   - Implement API key authentication (middleware.py)
   - Rate limiting (RateLimitMiddleware)
   - CORS configuration (settings.py)

6. Security Misconfiguration:
   - Environment-based configuration (settings.py)
   - Secure defaults in production
   - Disable debug mode in production

7. Cross-Site Scripting (XSS):
   - Input sanitization (sanitize_input)
   - Output encoding (FastAPI handles this)

8. Insecure Deserialization:
   - Use Pydantic for validation (models.py)
   - Validate all incoming data

9. Using Components with Known Vulnerabilities:
   - Keep dependencies updated (pyproject.toml)
   - Regular security audits

10. Insufficient Logging & Monitoring:
    - Structured logging (observability/logger.py)
    - Metrics collection (observability/metrics.py)
    - CloudWatch integration for production
"""

