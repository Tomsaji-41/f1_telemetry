"""
backend/charts/common.py
Shared utilities: envelope builder, time helpers, lap cleaning, track annotations, driver meta.
Assumes FastF1 3.1+. No F1 values are hardcoded here.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

try:
    from backend import config
    from backend.charts.schema import ChartResponse
except ImportError:
    import config
    try:
        from .schema import ChartResponse
    except ImportError:
        from schema import ChartResponse


# ---------------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------------

def envelope(source: str, status: str = "ok", note: str = "", **payload) -> Dict[str, Any]:
    raw = {
        "source": source,
        "status": status,
        "coverage_note": note,
        **payload,
    }
    try:
        return ChartResponse.model_validate(raw).model_dump()
    except Exception:
        norm_status = status
        if norm_status in ("empty", "outside_coverage", "not_ingested"):
            norm_status = "not_available"
        elif norm_status == "preparing":
            norm_status = "loading"
        return {
            "status": norm_status,
            "source": source,
            "coverage_note": note,
            "fetched_at": datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC"),
            **payload,
        }


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def ms(td) -> Optional[int]:
    """timedelta or NaT → integer milliseconds, or None."""
    try:
        if pd.isna(td):
            return None
    except Exception:
        if td is None:
            return None
    try:
        return int(round(td.total_seconds() * 1000))
    except Exception:
        return None


def secs(td) -> Optional[float]:
    """timedelta or NaT → float seconds rounded to 3 dp, or None."""
    try:
        if pd.isna(td):
            return None
    except Exception:
        if td is None:
            return None
    try:
        return round(td.total_seconds(), 3)
    except Exception:
        return None


def parse_lap_str(s: Optional[str]) -> Optional[float]:
    """'1:29.123' or '59.876' → seconds as float, None if empty or invalid."""
    if not s:
        return None
    try:
        m, _, rest = s.rpartition(":")
        return round((int(m) * 60 if m else 0) + float(rest), 3)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Lap cleaning
# ---------------------------------------------------------------------------

def clean_laps(laps: pd.DataFrame, keep_flags: bool = False) -> pd.DataFrame:
    """
    Exclude in-laps, out-laps, deleted laps and null times.
    keep_flags=True keeps SC/VSC laps but tags them with is_sc for toggling.
    """
    l = laps[laps["LapTime"].notna()].copy()
    # Exclude pit in/out laps
    if "PitInTime" in l.columns and "PitOutTime" in l.columns:
        l = l[l["PitInTime"].isna() & l["PitOutTime"].isna()]
    # Exclude deleted laps
    if "Deleted" in l.columns:
        l = l[~l["Deleted"].fillna(False).astype(bool)]
    # Tag safety-car laps (TrackStatus codes 4=SC, 5=RF, 6=VSC deploy, 7=VSC ending)
    if "TrackStatus" in l.columns:
        l["is_sc"] = l["TrackStatus"].fillna("").str.contains("[4567]", regex=True)
    else:
        l["is_sc"] = False
    return l if keep_flags else l[~l["is_sc"]]


# ---------------------------------------------------------------------------
# Run-length encoding helper
# ---------------------------------------------------------------------------

def runs(nums: List[int]) -> List[tuple]:
    """[3,4,5,9,10] → [(3,5),(9,10)]"""
    out: List[tuple] = []
    start = prev = None
    for n in sorted(nums):
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            out.append((start, prev))
            start = prev = n
    if start is not None:
        out.append((start, prev))
    return out


# ---------------------------------------------------------------------------
# Track annotations from FastF1 TrackStatus
# ---------------------------------------------------------------------------

def track_annotations(laps: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Return annotation bands for safety car, red flag, and VSC periods,
    plus individual pit events.
    """
    out: List[Dict[str, Any]] = []
    if "TrackStatus" not in laps.columns or "LapNumber" not in laps.columns:
        return out

    ts = laps["TrackStatus"].fillna("")
    for pat, typ, label in (
        ("4", "sc", "Safety car"),
        ("5", "red", "Red flag"),
        ("[67]", "vsc", "Virtual safety car"),
    ):
        nums = sorted(
            laps.loc[ts.str.contains(pat, regex=True), "LapNumber"]
            .dropna()
            .astype(int)
            .unique()
        )
        out += [
            {"type": typ, "lap_start": a, "lap_end": b, "label": label}
            for a, b in runs(nums)
        ]

    if "PitInTime" in laps.columns and "Driver" in laps.columns:
        pit_laps = laps[laps["PitInTime"].notna()][["Driver", "LapNumber"]]
        for r in pit_laps.itertuples(index=False):
            out.append(
                {
                    "type": "pit",
                    "lap_start": int(r.LapNumber),
                    "lap_end": int(r.LapNumber),
                    "label": r.Driver,
                }
            )

    return out


# ---------------------------------------------------------------------------
# Driver metadata
# ---------------------------------------------------------------------------

def drivers_meta(session, codes: List[str]) -> List[Dict[str, Any]]:
    """
    Build driver meta list from FastF1 session results and plotting.
    Second driver of the same team gets dash=True for dashed lines.
    Falls back to NEUTRAL_COLOUR when FastF1 plotting raises.
    """
    try:
        import fastf1.plotting as fp
        has_plotting = True
    except ImportError:
        has_plotting = False

    try:
        res = session.results.set_index("Abbreviation")
    except Exception:
        res = pd.DataFrame()

    seen: Dict[str, int] = {}
    out = []
    for c in codes:
        team = None
        full_name = c
        colour = None

        if c in res.index:
            try:
                team = str(res.at[c, "TeamName"])
            except Exception:
                pass
            try:
                full_name = str(res.at[c, "FullName"])
            except Exception:
                pass

        if has_plotting:
            try:
                colour = fp.get_driver_color(c, session)
            except Exception:
                colour = None

        out.append(
            {
                "code": c,
                "name": full_name,
                "team": team,
                "colour": colour or config.NEUTRAL_COLOUR,
                "dash": seen.get(team, 0) > 0,
            }
        )
        if team:
            seen[team] = seen.get(team, 0) + 1

    return out
