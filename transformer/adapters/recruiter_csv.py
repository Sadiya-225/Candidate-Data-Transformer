"""Recruiter CSV adapter: parse rows with name, email, phone, current_company, title."""

import csv
import logging
from typing import Union, Optional
from datetime import datetime

from .base import BaseSourceAdapter
from transformer.models import RawRecord

logger = logging.getLogger(__name__)


class RecruiterCSVAdapter(BaseSourceAdapter):
    """Adapter for recruiter CSV exports with standard columns."""

    @property
    def source_name(self) -> str:
        return "recruiter_csv"

    def detect(self, input_source: Union[str, bytes, dict]) -> bool:
        """Detect if input is a CSV file (by extension)."""
        if isinstance(input_source, str):
            return input_source.lower().endswith(".csv") and not input_source.startswith("http")
        return False

    def extract(self, raw_input: Union[str, bytes, dict]) -> RawRecord:
        """Extract rows from CSV file."""
        if not isinstance(raw_input, str):
            raise ValueError("RecruiterCSV adapter expects a file path (str)")

        file_path = raw_input
        rows = []
        error = None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames is None:
                    raise ValueError("CSV file is empty or has no header")

                # Normalize column names to lowercase
                fieldnames = [fn.lower() if fn else None for fn in reader.fieldnames]

                for i, row in enumerate(reader):
                    # Normalize keys
                    normalized_row = {k.lower() if k else None: v for k, v in row.items()}

                    # Extract standard fields
                    candidate = {
                        "name": normalized_row.get("name"),
                        "email": normalized_row.get("email"),
                        "phone": normalized_row.get("phone"),
                        "current_company": normalized_row.get("current_company") or normalized_row.get("company"),
                        "title": normalized_row.get("title") or normalized_row.get("job_title"),
                    }
                    rows.append(candidate)

                logger.info(f"Extracted {len(rows)} rows from {file_path}")

        except Exception as e:
            logger.error(f"Error reading CSV file {file_path}: {e}")
            error = str(e)

        return RawRecord(
            source_name=self.source_name,
            source_method="csv_file_parse",
            extracted_fields={
                "candidates": rows,
                "row_count": len(rows),
            },
            parse_error=error,
        )
