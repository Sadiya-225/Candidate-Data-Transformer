"""NORMALIZE stage: normalize fields using per-field normalizers."""

import logging
from typing import List, Optional, Any, Tuple
from transformer.models import RawRecord, NormalizedRecord, NormalizedValue
from transformer.normalize import (
    normalize_phone,
    normalize_date,
    normalize_country,
    normalize_email,
    normalize_name,
    normalize_skill,
    normalize_years_experience,
)

logger = logging.getLogger(__name__)


def normalize(raw_records: List[RawRecord]) -> List[NormalizedRecord]:
    """
    Normalize fields from raw records.

    Args:
        raw_records: List of RawRecord from EXTRACT stage

    Returns:
        List of NormalizedRecord (same count as input)
    """
    normalized_records = []

    for raw_record in raw_records:
        normalized = _normalize_record(raw_record)
        normalized_records.append(normalized)

    return normalized_records


def _normalize_record(raw_record: RawRecord) -> NormalizedRecord:
    """Normalize a single RawRecord."""
    normalized_fields = {}

    # For each extracted field, apply appropriate normalizer
    for field_name, raw_value in raw_record.extracted_fields.items():
        if field_name in ("candidates", "row_count"):
            # Special handling for CSV rows
            if field_name == "candidates" and isinstance(raw_value, list):
                normalized_fields[field_name] = NormalizedValue(
                    value=_normalize_candidate_list(raw_value, raw_record.source_name),
                    source=raw_record.source_name,
                    method="candidate_list_normalization",
                    success=True,
                    confidence=0.8,
                    raw_value=raw_value,
                )
            continue

        # Normalize scalar fields
        if isinstance(raw_value, str):
            normalized_value, confidence, success = _normalize_field(
                field_name, raw_value, raw_record.source_name
            )
            normalized_fields[field_name] = NormalizedValue(
                value=normalized_value,
                source=raw_record.source_name,
                method=f"normalize_{field_name}",
                success=success,
                confidence=confidence,
                raw_value=raw_value,
            )
        elif isinstance(raw_value, list):
            # Normalize list fields
            normalized_list = []
            for item in raw_value:
                if isinstance(item, str):
                    norm_val, conf, success = _normalize_field(
                        field_name, item, raw_record.source_name
                    )
                    if success:
                        normalized_list.append(norm_val)
            if normalized_list:
                normalized_fields[field_name] = NormalizedValue(
                    value=normalized_list,
                    source=raw_record.source_name,
                    method=f"normalize_list_{field_name}",
                    success=True,
                    confidence=0.8,
                    raw_value=raw_value,
                )
        elif isinstance(raw_value, dict):
            # Keep dicts as-is for now (e.g., profile data from GitHub)
            normalized_fields[field_name] = NormalizedValue(
                value=raw_value,
                source=raw_record.source_name,
                method="passthrough",
                success=True,
                confidence=0.7,
                raw_value=raw_value,
            )

    return NormalizedRecord(
        source_name=raw_record.source_name,
        source_method=raw_record.source_method,
        candidate_id_temp=_generate_temp_candidate_id(raw_record),
        normalized_fields=normalized_fields,
        parse_error=raw_record.parse_error,
    )


def _normalize_field(
    field_name: str, raw_value: str, source_name: str
) -> Tuple[Optional[Any], float, bool]:
    """Normalize a single field value based on field name."""
    field_lower = field_name.lower()

    if not raw_value or not isinstance(raw_value, str):
        return None, 0.0, False

    # Email
    if "email" in field_lower:
        return normalize_email(raw_value)

    # Phone
    if "phone" in field_lower:
        return normalize_phone(raw_value)

    # Name
    if "name" in field_lower:
        return normalize_name(raw_value)

    # Date fields
    if any(x in field_lower for x in ("start", "end", "date")):
        date_type = "end" if "end" in field_lower else "start"
        return normalize_date(raw_value, date_type=date_type)

    # Country
    if "country" in field_lower or "location" in field_lower:
        return normalize_country(raw_value)

    # Skill
    if "skill" in field_lower:
        norm_skill, conf, success, _ = normalize_skill(raw_value)
        return norm_skill, conf, success

    # Years experience
    if "year" in field_lower and "experience" in field_lower:
        return normalize_years_experience(raw_value)

    # Default: passthrough
    return raw_value, 0.7, True


def _normalize_candidate_list(
    candidates: list, source_name: str
) -> list:
    """Normalize a list of candidate dicts from a CSV or JSON source."""
    normalized = []

    for cand in candidates:
        if not isinstance(cand, dict):
            continue

        norm_cand = {}
        for key, value in cand.items():
            key_lower = key.lower()

            if value is None or not value:
                norm_cand[key] = value
                continue

            # Normalize specific fields
            if "email" in key_lower:
                norm_val, _, _ = normalize_email(value) if isinstance(value, str) else (value, 0, False)
            elif "phone" in key_lower:
                norm_val, _, _ = normalize_phone(value) if isinstance(value, str) else (value, 0, False)
            elif "name" in key_lower:
                norm_val, _, _ = normalize_name(value) if isinstance(value, str) else (value, 0, False)
            else:
                norm_val = value

            norm_cand[key] = norm_val

        normalized.append(norm_cand)

    return normalized


def _generate_temp_candidate_id(raw_record: RawRecord) -> str:
    """Generate a temporary candidate ID from raw record."""
    # Use source + extracted name/email as hint
    candidates = raw_record.extracted_fields.get("candidates")
    if candidates and isinstance(candidates, list) and len(candidates) > 0:
        first_cand = candidates[0]
        if isinstance(first_cand, dict):
            name = first_cand.get("name", "")
            email = first_cand.get("email", "")
            if name or email:
                return f"{raw_record.source_name}_{name or email}".replace(" ", "_")[:50]

    # Fallback: use source + hash
    import hashlib
    return f"{raw_record.source_name}_{hashlib.md5(str(raw_record.extracted_fields).encode()).hexdigest()[:8]}"
