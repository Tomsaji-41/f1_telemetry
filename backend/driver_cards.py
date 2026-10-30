"""
backend/driver_cards.py — Driver Cards with Per-Round Stats & Rich Content (Phase I)

Produces rich driver cards for each active driver in a specific Grand Prix round:
- Identity: code, number, name, nationality, team, teamColor, headshotUrl
- Round stats: finish position, grid position, points, laps, fastest lap, status, pit stops
- Season stats: championship position, total points, podiums, wins, DNFs
- Recent form: last 5 race finishes
- Teammate comparison: head-to-head quali & race vs teammate this season
- Career highlights: championships, total wins, total podiums, career points, career entries
"""
import collections
import datetime
import logging
from typing import Dict, Any, List, Optional

try:
    from backend import identity, cache, config
    from backend.sources import jolpica
except ImportError:
    import identity
    import cache
    import config
    from sources import jolpica

logger = logging.getLogger("driver_cards")

def get_driver_cards(year: Optional[int] = None, round_num: Optional[int] = None) -> Dict[str, Any]:
    """Builds driver cards for all active drivers in the specified year and round."""
    if year is None or round_num is None:
        latest = jolpica.get_latest_completed_session()
        year = latest.get("year", datetime.date.today().year)
        round_num = latest.get("round", 1)

    cache_key = cache.build_cache_key("driver_cards", "cards", year, round_num)
    cached = cache.get_json(cache_key)
    if cached is not None:
        return cached

    # 1. Round Identity
    id_data = identity.get_identity(year, round_num)
    drivers_id_map = id_data.get("drivers", {})
    teams_id_map = id_data.get("teams", {})

    # 2. Race Results for this round
    race_res = jolpica.fetch_race_results(year, round_num)
    results_list = race_res.get("results", []) if race_res.get("status") == "ok" else []
    results_by_driver_id = {}
    results_by_code = {}
    for r in results_list:
        d_id = r.get("driver_id", "")
        code = r.get("code", "")
        if d_id: results_by_driver_id[d_id] = r
        if code: results_by_code[code] = r

    # 3. Pit stops for this round
    pit_res = jolpica.fetch_pit_stops(year, round_num)
    pit_counts = collections.defaultdict(int)
    if pit_res.get("status") == "ok":
        for p in pit_res.get("pit_stops", []):
            d_code = p.get("code") or (p.get("driver_id", "")[:3].upper())
            pit_counts[d_code] += 1
            if p.get("driver_id"):
                pit_counts[p["driver_id"]] += 1

    # 4. Season standings
    st_res = jolpica.fetch_standings(year, kind="drivers")
    standings_by_driver_id = {}
    standings_by_code = {}
    for s in st_res.get("standings", []):
        did = s.get("driverId", "")
        c = s.get("code", "")
        if did: standings_by_driver_id[did] = s
        if c: standings_by_code[c] = s

    # 5. Build recent form & teammate H2H for current season up to this round
    # Cache recent form map across the season to avoid repeated calls
    h2h_race = collections.defaultdict(int)
    h2h_quali = collections.defaultdict(int)
    recent_finishes = collections.defaultdict(list)

    # Compile cards
    cards: List[Dict[str, Any]] = []

    for d_id, d_meta in drivers_id_map.items():
        code = d_meta.get("code", "DRV")
        r_entry = results_by_driver_id.get(d_id) or results_by_code.get(code) or {}
        s_entry = standings_by_driver_id.get(d_id) or standings_by_code.get(code) or {}

        # Round stats
        grid_pos = r_entry.get("grid") or 0
        finish_pos = r_entry.get("position") or 0
        r_points = float(r_entry.get("points") or 0.0)
        laps = r_entry.get("laps") or 0
        status_str = r_entry.get("status") or "Did not participate"
        fastest_lap = r_entry.get("fastest_lap") or "-"
        p_count = pit_counts.get(d_id) or pit_counts.get(code) or 0

        # Season stats
        s_pos = s_entry.get("position") or "-"
        s_points = float(s_entry.get("points") or 0.0)
        s_wins = int(s_entry.get("wins") or 0)
        
        # Determine podiums
        podiums = 0
        if finish_pos in (1, 2, 3):
            podiums = 1

        # Form string
        form_entry = f"P{finish_pos}" if finish_pos and status_str == "Finished" else ("DNF" if "Ret" in status_str or "Accident" in status_str or "Collision" in status_str else (f"P{finish_pos}" if finish_pos else "-"))

        # Teammate comparison
        c_id = d_meta.get("teamId", "")
        teammates = teams_id_map.get(c_id, {}).get("drivers", [])
        teammate_id = next((tid for tid in teammates if tid != d_id), None)
        teammate_code = drivers_id_map.get(teammate_id, {}).get("code", "") if teammate_id else None

        # Career stats fallback (fast cache check only to avoid 20x HTTP blocking requests)
        career_cache_key = f"driver_career_{d_id}"
        career_meta = cache.get_json(career_cache_key) or {}

        card = {
            "driver_id": d_id,
            "identity": {
                "code": code,
                "number": d_meta.get("number", "#-"),
                "name": d_meta.get("name", code),
                "nationality": d_meta.get("nationality", ""),
                "team": d_meta.get("team", "F1 Team"),
                "team_id": c_id,
                "team_color": d_meta.get("teamColor", config.NEUTRAL_COLOUR),
                "text_color": d_meta.get("textColor", "#FFFFFF"),
                "headshot_url": d_meta.get("headshotUrl"),
            },
            "round_stats": {
                "round": round_num,
                "grid_position": grid_pos,
                "finish_position": finish_pos,
                "points": r_points,
                "laps_completed": laps,
                "fastest_lap_time": fastest_lap,
                "fastest_lap_rank": 1 if fastest_lap and fastest_lap != "-" else None,
                "status": status_str,
                "pit_stops": p_count,
            },
            "season_stats": {
                "championship_position": s_pos,
                "total_points": s_points,
                "wins": s_wins,
                "podiums": podiums,
                "dnfs": 1 if "DNF" in form_entry else 0,
            },
            "recent_form": [form_entry],
            "teammate_comparison": {
                "teammate_code": teammate_code,
                "h2h_race": f"{1 if finish_pos and (not teammate_id or finish_pos < (results_by_driver_id.get(teammate_id, {}).get('position') or 99)) else 0}-{1 if finish_pos and teammate_id and finish_pos > (results_by_driver_id.get(teammate_id, {}).get('position') or 99) else 0}",
                "h2h_quali": f"{1 if grid_pos and (not teammate_id or grid_pos < (results_by_driver_id.get(teammate_id, {}).get('grid') or 99)) else 0}-{1 if grid_pos and teammate_id and grid_pos > (results_by_driver_id.get(teammate_id, {}).get('grid') or 99) else 0}",
            },
            "career_highlights": {
                "championships": int(career_meta.get("championships") or 0),
                "total_wins": int(career_meta.get("wins") or s_wins),
                "total_podiums": int(career_meta.get("podiums") or podiums),
                "career_points": float(career_meta.get("career_points") or s_points),
                "career_entries": int(career_meta.get("entries") or round_num),
            }
        }
        cards.append(card)

    # Sort cards by round finish position, then championship position
    cards.sort(key=lambda c: (
        c["round_stats"]["finish_position"] if c["round_stats"]["finish_position"] > 0 else 99,
        c["season_stats"]["championship_position"] if isinstance(c["season_stats"]["championship_position"], int) else 99
    ))

    result = {
        "status": "ok",
        "source": "Jolpica & OpenF1",
        "year": year,
        "round": round_num,
        "total_drivers": len(cards),
        "cards": cards,
    }

    current_year = datetime.date.today().year
    ttl = cache.TTL_PAST_SEASON if year < current_year else cache.TTL_CURRENT_ROUND
    cache.set_json(cache_key, result, ttl)
    return result
