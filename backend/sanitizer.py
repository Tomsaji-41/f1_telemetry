"""
backend/sanitizer.py — Data Shape & JSON Sanitizer (C-6)

Recursively sanitizes data structures for clean JSON serialization:
- NaN / Inf / -Inf -> None
- pd.NaT / NaT strings -> None
- Timedelta (pd.Timedelta, datetime.timedelta) -> seconds as float
- NumPy scalars (int64, float64, bool_) -> Python native types
"""
import math
import datetime
from typing import Any

try:
    import numpy as np
except ImportError:
    np = None

try:
    import pandas as pd
except ImportError:
    pd = None

def sanitize_value(val: Any) -> Any:
    """Sanitize a single scalar value."""
    if val is None:
        return None

    # Handle Pandas NaT
    if pd is not None and val is pd.NaT:
        return None
    if str(val) in ("NaT", "<NA>", "nan"):
        return None

    # Handle Timedelta
    if isinstance(val, datetime.timedelta):
        return round(val.total_seconds(), 4)
    if pd is not None and isinstance(val, getattr(pd, "Timedelta", type(None))):
        return round(val.total_seconds(), 4)

    # Handle Floats & Infs
    if isinstance(val, (float, getattr(np, "floating", float) if np else float)):
        if math.isnan(val) or math.isinf(val):
            return None
        return float(val)

    # Handle NumPy Integers & Booleans
    if np is not None:
        if isinstance(val, np.integer):
            return int(val)
        if isinstance(val, np.bool_):
            return bool(val)

    return val

def sanitize_for_json(obj: Any) -> Any:
    """Recursively sanitize dictionaries, lists, and scalars."""
    if isinstance(obj, dict):
        return {str(k): sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple, set)):
        return [sanitize_for_json(item) for item in obj]
    else:
        return sanitize_value(obj)

