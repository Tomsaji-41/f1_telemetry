"""
backend/identity.py
Identity and Colours Service (Phase 2).
Resolves official Jolpica driver codes, permanent numbers, constructor mappings,
and OpenF1 / FastF1 dynamic team colors with WCAG 2.1 text contrast and teammate disambiguation.
"""
import unicodedata
import re
import logging
from typing import Dict, Any, List, Optional, Tuple
import datetime

try:
    from backend import cache, config
    from backend.sources import jolpica
except ImportError:
    import cache, config
    from sources import jolpica

logger = logging.getLogger("identity")

def normalize_text(text: str) -> str:
    """Normalize text: remove accents, lowercase, strip punctuation."""
    if not text:
        return ""
    nfkd = unicodedata.normalize('NFKD', text)
    ascii_text = nfkd.encode('ASCII', 'ignore').decode('utf-8')
    cleaned = re.sub(r'[^a-zA-Z0-9\s]', '', ascii_text).lower().strip()
    return cleaned

def parse_hex(hex_str: str) -> Tuple[int, int, int]:
    clean = hex_str.replace("#", "").strip()
    if len(clean) == 3:
        clean = "".join([c + c for c in clean])
    if len(clean) != 6:
        return (158, 158, 176) # default neutral grey #9E9EB0
    try:
        num = int(clean, 16)
        return ((num >> 16) & 255, (num >> 8) & 255, num & 255)
    except Exception:
        return (158, 158, 176)

def get_relative_luminance(r: int, g: int, b: int) -> float:
    vals = []
    for c in (r, g, b):
        s = c / 255.0
        vals.append(s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4)
    return 0.2126 * vals[0] + 0.7152 * vals[1] + 0.0722 * vals[2]

def get_readable_text_color(bg_hex: str) -> str:
    """WCAG 2.1 contrast helper: returns #000000 or #FFFFFF for maximum contrast."""
    r, g, b = parse_hex(bg_hex)
    lum = get_relative_luminance(r, g, b)
    contrast_with_white = (1.0 + 0.05) / (lum + 0.05)
    contrast_with_black = (lum + 0.05) / (0.0 + 0.05)
    return "#000000" if contrast_with_black >= contrast_with_white else "#FFFFFF"

def lighten_color(hex_str: str, factor: float = 0.35) -> str:
    """Lighten a hex color for teammate stroke/tint disambiguation."""
    r, g, b = parse_hex(hex_str)
    r_new = int(r + (255 - r) * factor)
    g_new = int(g + (255 - g) * factor)
    b_new = int(b + (255 - b) * factor)
    return f"#{r_new:02x}{g_new:02x}{b_new:02x}".upper()

def get_season_identity(year: Optional[int] = None) -> Dict[str, Any]:
    """
    Returns unified identity map for all drivers and teams in the given season.
    Keyed by Jolpica unique driverId and constructorId.
    Cached for past seasons (30 days) and current season (1 day).
    """
    if year is None:
        latest = jolpica.get_latest_completed_session()
        year = latest.get("year", datetime.date.today().year)

    cache_key = f"identity_season_v2:{year}"
    cached = cache.get_json(cache_key)
    if cached is not None:
        return cached

    current_year = datetime.date.today().year
    ttl = cache.TTL_PAST_SEASON if year < current_year else cache.TTL_CURRENT_ROUND

    # 1. Fetch Jolpica driver standings
    st_res = jolpica.fetch_standings(year, kind="drivers")
    drivers_list = st_res.get("standings", [])
    if not drivers_list:
        # Fallback to schedule/race results to get active grid if standings empty
        sched = jolpica.fetch_schedule(year)
        if sched.get("status") == "ok" and sched.get("schedule"):
            r1 = sched["schedule"][0].get("round", 1)
            res1 = jolpica.fetch_race_results(year, r1)
            drivers_list = res1.get("results", [])

    # 2. OpenF1 drivers data for 2023+ (team_colour, headshot_url, name_acronym, driver_number)
    openf1_data = []
    if year >= 2023:
        url_of1 = f"https://api.openf1.org/v1/drivers?year={year}"
        raw_of1 = cache.cached_get_json(url_of1, ttl)
        if isinstance(raw_of1, list):
            openf1_data = raw_of1

    # Index OpenF1 by number, acronym, and normalized full name
    of1_by_num: Dict[str, Dict[str, Any]] = {}
    of1_by_acronym: Dict[str, Dict[str, Any]] = {}
    of1_by_name: Dict[str, Dict[str, Any]] = {}
    of1_team_colors: Dict[str, str] = {}

    for d in openf1_data:
        num = str(d.get("driver_number") or "").strip()
        acr = (d.get("name_acronym") or "").strip().upper()
        fn = normalize_text(d.get("full_name") or "")
        t_name = normalize_text(d.get("team_name") or "")
        t_col = d.get("team_colour")
        if t_col:
            clean_col = f"#{t_col.lstrip('#')}".upper()
            if num: of1_by_num[num] = {**d, "color": clean_col}
            if acr: of1_by_acronym[acr] = {**d, "color": clean_col}
            if fn: of1_by_name[fn] = {**d, "color": clean_col}
            if t_name: of1_team_colors[t_name] = clean_col

    # FastF1 plotting fallback for pre-2023
    fastf1_colors: Dict[str, str] = {}
    try:
        import fastf1.plotting
        if hasattr(fastf1.plotting, "TEAM_COLORS"):
            for t_k, c_v in fastf1.plotting.TEAM_COLORS.items():
                fastf1_colors[normalize_text(t_k)] = c_v
    except Exception:
        pass

    # 3. Build Driver Identity Map
    drivers_map: Dict[str, Dict[str, Any]] = {}
    teams_map: Dict[str, Dict[str, Any]] = {}
    team_driver_ids: Dict[str, List[str]] = {}
    seen_codes: Dict[str, str] = {}

    for s in drivers_list:
        d_id = s.get("driverId") or s.get("driver_id") or ""
        given = s.get("given_name") or ""
        family = s.get("family_name") or ""
        name = s.get("driver") or f"{given} {family}".strip() or d_id
        if not family and " " in name:
            parts = name.split()
            given = parts[0]
            family = " ".join(parts[1:])

        raw_code = s.get("code")
        if raw_code and len(raw_code) == 3:
            code = raw_code.upper()
        else:
            # Fallback to first 3 letters of family name, NOT given name
            code = family[:3].upper() if len(family) >= 3 else (family + "X")[:3].upper()
            logger.info(f"Driver {d_id} missing code; derived {code} from family name {family}")

        # Unique code verification
        if code in seen_codes and seen_codes[code] != d_id:
            # Disambiguate: 1st letter of given name + 2 of family
            code = (given[:1] + family[:2]).upper()
        seen_codes[code] = d_id

        num = str(s.get("number") or s.get("permanentNumber") or "")
        if num == "-" or not num:
            num = ""

        c_name = s.get("team") or s.get("constructor") or "Unknown"
        c_id = s.get("constructorId") or s.get("team_id") or normalize_text(c_name).replace(" ", "_")

        # Color resolution: OpenF1 -> FastF1 plotting -> Neutral
        color = None
        headshot = None

        # Try match from OpenF1 by number
        if num and num in of1_by_num:
            match = of1_by_num[num]
            color = match.get("color")
            headshot = match.get("headshot_url")
        # Try match by acronym
        elif code in of1_by_acronym:
            match = of1_by_acronym[code]
            color = match.get("color")
            headshot = match.get("headshot_url")
        # Try match by normalized name
        elif normalize_text(name) in of1_by_name:
            match = of1_by_name[normalize_text(name)]
            color = match.get("color")
            headshot = match.get("headshot_url")

        # Try team color match from OpenF1
        if not color and normalize_text(c_name) in of1_team_colors:
            color = of1_team_colors[normalize_text(c_name)]

        # Try FastF1 team color
        if not color:
            norm_c = normalize_text(c_name)
            for fk, fcol in fastf1_colors.items():
                if fk in norm_c or norm_c in fk:
                    color = fcol
                    break

        if not color:
            color = config.NEUTRAL_COLOUR

        text_color = get_readable_text_color(color)

        drivers_map[d_id] = {
            "driverId": d_id,
            "code": code,
            "number": num if num else "#-",
            "name": name,
            "givenName": given,
            "familyName": family,
            "nationality": s.get("nationality", ""),
            "dob": s.get("dob") or s.get("dateOfBirth", ""),
            "team": c_name,
            "teamId": c_id,
            "teamColor": color,
            "textColor": text_color,
            "headshotUrl": headshot,
        }

        team_driver_ids.setdefault(c_id, []).append(d_id)
        if c_id not in teams_map:
            teams_map[c_id] = {
                "teamId": c_id,
                "name": c_name,
                "teamColor": color,
                "textColor": text_color,
                "drivers": []
            }

    # 4. Teammate disambiguation (2.5) & 2-driver check (2.3)
    for c_id, d_ids in team_driver_ids.items():
        if len(d_ids) > 2:
            logger.warning("Team %s has %d current drivers registered for %s: %s", c_id, len(d_ids), year, d_ids)
        teams_map[c_id]["drivers"] = d_ids

        for idx, did in enumerate(d_ids):
            drv = drivers_map[did]
            if idx == 0:
                drv["isSecondDriver"] = False
                drv["dash"] = None
                drv["strokeDash"] = None
                drv["tintColor"] = drv["teamColor"]
            else:
                drv["isSecondDriver"] = True
                drv["dash"] = "4 2"
                drv["strokeDash"] = "4 2"
                drv["tintColor"] = lighten_color(drv["teamColor"], 0.35)

    result = {
        "status": "ok",
        "source": "Jolpica & OpenF1",
        "year": year,
        "drivers": drivers_map,
        "teams": teams_map,
    }

    cache.set_json(cache_key, result, ttl)
    return result
