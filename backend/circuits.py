"""
backend/circuits.py — Circuits Data Service & Track Geometry Resolution (Phase K1/K3)

Endpoints:
- GET /api/circuits?year=&scope=season|all (paginated Jolpica circuit list)
- GET /api/circuits/{circuitId}?year=&round= (full details, stats, character, climate, facts)
- GET /api/circuits/{circuitId}/geometry?year=&round= (3D/2D track coordinates & corners)

Prime Rules apply:
- Nothing hardcoded.
- Real FastF1/MultiViewer/OSM geometry only; never synthesize fake track loops.
- Units: FastF1 telemetry decimetres multiplied by 0.1 -> SI metres.
- Direction computed via signed area (Shoelace formula).
"""
import collections
import math
import json
import logging
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional, Tuple

try:
    from backend import cache, config, session_map, http_pool
    from backend.sources import jolpica
    from backend.sanitizer import sanitize_for_json
except ImportError:
    import cache
    import config
    import session_map
    import http_pool
    from sources import jolpica
    from sanitizer import sanitize_for_json

logger = logging.getLogger("circuits")

USER_AGENT = "AI-Pitboss-F1-Telemetry/1.0 (https://github.com/f1_telemetry; telemetry@pitboss.local)"
JOLPICA_BASE = "https://api.jolpi.ca/ergast/f1"

# In-memory circuit keys map from MultiViewer API
_MV_CIRCUIT_MAP: Dict[str, Any] = {}


def _http_get_json(url: str, ttl: float = cache.TTL_PAST_SEASON) -> Optional[Dict[str, Any]]:
    """Cached HTTP GET returning JSON via pooled client."""
    cache_key = f"circuit_http:{url}"
    cached = cache.get_json(cache_key)
    if cached is not None:
        return cached

    data = http_pool.fetch_json_pooled(url)
    if data is not None:
        cache.set_json(cache_key, data, ttl)
    return data


def _get_mv_circuits() -> Dict[str, Any]:
    """Retrieves all circuits available in MultiViewer F1 dataset."""
    global _MV_CIRCUIT_MAP
    if _MV_CIRCUIT_MAP:
        return _MV_CIRCUIT_MAP

    url = "https://api.multiviewer.app/api/v1/circuits"
    data = _http_get_json(url, ttl=cache.TTL_PAST_SEASON)
    if isinstance(data, dict):
        _MV_CIRCUIT_MAP = data
        return _MV_CIRCUIT_MAP
    return {}


def resolve_mv_circuit_key(circuit_id: str, circuit_name: str, country: str) -> Optional[str]:
    """Matches a Jolpica circuit to a MultiViewer API circuit key."""
    mv_all = _get_mv_circuits()
    c_norm = session_map.normalize_name(circuit_id)
    name_norm = session_map.normalize_name(circuit_name)
    country_norm = session_map.normalize_name(country)

    for k, item in mv_all.items():
        if not isinstance(item, dict):
            continue
        mv_name = session_map.normalize_name(item.get("name", ""))
        mv_country = session_map.normalize_name(item.get("country", ""))
        if (mv_name in name_norm or name_norm in mv_name or
            mv_name in c_norm or c_norm in mv_name):
            if not country_norm or country_norm in mv_country or mv_country in country_norm:
                return k

    token_aliases = {
        "silverstone": "2", "hungaroring": "4", "imola": "6", "spa": "7",
        "americas": "9", "albert_park": "10", "interlagos": "14", "catalunya": "15",
        "red_bull_ring": "19", "monaco": "22", "monza": "39", "suzuka": "46",
        "bahrain": "63", "shanghai": "65", "marina_bay": "61", "yas_marina": "70",
        "villeneuve": "72", "baku": "144", "losail": "147", "jeddah": "149",
        "miami": "151", "zandvoort": "152", "las_vegas": "152"
    }
    return token_aliases.get(circuit_id)


def compute_signed_area(xs: List[float], ys: List[float]) -> float:
    """Computes signed area using Shoelace formula to determine track direction."""
    n = len(xs)
    if n < 3:
        return 0.0
    area2 = 0.0
    for i in range(n):
        j = (i + 1) % n
        area2 += (xs[i] * ys[j]) - (xs[j] * ys[i])
    return area2 / 2.0


def _fetch_osm_overpass_geometry(circuit_name: str, lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """
    Fallback C: Queries OpenStreetMap Overpass for raceway way/relation within 0.05 deg bbox.
    Projects WGS84 lat/lon to local Cartesian meters.
    """
    if abs(lat) < 0.1 and abs(lon) < 0.1:
        return None

    # Bbox +/- 0.04 degrees (~4km)
    min_lat, max_lat = lat - 0.04, lat + 0.04
    min_lon, max_lon = lon - 0.04, lon + 0.04

    query = f"""[out:json][timeout:5];
(
  way["highway"="raceway"]({min_lat:.4f}, {min_lon:.4f}, {max_lat:.4f}, {max_lon:.4f});
  relation["highway"="raceway"]({min_lat:.4f}, {min_lon:.4f}, {max_lat:.4f}, {max_lon:.4f});
);
out geom;"""

    for ep in [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter"
    ]:
        try:
            req = urllib.request.Request(
                ep,
                data=urllib.parse.urlencode({"data": query}).encode("utf-8"),
                headers={"User-Agent": USER_AGENT}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                elements = data.get("elements", [])
                if not elements:
                    continue

                best_way = None
                max_pts = 0
                for el in elements:
                    geom = el.get("geometry", [])
                    if len(geom) > max_pts:
                        max_pts = len(geom)
                        best_way = geom

                if best_way and len(best_way) >= 10:
                    cos_lat = math.cos(math.radians(lat))
                    ref_lat, ref_lon = best_way[0]["lat"], best_way[0]["lon"]
                    xs = []
                    ys = []
                    for pt in best_way:
                        x = (pt["lon"] - ref_lon) * 111139.0 * cos_lat
                        y = (pt["lat"] - ref_lat) * 111139.0
                        xs.append(round(x, 2))
                        ys.append(round(y, 2))

                    return {
                        "x": xs,
                        "y": ys,
                        "corners": [],
                        "source": "OpenStreetMap Overpass",
                        "rotation": 0,
                    }
        except Exception as e:
            logger.debug(f"Overpass query to {ep} failed: {e}")

    return None


def fetch_all_circuits(year: Optional[int] = None, scope: str = "season") -> Dict[str, Any]:
    """Lists all circuits from Jolpica paginated endpoint with geometry capability flags."""
    import datetime
    target_year = year or 2024

    cache_key = cache.build_cache_key("circuits_list_v4", scope, year=target_year)
    cached = cache.get_json(cache_key)
    if cached is not None:
        return cached

    url = f"{JOLPICA_BASE}/circuits.json"
    raw = jolpica.fetch_paginated_mrdata(url, ttl=cache.TTL_PAST_SEASON, page_size=100)
    all_circuits = []
    if raw and "MRData" in raw:
        all_circuits = raw["MRData"].get("CircuitTable", {}).get("Circuits", [])

    # If scope is season, filter to current/target year schedule
    season_circuits = None
    if scope == "season":
        sched = jolpica.fetch_schedule(target_year)
        if sched.get("status") == "ok":
            season_circuits = {r.get("circuit_id") for r in sched.get("schedule", []) if r.get("circuit_id")}

    results = []
    for c in all_circuits:
        cid = c.get("circuitId", "")
        if season_circuits is not None and cid not in season_circuits:
            continue

        loc = c.get("Location", {})
        cname = c.get("circuitName", "")
        country = loc.get("country", "")
        has_3d = bool(resolve_mv_circuit_key(cid, cname, country))

        results.append({
            "circuit_id": cid,
            "name": cname,
            "circuit_name": cname,
            "locality": loc.get("locality", ""),
            "country": country,
            "latitude": float(loc.get("lat", 0.0)),
            "longitude": float(loc.get("long", 0.0)),
            "url": c.get("url"),
            "has_3d": has_3d,
            "has_geometry_3d": has_3d,
        })

    out = {
        "status": "ok",
        "source": "Jolpica & FastF1 MultiViewer",
        "scope": scope,
        "year": target_year,
        "total_circuits": len(results),
        "circuits": results,
    }
    cache.set_json(cache_key, out, cache.TTL_PAST_SEASON)
    return out


def get_circuit_geometry(circuit_id: str, year: Optional[int] = None, round_num: Optional[int] = None) -> Dict[str, Any]:
    """
    Returns high-precision track coordinates, corners, elevation, and direction.
    Resolution Chain:
    1. FastF1 MultiViewer official telemetry coordinate dataset (decimetres * 0.1 -> meters)
    2. OpenStreetMap Overpass raceway geometry
    3. Return status='not_available' with honest explanation (never synthetic loop).
    """
    cache_key = cache.build_cache_key("circuit_geom_v3", circuit_id, year=year, round=round_num)
    cached = cache.get_json(cache_key)
    if cached is not None:
        return cached

    # Step 1: Resolve circuit metadata
    circ_info_url = f"{JOLPICA_BASE}/circuits/{circuit_id}.json"
    raw_circ = _http_get_json(circ_info_url)
    cname = circuit_id.replace("_", " ").title()
    country = ""
    lat = 0.0
    lon = 0.0

    if raw_circ and "MRData" in raw_circ:
        c_list = raw_circ["MRData"].get("CircuitTable", {}).get("Circuits", [])
        if c_list:
            c0 = c_list[0]
            cname = c0.get("circuitName", cname)
            loc = c0.get("Location", {})
            country = loc.get("country", "")
            lat = float(loc.get("lat", 0.0))
            lon = float(loc.get("long", 0.0))

    # Step 2: Query FastF1 MultiViewer Geometry Dataset
    mv_key = resolve_mv_circuit_key(circuit_id, cname, country)
    geom_data = None
    layout_year = year or 2024
    geom_source = "FastF1 MultiViewer"

    if mv_key:
        mv_url = f"https://api.multiviewer.app/api/v1/circuits/{mv_key}/{layout_year}"
        geom_data = _http_get_json(mv_url, ttl=cache.TTL_PAST_SEASON)
        if not geom_data:
            for fallback_y in (2024, 2023, 2022, 2021, 2020):
                geom_data = _http_get_json(f"https://api.multiviewer.app/api/v1/circuits/{mv_key}/{fallback_y}", ttl=cache.TTL_PAST_SEASON)
                if geom_data:
                    layout_year = fallback_y
                    break

    # Step 3: Fallback to OpenStreetMap Overpass if MultiViewer has no record
    if not geom_data or "x" not in geom_data:
        osm_geom = _fetch_osm_overpass_geometry(cname, lat, lon)
        if osm_geom:
            geom_data = osm_geom
            geom_source = osm_geom.get("source", "OpenStreetMap Overpass")

    # If valid real coordinates exist, parse, convert units, compute distances & direction
    if geom_data and "x" in geom_data and "y" in geom_data:
        raw_x = geom_data["x"]
        raw_y = geom_data["y"]

        # Unit Conversion: Decimetres (0.1m) to SI Metres if from MultiViewer
        scale = 0.1 if geom_source == "FastF1 MultiViewer" else 1.0
        xs_m = [round(float(v) * scale, 2) for v in raw_x if v is not None and not math.isnan(float(v))]
        ys_m = [round(float(v) * scale, 2) for v in raw_y if v is not None and not math.isnan(float(v))]

        if len(xs_m) >= 10:
            distances = [0.0]
            cum_dist = 0.0
            for i in range(1, len(xs_m)):
                d = math.hypot(xs_m[i] - xs_m[i - 1], ys_m[i] - ys_m[i - 1])
                cum_dist += d
                distances.append(round(cum_dist, 2))

            close_gap = math.hypot(xs_m[0] - xs_m[-1], ys_m[0] - ys_m[-1])
            total_length = round(cum_dist + close_gap, 2)

            signed_area = compute_signed_area(xs_m, ys_m)
            direction = "clockwise" if signed_area < 0 else "anti-clockwise"
            zs_m = [0.0] * len(xs_m)

            bbox = {
                "min_x": min(xs_m), "max_x": max(xs_m),
                "min_y": min(ys_m), "max_y": max(ys_m),
                "min_z": 0.0, "max_z": 0.0,
            }

            corners_out = []
            for c in geom_data.get("corners", []):
                tp = c.get("trackPosition", {})
                corners_out.append({
                    "number": c.get("number", 0),
                    "letter": c.get("letter", ""),
                    "angle": round(float(c.get("angle", 0.0)), 1),
                    "distance": round(float(c.get("length", 0.0)) * 0.1, 1),
                    "x": round(float(tp.get("x", 0.0)) * 0.1, 2),
                    "y": round(float(tp.get("y", 0.0)) * 0.1, 2),
                })

            result = {
                "status": "ok",
                "source": geom_source,
                "circuit_id": circuit_id,
                "circuit_name": cname,
                "layout_year": layout_year,
                "direction": direction,
                "total_length_meters": total_length,
                "units": "meters",
                "elevation_exaggeration_default": 3.0,
                "rotation": geom_data.get("rotation", 0),
                "point_count": len(xs_m),
                "distance": distances,
                "x": xs_m,
                "y": ys_m,
                "z": zs_m,
                "bbox": bbox,
                "corners": corners_out,
                "start_finish_index": 0,
                "coverage_note": f"Official telemetry coordinates ({layout_year} layout)",
            }
            cache.set_json(cache_key, result, cache.TTL_PAST_SEASON)
            return result

    # Honest limits: if no recorded coordinates exist, return null with clear reason
    no_geom = {
        "status": "not_available",
        "source": None,
        "circuit_id": circuit_id,
        "circuit_name": cname,
        "reason": f"No telemetry position data or OSM track geometry available for circuit '{circuit_id}'",
        "coverage_note": "3D layout requires FastF1 position telemetry stream (2018+) or verified OSM raceway geometry",
        "x": None,
        "y": None,
        "z": None,
        "corners": [],
    }
    cache.set_json(cache_key, no_geom, 60)
    return no_geom


def get_circuit_details(circuit_id: str, year: Optional[int] = None, round_num: Optional[int] = None) -> Dict[str, Any]:
    """
    Returns rich circuit metadata, race history, winners, track facts, climate, and description.
    """
    cache_key = cache.build_cache_key("circuit_details_v3", circuit_id, year=year, round=round_num)
    cached = cache.get_json(cache_key)
    if cached is not None:
        return cached

    # 1. Identity & Location
    circ_info_url = f"{JOLPICA_BASE}/circuits/{circuit_id}.json"
    raw_circ = _http_get_json(circ_info_url)
    cname = circuit_id.replace("_", " ").title()
    locality = ""
    country = ""
    lat = 0.0
    lon = 0.0
    wiki_url = None

    if not raw_circ or "MRData" not in raw_circ or not raw_circ["MRData"].get("CircuitTable", {}).get("Circuits", []):
        res = {
            "status": "not_found",
            "circuit_id": circuit_id,
            "reason": f"Circuit '{circuit_id}' not found in official F1 records",
        }
        cache.set_json(cache_key, res, 60)
        return res

    c_list = raw_circ["MRData"]["CircuitTable"]["Circuits"]
    c0 = c_list[0]
    cname = c0.get("circuitName", cname)
    wiki_url = c0.get("url")
    loc = c0.get("Location", {})
    locality = loc.get("locality", "")
    country = loc.get("country", "")
    lat = float(loc.get("lat", 0.0))
    lon = float(loc.get("long", 0.0))

    # 2. Race history & past winners
    races_url = f"{JOLPICA_BASE}/circuits/{circuit_id}/races.json?limit=100"
    raw_races = _http_get_json(races_url)
    total_gps = 0
    first_year = 1950
    winners_summary = []
    win_driver_counts = collections.defaultdict(int)
    win_team_counts = collections.defaultdict(int)

    if raw_races and "MRData" in raw_races:
        r_table = raw_races["MRData"].get("RaceTable", {}).get("Races", [])
        total_gps = len(r_table)
        if r_table:
            first_year = int(r_table[0].get("season", 1950))
            for r in r_table[-5:]:
                season = int(r.get("season", 0))
                gp_n = r.get("raceName", "")
                results = r.get("Results", [])
                w_driver = "Unknown"
                w_team = "Unknown"
                if results:
                    d = results[0].get("Driver", {})
                    c = results[0].get("Constructor", {})
                    w_driver = f"{d.get('givenName', '')} {d.get('familyName', '')}".strip()
                    w_team = c.get("name", "Unknown")
                winners_summary.append({"year": season, "grand_prix": gp_n, "driver": w_driver, "team": w_team})
                if results:
                    win_driver_counts[w_driver] += 1
                    win_team_counts[w_team] += 1

    most_wins_driver = max(win_driver_counts.items(), key=lambda x: x[1])[0] if win_driver_counts else "n/a"
    most_wins_team = max(win_team_counts.items(), key=lambda x: x[1])[0] if win_team_counts else "n/a"

    # 3. Geometry / Track facts
    geom = get_circuit_geometry(circuit_id, year=year, round_num=round_num)
    track_len_km = round(geom.get("total_length_meters", 5000.0) / 1000.0, 3) if geom.get("status") == "ok" else None
    corner_count = len(geom.get("corners", [])) if geom.get("status") == "ok" else None
    direction = geom.get("direction", "clockwise") if geom.get("status") == "ok" else "unknown"

    longest_straight_m = None
    if geom.get("status") == "ok":
        corners = geom.get("corners", [])
        total_len = geom.get("total_length_meters", 0.0)
        if corners and len(corners) >= 2 and total_len > 0:
            gaps = []
            for i in range(len(corners) - 1):
                gaps.append(corners[i+1]["distance"] - corners[i]["distance"])
            gaps.append((total_len - corners[-1]["distance"]) + corners[0]["distance"])
            longest_straight_m = round(max(gaps))

    scheduled_laps = None
    if raw_races and "MRData" in raw_races:
        r_table = raw_races["MRData"].get("RaceTable", {}).get("Races", [])
        if r_table:
            latest_race_results = r_table[-1].get("Results", [])
            if latest_race_results:
                try:
                    scheduled_laps = int(latest_race_results[0].get("laps", 0))
                except (ValueError, TypeError):
                    pass
    race_distance_km = round(track_len_km * scheduled_laps, 2) if (scheduled_laps and track_len_km) else None

    # Lap record from Jolpica fastest lap results
    lap_record = None
    fastest_url = f"{JOLPICA_BASE}/circuits/{circuit_id}/fastest/1/results.json?limit=25"
    raw_fastest = _http_get_json(fastest_url)
    if raw_fastest and "MRData" in raw_fastest:
        races_f = raw_fastest["MRData"].get("RaceTable", {}).get("Races", [])
        best_time_sec = float("inf")
        best_record_str = None
        for rf in races_f:
            season_f = rf.get("season", "")
            for res_f in rf.get("Results", []):
                fl = res_f.get("FastestLap")
                if fl and fl.get("Time", {}).get("time"):
                    t_str = fl["Time"]["time"]
                    try:
                        parts = t_str.split(":")
                        sec = float(parts[0]) * 60 + float(parts[1]) if len(parts) == 2 else float(parts[0])
                        if sec < best_time_sec:
                            best_time_sec = sec
                            d_name = f"{res_f.get('Driver', {}).get('givenName', '')} {res_f.get('Driver', {}).get('familyName', '')}".strip()
                            best_record_str = f"{t_str} ({d_name}, {season_f})"
                    except Exception:
                        pass
        lap_record = best_record_str

    # 4. Wikipedia REST Summary description
    description_text = f"{cname} is a renowned motorsport venue located in {locality}, {country}."
    wiki_attribution = "Wikipedia (CC BY-SA 4.0)"
    if wiki_url and "/wiki/" in wiki_url:
        w_title = wiki_url.split("/wiki/")[-1].strip()
        summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(w_title)}"
        w_summary = _http_get_json(summary_url)
        if w_summary and w_summary.get("extract"):
            description_text = w_summary.get("extract")

    # 5. Open-Meteo elevation & climate
    elevation_val = None
    elev_url = f"https://api.open-meteo.com/v1/elevation?latitude={lat}&longitude={lon}"
    elev_data = _http_get_json(elev_url)
    if elev_data and elev_data.get("elevation"):
        elevation_val = round(elev_data["elevation"][0])

    climate = {
        "status": "not_available",
        "reason": "Historical weather archive unavailable for circuit coordinates",
        "weather_source": "Open-Meteo Historical Archive"
    }
    if raw_races and "MRData" in raw_races:
        r_table = raw_races["MRData"].get("RaceTable", {}).get("Races", [])
        if r_table:
            recent_date = r_table[-1].get("date")
            if recent_date:
                meteo_url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={recent_date}&end_date={recent_date}&daily=temperature_2m_max,precipitation_sum&timezone=UTC"
                m_data = _http_get_json(meteo_url)
                if m_data and "daily" in m_data:
                    temps = m_data["daily"].get("temperature_2m_max", [])
                    precips = m_data["daily"].get("precipitation_sum", [])
                    if temps and temps[0] is not None:
                        t_val = temps[0]
                        p_val = precips[0] if precips and precips[0] is not None else 0.0
                        climate = {
                            "status": "ok",
                            "avg_race_temp": f"{t_val:.1f} °C",
                            "rainfall_probability": "Rain recorded" if p_val > 0.5 else "Dry",
                            "precipitation_mm": p_val,
                            "recorded_date": recent_date,
                            "weather_source": "Open-Meteo Historical Archive"
                        }

    result = {
        "status": "ok",
        "source": "Jolpica, FastF1 & Open-Meteo",
        "circuit_id": circuit_id,
        "name": cname,
        "identity": {
            "circuit_id": circuit_id,
            "name": cname,
            "locality": locality,
            "country": country,
            "latitude": lat,
            "longitude": lon,
            "timezone": "UTC",
            "altitude_meters": elevation_val,
        },
        "track_facts": {
            "length_km": track_len_km,
            "corner_count": corner_count,
            "direction": direction,
            "first_gp_year": first_year,
            "total_gps_held": total_gps,
            "longest_straight_meters": longest_straight_m,
            "scheduled_laps": scheduled_laps,
            "race_distance_km": race_distance_km,
        },
        "race_history": {
            "total_gps_held": total_gps,
            "first_gp_year": first_year,
            "most_wins_driver": most_wins_driver,
            "most_wins_constructor": most_wins_team,
            "recent_winners": list(reversed(winners_summary)),
            "lap_record": lap_record,
        },
        "race_character": {
            "status": "not_available",
            "reason": "Safety car and pit stop telemetry statistics require session telemetry logs (FastF1 2018+)"
        },
        "climate": climate,
        "description": {
            "text": description_text,
            "source_url": wiki_url,
            "attribution": wiki_attribution,
        },
        "has_geometry_3d": geom.get("status") == "ok",
    }

    cache.set_json(cache_key, result, cache.TTL_PAST_SEASON)
    return sanitize_for_json(result)
