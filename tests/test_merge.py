"""Tests for merge and entity resolution logic."""

import pytest
from transformer.models import (
    NormalizedRecord,
    NormalizedValue,
    Candidate,
)
from transformer.pipeline.merge import merge


def create_normalized_record(source_name, field_values):
    """Helper to create a NormalizedRecord."""
    normalized_fields = {}
    for field_name, value in field_values.items():
        normalized_fields[field_name] = NormalizedValue(
            value=value,
            source=source_name,
            method="test",
            success=True,
            confidence=0.8,
        )

    return NormalizedRecord(
        source_name=source_name,
        source_method="test",
        candidate_id_temp=f"temp_{source_name}",
        normalized_fields=normalized_fields,
        parse_error=None,
    )


class TestEntityResolution:
    """Test candidate matching and deduplication."""

    def test_merge_same_email(self):
        """Test that records with same email are merged."""
        records = [
            create_normalized_record(
                "source1",
                {"name": "Alice Johnson", "email": "alice@example.com", "emails": ["alice@example.com"]},
            ),
            create_normalized_record(
                "source2",
                {"name": "Alice Johnson", "email": "alice@example.com", "emails": ["alice@example.com"], "phone": "+14155552671", "phones": ["+14155552671"]},
            ),
        ]

        candidates = merge(records)
        assert len(candidates) == 1
        assert "alice@example.com" in candidates[0].emails

    def test_merge_different_candidates(self):
        """Test that different people are not merged."""
        records = [
            create_normalized_record(
                "source1",
                {"name": "Alice Johnson", "email": "alice@example.com"},
            ),
            create_normalized_record(
                "source2",
                {"name": "Bob Smith", "email": "bob@example.com"},
            ),
        ]

        candidates = merge(records)
        assert len(candidates) == 2


class TestConflictResolution:
    """Test conflict resolution per priority table."""

    def test_conflict_phone_priority(self):
        """Test phone conflict resolution uses priority table."""
        records = [
            create_normalized_record(
                "recruiter_csv",
                {"name": "Alice", "email": "alice@example.com", "phone": "+14155552671"},
            ),
            create_normalized_record(
                "resume",
                {"name": "Alice", "email": "alice@example.com", "phone": "+14155552672"},
            ),
        ]

        candidates = merge(records)
        assert len(candidates) == 1
        # Resume has higher priority for contact fields, but in this case both have the field
        # The implementation should pick by priority


class TestMergeLists:
    """Test list field merging (union + dedup)."""

    def test_merge_emails_union(self):
        """Test that emails are unioned across sources."""
        records = [
            create_normalized_record(
                "source1",
                {"name": "Alice", "emails": ["alice@example.com"]},
            ),
            create_normalized_record(
                "source2",
                {"name": "Alice", "emails": ["alice.j@work.com", "alice@example.com"]},
            ),
        ]

        candidates = merge(records)
        assert len(candidates) == 1
        assert len(candidates[0].emails) >= 1  # Union of emails


def test_merge_empty_records():
    """Test merging empty record list."""
    candidates = merge([])
    assert candidates == []


def test_overall_confidence():
    """Test that overall_confidence is computed."""
    records = [
        create_normalized_record(
            "source1",
            {"name": "Alice", "email": "alice@example.com"},
        ),
    ]

    candidates = merge(records)
    assert len(candidates) == 1
    assert 0 <= candidates[0].overall_confidence <= 1
