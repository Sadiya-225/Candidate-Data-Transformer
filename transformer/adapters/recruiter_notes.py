"""Recruiter notes adapter: parse free-text notes with regex/heuristics."""

import logging
import re
from typing import Union

from .base import BaseSourceAdapter
from transformer.models import RawRecord

logger = logging.getLogger(__name__)

# Email and phone regex
EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
PHONE_REGEX = r"[\+]?[(]?[0-9]{3}[)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{4,6}"


class RecruiterNotesAdapter(BaseSourceAdapter):
    """Adapter for free-text recruiter notes."""

    @property
    def source_name(self) -> str:
        return "recruiter_notes"

    def detect(self, input_source: Union[str, bytes, dict]) -> bool:
        """Detect if input is a text notes file."""
        if isinstance(input_source, str):
            return input_source.lower().endswith(".txt")
        return False

    def extract(self, raw_input: Union[str, bytes, dict]) -> RawRecord:
        """Extract mentions from notes text."""
        error = None
        text = ""

        try:
            if isinstance(raw_input, str):
                # File path
                with open(raw_input, "r", encoding="utf-8") as f:
                    text = f.read()
            else:
                raise ValueError("RecruiterNotes adapter expects a file path")

            # Parse text for mentions
            extracted = self._parse_notes_text(text)
            logger.info(f"Extracted notes: {len(extracted['skill_mentions'])} skills, {len(extracted['company_mentions'])} companies")

        except Exception as e:
            logger.error(f"Error parsing recruiter notes: {e}")
            error = str(e)
            extracted = {
                "skill_mentions": [],
                "company_mentions": [],
                "title_mentions": [],
                "years_experience_hint": None,
            }

        return RawRecord(
            source_name=self.source_name,
            source_method="text_regex_heuristic",
            extracted_fields=extracted,
            raw_text=text,
            parse_error=error,
        )

    @staticmethod
    def _parse_notes_text(text: str) -> dict:
        """Parse recruiter notes for mentions."""
        extracted = {
            "skill_mentions": [],
            "company_mentions": [],
            "title_mentions": [],
            "years_experience_hint": None,
            "emails": [],
            "phones": [],
        }

        # Extract emails
        emails = re.findall(EMAIL_REGEX, text)
        extracted["emails"] = list(set(e.lower() for e in emails))

        # Extract phones
        phones = re.findall(PHONE_REGEX, text)
        extracted["phones"] = list(set(phones))

        # Extract years of experience mentions ("5 years", "5-7 years", etc.)
        years_match = re.search(r"(\d+)\s*(?:to|-|–)?\s*(\d+)?\s*(?:year|yr)s?\s*(?:of\s+experience)?", text, re.IGNORECASE)
        if years_match:
            start = int(years_match.group(1))
            end = int(years_match.group(2)) if years_match.group(2) else start
            extracted["years_experience_hint"] = (start + end) / 2

        # Extract skill mentions (look for common keywords)
        tech_skills = [
            "python", "javascript", "java", "react", "django", "flask", "sql",
            "kubernetes", "docker", "aws", "gcp", "azure", "postgres", "mongodb",
            "nodejs", "node.js", "typescript", "c++", "golang", "rust", "devops"
        ]
        for skill in tech_skills:
            if re.search(rf"\b{skill}\b", text, re.IGNORECASE):
                extracted["skill_mentions"].append(skill.capitalize())

        # Extract company mentions (look for common company patterns)
        # Look for capitalized words followed by "Inc", "LLC", "Ltd", "Corp"
        company_matches = re.findall(
            r"(?:at|worked at|formerly at)\s+([A-Z][a-zA-Z\s]+(?:Inc|LLC|Ltd|Corp|Inc\.|LLC\.|Ltd\.|Corp\.)?)",
            text
        )
        extracted["company_mentions"] = [c.strip() for c in company_matches]

        # Extract job title mentions
        titles = [
            "engineer", "manager", "developer", "analyst", "architect", "lead",
            "senior", "junior", "principal", "director", "vp", "cto", "ceo"
        ]
        for title in titles:
            if re.search(rf"\b{title}\b", text, re.IGNORECASE):
                extracted["title_mentions"].append(title.capitalize())

        return extracted
