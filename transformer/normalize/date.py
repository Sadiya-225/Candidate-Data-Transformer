"""Date normalization to YYYY-MM format."""

import logging
import re
from typing import Optional, Tuple
from datetime import datetime, timedelta, timezone
from dateutil import parser as dateutil_parser

logger = logging.getLogger(__name__)


def normalize_date(
    raw_value: Optional[str],
    date_type: str = "start"
) -> Tuple[Optional[str], float, bool]:
    """
    Normalize a date to YYYY-MM format.

    Args:
        raw_value: Date string in various formats (e.g., "2023-05", "May 2023", "05/01/2023", "2 years ago")
        date_type: "start" or "end" to hint how to handle partial dates
                   - "start": missing day → 01 (first of month)
                   - "end": missing day → last day of month

    Returns:
        Tuple of (normalized_date, confidence, success):
        - normalized_date: YYYY-MM format or None if unparseable
        - confidence: 0.0–1.0 based on certainty (lower for heuristics)
        - success: Whether parsing succeeded

    Notes:
        - Accepts ISO 8601, US M/D/YYYY, "Month YYYY", relative ("2 years ago")
        - Ambiguous dates (01/02/2020) interpreted as US (M/D/Y)
        - Heuristic-derived dates get lower confidence
    """
    if not raw_value or not isinstance(raw_value, str):
        return None, 0.0, False

    raw_value = raw_value.strip()
    if not raw_value:
        return None, 0.0, False

    # Check for relative date patterns first ("2 years ago", "6 months ago", etc.)
    relative_match = re.match(r"(\d+)\s*(?:years?|months?|days?)\s*ago", raw_value, re.IGNORECASE)
    if relative_match:
        return _parse_relative_date(relative_match.group(1), raw_value)

    # Try dateutil parser (handles most formats)
    try:
        parsed_date = dateutil_parser.parse(raw_value, fuzzy=False)
        formatted = parsed_date.strftime("%Y-%m")
        return formatted, 0.9, True
    except (ValueError, TypeError):
        pass

    # Try fuzzy parsing (may have extra text)
    try:
        parsed_date = dateutil_parser.parse(raw_value, fuzzy=True)
        formatted = parsed_date.strftime("%Y-%m")
        return formatted, 0.7, True  # Lower confidence due to fuzzy parsing
    except (ValueError, TypeError):
        pass

    # Last resort: try simple pattern matches
    # YYYY-MM or YYYY/MM or YYYY-M or YYYY/M
    simple_match = re.match(r"(\d{4})[-/](\d{1,2})", raw_value)
    if simple_match:
        year, month = simple_match.groups()
        try:
            # Validate month
            month_int = int(month)
            if 1 <= month_int <= 12:
                return f"{year}-{month_int:02d}", 0.8, True
        except ValueError:
            pass

    logger.warning(f"Could not parse date: {raw_value}")
    return None, 0.2, False


def _parse_relative_date(duration_str: str, original: str) -> Tuple[Optional[str], float, bool]:
    """Parse relative dates like '2 years ago'."""
    try:
        duration = int(duration_str)
        now = datetime.now(timezone.utc)

        if "year" in original.lower():
            target_date = now - timedelta(days=duration * 365)
        elif "month" in original.lower():
            target_date = now - timedelta(days=duration * 30)
        elif "day" in original.lower():
            target_date = now - timedelta(days=duration)
        else:
            return None, 0.0, False

        formatted = target_date.strftime("%Y-%m")
        return formatted, 0.6, True  # Lower confidence for heuristic
    except (ValueError, TypeError):
        logger.warning(f"Failed to parse relative date: {original}")
        return None, 0.2, False
