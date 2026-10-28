import datetime
import math
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("utils")

def format_points(pts: Union[int, float, str, None]) -> str:
    """Rule B9: Integers when whole, one decimal only for half points."""
    if pts is None or pts == "" or pts == "-":
        return "-"
    try:
        val = float(pts)
        if val.is_integer():
            return str(int(val))
        return f"{val:.1f}"
    except (ValueError, TypeError):
        return str(pts)

def format_lap_time(seconds_or_str: Union[float, int, str, None]) -> str:
    """Rule B9: Times as m:ss.mmm (or h:mm:ss.mmm)."""
    if seconds_or_str is None or seconds_or_str == "" or seconds_or_str == "-":
        return "-"
    if isinstance(seconds_or_str, str):
        # If already formatted as 1:24.062 or similar
        if ":" in seconds_or_str:
            return seconds_or_str
        try:
            sec = float(seconds_or_str)
        except ValueError:
            return seconds_or_str
    else:
        sec = float(seconds_or_str)

    if math.isnan(sec) or math.isinf(sec) or sec <= 0:
        return "-"

    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{int(h)}:{int(m):02d}:{s:06.3f}"
    return f"{int(m)}:{s:06.3f}"

def format_gap_display(gap_str_or_sec: Any) -> str:
    """Rule B9: Gaps with a plus sign for positive deltas, e.g. +5.432s or +1 lap."""
    if gap_str_or_sec is None or gap_str_or_sec == "" or gap_str_or_sec == "-":
        return "-"
    s = str(gap_str_or_sec).strip()
    if "lap" in s.lower() or "dnf" in s.lower() or "dsq" in s.lower() or "retired" in s.lower():
        if "lap" in s.lower() and not s.startswith("+"):
            return f"+{s}"
        return s
    if s.startswith("+"):
        if not s.endswith("s") and not any(w in s for w in ["lap", "L"]):
            return f"{s}s"
        return s
    try:
        f = float(s)
        if f == 0.0:
            return "Winner"
        return f"+{f:.3f}s"
    except (ValueError, TypeError):
        return s

def compute_and_validate_gaps(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Rule B8: Compute gap column server-side from total race time in milliseconds
    relative to the winner for lead-lap finishers, and '+N lap(s)' for lapped cars.
    Validates that gaps are non-decreasing with position among lead-lap finishers.
    If check fails, shows the raw API value labelled 'as reported' and logs a warning.
    """
    if not results:
        return results

    # Find winner / P1 lead lap
    winner_row = next((r for r in results if str(r.get("position")) in ["1", "P1"]), results[0] if results else None)
    winner_laps = int(winner_row.get("laps", winner_row.get("total_laps", 0))) if winner_row else 0
    winner_millis = winner_row.get("millis") or winner_row.get("time_millis") or winner_row.get("time_ms") if winner_row else None

    # Track previous gap for monotonic check
    prev_lead_gap_sec = 0.0

    processed_results = []
    for r in results:
        item = dict(r)
        pos = item.get("position")
        status = str(item.get("status", "Finished")).strip()
        laps = int(item.get("laps", 0)) if item.get("laps") is not None else winner_laps
        time_str = item.get("time", "")

        # P1 / Winner
        if str(pos) in ["1", "P1"]:
            item["gap"] = "Winner"
            processed_results.append(item)
            continue

        # If not finished
        if status not in ["Finished", ""] and not status.startswith("+"):
            item["gap"] = status
            processed_results.append(item)
            continue

        # Lapped cars
        if winner_laps > 0 and laps < winner_laps:
            lap_diff = winner_laps - laps
            item["gap"] = f"+{lap_diff} lap{'s' if lap_diff > 1 else ''}"
            processed_results.append(item)
            continue

        # Lead lap finisher
        gap_sec = None
        # Check raw millis
        item_millis = item.get("millis") or item.get("time_millis") or item.get("time_ms")
        if winner_millis and item_millis:
            try:
                gap_sec = (float(item_millis) - float(winner_millis)) / 1000.0
            except (ValueError, TypeError):
                pass

        if gap_sec is None and time_str:
            # Maybe time_str is e.g. "+5.432" or "1:24.062"
            clean_time = time_str.replace("+", "").replace("s", "").strip()
            try:
                gap_sec = float(clean_time)
            except ValueError:
                pass

        if gap_sec is not None:
            # Monotonic validation
            if gap_sec < prev_lead_gap_sec:
                logger.warning(f"Inconsistent gap detected at P{pos}: {gap_sec}s < prev {prev_lead_gap_sec}s. Flagging as reported.")
                item["gap"] = f"{format_gap_display(gap_sec)} (as reported)"
            else:
                prev_lead_gap_sec = gap_sec
                item["gap"] = format_gap_display(gap_sec)
        else:
            item["gap"] = format_gap_display(time_str) if time_str else "-"

        processed_results.append(item)

    return processed_results

def pd_isna(val) -> bool:
    """Safe NaN / NaT / None checker without importing pandas."""
    if val is None:
        return True
    try:
        import math
        if isinstance(val, float) and math.isnan(val):
            return True
    except (TypeError, ValueError):
        pass
    try:
        import pandas as pd
        return pd.isna(val)
    except Exception:
        return False


def format_utc_timestamp(dt: Optional[datetime.datetime] = None) -> str:
    """Rule B12: '27 Oct 2026, 04:24 UTC' formatted standard."""
    if dt is None:
        dt = datetime.datetime.now(datetime.timezone.utc)
    return dt.strftime("%d %b %Y, %H:%M UTC")
