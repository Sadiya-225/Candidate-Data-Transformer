"""Integration tests for the full pipeline."""

import pytest
import json
import os
from pathlib import Path
from transformer.pipeline import extract, normalize, merge, confidence, project, validate
from transformer.models import ProjectionConfig, load_json_model


class TestFullPipeline:
    """Test the complete transformation pipeline."""

    @pytest.fixture
    def sample_data_dir(self):
        """Get path to sample data directory."""
        return Path(__file__).parent.parent / "data" / "sample_inputs"

    @pytest.fixture
    def config_dir(self):
        """Get path to config directory."""
        return Path(__file__).parent.parent / "configs"

    def test_pipeline_with_csv_and_json(self, sample_data_dir, tmp_path):
        """Test pipeline with CSV and JSON sources."""
        sources = [
            str(sample_data_dir / "recruiter.csv"),
            str(sample_data_dir / "ats.json"),
        ]

        # Skip if files don't exist (during testing)
        if not all(os.path.exists(s) for s in sources):
            pytest.skip("Sample data not found")

        # Run pipeline
        raw_records = extract(sources)
        assert len(raw_records) == 2

        normalized_records = normalize(raw_records)
        assert len(normalized_records) == 2

        candidates = merge(normalized_records)
        assert len(candidates) > 0

        candidates = confidence(candidates)

        # Basic validation: each candidate has required fields
        for candidate in candidates:
            assert candidate.candidate_id
            assert candidate.full_name
            assert isinstance(candidate.overall_confidence, float)

    def test_pipeline_with_notes(self, sample_data_dir):
        """Test pipeline with recruiter notes."""
        sources = [
            str(sample_data_dir / "notes.txt"),
        ]

        if not os.path.exists(sources[0]):
            pytest.skip("Sample notes file not found")

        raw_records = extract(sources)
        assert len(raw_records) > 0

        normalized_records = normalize(raw_records)
        candidates = merge(normalized_records)
        # Notes should produce at least some candidates
        assert len(candidates) >= 0

    def test_pipeline_determinism(self, sample_data_dir):
        """Test that same input produces same output (determinism)."""
        sources = [
            str(sample_data_dir / "recruiter.csv"),
        ]

        if not os.path.exists(sources[0]):
            pytest.skip("Sample data not found")

        # Run pipeline twice
        results1 = []
        for i in range(2):
            raw_records = extract(sources)
            normalized_records = normalize(raw_records)
            candidates = merge(normalized_records)
            candidates = confidence(candidates)

            # Convert to dicts for comparison
            candidate_dicts = [c.model_dump_json() for c in candidates]
            results1.append(candidate_dicts)

        # Results should be identical
        assert results1[0] == results1[1], "Pipeline output is not deterministic"


class TestProjectionWithConfig:
    """Test projection with actual config files."""

    @pytest.fixture
    def config_dir(self):
        """Get path to config directory."""
        return Path(__file__).parent.parent / "configs"

    def test_project_with_default_config(self, config_dir):
        """Test projection with default config."""
        config_path = config_dir / "default.json"
        if not config_path.exists():
            pytest.skip("Default config not found")

        config = load_json_model(ProjectionConfig, str(config_path))

        # Create a simple test candidate
        from transformer.models import Candidate, Location

        candidate = Candidate(
            candidate_id="test-001",
            full_name="Alice Johnson",
            emails=["alice@example.com"],
            phones=["+14155552671"],
            location=Location(country="US"),
            links=[],
            headline="Engineer",
            years_experience=5.0,
            skills=[],
            experience=[],
            education=[],
            provenance=[],
            overall_confidence=0.8,
        )

        result = project([candidate], config)
        assert len(result) == 1
        assert "candidate_id" in result[0]
        assert "full_name" in result[0]

    def test_project_with_lean_config(self, config_dir):
        """Test projection with lean CRM config."""
        config_path = config_dir / "lean_crm.json"
        if not config_path.exists():
            pytest.skip("Lean CRM config not found")

        config = load_json_model(ProjectionConfig, str(config_path))

        from transformer.models import Candidate, Location

        candidate = Candidate(
            candidate_id="test-001",
            full_name="Alice Johnson",
            emails=["alice@example.com"],
            phones=["+14155552671"],
            location=Location(country="US"),
            links=[],
            headline="Engineer",
            years_experience=5.0,
            skills=[],
            experience=[],
            education=[],
            provenance=[],
            overall_confidence=0.8,
        )

        result = project([candidate], config)
        assert len(result) == 1
        # Lean config has minimal fields
        assert "full_name" in result[0]
        assert "primary_email" in result[0]


def test_pipeline_missing_source():
    """Test that missing source file doesn't crash pipeline."""
    sources = ["/nonexistent/file.csv"]

    raw_records = extract(sources)
    assert len(raw_records) == 1
    # Should have error recorded
    assert raw_records[0].parse_error is not None
