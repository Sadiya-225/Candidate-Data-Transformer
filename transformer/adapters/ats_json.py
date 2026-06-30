"""ATS JSON adapter: parse semi-structured ATS blob with ATS-specific field names."""

import json
import logging
from typing import Union, Optional, Any

from .base import BaseSourceAdapter
from transformer.models import RawRecord

logger = logging.getLogger(__name__)

# Common ATS field name patterns
ATS_FIELD_PATTERNS = [
    "candidateName", "candidateEmail", "candidatePhone",
    "jobTitle", "jobPosition", "skillTags", "skills",
    "workHistory", "employment", "education",
    "phoneNumbers", "contactEmail", "emails",
]


class ATSJSONAdapter(BaseSourceAdapter):
    """Adapter for semi-structured ATS JSON blobs."""

    @property
    def source_name(self) -> str:
        return "ats_json"

    def detect(self, input_source: Union[str, bytes, dict]) -> bool:
        """Detect if input is an ATS JSON (by extension or by field names)."""
        # If it's a dict, try to sniff for ATS fields
        if isinstance(input_source, dict):
            keys = set(input_source.keys()) | set(
                k for v in input_source.values()
                if isinstance(v, dict)
                for k in v.keys()
            )
            # Check if any ATS field pattern is present
            return any(pattern in str(keys) for pattern in ATS_FIELD_PATTERNS)

        # If it's a file path, check extension
        if isinstance(input_source, str) and not input_source.startswith("http"):
            return input_source.lower().endswith(".json")

        return False

    def extract(self, raw_input: Union[str, bytes, dict]) -> RawRecord:
        """Extract data from ATS JSON."""
        error = None
        candidates = []

        try:
            if isinstance(raw_input, str):
                # File path
                with open(raw_input, "r", encoding="utf-8") as f:
                    data = json.load(f)
            elif isinstance(raw_input, bytes):
                data = json.loads(raw_input.decode("utf-8"))
            elif isinstance(raw_input, dict):
                data = raw_input
            else:
                raise ValueError("ATS adapter expects file path, bytes, or dict")

            # ATS could be a single candidate dict or a list
            if isinstance(data, list):
                candidates_raw = data
            elif isinstance(data, dict) and "candidates" in data:
                candidates_raw = data["candidates"]
            else:
                candidates_raw = [data]

            # Normalize each candidate
            for cand in candidates_raw:
                if not isinstance(cand, dict):
                    continue

                normalized = self._normalize_ats_candidate(cand)
                candidates.append(normalized)

            logger.info(f"Extracted {len(candidates)} candidates from ATS JSON")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in ATS input: {e}")
            error = str(e)
        except Exception as e:
            logger.error(f"Error parsing ATS JSON: {e}")
            error = str(e)

        return RawRecord(
            source_name=self.source_name,
            source_method="ats_json_parse",
            extracted_fields={"candidates": candidates},
            parse_error=error,
        )

    @staticmethod
    def _normalize_ats_candidate(ats_dict: dict) -> dict:
        """Normalize ATS field names to canonical."""
        # Map common ATS field names to canonical names
        field_map = {
            # Names
            "candidateName": "name",
            "candidate_name": "name",
            "name": "name",
            "full_name": "name",
            # Email
            "candidateEmail": "email",
            "contactEmail": "email",
            "emails": "emails",
            "email": "email",
            # Phone
            "candidatePhone": "phone",
            "phoneNumbers": "phones",
            "phone": "phone",
            "phones": "phones",
            # Company/Employer
            "employer": "current_company",
            "company": "current_company",
            "current_employer": "current_company",
            # Job Title
            "jobTitle": "title",
            "job_title": "title",
            "title": "title",
            "position": "title",
            # Skills
            "skillTags": "skills",
            "skills": "skills",
            "skill_tags": "skills",
            # Experience
            "workHistory": "experience",
            "employment": "experience",
            "work_history": "experience",
            # Education
            "education": "education",
            # Headline
            "headline": "headline",
            "bio": "headline",
        }

        normalized = {}
        for ats_key, value in ats_dict.items():
            canonical_key = field_map.get(ats_key, ats_key)
            normalized[canonical_key] = value

        return normalized
