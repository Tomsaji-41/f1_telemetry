"""
backend/session_map.py — Dynamic Mapping between Jolpica and FastF1 Schedules

Maps Jolpica round numbers to FastF1 events by date, normalized Grand Prix name,
and circuit metadata — NOT by naive round number alone. Handles cancelled races
(e.g., 2023 Imola) and double headers (e.g., 2020 Styrian/70th Anniversary/Sakhir).
"""
import re
import datetime
import logging
from typing import Dict, Any, Optional, List

try:
    import fastf1
except ImportError:
    fastf1 = None

try:
    from backend.sources import jolpica
    from backend import cache
except ImportError:
    import sources.jolpica as jolpica
    import cache

logger = logging.getLogger("session_map")

_SEASON_MAP_CACHE: Dict[int, Dict[int, Dict[str, Any]]] = {}

def normalize_name(name: str) -> str:
    """Normalize Grand Prix, circuit, or city name for resilient matching."""
    if not name:
        return ""
    text = name.lower()
    text = re.sub(r"\b(grand\s*prix|gp|formula\s*1|f1|international|autodromo|circuit|autodrome)\b", "", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return " ".join(text.split())

def _parse_date(date_val: Any) -> Optional[datetime.date]:
    if date_val is None:
        return None
    # Handle pandas NaT / NaN
    if str(date_val) in ("NaT", "nan", "<NA>"):
        return None
    if hasattr(date_val, "date"):
        try:
            return date_val.date()
        except Exception:
            pass
    if isinstance(date_val, datetime.date):
        return date_val
    try:
        s = str(date_val).split("T")[0].split()[0]
        return datetime.date.fromisoformat(s)
    except Exception:
        return None

def get_season_mapping(year: int) -> Dict[int, Dict[str, Any]]:
    """
    Builds and returns a mapping of Jolpica round -> FastF1 event info.
    Cached per season.
    """
    if year in _SEASON_MAP_CACHE:
        return _SEASON_MAP_CACHE[year]

    mapping: Dict[int, Dict[str, Any]] = {}

    # 1. Fetch Jolpica schedule
    j_sched = jolpica.fetch_schedule(year) if jolpica else {}
    j_races = j_sched.get("schedule", []) if j_sched.get("status") == "ok" else []

    # 2. Fetch FastF1 schedule if available
    ff1_events: List[Dict[str, Any]] = []
    if fastf1 is not None and year >= 2018:
        try:
            sched_df = fastf1.get_event_schedule(year, include_testing=False)
            for _, row in sched_df.iterrows():
                ev_rnd = row.get("RoundNumber")
                try:
                    ev_rnd_int = int(ev_rnd)
                except (ValueError, TypeError):
                    ev_rnd_int = 0
                if ev_rnd_int <= 0:
                    continue
                ev_date = _parse_date(row.get("EventDate")) or _parse_date(row.get("Session5Date"))
                ff1_events.append({
                    "fastf1_round": ev_rnd_int,
                    "event_name": str(row.get("EventName", "")),
                    "location": str(row.get("Location", "")),
                    "country": str(row.get("Country", "")),
                    "date": ev_date,
                    "raw_event": row,
                })
        except Exception as e:
            logger.warning(f"Could not load FastF1 schedule for {year}: {e}")

    for r_obj in j_races:
        j_round = int(r_obj.get("round", 0))
        j_name = r_obj.get("grand_prix") or r_obj.get("race_name", "")
        j_date = _parse_date(r_obj.get("date"))
        j_norm = normalize_name(j_name)
        j_circuit = r_obj.get("circuit_name", "")
        j_circuit_norm = normalize_name(j_circuit)

        matched_ff1 = None

        # Strategy A: Date proximity (within 4 days) AND normalized token overlap
        if j_date and ff1_events:
            for ev in ff1_events:
                if ev["date"]:
                    diff_days = abs((ev["date"] - j_date).days)
                    if diff_days <= 4:
                        ev_norm = normalize_name(ev["event_name"])
                        ev_loc = normalize_name(ev["location"])
                        if (ev_norm in j_norm or j_norm in ev_norm or
                            ev_loc in j_norm or j_norm in ev_loc or
                            ev_loc in j_circuit_norm or not j_norm):
                            matched_ff1 = ev
                            break

        # Strategy B: If no date match, match by normalized name
        if not matched_ff1 and ff1_events:
            for ev in ff1_events:
                ev_norm = normalize_name(ev["event_name"])
                if ev_norm and (ev_norm == j_norm or ev_norm in j_norm or j_norm in ev_norm):
                    matched_ff1 = ev
                    break

        if matched_ff1:
            mapping[j_round] = {
                "jolpica_round": j_round,
                "grand_prix": j_name,
                "date": str(j_date) if j_date else None,
                "fastf1_available": True,
                "fastf1_round": matched_ff1["fastf1_round"],
                "fastf1_name": matched_ff1["event_name"],
                "location": matched_ff1["location"],
                "is_cancelled": False,
            }
        else:
            # Check if cancelled or pre-FastF1
            is_cancelled = False
            if year == 2023 and ("imola" in j_norm or "emilia" in j_norm):
                is_cancelled = True

            mapping[j_round] = {
                "jolpica_round": j_round,
                "grand_prix": j_name,
                "date": str(j_date) if j_date else None,
                "fastf1_available": False,
                "fastf1_round": None,
                "fastf1_name": None,
                "location": r_obj.get("circuit_name"),
                "is_cancelled": is_cancelled,
                "reason": "Cancelled session" if is_cancelled else ("Pre-2018 session" if year < 2018 else "Not matched in FastF1 calendar"),
            }

    _SEASON_MAP_CACHE[year] = mapping
    return mapping

def jolpica_to_fastf1_round(year: int, jolpica_round: int) -> Optional[int]:
    """Resolves the corresponding FastF1 round number for a Jolpica round number."""
    mapping = get_season_mapping(year)
    round_info = mapping.get(jolpica_round)
    if round_info and round_info.get("fastf1_available"):
        return round_info.get("fastf1_round")
    return None

def get_event_meta(year: int, round_num: int) -> Dict[str, Any]:
    """Returns mapping metadata for a given year and Jolpica round."""
    mapping = get_season_mapping(year)
    return mapping.get(round_num, {
        "jolpica_round": round_num,
        "fastf1_available": False,
        "is_cancelled": False,
        "reason": f"Round {round_num} not found in {year} schedule",
    })
