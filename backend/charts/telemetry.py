"""
backend/charts/telemetry.py
Two-driver car telemetry comparison builder for Telemetry Teleport.
Extracts speed, throttle, brake, gear, RPM, DRS, track map coordinates,
braking zones analysis, and aerodynamic/chassis proxies.
"""
import math
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

try:
    from backend import config
    from backend.sources import jolpica as _J
except ImportError:
    import config
    from sources import jolpica as _J

from .common import envelope, drivers_meta


def _downsample_series(arr, target_len=350):
    """Downsample a numeric list or array to target_len points for smooth 60fps rendering."""
    if arr is None or len(arr) == 0:
        return []
    if len(arr) <= target_len:
        return [round(float(v), 2) if isinstance(v, (int, float, np.number)) else v for v in arr]
    indices = np.linspace(0, len(arr) - 1, target_len).astype(int)
    return [round(float(arr[i]), 2) if isinstance(arr[i], (int, float, np.number)) else arr[i] for i in indices]


def get_two_fastest_qualifiers(year: int, rnd: int) -> List[str]:
    """Retrieve the top 2 qualifiers from Jolpica qualifying results, fallback to VER, HAM."""
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


def detect_braking_zones(dist, speed, brake, threshold_dist=30):
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
                v_min = min(speed[start_idx:end_idx + 1])
                # proxy decel: delta_v^2 / (2 * distance)
                v1_ms = v_entry / 3.6
                v2_ms = v_min / 3.6
                decel_g = round(abs(v1_ms**2 - v2_ms**2) / (2 * max(zone_len, 1) * 9.81), 2)
                zones.append({
                    "zone": len(zones) + 1,
                    "distance_m": round(d_start, 1),
                    "length_m": round(zone_len, 1),
                    "entry_speed_kmh": round(v_entry, 1),
                    "min_speed_kmh": round(v_min, 1),
                    "delta_kmh": round(v_entry - v_min, 1),
                    "decel_g": decel_g
                })
    return zones[:10]  # Top braking zones


def build_telemetry_compare(
    session,
    driver1: Optional[str] = None,
    driver2: Optional[str] = None,
    year: int = 2024,
    rnd: int = 1
) -> Dict[str, Any]:
    """
    Build two-driver telemetry comparison:
    Speed, Throttle, Brake, Gear, RPM, DRS, Track Map, Braking Table, Proxies.
    """
    try:
        # Determine drivers
        if not driver1 or not driver2:
            default_pair = get_two_fastest_qualifiers(year, rnd)
            driver1 = driver1 or default_pair[0]
            driver2 = driver2 or default_pair[1]

        laps = session.laps
        if laps is None or laps.empty:
            return envelope("FastF1", "empty", "No lap data available for telemetry.")

        l1 = laps.pick_driver(driver1)
        l2 = laps.pick_driver(driver2)

        if l1.empty or l2.empty:
            # Fallback to available drivers
            avail = list(laps["Driver"].unique())
            if len(avail) >= 2:
                driver1 = avail[0]
                driver2 = avail[1]
                l1 = laps.pick_driver(driver1)
                l2 = laps.pick_driver(driver2)
            else:
                return envelope("FastF1", "empty", f"Driver {driver1} or {driver2} has no laps.")

        fastest1 = l1.pick_fastest()
        fastest2 = l2.pick_fastest()

        if fastest1 is None or fastest2 is None:
            return envelope("FastF1", "empty", "Could not find fastest lap for telemetry compare.")

        car1 = fastest1.get_car_data().add_distance()
        car2 = fastest2.get_car_data().add_distance()

        d1_dist = car1["Distance"].to_numpy()
        d2_dist = car2["Distance"].to_numpy()
        max_dist = min(float(d1_dist[-1]), float(d2_dist[-1]))

        # Common distance grid (400 points)
        grid_dist = np.linspace(0, max_dist, 400)

        # Interpolate car 1
        s1 = np.interp(grid_dist, d1_dist, car1["Speed"].to_numpy())
        th1 = np.interp(grid_dist, d1_dist, car1["Throttle"].to_numpy())
        br1 = np.interp(grid_dist, d1_dist, car1["Brake"].astype(int).to_numpy())
        gear1 = np.interp(grid_dist, d1_dist, car1["nGear"].to_numpy()) if "nGear" in car1 else np.zeros_like(grid_dist)
        rpm1 = np.interp(grid_dist, d1_dist, car1["RPM"].to_numpy()) if "RPM" in car1 else np.zeros_like(grid_dist)
        drs1 = np.interp(grid_dist, d1_dist, car1["DRS"].to_numpy()) if "DRS" in car1 else np.zeros_like(grid_dist)

        # Interpolate car 2
        s2 = np.interp(grid_dist, d2_dist, car2["Speed"].to_numpy())
        th2 = np.interp(grid_dist, d2_dist, car2["Throttle"].to_numpy())
        br2 = np.interp(grid_dist, d2_dist, car2["Brake"].astype(int).to_numpy())
        gear2 = np.interp(grid_dist, d2_dist, car2["nGear"].to_numpy()) if "nGear" in car2 else np.zeros_like(grid_dist)
        rpm2 = np.interp(grid_dist, d2_dist, car2["RPM"].to_numpy()) if "RPM" in car2 else np.zeros_like(grid_dist)
        drs2 = np.interp(grid_dist, d2_dist, car2["DRS"].to_numpy()) if "DRS" in car2 else np.zeros_like(grid_dist)

        # Track coordinates from pos data if available
        track_coords = []
        try:
            pos1 = fastest1.get_pos_data()
            if pos1 is not None and not pos1.empty and "X" in pos1 and "Y" in pos1:
                p_dist = pos1["Distance"].to_numpy() if "Distance" in pos1 else np.linspace(0, max_dist, len(pos1))
                x_interp = np.interp(grid_dist, p_dist, pos1["X"].to_numpy())
                y_interp = np.interp(grid_dist, p_dist, pos1["Y"].to_numpy())
                for i in range(0, len(grid_dist), 2):  # 200 points for track map
                    track_coords.append({
                        "x": round(float(x_interp[i]), 1),
                        "y": round(float(y_interp[i]), 1),
                        "dist": round(float(grid_dist[i]), 1),
                        "delta_speed": round(float(s1[i] - s2[i]), 1)
                    })
        except Exception:
            pass

        # Braking zones
        braking_zones = detect_braking_zones(grid_dist, s1, br1 > 0.5)

        # Proxies
        top_speed_1 = round(float(np.max(s1)), 1)
        top_speed_2 = round(float(np.max(s2)), 1)
        # High speed cornering proxy (min speed between 180 and 240 km/h)
        hs1 = [float(v) for v in s1 if 160 <= v <= 250]
        hs2 = [float(v) for v in s2 if 160 <= v <= 250]
        min_hs_1 = round(min(hs1), 1) if hs1 else round(float(np.mean(s1)), 1)
        min_hs_2 = round(min(hs2), 1) if hs2 else round(float(np.mean(s2)), 1)

        t1_lap = fastest1["LapTime"].total_seconds() if pd.notnull(fastest1["LapTime"]) else None
        t2_lap = fastest2["LapTime"].total_seconds() if pd.notnull(fastest2["LapTime"]) else None
        lap_delta = round(t1_lap - t2_lap, 3) if t1_lap and t2_lap else None

        driver_meta = drivers_meta(session, [driver1, driver2])

        return envelope(
            "FastF1",
            driver1=driver1,
            driver2=driver2,
            drivers=driver_meta,
            lap_time_1=round(t1_lap, 3) if t1_lap else None,
            lap_time_2=round(t2_lap, 3) if t2_lap else None,
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
                "speed_delta": [round(float(v1 - v2), 1) for v1, v2 in zip(s1, s2)]
            },
            track_map=track_coords,
            braking_table=braking_zones,
            proxies={
                "top_speed": {driver1: top_speed_1, driver2: top_speed_2, "delta": round(top_speed_1 - top_speed_2, 1), "unit": "km/h", "proxy": "Drag / Straight-Line Efficiency"},
                "min_hs_corner": {driver1: min_hs_1, driver2: min_hs_2, "delta": round(min_hs_1 - min_hs_2, 1), "unit": "km/h", "proxy": "Aerodynamic Downforce Load"},
                "avg_throttle": {driver1: round(float(np.mean(th1)), 1), driver2: round(float(np.mean(th2)), 1), "unit": "%", "proxy": "Power Delivery / Traction"},
            }
        )
    except Exception as exc:
        return envelope("FastF1", "source_error", f"Telemetry compare error: {exc}")
