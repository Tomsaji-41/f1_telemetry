import datetime
import json
import logging
import sqlite3
from typing import TypedDict, Optional, List, Dict, Any

try:
    from backend import config, tools
    from backend.sources import jolpica
except ImportError:
    import config, tools
    from sources import jolpica

logger = logging.getLogger("state")

class Pending(TypedDict):
    intent: str
    slots: dict            # filled slots
    awaiting: str          # slot we asked for: year | grand_prix | driver | kind | metric
    page: int              # option page for paging
    options: list          # last options shown [{label, value, action}]

class ConvState(TypedDict):
    pending: Optional[Pending]
    last_race: Optional[dict]      # {year, round, grand_prix_name}
    greeted: bool

def _init_state_table():
    try:
        conn = sqlite3.connect(str(config.DB_PATH), timeout=10.0)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation_state (
                conv_key TEXT PRIMARY KEY,
                state_json TEXT,
                updated_at REAL
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Error initializing conversation_state table: {e}")

_init_state_table()

def get_conv_state(conversation_id: str, client_id: str = "default") -> ConvState:
    conv_key = f"{client_id}:{conversation_id}"
    try:
        conn = sqlite3.connect(str(config.DB_PATH), timeout=5.0)
        cur = conn.cursor()
        cur.execute("SELECT state_json FROM conversation_state WHERE conv_key = ?", (conv_key,))
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            data = json.loads(row[0])
            return {
                "pending": data.get("pending"),
                "last_race": data.get("last_race"),
                "greeted": data.get("greeted", False)
            }
    except Exception as e:
        logger.warning(f"Error reading conv_state for {conv_key}: {e}")

    return {
        "pending": None,
        "last_race": None,
        "greeted": False
    }

def save_conv_state(conversation_id: str, client_id: str, state: ConvState) -> None:
    conv_key = f"{client_id}:{conversation_id}"
    try:
        import time
        state_json = json.dumps(state)
        conn = sqlite3.connect(str(config.DB_PATH), timeout=5.0)
        conn.execute(
            "INSERT OR REPLACE INTO conversation_state (conv_key, state_json, updated_at) VALUES (?, ?, ?)",
            (conv_key, state_json, time.time())
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Error saving conv_state for {conv_key}: {e}")

def get_slot_display_name(slot: str) -> str:
    mapping = {
        "year": "Season",
        "grand_prix": "Race",
        "driver": "Driver",
        "driver_b": "Driver B",
        "kind": "Standings Type",
        "metric": "Metric",
    }
    return mapping.get(slot, slot.replace("_", " ").title())

def format_progress_line(intent: str, slots: dict, awaiting: str) -> str:
    """
    Progress line above chips shows human names:
    e.g. "Charles Leclerc > Strategy > 2026 > Race ?"
    Never "grand_prix". Slot names shown to users: Season, Race, Driver.
    """
    parts = []
    # Driver first if filled
    if slots.get("driver"):
        d_val = slots["driver"]
        parts.append(d_val.title())

    # Intent title
    intent_titles = {
        "driver_strategy": "Strategy",
        "pit_stops": "Pit Stops",
        "tyre_stints": "Tyre Stints",
        "tyre_degradation": "Tyre Degradation",
        "winner": "Winner",
        "race_result": "Race Result",
        "qualifying": "Qualifying",
        "standings": "Standings",
        "schedule": "Schedule",
        "champions": "Champions",
        "compare_drivers": "Comparison",
        "sector_analysis": "Sector Pace",
        "lap_times": "Lap Times",
    }
    parts.append(intent_titles.get(intent, intent.replace("_", " ").title()))

    # Year if filled
    if slots.get("year"):
        parts.append(str(slots["year"]))

    # Grand Prix if filled
    if slots.get("grand_prix"):
        parts.append(str(slots["grand_prix"]).title())

    # Awaiting slot
    awaiting_display = get_slot_display_name(awaiting)
    parts.append(f"{awaiting_display} ?")

    return " > ".join(parts)

def build_year_options() -> List[Dict[str, Any]]:
    """
    First chip of the year question is 'Latest completed race' (value 'latest').
    """
    cur_year = datetime.date.today().year
    opts = [
        {"label": "Latest completed race", "value": "latest", "action": "select"},
        {"label": str(cur_year), "value": str(cur_year), "action": "select"},
        {"label": str(cur_year - 1), "value": str(cur_year - 1), "action": "select"},
        {"label": str(cur_year - 2), "value": str(cur_year - 2), "action": "select"},
        {"label": str(cur_year - 3), "value": str(cur_year - 3), "action": "select"},
        {"label": str(cur_year - 4), "value": str(cur_year - 4), "action": "select"},
    ]
    return opts

def build_race_options(year: int, page: int = 0) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Race chips: up to 6 completed races per page, newest first, label 'R17 Singapore',
    built from the cached schedule of that year. 'More races' appears when more remain.
    If the schedule cannot be loaded, say 'Type the race name' and accept free text.
    """
    sched_res = tools.get_season_schedule(year)
    if sched_res.get("status") != "ok":
        return [], False

    schedule = sched_res.get("schedule", [])
    today = datetime.date.today().isoformat()
    # Filter completed races
    completed = [r for r in schedule if r.get("date", "") <= today]
    # If in the past season and none flagged with date <= today, all are completed
    if not completed and year < datetime.date.today().year:
        completed = list(schedule)

    # Sort newest first (highest round number first)
    completed.sort(key=lambda x: x.get("round", 0), reverse=True)

    page_size = 6
    start_idx = page * page_size
    end_idx = start_idx + page_size
    page_races = completed[start_idx:end_idx]

    options = []
    for r in page_races:
        rnd = r.get("round")
        race_name = r.get("grand_prix") or r.get("race_name") or ""
        if not rnd or not race_name:
            continue
        options.append({
            "label": f"R{rnd} {race_name}",
            "value": race_name,
            "round": int(rnd),
            "action": "select"
        })

    has_more = end_idx < len(completed)
    if has_more:
        options.append({
            "label": "More races",
            "value": "more_races",
            "action": "page_more"
        })

    return options, has_more
