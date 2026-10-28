"""
backend/charts/pit.py
Pit stop data builder — Jolpica primary, FastF1 pit-lane enrichment for 2018+.
Mapped driver metadata, race control message context for suspect stops,
team summaries, and driver aggregates.
"""
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

try:
    from backend import config
    from backend.sources import jolpica as _J
except ImportError:
    import config
    from sources import jolpica as _J

from .common import envelope, parse_lap_str


def _get_team_color(team: str, session=None) -> str:
    try:
        import fastf1.plotting as fp
        c = fp.get_team_color(team, session)
        if c:
            return c
    except Exception:
        pass
    return getattr(config, "NEUTRAL_COLOUR", "#A9A9BC")


def _get_driver_directory(year: int, rnd: int, session=None) -> Dict[str, Dict[str, str]]:
    """Fetch race results to map driverId -> {code, name, team, color}."""
    dir_map: Dict[str, Dict[str, str]] = {}
    try:
        res = _J.fetch_race_results(year, rnd)
        if res.get("status") == "ok":
            for r in res.get("results", []):
                d_id = r.get("driver_id", "").lower()
                code = r.get("code") or (d_id[:3].upper() if d_id else "UNK")
                given = r.get("given_name", "")
                family = r.get("family_name", "")
                name_parts = f"{given} {family}".strip()
                full_name = r.get("driver") or r.get("name") or name_parts or code
                team = r.get("constructor") or r.get("constructor_name") or r.get("team") or "Unknown"
                color = _get_team_color(team, session)
                info = {
                    "code": code.upper(),
                    "name": full_name,
                    "team": team,
                    "color": color,
                }
                dir_map[d_id] = info
                # Also index by code
                dir_map[code.lower()] = info
                dir_map[code.upper()] = info
    except Exception:
        pass
    return dir_map


def _find_race_control_context(session, lap: int) -> Optional[str]:
    """Look up race control messages around a given lap (lap or lap+1)."""
    if session is None:
        return None
    try:
        msgs = getattr(session, "race_control_messages", None)
        if msgs is None or msgs.empty:
            msgs = getattr(session, "messages", None)
        if msgs is not None and not msgs.empty and "Message" in msgs:
            # Check for messages with Lap == lap or lap+1
            matched = []
            for _, row in msgs.iterrows():
                row_lap = row.get("Lap")
                if pd.notna(row_lap) and int(row_lap) in (lap, lap + 1):
                    msg_txt = str(row.get("Message", "")).strip()
                    if msg_txt:
                        matched.append(f"Lap {int(row_lap)}: {msg_txt}")
            if matched:
                return " | ".join(matched[:2])
    except Exception:
        pass
    return None


def pit_stops(
    year: int, rnd: int, session=None
) -> Dict[str, Any]:
    """
    Returns pit stop data meeting V7-3 B spec:
    - Driver 3-letter code, full name, team, team colour mapped from race results.
    - FastF1 PitIn/PitOut pit lane time enrichment.
    - Suspect stops flagged with 'as reported' and attached race control context.
    - Chronological order, driver groups with total time, and team summaries.
    """
    try:
        if year < 2012:
            return envelope(
                "Jolpica",
                "outside_coverage",
                "Pit stop data exists from 2012.",
                stops=[],
                team_summary={},
                driver_summary=[],
            )

        raw = _J.fetch_pit_stops(year, rnd)
        if raw.get("status") != "ok":
            status = "empty" if year >= 2012 else "outside_coverage"
            return envelope(
                "Jolpica",
                status,
                raw.get("coverage_note", ""),
                stops=[],
                team_summary={},
                driver_summary=[],
            )

        driver_dir = _get_driver_directory(year, rnd, session)

        rows: List[Dict[str, Any]] = []
        for p in raw.get("pit_stops", []):
            raw_id = p.get("driver_id", "")
            d_info = driver_dir.get(raw_id.lower()) or {
                "code": raw_id[:3].upper() if raw_id else "UNK",
                "name": raw_id.replace("_", " ").title(),
                "team": "Unknown",
                "color": "#A9A9BC",
            }

            dur = parse_lap_str(p.get("duration"))
            suspect = (
                dur is None
                or dur > config.PIT_MAX_S
                or dur < config.PIT_MIN_S
            )

            lap_num = int(p.get("lap", 0))

            # Context for suspect durations
            context = None
            if suspect and session is not None:
                context = _find_race_control_context(session, lap_num)

            rows.append(
                {
                    "driver_id": raw_id,
                    "code": d_info["code"],
                    "name": d_info["name"],
                    "team": d_info["team"],
                    "color": d_info["color"],
                    "stop": int(p.get("stop", 0)),
                    "lap": lap_num,
                    "duration_s": dur,
                    "suspect": suspect,
                    "suspect_label": "as reported" if suspect else None,
                    "context": context,
                    "pit_lane_s": None,
                    "pit_lane_note": None if (session is not None and year >= 2018) else "n/a (FastF1 not loaded)",
                    "source": "Jolpica",
                }
            )

        # Sort chronologically by lap, then stop
        rows.sort(key=lambda x: (x["lap"], x["stop"]))

        # Enrich with FastF1 pit-lane times when session is available
        if session is not None and year >= 2018:
            try:
                laps = session.laps
                out_laps = laps[laps["PitOutTime"].notna()]
                for r in out_laps.itertuples(index=False):
                    lap_n = int(r.LapNumber)
                    prev = laps[
                        (laps["Driver"] == r.Driver)
                        & (laps["LapNumber"] == lap_n - 1)
                    ]
                    if len(prev) == 0:
                        continue
                    pit_in = prev["PitInTime"].iloc[0]
                    if pd.isna(pit_in):
                        continue
                    try:
                        lane_s = round(
                            (r.PitOutTime - pit_in).total_seconds(), 3
                        )
                    except Exception:
                        continue
                    for x in rows:
                        if (x["code"] == r.Driver or x["driver_id"] == str(r.Driver).lower()) and x["lap"] == lap_n - 1:
                            x["pit_lane_s"] = lane_s
                            x["pit_lane_note"] = None
            except Exception:
                pass

        # Calculate 95th percentile of non-suspect stops for chart scale clipping
        non_suspect_durs = [r["duration_s"] for r in rows if r["duration_s"] is not None and not r["suspect"]]
        p95_dur = float(np.percentile(non_suspect_durs, 95)) if non_suspect_durs else 30.0

        # Group stops per driver with total pit time
        driver_summary_dict: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            code = r["code"]
            if code not in driver_summary_dict:
                driver_summary_dict[code] = {
                    "code": code,
                    "name": r["name"],
                    "team": r["team"],
                    "color": r["color"],
                    "total_stops": 0,
                    "total_pit_time_s": 0.0,
                    "has_suspect_time": False,
                    "stops": [],
                }
            ds = driver_summary_dict[code]
            ds["total_stops"] += 1
            if r["duration_s"] is not None and not r["suspect"]:
                ds["total_pit_time_s"] = round(ds["total_pit_time_s"] + r["duration_s"], 3)
            if r["suspect"]:
                ds["has_suspect_time"] = True
            ds["stops"].append(r)

        driver_summary = list(driver_summary_dict.values())
        driver_summary.sort(key=lambda d: d["total_pit_time_s"] if d["total_pit_time_s"] > 0 else 999.0)

        # Team summary: median and best stop per team (non-suspect only)
        team_stops: Dict[str, List[float]] = {}
        for r in rows:
            if r["duration_s"] is not None and not r["suspect"]:
                team_stops.setdefault(r["team"], []).append(r["duration_s"])

        team_summary: Dict[str, Dict[str, Any]] = {}
        for team, durs in team_stops.items():
            if durs:
                team_summary[team] = {
                    "team": team,
                    "best_stop_s": round(min(durs), 3),
                    "median_stop_s": round(float(np.median(durs)), 3),
                    "count": len(durs),
                    "color": _get_team_color(team, session),
                }

        source_label = "Jolpica, FastF1" if session is not None and year >= 2018 else "Jolpica"
        return envelope(
            source_label,
            "ok" if rows else "empty",
            "" if year >= 2012 else "Pit stop data exists from 2012.",
            stops=rows,
            series=rows,
            driver_summary=driver_summary,
            team_summary=team_summary,
            p95_duration_s=round(p95_dur, 2),
        )
    except Exception as exc:
        return envelope("Jolpica", "source_error", f"pit_stops error: {exc}", stops=[], series=[])
