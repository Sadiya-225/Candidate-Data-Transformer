"""VALIDATE stage: validate output against config schema."""

import logging
from typing import List, Dict, Any
import jsonschema
from jsonschema import ValidationError

from transformer.models import ProjectionConfig

logger = logging.getLogger(__name__)


def validate(
    output: List[Dict[str, Any]],
    config: ProjectionConfig,
) -> List[Dict[str, Any]]:
    """
    Validate output against config-derived JSON schema.

    Args:
        output: List of projected candidate dicts
        config: ProjectionConfig

    Returns:
        Same output if validation passes

    Raises:
        ValidationError if validation fails

    Notes:
        - Never silently emit invalid JSON
        - Raises descriptive error with all violations
    """
    schema = _generate_schema(config)

    errors = []
    for i, candidate in enumerate(output):
        try:
            jsonschema.validate(instance=candidate, schema=schema)
        except ValidationError as e:
            errors.append(f"Candidate {i}: {e.message}")

    if errors:
        error_msg = f"Validation failed for {len(errors)} candidate(s):\n" + "\n".join(errors[:5])
        if len(errors) > 5:
            error_msg += f"\n... and {len(errors) - 5} more errors"
        logger.error(error_msg)
        raise ValidationError(error_msg)

    logger.info(f"Validated {len(output)} candidates")
    return output


def _generate_schema(config: ProjectionConfig) -> Dict[str, Any]:
    """Generate JSON schema from projection config."""
    properties = {}
    required = []

    for field_config in config.fields:
        json_type = _type_to_json_type(field_config.type)

        # Allow null for non-required fields
        if field_config.required:
            prop_schema = {"type": json_type}
        else:
            prop_schema = {"type": [json_type, "null"]}

        if field_config.required:
            required.append(field_config.path)

        properties[field_config.path] = prop_schema

    # Add confidence/provenance fields if global flags are set
    if config.include_confidence:
        properties["overall_confidence"] = {"type": "number"}
    if config.include_provenance:
        properties["provenance"] = {"type": "array"}

    schema = {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": True,  # Allow extra fields
    }

    return schema


def _type_to_json_type(type_spec: str) -> str:
    """Map projection config type to JSON schema type."""
    type_lower = type_spec.lower()

    if "[]" in type_lower:
        return "array"
    elif "string" in type_lower:
        return "string"
    elif "number" in type_lower:
        return "number"
    elif "object" in type_lower:
        return "object"
    else:
        return "string"  # Default
