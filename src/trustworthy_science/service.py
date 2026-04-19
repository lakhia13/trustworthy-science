"""Service layer for TruthFilter singleton."""

import logging

from trustworthy_science.api import TruthFilter

logger = logging.getLogger(__name__)

# Global TruthFilter instance
_tf: TruthFilter | None = None


def get_truth_filter() -> TruthFilter:
    """Get or initialize the global TruthFilter instance."""
    global _tf
    if _tf is None:
        logger.info("Initializing TruthFilter from config...")
        _tf = TruthFilter.from_config()
    return _tf


def reload_truth_filter() -> TruthFilter:
    """Reload and reinitialize TruthFilter from config."""
    global _tf
    logger.info("Reloading TruthFilter config...")
    _tf = TruthFilter.from_config()
    return _tf
