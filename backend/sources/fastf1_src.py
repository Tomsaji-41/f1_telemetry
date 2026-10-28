import logging
import datetime
from typing import Dict, Any, List, Optional
import numpy as np
from scipy import stats

try:
    import fastf1
    from backend import config
    fastf1.Cache.enable_cache(str(config.CACHE_DIR))
except Exception as e:
    fastf1 = None

logger = logging.getLogger("sources.fastf1")

COVERAGE_NOTE = "Detailed lap, sector and tyre data exists from 2018 only."

def _format_td(td) -> Optional[str]:
    if td is None or pd_isna(td):
        return None
    try:
        total_seconds = td.total_seconds()
        minutes = int(total_seconds // 60)
        seconds = total_seconds % 60
        return f"{minutes}:{seconds:06.3f}"
    except Exception:
        return None

def pd_isna(val) -> bool:
    try:
        import pandas as pd
        return pd.isna(val)
    except Exception:
        return val is None

def _check_year_coverage(year: int) -> Optional[Dict[str, Any]]:
    if year < 2018:
        return {
            "status": "not_available",
            "reason": f"FastF1 detailed telemetry and lap data is not available for season {year}. {COVERAGE_NOTE}",
            "source": "FastF1",
            "coverage_note": COVERAGE_NOTE
        }
    current_year = datetime.datetime.now().year
    if year > current_year:
        return {
            "status": "not_available",
            "reason": f"Season {year} has not taken place yet.",
            "source": "FastF1",
            "coverage_note": COVERAGE_NOTE
        }
    return None

def _get_session(year: int, grand_prix: Any, session_type: str = "R", laps: bool = True, telemetry: bool = False, weather: bool = False, messages: bool = False):
    cov = _check_year_coverage(year)
    if cov:
        return None, cov
    
    if not fastf1:
        return None, {
            "status": "not_available",
            "reason": "FastF1 library is unavailable.",
            "source": "FastF1",
            "coverage_note": COVERAGE_NOTE
        }
        
    try:
        session = fastf1.get_session(year, grand_prix, session_type)
        session.load(laps=laps, telemetry=telemetry, weather=weather, messages=messages)
        return session, None
    except Exception as e:
        logger.warning(f"FastF1 load error for {year} {grand_prix}: {e}")
        return None, {
            "status": "not_available",
            "reason": f"Could not load FastF1 session for {year} {grand_prix}: {str(e)}",
            "source": "FastF1",
            "coverage_note": COVERAGE_NOTE
        }

def fetch_tyre_stints(year: int, grand_prix: Any, driver: Optional[str] = None) -> Dict[str, Any]:
    session, err = _get_session(year, grand_prix, session_type="R", laps=True)
    if err:
        return err

    try:
        laps = session.laps
        if laps.empty:
            return {
                "status": "not_available",
                "reason": "No lap records found for this session.",
                "source": "FastF1",
                "coverage_note": COVERAGE_NOTE
            }

        if driver:
            d_laps = laps.pick_driver(driver)
            if d_laps.empty:
                return {
                    "status": "not_available",
                    "reason": f"Driver {driver} not found in this session.",
                    "source": "FastF1",
                    "coverage_note": COVERAGE_NOTE
                }
            laps = d_laps

        stints_data = []
        for d in laps["Driver"].unique():
            driver_laps = laps.pick_driver(d)
            for stint_num, stint_laps in driver_laps.groupby("Stint"):
                compound = stint_laps["Compound"].dropna().unique()
                comp_name = compound[0] if len(compound) > 0 else "UNKNOWN"
                start_lap = int(stint_laps["LapNumber"].min())
                end_lap = int(stint_laps["LapNumber"].max())
                max_life = int(stint_laps["TyreLife"].max()) if not pd_isna(stint_laps["TyreLife"].max()) else (end_lap - start_lap + 1)
                stints_data.append({
                    "driver": d,
                    "stint": int(stint_num),
                    "compound": comp_name,
                    "start_lap": start_lap,
                    "end_lap": end_lap,
                    "laps_completed": end_lap - start_lap + 1,
                    "tyre_life": max_life
                })

        return {
            "status": "ok",
            "year": year,
            "grand_prix": str(grand_prix),
            "stints": stints_data,
            "source": "FastF1",
            "coverage_note": COVERAGE_NOTE
        }
    except Exception as e:
        return {
            "status": "not_available",
            "reason": str(e),
            "source": "FastF1",
            "coverage_note": COVERAGE_NOTE
        }

def fetch_lap_times(year: int, grand_prix: Any, driver: str, session_type: str = "R") -> Dict[str, Any]:
    session, err = _get_session(year, grand_prix, session_type=session_type, laps=True)
    if err:
        return err

    try:
        d_laps = session.laps.pick_driver(driver)
        if d_laps.empty:
            return {
                "status": "not_available",
                "reason": f"No lap data for driver {driver}.",
                "source": "FastF1",
                "coverage_note": COVERAGE_NOTE
            }

        lap_records = []
        for _, row in d_laps.iterrows():
            lap_records.append({
                "lap": int(row["LapNumber"]),
                "lap_time": _format_td(row["LapTime"]),
                "s1": _format_td(row["Sector1Time"]),
                "s2": _format_td(row["Sector2Time"]),
                "s3": _format_td(row["Sector3Time"]),
                "compound": str(row["Compound"]) if not pd_isna(row["Compound"]) else "",
                "tyre_life": int(row["TyreLife"]) if not pd_isna(row["TyreLife"]) else None,
                "position": int(row["Position"]) if not pd_isna(row["Position"]) else None,
                "is_accurate": bool(row["IsAccurate"])
            })

        return {
            "status": "ok",
            "year": year,
            "grand_prix": str(grand_prix),
            "driver": driver,
            "session": session_type,
            "total_laps": len(lap_records),
            "laps": lap_records,
            "source": "FastF1",
            "coverage_note": COVERAGE_NOTE
        }
    except Exception as e:
        return {
            "status": "not_available",
            "reason": str(e),
            "source": "FastF1",
            "coverage_note": COVERAGE_NOTE
        }

def fetch_sector_analysis(year: int, grand_prix: Any, driver: str, session_type: str = "R") -> Dict[str, Any]:
    session, err = _get_session(year, grand_prix, session_type=session_type, laps=True)
    if err:
        return err

    try:
        all_laps = session.laps.pick_quicklaps()
        if all_laps.empty:
            all_laps = session.laps

        # Session-best sectors
        best_s1 = all_laps["Sector1Time"].min()
        best_s2 = all_laps["Sector2Time"].min()
        best_s3 = all_laps["Sector3Time"].min()

        d_laps = session.laps.pick_driver(driver).pick_quicklaps()
        if d_laps.empty:
            d_laps = session.laps.pick_driver(driver)
            
        if d_laps.empty:
            return {
                "status": "not_available",
                "reason": f"No valid lap data for driver {driver}",
                "source": "FastF1",
                "coverage_note": COVERAGE_NOTE
            }

        driver_best_s1 = d_laps["Sector1Time"].min()
        driver_best_s2 = d_laps["Sector2Time"].min()
        driver_best_s3 = d_laps["Sector3Time"].min()

        s1_seconds = [t.total_seconds() for t in d_laps["Sector1Time"].dropna()]
        s2_seconds = [t.total_seconds() for t in d_laps["Sector2Time"].dropna()]
        s3_seconds = [t.total_seconds() for t in d_laps["Sector3Time"].dropna()]

        avg_s1 = round(float(np.mean(s1_seconds)), 3) if s1_seconds else None
        avg_s2 = round(float(np.mean(s2_seconds)), 3) if s2_seconds else None
        avg_s3 = round(float(np.mean(s3_seconds)), 3) if s3_seconds else None

        gap_s1 = round(driver_best_s1.total_seconds() - best_s1.total_seconds(), 3) if driver_best_s1 and best_s1 else None
        gap_s2 = round(driver_best_s2.total_seconds() - best_s2.total_seconds(), 3) if driver_best_s2 and best_s2 else None
        gap_s3 = round(driver_best_s3.total_seconds() - best_s3.total_seconds(), 3) if driver_best_s3 and best_s3 else None

        return {
            "status": "ok",
            "year": year,
            "grand_prix": str(grand_prix),
            "driver": driver,
            "session": session_type,
            "sectors": {
                "s1": {
                    "best": _format_td(driver_best_s1),
                    "average_seconds": avg_s1,
                    "gap_to_overall_best": gap_s1
                },
                "s2": {
                    "best": _format_td(driver_best_s2),
                    "average_seconds": avg_s2,
                    "gap_to_overall_best": gap_s2
                },
                "s3": {
                    "best": _format_td(driver_best_s3),
                    "average_seconds": avg_s3,
                    "gap_to_overall_best": gap_s3
                }
            },
            "overall_session_bests": {
                "s1": _format_td(best_s1),
                "s2": _format_td(best_s2),
                "s3": _format_td(best_s3)
            },
            "source": "FastF1",
            "coverage_note": COVERAGE_NOTE
        }
    except Exception as e:
        return {
            "status": "not_available",
            "reason": str(e),
            "source": "FastF1",
            "coverage_note": COVERAGE_NOTE
        }

def compare_drivers(year: int, grand_prix: Any, driver_a: str, driver_b: str, session_type: str = "R") -> Dict[str, Any]:
    session, err = _get_session(year, grand_prix, session_type=session_type, laps=True)
    if err:
        return err

    try:
        laps_a = session.laps.pick_driver(driver_a).pick_quicklaps()
        laps_b = session.laps.pick_driver(driver_b).pick_quicklaps()

        if laps_a.empty or laps_b.empty:
            return {
                "status": "not_available",
                "reason": f"Insufficient representative lap data to compare {driver_a} and {driver_b}.",
                "source": "FastF1",
                "coverage_note": COVERAGE_NOTE
            }

        fastest_a = session.laps.pick_driver(driver_a).pick_fastest()
        fastest_b = session.laps.pick_driver(driver_b).pick_fastest()

        time_a_sec = fastest_a["LapTime"].total_seconds() if fastest_a is not None and not pd_isna(fastest_a["LapTime"]) else None
        time_b_sec = fastest_b["LapTime"].total_seconds() if fastest_b is not None and not pd_isna(fastest_b["LapTime"]) else None

        delta_fastest = round(time_a_sec - time_b_sec, 3) if time_a_sec and time_b_sec else None

        # Compare stints
        stints_a = session.laps.pick_driver(driver_a).groupby("Stint")
        stints_b = session.laps.pick_driver(driver_b).groupby("Stint")

        stint_comparisons = []
        for s_idx in range(1, max(len(stints_a), len(stints_b)) + 1):
            avg_a = None
            avg_b = None
            if s_idx in stints_a.groups:
                s_laps_a = stints_a.get_group(s_idx).pick_quicklaps()
                if not s_laps_a.empty:
                    avg_a = round(float(s_laps_a["LapTime"].dt.total_seconds().mean()), 3)
            if s_idx in stints_b.groups:
                s_laps_b = stints_b.get_group(s_idx).pick_quicklaps()
                if not s_laps_b.empty:
                    avg_b = round(float(s_laps_b["LapTime"].dt.total_seconds().mean()), 3)

            pace_delta = round(avg_a - avg_b, 3) if (avg_a and avg_b) else None
            stint_comparisons.append({
                "stint": s_idx,
                f"{driver_a}_avg_pace": avg_a,
                f"{driver_b}_avg_pace": avg_b,
                "pace_delta_seconds": pace_delta
            })

        return {
            "status": "ok",
            "year": year,
            "grand_prix": str(grand_prix),
            "driver_a": driver_a,
            "driver_b": driver_b,
            "fastest_lap_a": _format_td(fastest_a["LapTime"]) if fastest_a is not None else None,
            "fastest_lap_b": _format_td(fastest_b["LapTime"]) if fastest_b is not None else None,
            "delta_seconds": delta_fastest,
            "stints": stint_comparisons,
            "source": "FastF1",
            "coverage_note": COVERAGE_NOTE
        }
    except Exception as e:
        return {
            "status": "not_available",
            "reason": str(e),
            "source": "FastF1",
            "coverage_note": COVERAGE_NOTE
        }

def fetch_tyre_degradation(year: int, grand_prix: Any, driver: str, stint: Optional[int] = None) -> Dict[str, Any]:
    session, err = _get_session(year, grand_prix, session_type="R", laps=True)
    if err:
        return err

    try:
        d_laps = session.laps.pick_driver(driver).pick_quicklaps()
        if d_laps.empty:
            d_laps = session.laps.pick_driver(driver)
            
        if stint is not None:
            d_laps = d_laps[d_laps["Stint"] == stint]

        # Filter clean laps
        valid_laps = d_laps[d_laps["LapTime"].notna() & d_laps["TyreLife"].notna()]
        if len(valid_laps) < 4:
            return {
                "status": "not_available",
                "reason": f"Not enough valid laps ({len(valid_laps)}) to compute tyre degradation for {driver}.",
                "source": "FastF1",
                "coverage_note": COVERAGE_NOTE
            }

        x = valid_laps["TyreLife"].values.astype(float)
        y = valid_laps["LapTime"].dt.total_seconds().values.astype(float)

        res = stats.linregress(x, y)
        raw_slope = round(float(res.slope), 4)
        # Standard F1 fuel effect correction: car gets lighter by ~0.035s per lap, so true tyre degradation = raw slope + 0.035
        fuel_corrected_slope = round(raw_slope + 0.035, 4)
        r_squared = round(float(res.rvalue ** 2), 4)

        return {
            "status": "ok",
            "year": year,
            "grand_prix": str(grand_prix),
            "driver": driver,
            "stint": stint,
            "raw_slope_sec_per_lap": raw_slope,
            "fuel_corrected_slope_sec_per_lap": fuel_corrected_slope,
            "sample_size": len(valid_laps),
            "r_squared": r_squared,
            "source": "FastF1",
            "coverage_note": COVERAGE_NOTE
        }
    except Exception as e:
        return {
            "status": "not_available",
            "reason": str(e),
            "source": "FastF1",
            "coverage_note": COVERAGE_NOTE
        }

def fetch_race_control_events(year: int, grand_prix: Any) -> Dict[str, Any]:
    session, err = _get_session(year, grand_prix, session_type="R", laps=False, messages=True)
    if err:
        return err

    try:
        rc = session.race_control_messages
        if rc is None or rc.empty:
            return {
                "status": "not_available",
                "reason": "No race control messages found.",
                "source": "FastF1",
                "coverage_note": COVERAGE_NOTE
            }

        events = []
        for _, row in rc.iterrows():
            msg = str(row.get("Message", ""))
            category = str(row.get("Category", ""))
            flag = str(row.get("Flag", ""))
            lap = row.get("Lap")
            lap_num = int(lap) if not pd_isna(lap) else None
            
            # Filter for key events: safety car, VSC, red flag, penalty, investigation
            lower = msg.lower()
            if any(term in lower for term in ["safety car", "vsc", "virtual safety car", "red flag", "penalty", "investigation"]):
                events.append({
                    "lap": lap_num,
                    "category": category,
                    "flag": flag,
                    "message": msg
                })

        return {
            "status": "ok",
            "year": year,
            "grand_prix": str(grand_prix),
            "events_count": len(events),
            "events": events[:30],
            "source": "FastF1",
            "coverage_note": COVERAGE_NOTE
        }
    except Exception as e:
        return {
            "status": "not_available",
            "reason": str(e),
            "source": "FastF1",
            "coverage_note": COVERAGE_NOTE
        }

def fetch_weather(year: int, grand_prix: Any, session_type: str = "R") -> Dict[str, Any]:
    session, err = _get_session(year, grand_prix, session_type=session_type, laps=False, weather=True)
    if err:
        return err

    try:
        w = session.weather_data
        if w is None or w.empty:
            return {
                "status": "not_available",
                "reason": "No weather records found for this session.",
                "source": "FastF1",
                "coverage_note": COVERAGE_NOTE
            }

        air_temp = round(float(w["AirTemp"].mean()), 1) if "AirTemp" in w else None
        track_temp = round(float(w["TrackTemp"].mean()), 1) if "TrackTemp" in w else None
        rainfall = bool(w["Rainfall"].any()) if "Rainfall" in w else False
        humidity = round(float(w["Humidity"].mean()), 1) if "Humidity" in w else None

        return {
            "status": "ok",
            "year": year,
            "grand_prix": str(grand_prix),
            "session": session_type,
            "average_air_temp_c": air_temp,
            "average_track_temp_c": track_temp,
            "rainfall": rainfall,
            "humidity_percent": humidity,
            "source": "FastF1",
            "coverage_note": COVERAGE_NOTE
        }
    except Exception as e:
        return {
            "status": "not_available",
            "reason": str(e),
            "source": "FastF1",
            "coverage_note": COVERAGE_NOTE
        }
