"""Country code normalization to ISO-3166 alpha-2 format."""

import logging
from typing import Optional, Tuple
import pycountry
from difflib import get_close_matches

logger = logging.getLogger(__name__)

# Common country name mappings not in pycountry
COUNTRY_ALIASES = {
    "usa": "US",
    "us": "US",
    "united states": "US",
    "america": "US",
    "uk": "GB",
    "united kingdom": "GB",
    "gb": "GB",
    "england": "GB",
    "holland": "NL",
    "netherlands": "NL",
    "holland": "NL",
    "south korea": "KR",
    "korea": "KR",
    "south korea": "KR",
    "prc": "CN",
    "china": "CN",
    "peoples republic of china": "CN",
    "republic of ireland": "IE",
    "ireland": "IE",
    "türkiye": "TR",
    "turkey": "TR",
    "czechia": "CZ",
    "czech republic": "CZ",
    "eswatini": "SZ",
    "swaziland": "SZ",
    "timor-leste": "TL",
    "east timor": "TL",
    "oman": "OM",
    "sultanate of oman": "OM",
    "uae": "AE",
    "emirates": "AE",
    "uaes": "AE",
}


def normalize_country(
    raw_value: Optional[str],
) -> Tuple[Optional[str], float, bool]:
    """
    Normalize a country name or code to ISO-3166 alpha-2 format.

    Args:
        raw_value: Country name or code (e.g., "United States", "US", "GB")

    Returns:
        Tuple of (iso_alpha_2, confidence, success):
        - iso_alpha_2: ISO-3166 alpha-2 code or None if not recognized
        - confidence: 0.0–1.0 based on match certainty
        - success: Whether parsing succeeded

    Notes:
        - Accepts full names, alpha-2, and alpha-3 codes
        - Handles common misspellings via fuzzy matching
        - Case-insensitive
    """
    if not raw_value or not isinstance(raw_value, str):
        return None, 0.0, False

    raw_value = raw_value.strip()
    if not raw_value:
        return None, 0.0, False

    original = raw_value
    normalized = raw_value.lower()

    # 1. Check exact alias matches first
    if normalized in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[normalized], 0.95, True

    # 2. Try as alpha-2 code
    try:
        country = pycountry.countries.get(alpha_2=normalized.upper())
        if country:
            return country.alpha_2, 0.99, True
    except (KeyError, AttributeError):
        pass

    # 3. Try as alpha-3 code
    try:
        country = pycountry.countries.get(alpha_3=normalized.upper())
        if country:
            return country.alpha_2, 0.98, True
    except (KeyError, AttributeError):
        pass

    # 4. Try as full country name
    try:
        country = pycountry.countries.search_fuzzy(normalized)
        if country:
            return country[0].alpha_2, 0.95, True
    except LookupError:
        pass

    # 5. Try fuzzy matching against aliases
    close_matches = get_close_matches(normalized, COUNTRY_ALIASES.keys(), n=1, cutoff=0.8)
    if close_matches:
        matched_alias = close_matches[0]
        return COUNTRY_ALIASES[matched_alias], 0.8, True

    logger.warning(f"Could not normalize country: {original}")
    return None, 0.1, False
