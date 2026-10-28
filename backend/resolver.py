import datetime
import logging
import re
import sqlite3
from typing import Dict, Any, List, Optional
from rapidfuzz import fuzz, process

try:
    from backend import config, cache
    from backend.sources import jolpica
except ImportError:
    import config, cache
    from sources import jolpica

logger = logging.getLogger("resolver")

def get_current_year() -> int:
    return datetime.date.today().year

def _get_driver_seasons_summary(driver_id: str) -> Optional[str]:
    """Returns active years range for a driver, e.g. '1991-2012' from Jolpica."""
    url = f"{jolpica.JOLPICA_BASE}/drivers/{driver_id}/seasons.json?limit=100"
    data = cache.cached_get_json(url, cache.TTL_PAST_SEASON)
    if data and "MRData" in data:
        seasons = data["MRData"].get("SeasonTable", {}).get("Seasons", [])
        if seasons:
            start_yr = seasons[0]["season"]
            end_yr = seasons[-1]["season"]
            return f"{start_yr}-{end_yr}" if start_yr != end_yr else start_yr
    return None

def resolve_driver(text: str, year: Optional[int] = None) -> Dict[str, Any]:
    query = text.strip()
    query_lower = query.lower()

    NON_DRIVER_WORDS = {
        "hello", "hi", "hey", "greetings", "good", "morning", "afternoon", "evening",
        "thanks", "thank", "test", "help", "who", "what", "where", "which", "when",
        "how", "tell", "show", "can", "you", "please", "yes", "no", "okay", "ok",
        "standings", "schedule", "result", "strategy", "winner", "circuit"
    }
    if query_lower in NON_DRIVER_WORDS or len(query_lower) < 2:
        return {
            "status": "not_available",
            "reason": f"'{text}' is not a driver name."
        }

    current_year = get_current_year()
    candidates = []

    if year:
        url = f"{jolpica.JOLPICA_BASE}/{year}/drivers.json?limit=100"
        ttl = cache.TTL_PAST_SEASON if year < current_year else cache.TTL_CURRENT_STANDINGS
        data = cache.cached_get_json(url, ttl)
        drivers = data.get("MRData", {}).get("DriverTable", {}).get("Drivers", []) if data else []
        for d in drivers:
            did = d.get("driverId", "")
            code = (d.get("code") or "").lower()
            fam = (d.get("familyName") or "").lower()
            given = (d.get("givenName") or "").lower()
            full = f"{given} {fam}".strip()

            if query_lower in [code, fam, full, did] or fam.startswith(query_lower) or fuzz.ratio(query_lower, fam) >= 80 or fuzz.ratio(query_lower, full) >= 80 or fuzz.token_sort_ratio(query_lower, full) >= 80:
                active_years = _get_driver_seasons_summary(did) or str(year)
                candidates.append({
                    "driver_id": did,
                    "code": d.get("code", ""),
                    "given_name": d.get("givenName", ""),
                    "family_name": d.get("familyName", ""),
                    "name": full.title(),
                    "years_active": active_years,
                    "label": f"{d.get('givenName', '')} ({active_years})".strip()
                })
    else:
        # Query local SQLite drivers_lookup
        try:
            conn = sqlite3.connect(str(config.DB_PATH), timeout=5.0)
            cur = conn.cursor()
            cur.execute("SELECT driver_id, code, given_name, family_name, full_name, has_results FROM drivers_lookup WHERE has_results > 0")
            rows = cur.fetchall()
            conn.close()

            for did, code, gn, fn, full, has_res in rows:
                code_l = (code or "").lower()
                fam_l = (fn or "").lower()
                given_l = (gn or "").lower()
                full_l = (full or "").lower()

                is_match = False
                match_type = "family"
                if query_lower in [code_l, did]:
                    is_match = True
                    match_type = "code"
                elif query_lower == given_l:
                    is_match = True
                    match_type = "given"
                elif query_lower in [fam_l, full_l]:
                    is_match = True
                    match_type = "family"
                elif fam_l.startswith(query_lower) and len(query_lower) >= 4:
                    is_match = True
                    match_type = "family"
                elif fuzz.ratio(query_lower, fam_l) >= 80 or fuzz.ratio(query_lower, full_l) >= 80 or fuzz.token_sort_ratio(query_lower, full_l) >= 80:
                    is_match = True
                    match_type = "family"

                if is_match:
                    active_years = _get_driver_seasons_summary(did) or ""
                    candidates.append({
                        "driver_id": did,
                        "code": code,
                        "given_name": gn,
                        "family_name": fn,
                        "name": full.title(),
                        "years_active": active_years,
                        "label": f"{gn} ({active_years})".strip() if active_years else full.title(),
                        "match_type": match_type
                    })
        except Exception as e:
            logger.warning(f"Error querying drivers_lookup: {e}")

    if not candidates:
        return {
            "status": "not_available",
            "reason": f"Driver '{text}' could not be resolved."
        }

    # If multiple candidates, check if code or given name matched a recent driver in last 10 seasons (Section 2.4)
    if len(candidates) > 1 and not year:
        # Check if match was by code or given name (or exact match vs older surname collision)
        exact_code_or_given = [c for c in candidates if c.get("match_type") in ("code", "given")]
        if exact_code_or_given:
            def is_recent(c):
                y_str = c.get("years_active", "")
                m = re.findall(r"\b(19\d{2}|20\d{2})\b", y_str)
                if m:
                    last_yr = int(m[-1])
                    return last_yr >= (current_year - 9)
                return False

            recent_cands = [c for c in exact_code_or_given if is_recent(c)]
            if len(recent_cands) == 1:
                candidates = recent_cands

    # If exactly 1 candidate: accept silently (Section 2.4)
    if len(candidates) == 1:
        c = candidates[0]
        return {
            "status": "ok",
            "driver_id": c["driver_id"],
            "code": c["code"],
            "name": f"{c['given_name']} {c['family_name']}".strip()
        }

    # 2 or more candidates: ask with full names and years active
    names_str = ", ".join(f"{c['label']}" for c in candidates)
    return {
        "status": "ambiguous",
        "candidates": candidates,
        "message": f"Which {query.title()} did you mean? ({names_str})"
    }

def resolve_gp(text: str, year: int) -> Dict[str, Any]:
    sched = jolpica.fetch_schedule(year)
    if sched.get("status") != "ok":
        return sched

    schedule_list = sched.get("schedule", [])
    if not schedule_list:
        return {
            "status": "not_available",
            "reason": f"No schedule data available for season {year}."
        }

    # If text is an integer round number
    if isinstance(text, int) or (isinstance(text, str) and text.strip().isdigit()):
        r_num = int(text)
        for r in schedule_list:
            if r["round"] == r_num:
                return {
                    "status": "ok",
                    "round": r["round"],
                    "grand_prix": r["grand_prix"],
                    "circuit": r["circuit_name"]
                }
        return {
            "status": "not_available",
            "reason": f"Round {r_num} does not exist in season {year}."
        }

    query = str(text).strip()
    query_lower = query.lower()

    if len(query_lower) <= 2:
        return {
            "status": "not_available",
            "reason": f"Grand Prix '{text}' not found in season {year}."
        }

    # Pass 1: exact word boundary match
    for r in schedule_list:
        gp_name = r.get("grand_prix", "").lower()
        circuit = r.get("circuit_name", "").lower()
        locality = r.get("locality", "").lower()
        country = r.get("country", "").lower()

        fields = [gp_name, circuit, locality, country]
        for fld in fields:
            if re.search(rf"\b{re.escape(query_lower)}\b", fld):
                return {
                    "status": "ok",
                    "round": r["round"],
                    "grand_prix": r["grand_prix"],
                    "circuit": r["circuit_name"]
                }

    # Pass 2: substring or fuzzy matching
    best_match = None
    best_score = 0.0

    for r in schedule_list:
        gp_name = r.get("grand_prix", "")
        circuit = r.get("circuit_name", "")
        locality = r.get("locality", "")
        country = r.get("country", "")

        fields = [gp_name, circuit, locality, country, f"{locality} Grand Prix", f"{country} Grand Prix"]
        for fld in fields:
            fld_lower = fld.lower()
            score = fuzz.ratio(query_lower, fld_lower)
            if score > best_score:
                best_score = score
                best_match = r

    if best_match and best_score >= 65:
        return {
            "status": "ok",
            "round": best_match["round"],
            "grand_prix": best_match["grand_prix"],
            "circuit": best_match["circuit_name"]
        }

    return {
        "status": "not_available",
        "reason": f"Grand Prix '{text}' not found in season {year}."
    }

def resolve_team(text: str, year: Optional[int] = None) -> Dict[str, Any]:
    query = text.strip()
    query_lower = query.lower()

    # Common team aliases (Section 2.4)
    alias_map = {
        "scuderia": "ferrari",
        "scuderia ferrari": "ferrari",
        "racing bulls": "rb",
        "racing bull": "rb",
        "vcarb": "rb",
        "toro rosso": "toro_rosso",
        "alphatauri": "alphatauri",
        "alpha tauri": "alphatauri",
        "brawn": "brawn",
        "brawn gp": "brawn",
        "mercedes": "mercedes",
        "red bull": "red_bull",
        "mclaren": "mclaren",
        "alpine": "alpine",
        "aston martin": "aston_martin",
        "williams": "williams",
        "sauber": "sauber",
        "kick sauber": "sauber",
        "haas": "haas"
    }
    target_cid = alias_map.get(query_lower)

    current_year = get_current_year()
    url = f"{jolpica.JOLPICA_BASE}/{year}/constructors.json?limit=100" if year else f"{jolpica.JOLPICA_BASE}/constructors.json?limit=300"
    ttl = cache.TTL_PAST_SEASON if (year and year < current_year) else cache.TTL_CURRENT_STANDINGS
    data = cache.cached_get_json(url, ttl)
    cons = []
    if data and "MRData" in data:
        cons = data["MRData"].get("ConstructorTable", {}).get("Constructors", [])

    if target_cid:
        for c in cons:
            if c.get("constructorId") == target_cid:
                return {
                    "status": "ok",
                    "constructor_id": c.get("constructorId"),
                    "name": c.get("name")
                }
        return {
            "status": "ok",
            "constructor_id": target_cid,
            "name": target_cid.replace("_", " ").title()
        }

    if len(query_lower) <= 2 and query_lower not in ["rb"]:
        return {
            "status": "not_available",
            "reason": f"Team '{text}' could not be resolved."
        }

    cons_map = {}
    for c in cons:
        name = c.get("name", "")
        cid = c.get("constructorId", "")
        cons_map[name] = c
        cons_map[cid] = c

    matches = process.extract(query, list(cons_map.keys()), scorer=fuzz.WRatio, limit=5)
    if not matches:
        return {
            "status": "not_available",
            "reason": f"Team '{text}' could not be resolved."
        }

    top_key, top_score, _ = matches[0]
    if top_score < 80:
        return {
            "status": "not_available",
            "reason": f"Team '{text}' could not be resolved."
        }

    matched_c = cons_map[top_key]
    return {
        "status": "ok",
        "constructor_id": matched_c.get("constructorId"),
        "name": matched_c.get("name")
    }

def resolve_circuit(text: str) -> Dict[str, Any]:
    query = text.strip()
    query_lower = query.lower()

    if len(query_lower) <= 2:
        return {
            "status": "not_available",
            "reason": f"Circuit '{text}' could not be resolved."
        }

    url = f"{jolpica.JOLPICA_BASE}/circuits.json?limit=100"
    data = cache.cached_get_json(url, cache.TTL_PAST_SEASON)
    circuits = []
    if data and "MRData" in data:
        circuits = data["MRData"].get("CircuitTable", {}).get("Circuits", [])

    for c in circuits:
        c_name = c.get("circuitName", "").lower()
        loc = c.get("Location", {}).get("locality", "").lower()
        country = c.get("Location", {}).get("country", "").lower()
        cid = c.get("circuitId", "").lower()

        if query_lower in c_name or query_lower in loc or query_lower in country or query_lower in cid:
            return {
                "status": "ok",
                "circuit_id": c.get("circuitId"),
                "circuit_name": c.get("circuitName"),
                "locality": c.get("Location", {}).get("locality"),
                "country": c.get("Location", {}).get("country")
            }

    return {
        "status": "not_available",
        "reason": f"Circuit '{text}' could not be resolved."
    }
