"""DETECT stage: identify source type and return adapter."""

import logging
from typing import Union, Optional, Tuple
from transformer.adapters import detect_source, BaseSourceAdapter

logger = logging.getLogger(__name__)


def detect(
    input_source: Union[str, bytes, dict]
) -> Tuple[Optional[BaseSourceAdapter], str]:
    """
    Detect source type and return adapter.

    Args:
        input_source: File path, bytes, dict, or URI

    Returns:
        Tuple of (adapter, source_name) if detected, (None, "unknown") if not
    """
    adapter = detect_source(input_source)

    if adapter:
        return adapter, adapter.source_name

    logger.warning(f"Source type not detected for: {input_source}")
    return None, "unknown"
