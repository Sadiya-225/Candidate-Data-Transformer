"""Skill normalization against a canonical taxonomy."""

import logging
import json
import os
from typing import Optional, Tuple, Dict, List

logger = logging.getLogger(__name__)

# Cache for taxonomy (loaded once)
_TAXONOMY_CACHE: Optional[Dict[str, List[str]]] = None


def _load_taxonomy() -> Dict[str, List[str]]:
    """Load and cache the skills taxonomy."""
    global _TAXONOMY_CACHE

    if _TAXONOMY_CACHE is not None:
        return _TAXONOMY_CACHE

    # Find taxonomy file relative to this module
    module_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(module_dir))
    taxonomy_path = os.path.join(project_root, "data", "skills_taxonomy.json")

    if not os.path.exists(taxonomy_path):
        logger.warning(f"Skills taxonomy not found at {taxonomy_path}, using empty taxonomy")
        _TAXONOMY_CACHE = {}
        return _TAXONOMY_CACHE

    try:
        with open(taxonomy_path, "r") as f:
            data = json.load(f)
            # Convert to canonical -> aliases mapping
            _TAXONOMY_CACHE = data.get("skills", {})
            return _TAXONOMY_CACHE
    except Exception as e:
        logger.error(f"Failed to load skills taxonomy: {e}")
        _TAXONOMY_CACHE = {}
        return _TAXONOMY_CACHE


def normalize_skill(raw_value: Optional[str]) -> Tuple[Optional[str], float, bool, bool]:
    """
    Normalize a skill name to canonical form.

    Args:
        raw_value: Skill name (e.g., "ReactJS", "react", "React.js", "Kubernetes", "k8s")

    Returns:
        Tuple of (canonical_skill, confidence, success, canonicalized):
        - canonical_skill: Canonical skill name or original if not recognized
        - confidence: 0.0–1.0
        - success: Whether processing succeeded (True if we got any skill)
        - canonicalized: Whether the skill was found in taxonomy

    Notes:
        - If skill found in taxonomy: return canonical name, high confidence
        - If skill not found: return raw value, mark canonicalized=False
        - Never drop unrecognized skills
    """
    if not raw_value or not isinstance(raw_value, str):
        return None, 0.0, False, False

    raw_value = raw_value.strip()
    if not raw_value:
        return None, 0.0, False, False

    taxonomy = _load_taxonomy()
    if not taxonomy:
        # No taxonomy, just normalize casing and return
        return raw_value, 0.5, True, False

    # Normalize for lookup: lowercase, strip whitespace
    lookup_key = raw_value.lower().strip()

    # Check each canonical skill and its aliases
    for canonical, aliases in taxonomy.items():
        # Check canonical name
        if canonical.lower() == lookup_key:
            return canonical, 0.95, True, True

        # Check aliases
        for alias in aliases:
            if alias.lower() == lookup_key:
                return canonical, 0.90, True, True

    # Not found in taxonomy: return raw value with canonicalized=False
    logger.debug(f"Skill not in taxonomy: {raw_value}")
    return raw_value, 0.6, True, False
