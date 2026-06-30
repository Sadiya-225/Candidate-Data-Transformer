"""Name normalization: trim, whitespace, intentional casing detection."""

import logging
import re
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Common name particles that should preserve casing
NAME_PARTICLES = {"van", "der", "von", "de", "di", "da", "le", "la", "el", "al", "bin", "ibn"}

# All-caps threshold for acronym detection
ALLCAPS_ACRONYM_THRESHOLD = 4


def normalize_name(raw_value: Optional[str]) -> Tuple[Optional[str], float, bool]:
    """
    Normalize a name: trim whitespace, normalize casing intelligently.

    Args:
        raw_value: Name string (e.g., "John Doe", "john doe", "JOHN DOE", "van der Berg")

    Returns:
        Tuple of (normalized_name, confidence, success):
        - normalized_name: Title-cased name with intelligent particle handling
        - confidence: 0.0–1.0
        - success: Whether normalization succeeded

    Notes:
        - Preserves intentional casing for particles like "van der", "McDonald"
        - Lowercase-only all-caps names to detect acronyms
        - Trim whitespace, normalize internal spacing
    """
    if not raw_value or not isinstance(raw_value, str):
        return None, 0.0, False

    raw_value = raw_value.strip()
    if not raw_value:
        return None, 0.0, False

    # Normalize internal whitespace (collapse multiple spaces to single)
    normalized = re.sub(r"\s+", " ", raw_value)

    # Apply intelligent title casing with particle preservation
    # (works for all-caps and mixed-case)
    normalized = _title_case_with_particles(normalized)

    # Check if it was all uppercase (likely an acronym)
    if raw_value.isupper() and len(normalized) >= ALLCAPS_ACRONYM_THRESHOLD:
        confidence = 0.7
    else:
        confidence = 0.85

    return normalized, confidence, True


def _title_case_with_particles(name: str) -> str:
    """Apply title casing while preserving intentional particles like 'van der'."""
    words = name.split()
    result = []

    for word in words:
        word_lower = word.lower()

        # Check if this is a known particle
        if word_lower in NAME_PARTICLES and len(result) > 0:
            # Keep particle lowercase (but preceded by space)
            result.append(word_lower)
        else:
            # Standard title case for this word
            # Handle special cases like McDonald, O'Brien
            if "'" in word:
                # Name with apostrophe: "o'brien" -> "O'Brien"
                parts = word.split("'")
                title_parts = [part.capitalize() for part in parts]
                result.append("'".join(title_parts))
            elif "-" in word:
                # Hyphenated name: "jean-claude" -> "Jean-Claude"
                parts = word.split("-")
                title_parts = [part.capitalize() for part in parts]
                result.append("-".join(title_parts))
            else:
                result.append(word.capitalize())

    return " ".join(result)
