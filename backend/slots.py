import datetime
import logging
import re
from typing import Dict, Any, List, Optional, Tuple, Union
from rapidfuzz import fuzz, process

try:
    from backend import resolver, tools, cache
    from backend.sources import jolpica
except ImportError:
    import resolver, tools, cache
    from sources import jolpica

logger = logging.getLogger("slots")

# INTENT DEFINITIONS AND REQUIRED SLOTS
# driver_strategy / tyre_stints / pit_stops : driver, year, grand_prix
# tyre_degradation / sector_analysis / lap_times : driver, year, grand_prix
# compare_drivers : driver_a, driver_b, year, grand_prix
# race_result / winner / qualifying / race_control / weather : year, grand_prix
# standings : year, kind (drivers or constructors)
# champions : none (optional start_year, end_year)
# driver_profile : driver
# team_history : team
# circuit_info : grand_prix or circuit (no year)
# career_records : metric (optional)
# schedule : year

INTENT_REQUIRED_SLOTS: Dict[str, List[str]] = {
    "driver_strategy": ["driver", "year", "grand_prix"],
    "tyre_stints": ["driver", "year", "grand_prix"],
    "pit_stops": ["grand_prix", "year"],  # user can ask for race pit stops, driver optional
    "pit_stops_driver": ["driver", "year", "grand_prix"],
    "tyre_degradation": ["driver", "year", "grand_prix"],
    "sector_analysis": ["driver", "year", "grand_prix"],
    "lap_times": ["driver", "year", "grand_prix"],
    "compare_drivers": ["driver_a", "driver_b", "year", "grand_prix"],
    "race_result": ["year", "grand_prix"],
    "winner": ["year", "grand_prix"],
    "qualifying": ["year", "grand_prix"],
    "race_control": ["year", "grand_prix"],
    "weather": ["year", "grand_prix"],
    "standings": ["year", "kind"],
    "champions": [],
    "driver_profile": ["driver"],
    "team_history": ["team"],
    "circuit_info": ["circuit_or_gp"],
    "career_records": [],
    "schedule": ["year"],
    "unknown": [],
}

# Slot priority order: ask the most limiting missing slot first
# year is generally asked before grand_prix; driver before race; etc.
SLOT_PRIORITY: Dict[str, int] = {
    "driver": 1,
    "driver_a": 1,
    "driver_b": 2,
    "year": 3,
    "grand_prix": 4,
    "kind": 5,
    "circuit_or_gp": 1,
    "team": 1,
}

def get_current_year() -> int:
    return datetime.date.today().year

def is_context_reuse_phrase(text: str) -> bool:
    cleaned = text.strip().lower()
    phrases = ["that race", "same race", "there", "same weekend", "in that race", "at that race"]
    return any(p in cleaned for p in phrases)

def detect_intent(text: str) -> Tuple[str, float]:
    """
    Classifies the user query into an intent using keyword and pattern matching.
    Returns (intent_name, confidence).
    """
    q = text.lower().strip()

    # Compare drivers
    if ("compare" in q or " vs " in q or " versus " in q) and any(w in q for w in ["tyre", "deg", "degradation", "pace", "lap", "telemetry"]):
        return "compare_drivers", 95.0

    # Tyre degradation
    if any(w in q for w in ["tyre degradation", "tire degradation", "degradation", "deg", "tyre wear", "tire wear"]):
        return "tyre_degradation", 95.0

    # Sector analysis
    if any(w in q for w in ["sector", "s1", "s2", "s3", "sector pace", "sectors"]):
        return "sector_analysis", 95.0

    # Lap times
    if any(w in q for w in ["lap time", "lap times", "fastest lap", "laps"]):
        if "fastest lap" in q and not any(k in q for k in ["compare", "stint", "strategy"]):
            # could be part of race result or lap times
            pass
        else:
            return "lap_times", 90.0

    # Strategy / stints
    if "strategy" in q:
        return "driver_strategy", 95.0
    if "stint" in q or "stints" in q or "compound" in q or "compounds" in q:
        return "tyre_stints", 95.0

    # Pit stops
    if "pit stop" in q or "pitstop" in q or "pit stops" in q or "pitstops" in q or "pitted" in q or "stops" in q:
        return "pit_stops", 95.0

    # Winner / Won
    if re.search(r"\b(who won|winner of|race winner|won the|won)\b", q):
        return "winner", 95.0

    # Qualifying
    if any(w in q for w in ["qualifying", "pole position", "quali", "pole"]):
        return "qualifying", 95.0

    # Standings
    if any(w in q for w in ["standing", "standings", "leaderboard", "points table", "championship points"]):
        return "standings", 95.0

    # Champions
    if any(w in q for w in ["champions", "champion", "world champion", "title winners", "wdf", "wcc"]):
        return "champions", 95.0

    # Race control / safety car
    if any(w in q for w in ["safety car", "vsc", "virtual safety car", "red flag", "penalties", "race control"]):
        return "race_control", 95.0

    # Weather
    if any(w in q for w in ["weather", "rain", "temperature", "track temp", "wet race"]):
        return "weather", 95.0

    # Circuit info
    if any(w in q for w in ["which circuit", "what circuit", "circuit hosts", "circuit info", "track info", "where is"]):
        return "circuit_info", 95.0

    # Schedule / Calendar
    if any(w in q for w in ["schedule", "calendar", "races this year", "next race"]):
        return "schedule", 90.0

    # Driver profile / career records
    if any(w in q for w in ["career", "profile", "bio", "how many wins", "career wins", "world titles", "wins", "titles", "records", "stats"]):
        return "driver_profile", 85.0

    # Team history
    if any(w in q for w in ["team history", "constructor history"]):
        return "team_history", 90.0

    # Race result fallback
    if any(w in q for w in ["race result", "results", "finish", "finished", "classification", "grand prix", "gp"]):
        return "race_result", 85.0

    # Conversational or unknown input
    if any(w in q for w in ["hello", "hi", "hey", "help", "who are you", "what can you do"]):
        return "unknown", 95.0

    return "unknown", 0.0

def extract_slots_from_text(text: str, intent: Optional[str] = None) -> Dict[str, Any]:
    """
    Extracts slots (year, grand_prix, driver, driver_a, driver_b, kind, circuit_or_gp)
    from plain text using rapidfuzz and regex.
    """
    slots: Dict[str, Any] = {}
    if intent == "unknown":
        return slots

    current_year = get_current_year()

    # 1. Year extraction: e.g. 2024, '23, 1998, or "last year", "this year"
    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", text)
    if year_match:
        slots["year"] = int(year_match.group(1))
    else:
        q_lower = text.lower()
        if "last year" in q_lower:
            slots["year"] = current_year - 1
        elif "this year" in q_lower or "current year" in q_lower or "current season" in q_lower:
            slots["year"] = current_year

    # 2. Kind extraction for standings
    if intent == "standings" or "standing" in text.lower():
        if "constructor" in text.lower() or "team" in text.lower():
            slots["kind"] = "constructors"
        elif "driver" in text.lower():
            slots["kind"] = "drivers"

    # 3. Circuit extraction for circuit_info
    if intent == "circuit_info" or any(w in text.lower() for w in ["which circuit", "what circuit", "circuit hosts"]):
        # Match circuit or GP name from text
        gp_match = re.search(r"(?:hosts?\s+(?:the\s+)?|for\s+(?:the\s+)?)([a-zA-Z\s]+?)(?:\s+grand\s+prix|\s+gp|\?|$)", text, re.IGNORECASE)
        if gp_match:
            candidate = gp_match.group(1).strip()
            if candidate:
                slots["circuit_or_gp"] = candidate
        if not slots.get("circuit_or_gp"):
            for known_name in ["belgian", "italian", "british", "monaco", "spa", "monza", "silverstone", "bahrain", "suzuka", "zandvoort"]:
                if known_name in text.lower():
                    slots["circuit_or_gp"] = known_name
                    break

    # 4. Compare drivers: look for "X and Y" or "X vs Y"
    if intent == "compare_drivers" or (" vs " in text.lower() or " and " in text.lower()):
        m = re.search(r"compare\s+([a-zA-Z]+)\s+(?:and|vs\.?)\s+([a-zA-Z]+)", text, re.IGNORECASE)
        if m:
            d1_res = resolver.resolve_driver(m.group(1))
            d2_res = resolver.resolve_driver(m.group(2))
            if d1_res.get("status") == "ok":
                slots["driver_a"] = d1_res["driver_id"]
                slots["driver_a_name"] = d1_res["name"]
            if d2_res.get("status") == "ok":
                slots["driver_b"] = d2_res["driver_id"]
                slots["driver_b_name"] = d2_res["name"]

    # 5. Single driver extraction
    if "driver" not in slots and "driver_a" not in slots:
        # Check known aliases in query
        words = re.findall(r"\b[A-Za-z]+\b", text)
        for w in words:
            wl = w.lower()
            if wl in ["f1", "race", "strategy", "won", "who", "show", "tell", "compare", "degradation", "pit", "stops", "the", "at", "in", "year", "round", "driver", "which", "hosts", "monaco", "monza", "spa", "silverstone", "bahrain"]:
                continue
            res = resolver.resolve_driver(w)
            if res.get("status") == "ok":
                slots["driver"] = res["driver_id"]
                slots["driver_name"] = res["name"]
                slots["driver_code"] = res.get("code")
                break
            elif res.get("status") == "ambiguous":
                # Special handling for Schumacher etc.
                slots["driver"] = "ambiguous"
                slots["driver_ambiguous_name"] = w
                slots["driver_candidates"] = res.get("candidates", [])
                break

    # 6. Grand Prix extraction
    # Check known track / GP names
    known_gps = [
        ("bahrain", "Bahrain"), ("saudi", "Saudi Arabian"), ("australia", "Australian"),
        ("melbourne", "Australian"), ("japan", "Japanese"), ("suzuka", "Japanese"),
        ("china", "Chinese"), ("shanghai", "Chinese"), ("miami", "Miami"),
        ("emilia", "Emilia Romagna"), ("imola", "Emilia Romagna"), ("monaco", "Monaco"),
        ("canada", "Canadian"), ("montreal", "Canadian"), ("spain", "Spanish"),
        ("barcelona", "Spanish"), ("austria", "Austrian"), ("spielberg", "Austrian"),
        ("red bull ring", "Austrian"), ("britain", "British"), ("british", "British"),
        ("silverstone", "British"), ("hungary", "Hungarian"), ("hungaroring", "Hungarian"),
        ("belgium", "Belgian"), ("belgian", "Belgian"), ("spa", "Belgian"),
        ("netherlands", "Dutch"), ("dutch", "Dutch"), ("zandvoort", "Dutch"),
        ("italy", "Italian"), ("italian", "Italian"), ("monza", "Italian"),
        ("baku", "Azerbaijan"), ("azerbaijan", "Azerbaijan"), ("singapore", "Singapore"),
        ("united states", "United States"), ("cota", "United States"), ("austin", "United States"),
        ("mexico", "Mexico City"), ("brazil", "São Paulo"), ("interlagos", "São Paulo"),
        ("las vegas", "Las Vegas"), ("qatar", "Qatar"), ("losail", "Qatar"),
        ("abu dhabi", "Abu Dhabi"), ("yas marina", "Abu Dhabi")
    ]
    t_lower = text.lower()
    for trigger, gp_name in known_gps:
        if trigger in t_lower:
            slots["grand_prix"] = gp_name
            break

    return slots

def get_year_options(intent: str) -> List[Dict[str, Any]]:
    """
    Builds year chips:
    FastF1-based: 2018 to current server year.
    Results/standings: recent years back from current server year.
    Mark season still running as "(in progress)".
    Always include a chip "Latest completed race" (value: "latest").
    """
    current_year = get_current_year()
    is_fastf1 = intent in ["driver_strategy", "tyre_stints", "tyre_degradation", "sector_analysis", "lap_times", "compare_drivers"]
    start_year = 2018 if is_fastf1 else max(1950, current_year - 5)

    options: List[Dict[str, Any]] = []
    # Newest years first
    for y in range(current_year, start_year - 1, -1):
        label = str(y)
        if y == current_year:
            label += " (in progress)"
        options.append({"label": label, "value": y})

    # Add Latest completed race chip
    options.append({"label": "Latest completed race", "value": "latest"})
    return options[:6]

def get_grand_prix_options(year: int, page: int = 0, page_size: int = 5) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Returns that year's schedule, completed rounds only, newest first.
    Shows the first 5 or 6 as chips, plus 'More races' if more exist.
    Returns (options, has_more).
    """
    sched_res = tools.get_season_schedule(year)
    today = datetime.date.today().isoformat()
    races = []
    if sched_res.get("status") == "ok":
        raw_races = sched_res.get("schedule", [])
        # Filter to completed or past races if date <= today
        for r in raw_races:
            r_date = r.get("date", "")
            if not r_date or r_date <= today:
                races.append(r)
        if not races and raw_races:
            # If current year has no completed races yet or early in season, take what exists
            races = raw_races

    # Newest first
    races.reverse()

    start_idx = page * page_size
    end_idx = start_idx + page_size
    sliced = races[start_idx:end_idx]
    has_more = end_idx < len(races)

    options: List[Dict[str, Any]] = []
    for r in sliced:
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

    if has_more:
        options.append({"label": "More races", "value": "MORE_RACES", "page": page + 1})

    return options, has_more

def get_driver_options(year: Optional[int] = None, grand_prix: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Returns candidate drivers from that race's entry list if year and race known,
    or top drivers from that season.
    """
    options: List[Dict[str, Any]] = []
    if year and grand_prix:
        try:
            res = tools.get_race_result(year, grand_prix)
            if res.get("status") == "ok":
                for row in res.get("results", [])[:6]:
                    options.append({
                        "label": f"{row.get('driver')} ({row.get('constructor')})",
                        "value": row.get("driver")
                    })
                if options:
                    return options
        except Exception:
            pass

    # Fallback to key current/recent drivers
    recent_drivers = [
        {"label": "Max Verstappen", "value": "Verstappen"},
        {"label": "Lewis Hamilton", "value": "Hamilton"},
        {"label": "Lando Norris", "value": "Norris"},
        {"label": "Charles Leclerc", "value": "Leclerc"},
        {"label": "Fernando Alonso", "value": "Alonso"},
        {"label": "Oscar Piastri", "value": "Piastri"},
    ]
    return recent_drivers

def get_ambiguous_driver_options(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    options = []
    for c in candidates:
        name = c.get("name", "")
        # Add years active info
        if "Michael" in name:
            label = "Michael Schumacher (1991-2012)"
        elif "Ralf" in name:
            label = "Ralf Schumacher (1997-2007)"
        elif "Mick" in name:
            label = "Mick Schumacher (2021-2022)"
        else:
            label = name
        options.append({"label": label, "value": name})
    return options

def check_early_honesty(intent: str, slots: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Rule: Early honesty at the first slot that makes the intent impossible.
    1. If chosen year is before 2018 and the intent needs lap or tyre data:
       "Detailed tyre and lap data starts in 2018. For <year> I can show the race result,
        qualifying and pit stops (from 2012)." and offer those as chips.
    2. If the race is in the future:
       say it has not happened yet and offer the latest race.
    """
    year = slots.get("year")
    current_year = get_current_year()

    # Future race check
    if year is not None and year > current_year:
        return {
            "type": "coverage_limit",
            "message": f"Season {year} has not happened yet.",
            "options": [{"label": "Latest completed race", "value": "latest"}],
            "followups": [{"label": "Latest completed race", "value": "latest"}]
        }

    # Pre-2018 FastF1 check
    is_fastf1_intent = intent in ["driver_strategy", "tyre_stints", "tyre_degradation", "sector_analysis", "lap_times", "compare_drivers"]
    if is_fastf1_intent and year is not None and year < 2018:
        alt_options = [
            {"label": "Race Result", "intent": "race_result"},
            {"label": "Qualifying", "intent": "qualifying"}
        ]
        if year >= 2012:
            alt_options.append({"label": "Pit Stops", "intent": "pit_stops"})
        return {
            "type": "coverage_limit",
            "message": f"Detailed tyre and lap data starts in 2018. For {year} I can show the race result, qualifying and pit stops (from 2012).",
            "options": alt_options,
            "followups": alt_options
        }

    return None

def build_clarify_turn(
    intent: str,
    filled_slots: Dict[str, Any],
    awaiting_slot: str,
    page: int = 0
) -> Dict[str, Any]:
    """
    Builds the clarify response with 3 to 6 tappable options built from real data,
    plus free-text option.
    Clarify text style (short, human):
      "Which season should I look at for Alonso's strategy?"
      "Which race in 2024?"
    Show a small progress line above the chips: "Alonso > strategy > 2024 > race ?"
    Target: Under 100ms, NO LLM, NO uncached tools.
    """
    driver_name = filled_slots.get("driver_name") or filled_slots.get("driver") or ""
    year = filled_slots.get("year")
    grand_prix = filled_slots.get("grand_prix")

    # Build progress breadcrumb
    parts = []
    if driver_name:
        parts.append(driver_name.capitalize())
    clean_intent = intent.replace("driver_", "").replace("_", " ")
    parts.append(clean_intent)
    if year:
        parts.append(str(year))
    if grand_prix:
        parts.append(str(grand_prix))
    parts.append(f"{awaiting_slot} ?")
    progress_str = " > ".join(parts)

    options: List[Dict[str, Any]] = []
    question = ""

    if awaiting_slot == "year":
        if driver_name:
            question = f"Which season should I look at for {driver_name.capitalize()}'s {clean_intent}?"
        else:
            question = f"Which season should I check for the {clean_intent}?"
        options = get_year_options(intent)

    elif awaiting_slot == "grand_prix":
        if year:
            question = f"Which race in {year}?"
        else:
            question = "Which race should I look at?"
        options, _ = get_grand_prix_options(year or get_current_year(), page=page)

    elif awaiting_slot == "driver":
        if filled_slots.get("driver") == "ambiguous":
            candidates = filled_slots.get("driver_candidates", [])
            name = filled_slots.get("driver_ambiguous_name", "the driver")
            question = f"Which {name.capitalize()} did you mean?"
            options = get_ambiguous_driver_options(candidates)
        else:
            question = f"Which driver's {clean_intent} should I check?"
            options = get_driver_options(year, grand_prix)

    elif awaiting_slot == "kind":
        question = "Drivers or Constructors standings?"
        options = [
            {"label": "Drivers", "value": "drivers"},
            {"label": "Constructors", "value": "constructors"}
        ]

    elif awaiting_slot == "circuit_or_gp":
        question = "Which circuit or Grand Prix would you like information on?"
        options = [
            {"label": "Spa-Francorchamps", "value": "Spa"},
            {"label": "Monza", "value": "Monza"},
            {"label": "Silverstone", "value": "Silverstone"},
            {"label": "Monaco", "value": "Monaco"},
            {"label": "Bahrain", "value": "Bahrain"},
            {"label": "Suzuka", "value": "Suzuka"},
        ]

    elif awaiting_slot in ["race_or_driver", "driver_or_race"]:
        question = "Which race or driver's pit stops should I show?"
        options = [
            {"label": "Latest completed race", "value": "latest"},
            {"label": "Monza", "value": "Monza"},
            {"label": "Silverstone", "value": "Silverstone"},
            {"label": "Max Verstappen", "value": "Verstappen"},
            {"label": "Lewis Hamilton", "value": "Hamilton"},
            {"label": "Fernando Alonso", "value": "Alonso"},
        ]

    elif awaiting_slot == "team":
        question = "Which constructor or team?"
        options = [
            {"label": "Ferrari", "value": "Ferrari"},
            {"label": "McLaren", "value": "McLaren"},
            {"label": "Mercedes", "value": "Mercedes"},
            {"label": "Red Bull", "value": "Red Bull"},
            {"label": "Williams", "value": "Williams"},
            {"label": "Aston Martin", "value": "Aston Martin"},
        ]

    else:
        question = f"Please specify {awaiting_slot}."
        options = []

    return {
        "slot": awaiting_slot,
        "question": question,
        "options": options,
        "allow_text": True,
        "progress": progress_str
    }

def resolve_gp_name(text: str, year: Optional[int] = None) -> Optional[str]:
    """Resolves Grand Prix name from text against known GPs or schedule."""
    t_clean = text.strip().lower()
    known_gps = [
        ("bahrain", "Bahrain"), ("saudi", "Saudi Arabian"), ("australia", "Australian"),
        ("melbourne", "Australian"), ("japan", "Japanese"), ("suzuka", "Japanese"),
        ("china", "Chinese"), ("shanghai", "Chinese"), ("miami", "Miami"),
        ("emilia", "Emilia Romagna"), ("imola", "Emilia Romagna"), ("monaco", "Monaco"),
        ("canada", "Canadian"), ("montreal", "Canadian"), ("spain", "Spanish"),
        ("barcelona", "Spanish"), ("austria", "Austrian"), ("spielberg", "Austrian"),
        ("red bull ring", "Austrian"), ("britain", "British"), ("british", "British"),
        ("silverstone", "British"), ("hungary", "Hungarian"), ("hungaroring", "Hungarian"),
        ("belgium", "Belgian"), ("belgian", "Belgian"), ("spa", "Belgian"),
        ("netherlands", "Dutch"), ("dutch", "Dutch"), ("zandvoort", "Dutch"),
        ("italy", "Italian"), ("italian", "Italian"), ("monza", "Italian"),
        ("baku", "Azerbaijan"), ("azerbaijan", "Azerbaijan"), ("singapore", "Singapore"),
        ("united states", "United States"), ("cota", "United States"), ("austin", "United States"),
        ("mexico", "Mexico City"), ("brazil", "São Paulo"), ("interlagos", "São Paulo"),
        ("las vegas", "Las Vegas"), ("qatar", "Qatar"), ("losail", "Qatar"),
        ("abu dhabi", "Abu Dhabi"), ("yas marina", "Abu Dhabi")
    ]
    for trigger, gp in known_gps:
        if trigger in t_clean:
            return gp

    # Rapidfuzz against schedule if year available
    if year:
        sched = tools.get_season_schedule(year)
        if sched.get("status") == "ok":
            rounds = [r.get("grand_prix", "").replace(" Grand Prix", "") for r in sched.get("schedule", [])]
            match = process.extractOne(text, rounds, scorer=fuzz.ratio)
            if match and match[1] >= 65:
                return match[0]

    return None

def get_missing_slot(intent: str, filled_slots: Dict[str, Any]) -> Optional[str]:
    """Finds the most limiting missing slot first according to SLOT_PRIORITY."""
    if intent == "pit_stops":
        if not filled_slots.get("driver") and not filled_slots.get("grand_prix") and not filled_slots.get("race_or_driver"):
            return "race_or_driver"
        if not filled_slots.get("year"):
            return "year"
        if not filled_slots.get("grand_prix"):
            return "grand_prix"
        return None

    required = list(INTENT_REQUIRED_SLOTS.get(intent, []))
    missing = []
    for s in required:
        val = filled_slots.get(s)
        if val is None or val == "" or val == "ambiguous":
            missing.append(s)

    if not missing:
        return None

    missing.sort(key=lambda s: SLOT_PRIORITY.get(s, 10))
    return missing[0]

def merge_pending_answer(
    pending_state: Dict[str, Any],
    user_text: str
) -> Tuple[Optional[Dict[str, Any]], bool]:
    """
    Merges user response into pending state.
    Returns (updated_pending_state, is_matched).
    If user_text is a cancel or unrelated question, is_matched is False.
    """
    if not pending_state:
        return None, False

    clean_text = user_text.strip()
    clean_lower = clean_text.lower()

    if clean_lower in ["cancel", "stop", "nevermind", "exit", "clear"]:
        return None, True

    # Early check: if the user asked a new question or command, drop pending state
    new_intent, conf = detect_intent(clean_text)
    is_new_question = (
        (conf >= 70.0 and new_intent != "unknown" and new_intent != pending_state.get("intent"))
        or any(clean_lower.startswith(w) for w in ["who ", "which ", "what ", "where ", "when ", "how ", "tell ", "show ", "compare ", "standings ", "schedule "])
        or any(w in clean_lower for w in ["who won", "standings", "schedule", "circuit", "compare", "strategy", "qualifying", "pole", "weather", "hello", "hi ", "hey"])
    )
    if is_new_question:
        return None, False

    awaiting_slot = pending_state.get("awaiting_slot")
    filled_slots = dict(pending_state.get("filled_slots", {}))
    intent = pending_state.get("intent", "driver_strategy")
    current_year = get_current_year()

    # 1. Year slot
    if awaiting_slot == "year":
        if clean_lower in ["last year", "previous year", "last season", "previous season"]:
            filled_slots["year"] = current_year - 1
            return {"intent": intent, "filled_slots": filled_slots, "awaiting_slot": get_missing_slot(intent, filled_slots)}, True
        if clean_lower in ["this year", "current year", "this season", "current season"]:
            filled_slots["year"] = current_year
            return {"intent": intent, "filled_slots": filled_slots, "awaiting_slot": get_missing_slot(intent, filled_slots)}, True
        if clean_lower == "latest":
            filled_slots["year"] = current_year
            return {"intent": intent, "filled_slots": filled_slots, "awaiting_slot": get_missing_slot(intent, filled_slots)}, True
        m = re.search(r"\b(19\d{2}|20\d{2})\b", clean_text)
        if m:
            filled_slots["year"] = int(m.group(1))
            return {"intent": intent, "filled_slots": filled_slots, "awaiting_slot": get_missing_slot(intent, filled_slots)}, True
        try:
            val = int(clean_text)
            if 1950 <= val <= current_year + 10:
                filled_slots["year"] = val
                return {"intent": intent, "filled_slots": filled_slots, "awaiting_slot": get_missing_slot(intent, filled_slots)}, True
        except ValueError:
            pass

    # 2. Grand Prix slot
    elif awaiting_slot == "grand_prix":
        if clean_lower == "latest":
            # Resolve to latest completed race of that year
            y = filled_slots.get("year", current_year)
            sched_res = tools.get_season_schedule(y)
            if sched_res.get("status") == "ok":
                races = sched_res.get("schedule", [])
                if races:
                    filled_slots["grand_prix"] = races[-1].get("grand_prix", "").replace(" Grand Prix", "")
                    return {"intent": intent, "filled_slots": filled_slots, "awaiting_slot": get_missing_slot(intent, filled_slots)}, True
            filled_slots["grand_prix"] = "Bahrain"
            return {"intent": intent, "filled_slots": filled_slots, "awaiting_slot": get_missing_slot(intent, filled_slots)}, True

        gp_name = resolve_gp_name(clean_text, year=filled_slots.get("year"))
        if gp_name:
            filled_slots["grand_prix"] = gp_name
            return {"intent": intent, "filled_slots": filled_slots, "awaiting_slot": get_missing_slot(intent, filled_slots)}, True

    # 3. Driver slot
    elif awaiting_slot in ["driver", "driver_a", "driver_b"]:
        d_res = resolver.resolve_driver(clean_text, year=filled_slots.get("year"))
        if d_res.get("status") == "ok":
            filled_slots[awaiting_slot] = d_res["driver_id"]
            filled_slots[f"{awaiting_slot}_name"] = d_res["name"]
            filled_slots[f"{awaiting_slot}_code"] = d_res.get("code")
            return {"intent": intent, "filled_slots": filled_slots, "awaiting_slot": get_missing_slot(intent, filled_slots)}, True

    # 4. Standings kind slot
    elif awaiting_slot == "kind":
        if "construct" in clean_lower or "team" in clean_lower:
            filled_slots["kind"] = "constructors"
            return {"intent": intent, "filled_slots": filled_slots, "awaiting_slot": get_missing_slot(intent, filled_slots)}, True
        if "driver" in clean_lower:
            filled_slots["kind"] = "drivers"
            return {"intent": intent, "filled_slots": filled_slots, "awaiting_slot": get_missing_slot(intent, filled_slots)}, True

    # 5. Race or Driver slot (for pit stops)
    elif awaiting_slot in ["race_or_driver", "driver_or_race"]:
        # Check if driver
        d_res = resolver.resolve_driver(clean_text, year=filled_slots.get("year"))
        if d_res.get("status") == "ok":
            filled_slots["driver"] = d_res["driver_id"]
            filled_slots["driver_name"] = d_res["name"]
            return {"intent": intent, "filled_slots": filled_slots, "awaiting_slot": get_missing_slot(intent, filled_slots)}, True
        # Check if GP
        if clean_lower == "latest":
            filled_slots["grand_prix"] = "latest"
            return {"intent": intent, "filled_slots": filled_slots, "awaiting_slot": get_missing_slot(intent, filled_slots)}, True
        gp_name = resolve_gp_name(clean_text, year=filled_slots.get("year"))
        if gp_name:
            filled_slots["grand_prix"] = gp_name
            return {"intent": intent, "filled_slots": filled_slots, "awaiting_slot": get_missing_slot(intent, filled_slots)}, True

    # 6. Circuit or GP slot
    elif awaiting_slot == "circuit_or_gp":
        filled_slots["circuit_or_gp"] = clean_text
        return {"intent": intent, "filled_slots": filled_slots, "awaiting_slot": get_missing_slot(intent, filled_slots)}, True

    # Check if this looks like a completely new question
    new_intent, conf = detect_intent(clean_text)
    if conf >= 80.0 or any(w in clean_lower for w in ["who won", "standings", "schedule", "circuit", "compare", "strategy"]):
        return None, False

    return None, False
