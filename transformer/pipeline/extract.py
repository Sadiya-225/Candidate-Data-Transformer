"""EXTRACT stage: orchestrate extraction from multiple sources."""

import logging
from typing import Union, List
from transformer.models import RawRecord
from transformer.pipeline.detect import detect

logger = logging.getLogger(__name__)


def extract(sources: List[Union[str, bytes, dict]]) -> List[RawRecord]:
    """
    Extract raw data from all sources.

    Args:
        sources: List of file paths, bytes, dicts, or URIs

    Returns:
        List of RawRecord objects (one per source)

    Notes:
        - Never crashes on a single bad source
        - Logs errors and continues
        - Sources with errors have parse_error field set
    """
    raw_records = []

    for source_input in sources:
        try:
            adapter, source_name = detect(source_input)

            if adapter is None:
                logger.warning(f"Skipping unrecognized source: {source_input}")
                # Create a minimal RawRecord documenting the skip
                raw_records.append(
                    RawRecord(
                        source_name="unknown",
                        source_method="detection_failed",
                        extracted_fields={},
                        parse_error="Source type not recognized",
                    )
                )
                continue

            # Extract
            raw_record = adapter.extract(source_input)
            raw_records.append(raw_record)
            logger.info(f"Extracted from {source_name}: {source_input}")

        except Exception as e:
            logger.error(f"Failed to extract from source {source_input}: {e}")
            raw_records.append(
                RawRecord(
                    source_name="error",
                    source_method="extraction_exception",
                    extracted_fields={},
                    parse_error=str(e),
                )
            )

    return raw_records
