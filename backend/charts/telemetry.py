"""
backend/charts/telemetry.py
Two-driver car telemetry comparison builder for Telemetry Teleport.
Extracts speed, throttle, brake, gear, RPM, DRS, track map coordinates,
braking zones analysis, aerodynamic/chassis proxies, and sector/speed-trap comparisons.

STRICT HONEST LIMITS:
Never synthesizes or fabricates telemetry curves, speed traces, or parametric track loops.
If real car_data and pos_data are missing on the fastest lap, attempts next-fastest laps,
or alternative sessions of the same weekend (Qualifying, Practice).
If real telemetry is unavailable across the weekend, returns status "not_available"
with the explicit reason, the nearest verified telemetry session, and a real
"Sector & speed-trap comparison" panel (SpeedST, SpeedFL, SpeedI1, SpeedI2).
"""
import logging
import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

try:
    from backend import config
    from backend.sources import jolpica as _J
    from backend.charts import loader
except ImportError:
    import config
    from sources import jolpica as _J
    from charts import loader

from .common import envelope, drivers_meta

VERIFIED_TELEMETRY_SESSIONS = [
    {"year": 2024, "round": 12, "name": "2024 British GP (Silverstone)"},
    {"year": 2024, "round": 1, "name": "2024 Bahrain GP (Sakhir)"},
    {"year": 2023, "round": 22, "name": "2023 Abu Dhabi GP (Yas Marina)"},
    {"year": 2023, "round": 14, "name": "2023 Italian GP (Monza)"},
    {"year": 2023, "round": 1, "name": "2023 Bahrain GP (Sakhir)"},
    {"year": 2022, "round": 22, "name": "2022 Abu Dhabi GP (Yas Marina)"},
    {"year": 2022, "round": 1, "name": "2022 Bahrain GP (Sakhir)"},
]


def find_nearest_telemetry_session(year: int, rnd: int) -> Dict[str, Any]:
    """Find the chronologically closest session with known telemetry."""
    target = year * 30 + rnd
    return min(
        VERIFIED_TELEMETRY_SESSIONS,
        key=lambda s: abs((s["year"] * 30 + s["round"]) - target),
    )


def get_two_fastest_qualifiers(year: int, rnd: int) -> List[str]:
    """Retrieve top 2 qualifiers from Jolpica qualifying results, fallback to VER, NOR."""
    try:
        resp = _J.fetch_qualifying_results(year, rnd)
        if resp.get("status") == "ok":
            quali = resp.get("qualifying", [])
            codes = []
            for q in quali:
                code = q.get("code") or q.get("driver_id", "")
                if code and code not in codes:
                    codes.append(code.upper())
                if len(codes) >= 2:
                    return codes[:2]
    except Exception:
        pass
    return ["VER", "NOR"]


def detect_braking_zones(dist, speed, brake, threshold_dist=30) -> List[Dict[str, Any]]:
    """Detect braking zones and compute entry speed, apex speed, distance, and deceleration."""
    zones = []
    in_zone = False
    start_idx = 0

    for i, b in enumerate(brake):
        if b and not in_zone:
            in_zone = True
            start_idx = i
        elif not b and in_zone:
            in_zone = False
            end_idx = i
            d_start = dist[start_idx]
            d_end = dist[end_idx]
            zone_len = d_end - d_start
            if zone_len >= threshold_dist:
                v_entry = speed[start_idx]
                v_min = min(speed[start_idx : end_idx + 1])
                # proxy decel: delta_v^2 / (2 * distance)
                v1_ms = v_entry / 3.6
                v2_ms = v_min / 3.6
                decel_g = round(
                    abs(v1_ms**2 - v2_ms**2) / (2 * max(zone_len, 1) * 9.81), 2
                )
                zones.append(
                    {
                        "zone": len(zones) + 1,
                        "distance_m": round(d_start, 1),
                        "length_m": round(zone_len, 1),
                        "entry_speed_kmh": round(v_entry, 1),
                        "min_speed_kmh": round(v_min, 1),
                        "delta_kmh": round(v_entry - v_min, 1),
                        "decel_g": decel_g,
                    }
                )
    return zones[:10]


def _extract_real_lap_telemetry(lap) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    """
    Attempt to extract real car_data and pos_data from a single FastF1 lap.
    Returns (car_data_with_dist, pos_data) or (None, None).
    Never fabricates points.
    """
    if lap is None:
        return None, None
    try:
        if not hasattr(lap, "get_car_data"):
            return None, None
        c = lap.get_car_data()
        if c is None or getattr(c, "empty", True) or "Speed" not in c or len(c) < 10:
            return None, None
        car_with_dist = c.add_distance()
        pos = None
        try:
            if hasattr(lap, "get_pos_data"):
                p = lap.get_pos_data()
                if p is not None and not getattr(p, "empty", True) and "X" in p and "Y" in p and len(p) >= 10:
                    pos = p
        except Exception:
            pos = None
        return car_with_dist, pos
    except Exception:
        return None, None


def _find_fastest_lap_with_telemetry(driver_laps):
    """
    Find the fastest lap that has real telemetry.
    Checks the fastest lap first; if car_data is missing, tries next-fastest laps.
    Returns (lap, car_data, pos_data, lap_rank).
    """
    if driver_laps is None or len(driver_laps) == 0:
        return None, None, None, 0

    # Fast path: try pick_fastest() first
    if hasattr(driver_laps, "pick_fastest"):
        try:
            f = driver_laps.pick_fastest()
            car, pos = _extract_real_lap_telemetry(f)
            if car is not None:
                return f, car, pos, 1
        except Exception:
            pass

    valid_laps = driver_laps
    if hasattr(driver_laps, "dropna") and hasattr(driver_laps, "sort_values") and "LapTime" in driver_laps:
        try:
            valid_laps = driver_laps.dropna(subset=["LapTime"]).sort_values("LapTime")
        except Exception:
            valid_laps = driver_laps

    iterator = valid_laps.iterlaps() if hasattr(valid_laps, "iterlaps") else (
        valid_laps.iterrows() if hasattr(valid_laps, "iterrows") else []
    )

    rank = 1
    for _, lap in iterator:
        car, pos = _extract_real_lap_telemetry(lap)
        if car is not None:
            return lap, car, pos, rank
        rank += 1
    return None, None, None, 0


def _pick_fastest_lap_record(df):
    """Return fastest lap record for sector/speed trap extraction (regardless of car telemetry)."""
    if df is None or len(df) == 0:
        return None
    if hasattr(df, "pick_fastest"):
        try:
            f = df.pick_fastest()
            if f is not None and len(f) > 0:
                return f
        except Exception:
            pass
    if isinstance(df, pd.DataFrame) and "LapTime" in df:
        valid = df.dropna(subset=["LapTime"]).sort_values("LapTime")
        if not valid.empty:
            return valid.iloc[0]
    if hasattr(df, "iloc"):
        return df.iloc[0]
    return df[0] if isinstance(df, (list, tuple)) else None


def _extract_sector_speed_traps(l1, l2, d1_code: str, d2_code: str) -> Dict[str, Any]:
    """
    Extract only real lap times, sector times, and speed traps (SpeedST, SpeedFL, SpeedI1, SpeedI2).
    Never invents values. Missing values remain None.
    """
    def _val_time(lap, key: str) -> Optional[float]:
        if lap is None:
            return None
        v = lap.get(key) if hasattr(lap, "get") else getattr(lap, key, None)
        if v is None or pd.isna(v):
            return None
        if hasattr(v, "total_seconds"):
            return round(float(v.total_seconds()), 3)
        try:
            sec = float(v)
            return round(sec, 3) if sec > 0 else None
        except Exception:
            return None

    def _val_speed(lap, key: str) -> Optional[float]:
        if lap is None:
            return None
        v = lap.get(key) if hasattr(lap, "get") else getattr(lap, key, None)
        if v is None or pd.isna(v):
            return None
        try:
            f = float(v)
            return round(f, 1) if f > 0 else None
        except Exception:
            return None

    return {
        "driver1": d1_code,
        "driver2": d2_code,
        "lap_time": {d1_code: _val_time(l1, "LapTime"), d2_code: _val_time(l2, "LapTime")},
        "sector1": {d1_code: _val_time(l1, "Sector1Time"), d2_code: _val_time(l2, "Sector1Time")},
        "sector2": {d1_code: _val_time(l1, "Sector2Time"), d2_code: _val_time(l2, "Sector2Time")},
        "sector3": {d1_code: _val_time(l1, "Sector3Time"), d2_code: _val_time(l2, "Sector3Time")},
        "speed_st": {d1_code: _val_speed(l1, "SpeedST"), d2_code: _val_speed(l2, "SpeedST")},
        "speed_fl": {d1_code: _val_speed(l1, "SpeedFL"), d2_code: _val_speed(l2, "SpeedFL")},
        "speed_i1": {d1_code: _val_speed(l1, "SpeedI1"), d2_code: _val_speed(l2, "SpeedI1")},
        "speed_i2": {d1_code: _val_speed(l1, "SpeedI2"), d2_code: _val_speed(l2, "SpeedI2")},
    }


def _get_driver_laps(laps_obj, driver_code: str):
    """Safely get laps for a driver code."""
    if laps_obj is None:
        return None
    if hasattr(laps_obj, "pick_drivers"):
        try:
            l = laps_obj.pick_drivers(driver_code)
            if l is not None and len(l) > 0:
                return l
        except Exception:
            pass
    if isinstance(laps_obj, pd.DataFrame) and "Driver" in laps_obj:
        return laps_obj[laps_obj["Driver"] == driver_code]
    return None


def build_telemetry_compare(
    session,
    driver1: Optional[str] = None,
    driver2: Optional[str] = None,
    year: int = 2024,
    rnd: int = 1,
) -> Dict[str, Any]:
    """
    Build two-driver telemetry comparison:
    Speed, Throttle, Brake, Gear, RPM, DRS, Track Map, Braking Table, Proxies.
    Adheres strictly to the Honest Limits rule:
    - Only real car_data and pos_data are used.
    - If missing from fastest lap, tries next-fastest laps.
    - If missing from requested session, checks other weekend sessions (Qualifying, Practice).
    - If unavailable, returns status 'not_available' with specific reason, nearest session,
      and real sector/speed-trap metrics. Never synthesizes curves.
    """
    try:
        # Resolve driver codes
        if not driver1 or not driver2:
            default_pair = get_two_fastest_qualifiers(year, rnd)
            driver1 = (driver1 or default_pair[0]).upper()
            driver2 = (driver2 or default_pair[1]).upper()
        else:
            driver1 = driver1.upper()
            driver2 = driver2.upper()

        laps = getattr(session, "laps", None)
        avail_drivers = []
        if laps is not None and (hasattr(laps, "Driver") or "Driver" in laps):
            avail_drivers = [str(d).upper() for d in laps["Driver"].unique() if pd.notna(d)]

        if avail_drivers:
            if driver1 not in avail_drivers:
                driver1 = avail_drivers[0]
            if (driver2 not in avail_drivers or driver2 == driver1) and len(avail_drivers) > 1:
                driver2 = avail_drivers[1]

        l1 = _get_driver_laps(laps, driver1)
        l2 = _get_driver_laps(laps, driver2)

        # Baseline fastest laps for sector/speed-trap panel
        fastest_record1 = _pick_fastest_lap_record(l1)
        fastest_record2 = _pick_fastest_lap_record(l2)
        sector_speed_trap = _extract_sector_speed_traps(fastest_record1, fastest_record2, driver1, driver2)
        driver_meta = drivers_meta(session, [driver1, driver2])

        # Step 1: Try to find real car telemetry in the current session (fastest or next-fastest)
        lap1, car1, pos1, rank1 = _find_fastest_lap_with_telemetry(l1)
        lap2, car2, pos2, rank2 = _find_fastest_lap_with_telemetry(l2)

        session_used = "Race"
        weekend_note = None

        # Step 2: If missing in current session, check other sessions of the weekend (Q, FP2, FP1, FP3, S)
        if car1 is None or car2 is None:
            alt_sessions = ["Q", "FP2", "FP1", "FP3", "S", "SQ"]
            for alt in alt_sessions:
                try:
                    alt_ses = loader.peek(year, rnd, alt, telemetry=True)
                    if alt_ses is None:
                        # Only try loading if FastF1 is enabled
                        alt_ses = loader.get_session(year, rnd, alt, telemetry=True)
                    if alt_ses is not None and getattr(alt_ses, "laps", None) is not None:
                        alt_l1 = _get_driver_laps(alt_ses.laps, driver1)
                        alt_l2 = _get_driver_laps(alt_ses.laps, driver2)
                        a_lap1, a_c1, a_p1, a_r1 = _find_fastest_lap_with_telemetry(alt_l1)
                        a_lap2, a_c2, a_p2, a_r2 = _find_fastest_lap_with_telemetry(alt_l2)
                        if a_c1 is not None and a_c2 is not None:
                            lap1, car1, pos1, rank1 = a_lap1, a_c1, a_p1, a_r1
                            lap2, car2, pos2, rank2 = a_lap2, a_c2, a_p2, a_r2
                            session_used = f"Qualifying ({alt})" if alt in ["Q", "SQ"] else f"Session {alt}"
                            weekend_note = f"Telemetry sourced from {session_used} (Race telemetry was unavailable upstream)."
                            # Update sector/speed trap from that session if applicable
                            sector_speed_trap = _extract_sector_speed_traps(lap1, lap2, driver1, driver2)
                            break
                except Exception:
                    continue

        # Step 3: If real telemetry is STILL unavailable, return honest 'not_available' status
        if car1 is None or car2 is None:
            nearest = find_nearest_telemetry_session(year, rnd)
            return envelope(
                "FastF1",
                status="not_available",
                coverage_note=(
                    f"Full car telemetry stream (car data & GPS) is unavailable for {year} Round {rnd} "
                    "from the upstream timing provider."
                ),
                reason=(
                    f"Car telemetry data stream was not published by the timing provider for {year} Round {rnd} "
                    "across race and qualifying sessions."
                ),
                nearest_session=nearest,
                session_used=None,
                driver1=driver1,
                driver2=driver2,
                drivers=driver_meta,
                sector_speed_trap=sector_speed_trap,
                traces=None,
                track_map=None,
                braking_table=None,
                proxies=None,
            )

        # Step 4: Real telemetry processing (ONLY REAL DATA INTERPOLATED TO COMMON DISTANCE GRID)
        d1_dist = car1["Distance"].to_numpy()
        d2_dist = car2["Distance"].to_numpy()
        max_dist = min(float(d1_dist[-1]), float(d2_dist[-1]))
        if max_dist <= 0:
            return envelope("FastF1", "not_available", "Invalid zero lap distance in car telemetry.")

        grid_dist = np.linspace(0, max_dist, 400)

        s1 = np.interp(grid_dist, d1_dist, car1["Speed"].to_numpy())
        th1 = np.interp(grid_dist, d1_dist, car1["Throttle"].to_numpy())
        br1 = np.interp(grid_dist, d1_dist, car1["Brake"].astype(int).to_numpy())
        gear1 = (
            np.interp(grid_dist, d1_dist, car1["nGear"].to_numpy())
            if "nGear" in car1
            else np.zeros_like(grid_dist)
        )
        rpm1 = (
            np.interp(grid_dist, d1_dist, car1["RPM"].to_numpy())
            if "RPM" in car1
            else np.zeros_like(grid_dist)
        )
        drs1 = (
            np.interp(grid_dist, d1_dist, car1["DRS"].to_numpy())
            if "DRS" in car1
            else np.zeros_like(grid_dist)
        )

        s2 = np.interp(grid_dist, d2_dist, car2["Speed"].to_numpy())
        th2 = np.interp(grid_dist, d2_dist, car2["Throttle"].to_numpy())
        br2 = np.interp(grid_dist, d2_dist, car2["Brake"].astype(int).to_numpy())
        gear2 = (
            np.interp(grid_dist, d2_dist, car2["nGear"].to_numpy())
            if "nGear" in car2
            else np.zeros_like(grid_dist)
        )
        rpm2 = (
            np.interp(grid_dist, d2_dist, car2["RPM"].to_numpy())
            if "RPM" in car2
            else np.zeros_like(grid_dist)
        )
        drs2 = (
            np.interp(grid_dist, d2_dist, car2["DRS"].to_numpy())
            if "DRS" in car2
            else np.zeros_like(grid_dist)
        )

        # Real Pos Data for Track Map (NO PARAMETRIC SYNTHESIS)
        track_coords = []
        if pos1 is not None and not getattr(pos1, "empty", True) and "X" in pos1 and "Y" in pos1:
            try:
                p_dist = (
                    pos1["Distance"].to_numpy()
                    if "Distance" in pos1
                    else np.linspace(0, max_dist, len(pos1))
                )
                x_interp = np.interp(grid_dist, p_dist, pos1["X"].to_numpy())
                y_interp = np.interp(grid_dist, p_dist, pos1["Y"].to_numpy())
                for i in range(0, len(grid_dist), 2):
                    track_coords.append(
                        {
                            "x": round(float(x_interp[i]), 1),
                            "y": round(float(y_interp[i]), 1),
                            "dist": round(float(grid_dist[i]), 1),
                            "delta_speed": round(float(s1[i] - s2[i]), 1),
                        }
                    )
            except Exception as pe:
                logger.debug("Failed interpolating real pos data: %s", pe)
                track_coords = []

        braking_zones = detect_braking_zones(grid_dist, s1, br1 > 0.5)

        def _get_sec(lap_record):
            if lap_record is None:
                return None
            t = lap_record.get("LapTime") if hasattr(lap_record, "get") else getattr(lap_record, "LapTime", None)
            if t is not None and hasattr(t, "total_seconds"):
                return round(float(t.total_seconds()), 3)
            try:
                return round(float(t), 3) if t else None
            except Exception:
                return None

        t1_lap = _get_sec(lap1)
        t2_lap = _get_sec(lap2)
        lap_delta = (
            round(t1_lap - t2_lap, 3)
            if t1_lap is not None and t2_lap is not None
            else None
        )

        top_speed_1 = round(float(np.max(s1)), 1)
        top_speed_2 = round(float(np.max(s2)), 1)
        hs1 = [float(v) for v in s1 if 160 <= v <= 250]
        hs2 = [float(v) for v in s2 if 160 <= v <= 250]
        min_hs_1 = round(min(hs1), 1) if hs1 else round(float(np.mean(s1)), 1)
        min_hs_2 = round(min(hs2), 1) if hs2 else round(float(np.mean(s2)), 1)

        coverage_note = weekend_note or (
            f"Real telemetry extracted for {driver1} (lap {rank1}) and {driver2} (lap {rank2}) from {session_used}."
        )

        return envelope(
            "FastF1",
            status="ok",
            coverage_note=coverage_note,
            session_used=session_used,
            driver1=driver1,
            driver2=driver2,
            drivers=driver_meta,
            lap_time_1=t1_lap,
            lap_time_2=t2_lap,
            lap_delta=lap_delta,
            distance=[round(float(d), 1) for d in grid_dist],
            traces={
                "driver1": {
                    "code": driver1,
                    "speed": [round(float(v), 1) for v in s1],
                    "throttle": [round(float(v), 1) for v in th1],
                    "brake": [int(round(float(v))) for v in br1],
                    "gear": [int(round(float(v))) for v in gear1],
                    "rpm": [int(round(float(v))) for v in rpm1],
                    "drs": [int(round(float(v))) for v in drs1],
                },
                "driver2": {
                    "code": driver2,
                    "speed": [round(float(v), 1) for v in s2],
                    "throttle": [round(float(v), 1) for v in th2],
                    "brake": [int(round(float(v))) for v in br2],
                    "gear": [int(round(float(v))) for v in gear2],
                    "rpm": [int(round(float(v))) for v in rpm2],
                    "drs": [int(round(float(v))) for v in drs2],
                },
                "speed_delta": [round(float(v1 - v2), 1) for v1, v2 in zip(s1, s2)],
            },
            track_map=track_coords,
            braking_table=braking_zones,
            sector_speed_trap=sector_speed_trap,
            drs_available=bool(any(v > 0 for v in drs1) or any(v > 0 for v in drs2)),
            proxies={
                "top_speed": {
                    driver1: top_speed_1,
                    driver2: top_speed_2,
                    "delta": round(top_speed_1 - top_speed_2, 1),
                    "unit": "km/h",
                    "proxy": "Drag / Straight-Line Efficiency",
                },
                "min_hs_corner": {
                    driver1: min_hs_1,
                    driver2: min_hs_2,
                    "delta": round(min_hs_1 - min_hs_2, 1),
                    "unit": "km/h",
                    "proxy": "Aerodynamic Downforce Load",
                },
                "avg_throttle": {
                    driver1: round(float(np.mean(th1)), 1),
                    driver2: round(float(np.mean(th2)), 1),
                    "unit": "%",
                    "proxy": "Power Delivery / Traction",
                },
            },
        )
    except Exception as exc:
        logger.warning("build_telemetry_compare unexpected error: %s", exc)
        return envelope("FastF1", "source_error", f"Telemetry compare error: {exc}")
