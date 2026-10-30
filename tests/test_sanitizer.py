import math
import datetime
import pytest
import numpy as np
import pandas as pd
from backend.sanitizer import sanitize_for_json, sanitize_value

def test_sanitize_scalars():
    assert sanitize_value(float("nan")) is None
    assert sanitize_value(float("inf")) is None
    assert sanitize_value(float("-inf")) is None
    assert sanitize_value(pd.NaT) is None
    assert sanitize_value("NaT") is None

    # Timedeltas
    td = datetime.timedelta(seconds=92, milliseconds=450)
    assert sanitize_value(td) == 92.45
    p_td = pd.Timedelta(seconds=14, milliseconds=200)
    assert sanitize_value(p_td) == 14.2

    # NumPy scalars
    assert isinstance(sanitize_value(np.int64(42)), int)
    assert isinstance(sanitize_value(np.float64(3.14)), float)
    assert isinstance(sanitize_value(np.bool_(True)), bool)

def test_sanitize_nested_structure():
    payload = {
        "status": "ok",
        "nested": [
            {"val": float("nan"), "time": pd.Timedelta(seconds=65)},
            {"val": np.int64(10), "flag": np.bool_(False), "nat": pd.NaT}
        ]
    }
    cleaned = sanitize_for_json(payload)
    assert cleaned["status"] == "ok"
    assert cleaned["nested"][0]["val"] is None
    assert cleaned["nested"][0]["time"] == 65.0
    assert cleaned["nested"][1]["val"] == 10
    assert cleaned["nested"][1]["flag"] is False
    assert cleaned["nested"][1]["nat"] is None

