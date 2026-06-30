"""Base source adapter interface."""

from abc import ABC, abstractmethod
from typing import Union, Optional, Any
import logging

from transformer.models import RawRecord

logger = logging.getLogger(__name__)


class BaseSourceAdapter(ABC):
    """
    Abstract base class for all source adapters.

    Each adapter knows how to detect and extract data from one source type
    (CSV, JSON, API, PDF, text, etc.).
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique identifier for this source type (e.g., 'recruiter_csv', 'github_profile')."""
        pass

    @abstractmethod
    def detect(self, input_source: Union[str, bytes, dict]) -> bool:
        """
        Check if this adapter can handle the given input.

        Args:
            input_source: File path (str), raw bytes, JSON dict, or URI string

        Returns:
            True if this adapter recognizes the input, False otherwise.
        """
        pass

    @abstractmethod
    def extract(self, raw_input: Union[str, bytes, dict]) -> RawRecord:
        """
        Extract raw data from input into a RawRecord.

        Args:
            raw_input: File path, bytes, dict, or string (depending on source type)

        Returns:
            RawRecord with extracted fields and metadata

        Raises:
            May raise exceptions; caller should catch and degrade gracefully.
        """
        pass
