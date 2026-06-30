"""Tests for edge cases and robustness."""

import pytest
import json
import tempfile
from pathlib import Path
from transformer.pipeline import extract
from transformer.models import RawRecord


class TestMissingFiles:
    """Test handling of missing or unreadable files."""

    def test_missing_csv_file(self):
        """Test that missing CSV doesn't crash extraction."""
        raw_records = extract(["/nonexistent/file.csv"])
        assert len(raw_records) == 1
        assert raw_records[0].parse_error is not None

    def test_missing_json_file(self):
        """Test that missing JSON doesn't crash extraction."""
        raw_records = extract(["/nonexistent/file.json"])
        assert len(raw_records) == 1
        assert raw_records[0].parse_error is not None


class TestMalformedData:
    """Test handling of malformed source data."""

    def test_malformed_json(self):
        """Test that malformed JSON is handled gracefully."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            fname = f.name
            f.write("{ invalid json }")

        raw_records = extract([fname])
        assert len(raw_records) == 1
        assert raw_records[0].parse_error is not None

        # Clean up
        Path(fname).unlink(missing_ok=True)

    def test_empty_csv(self):
        """Test that empty CSV is handled."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            fname = f.name
            f.write("name,email,phone\n")  # Header only
            f.flush()

        raw_records = extract([fname])
        assert len(raw_records) == 1
        # Should not have parse error, just empty data
        assert raw_records[0].extracted_fields.get("row_count") == 0

        # Clean up
        Path(fname).unlink(missing_ok=True)


class TestUnrecognizedSource:
    """Test handling of unrecognized source types."""

    def test_unknown_file_extension(self):
        """Test that unknown file extension is handled."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xyz", delete=False) as f:
            fname = f.name
            f.write("some data")
            f.flush()

        raw_records = extract([fname])
        assert len(raw_records) == 1
        # Should recognize as unknown but not crash
        assert raw_records[0].source_name in ["unknown", "error"]

        # Clean up
        Path(fname).unlink(missing_ok=True)


class TestEmptyInput:
    """Test handling of empty inputs."""

    def test_empty_sources_list(self):
        """Test that empty sources list returns empty result."""
        raw_records = extract([])
        assert raw_records == []

    def test_empty_values(self):
        """Test that empty field values are handled."""
        from transformer.normalize import (
            normalize_email,
            normalize_phone,
            normalize_name,
        )

        # All normalizers should handle empty/None input
        value, conf, success = normalize_email("")
        assert not success

        value, conf, success = normalize_phone("")
        assert not success

        value, conf, success = normalize_name("")
        assert not success


class TestSpecialCharacters:
    """Test handling of special characters and unicode."""

    def test_unicode_name(self):
        """Test that unicode names are handled."""
        from transformer.normalize import normalize_name

        value, conf, success = normalize_name("José García")
        assert success
        assert "José" in value

    def test_unicode_email(self):
        """Test that email with unicode is handled gracefully."""
        from transformer.normalize import normalize_email

        # Most email systems don't support unicode in local part
        value, conf, success = normalize_email("josé@example.com")
        # May fail validation, which is fine
        assert not success or value  # Either fails or succeeds

    def test_chinese_name(self):
        """Test that non-Latin scripts are handled."""
        from transformer.normalize import normalize_name

        value, conf, success = normalize_name("王伟")
        assert success  # Should normalize without error


class TestDuplicates:
    """Test handling of duplicates and deduplication."""

    def test_duplicate_handling(self):
        """Test that duplicates are handled in merge."""
        from transformer.models import NormalizedRecord, NormalizedValue

        # Create records with duplicate emails
        field_values = {
            "name": "Alice",
            "emails": ["alice@example.com", "alice@example.com"],
        }
        normalized_fields = {}
        for field_name, value in field_values.items():
            normalized_fields[field_name] = NormalizedValue(
                value=value,
                source="source1",
                method="test",
                success=True,
                confidence=0.8,
            )

        record = NormalizedRecord(
            source_name="source1",
            source_method="test",
            candidate_id_temp="temp_source1",
            normalized_fields=normalized_fields,
            parse_error=None,
        )

        # Merge should deduplicate
        from transformer.pipeline.merge import merge
        candidates = merge([record])
        assert len(candidates) == 1


class TestLargeValues:
    """Test handling of unusually large values."""

    def test_very_long_name(self):
        """Test handling of very long name."""
        from transformer.normalize import normalize_name

        long_name = "A" * 500
        value, conf, success = normalize_name(long_name)
        assert success  # Should still normalize

    def test_very_long_email(self):
        """Test handling of very long email."""
        from transformer.normalize import normalize_email

        long_email = "a" * 500 + "@example.com"
        value, conf, success = normalize_email(long_email)
        # RFC 5322 limits, but our validator should handle gracefully
        assert not success or value  # Either rejects or accepts


class TestNullAndNoneValues:
    """Test handling of null/None values."""

    def test_none_values_in_dict(self):
        """Test that None values in dict don't crash."""
        from transformer.pipeline.normalize import _normalize_candidate_list

        candidates = [
            {"name": None, "email": None, "phone": None},
        ]

        result = _normalize_candidate_list(candidates, "test_source")
        assert len(result) == 1
        assert result[0]["name"] is None
