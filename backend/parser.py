import datetime
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from rapidfuzz import fuzz, process

try:
    from backend import resolver, cache
except ImportError:
    import resolver, cache

logger = logging.getLogger("parser")

INTENT_REQUIRED_SLOTS: Dict[str, List[str]] = {
    "driver_strategy": ["driver", "year", "grand_prix"],
    "pit_stops": ["grand_prix", "year"],
    "tyre_stints": ["driver", "year", "grand_prix"],
    "tyre_degradation": ["driver", "year", "grand_prix"],
    "winner": ["grand_prix", "year"],
    "race_result": ["grand_prix", "year"],
    "qualifying": ["grand_prix", "year"],
    "standings": ["year", "kind"],
    "champions": ["year"],
    "circuit_info": ["grand_prix"],
    "schedule": ["year"],
    "driver_profile": ["driver"],
    "multi_metric": ["driver"],
    "team_history": ["team"],
    "career_records": [],
    "subjective": [],
    "compare_drivers": ["driver", "driver_b", "year", "grand_prix"],
    "sector_analysis": ["driver", "year", "grand_prix"],
    "lap_times": ["driver", "year", "grand_prix"],
    "race_control": ["grand_prix", "year"],
    "weather": ["grand_prix", "year"],
    "live": [],
    "smalltalk": [],
    "out_of_scope": [],
    "unknown": [],
}

COMMON_DRIVERS = [
    "alonso", "hamilton", "leclerc", "verstappen", "norris", "piastri",
    "russell", "sainz", "perez", "bottas", "gasly", "tsunoda", "ocon",
    "albon", "hulkenberg", "magnussen", "ricciardo", "stroll", "zhou",
    "vettel", "raikkonen", "schumacher", "massa", "button", "rosberg",
    "barrichello", "webber", "coulthard", "montoya", "fisichella", "trulli",
    "heidfeld", "kubica", "latifi", "mazepin", "giovinazzi", "sargeant", "de vries", "lawson", "bearman", "colapinto", "antonelli"
]

NON_GP_WORDS = {
    "race", "races", "calendar", "schedule", "right", "now", "next", "year", "driver",
    "drivers", "strategy", "strategies", "the", "for", "who", "won", "winner", "result",
    "results", "grid", "pole", "qualifying", "quali", "tell", "about", "history", "pit",
    "stop", "stops", "stint", "stints", "fastest", "lap", "laps", "most", "points", "standing",
    "standings", "weather", "rain", "temperature", "speed", "sector", "sectors", "ever",
    "best", "greatest", "goat", "red", "flag", "safety", "car", "vsc", "live", "timing", "did",
    "make", "at", "in", "of", "and", "vs", "versus", "compare", "degradation", "deg", "explain",
    "recipe", "pizza", "will", "is", "there", "on"
}

def normalize_text(text: str) -> str:
    """
    Normalise: lowercase, strip punctuation, collapse repeated letters ("strategyy"),
    split glued words by fuzzy-matching a driver at the start ("leclercrrace" -> "leclerc race"),
    stem plurals (strategies -> strategy, stops -> stop, stints -> stint). "tire" == "tyre".
    """
    if not text:
        return ""
    q = text.lower().strip()

    # Tire == tyre
    q = re.sub(r"\btires\b", "tyres", q)
    q = re.sub(r"\btire\b", "tyre", q)

    # Strip punctuation except hyphens inside words or ranges
    q = re.sub(r"[?!.,;:()\[\]\"']", " ", q)
    q = re.sub(r"\s+", " ", q).strip()

    # Collapse repeated letters (3+ of any char)
    q = re.sub(r"([a-z])\1{2,}", r"\1", q)
    # Specific common repeats at word ends or typos
    q = re.sub(r"\bstrategyy+\b", "strategy", q)

    # Split glued words: fuzzy-match a driver at the start
    words = q.split()
    split_words = []
    for w in words:
        glued_found = False
        for d in COMMON_DRIVERS:
            if w.startswith(d) and len(w) > len(d) + 2:
                remainder = w[len(d):]
                remainder_clean = re.sub(r"^([a-z])\1+", r"\1", remainder)
                split_words.append(d)
                split_words.append(remainder_clean)
                glued_found = True
                break
        if not glued_found:
            split_words.append(w)
    q = " ".join(split_words)

    # Stem plurals
    q = re.sub(r"\bstrategies\b", "strategy", q)
    q = re.sub(r"\bstops\b", "stop", q)
    q = re.sub(r"\bstints\b", "stint", q)
    q = re.sub(r"\bcompounds\b", "compound", q)

    return q.strip()

def detect_intent(text: str) -> Tuple[str, float]:
    """
    Detect intent from normalized text.
    Returns (intent_name, confidence).
    """
    q = normalize_text(text)

    # Smalltalk
    if q in ["hello", "hi", "hii", "hey", "help", "what can you do"]:
        return "smalltalk", 99.0
    if q in ["thanks", "thank you", "thx"]:
        return "smalltalk", 99.0

    # Out of scope
    if any(p in q for p in ["pizza", "recipe", "cook", "stock market"]):
        return "out_of_scope", 99.0
    if "who will win" in q or "predict" in q or "who is going to win" in q:
        return "out_of_scope", 95.0

    # Live timing
    if any(p in q for p in ["live timing", "right now", "current session", "race on right now", "is there a race on"]):
        return "live", 95.0

    # Race control
    if any(p in q for p in ["safety car", "safety cars", "vsc", "virtual safety car", "red flag", "penalty", "penalties", "investigation", "investigations"]):
        return "race_control", 95.0

    # Weather (use word boundary for rain to avoid bahrain)
    if any(p in q for p in ["weather", "raining", "temperature", "wet track"]) or re.search(r"\brain\b", q):
        return "weather", 95.0

    # Compare drivers
    if "compare" in q or " vs " in q or " versus " in q:
        return "compare_drivers", 95.0

    # Sector analysis
    if any(p in q for p in ["sector", "sectors", "s1", "s2", "s3"]):
        return "sector_analysis", 95.0

    # Lap times
    if ("lap time" in q or "lap times" in q or "lap by lap" in q or re.search(r"\blaps?\b", q)) and not any(k in q for k in ["fastest lap", "most", "who won", "winner", "result", "strategy", "stint", "stop"]):
        return "lap_times", 90.0

    # Tyre degradation
    if any(p in q for p in ["degradation", "deg", "tyre wear", "tire wear", "tyre life", "tire life"]):
        return "tyre_degradation", 95.0

    # Tyre stints
    if "stint" in q or "tyre sequence" in q or "tire sequence" in q:
        return "tyre_stints", 95.0

    # Pit stops
    if any(p in q for p in ["pit stop", "pit stops", "how many stop", "box", "pits", "show me the pit stop"]) and "strategy" not in q:
        return "pit_stops", 95.0

    # Driver strategy
    if any(p in q for p in ["strategy", "strat", "pit plan", "tyre strategy", "race strategy", "compound"]):
        return "driver_strategy", 95.0

    # Multi-intent / multi-metric detection (Rule B2) - runs if driver/team and multiple metrics present
    has_podium = any(p in q for p in ["podium", "podiums"])
    has_standings = any(p in q for p in ["standing", "standings", "points table", "leaderboard"])
    has_wins = any(p in q for p in ["wins", "victories"]) and not any(p in q for p in ["who won", "winner"])
    has_poles = any(p in q for p in ["poles", "pole positions"])
    has_pits = any(p in q for p in ["pit stop", "pit stops"])
    has_stints = any(p in q for p in ["stints", "tyre stints"])

    metric_signals = sum([bool(has_podium), bool(has_standings), bool(has_wins), bool(has_poles), bool(has_pits), bool(has_stints)])
    if metric_signals >= 2:
        return "multi_metric", 96.0

    # Standings (must check championship positions / points table / standings before champions)
    if any(p in q for p in ["standing", "standings", "championship position", "championship positions", "points table", "leaderboard", "constructors standing", "drivers table", "who won the most races in"]):
        return "standings", 95.0

    # Champions
    if any(p in q for p in ["world champion", "world champions", "champions", "champion", "world title", "title winner", "title winners", "drivers championship", "constructors champion"]):
        return "champions", 95.0

    # Schedule / Calendar
    if any(p in q for p in ["calendar", "schedule", "rounds"]):
        return "schedule", 95.0

    # Circuit info
    if any(p in q for p in ["which circuit", "where is", "track", "venue", "hosts", "held", "tell me about spa"]):
        return "circuit_info", 95.0

    # Career records
    if any(p in q for p in ["most win", "most wins", "most pole", "most poles", "win rate leader", "win rate leaders", "in f1 history"]) and "in 20" not in q:
        return "career_records", 95.0

    # Subjective
    if any(p in q for p in ["best driver", "greatest driver", "greatest f1 driver", "goat", "fastest ever"]):
        return "subjective", 95.0

    # Driver profile
    if (any(p in q for p in ["tell me about", "career", "stats", "how many title"]) and not any(k in q for k in ["circuit", "spa", "monza"])) or (q in ["schumacher", "verstappen"]):
        return "driver_profile", 95.0

    # Team history
    if "history" in q and any(t in q for t in ["ferrari", "mclaren", "mercedes", "williams", "red bull", "team"]):
        return "team_history", 95.0

    # Winner
    if any(p in q for p in ["who won", "winner", "won"]):
        return "winner", 95.0

    # Qualifying
    if any(p in q for p in ["qualifying", "quali", "pole", "grid"]):
        return "qualifying", 95.0

    # Race result
    if any(p in q for p in ["result", "results", "podium", "finished", "classification", "fastest lap"]) or re.search(r"\b\w+\s+wins\b", q):
        return "race_result", 95.0

    # Bare entity checks (Rule B1)
    words = q.split()
    if len(words) <= 2:
        # Check driver
        for d in COMMON_DRIVERS:
            if q == d or (len(words) == 2 and (words[0] == "driver" or words[1] == "driver") and d in words):
                return "driver_profile", 95.0
        # Check team
        teams_list = ["ferrari", "mclaren", "mercedes", "williams", "red bull", "aston martin", "alpine", "haas", "sauber", "rb", "racing bulls"]
        for t in teams_list:
            if q == t or (len(words) == 2 and (words[0] == "team" or words[1] == "team") and t in q):
                return "team_history", 95.0
        # Check circuit
        circuits_list = ["monza", "spa", "silverstone", "monaco", "suzuka", "zandvoort", "imola", "interlagos", "melbourne"]
        for c in circuits_list:
            if q == c or (len(words) == 2 and (words[0] == "circuit" or words[1] == "circuit") and c in q):
                return "circuit_info", 95.0

    # Unknown
    return "unknown", 20.0

def extract_slots(text: str, intent: str) -> Dict[str, Any]:
    """
    Extracts all slots from text.
    """
    norm = normalize_text(text)
    slots: Dict[str, Any] = {}

    if intent in ["subjective", "out_of_scope", "smalltalk", "live", "unknown"]:
        return slots

    # 1. Year extraction
    m_range = re.search(r"\b(19\d\d|20\d\d)\s*(?:to|-)\s*(19\d\d|20\d\d)\b", norm)
    if m_range:
        slots["year"] = f"{m_range.group(1)}-{m_range.group(2)}"
    elif "last year" in norm:
        slots["year"] = "relative:-1"
    elif "last race" in norm or "latest race" in norm or "latest completed" in norm:
        slots["year"] = "latest"
    else:
        m_year = re.search(r"\b(19\d\d|20\d\d)\b", norm)
        if m_year:
            slots["year"] = m_year.group(1)

    # 2. Grand Prix extraction (skip for schedule, standings, champions, subjective, etc.)
    if intent not in ["schedule", "standings", "champions", "career_records"]:
        if "last race" in norm or "latest race" in norm or "latest completed" in norm:
            slots["grand_prix"] = "latest"
        else:
            gp_names = [
                "abu dhabi", "emilia romagna", "emilia-romagna", "las vegas", "united states",
                "saudi arabian", "mexico city", "monza", "spa-francorchamps", "spa", "silverstone",
                "monaco", "bahrain", "hungary", "hungaroring", "brazilian", "brazil", "suzuka",
                "japanese", "japan", "belgian", "belgium", "italian", "italy", "austrian", "austria",
                "british", "britain", "singapore", "baku", "azerbaijan", "miami", "cota", "austin",
                "mexico", "mexican", "canadian", "canada", "spanish", "spain", "catalunya", "barcelona",
                "zandvoort", "dutch", "melbourne", "australian", "australia", "jeddah", "saudi",
                "qatar", "lusail", "china", "chinese", "shanghai", "imola", "france", "french",
                "european", "europe", "german", "germany", "hockenheim", "nurburgring", "malaysian",
                "malaysia", "sepang", "turkish", "turkey", "istanbul", "russian", "russia", "sochi",
                "korean", "korea", "indian", "india", "portuguese", "portugal", "algarve", "portimao",
                "sakhir", "tuscan", "mugello", "eifel", "styrian"
            ]
            for gp in gp_names:
                if re.search(rf"\b{re.escape(gp)}\b", norm):
                    slots["grand_prix"] = "spa" if gp == "spa-francorchamps" else gp
                    break

            if "grand_prix" not in slots:
                m_gp = re.search(r"\b([a-z\s]+?)\s+(?:grand\s+prix|gp)\b", norm)
                if m_gp:
                    raw_gp = m_gp.group(1).strip()
                    words = [w for w in raw_gp.split() if w not in NON_GP_WORDS and not re.match(r"^\d+$", w)]
                    if words:
                        slots["grand_prix"] = " ".join(words)

            if "grand_prix" not in slots:
                # Fuzzy match only words not in NON_GP_WORDS
                for w in norm.split():
                    if w not in NON_GP_WORDS and len(w) >= 4:
                        match = process.extractOne(w, gp_names, scorer=fuzz.ratio, score_cutoff=85)
                        if match:
                            slots["grand_prix"] = match[0]
                            break

    # 3. Driver extraction
    driver_aliases = {
        "alonso": "alonso", "alonzo": "alonso",
        "hamilton": "hamilton", "hamiltn": "hamilton", "ham": "hamilton", "lewis": "hamilton",
        "leclerc": "leclerc", "charles": "leclerc",
        "verstappen": "verstappen", "max": "verstappen", "ver": "verstappen",
        "norris": "norris", "lando": "norris", "nor": "norris",
        "piastri": "piastri", "oscar": "piastri", "pia": "piastri",
        "schumacher": "schumacher", "mick": "schumacher", "michael": "schumacher", "ralf": "schumacher",
        "russell": "russell", "george": "russell",
        "sainz": "sainz", "carlos": "sainz",
        "perez": "perez", "checo": "perez",
        "bottas": "bottas", "gasly": "gasly", "tsunoda": "tsunoda",
        "ocon": "ocon", "albon": "albon", "hulkenberg": "hulkenberg",
        "antonelli": "antonelli", "kimi antonelli": "antonelli",
        "bearman": "bearman", "colapinto": "colapinto", "lawson": "lawson",
        "hadjar": "hadjar", "doohan": "doohan", "bortoleto": "bortoleto"
    }

    found_drivers = []
    # If "charles leclerc", map to leclerc
    if "charles leclerc" in norm:
        found_drivers.append("leclerc")
    elif "max verstappen" in norm:
        found_drivers.append("verstappen")
    else:
        for word in norm.split():
            if word in driver_aliases:
                d = driver_aliases[word]
                if d not in found_drivers:
                    found_drivers.append(d)
            elif word not in NON_GP_WORDS and len(word) >= 4:
                m = process.extractOne(word, list(driver_aliases.keys()), scorer=fuzz.ratio, score_cutoff=85)
                if m:
                    d = driver_aliases[m[0]]
                    if d not in found_drivers:
                        found_drivers.append(d)

    if intent == "compare_drivers":
        if len(found_drivers) >= 2:
            slots["driver"] = found_drivers[0]
            slots["driver_b"] = found_drivers[1]
        elif len(found_drivers) == 1:
            slots["driver"] = found_drivers[0]
    else:
        if found_drivers:
            slots["driver"] = found_drivers[0]

    # 4. Kind (drivers vs constructors)
    if any(k in norm for k in ["constructors", "constructor", "team standing", "team standings"]):
        slots["kind"] = "constructors"
    elif any(k in norm for k in ["drivers", "driver"]):
        slots["kind"] = "drivers"
    elif intent == "standings" and "who won the most races" in norm:
        slots["kind"] = "drivers"

    # 5. Metric
    if "most win" in norm or "most wins" in norm or "win rate" in norm:
        slots["metric"] = "win_rate" if "win rate" in norm else "wins"
    elif "most pole" in norm or "most poles" in norm:
        slots["metric"] = "poles"

    # 6. Topic
    if "fastest lap" in norm:
        slots["topic"] = "fastest_lap"
    elif "most races" in norm or ("who won the most" in norm and intent == "standings"):
        slots["topic"] = "wins"
    elif intent == "compare_drivers":
        if any(w in norm for w in ["tyre degradation", "degradation", "deg"]):
            slots["topic"] = "tyre_degradation"
        elif "qualifying" in norm or "quali" in norm:
            slots["topic"] = "qualifying"

    # 7. Team
    if "ferrari" in norm:
        slots["team"] = "ferrari"
    elif "mclaren" in norm:
        slots["team"] = "mclaren"
    elif "mercedes" in norm:
        slots["team"] = "mercedes"
    elif "red bull" in norm:
        slots["team"] = "red_bull"
    elif "williams" in norm:
        slots["team"] = "williams"

    # 8. Multi-metric (Rule B2)
    if intent == "multi_metric":
        metrics = []
        if any(p in norm for p in ["podium", "podiums"]):
            metrics.append("podiums")
        if any(p in norm for p in ["standing", "standings", "points table", "leaderboard"]):
            metrics.append("standings")
        if any(p in norm for p in ["wins", "victories"]):
            metrics.append("wins")
        if any(p in norm for p in ["poles", "pole positions"]):
            metrics.append("poles")
        slots["metrics"] = metrics

    return slots

def get_missing_slots(intent: str, slots: Dict[str, Any], raw_text: str = "") -> List[str]:
    """
    Computes the missing slots the bot must ask for, in priority order.
    """
    norm = normalize_text(raw_text)

    if intent == "multi_metric":
        if "driver" not in slots:
            return ["driver"]
        return []

    if intent == "driver_strategy":
        missing = []
        if "driver" not in slots:
            missing.append("driver")
        if "year" not in slots:
            missing.append("year")
        if "grand_prix" not in slots:
            missing.append("grand_prix")
        return missing

    if intent == "pit_stops":
        missing = []
        if "year" not in slots and "grand_prix" not in slots:
            return ["year", "grand_prix"]
        if "year" not in slots:
            missing.append("year")
        if "grand_prix" not in slots:
            missing.append("grand_prix")
        return missing

    if intent == "tyre_stints":
        missing = []
        if "driver" not in slots and "year" not in slots and "grand_prix" not in slots:
            return ["year", "grand_prix"]
        if "year" not in slots:
            missing.append("year")
        if "grand_prix" not in slots:
            missing.append("grand_prix")
        return missing

    if intent == "winner":
        missing = []
        if "grand_prix" in slots and "year" not in slots:
            return ["year"]
        if "year" not in slots:
            missing.append("year")
        if "grand_prix" not in slots:
            missing.append("grand_prix")
        return missing

    if intent == "standings":
        if "year" not in slots and "kind" not in slots:
            return ["year", "kind"]
        if "year" not in slots:
            return ["year"]
        if "kind" not in slots:
            return ["kind"]
        return []

    if intent == "schedule":
        if "year" not in slots:
            return ["year"]
        return []

    if intent == "compare_drivers":
        missing = []
        if "year" not in slots:
            missing.append("year")
        if "grand_prix" not in slots:
            missing.append("grand_prix")
        return missing

    if intent == "sector_analysis":
        missing = []
        if "year" not in slots:
            missing.append("year")
        if "grand_prix" not in slots:
            missing.append("grand_prix")
        return missing

    if intent == "race_result":
        missing = []
        driver = slots.get("driver", "")
        has_first_name = any(fn in norm for fn in ["max", "jos", "michael", "ralf", "mick"]) or " " in driver or "_" in driver
        if driver in ["schumacher", "verstappen"] and not has_first_name:
            missing.append("driver")
        if "year" not in slots:
            missing.append("year")
        return missing

    if intent == "driver_profile":
        driver = slots.get("driver", "")
        has_first_name = any(fn in norm for fn in ["max", "jos", "michael", "ralf", "mick"]) or " " in driver or "_" in driver
        if driver in ["schumacher", "verstappen"] and not has_first_name:
            return ["driver"]

    return []
