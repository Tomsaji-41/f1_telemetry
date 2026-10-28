import logging
from typing import Dict, Any, Optional, List
try:
    from backend import cache
except ImportError:
    import cache

logger = logging.getLogger("sources.openf1")

OPENF1_BASE = "https://api.openf1.org/v1"

def fetch_live_session() -> Dict[str, Any]:
    # Cache for 15 seconds
    url_session = f"{OPENF1_BASE}/sessions?session_key=latest"
    session_data = cache.cached_get_json(url_session, cache.TTL_LIVE_SESSION)
    if not session_data or not isinstance(session_data, list) or len(session_data) == 0:
        return {
            "status": "not_available",
            "reason": "No live or recent session available from OpenF1",
            "source": "OpenF1",
            "coverage_note": "Covers 2023 onward."
        }
    
    session = session_data[-1]
    session_key = session.get("session_key")
    
    # Fetch latest positions
    url_pos = f"{OPENF1_BASE}/position?session_key={session_key}"
    pos_data = cache.cached_get_json(url_pos, cache.TTL_LIVE_SESSION) or []
    
    # Group by driver and get latest position
    latest_positions = {}
    if isinstance(pos_data, list):
        for p in pos_data:
            d_num = p.get("driver_number")
            if d_num is not None:
                latest_positions[d_num] = p.get("position")
                
    # Fetch drivers info
    url_drivers = f"{OPENF1_BASE}/drivers?session_key={session_key}"
    drivers_data = cache.cached_get_json(url_drivers, cache.TTL_CURRENT_ROUND) or []
    
    drivers_summary = []
    if isinstance(drivers_data, list):
        for d in drivers_data:
            d_num = d.get("driver_number")
            drivers_summary.append({
                "driver_number": d_num,
                "code": d.get("name_acronym"),
                "full_name": d.get("full_name"),
                "team": d.get("team_name"),
                "team_colour": f"#{d.get('team_colour')}" if d.get("team_colour") else None,
                "headshot_url": d.get("headshot_url"),
                "position": latest_positions.get(d_num)
            })
            
    drivers_summary.sort(key=lambda x: (x["position"] if x["position"] is not None else 999))

    return {
        "status": "ok",
        "session_name": session.get("session_name"),
        "session_type": session.get("session_type"),
        "circuit_short_name": session.get("circuit_short_name"),
        "country_name": session.get("country_name"),
        "year": session.get("year"),
        "date_start": session.get("date_start"),
        "positions": drivers_summary[:20],
        "source": "OpenF1",
        "coverage_note": "Covers 2023 onward."
    }

def fetch_driver_image(driver_code_or_name: str, year: Optional[int] = None) -> Dict[str, Any]:
    url = f"{OPENF1_BASE}/drivers?session_key=latest"
    drivers_data = cache.cached_get_json(url, cache.TTL_PAST_SEASON)
    
    matched = None
    query = driver_code_or_name.strip().lower()
    
    if drivers_data and isinstance(drivers_data, list):
        for d in drivers_data:
            acronym = (d.get("name_acronym") or "").lower()
            last_name = (d.get("last_name") or "").lower()
            full_name = (d.get("full_name") or "").lower()
            if query == acronym or query == last_name or query in full_name or full_name in query:
                matched = d
                break
                
    if matched:
        team_color = matched.get("team_colour")
        if team_color and not team_color.startswith("#"):
            team_color = f"#{team_color}"
        return {
            "status": "ok",
            "driver": matched.get("full_name"),
            "code": matched.get("name_acronym"),
            "headshot_url": matched.get("headshot_url"),
            "team": matched.get("team_name"),
            "team_colour": team_color,
            "has_placeholder": not bool(matched.get("headshot_url")),
            "source": "OpenF1",
            "coverage_note": "Covers 2023 onward."
        }

    return {
        "status": "not_available",
        "reason": f"No headshot image found for '{driver_code_or_name}'",
        "driver": driver_code_or_name,
        "headshot_url": None,
        "team_colour": None,
        "has_placeholder": True,
        "source": "OpenF1",
        "coverage_note": "Covers 2023 onward."
    }
