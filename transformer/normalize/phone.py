"""Phone number normalization to E.164 format using phonenumbers library."""

import logging
import phonenumbers
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def normalize_phone(
    raw_value: Optional[str],
    region_hint: Optional[str] = None
) -> Tuple[Optional[str], float, bool]:
    """
    Normalize a phone number to E.164 format.

    Args:
        raw_value: Raw phone number string (e.g., "+1-415-555-2671", "415-555-2671")
        region_hint: ISO 3166-1 alpha-2 country code for region inference (e.g., "US", "GB")

    Returns:
        Tuple of (normalized_phone, confidence, success):
        - normalized_phone: E.164 formatted string or None if parsing failed
        - confidence: 0.0–1.0 based on certainty of parse
        - success: Whether parsing succeeded

    Notes:
        - If no country code and no region_hint, defaults to "US" with low confidence (0.5)
        - Invalid phones return (None, 0.3, False)
        - Never invents a country code; missing region results in low confidence
    """
    if not raw_value or not isinstance(raw_value, str):
        return None, 0.0, False

    raw_value = raw_value.strip()
    if not raw_value:
        return None, 0.0, False

    # Default region if not provided
    if not region_hint:
        region_hint = "US"
        region_inferred = True
    else:
        region_inferred = False

    try:
        # Attempt to parse the number
        parsed = phonenumbers.parse(raw_value, region_hint)

        # Validate the parsed number
        if not phonenumbers.is_valid_number(parsed):
            logger.warning(f"Invalid phone number after parsing: {raw_value}")
            return None, 0.3, False

        # Format to E.164
        formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)

        # Confidence: lower if region was inferred
        confidence = 0.7 if region_inferred else 0.95

        return formatted, confidence, True

    except phonenumbers.NumberParseException as e:
        logger.warning(f"Failed to parse phone number '{raw_value}': {e}")
        return None, 0.3, False
    except Exception as e:
        logger.error(f"Unexpected error normalizing phone '{raw_value}': {e}")
        return None, 0.1, False
