"""Tests for projection logic."""

import pytest
from transformer.models import (
    Candidate,
    Location,
    Link,
    Skill,
    Experience,
    Education,
    Provenance,
    ProvenanceEntry,
    FieldConfig,
    ProjectionConfig,
)
from transformer.pipeline.project import project


def create_test_candidate():
    """Create a test candidate."""
    return Candidate(
        candidate_id="test-001",
        full_name="Alice Johnson",
        emails=["alice@example.com", "alice.j@work.com"],
        phones=["+14155552671", "+14155552672"],
        location=Location(city="San Francisco", region="CA", country="US"),
        links=[
            Link(type="github", url="https://github.com/alice"),
            Link(type="linkedin", url="https://linkedin.com/in/alice"),
        ],
        headline="Senior Software Engineer",
        years_experience=7.5,
        skills=[
            Skill(name="Python", confidence=0.95, canonicalized=True, sources=["resume"]),
            Skill(name="Kubernetes", confidence=0.9, canonicalized=True, sources=["github"]),
        ],
        experience=[
            Experience(
                company="TechCorp",
                title="Senior Engineer",
                start="2021-05",
                end=None,
                source="resume",
            ),
        ],
        education=[
            Education(
                institution="UC Berkeley",
                degree="Bachelor",
                field="Computer Science",
                end_year="2015",
                source="linkedin",
            ),
        ],
        provenance=[
            Provenance(
                field="full_name",
                value="Alice Johnson",
                sources=[ProvenanceEntry(source_name="resume", extraction_method="parsing", confidence=0.9)],
                final_confidence=0.9,
                extraction_method="direct",
            ),
        ],
        overall_confidence=0.85,
    )


class TestProjectDottedPath:
    """Test dotted path evaluation."""

    def test_project_simple_field(self):
        """Test projecting a simple field."""
        config = ProjectionConfig(
            fields=[
                FieldConfig(path="name", from_="full_name", type="string")
            ]
        )
        candidate = create_test_candidate()

        result = project([candidate], config)
        assert len(result) == 1
        assert result[0]["name"] == "Alice Johnson"

    def test_project_nested_field(self):
        """Test projecting nested field (location.country)."""
        config = ProjectionConfig(
            fields=[
                FieldConfig(path="country", from_="location.country", type="string")
            ]
        )
        candidate = create_test_candidate()

        result = project([candidate], config)
        assert len(result) == 1
        assert result[0]["country"] == "US"


class TestProjectArrayIndexing:
    """Test array indexing in projection."""

    def test_project_first_email(self):
        """Test projecting first email."""
        config = ProjectionConfig(
            fields=[
                FieldConfig(path="primary_email", from_="emails[0]", type="string")
            ]
        )
        candidate = create_test_candidate()

        result = project([candidate], config)
        assert len(result) == 1
        assert result[0]["primary_email"] == "alice@example.com"

    def test_project_second_phone(self):
        """Test projecting second phone."""
        config = ProjectionConfig(
            fields=[
                FieldConfig(path="secondary_phone", from_="phones[1]", type="string")
            ]
        )
        candidate = create_test_candidate()

        result = project([candidate], config)
        assert len(result) == 1
        assert result[0]["secondary_phone"] == "+14155552672"

    def test_project_out_of_bounds_index(self):
        """Test accessing index beyond array size."""
        config = ProjectionConfig(
            fields=[
                FieldConfig(path="email", from_="emails[10]", type="string", required=False)
            ],
            on_missing="null"
        )
        candidate = create_test_candidate()

        result = project([candidate], config)
        assert len(result) == 1
        assert result[0].get("email") is None


class TestProjectArrayFlattening:
    """Test array flattening in projection."""

    def test_project_skill_names(self):
        """Test flattening skill names."""
        config = ProjectionConfig(
            fields=[
                FieldConfig(path="skills", from_="skills[].name", type="string[]")
            ]
        )
        candidate = create_test_candidate()

        result = project([candidate], config)
        assert len(result) == 1
        assert "Python" in result[0]["skills"]
        assert "Kubernetes" in result[0]["skills"]

    def test_project_all_experience(self):
        """Test flattening all experience objects."""
        config = ProjectionConfig(
            fields=[
                FieldConfig(path="all_companies", from_="experience[].company", type="string[]")
            ]
        )
        candidate = create_test_candidate()

        result = project([candidate], config)
        assert len(result) == 1
        assert "TechCorp" in result[0]["all_companies"]


class TestProjectMissingHandling:
    """Test handling of missing values."""

    def test_missing_null(self):
        """Test on_missing='null'."""
        config = ProjectionConfig(
            fields=[
                FieldConfig(path="missing_field", from_="nonexistent", type="string")
            ],
            on_missing="null"
        )
        candidate = create_test_candidate()

        result = project([candidate], config)
        assert "missing_field" in result[0]
        assert result[0]["missing_field"] is None

    def test_missing_omit(self):
        """Test on_missing='omit'."""
        config = ProjectionConfig(
            fields=[
                FieldConfig(path="missing_field", from_="nonexistent", type="string")
            ],
            on_missing="omit"
        )
        candidate = create_test_candidate()

        result = project([candidate], config)
        assert "missing_field" not in result[0]

    def test_missing_error_not_required(self):
        """Test on_missing='error' with required=False doesn't error."""
        config = ProjectionConfig(
            fields=[
                FieldConfig(path="missing_field", from_="nonexistent", type="string", required=False)
            ],
            on_missing="error"
        )
        candidate = create_test_candidate()

        # Should not raise
        result = project([candidate], config)
        assert len(result) == 1


class TestProjectConfidenceProvenance:
    """Test confidence and provenance inclusion."""

    def test_include_confidence(self):
        """Test including confidence in output."""
        config = ProjectionConfig(
            include_confidence=True,
            fields=[
                FieldConfig(path="name", from_="full_name", type="string")
            ]
        )
        candidate = create_test_candidate()

        result = project([candidate], config)
        assert "overall_confidence" in result[0]

    def test_field_confidence(self):
        """Test field-level confidence."""
        config = ProjectionConfig(
            fields=[
                FieldConfig(
                    path="name",
                    from_="full_name",
                    type="string",
                    include_confidence=True
                )
            ]
        )
        candidate = create_test_candidate()

        result = project([candidate], config)
        assert "name_confidence" in result[0]
