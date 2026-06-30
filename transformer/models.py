"""
Pydantic models for the candidate data transformer pipeline.

Defines the canonical internal schema (Candidate) and intermediate stage representations.
"""

from typing import Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field, EmailStr, field_validator, ConfigDict
import json


# ============================================================================
# Intermediate Stage Models
# ============================================================================


class RawRecord(BaseModel):
    """Raw extracted data from a single source, before normalization.

    This is the output of the EXTRACT stage (source adapter output).
    """
    source_name: str  # e.g. "recruiter_csv", "github_profile", "resume_pdf"
    source_method: str  # e.g. "api", "file_parse", "text_regex"
    extracted_fields: dict[str, Any]  # {field_name: raw_value}
    raw_text: Optional[str] = None  # Original text for debugging
    parse_error: Optional[str] = None  # If parsing partially failed
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NormalizedValue(BaseModel):
    """A single field after normalization: value + metadata about extraction."""
    value: Any  # The normalized value (str, int, float, list, dict, None)
    source: str  # "recruiter_csv", etc.
    method: str  # How it was extracted
    success: bool  # Did normalization succeed?
    confidence: float  # 0.0–1.0
    raw_value: Optional[Any] = None  # Keep original for provenance


class NormalizedRecord(BaseModel):
    """Normalized data from a single source.

    Output of NORMALIZE stage: same structure as RawRecord but all fields processed.
    """
    source_name: str
    source_method: str
    candidate_id_temp: str  # Temporary candidate ID (will be finalized during merge)
    normalized_fields: dict[str, NormalizedValue]
    parse_error: Optional[str] = None


# ============================================================================
# Canonical Schema Models (Internal Representation)
# ============================================================================


class Location(BaseModel):
    """Candidate's geographic location."""
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None  # ISO-3166 alpha-2


class Link(BaseModel):
    """A single link (LinkedIn, GitHub, portfolio, etc.)."""
    type: str  # "linkedin", "github", "portfolio", "other"
    url: str


class Skill(BaseModel):
    """A single skill with confidence and provenance."""
    name: str  # Canonical or raw skill name
    confidence: float  # 0.0–1.0
    canonicalized: bool  # Was it matched to taxonomy?
    sources: list[str]  # ["github", "resume", ...]


class Experience(BaseModel):
    """A single employment or project entry."""
    company: Optional[str] = None
    title: Optional[str] = None
    start: Optional[str] = None  # YYYY-MM format
    end: Optional[str] = None  # YYYY-MM format
    summary: Optional[str] = None  # Brief description
    source: str  # "resume", "linkedin", "ats", etc.


class Education(BaseModel):
    """A single education entry."""
    institution: Optional[str] = None
    degree: Optional[str] = None  # "Bachelor", "Master", "PhD"
    field: Optional[str] = None  # "Computer Science"
    end_year: Optional[str] = None  # YYYY format
    source: str  # Where this came from


class ProvenanceEntry(BaseModel):
    """Provenance for a single source contribution to a field."""
    source_name: str
    extraction_method: str
    confidence: float
    raw_value: Optional[Any] = None


class Provenance(BaseModel):
    """Complete provenance for a single field value."""
    field: str
    value: Optional[Any]  # The final value
    sources: list[ProvenanceEntry]  # All contributing sources
    final_confidence: float  # 0.0–1.0
    extraction_method: str  # "direct", "merged", "heuristic", "api", etc.
    match_method: Optional[str] = None  # "email", "fuzzy_name_phone", etc.


class Candidate(BaseModel):
    """Complete canonical candidate profile.

    Output of MERGE/CONFIDENCE stages; input to PROJECT stage.
    This is the authoritative internal representation.
    """
    candidate_id: str  # UUID5 (deterministic)
    full_name: str
    emails: list[str] = []  # Lowercase, validated, deduplicated
    phones: list[str] = []  # E.164 format, deduplicated
    location: Optional[Location] = None
    links: list[Link] = []
    headline: Optional[str] = None
    years_experience: Optional[float] = None
    skills: list[Skill] = []
    experience: list[Experience] = []
    education: list[Education] = []
    provenance: list[Provenance] = []
    overall_confidence: float  # 0.0–1.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), exclude=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), exclude=True)

    def model_dump_json(self, **kwargs) -> str:
        """Override to exclude timestamps from JSON serialization."""
        return super().model_dump_json(**{**kwargs, 'exclude': {'created_at', 'updated_at'}})

    def model_dump(self, **kwargs) -> dict:
        """Override to exclude timestamps from dict serialization."""
        return super().model_dump(**{**kwargs, 'exclude': {'created_at', 'updated_at'}})


# ============================================================================
# Configuration Models
# ============================================================================


class FieldConfig(BaseModel):
    """Config for a single output field."""
    model_config = ConfigDict(populate_by_name=True)  # Allow both alias and field name

    path: str  # Output key (e.g. "full_name", "primary_email")
    from_: str = Field(alias="from")  # Canonical path expression
    type: str  # "string", "string[]", "number", "object", "object[]"
    required: bool = False
    normalize: Optional[str] = None  # "E164", "canonical", etc.
    include_provenance: bool = False
    include_confidence: bool = False


class ProjectionConfig(BaseModel):
    """Runtime config for the PROJECT stage."""
    version: str = "1.0"
    fields: list[FieldConfig]
    include_confidence: bool = False
    include_provenance: bool = False
    on_missing: str = "null"  # "null", "omit", "error"

    @field_validator("on_missing")
    @classmethod
    def validate_on_missing(cls, v: str) -> str:
        if v not in ("null", "omit", "error"):
            raise ValueError("on_missing must be 'null', 'omit', or 'error'")
        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        if v != "1.0":
            raise ValueError("Only config version '1.0' is supported")
        return v


class SourcePriority(BaseModel):
    """Source priority rules for a single field group."""
    field_group: str  # "contact", "employment", "skills", "headline", "years_experience"
    priorities: list[str]  # ["ats", "recruiter_csv", "resume", ...]


class MergePolicy(BaseModel):
    """Merge policy configuration loaded from data/merge_policy.json."""
    version: str = "1.0"
    field_groups: dict[str, list[str]]  # {field_group: [source1, source2, ...]}


# ============================================================================
# Utilities
# ============================================================================


def load_json_model(model_class, file_path: str):
    """Load and validate a JSON file as a Pydantic model."""
    with open(file_path, "r") as f:
        data = json.load(f)
    return model_class.model_validate(data)


def dump_json_model(model: BaseModel, file_path: str, pretty: bool = True) -> None:
    """Dump a Pydantic model to JSON file."""
    with open(file_path, "w") as f:
        if pretty:
            f.write(model.model_dump_json(indent=2))
        else:
            f.write(model.model_dump_json())
