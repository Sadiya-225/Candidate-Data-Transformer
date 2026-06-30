"""MERGE stage: entity resolution and conflict resolution across sources."""

import logging
import hashlib
import json
import os
from typing import List, Dict, Optional, Set, Tuple, Any
from uuid import uuid5, NAMESPACE_DNS
from collections import defaultdict

from transformer.models import (
    NormalizedRecord,
    Candidate,
    Location,
    Link,
    Skill,
    Experience,
    Education,
    Provenance,
    ProvenanceEntry,
    MergePolicy,
)

logger = logging.getLogger(__name__)

# Load merge policy
def _load_merge_policy() -> Dict[str, List[str]]:
    """Load merge policy from data/merge_policy.json."""
    module_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(module_dir))
    policy_path = os.path.join(project_root, "data", "merge_policy.json")

    try:
        with open(policy_path, "r") as f:
            policy_data = json.load(f)
            return policy_data.get("field_groups", {})
    except Exception as e:
        logger.warning(f"Could not load merge policy: {e}, using empty policy")
        return {}


MERGE_POLICY = _load_merge_policy()


def merge(normalized_records: List[NormalizedRecord]) -> List[Candidate]:
    """
    Merge normalized records into canonical candidates.

    Args:
        normalized_records: List of NormalizedRecord from NORMALIZE stage

    Returns:
        List of Candidate objects (merged and deduplicated)
    """
    # Step 1: Entity resolution - group records by candidate
    candidate_groups = _entity_resolution(normalized_records)

    # Step 2: For each group, create a merged Candidate
    candidates = []
    for candidate_id, records in candidate_groups.items():
        merged = _merge_candidate_group(candidate_id, records)
        candidates.append(merged)

    logger.info(f"Merged {len(normalized_records)} records into {len(candidates)} candidates")
    return candidates


def _entity_resolution(
    normalized_records: List[NormalizedRecord],
) -> Dict[str, List[NormalizedRecord]]:
    """
    Group normalized records by candidate (entity resolution).

    Strategy:
    1. Primary key: normalized email (if present in 2+ sources)
    2. Fallback: hash(normalized name + normalized phone)
    3. Match method recorded in provenance

    Returns:
        Dict of {candidate_id: [records]}
    """
    candidate_groups: Dict[str, List[NormalizedRecord]] = defaultdict(list)
    email_to_id: Dict[str, str] = {}
    name_phone_to_id: Dict[str, str] = {}

    for record in normalized_records:
        # Extract email
        email = _get_normalized_field(record, "email")
        # Extract name and phone for fallback
        name = _get_normalized_field(record, "name")
        phone = _get_normalized_field(record, "phone")

        candidate_id = None

        # Try email match first
        if email:
            email_lower = email.lower()
            if email_lower in email_to_id:
                candidate_id = email_to_id[email_lower]
            else:
                # Check if this email appears in other records
                for other_email in email_to_id.keys():
                    if other_email == email_lower:
                        candidate_id = email_to_id[other_email]
                        break

        # Fallback: name + phone match
        if not candidate_id and name and phone:
            name_phone_key = _hash_name_phone(name, phone)
            if name_phone_key in name_phone_to_id:
                candidate_id = name_phone_to_id[name_phone_key]

        # New candidate
        if not candidate_id:
            candidate_id = str(uuid5(NAMESPACE_DNS, email or f"{name}_{phone}" or str(uuid5(NAMESPACE_DNS, "unknown"))))
            if email:
                email_to_id[email.lower()] = candidate_id
            if name and phone:
                name_phone_key = _hash_name_phone(name, phone)
                name_phone_to_id[name_phone_key] = candidate_id

        candidate_groups[candidate_id].append(record)

    return candidate_groups


def _get_normalized_field(record: NormalizedRecord, field_name: str) -> Optional[str]:
    """Extract and get a normalized field value from a record."""
    candidates = record.normalized_fields.get("candidates")

    if candidates and isinstance(candidates.value, list) and len(candidates.value) > 0:
        cand = candidates.value[0]
        if isinstance(cand, dict):
            return cand.get(field_name)

    # Try direct field
    if field_name in record.normalized_fields:
        field_val = record.normalized_fields[field_name]
        if field_val.value:
            return str(field_val.value)

    return None


def _hash_name_phone(name: str, phone: str) -> str:
    """Create a deterministic hash of name + phone for fuzzy matching."""
    combined = f"{name.lower().strip()}_{phone.strip()}"
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


def _merge_candidate_group(
    candidate_id: str, records: List[NormalizedRecord]
) -> Candidate:
    """Merge a group of records for one candidate using conflict resolution."""
    # Resolve each field using priority table
    full_name = _resolve_field("full_name", records, "name")
    emails = _resolve_list_field("email", "emails", records)
    phones = _resolve_list_field("phone", "phones", records)
    location = _resolve_location(records)
    links = _resolve_links(records)
    headline = _resolve_field("headline", records, "headline")
    years_experience = _resolve_years_experience(records)
    skills = _resolve_skills(records)
    experience = _resolve_experience(records)
    education = _resolve_education(records)

    # Build provenance
    provenance = _build_provenance(
        records,
        full_name,
        emails,
        phones,
        headline,
        years_experience,
        skills,
    )

    # Calculate overall confidence
    overall_confidence = _calculate_overall_confidence(provenance)

    return Candidate(
        candidate_id=candidate_id,
        full_name=full_name or "Unknown",
        emails=emails,
        phones=phones,
        location=location,
        links=links,
        headline=headline,
        years_experience=years_experience,
        skills=skills,
        experience=experience,
        education=education,
        provenance=provenance,
        overall_confidence=overall_confidence,
    )


def _resolve_field(
    field_type: str, records: List[NormalizedRecord], field_name: str = None
) -> Optional[str]:
    """Resolve a scalar field using priority table."""
    if field_name is None:
        field_name = field_type

    candidates_by_source = defaultdict(list)

    # Collect field values from all sources
    for record in records:
        source = record.source_name

        # Extract value from either candidates list or direct field
        candidates = record.normalized_fields.get("candidates")
        if candidates and isinstance(candidates.value, list):
            for cand in candidates.value:
                if isinstance(cand, dict) and field_name in cand:
                    value = cand[field_name]
                    if value:
                        candidates_by_source[source].append(value)

        # Try direct field
        if field_name in record.normalized_fields:
            value = record.normalized_fields[field_name].value
            if value:
                candidates_by_source[source].append(value)

    # Resolve using priority table
    return _pick_best_value(field_type, candidates_by_source)


def _resolve_list_field(
    field_name: str, list_field_name: str, records: List[NormalizedRecord]
) -> List[str]:
    """Resolve a list field (union + dedup)."""
    seen = set()
    result = []

    for record in records:
        # From candidates list
        candidates = record.normalized_fields.get("candidates")
        if candidates and isinstance(candidates.value, list):
            for cand in candidates.value:
                if isinstance(cand, dict):
                    # Check both singular and plural forms
                    for key in [field_name, list_field_name, f"{field_name}s"]:
                        value = cand.get(key)
                        if value:
                            if isinstance(value, list):
                                for item in value:
                                    normalized = str(item).lower().strip()
                                    if normalized and normalized not in seen:
                                        seen.add(normalized)
                                        result.append(item)
                            else:
                                normalized = str(value).lower().strip()
                                if normalized and normalized not in seen:
                                    seen.add(normalized)
                                    result.append(value)

        # Direct field
        if list_field_name in record.normalized_fields:
            value = record.normalized_fields[list_field_name].value
            if isinstance(value, list):
                for item in value:
                    normalized = str(item).lower().strip()
                    if normalized and normalized not in seen:
                        seen.add(normalized)
                        result.append(item)

    return result


def _resolve_location(records: List[NormalizedRecord]) -> Optional[Location]:
    """Resolve location fields."""
    city = _resolve_field("contact", records, "city")
    region = _resolve_field("contact", records, "region")
    country = _resolve_field("contact", records, "country")

    if city or region or country:
        return Location(city=city, region=region, country=country)
    return None


def _resolve_links(records: List[NormalizedRecord]) -> List[Link]:
    """Resolve links (union)."""
    seen = set()
    links = []

    for record in records:
        candidates = record.normalized_fields.get("candidates")
        if candidates and isinstance(candidates.value, list):
            for cand in candidates.value:
                if isinstance(cand, dict):
                    for link_type in ["linkedin", "github", "portfolio"]:
                        value = cand.get(link_type)
                        if value and (link_type, value) not in seen:
                            links.append(Link(type=link_type, url=value))
                            seen.add((link_type, value))

    return links


def _resolve_years_experience(records: List[NormalizedRecord]) -> Optional[float]:
    """Resolve years of experience (average of high-confidence values)."""
    values = []

    for record in records:
        candidates = record.normalized_fields.get("candidates")
        if candidates and isinstance(candidates.value, list):
            for cand in candidates.value:
                if isinstance(cand, dict):
                    value = cand.get("years_experience")
                    if value:
                        try:
                            values.append(float(value))
                        except (ValueError, TypeError):
                            pass

        if "years_experience_hint" in record.normalized_fields:
            value = record.normalized_fields["years_experience_hint"].value
            if value:
                try:
                    values.append(float(value))
                except (ValueError, TypeError):
                    pass

    if values:
        return sum(values) / len(values)
    return None


def _resolve_skills(records: List[NormalizedRecord]) -> List[Skill]:
    """Resolve skills (union by canonical name)."""
    skills_dict: Dict[str, Skill] = {}

    for record in records:
        source = record.source_name

        candidates = record.normalized_fields.get("candidates")
        if candidates and isinstance(candidates.value, list):
            for cand in candidates.value:
                if isinstance(cand, dict):
                    for skills_key in ["skills", "skill_mentions", "languages"]:
                        values = cand.get(skills_key)
                        if values and isinstance(values, list):
                            for skill_name in values:
                                if skill_name:
                                    skill_name = str(skill_name).strip()
                                    if skill_name not in skills_dict:
                                        skills_dict[skill_name] = Skill(
                                            name=skill_name,
                                            confidence=0.7,
                                            canonicalized=False,
                                            sources=[source],
                                        )
                                    else:
                                        if source not in skills_dict[skill_name].sources:
                                            skills_dict[skill_name].sources.append(source)

    return list(skills_dict.values())


def _resolve_experience(records: List[NormalizedRecord]) -> List[Experience]:
    """Resolve experience entries (union)."""
    seen = set()
    experiences = []

    for record in records:
        source = record.source_name

        candidates = record.normalized_fields.get("candidates")
        if candidates and isinstance(candidates.value, list):
            for cand in candidates.value:
                if isinstance(cand, dict):
                    value = cand.get("experience")
                    if value and isinstance(value, list):
                        for exp in value:
                            if isinstance(exp, dict):
                                company = exp.get("company")
                                title = exp.get("title")
                                key = f"{company}_{title}"
                                if key not in seen:
                                    experiences.append(
                                        Experience(
                                            company=company,
                                            title=title,
                                            start=exp.get("start"),
                                            end=exp.get("end"),
                                            summary=exp.get("summary"),
                                            source=source,
                                        )
                                    )
                                    seen.add(key)

    return experiences


def _resolve_education(records: List[NormalizedRecord]) -> List[Education]:
    """Resolve education entries (union)."""
    seen = set()
    educations = []

    for record in records:
        source = record.source_name

        candidates = record.normalized_fields.get("candidates")
        if candidates and isinstance(candidates.value, list):
            for cand in candidates.value:
                if isinstance(cand, dict):
                    value = cand.get("education")
                    if value and isinstance(value, list):
                        for edu in value:
                            if isinstance(edu, dict):
                                institution = edu.get("institution")
                                degree = edu.get("degree")
                                key = f"{institution}_{degree}"
                                if key not in seen:
                                    educations.append(
                                        Education(
                                            institution=institution,
                                            degree=degree,
                                            field=edu.get("field"),
                                            end_year=edu.get("end_year"),
                                            source=source,
                                        )
                                    )
                                    seen.add(key)

    return educations


def _pick_best_value(field_type: str, candidates_by_source: Dict[str, List[str]]) -> Optional[str]:
    """Pick the best value using priority table."""
    if not candidates_by_source:
        return None

    # Get priority order for this field type
    priorities = MERGE_POLICY.get(field_type, [])
    if not priorities:
        # Fallback: alphabetical order for determinism
        priorities = sorted(candidates_by_source.keys())

    # Find first source in priority order that has a value
    for source in priorities:
        if source in candidates_by_source and candidates_by_source[source]:
            return candidates_by_source[source][0]

    # Fallback: alphabetical by source name (deterministic tie-break)
    for source in sorted(candidates_by_source.keys()):
        if candidates_by_source[source]:
            return candidates_by_source[source][0]

    return None


def _build_provenance(
    records: List[NormalizedRecord],
    full_name: Optional[str],
    emails: List[str],
    phones: List[str],
    headline: Optional[str],
    years_experience: Optional[float],
    skills: List[Skill],
) -> List[Provenance]:
    """Build provenance for all resolved fields."""
    provenance = []

    # Full name provenance
    if full_name:
        provenance.append(
            Provenance(
                field="full_name",
                value=full_name,
                sources=[ProvenanceEntry(source_name=r.source_name, extraction_method="normalization", confidence=0.8) for r in records],
                final_confidence=0.85,
                extraction_method="merged",
            )
        )

    # Emails provenance
    if emails:
        provenance.append(
            Provenance(
                field="emails",
                value=",".join(emails),
                sources=[ProvenanceEntry(source_name=r.source_name, extraction_method="normalization", confidence=0.9) for r in records],
                final_confidence=0.9,
                extraction_method="union",
            )
        )

    # Phones provenance
    if phones:
        provenance.append(
            Provenance(
                field="phones",
                value=",".join(phones),
                sources=[ProvenanceEntry(source_name=r.source_name, extraction_method="normalization", confidence=0.85) for r in records],
                final_confidence=0.85,
                extraction_method="union",
            )
        )

    return provenance


def _calculate_overall_confidence(provenance: List[Provenance]) -> float:
    """Calculate overall confidence as weighted average of field confidences."""
    if not provenance:
        return 0.5

    field_weights = {
        "full_name": 0.2,
        "emails": 0.2,
        "phones": 0.1,
        "location": 0.1,
        "skills": 0.15,
        "experience": 0.15,
        "education": 0.1,
    }

    total_weighted = 0.0
    total_weight = 0.0

    for prov in provenance:
        weight = field_weights.get(prov.field, 0.1)
        total_weighted += prov.final_confidence * weight
        total_weight += weight

    if total_weight == 0:
        return 0.5

    return total_weighted / total_weight
