"""Resume PDF adapter: extract text and parse with regex/heuristics."""

import logging
import re
from typing import Union, Optional, List
import pdfplumber

from .base import BaseSourceAdapter
from transformer.models import RawRecord

logger = logging.getLogger(__name__)

# Email regex
EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
# Phone regex (simple)
PHONE_REGEX = r"[\+]?[(]?[0-9]{3}[)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{4,6}"


class ResumePDFAdapter(BaseSourceAdapter):
    """Adapter for PDF resumes using pdfplumber."""

    @property
    def source_name(self) -> str:
        return "resume_pdf"

    def detect(self, input_source: Union[str, bytes, dict]) -> bool:
        """Detect if input is a PDF file."""
        if isinstance(input_source, str):
            return input_source.lower().endswith(".pdf")
        elif isinstance(input_source, bytes):
            # Check for PDF magic number
            return input_source.startswith(b"%PDF")
        return False

    def extract(self, raw_input: Union[str, bytes, dict]) -> RawRecord:
        """Extract data from PDF resume."""
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
            # Load PDF
            if isinstance(raw_input, str):
                pdf_file = pdfplumber.open(raw_input)
            elif isinstance(raw_input, bytes):
                import io
                pdf_file = pdfplumber.open(io.BytesIO(raw_input))
            else:
                raise ValueError("Resume PDF adapter expects file path or bytes")

            # Extract all text
            for page in pdf_file.pages:
                text += page.extract_text() or ""

            pdf_file.close()

            # Parse extracted text
            extracted = self._parse_resume_text(text)

        except Exception as e:
            logger.error(f"Error parsing PDF resume: {e}")
            error = str(e)

        return RawRecord(
            source_name=self.source_name,
            source_method="pdf_text_extraction",
            extracted_fields=extracted,
            raw_text=text[:1000],  # Keep first 1000 chars for debugging
            parse_error=error,
        )

    @staticmethod
    def _parse_resume_text(text: str) -> dict:
        """Parse resume text using heuristics."""
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
        for line in lines[:5]:  # Check first few lines
            line = line.strip()
            if len(line) > 5 and len(line) < 100 and not "@" in line:
                # Likely a name
                extracted["name"] = line
                break

        # Extract skills (look for "Skills" section)
        skills_match = re.search(
            r"(?:Skills|Technical Skills|Competencies)[:\s]+(.*?)(?:Experience|Projects|Education|$)",
            text,
            re.IGNORECASE | re.DOTALL
        )
        if skills_match:
            skills_text = skills_match.group(1)
            # Split by comma, bullet, newline
            skills = re.split(r"[,\n•\-]+", skills_text)
            extracted["skills"] = [
                s.strip() for s in skills if s.strip() and len(s.strip()) < 50
            ]

        # Extract education (look for "Education" section)
        edu_match = re.search(
            r"(?:Education|Academic Background)[:\s]+(.*?)(?:Experience|Projects|Skills|$)",
            text,
            re.IGNORECASE | re.DOTALL
        )
        if edu_match:
            edu_text = edu_match.group(1)
            # Look for degree patterns: Bachelor, Master, PhD, etc.
            degree_matches = re.findall(
                r"(Bachelor|Master|PhD|Associate|Diploma)['\s]?s?\s+(?:of|in)?\s+([^,\n]+)",
                edu_text,
                re.IGNORECASE
            )
            extracted["education"] = [
                {"degree": d[0], "field": d[1].strip()} for d in degree_matches
            ]

        # Extract experience (look for date ranges)
        exp_matches = re.findall(
            r"(.*?)\s+[\|–\-]\s+(.*?)\s+(?:\(|at|@)\s+([^,\n]+)",
            text
        )
        extracted["experience"] = [
            {"title": e[1].strip(), "company": e[2].strip()} for e in exp_matches[:10]
        ]

        return extracted
