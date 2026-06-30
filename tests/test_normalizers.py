"""Tests for normalizer functions."""

import pytest
from transformer.normalize import (
    normalize_phone,
    normalize_date,
    normalize_country,
    normalize_email,
    normalize_name,
    normalize_skill,
    normalize_years_experience,
)


class TestPhoneNormalizer:
    """Test phone number normalization."""

    def test_normalize_valid_us_phone(self):
        value, conf, success = normalize_phone("+1-415-555-2671")
        assert success
        assert value == "+14155552671"
        assert conf >= 0.7  # Confidence 0.95 when region_hint provided, 0.7 when inferred

    def test_normalize_us_phone_without_country_code(self):
        value, conf, success = normalize_phone("415-555-2671", region_hint="US")
        assert success
        assert value.startswith("+1")
        assert conf > 0.7

    def test_normalize_invalid_phone(self):
        value, conf, success = normalize_phone("not a phone")
        assert not success
        assert value is None
        assert conf < 0.5

    def test_normalize_empty_phone(self):
        value, conf, success = normalize_phone("")
        assert not success
        assert value is None


class TestDateNormalizer:
    """Test date normalization."""

    def test_normalize_iso_date(self):
        value, conf, success = normalize_date("2023-05-15")
        assert success
        assert value == "2023-05"
        assert conf > 0.8

    def test_normalize_us_date(self):
        value, conf, success = normalize_date("05/15/2023")
        assert success
        assert value == "2023-05"

    def test_normalize_month_year(self):
        value, conf, success = normalize_date("May 2023")
        assert success
        assert value == "2023-05"

    def test_normalize_relative_date(self):
        value, conf, success = normalize_date("2 years ago")
        assert success
        assert conf < 0.8  # Heuristic, lower confidence

    def test_normalize_invalid_date(self):
        value, conf, success = normalize_date("not a date")
        assert not success
        assert value is None


class TestCountryNormalizer:
    """Test country normalization."""

    def test_normalize_country_alpha2(self):
        value, conf, success = normalize_country("US")
        assert success
        assert value == "US"
        assert conf > 0.9

    def test_normalize_country_full_name(self):
        value, conf, success = normalize_country("United States")
        assert success
        assert value == "US"
        assert conf > 0.8

    def test_normalize_country_alias(self):
        value, conf, success = normalize_country("UK")
        assert success
        assert value == "GB"

    def test_normalize_invalid_country(self):
        value, conf, success = normalize_country("Atlantis")
        assert not success
        assert value is None


class TestEmailNormalizer:
    """Test email normalization."""

    def test_normalize_valid_email(self):
        value, conf, success = normalize_email("John.Doe@Example.COM")
        assert success
        assert value == "john.doe@example.com"
        assert conf > 0.9

    def test_normalize_invalid_email(self):
        value, conf, success = normalize_email("not-an-email")
        assert not success
        assert value is None

    def test_normalize_empty_email(self):
        value, conf, success = normalize_email("")
        assert not success
        assert value is None


class TestNameNormalizer:
    """Test name normalization."""

    def test_normalize_simple_name(self):
        value, conf, success = normalize_name("john doe")
        assert success
        assert value == "John Doe"

    def test_normalize_name_with_particle(self):
        value, conf, success = normalize_name("jean van der berg")
        assert success
        assert "van der" in value.lower()

    def test_normalize_all_caps_name(self):
        value, conf, success = normalize_name("JOHN DOE")
        assert success
        assert value == "John Doe"

    def test_normalize_hyphenated_name(self):
        value, conf, success = normalize_name("jean-claude")
        assert success
        assert value == "Jean-Claude"


class TestSkillNormalizer:
    """Test skill normalization."""

    def test_normalize_canonical_skill(self):
        value, conf, success, canonicalized = normalize_skill("Python")
        assert success
        assert value == "Python"
        assert canonicalized

    def test_normalize_skill_alias(self):
        value, conf, success, canonicalized = normalize_skill("ReactJS")
        assert success
        assert value == "React"
        assert canonicalized

    def test_normalize_unrecognized_skill(self):
        value, conf, success, canonicalized = normalize_skill("XyzUnknownTech")
        assert success
        assert value == "XyzUnknownTech"
        assert not canonicalized  # Not in taxonomy


class TestYearsExperienceNormalizer:
    """Test years of experience normalization."""

    def test_normalize_simple_years(self):
        value, conf, success = normalize_years_experience("5")
        assert success
        assert value == 5.0

    def test_normalize_years_with_decimal(self):
        value, conf, success = normalize_years_experience("5.5")
        assert success
        assert value == 5.5

    def test_normalize_year_range(self):
        value, conf, success = normalize_years_experience("5-7 years")
        assert success
        assert 5 <= value <= 7

    def test_normalize_invalid_years(self):
        value, conf, success = normalize_years_experience("many years")
        assert not success
        assert value is None
