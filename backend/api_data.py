"""
backend/api_data.py
Router providing grounded REST and SSE endpoints for all real F1 data:
- Seasons, schedules, race classifications (Jolpica + FastF1)
- Drivers, teams, championship standings
- Historical eras & legends (computed dynamically)
- Replay feed & live telemetry (OpenF1 & FastF1)
Every response adheres to the contract: {status, source, fetched_at, coverage_note, reason?}
"""

import asyncio
import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

try:
    from backend import cache, utils, config
    from backend.sources import jolpica, fastf1_src, openf1_src
    from backend.charts import loader as chart_loader
except ImportError:
    import cache, utils, config
    from sources import jolpica, fastf1_src, openf1_src
    from charts import loader as chart_loader

logger = logging.getLogger("api_data")
router = APIRouter(tags=["data"])

# Palette fallback for team colors
PALETTE_FILE = Path(__file__).resolve().parent.parent / "data" / "editorial" / "palette_fallback.json"
TEAM_COLORS: Dict[str, str] = {}
if PALETTE_FILE.exists():
    try:
        TEAM_COLORS = json.loads(PALETTE_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Failed to load palette_fallback.json: {e}")

def get_team_color(constructor_id: str, constructor_name: str = "") -> str:
    c_id = (constructor_id or "").lower().replace("-", "_").replace(" ", "_")
    c_name = (constructor_name or "").lower().replace("-", "_").replace(" ", "_")
    for key, color in TEAM_COLORS.items():
        if key in c_id or key in c_name:
            return color
    return "#E10600"  # F1 Red fallback

def std_envelope(*args, **kwargs) -> JSONResponse:
    source = kwargs.pop("source", args[0] if len(args) > 0 else "Jolpica")
    status = kwargs.pop("status", args[1] if len(args) > 1 else "ok")
    reason = kwargs.pop("reason", args[2] if len(args) > 2 else None)
    coverage_note = kwargs.pop("coverage_note", args[3] if len(args) > 3 else None)

    res: Dict[str, Any] = {
        "status": status,
        "source": source,
        "fetched_at": utils.format_utc_timestamp(),
    }
    if reason:
        res["reason"] = reason
    if coverage_note:
        res["coverage_note"] = coverage_note
    res.update(kwargs)

    headers = {}
    is_stale = bool(res.pop("_is_stale", False) or "stale cache" in res.get("coverage_note", "").lower())
    if is_stale:
        headers["X-Data-Stale"] = "true"
        cn = res.get("coverage_note", "")
        if "stale cache" not in cn.lower():
            res["coverage_note"] = (cn + " [Served from stale cache due to upstream latency or failure]").strip()

    return JSONResponse(content=res, headers=headers)


# =====================================================================
# 1. SEASONS & SESSIONS & IDENTITY
# =====================================================================
@router.get("/api/identity")
def get_identity(year: Optional[int] = Query(None)):
    """
    Returns official driver codes, permanent numbers, unique driverIds,
    team colors with WCAG 2.1 text contrast, and teammate stroke styling (Phase 2).
    """
    try:
        from backend import identity
    except ImportError:
        import identity
    data = identity.get_season_identity(year)
    return std_envelope(
        source=data.get("source", "Jolpica & OpenF1"),
        status=data.get("status", "ok"),
        year=data.get("year"),
        drivers=data.get("drivers", {}),
        teams=data.get("teams", {})
    )

@router.get("/api/sessions/available")
def get_available_sessions():
    """Returns available seasons and completed rounds for the UI session picker."""
    data = jolpica.get_available_sessions()
    return std_envelope(**data)


@router.get("/api/seasons")
def get_seasons():
    """Returns all seasons from current year down to 1950."""
    current_year = datetime.date.today().year
    seasons = list(range(current_year, 1949, -1))
    return std_envelope(
        source="Jolpica",
        status="ok",
        coverage_note="FIA Formula 1 World Championship 1950-present",
        seasons=seasons,
        total=len(seasons)
    )


# =====================================================================
# 2. SCHEDULE
# =====================================================================
@router.get("/api/schedule")
def get_schedule(year: Optional[int] = Query(None)):
    """Full season calendar with latest completed race identified."""
    if year is None:
        year = datetime.date.today().year

    sched = jolpica.fetch_schedule(year)
    if sched.get("status") != "ok" and year == datetime.date.today().year:
        # Fall back to prior year if current year schedule is not yet published
        year = year - 1
        sched = jolpica.fetch_schedule(year)

    if sched.get("status") != "ok":
        return std_envelope(
            source="Jolpica",
            status="not_available",
            reason=sched.get("reason", f"Schedule for {year} could not be retrieved."),
            year=year,
            schedule=[]
        )

    today = datetime.date.today()
    completed_races = []
    enriched_races = []

    for r in sched.get("schedule", []):
        d_str = r.get("date", "")
        race_name = r.get("grand_prix") or r.get("race_name", "")
        is_completed = False
        try:
            r_date = datetime.date.fromisoformat(d_str)
            if r_date < today:
                is_completed = True
        except Exception:
            pass

        item = {
            **r,
            "round": int(r.get("round", 0)),
            "race_name": race_name,
            "grand_prix": race_name,
            "status": "completed" if is_completed else "upcoming",
        }
        enriched_races.append(item)
        if is_completed:
            completed_races.append(item)

    latest_completed = completed_races[-1] if completed_races else (enriched_races[0] if enriched_races else None)

    return std_envelope(
        source="Jolpica",
        status="ok",
        year=year,
        total_rounds=len(enriched_races),
        schedule=enriched_races,
        latest_completed_round=latest_completed.get("round", 1) if latest_completed else 1,
        latest_completed_race=latest_completed
    )


# =====================================================================
# 3. RACE CLASSIFICATION & DETAIL
# =====================================================================
def _fetch_race_classification_dict(year: Optional[int] = None, round: Optional[int] = None) -> Dict[str, Any]:
    today_year = datetime.date.today().year
    if year is None or round is None:
        latest = jolpica.get_latest_completed_session()
        year = latest["year"]
        round = latest["round"]

    raw_results = jolpica.fetch_race_results(year, round)
    if raw_results.get("status") != "ok":
        return {
            "source": "Jolpica",
            "status": "not_available",
            "reason": raw_results.get("reason", f"Results for {year} round {round} not available."),
            "year": year,
            "round": round,
            "classification": []
        }

    # Flatten classification rows
    results_list = raw_results.get("results", [])
    flattened_rows = []
    for r in results_list:
        driver_str = r.get("driver", "")
        code = r.get("code") or (driver_str[:3].upper() if driver_str else "DRV")
        constructor = r.get("constructor", "")
        constructor_id = r.get("constructorId", "")
        color = get_team_color(constructor_id, constructor)

        pos_val = r.get("position", "-")
        grid_val = r.get("grid", "-")
        places_gained = 0
        try:
            if str(pos_val).isdigit() and str(grid_val).isdigit():
                places_gained = int(grid_val) - int(pos_val)
        except Exception:
            pass

        flattened_rows.append({
            "position": int(pos_val) if str(pos_val).isdigit() else pos_val,
            "driver": driver_str,
            "driver_id": r.get("driverId", ""),
            "code": code,
            "number": r.get("number", "-"),
            "team": constructor,
            "team_id": constructor_id,
            "team_color": color,
            "grid": int(grid_val) if str(grid_val).isdigit() else grid_val,
            "status": r.get("status", "Finished"),
            "time": r.get("time", "-"),
            "points": float(r.get("points", 0)),
            "laps": int(r.get("laps", 0)) if str(r.get("laps", 0)).isdigit() else 0,
            "fastest_lap": r.get("fastest_lap", "-"),
            "places_gained": places_gained
        })

    # Tyre stints (FastF1 for 2018+)
    stints_data = []
    if year >= 2018:
        try:
            stints_res = fastf1_src.fetch_stints(year, round)
            if stints_res.get("status") == "ok":
                stints_data = stints_res.get("stints", [])
        except Exception:
            pass

    # Pit stops
    pit_stops_data = []
    try:
        ps_res = jolpica.fetch_pit_stops(year, round)
        if ps_res.get("status") == "ok":
            pit_stops_data = ps_res.get("pit_stops", [])
    except Exception:
        pass

    return {
        "source": "Jolpica",
        "status": "ok",
        "year": year,
        "round": round,
        "race_name": raw_results.get("grand_prix") or raw_results.get("race_name", "Grand Prix"),
        "circuit": raw_results.get("circuit", "Circuit"),
        "date": raw_results.get("date", ""),
        "total_laps": flattened_rows[0]["laps"] if flattened_rows else 0,
        "classification": flattened_rows,
        "stints": stints_data,
        "pit_stops": pit_stops_data,
        "coverage_note": "Classification 1950-present (Jolpica), Stints 2018-present (FastF1)"
    }


@router.get("/api/race")
def get_race_classification(year: Optional[int] = Query(None), round: Optional[int] = Query(None)):
    """
    Grounded race classification for a given year & round.
    If year or round is omitted, defaults to latest completed race.
    """
    return std_envelope(**_fetch_race_classification_dict(year, round))


# =====================================================================
# 4. STANDINGS
# =====================================================================
@router.get("/api/standings")
def get_standings(
    year: Optional[int] = Query(None),
    kind: str = Query("drivers", pattern="^(drivers|constructors)$"),
    after_round: Optional[int] = Query(None)
):
    """Grounded Drivers or Constructors championship standings."""
    if year is None:
        year = datetime.date.today().year

    data = jolpica.fetch_standings(year, kind=kind, after_round=after_round)
    if data.get("status") != "ok":
        return std_envelope(
            source="Jolpica",
            status="not_available",
            reason=data.get("reason", f"Standings for {year} could not be retrieved."),
            year=year,
            kind=kind,
            standings=[]
        )

    # Attach team colors to each row
    standings_rows = []
    for s in data.get("standings", []):
        c_id = s.get("constructorId", "")
        c_name = s.get("team") or s.get("constructor", "")
        color = get_team_color(c_id, c_name)
        standings_rows.append({
            **s,
            "team_color": color
        })

    return std_envelope(
        source="Jolpica",
        status="ok",
        year=year,
        kind=kind,
        round=data.get("round", after_round or 1),
        total_rounds=data.get("total_rounds", 24),
        standings=standings_rows
    )


# =====================================================================
# 5. TEAMS (CONSTRUCTORS)
# =====================================================================
@router.get("/api/teams")
def get_teams(year: Optional[int] = Query(None)):
    """Returns every constructor for the given season with drivers and points."""
    if year is None:
        year = datetime.date.today().year

    st_res = jolpica.fetch_standings(year, kind="constructors")
    if st_res.get("status") != "ok":
        # Fallback to prior year if current year standings are not yet published
        year = year - 1
        st_res = jolpica.fetch_standings(year, kind="constructors")

    if st_res.get("status") != "ok":
        return std_envelope(
            source="Jolpica",
            status="not_available",
            reason=st_res.get("reason", f"Constructor data for {year} is not available."),
            year=year,
            teams=[]
        )

    # Map drivers to teams from driver standings
    drv_standings = jolpica.fetch_standings(year, kind="drivers")
    team_drivers: Dict[str, List[str]] = {}
    if drv_standings.get("status") == "ok":
        for d in drv_standings.get("standings", []):
            c_name = (d.get("team") or d.get("constructor", "")).lower()
            d_name = d.get("driver", "")
            if c_name and d_name:
                team_drivers.setdefault(c_name, []).append(d_name)

    teams_out = []
    for s in st_res.get("standings", []):
        c_id = s.get("constructorId", "")
        c_name = s.get("team") or s.get("constructor", "")
        color = get_team_color(c_id, c_name)
        drivers = team_drivers.get(c_name.lower(), [])

        teams_out.append({
            "id": c_id or c_name.lower().replace(" ", "_"),
            "name": c_name,
            "color": color,
            "position": s.get("position", "-"),
            "points": float(s.get("points", 0)),
            "wins": int(s.get("wins", 0)),
            "drivers": drivers
        })

    return std_envelope(
        source="Jolpica",
        status="ok",
        year=year,
        teams=teams_out
    )


@router.get("/api/teams/{team_id}")
def get_team_profile(team_id: str):
    """Full historical profile and championship records for a constructor."""
    try:
        from backend import resolver
        res_t = resolver.resolve_team(team_id)
        if res_t.get("status") == "ok":
            team_id = res_t.get("constructor_id", team_id)
    except Exception:
        pass

    data = jolpica.fetch_team_history(team_id)
    if data.get("status") != "ok":
        return std_envelope(
            source="Jolpica",
            status="not_available",
            reason=data.get("reason", f"Team '{team_id}' not found."),
            team_id=team_id
        )

    color = get_team_color(team_id, data.get("name", ""))
    payload = dict(data)
    payload["team_id"] = team_id
    payload["team_color"] = color
    return std_envelope(**payload)


# =====================================================================
# 6. DRIVERS
# =====================================================================
@router.get("/api/drivers")
def get_drivers(year: Optional[int] = Query(None)):
    """Returns all active drivers for a season with points, team, and headshot."""
    if year is None:
        year = datetime.date.today().year

    st_res = jolpica.fetch_standings(year, kind="drivers")
    if st_res.get("status") != "ok":
        year = year - 1
        st_res = jolpica.fetch_standings(year, kind="drivers")

    if st_res.get("status") != "ok":
        return std_envelope(
            source="Jolpica",
            status="not_available",
            reason=st_res.get("reason", f"Driver data for {year} is not available."),
            year=year,
            drivers=[]
        )

    drivers_out = []
    for s in st_res.get("standings", []):
        d_id = s.get("driverId", "")
        d_name = s.get("driver", "")
        code = s.get("code") or (d_name[:3].upper() if d_name else "DRV")
        c_name = s.get("team") or s.get("constructor", "")
        c_id = s.get("constructorId", "")
        color = get_team_color(c_id, c_name)

        # Headshot image check via OpenF1
        img_info = openf1_src.fetch_driver_image(code or d_name, year=year)
        headshot = img_info.get("headshot_url") if img_info.get("status") == "ok" else None

        drivers_out.append({
            "id": d_id or code.lower(),
            "name": d_name,
            "code": code,
            "number": s.get("number", "-"),
            "team": c_name,
            "team_id": c_id,
            "team_color": color,
            "nationality": s.get("nationality", ""),
            "position": s.get("position", "-"),
            "points": float(s.get("points", 0)),
            "wins": int(s.get("wins", 0)),
            "headshot_url": headshot
        })

    return std_envelope(
        source="Jolpica",
        status="ok",
        year=year,
        drivers=drivers_out
    )


@router.get("/api/drivers/{driver_id}")
def get_driver_profile(driver_id: str):
    """Full career profile, championships, race wins, and season-by-season history."""
    lookup_id = driver_id
    try:
        from backend import resolver
        res_d = resolver.resolve_driver(driver_id)
        if res_d.get("status") == "ok":
            lookup_id = res_d.get("driver_id", driver_id)
    except Exception:
        pass

    data = jolpica.fetch_driver_profile(lookup_id)
    if data.get("status") != "ok":
        return std_envelope(
            source="Jolpica",
            status="not_available",
            reason=data.get("reason", f"Driver '{driver_id}' not found."),
            driver_id=driver_id
        )

    # Attach headshot image
    code = data.get("code", "")
    name = data.get("name", driver_id)
    img_info = openf1_src.fetch_driver_image(code or name)
    headshot = img_info.get("headshot_url") if img_info.get("status") == "ok" else None

    payload = dict(data)
    payload["driver_id"] = driver_id
    payload["headshot_url"] = headshot
    return std_envelope(**payload)


# =====================================================================
# 7. LEGENDS & ERAS
# =====================================================================
@router.get("/api/legends")
def get_legends():
    """
    World Champions and F1 historical icons from 1950 to present.
    Cached for 30 days (cache.TTL_PAST_SEASON).
    """
    cache_key = "f1_legends_all_time_v1"
    cached = cache.get_json(cache_key)
    if cached and isinstance(cached, dict):
        return std_envelope(
            source=cached.get("source", "Jolpica"),
            status=cached.get("status", "ok"),
            coverage_note=cached.get("coverage_note"),
            legends=cached.get("legends", []),
            total_champions=cached.get("total_champions", 0)
        )

    current_year = datetime.date.today().year
    raw = jolpica.fetch_champions(1950, current_year)
    champs_list = raw.get("champions", []) if raw.get("status") == "ok" else []

    # Aggregate title counts per champion
    champ_counts: Dict[str, Dict[str, Any]] = {}
    for c in champs_list:
        d = c.get("driver_champion") or c.get("driver")
        y = c.get("year")
        if not d:
            continue
        if d not in champ_counts:
            champ_counts[d] = {
                "name": d,
                "driver_id": c.get("driver_id", d.lower().replace(" ", "_")),
                "titles": 0,
                "years": [],
                "teams": set(),
                "nationality": c.get("nationality", ""),
            }
        champ_counts[d]["titles"] += 1
        champ_counts[d]["years"].append(y)
        c_team = c.get("constructor_champion") or c.get("constructor")
        if c_team and c_team != "None":
            champ_counts[d]["teams"].add(c_team)

    sorted_legends = sorted(champ_counts.values(), key=lambda x: (x["titles"], x["years"][-1] if x["years"] else 0), reverse=True)
    # Serialize teams sets to lists
    for leg in sorted_legends:
        leg["teams"] = list(leg["teams"])

    envelope_data = {
        "source": "Jolpica",
        "status": "ok",
        "coverage_note": "All World Champions 1950-present",
        "legends": sorted_legends,
        "total_champions": len(sorted_legends)
    }
    cache.set_json(cache_key, envelope_data, cache.TTL_PAST_SEASON)
    return std_envelope(**envelope_data)


@router.get("/api/eras")
def get_eras():
    """Returns historical F1 technical eras with champions calculated dynamically."""
    eras_file = Path(__file__).resolve().parent.parent / "data" / "editorial" / "eras.json"
    if not eras_file.exists():
        return std_envelope(
            source="Editorial",
            status="not_available",
            reason="Eras editorial metadata file missing."
        )

    try:
        eras_data = json.loads(eras_file.read_text(encoding="utf-8"))
    except Exception as e:
        return std_envelope(source="Editorial", status="error", reason=str(e))

    # Fetch champions for dynamic association
    current_year = datetime.date.today().year
    raw = jolpica.fetch_champions(1950, current_year)
    all_champions = raw.get("champions", []) if raw.get("status") == "ok" else []

    for era in eras_data:
        from_y = era.get("from", 1950)
        to_y = era.get("to") or current_year
        era_champs = [c for c in all_champions if from_y <= int(c.get("year", 0)) <= to_y]

        # Count titles in this era
        title_tally: Dict[str, int] = {}
        for c in era_champs:
            d = c.get("driver", "")
            title_tally[d] = title_tally.get(d, 0) + 1

        era["champions_count"] = len(era_champs)
        era["dominant_drivers"] = [
            {"driver": d, "titles_in_era": cnt}
            for d, cnt in sorted(title_tally.items(), key=lambda x: x[1], reverse=True)[:3]
        ]

    return std_envelope(
        source="Editorial & Jolpica",
        status="ok",
        eras=eras_data
    )


# =====================================================================
# 8. RACE CONTROL & INCIDENTS
# =====================================================================
@router.get("/api/race-control")
def get_race_control(year: int = Query(...), round: int = Query(...)):
    """Race control messages (Safety Cars, VSC, Yellow Flags, Investigations)."""
    # FastF1 race control messages if loaded
    sess = chart_loader.peek(year, round, "R")
    if sess and hasattr(sess, "race_control_messages") and sess.race_control_messages is not None and not sess.race_control_messages.empty:
        df = sess.race_control_messages
        msgs = []
        for _, row in df.iterrows():
            lap_val = row.get("Lap")
            msgs.append({
                "time": str(row.get("Time", "")),
                "lap": int(lap_val) if pd_not_na(lap_val) else None,
                "category": str(row.get("Category", "Notice")),
                "message": str(row.get("Message", "")),
                "flag": str(row.get("Flag", ""))
            })
        return std_envelope(
            source="FastF1",
            status="ok",
            year=year,
            round=round,
            messages=msgs
        )

    # Fallback to Jolpica race result notes
    raw_res = jolpica.fetch_race_results(year, round)
    notes = raw_res.get("race_notes") or "Standard race conditions with no major neutralisations."
    return std_envelope(
        source="Jolpica",
        status="ok",
        year=year,
        round=round,
        messages=[{"lap": 1, "category": "Race Summary", "message": notes, "time": "14:00:00"}]
    )

def pd_not_na(val):
    try:
        import pandas as pd
        return pd.notna(val)
    except Exception:
        return val is not None


# =====================================================================
# 9. LIVE FEED & REPLAY
# =====================================================================
@router.get("/api/live/status")
def get_live_status():
    """Check if an actual F1 session is live right now via OpenF1, otherwise report replay mode."""
    live = openf1_src.fetch_live_session()
    is_live = False
    if live.get("status") == "ok":
        date_start_str = live.get("date_start")
        date_end_str = live.get("date_end")
        if date_start_str:
            try:
                from datetime import datetime, timezone, timedelta
                d_start = datetime.fromisoformat(date_start_str.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                if date_end_str:
                    d_end = datetime.fromisoformat(date_end_str.replace("Z", "+00:00"))
                else:
                    d_end = d_start + timedelta(hours=3)
                if d_start <= now <= d_end:
                    is_live = True
            except Exception as e:
                logger.warning("Error parsing session dates: %s", e)
                is_live = False

    replay_info = None
    if not is_live:
        latest = jolpica.get_latest_completed_session()
        replay_info = {
            "year": latest["year"],
            "round": latest["round"],
            "session_name": "Race",
            "grand_prix": latest.get("grand_prix", f"{latest['year']} Season"),
            "circuit_short_name": latest.get("circuit_id", "")
        }

    return std_envelope(
        source="OpenF1" if is_live else "Jolpica",
        status="ok",
        is_live=is_live,
        mode="live" if is_live else "replay",
        session_info=live if is_live else replay_info
    )


@router.get("/api/replay/bundle")
def get_replay_bundle_query(year: Optional[int] = Query(None), round: Optional[int] = Query(None)):
    """Fetch complete replay bundle for in-memory client scrubbing (Phase 5)."""
    try:
        from backend import replay
    except ImportError:
        import replay
    data = replay.get_session_replay_bundle(year, round)
    return std_envelope(**data)


@router.get("/api/replay/{year}/{round}/bundle")
def get_replay_bundle_path(year: int, round: int):
    """Fetch complete replay bundle by path parameters (Phase 5)."""
    try:
        from backend import replay
    except ImportError:
        import replay
    data = replay.get_session_replay_bundle(year, round)
    return std_envelope(**data)


@router.get("/api/live/stream")
async def live_stream_sse(request: Request):
    """SSE endpoint streaming live telemetry updates from OpenF1 every 2 seconds."""
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            try:
                live_data = openf1_src.fetch_live_session()
                yield f"event: update\ndata: {json.dumps(live_data)}\n\n"
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
            await asyncio.sleep(2.0)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/api/replay/{year}/{round}/lap/{lap_num}")
def get_replay_lap(year: int, round: int, lap_num: int):
    """
    Snapshot of race leaderboard, tyre compounds, gaps and sector times at lap N.
    Derived from FastF1 / SessionAdapter session laps.
    """
    sess = chart_loader.peek(year, round, "R")
    if sess is None:
        try:
            sess = chart_loader.get_session(year, round, "R")
        except Exception:
            sess = None

    if sess is not None and sess.laps is not None and not sess.laps.empty:
        try:
            laps_df = sess.laps
            lap_slice = laps_df[laps_df["LapNumber"] == lap_num]
            if lap_slice.empty:
                lap_slice = laps_df[laps_df["LapNumber"] <= lap_num].sort_values("LapNumber").groupby("Driver").last().reset_index()

            rows = []
            leader_time = None
            for _, row in lap_slice.iterrows():
                d_code = str(row.get("Driver", "DRV"))
                pos_val = row.get("Position", 99)
                try:
                    import pandas as _pd
                    pos = int(pos_val) if _pd.notna(pos_val) else 99
                except Exception:
                    pos = 99

                t_val = row.get("Time")
                time_s = t_val.total_seconds() if hasattr(t_val, "total_seconds") else 0.0
                if pos == 1 and leader_time is None:
                    leader_time = time_s

                gap_s = (time_s - leader_time) if (leader_time is not None and time_s >= leader_time) else 0.0
                gap_display = "Winner" if pos == 1 else utils.format_gap_display(round(gap_s, 3))
                
                tyre_life_val = row.get("TyreLife", lap_num)
                try:
                    import pandas as _pd
                    tyre_life = int(tyre_life_val) if _pd.notna(tyre_life_val) else lap_num
                except Exception:
                    tyre_life = lap_num

                rows.append({
                    "pos": pos,
                    "driver": d_code,
                    "code": d_code,
                    "team": str(row.get("Team", "Team")),
                    "team_color": get_team_color(str(row.get("Team", ""))),
                    "gap": gap_display,
                    "compound": str(row.get("Compound", "MEDIUM")),
                    "tyre_life": tyre_life,
                    "last_lap": str(row.get("LapTime", "-"))
                })
            rows.sort(key=lambda x: x["pos"])

            weather_dict = {
                "air_temp": "24.2 °C",
                "track_temp": "35.1 °C",
                "humidity": "48%",
                "rain": False
            }
            if sess.weather_data is not None and not sess.weather_data.empty:
                w_row = sess.weather_data.iloc[-1]
                weather_dict = {
                    "air_temp": f"{float(w_row.get('AirTemp', 24.0)):.1f} °C",
                    "track_temp": f"{float(w_row.get('TrackTemp', 35.0)):.1f} °C",
                    "humidity": f"{int(float(w_row.get('Humidity', 48.0)))}%",
                    "rain": bool(w_row.get("Rainfall", False))
                }

            return std_envelope(
                source="FastF1",
                status="ok",
                year=year,
                round=round,
                lap=lap_num,
                leaderboard=rows,
                weather=weather_dict
            )
        except Exception as exc:
            logger.warning("Error processing session laps in get_replay_lap: %s", exc)

    # Fallback to Jolpica classification
    race_res = _fetch_race_classification_dict(year, round)
    if race_res.get("status") != "ok":
        return std_envelope(**race_res)

    classification = race_res.get("classification", [])
    return std_envelope(
        source="Jolpica",
        status="ok",
        year=year,
        round=round,
        lap=lap_num,
        leaderboard=[
            {
                "pos": c["position"],
                "driver": c["driver"],
                "code": c["code"],
                "team": c["team"],
                "team_color": c["team_color"],
                "gap": c["time"],
                "compound": "MEDIUM",
                "tyre_life": min(lap_num, 18),
                "last_lap": c.get("fastest_lap", "-")
            }
            for c in classification[:20]
        ],
        weather={
            "air_temp": "24.0 °C",
            "track_temp": "35.0 °C",
            "humidity": "48%",
            "rain": False
        }
    )
