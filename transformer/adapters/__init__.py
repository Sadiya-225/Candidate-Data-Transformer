"""Source adapters for different candidate data sources."""

import logging
from typing import Union, Type, Optional
from transformer.adapters.base import BaseSourceAdapter
from transformer.adapters.recruiter_csv import RecruiterCSVAdapter
from transformer.adapters.ats_json import ATSJSONAdapter
from transformer.adapters.github import GitHubProfileAdapter
from transformer.adapters.resume_pdf import ResumePDFAdapter
from transformer.adapters.resume_docx import ResumeDocxAdapter
from transformer.adapters.recruiter_notes import RecruiterNotesAdapter

logger = logging.getLogger(__name__)

# Source registry: maps adapter names to adapter classes
SOURCE_REGISTRY = {
    "recruiter_csv": RecruiterCSVAdapter,
    "ats_json": ATSJSONAdapter,
    "github": GitHubProfileAdapter,
    "resume_pdf": ResumePDFAdapter,
    "resume_docx": ResumeDocxAdapter,
    "recruiter_notes": RecruiterNotesAdapter,
}


def detect_source(input_source: Union[str, bytes, dict]) -> Optional[BaseSourceAdapter]:
    """
    Detect the source type and return an instantiated adapter.

    Args:
        input_source: File path, bytes, dict, or URI string

    Returns:
        Instantiated adapter if detected, None if unrecognized (with warning logged)
    """
    for source_name, adapter_class in SOURCE_REGISTRY.items():
        try:
            adapter = adapter_class()
            if adapter.detect(input_source):
                logger.debug(f"Detected source type: {source_name}")
                return adapter
        except Exception as e:
            logger.debug(f"Adapter {source_name} detection failed: {e}")
            continue

    logger.warning(f"Could not detect source type for input: {input_source}")
    return None


__all__ = [
    "BaseSourceAdapter",
    "RecruiterCSVAdapter",
    "ATSJSONAdapter",
    "GitHubProfileAdapter",
    "ResumePDFAdapter",
    "ResumeDocxAdapter",
    "RecruiterNotesAdapter",
    "SOURCE_REGISTRY",
    "detect_source",
]
