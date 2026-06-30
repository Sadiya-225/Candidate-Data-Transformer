"""Resume DOCX adapter: extract text and parse with regex/heuristics."""

import logging
import re
from typing import Union
from docx import Document

from .base import BaseSourceAdapter
from transformer.models import RawRecord
from .resume_pdf import EMAIL_REGEX, PHONE_REGEX

logger = logging.getLogger(__name__)


class ResumeDocxAdapter(BaseSourceAdapter):
    """Adapter for DOCX resumes using python-docx."""

    @property
    def source_name(self) -> str:
        return "resume_docx"

    def detect(self, input_source: Union[str, bytes, dict]) -> bool:
        """Detect if input is a DOCX file."""
        if isinstance(input_source, str):
            return input_source.lower().endswith(".docx")
        return False

    def extract(self, raw_input: Union[str, bytes, dict]) -> RawRecord:
        """Extract data from DOCX resume."""
        error = None
        text = ""
        extracted = {
            "name": None,
            "emails": [],
            "phones": [],
            "skills": [],
            "experience": [],
            "education": [],
        }

        try:
            if not isinstance(raw_input, str):
                raise ValueError("Resume DOCX adapter expects a file path (str)")

            # Load DOCX
            doc = Document(raw_input)

            # Extract all text from paragraphs
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text += paragraph.text + "\n"

            # Parse extracted text (reuse PDF parsing logic)
            extracted = self._parse_resume_text(text)

            logger.info(f"Extracted resume from DOCX, found {len(extracted['skills'])} skills")

        except Exception as e:
            logger.error(f"Error parsing DOCX resume: {e}")
            error = str(e)

        return RawRecord(
            source_name=self.source_name,
            source_method="docx_text_extraction",
            extracted_fields=extracted,
            raw_text=text[:1000],
            parse_error=error,
        )

    @staticmethod
    def _parse_resume_text(text: str) -> dict:
        """Parse resume text using heuristics (same as PDF)."""
        extracted = {
            "name": None,
            "emails": [],
            "phones": [],
            "skills": [],
            "experience": [],
            "education": [],
        }

        # Extract emails
        emails = re.findall(EMAIL_REGEX, text)
        extracted["emails"] = list(set(e.lower() for e in emails))

        # Extract phone numbers
        phones = re.findall(PHONE_REGEX, text)
        extracted["phones"] = list(set(phones))

        # Extract name (first line, usually)
        lines = text.split("\n")
        for line in lines[:5]:
            line = line.strip()
            if len(line) > 5 and len(line) < 100 and "@" not in line:
                extracted["name"] = line
                break

        # Extract skills
        skills_match = re.search(
            r"(?:Skills|Technical Skills|Competencies)[:\s]+(.*?)(?:Experience|Projects|Education|$)",
            text,
            re.IGNORECASE | re.DOTALL
        )
        if skills_match:
            skills_text = skills_match.group(1)
            skills = re.split(r"[,\n•\-]+", skills_text)
            extracted["skills"] = [
                s.strip() for s in skills if s.strip() and len(s.strip()) < 50
            ]

        # Extract education
        edu_match = re.search(
            r"(?:Education|Academic Background)[:\s]+(.*?)(?:Experience|Projects|Skills|$)",
            text,
            re.IGNORECASE | re.DOTALL
        )
        if edu_match:
            edu_text = edu_match.group(1)
            degree_matches = re.findall(
                r"(Bachelor|Master|PhD|Associate|Diploma)['\s]?s?\s+(?:of|in)?\s+([^,\n]+)",
                edu_text,
                re.IGNORECASE
            )
            extracted["education"] = [
                {"degree": d[0], "field": d[1].strip()} for d in degree_matches
            ]

        # Extract experience
        exp_matches = re.findall(
            r"(.*?)\s+[\|–\-]\s+(.*?)\s+(?:\(|at|@)\s+([^,\n]+)",
            text
        )
        extracted["experience"] = [
            {"title": e[1].strip(), "company": e[2].strip()} for e in exp_matches[:10]
        ]

        return extracted
