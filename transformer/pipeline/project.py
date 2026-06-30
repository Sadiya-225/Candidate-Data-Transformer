"""PROJECT stage: transform canonical candidates into configured output shape."""

import logging
import re
from typing import List, Dict, Any, Optional
from transformer.models import Candidate, ProjectionConfig

logger = logging.getLogger(__name__)


def project(
    candidates: List[Candidate],
    config: ProjectionConfig,
) -> List[Dict[str, Any]]:
    """
    Project candidates into output shape using config.

    Args:
        candidates: List of Candidate from CONFIDENCE stage
        config: ProjectionConfig defining output schema

    Returns:
        List of dicts matching the output schema
    """
    results = []

    for candidate in candidates:
        projected = _project_candidate(candidate, config)
        results.append(projected)

    logger.info(f"Projected {len(candidates)} candidates")
    return results


def _project_candidate(candidate: Candidate, config: ProjectionConfig) -> Dict[str, Any]:
    """Project a single candidate using config."""
    output = {}

    for field_config in config.fields:
        path_expr = field_config.from_
        output_key = field_config.path

        # Evaluate path expression
        try:
            value = _evaluate_path(path_expr, candidate)
        except Exception as e:
            logger.warning(f"Failed to evaluate path '{path_expr}': {e}")
            value = None

        # Apply per-field normalization if specified
        if value is not None and field_config.normalize:
            value = _apply_normalization(value, field_config.normalize)

        # Handle missing values
        if value is None:
            if config.on_missing == "error" and field_config.required:
                raise ValueError(f"Required field {output_key} (from {path_expr}) is missing")
            elif config.on_missing == "omit":
                continue
            # else: "null" (default)

        # Convert to JSON-serializable format
        if hasattr(value, 'model_dump'):  # Pydantic model
            value = value.model_dump()
        elif isinstance(value, list):
            # Convert list items if they're Pydantic models
            value = [
                item.model_dump() if hasattr(item, 'model_dump') else item
                for item in value
            ]

        # Set value
        output[output_key] = value

        # Add confidence/provenance if requested
        if field_config.include_confidence:
            output[f"{output_key}_confidence"] = _get_field_confidence(candidate, path_expr)
        if field_config.include_provenance:
            output[f"{output_key}_provenance"] = _get_field_provenance(candidate, path_expr)

    # Add global confidence/provenance if requested
    if config.include_confidence:
        output["overall_confidence"] = candidate.overall_confidence
    if config.include_provenance:
        output["provenance"] = [p.model_dump() for p in candidate.provenance]

    return output


def _evaluate_path(path_expr: str, candidate: Candidate) -> Any:
    """
    Evaluate a path expression against a candidate.

    Supported syntax:
    - Dotted paths: `full_name`, `location.country`
    - Array indexing: `emails[0]`, `phones[1]`
    - Array flattening: `skills[].name`, `experience[].title`
    """
    path_expr = path_expr.strip()

    # Array flattening: "skills[].name" or "experience[]"
    if "[]" in path_expr:
        return _evaluate_array_flatten(path_expr, candidate)

    # Array indexing: "emails[0]", "phones[1]"
    if "[" in path_expr and "]" in path_expr:
        return _evaluate_array_index(path_expr, candidate)

    # Dotted path: "location.country", "full_name"
    return _evaluate_dotted_path(path_expr, candidate)


def _evaluate_dotted_path(path_expr: str, obj: Any) -> Any:
    """Evaluate a dotted path like 'location.country' or 'full_name'."""
    parts = path_expr.split(".")

    current = obj
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            # Try as attribute
            current = getattr(current, part, None)

        if current is None:
            return None

    return current


def _evaluate_array_index(path_expr: str, obj: Any) -> Any:
    """Evaluate array indexing like 'emails[0]' or 'phones[1]'."""
    match = re.match(r"([\w.]+)\[(\d+)\]", path_expr)
    if not match:
        raise ValueError(f"Invalid array index syntax: {path_expr}")

    base_path = match.group(1)
    index = int(match.group(2))

    # Evaluate base path
    value = _evaluate_dotted_path(base_path, obj)
    if not isinstance(value, list):
        return None

    if index < len(value):
        return value[index]

    return None


def _evaluate_array_flatten(path_expr: str, obj: Any) -> List[Any]:
    """Evaluate array flattening like 'skills[].name' or 'experience[]'."""
    # Pattern: "base[].subfield" or "base[]"
    match = re.match(r"([\w.]+)\[\](?:\.(\w+))?", path_expr)
    if not match:
        raise ValueError(f"Invalid array flatten syntax: {path_expr}")

    base_path = match.group(1)
    subfield = match.group(2)

    # Evaluate base path to get array
    value = _evaluate_dotted_path(base_path, obj)
    if not isinstance(value, list):
        return []

    # If no subfield, return array as-is
    if not subfield:
        return value

    # Extract subfield from each element
    results = []
    for item in value:
        if isinstance(item, dict):
            subval = item.get(subfield)
        else:
            subval = getattr(item, subfield, None)

        if subval is not None:
            results.append(subval)

    return results


def _apply_normalization(value: Any, normalize_spec: str) -> Any:
    """Apply normalization override specified in config."""
    if not isinstance(value, str):
        return value

    from transformer.normalize import (
        normalize_phone,
        normalize_skill,
    )

    if normalize_spec == "E164":
        # Re-normalize as phone
        normalized, _, _ = normalize_phone(value)
        return normalized
    elif normalize_spec == "canonical":
        # Normalize as skill
        normalized, _, _, _ = normalize_skill(value)
        return normalized
    else:
        # Unknown normalization, return as-is
        logger.warning(f"Unknown normalization spec: {normalize_spec}")
        return value


def _get_field_confidence(candidate: Candidate, path_expr: str) -> Optional[float]:
    """Get confidence for a field from provenance."""
    # Extract base field name from path expression
    base_field = path_expr.split("[")[0].split(".")[0]

    for prov in candidate.provenance:
        if prov.field == base_field:
            return prov.final_confidence

    # Default: use overall confidence
    return candidate.overall_confidence


def _get_field_provenance(candidate: Candidate, path_expr: str) -> Optional[Dict[str, Any]]:
    """Get provenance for a field."""
    base_field = path_expr.split("[")[0].split(".")[0]

    for prov in candidate.provenance:
        if prov.field == base_field:
            return prov.model_dump()

    return None
