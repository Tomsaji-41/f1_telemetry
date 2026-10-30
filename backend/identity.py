"""
backend/identity.py
Identity and Colours Service (Phase 2).
Resolves official Jolpica driver codes, permanent numbers, constructor mappings,
and OpenF1 / FastF1 dynamic team colors with WCAG 2.1 text contrast and teammate disambiguation.
"""
import os
import json
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

def resolve_wikipedia_headshot(name: str, wiki_url: Optional[str] = None) -> Optional[str]:
    """Retrieve driver headshot thumbnail from Wikipedia REST summary API."""
    try:
        slug = ""
        if wiki_url and "/wiki/" in wiki_url:
            slug = wiki_url.split("/wiki/")[-1].strip()
        if not slug and name:
            slug = name.strip().replace(" ", "_")
        if not slug:
            return None
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}"
        headers = {"User-Agent": "F1TelemetryApp/1.0 (https://github.com/example/f1_telemetry)"}
        data = cache.cached_get_json(url, cache.TTL_PAST_SEASON, headers=headers)
        if isinstance(data, dict):
            thumb = data.get("thumbnail")
            if isinstance(thumb, dict) and thumb.get("source"):
                return thumb["source"]
    except Exception:
        pass
    return None


def get_openf1_fallback_headshot(num: str, acr: str, name: str) -> Optional[str]:
    """Fallback search across OpenF1 drivers if not found in current session."""
    url = "https://api.openf1.org/v1/drivers"
    data = cache.cached_get_json(url, cache.TTL_PAST_SEASON)
    if isinstance(data, list):
        norm_name = normalize_text(name)
        for d in data:
            d_num = str(d.get("driver_number") or "").strip()
            d_acr = (d.get("name_acronym") or "").strip().upper()
            d_name = normalize_text(d.get("full_name") or "")
            hs = d.get("headshot_url")
            if hs:
                if (num and d_num == num) or (acr and d_acr == acr) or (norm_name and norm_name == d_name):
                    return hs
    return None


def get_season_identity(year: Optional[int] = None) -> Dict[str, Any]:
    """
    Returns unified identity map for all drivers and teams in the given season.
    Keyed by Jolpica unique driverId and constructorId.
    Cached for past seasons (30 days) and current season (1 day).
    """
    if year is None:
        latest = jolpica.get_latest_completed_session()
        year = latest.get("year", datetime.date.today().year)

    cache_key = f"identity_season_v3:{year}"
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
        raw_of1 = cache.cached_get_json("https://api.openf1.org/v1/drivers?session_key=latest", ttl)
        if not isinstance(raw_of1, list) or not raw_of1:
            raw_of1 = cache.cached_get_json("https://api.openf1.org/v1/drivers", ttl)
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

    # FastF1 runtime constants loader for official constructor colors
    fastf1_colors: Dict[str, str] = {}
    try:
        import fastf1.plotting
        const_file = os.path.join(os.path.dirname(fastf1.plotting.__file__), "constants.json")
        if os.path.exists(const_file):
            with open(const_file, "r", encoding="utf-8") as f:
                const_data = json.load(f)

            yr_str = str(year)
            available_years = sorted([int(y) for y in const_data.keys() if y.isdigit()], reverse=True)
            chosen_year = None
            if yr_str in const_data:
                chosen_year = yr_str
            elif available_years:
                chosen_year = str(min(available_years, key=lambda y: abs(y - year)))

            def extract_teams(y_key: str):
                t_dict = const_data.get(y_key, {}).get("teams", {})
                for t_key, t_info in t_dict.items():
                    colors = t_info.get("colors", {})
                    hex_col = colors.get("official") or colors.get("fastf1")
                    if hex_col:
                        clean_hex = f"#{hex_col.lstrip('#')}".upper()
                        fastf1_colors[normalize_text(t_key)] = clean_hex
                        sn = t_info.get("short_name")
                        if sn:
                            fastf1_colors[normalize_text(sn)] = clean_hex

            # Populate historical years first as fallbacks, then overwrite with target season
            for av_yr in available_years:
                extract_teams(str(av_yr))
            if chosen_year:
                extract_teams(chosen_year)
    except Exception as e:
        logger.warning(f"Could not load FastF1 constants.json team colors: {e}")

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

        # Headshot fallback chain: OpenF1 (other seasons) -> Wikipedia REST summary API
        if not headshot:
            headshot = get_openf1_fallback_headshot(num, code, name)
        if not headshot:
            headshot = resolve_wikipedia_headshot(name, s.get("url"))

        # Try team color match from OpenF1
        if not color and normalize_text(c_name) in of1_team_colors:
            color = of1_team_colors[normalize_text(c_name)]

        # Try FastF1 team color
        if not color:
            norm_c = normalize_text(c_name)
            norm_cid = normalize_text(c_id)
            c_words = set(norm_c.split())
            for fk, fcol in fastf1_colors.items():
                fk_words = set(fk.split())
                if (fk == norm_c or fk in norm_c or norm_c in fk or
                    fk == norm_cid or fk in norm_cid or norm_cid in fk or
                    (fk_words and fk_words.issubset(c_words)) or
                    (c_words and fk in c_words)):
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
        elif teams_map[c_id].get("teamColor") == config.NEUTRAL_COLOUR and color != config.NEUTRAL_COLOUR:
            teams_map[c_id]["teamColor"] = color
            teams_map[c_id]["textColor"] = text_color

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

def get_round_identity(year: int, round_num: int) -> Dict[str, Any]:
    """
    Returns unified identity map for drivers and teams tailored to a specific round,
    reflecting mid-season driver substitutions, seat swaps, and round-specific constructor lineups.
    """
    cache_key = f"identity_round_v3:{year}:{round_num}"
    cached = cache.get_json(cache_key)
    if cached is not None:
        return cached

    season_id = get_season_identity(year)
    s_drivers = season_id.get("drivers", {})
    s_teams = season_id.get("teams", {})

    # Fetch race results for the specific round
    race_res = jolpica.fetch_race_results(year, round_num)
    results_list = race_res.get("results", []) if race_res.get("status") == "ok" else []

    if not results_list:
        # Fall back to qualifying or season identity if race results not yet published
        q_res = jolpica.fetch_qualifying_results(year, round_num)
        results_list = q_res.get("qualifying", []) if q_res.get("status") == "ok" else []

    if not results_list:
        res = dict(season_id)
        res["round"] = round_num
        return res

    drivers_map: Dict[str, Dict[str, Any]] = {}
    teams_map: Dict[str, Dict[str, Any]] = {}
    team_driver_ids: Dict[str, List[str]] = {}

    for r in results_list:
        d_id = r.get("driver_id") or r.get("driverId") or ""
        code = r.get("code") or (d_id[:3].upper() if d_id else "DRV")
        name = r.get("driver") or r.get("name") or code
        c_name = r.get("constructor") or r.get("team") or "F1 Team"
        c_id = normalize_text(c_name).replace(" ", "_")
        num = str(r.get("number", "")).strip()

        base_drv = s_drivers.get(d_id, {})
        base_team = s_teams.get(c_id, {})

        team_color = base_drv.get("teamColor") or base_team.get("teamColor") or config.NEUTRAL_COLOUR
        text_color = base_drv.get("textColor") or base_team.get("textColor") or get_readable_text_color(team_color)
        headshot = base_drv.get("headshotUrl") or resolve_wikipedia_headshot(name)

        drivers_map[d_id] = {
            "driverId": d_id,
            "code": code,
            "number": num if num else base_drv.get("number", "#-"),
            "name": name,
            "givenName": base_drv.get("givenName", name.split()[0] if name else ""),
            "familyName": base_drv.get("familyName", name.split()[-1] if name else ""),
            "nationality": base_drv.get("nationality", ""),
            "dob": base_drv.get("dob", ""),
            "team": c_name,
            "teamId": c_id,
            "teamColor": team_color,
            "textColor": text_color,
            "headshotUrl": headshot,
        }

        team_driver_ids.setdefault(c_id, []).append(d_id)
        if c_id not in teams_map:
            teams_map[c_id] = {
                "teamId": c_id,
                "name": c_name,
                "teamColor": team_color,
                "textColor": text_color,
                "drivers": []
            }

    # Teammate disambiguation for this specific round
    for c_id, d_ids in team_driver_ids.items():
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

    current_year = datetime.date.today().year
    ttl = cache.TTL_PAST_SEASON if year < current_year else cache.TTL_CURRENT_ROUND
    result = {
        "status": "ok",
        "source": "Jolpica & OpenF1",
        "year": year,
        "round": round_num,
        "drivers": drivers_map,
        "teams": teams_map,
    }
    cache.set_json(cache_key, result, ttl)
    return result

def get_identity(year: Optional[int] = None, round: Optional[int] = None) -> Dict[str, Any]:
    """Unified entrypoint: resolves round-specific identity if round is supplied, else season identity."""
    if year is None:
        latest = jolpica.get_latest_completed_session()
        year = latest.get("year", datetime.date.today().year)
    if round is not None:
        return get_round_identity(year, round)
    return get_season_identity(year)
