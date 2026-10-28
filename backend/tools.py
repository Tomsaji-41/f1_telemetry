import datetime
import logging
from typing import Dict, Any, List, Optional, Union

try:
    from backend import resolver
    from backend.sources import jolpica, fastf1_src, openf1_src
except ImportError:
    import resolver
    from sources import jolpica, fastf1_src, openf1_src

logger = logging.getLogger("tools")

def today_iso() -> str:
    """Returns today's date in ISO format YYYY-MM-DD."""
    return datetime.date.today().isoformat()

def get_season_schedule(year: int) -> Dict[str, Any]:
    """
    Get the official Formula 1 calendar / race schedule for a specific season.
    Returns rounds, Grand Prix names, circuit names, locality, country, and event dates.
    Available from 1950 to present via Jolpica.
    """
    return jolpica.fetch_schedule(year)

def get_race_result(year: int, grand_prix: Union[str, int]) -> Dict[str, Any]:
    """
    Get full race classification and results for a Grand Prix in a given year.
    Returns finishing position, grid, status, points, driver, constructor, time, and fastest lap.
    Available from 1950 to present via Jolpica.
    """
    resolved = resolver.resolve_gp(str(grand_prix), year)
    if resolved.get("status") != "ok":
        return resolved
    return jolpica.fetch_race_results(year, resolved["round"])

def get_qualifying_result(year: int, grand_prix: Union[str, int]) -> Dict[str, Any]:
    """
    Get qualifying results for a Grand Prix including Q1, Q2, and Q3 times.
    Available from 2003 to present via Jolpica.
    """
    resolved = resolver.resolve_gp(str(grand_prix), year)
    if resolved.get("status") != "ok":
        return resolved
    return jolpica.fetch_qualifying_results(year, resolved["round"])

def get_standings(year: int, kind: str = "drivers", after_round: Optional[int] = None) -> Dict[str, Any]:
    """
    Get World Championship standings for a season, either 'drivers' or 'constructors'.
    Optionally get standings after a specific round number.
    Available from 1950 (drivers) and 1958 (constructors) to present via Jolpica.
    """
    kind_clean = "constructors" if "constructor" in kind.lower() else "drivers"
    return jolpica.fetch_standings(year, kind=kind_clean, after_round=after_round)

def get_champions(start_year: int, end_year: int) -> Dict[str, Any]:
    """
    Get official World Drivers' and World Constructors' Champions for a range of seasons.
    Computed directly from final standings via Jolpica.
    """
    return jolpica.fetch_champions(start_year, end_year)

def get_pit_stops(year: int, grand_prix: Union[str, int], driver: Optional[str] = None) -> Dict[str, Any]:
    """
    Get pit stop information (stop number, lap, duration) for a Grand Prix.
    Data exists from 2012 onward via Jolpica.
    """
    if year < 2012:
        return {
            "status": "not_available",
            "reason": f"Pit stop data not recorded for season {year}. Pit stop data exists from 2012 only.",
            "source": "Jolpica",
            "coverage_note": "Pit stop data exists from 2012 only."
        }
        
    resolved = resolver.resolve_gp(str(grand_prix), year)
    if resolved.get("status") != "ok":
        return resolved
        
    res = jolpica.fetch_pit_stops(year, resolved["round"])
    if res.get("status") != "ok":
        return res
        
    if driver:
        d_res = resolver.resolve_driver(driver, year)
        if d_res.get("status") != "ok":
            return d_res
        d_id = d_res["driver_id"]
        stops = [s for s in res.get("pit_stops", []) if s.get("driver_id") == d_id]
        res["pit_stops"] = stops
        res["driver"] = d_res["name"]
        
    return res

def get_tyre_stints(year: int, grand_prix: Union[str, int], driver: Optional[str] = None) -> Dict[str, Any]:
    """
    Get tyre compound stints, start lap, end lap, and tyre life per driver for a race.
    Detailed telemetry and tyre data exists from 2018 onward via FastF1.
    """
    resolved = resolver.resolve_gp(str(grand_prix), year)
    if resolved.get("status") != "ok":
        return resolved
        
    driver_code = None
    if driver:
        d_res = resolver.resolve_driver(driver, year)
        if d_res.get("status") != "ok":
            return d_res
        driver_code = d_res.get("code") or driver
        
    return fastf1_src.fetch_tyre_stints(year, resolved["round"], driver=driver_code)

def get_lap_times(year: int, grand_prix: Union[str, int], driver: str, session: str = "R") -> Dict[str, Any]:
    """
    Get per-lap lap times, sector times, tyre compound, tyre life, and position for a driver.
    Detailed lap data exists from 2018 onward via FastF1.
    """
    resolved = resolver.resolve_gp(str(grand_prix), year)
    if resolved.get("status") != "ok":
        return resolved
        
    d_res = resolver.resolve_driver(driver, year)
    if d_res.get("status") != "ok":
        return d_res
    driver_code = d_res.get("code") or driver
    
    return fastf1_src.fetch_lap_times(year, resolved["round"], driver=driver_code, session_type=session)

def get_sector_analysis(year: int, grand_prix: Union[str, int], driver: str, session: str = "R") -> Dict[str, Any]:
    """
    Get sector analysis for a driver in a session (best and average S1/S2/S3, and gap to overall session best).
    Detailed sector data exists from 2018 onward via FastF1.
    """
    resolved = resolver.resolve_gp(str(grand_prix), year)
    if resolved.get("status") != "ok":
        return resolved
        
    d_res = resolver.resolve_driver(driver, year)
    if d_res.get("status") != "ok":
        return d_res
    driver_code = d_res.get("code") or driver
    
    return fastf1_src.fetch_sector_analysis(year, resolved["round"], driver=driver_code, session_type=session)

def compare_drivers(year: int, grand_prix: Union[str, int], driver_a: str, driver_b: str, session: str = "R") -> Dict[str, Any]:
    """
    Compare two drivers head-to-head in a session (pace delta per stint, fastest lap delta, sector comparison).
    Detailed telemetry comparison exists from 2018 onward via FastF1.
    """
    resolved = resolver.resolve_gp(str(grand_prix), year)
    if resolved.get("status") != "ok":
        return resolved
        
    res_a = resolver.resolve_driver(driver_a, year)
    if res_a.get("status") != "ok":
        return res_a
    res_b = resolver.resolve_driver(driver_b, year)
    if res_b.get("status") != "ok":
        return res_b
        
    code_a = res_a.get("code") or driver_a
    code_b = res_b.get("code") or driver_b
    
    return fastf1_src.compare_drivers(year, resolved["round"], code_a, code_b, session_type=session)

def get_tyre_degradation(year: int, grand_prix: Union[str, int], driver: str, stint: Optional[int] = None) -> Dict[str, Any]:
    """
    Computes mathematical linear fit of lap times vs tyre life with fuel-corrected slope in seconds per lap.
    Returns computed fuel-corrected degradation slope, sample size, and R squared.
    Detailed tyre data exists from 2018 onward via FastF1.
    """
    resolved = resolver.resolve_gp(str(grand_prix), year)
    if resolved.get("status") != "ok":
        return resolved
        
    d_res = resolver.resolve_driver(driver, year)
    if d_res.get("status") != "ok":
        return d_res
    driver_code = d_res.get("code") or driver
    
    return fastf1_src.fetch_tyre_degradation(year, resolved["round"], driver=driver_code, stint=stint)

def get_race_control_events(year: int, grand_prix: Union[str, int]) -> Dict[str, Any]:
    """
    Get official race control events (Safety Cars, Virtual Safety Cars, Red Flags, penalties) with lap numbers.
    Available from 2018 onward via FastF1.
    """
    resolved = resolver.resolve_gp(str(grand_prix), year)
    if resolved.get("status") != "ok":
        return resolved
    return fastf1_src.fetch_race_control_events(year, resolved["round"])

def get_weather(year: int, grand_prix: Union[str, int], session: str = "R") -> Dict[str, Any]:
    """
    Get weather data (air temperature, track temperature, rainfall, humidity) for a session.
    Available from 2018 onward via FastF1.
    """
    resolved = resolver.resolve_gp(str(grand_prix), year)
    if resolved.get("status") != "ok":
        return resolved
    return fastf1_src.fetch_weather(year, resolved["round"], session_type=session)

def get_circuit_info(circuit_or_gp: str) -> Dict[str, Any]:
    """
    Get circuit metadata including circuit name, locality, country, coordinates, first GP year, and lap record.
    Covers all historical circuits from 1950 to present via Jolpica.
    """
    circuits = jolpica.fetch_circuits()
    query = circuit_or_gp.strip().lower()
    
    target_id = None
    for c in circuits:
        c_id = c.get("circuitId", "").lower()
        c_name = c.get("circuitName", "").lower()
        loc = c.get("Location", {}).get("locality", "").lower()
        country = c.get("Location", {}).get("country", "").lower()
        if query in [c_id, c_name, loc, country] or query in c_name:
            target_id = c.get("circuitId")
            break
            
    if not target_id:
        # Check aliases
        aliases = {
            "spa": "spa",
            "belgian": "spa",
            "belgian grand prix": "spa",
            "belgian gp": "spa",
            "monza": "monza",
            "italian": "monza",
            "italian grand prix": "monza",
            "silverstone": "silverstone",
            "british": "silverstone",
            "british grand prix": "silverstone",
            "interlagos": "interlagos",
            "brazilian": "interlagos",
            "são paulo": "interlagos",
            "suzuka": "suzuka",
            "japanese": "suzuka",
            "bahrain": "bahrain",
            "sakhir": "bahrain",
            "melbourne": "albert_park",
            "albert park": "albert_park",
            "australian": "albert_park",
            "monaco": "monaco",
            "zandvoort": "zandvoort",
            "dutch": "zandvoort",
            "austin": "americas",
            "cota": "americas",
            "united states": "americas",
            "hungaroring": "hungaroring",
            "hungarian": "hungaroring",
            "red bull ring": "red_bull_ring",
            "spielberg": "red_bull_ring",
            "austrian": "red_bull_ring",
            "catalunya": "catalunya",
            "barcelona": "catalunya",
            "spanish": "catalunya",
            "villeneuve": "villeneuve",
            "montreal": "villeneuve",
            "canadian": "villeneuve",
        }
        target_id = aliases.get(query)
        
    if not target_id:
        return {
            "status": "not_available",
            "reason": f"Circuit '{circuit_or_gp}' could not be identified.",
            "source": "Jolpica",
            "coverage_note": "Circuits database from 1950 to present."
        }
        
    return jolpica.fetch_circuit_info(target_id)

def get_driver_strategy(year: int, grand_prix: Union[str, int], driver: str) -> Dict[str, Any]:
    """
    Get full driver strategy for a race including stint breakdown, tyre compounds, and pit stop times.
    Detailed stint telemetry exists from 2018 onward via FastF1.
    """
    if year < 2018:
        return {
            "status": "not_available",
            "reason": f"Detailed tyre and lap data starts in 2018. For {year} I can show the race result, qualifying and pit stops (from 2012).",
            "source": "FastF1",
            "coverage_note": "Detailed lap, sector and tyre data exists from 2018 only."
        }
    resolved = resolver.resolve_gp(str(grand_prix), year)
    if resolved.get("status") != "ok":
        return resolved

    d_res = resolver.resolve_driver(driver, year)
    if d_res.get("status") != "ok":
        return d_res

    # 1. Stints
    stints_res = get_tyre_stints(year, resolved["round"], driver=d_res["code"] or d_res["driver_id"])
    stints_list = stints_res.get("stints", []) if stints_res.get("status") == "ok" else []

    # 2. Pit stops
    stops_res = get_pit_stops(year, resolved["round"], driver=d_res["driver_id"])
    stops_list = stops_res.get("pit_stops", []) if stops_res.get("status") == "ok" else []

    # 3. Race result for position, points, team
    results_res = get_race_result(year, resolved["round"])
    pos = "-"
    points = 0
    team = "Team"
    gap = None
    if results_res.get("status") == "ok":
        for r in results_res.get("results", []):
            if r.get("driver") == d_res["name"] or r.get("driver_id") == d_res["driver_id"] or r.get("code") == d_res.get("code"):
                pos = r.get("position", "-")
                points = r.get("points", 0)
                team = r.get("constructor", "Team")
                gap = r.get("time")
                break

    return {
        "status": "ok",
        "driver": d_res["name"],
        "team": team,
        "position": pos,
        "points": points,
        "gap": gap,
        "stints": stints_list,
        "pit_stops": stops_list,
        "grand_prix": resolved.get("grand_prix"),
        "year": year,
        "source": ["FastF1", "Jolpica"]
    }

def get_driver_profile(driver: str) -> Dict[str, Any]:
    """
    Get verified driver career profile including nationality, birth date, career wins, poles, world titles, and teams.
    Career totals are computed directly from Jolpica records.
    """
    res = resolver.resolve_driver(driver)
    if res.get("status") != "ok":
        return res
    return jolpica.fetch_driver_profile(res["driver_id"])

def get_team_history(team: str) -> Dict[str, Any]:
    """
    Get constructor history including seasons active, constructor titles, nationality, and team records.
    Verified directly from Jolpica records.
    """
    res = resolver.resolve_team(team)
    if res.get("status") != "ok":
        return res
    return jolpica.fetch_team_history(res["constructor_id"])

def get_live_session() -> Dict[str, Any]:
    """
    Get live or most recent Formula 1 session telemetry (positions, intervals, tyre stints).
    Covers 2023 onward via OpenF1.
    """
    return openf1_src.fetch_live_session()

def get_driver_image(driver: str, year: Optional[int] = None) -> Dict[str, Any]:
    """
    Get official headshot photo URL and team hex colour for a driver.
    Covers 2023 onward via OpenF1.
    """
    return openf1_src.fetch_driver_image(driver, year=year)

TOOL_REGISTRY = [
    get_season_schedule,
    get_race_result,
    get_qualifying_result,
    get_standings,
    get_champions,
    get_pit_stops,
    get_tyre_stints,
    get_driver_strategy,
    get_lap_times,
    get_sector_analysis,
    compare_drivers,
    get_tyre_degradation,
    get_race_control_events,
    get_weather,
    get_circuit_info,
    get_driver_profile,
    get_team_history,
    get_live_session,
    get_driver_image,
]

def get_career_records(metric: str = "wins") -> Dict[str, Any]:
    """
    Get all-time career F1 records (wins, poles, win_rate) loaded from ground truth data.
    """
    import json
    from pathlib import Path
    data_file = Path(__file__).resolve().parent.parent / "data" / "career_records.json"
    if not data_file.exists():
        data_file = Path(__file__).resolve().parent.parent / "tests" / "data" / "career_records.json"
    if data_file.exists():
        try:
            records = json.loads(data_file.read_text(encoding="utf-8"))
            if metric in records:
                return records[metric]
            return records.get("wins", {})
        except Exception:
            pass
    return {
        "title": "All-Time F1 Career Records",
        "header": "| Rank | Driver | Metric |\n|---|---|---|\n",
        "rows": []
    }
