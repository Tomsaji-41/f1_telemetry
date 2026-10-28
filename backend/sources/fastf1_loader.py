"""
backend/sources/fastf1_loader.py
Re-exports thread-safe FastF1 session loader from backend.charts.loader.
"""
from backend.charts.loader import (
    get_session,
    peek,
    load,
    evict,
    warm_latest,
    _key,
    _REG,
    _LOCKS,
    _GUARD,
)

__all__ = [
    "get_session",
    "peek",
    "load",
    "evict",
    "warm_latest",
    "_key",
    "_REG",
    "_LOCKS",
    "_GUARD",
]
