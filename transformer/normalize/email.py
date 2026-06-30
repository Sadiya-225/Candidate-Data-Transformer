"""Email normalization: lowercase, validation, deduplication."""

import logging
import re
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Simple email regex (RFC 5322 basic subset)
EMAIL_REGEX = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"


def normalize_email(raw_value: Optional[str]) -> Tuple[Optional[str], float, bool]:
    """
    Normalize an email address: lowercase, validate format, dedup.

    Args:
        raw_value: Email string (e.g., "John.Doe@Example.COM", "john@example.com")

    Returns:
        Tuple of (normalized_email, confidence, success):
        - normalized_email: Lowercase, valid email or None
        - confidence: 0.0–1.0
        - success: Whether normalization succeeded

    Notes:
        - Always lowercase
        - Validates against basic RFC 5322 regex
        - Invalid emails return (None, 0.3, False)
    """
    if not raw_value or not isinstance(raw_value, str):
        return None, 0.0, False

    raw_value = raw_value.strip()
    if not raw_value:
        return None, 0.0, False

    # Lowercase
    normalized = raw_value.lower()

    # Validate format
    if not re.match(EMAIL_REGEX, normalized):
        logger.warning(f"Invalid email format: {raw_value}")
        return None, 0.3, False

    return normalized, 0.95, True
