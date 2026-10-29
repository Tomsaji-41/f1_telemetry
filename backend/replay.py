"""
backend/replay.py
High-performance session replay bundle generator.
Returns full laps matrix per driver with gap to leader, interval,
tyre compound, tyre age, pit events, track status, and real weather.
Client fetches bundle ONCE and scrubs in memory.
"""

import collections
import datetime
import json
import logging
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

try:
    from backend import cache, config, identity, utils
    from backend.charts import loader as chart_loader
    from backend.sources import jolpica, openf1_src
except ImportError:
    import cache, config, identity, utils
    from charts import loader as chart_loader
    from sources import jolpica, openf1_src

logger = logging.getLogger("replay")


def _format_time_delta(td: Any) -> str:
    """Format pd.Timedelta or seconds float into M:SS.mmm or SS.mmm."""
    if td is None or pd.isna(td):
        return "-"
    if hasattr(td, "total_seconds"):
        s = td.total_seconds()
    else:
        try:
            s = float(td)
        except Exception:
            return "-"
    if s <= 0:
        return "-"
    mins = int(s // 60)
    secs = s % 60
    if mins > 0:
        return f"{mins}:{secs:06.3f}"
    return f"{secs:.3f}"


def _sanitize_for_json(obj: Any) -> Any:
    """Recursively replaces NaN and inf with None."""
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    elif isinstance(obj, float):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return obj
    return obj


def get_session_replay_bundle(year: Optional[int] = None, rnd: Optional[int] = None) -> Dict[str, Any]:
    """
    Builds the complete replay bundle for a race session.
    Cached in SQLite with TTL_PAST_SEASON.
    """
    if year is None or rnd is None:
        latest = jolpica.get_latest_completed_session()
        year = latest["year"]
        rnd = latest["round"]

    cache_key = f"replay_bundle_v2_{year}_{rnd}"
    cached_str = cache.get(cache_key)
    if cached_str is not None and isinstance(cached_str, str):
        try:
            cached = json.loads(cached_str)
            if isinstance(cached, dict) and cached.get("status") == "ok":
                return cached
        except Exception:
            pass

    # Fetch session from chart loader
    try:
        sess = chart_loader.get_session(year, rnd, "R")
    except Exception as exc:
        logger.warning("Failed to load session for %s R%s: %s", year, rnd, exc)
        return {
            "status": "not_available",
            "reason": f"Session replay data not available for {year} Round {rnd}: {exc}",
            "source": "SessionLoader",
            "year": year,
            "round": rnd
        }

    laps_df = getattr(sess, "laps", None)
    if laps_df is None or laps_df.empty or "LapNumber" not in laps_df:
        return {
            "status": "not_available",
            "reason": f"No lap timing data recorded for {year} Round {rnd}",
            "source": "SessionLoader",
            "year": year,
            "round": rnd
        }

    # Total laps
    try:
        total_laps = int(laps_df["LapNumber"].max())
    except Exception:
        total_laps = 1

    # Season identity for colors, numbers, codes
    season_id = identity.get_season_identity(year)
    drivers_id_map = season_id.get("drivers", {})
    teams_id_map = season_id.get("teams", {})

    # Race details
    race_info = jolpica.fetch_race_results(year, rnd)
    gp_name = race_info.get("grand_prix") or f"{year} Round {rnd}"
    circuit_name = race_info.get("circuit_name") or "Circuit"

    # Weather: try OpenF1 if 2023-2024, or FastF1 weather_data if present
    weather_by_lap = {}
    if 2023 <= year <= 2024:
        try:
            url_sess = f"https://api.openf1.org/v1/sessions?year={year}&session_name=Race"
            sess_list = cache.cached_get_json(url_sess, cache.TTL_PAST_SEASON)
            if sess_list and isinstance(sess_list, list) and len(sess_list) >= rnd:
                s_key = sess_list[rnd - 1].get("session_key")
                if s_key:
                    url_w = f"https://api.openf1.org/v1/weather?session_key={s_key}"
                    raw_w = cache.cached_get_json(url_w, cache.TTL_PAST_SEASON)
                    if raw_w and isinstance(raw_w, list):
                        step = max(1, len(raw_w) // max(total_laps, 1))
                        for lap_idx in range(1, total_laps + 1):
                            w_idx = min(len(raw_w) - 1, (lap_idx - 1) * step)
                            w_item = raw_w[w_idx]
                            weather_by_lap[lap_idx] = {
                                "air_temp": f"{float(w_item.get('air_temperature', 0.0)):.1f} °C",
                                "track_temp": f"{float(w_item.get('track_temperature', 0.0)):.1f} °C",
                                "humidity": f"{int(float(w_item.get('humidity', 0.0)))}%",
                                "wind_speed": f"{float(w_item.get('wind_speed', 0.0)):.1f} m/s",
                                "rainfall": bool(w_item.get("rainfall", False)),
                            }
        except Exception as exc:
            logger.debug("OpenF1 weather lookup failed: %s", exc)

    # Pit stops from Jolpica
    pit_res = jolpica.fetch_pit_stops(year, rnd)
    pit_events = []
    pit_stops_by_driver_lap = set()
    if pit_res.get("status") == "ok":
        for p in pit_res.get("pit_stops", []):
            d_code = p.get("code") or (p.get("driver_id", "")[:3].upper())
            p_lap = int(p.get("lap", 0)) if str(p.get("lap", "")).isdigit() else 0
            p_stop = int(p.get("stop", 1)) if str(p.get("stop", "")).isdigit() else 1
            p_dur = p.get("duration", "")
            if p_lap > 0 and d_code:
                pit_events.append({
                    "driver": p.get("driver_id", d_code),
                    "code": d_code,
                    "lap": p_lap,
                    "stop": p_stop,
                    "duration": p_dur
                })
                pit_stops_by_driver_lap.add((d_code, p_lap))

    # Compute tyre age and stints per driver
    # Stint count increases on pit stop or when Compound changes
    driver_laps_grouped = laps_df.sort_values(["Driver", "LapNumber"]).groupby("Driver")
    tyre_age_map = {}
    stint_map = {}
    last_lap_time_map = {}
    cum_time_map = {}

    for d_code, group in driver_laps_grouped:
        curr_age = 1
        curr_stint = 1
        prev_compound = None
        for _, row in group.iterrows():
            l_num = int(row["LapNumber"])
            comp = str(row.get("Compound", "MEDIUM")).upper()
            if prev_compound is not None and comp != prev_compound:
                curr_age = 1
                curr_stint += 1
            elif (d_code, l_num) in pit_stops_by_driver_lap or bool(row.get("PitInTime") is not None and pd.notna(row.get("PitInTime"))):
                curr_age = 1
                curr_stint += 1
            else:
                curr_age += 1

            prev_compound = comp
            tyre_age_map[(d_code, l_num)] = curr_age
            stint_map[(d_code, l_num)] = curr_stint
            
            l_time = row.get("LapTime")
            last_lap_time_map[(d_code, l_num)] = _format_time_delta(l_time)
            
            t_val = row.get("Time")
            if hasattr(t_val, "total_seconds"):
                cum_time_map[(d_code, l_num)] = t_val.total_seconds()
            elif isinstance(t_val, (int, float)):
                cum_time_map[(d_code, l_num)] = float(t_val)

    # Build per-lap matrices
    laps_matrix = {}
    chart_positions = collections.defaultdict(list)
    chart_lap_times = collections.defaultdict(list)

    all_driver_codes = sorted(list(laps_df["Driver"].unique()))

    for lap_idx in range(1, total_laps + 1):
        lap_rows = laps_df[laps_df["LapNumber"] == lap_idx]
        
        # Track status resolution
        track_status = "GREEN"
        if not lap_rows.empty and "TrackStatus" in lap_rows:
            ts_vals = lap_rows["TrackStatus"].astype(str).tolist()
            combined_ts = "".join(ts_vals)
            if "5" in combined_ts:
                track_status = "RED"
            elif "4" in combined_ts:
                track_status = "SC"
            elif "6" in combined_ts:
                track_status = "VSC"
            elif "2" in combined_ts:
                track_status = "YELLOW"
        if lap_idx == total_laps:
            track_status = "CHEQUERED"

        # Leaderboard calculation
        leaderboard_rows = []
        if not lap_rows.empty:
            sorted_lap = lap_rows.sort_values("Position") if "Position" in lap_rows else lap_rows
            leader_sec = None
            prev_sec = None

            for _, r in sorted_lap.iterrows():
                code = str(r["Driver"])
                d_id_info = drivers_id_map.get(code, {})
                t_color = d_id_info.get("team_colour") or "#E10600"
                t_name = d_id_info.get("team") or str(r.get("Team", "F1 Team"))
                d_name = d_id_info.get("name") or code

                pos_val = r.get("Position", 99)
                try:
                    pos = int(pos_val) if pd.notna(pos_val) else 99
                except Exception:
                    pos = 99

                c_sec = cum_time_map.get((code, lap_idx))
                if pos == 1 and leader_sec is None and c_sec is not None:
                    leader_sec = c_sec

                if pos == 1:
                    gap_str = "LEADER"
                    interval_str = "-"
                elif leader_sec is not None and c_sec is not None:
                    gap_diff = max(0.0, c_sec - leader_sec)
                    gap_str = f"+{gap_diff:.3f}s"
                    if prev_sec is not None:
                        int_diff = max(0.0, c_sec - prev_sec)
                        interval_str = f"+{int_diff:.3f}s"
                    else:
                        interval_str = gap_str
                else:
                    gap_str = "-"
                    interval_str = "-"

                if c_sec is not None:
                    prev_sec = c_sec

                comp = str(r.get("Compound", "MEDIUM")).upper()
                tyre_age = tyre_age_map.get((code, lap_idx), 1)
                last_lap = last_lap_time_map.get((code, lap_idx), "-")
                is_pit = (code, lap_idx) in pit_stops_by_driver_lap

                leaderboard_rows.append({
                    "pos": pos,
                    "code": code,
                    "driver": d_name,
                    "team": t_name,
                    "team_color": t_color,
                    "gap": gap_str,
                    "interval": interval_str,
                    "compound": comp,
                    "tyre_life": tyre_age,
                    "last_lap": last_lap,
                    "is_pit": is_pit
                })

                chart_positions[code].append(pos)
                raw_lt = r.get("LapTime")
                lt_sec = raw_lt.total_seconds() if hasattr(raw_lt, "total_seconds") else None
                if lt_sec is not None:
                    try:
                        if pd.isna(lt_sec) or not np.isfinite(float(lt_sec)):
                            lt_sec = None
                        else:
                            lt_sec = round(float(lt_sec), 3)
                    except Exception:
                        lt_sec = None
                chart_lap_times[code].append(lt_sec)

        laps_matrix[lap_idx] = {
            "lap": lap_idx,
            "track_status": track_status,
            "weather": weather_by_lap.get(lap_idx),
            "leaderboard": leaderboard_rows
        }

    # Summary drivers dictionary
    drivers_meta = {}
    for code in all_driver_codes:
        d_info = drivers_id_map.get(code, {})
        drivers_meta[code] = {
            "code": code,
            "name": d_info.get("name") or code,
            "team": d_info.get("team") or "F1 Team",
            "team_color": d_info.get("team_colour") or "#E10600",
            "number": d_info.get("permanentNumber") or "",
            "dash": d_info.get("dash", "")
        }

    bundle = {
        "status": "ok",
        "source": getattr(sess, "source", "FastF1 & Jolpica"),
        "year": year,
        "round": rnd,
        "grand_prix": gp_name,
        "circuit_name": circuit_name,
        "total_laps": total_laps,
        "drivers": drivers_meta,
        "pit_events": pit_events,
        "laps": laps_matrix,
        "chart_data": {
            "laps": list(range(1, total_laps + 1)),
            "positions": dict(chart_positions),
            "lap_times": dict(chart_lap_times)
        }
    }

    bundle = _sanitize_for_json(bundle)

    try:
        cache.set(cache_key, json.dumps(bundle), cache.TTL_PAST_SEASON)
    except Exception as exc:
        logger.warning("Failed to cache replay bundle: %s", exc)
    return bundle
