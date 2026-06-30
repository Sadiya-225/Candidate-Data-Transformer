"""Years of experience normalization: parse and round to 0.5-year precision."""

import logging
import re
from typing import Optional, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def normalize_years_experience(
    raw_value: Optional[str],
    derived_from_dates: bool = False
) -> Tuple[Optional[float], float, bool]:
    """
    Normalize years of experience to a float (0.5-year precision).

    Args:
        raw_value: Years of experience as string (e.g., "5", "5.5", "5-7 years", "5 years")
        derived_from_dates: Whether this value was derived from date range calculations (higher confidence)

    Returns:
        Tuple of (years_exp, confidence, success):
        - years_exp: Float rounded to 0.5 precision (e.g., 5.0, 5.5, 7.0) or None
        - confidence: 0.0–1.0 (higher if derived from dates, lower if heuristic)
        - success: Whether parsing succeeded

    Notes:
        - Accepts: "5", "5.5", "5-7 years", "approx 5 years", etc.
        - Rounds to nearest 0.5 year
        - Date-derived values get confidence 0.9
        - Explicit values get confidence 0.85
        - Heuristic values get confidence 0.6
    """
    if not raw_value or not isinstance(raw_value, str):
        return None, 0.0, False

    raw_value = raw_value.strip()
    if not raw_value:
        return None, 0.0, False

    # Try to extract numeric value
    years = _extract_years(raw_value)

    if years is None:
        logger.warning(f"Could not parse years of experience: {raw_value}")
        return None, 0.2, False

    # Round to nearest 0.5
    rounded = round(years * 2) / 2

    # Confidence based on derivation method
    if derived_from_dates:
        confidence = 0.9
    elif re.match(r"^\d+\.?\d*$", raw_value):
        # Explicit numeric value
        confidence = 0.85
    else:
        # Heuristic parsing
        confidence = 0.6

    return rounded, confidence, True


def _extract_years(text: str) -> Optional[float]:
    """Extract numeric years value from text."""
    text = text.lower()

    # Pattern 1: "X-Y years" or "X to Y years" -> take average
    range_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:to|-)\s*(\d+(?:\.\d+)?)\s*(?:years?)?", text)
    if range_match:
        try:
            start = float(range_match.group(1))
            end = float(range_match.group(2))
            return (start + end) / 2
        except ValueError:
            pass

    # Pattern 2: "X years" or "X year"
    years_match = re.search(r"(\d+(?:\.\d+)?)\s*years?", text)
    if years_match:
        try:
            return float(years_match.group(1))
        except ValueError:
            pass

    # Pattern 3: Just a number "5" or "5.5"
    num_match = re.search(r"^(\d+(?:\.\d+)?)$", text)
    if num_match:
        try:
            return float(num_match.group(1))
        except ValueError:
            pass

    return None


def derive_years_experience_from_dates(
    experiences: list[dict],
) -> Optional[float]:
    """
    Derive years of experience from a list of employment dates.

    Args:
        experiences: List of dicts with 'start' and 'end' date fields (YYYY-MM format)

    Returns:
        Total years of experience (float) or None if insufficient data
    """
    if not experiences:
        return None

    from dateutil.parser import parse

    total_days = 0.0

    for exp in experiences:
        start_str = exp.get("start")
        end_str = exp.get("end")

        if not start_str:
            continue

        try:
            start_date = parse(start_str)
            # End date defaults to today if not provided
            end_date = parse(end_str) if end_str else datetime.now(timezone.utc)

            delta = (end_date - start_date).days
            if delta > 0:
                total_days += delta
        except Exception as e:
            logger.warning(f"Failed to parse dates for experience: {e}")
            continue

    if total_days <= 0:
        return None

    # Convert days to years (365.25 days per year)
    years = total_days / 365.25

    # Round to 0.5 precision
    return round(years * 2) / 2
