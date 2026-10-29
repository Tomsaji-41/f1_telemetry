import datetime
import logging
from typing import Dict, Any, List, Optional
try:
    from backend import cache
except ImportError:
    import cache

logger = logging.getLogger("sources.jolpica")

JOLPICA_BASE = "https://api.jolpi.ca/ergast/f1"

def _get_ttl_for_year(year: int) -> float:
    current_year = datetime.datetime.now().year
    if year < current_year:
        return cache.TTL_PAST_SEASON
    return cache.TTL_CURRENT_ROUND

def fetch_schedule(year: int) -> Dict[str, Any]:
    url = f"{JOLPICA_BASE}/{year}.json?limit=100"
    current_year = datetime.datetime.now().year
    ttl = cache.TTL_PAST_SEASON if year < current_year else cache.TTL_CURRENT_STANDINGS
    data = cache.cached_get_json(url, ttl)
    if not data or "MRData" not in data:
        return {
            "status": "not_available",
            "reason": f"No schedule data found for season {year}",
            "source": "Jolpica",
            "coverage_note": "Schedules available from 1950 to present."
        }
    
    races = data["MRData"].get("RaceTable", {}).get("Races", [])
    if not races:
        return {
            "status": "not_available",
            "reason": f"No races scheduled or published for season {year}",
            "source": "Jolpica",
            "coverage_note": "Schedules available from 1950 to present."
        }
    
    formatted_races = []
    for r in races:
        circuit = r.get("Circuit", {})
        loc = circuit.get("Location", {})
        formatted_races.append({
            "round": int(r.get("round", 0)),
            "grand_prix": r.get("raceName", ""),
            "circuit_id": circuit.get("circuitId", ""),
            "circuit_name": circuit.get("circuitName", ""),
            "locality": loc.get("locality", ""),
            "country": loc.get("country", ""),
            "date": r.get("date", "")
        })
    
    return {
        "status": "ok",
        "year": year,
        "total_rounds": len(formatted_races),
        "schedule": formatted_races,
        "source": "Jolpica",
        "coverage_note": "Schedules available from 1950 to present."
    }

def get_latest_completed_session() -> Dict[str, Any]:
    """
    Runtime session resolver: queries Jolpica schedule and race results
    to dynamically identify the most recent completed Grand Prix with classified results.
    """
    current_year = datetime.datetime.now().year
    today = datetime.date.today()
    
    for yr in [current_year, current_year - 1, current_year - 2]:
        sched_res = fetch_schedule(yr)
        if sched_res.get("status") == "ok":
            races = sched_res.get("schedule", [])
            for r in reversed(races):
                d_str = r.get("date", "")
                try:
                    r_date = datetime.date.fromisoformat(d_str)
                    if r_date <= today:
                        rnd = int(r.get("round", 1))
                        res = fetch_race_results(yr, rnd)
                        if res.get("status") == "ok" and res.get("results"):
                            return {
                                "year": yr,
                                "round": rnd,
                                "grand_prix": r.get("grand_prix") or res.get("grand_prix", ""),
                                "date": r.get("date", ""),
                                "circuit": r.get("circuit_name", "") or res.get("circuit", ""),
                                "circuit_id": r.get("circuit_id", "")
                            }
                except Exception:
                    continue

    return {
        "year": 2024,
        "round": 24,
        "grand_prix": "Abu Dhabi Grand Prix",
        "date": "2024-12-08",
        "circuit": "Yas Marina Circuit",
        "circuit_id": "yas_marina"
    }

def get_available_sessions() -> Dict[str, Any]:
    """
    Returns available seasons and completed rounds for the UI session picker.
    """
    current_year = datetime.datetime.now().year
    seasons = list(range(current_year, 1949, -1))
    latest = get_latest_completed_session()
    return {
        "status": "ok",
        "source": "Jolpica",
        "current_year": current_year,
        "latest_completed": latest,
        "seasons": seasons,
        "coverage_note": "FIA Formula 1 World Championship 1950-present"
    }

def fetch_race_results(year: int, round_num: int) -> Dict[str, Any]:
    url = f"{JOLPICA_BASE}/{year}/{round_num}/results.json?limit=100"
    ttl = _get_ttl_for_year(year)
    data = cache.cached_get_json(url, ttl)
    if not data or "MRData" not in data:
        return {
            "status": "not_available",
            "reason": f"Race results unavailable for {year} round {round_num}",
            "source": "Jolpica",
            "coverage_note": "Results available from 1950 to present."
        }
    
    races = data["MRData"].get("RaceTable", {}).get("Races", [])
    if not races or not races[0].get("Results"):
        return {
            "status": "not_available",
            "reason": f"Race results not yet available or race has not taken place for {year} round {round_num}",
            "source": "Jolpica",
            "coverage_note": "Results available from 1950 to present."
        }
    
    race = races[0]
    results_list = []
    for r in race.get("Results", []):
        driver = r.get("Driver", {})
        constructor = r.get("Constructor", {})
        fastest = r.get("FastestLap", {})
        results_list.append({
            "position": int(r.get("position", 0)),
            "driver": f"{driver.get('givenName', '')} {driver.get('familyName', '')}".strip(),
            "code": driver.get("code", ""),
            "driver_id": driver.get("driverId", ""),
            "constructor": constructor.get("name", ""),
            "grid": int(r.get("grid", 0)),
            "laps": int(r.get("laps", 0)),
            "status": r.get("status", ""),
            "points": float(r.get("points", 0)),
            "time": r.get("Time", {}).get("time", ""),
            "fastest_lap": fastest.get("Time", {}).get("time", "") if fastest else ""
        })
    
    return {
        "status": "ok",
        "year": year,
        "round": round_num,
        "grand_prix": race.get("raceName", ""),
        "date": race.get("date", ""),
        "circuit": race.get("Circuit", {}).get("circuitName", ""),
        "results": results_list,
        "source": "Jolpica",
        "coverage_note": "Results available from 1950 to present."
    }

def fetch_qualifying_results(year: int, round_num: int) -> Dict[str, Any]:
    url = f"{JOLPICA_BASE}/{year}/{round_num}/qualifying.json?limit=100"
    ttl = _get_ttl_for_year(year)
    data = cache.cached_get_json(url, ttl)
    if not data or "MRData" not in data:
        return {
            "status": "not_available",
            "reason": f"Qualifying results unavailable for {year} round {round_num}",
            "source": "Jolpica",
            "coverage_note": "Detailed qualifying results available from 2003 to present."
        }
    
    races = data["MRData"].get("RaceTable", {}).get("Races", [])
    if not races or not races[0].get("QualifyingResults"):
        return {
            "status": "not_available",
            "reason": f"Qualifying data not available for {year} round {round_num}",
            "source": "Jolpica",
            "coverage_note": "Detailed qualifying results available from 2003 to present."
        }
    
    race = races[0]
    q_list = []
    for q in race.get("QualifyingResults", []):
        driver = q.get("Driver", {})
        q_list.append({
            "position": int(q.get("position", 0)),
            "driver": f"{driver.get('givenName', '')} {driver.get('familyName', '')}".strip(),
            "code": driver.get("code", ""),
            "constructor": q.get("Constructor", {}).get("name", ""),
            "q1": q.get("Q1", ""),
            "q2": q.get("Q2", ""),
            "q3": q.get("Q3", "")
        })
    
    return {
        "status": "ok",
        "year": year,
        "round": round_num,
        "grand_prix": race.get("raceName", ""),
        "qualifying": q_list,
        "source": "Jolpica",
        "coverage_note": "Detailed qualifying results available from 2003 to present."
    }

def map_driver_standings(js: dict, total_rounds: int) -> dict:
    sl = js["MRData"]["StandingsTable"]["StandingsLists"][0]
    rows = []
    seen_codes: Dict[str, str] = {}
    for s in sl.get("DriverStandings", []):
        drv = s.get("Driver") or {}
        d_id = drv.get("driverId") or ""
        given = drv.get("givenName") or ""
        family = drv.get("familyName") or ""
        raw_code = drv.get("code")
        if raw_code and len(raw_code) == 3:
            code = raw_code.upper()
        else:
            # Fall back to first 3 letters of family name (Phase 2.1)
            code = family[:3].upper() if len(family) >= 3 else (family + "X")[:3].upper()
            logger.info("Driver %s missing official code; derived %s from family name", d_id, code)

        # Unique code verification within season
        if code in seen_codes and seen_codes[code] != d_id:
            code = (given[:1] + family[:2]).upper()
        seen_codes[code] = d_id

        num = drv.get("permanentNumber") or s.get("number") or "-"

        cons = s.get("Constructors") or []
        pts = float(s["points"])
        pos_raw = s.get("position")
        if pos_raw is not None:
            try:
                pos_val = int(pos_raw)
            except (ValueError, TypeError):
                pos_val = s.get("positionText", "n/a")
        else:
            pos_val = s.get("positionText", "n/a")
        if not pos_val or str(pos_val) == "-":
            pos_val = "n/a"

        team_name = cons[-1]["name"] if cons else "n/a"
        c_id = cons[-1]["constructorId"] if cons else ""
        if not team_name or team_name == "-":
            team_name = "n/a"

        rows.append({
            "pos": pos_val,
            "position": pos_val,
            "driverId": d_id,
            "driver_id": d_id,
            "code": code,
            "number": num,
            "driver": f'{given} {family}'.strip(),
            "given_name": given,
            "family_name": family,
            "nationality": drv.get("nationality", ""),
            "dob": drv.get("dateOfBirth", ""),
            "constructorId": c_id,
            "team_id": c_id,
            "team": team_name,
            "constructor": team_name,
            "points": int(pts) if pts == int(pts) else pts,
            "wins": int(s.get("wins", 0)),
        })
    return {
        "status": "ok",
        "season": int(sl.get("season", 0)),
        "round": int(sl.get("round", 0)),
        "total_rounds": total_rounds,
        "rows": rows,
        "standings": rows,
        "kind": "drivers",
        "source": "Jolpica"
    }

def map_constructor_standings(js: dict, total_rounds: int) -> dict:
    sl = js["MRData"]["StandingsTable"]["StandingsLists"][0]
    rows = []
    for s in sl.get("ConstructorStandings", []):
        cons = s.get("Constructor") or {}
        pts = float(s["points"])
        pos_raw = s.get("position")
        if pos_raw is not None:
            try:
                pos_val = int(pos_raw)
            except (ValueError, TypeError):
                pos_val = s.get("positionText", "n/a")
        else:
            pos_val = s.get("positionText", "n/a")
        if not pos_val or str(pos_val) == "-":
            pos_val = "n/a"

        team_name = cons.get("name", "n/a") if cons else "n/a"
        if not team_name or team_name == "-":
            team_name = "n/a"

        rows.append({
            "pos": pos_val,
            "position": pos_val,
            "team": team_name,
            "constructor": team_name,
            "points": int(pts) if pts == int(pts) else pts,
            "wins": int(s.get("wins", 0)),
        })
    return {
        "status": "ok",
        "season": int(sl.get("season", 0)),
        "round": int(sl.get("round", 0)),
        "total_rounds": total_rounds,
        "rows": rows,
        "standings": rows,
        "kind": "constructors",
        "source": "Jolpica"
    }

def fetch_standings(year: int, kind: str = "drivers", after_round: Optional[int] = None) -> Dict[str, Any]:
    current_year = datetime.datetime.now().year
    ttl = cache.TTL_PAST_SEASON if year < current_year else cache.TTL_CURRENT_STANDINGS
    
    # Get total_rounds from schedule
    total_rounds = 0
    sched = fetch_schedule(year)
    if sched.get("status") == "ok":
        total_rounds = len(sched.get("schedule", []))
    if not total_rounds:
        total_rounds = 24 if year >= 2024 else 22

    round_part = f"/{after_round}" if after_round else ""
    endpoint = "driverStandings" if kind == "drivers" else "constructorStandings"
    url = f"{JOLPICA_BASE}/{year}{round_part}/{endpoint}.json?limit=100"
    
    data = cache.cached_get_json(url, ttl)
    if not data or "MRData" not in data:
        return {
            "status": "not_available",
            "reason": f"Standings data unavailable for {year}",
            "source": "Jolpica",
            "coverage_note": "Standings available from 1950 to present."
        }
    
    standings_table = data["MRData"].get("StandingsTable", {})
    lists = standings_table.get("StandingsLists", [])
    if not lists:
        return {
            "status": "not_available",
            "reason": f"No standings found for {year} {kind}",
            "source": "Jolpica",
            "coverage_note": "Standings available from 1950 to present."
        }
    
    if kind == "drivers":
        return map_driver_standings(data, total_rounds)
    else:
        return map_constructor_standings(data, total_rounds)

def fetch_champions(start_year: int, end_year: int) -> Dict[str, Any]:
    champions = []
    for yr in range(start_year, end_year + 1):
        url_d = f"{JOLPICA_BASE}/{yr}/driverStandings/1.json"
        data_d = cache.cached_get_json(url_d, cache.TTL_PAST_SEASON)
        
        url_c = f"{JOLPICA_BASE}/{yr}/constructorStandings/1.json"
        data_c = cache.cached_get_json(url_c, cache.TTL_PAST_SEASON)
        
        d_champ = "Unknown"
        d_pts = 0.0
        d_wins = 0
        c_champ = "None"
        c_pts = 0.0
        
        if data_d and "MRData" in data_d:
            lists = data_d["MRData"].get("StandingsTable", {}).get("StandingsLists", [])
            if lists and lists[0].get("DriverStandings"):
                top_d = lists[0]["DriverStandings"][0]
                driver = top_d.get("Driver", {})
                d_champ = f"{driver.get('givenName', '')} {driver.get('familyName', '')}".strip()
                d_pts = float(top_d.get("points", 0))
                d_wins = int(top_d.get("wins", 0))
                
        if data_c and "MRData" in data_c:
            lists = data_c["MRData"].get("StandingsTable", {}).get("StandingsLists", [])
            if lists and lists[0].get("ConstructorStandings"):
                top_c = lists[0]["ConstructorStandings"][0]
                c_champ = top_c.get("Constructor", {}).get("name", "")
                c_pts = float(top_c.get("points", 0))
                
        champions.append({
            "year": yr,
            "driver_champion": d_champ,
            "driver_points": d_pts,
            "driver_wins": d_wins,
            "constructor_champion": c_champ,
            "constructor_points": c_pts
        })
        
    return {
        "status": "ok",
        "start_year": start_year,
        "end_year": end_year,
        "champions": champions,
        "source": "Jolpica",
        "coverage_note": "Championship records available from 1950 (drivers) and 1958 (constructors)."
    }

def fetch_pit_stops(year: int, round_num: int) -> Dict[str, Any]:
    if year < 2012:
        return {
            "status": "not_available",
            "reason": f"Pit stop data not recorded for {year}. Pit stop data exists from 2012 only.",
            "source": "Jolpica",
            "coverage_note": "Pit stop data exists from 2012 only."
        }
        
    url = f"{JOLPICA_BASE}/{year}/{round_num}/pitstops.json?limit=100"
    ttl = _get_ttl_for_year(year)
    data = cache.cached_get_json(url, ttl)
    if not data or "MRData" not in data:
        return {
            "status": "not_available",
            "reason": f"Pit stop data unavailable for {year} round {round_num}",
            "source": "Jolpica",
            "coverage_note": "Pit stop data exists from 2012 only."
        }
        
    race_table = data["MRData"].get("RaceTable", {})
    races = race_table.get("Races", [])
    if not races:
        if str(race_table.get("round")) == str(round_num) or data["MRData"].get("total") == "0":
            return {
                "status": "ok",
                "year": year,
                "round": round_num,
                "pit_stops": [],
                "source": "Jolpica",
                "coverage_note": "Pit stop data exists from 2012 only."
            }
        return {
            "status": "not_available",
            "reason": f"No race found for {year} round {round_num}",
            "source": "Jolpica",
            "coverage_note": "Pit stop data exists from 2012 only."
        }
        
    stops = []
    for s in races[0].get("PitStops", []):
        stops.append({
            "driver_id": s.get("driverId", ""),
            "stop": int(s.get("stop", 0)),
            "lap": int(s.get("lap", 0)),
            "time": s.get("time", ""),
            "duration": s.get("duration", "")
        })
        
    return {
        "status": "ok",
        "year": year,
        "round": round_num,
        "pit_stops": stops,
        "source": "Jolpica",
        "coverage_note": "Pit stop data exists from 2012 only."
    }
        
    return {
        "status": "ok",
        "year": year,
        "round": round_num,
        "grand_prix": races[0].get("raceName", ""),
        "pit_stops": stops,
        "source": "Jolpica",
        "coverage_note": "Pit stop data exists from 2012 only."
    }

def fetch_circuits() -> List[Dict[str, Any]]:
    url = f"{JOLPICA_BASE}/circuits.json?limit=150"
    data = cache.cached_get_json(url, cache.TTL_PAST_SEASON)
    if not data or "MRData" not in data:
        return []
    circuits = data["MRData"].get("CircuitTable", {}).get("Circuits", [])
    return circuits

def fetch_circuit_info(circuit_id: str) -> Dict[str, Any]:
    url = f"{JOLPICA_BASE}/circuits/{circuit_id}.json"
    data = cache.cached_get_json(url, cache.TTL_PAST_SEASON)
    if not data or "MRData" not in data:
        return {
            "status": "not_available",
            "reason": f"Circuit {circuit_id} not found",
            "source": "Jolpica",
            "coverage_note": "Circuits database from 1950 to present."
        }
    
    circuits = data["MRData"].get("CircuitTable", {}).get("Circuits", [])
    if not circuits:
        return {
            "status": "not_available",
            "reason": f"Circuit {circuit_id} not found",
            "source": "Jolpica",
            "coverage_note": "Circuits database from 1950 to present."
        }
    
    c = circuits[0]
    loc = c.get("Location", {})
    
    # Check first GP year and lap record from races at this circuit
    races_url = f"{JOLPICA_BASE}/circuits/{circuit_id}/races.json?limit=1"
    first_race_data = cache.cached_get_json(races_url, cache.TTL_PAST_SEASON)
    first_year = None
    if first_race_data and "MRData" in first_race_data:
        r_list = first_race_data["MRData"].get("RaceTable", {}).get("Races", [])
        if r_list:
            first_year = int(r_list[0].get("season", 0))
            
    # Fastest lap / lap record query
    fl_url = f"{JOLPICA_BASE}/circuits/{circuit_id}/fastest/1/results.json?limit=1"
    fl_data = cache.cached_get_json(fl_url, cache.TTL_PAST_SEASON)
    lap_record = None
    if fl_data and "MRData" in fl_data:
        fl_races = fl_data["MRData"].get("RaceTable", {}).get("Races", [])
        if fl_races and fl_races[0].get("Results"):
            res = fl_races[0]["Results"][0]
            fl_info = res.get("FastestLap", {})
            driver = res.get("Driver", {})
            lap_record = {
                "time": fl_info.get("Time", {}).get("time", ""),
                "driver": f"{driver.get('givenName', '')} {driver.get('familyName', '')}".strip(),
                "year": fl_races[0].get("season", "")
            }

    return {
        "status": "ok",
        "circuit_id": c.get("circuitId", ""),
        "circuit_name": c.get("circuitName", ""),
        "locality": loc.get("locality", ""),
        "country": loc.get("country", ""),
        "lat": loc.get("lat", ""),
        "long": loc.get("long", ""),
        "first_gp_year": first_year,
        "lap_record": lap_record,
        "source": "Jolpica",
        "coverage_note": "Circuits database from 1950 to present."
    }

def fetch_driver_profile(driver_id: str) -> Dict[str, Any]:
    url = f"{JOLPICA_BASE}/drivers/{driver_id}.json"
    data = cache.cached_get_json(url, cache.TTL_PAST_SEASON)
    if not data or "MRData" not in data:
        return {
            "status": "not_available",
            "reason": f"Driver {driver_id} not found",
            "source": "Jolpica",
            "coverage_note": "Driver database 1950 to present."
        }
    
    drivers = data["MRData"].get("DriverTable", {}).get("Drivers", [])
    if not drivers:
        return {
            "status": "not_available",
            "reason": f"Driver {driver_id} not found",
            "source": "Jolpica",
            "coverage_note": "Driver database 1950 to present."
        }
        
    d = drivers[0]
    
    # Query wins count
    wins_data = cache.cached_get_json(f"{JOLPICA_BASE}/drivers/{driver_id}/results/1.json?limit=1", cache.TTL_CURRENT_ROUND)
    wins = int(wins_data.get("MRData", {}).get("total", 0)) if wins_data else 0
    
    # Query poles count
    poles_data = cache.cached_get_json(f"{JOLPICA_BASE}/drivers/{driver_id}/qualifying/1.json?limit=1", cache.TTL_CURRENT_ROUND)
    poles = int(poles_data.get("MRData", {}).get("total", 0)) if poles_data else 0
    
    # Query titles count
    titles_data = cache.cached_get_json(f"{JOLPICA_BASE}/drivers/{driver_id}/driverStandings/1.json?limit=100", cache.TTL_CURRENT_ROUND)
    titles = 0
    title_years = []
    if titles_data and "MRData" in titles_data:
        st_lists = titles_data["MRData"].get("StandingsTable", {}).get("StandingsLists", [])
        for sl in st_lists:
            # Standings list at final round or championship win
            yr = sl.get("season")
            if yr:
                title_years.append(int(yr))
        titles = len(title_years)

    # Teams active
    teams_data = cache.cached_get_json(f"{JOLPICA_BASE}/drivers/{driver_id}/constructors.json?limit=100", cache.TTL_PAST_SEASON)
    teams = []
    if teams_data and "MRData" in teams_data:
        c_list = teams_data["MRData"].get("ConstructorTable", {}).get("Constructors", [])
        teams = [c.get("name", "") for c in c_list]

    return {
        "status": "ok",
        "driver_id": d.get("driverId", ""),
        "full_name": f"{d.get('givenName', '')} {d.get('familyName', '')}".strip(),
        "code": d.get("code", ""),
        "permanent_number": d.get("permanentNumber", ""),
        "nationality": d.get("nationality", ""),
        "birth_date": d.get("dateOfBirth", ""),
        "career_wins": wins,
        "career_poles": poles,
        "world_titles": titles,
        "title_years": sorted(title_years),
        "teams": teams,
        "source": "Jolpica",
        "coverage_note": "Career totals verified directly from Jolpica."
    }

def fetch_team_history(constructor_id: str) -> Dict[str, Any]:
    url = f"{JOLPICA_BASE}/constructors/{constructor_id}.json"
    data = cache.cached_get_json(url, cache.TTL_PAST_SEASON)
    if not data or "MRData" not in data:
        return {
            "status": "not_available",
            "reason": f"Team {constructor_id} not found",
            "source": "Jolpica",
            "coverage_note": "Constructor database 1950 to present."
        }
        
    constructors = data["MRData"].get("ConstructorTable", {}).get("Constructors", [])
    if not constructors:
        return {
            "status": "not_available",
            "reason": f"Team {constructor_id} not found",
            "source": "Jolpica",
            "coverage_note": "Constructor database 1950 to present."
        }
        
    c = constructors[0]
    
    # Titles
    titles_data = cache.cached_get_json(f"{JOLPICA_BASE}/constructors/{constructor_id}/constructorStandings/1.json?limit=100", cache.TTL_CURRENT_ROUND)
    titles = 0
    title_years = []
    if titles_data and "MRData" in titles_data:
        st_lists = titles_data["MRData"].get("StandingsTable", {}).get("StandingsLists", [])
        for sl in st_lists:
            yr = sl.get("season")
            if yr:
                title_years.append(int(yr))
        titles = len(title_years)
        
    # Seasons active
    seasons_data = cache.cached_get_json(f"{JOLPICA_BASE}/constructors/{constructor_id}/seasons.json?limit=100", cache.TTL_PAST_SEASON)
    seasons = []
    if seasons_data and "MRData" in seasons_data:
        s_list = seasons_data["MRData"].get("SeasonTable", {}).get("Seasons", [])
        seasons = [int(s.get("season", 0)) for s in s_list]

    return {
        "status": "ok",
        "constructor_id": c.get("constructorId", ""),
        "name": c.get("name", ""),
        "nationality": c.get("nationality", ""),
        "seasons_active": f"{min(seasons)} - {max(seasons)}" if seasons else "Unknown",
        "total_seasons": len(seasons),
        "constructor_titles": titles,
        "title_years": sorted(title_years),
        "source": "Jolpica",
        "coverage_note": "Constructor history verified from Jolpica."
    }
