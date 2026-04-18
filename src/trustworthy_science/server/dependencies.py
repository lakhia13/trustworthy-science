from __future__ import annotations
import threading
from trustworthy_science.api import TruthFilter

_truth_filter: TruthFilter | None = None
_reload_lock = threading.Lock()

def get_truth_filter() -> TruthFilter:
    if _truth_filter is None:
        raise RuntimeError("TruthFilter not initialized. Server lifespan may not have run.")
    return _truth_filter

def init_truth_filter(config_path: str) -> None:
    global _truth_filter
    _truth_filter = TruthFilter.from_config(config_path)

def reload_truth_filter(config_path: str) -> None:
    """Rebuild the TruthFilter graph from a (possibly updated) config file.
    Protected by a lock so concurrent reloads don't race.
    In-flight requests hold their own graph reference on the call stack and
    are unaffected; only new requests after the lock releases use the new graph.
    """
    global _truth_filter
    with _reload_lock:
        if _truth_filter is None:
            init_truth_filter(config_path)
        else:
            _truth_filter.reload_config(config_path)
