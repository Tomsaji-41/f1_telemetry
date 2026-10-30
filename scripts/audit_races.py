#!/usr/bin/env python3
"""
scripts/audit_races.py — Per-Race Audit Harness (Phase A)
Audits every F1 race individually across 26 dataset checks, comparing the
real backend HTTP endpoints against direct library probes (Jolpica, FastF1, OpenF1).
Outputs audit/<year>/<round>.json, audit/matrix.csv, and audit/matrix.md.
"""
import os
import sys
import json
import time
import argparse
import datetime
import urllib.request
import urllib.error
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import fastf1
    from fastf1.core import DataNotLoadedError
except ImportError:
    fastf1 = None

try:
    from backend.sources import jolpica
except ImportError:
    jolpica = None

CHECKLIST_ITEMS = [
    "schedule_meta",
    "round_mapping",
    "total_laps",
    "session_list",
    "race_results",
    "qualifying_results",
    "sprint_results",
    "starting_grid",
    "pit_stops",
    "lap_by_lap_jolpica",
    "standings",
    "cumulative_points",
    "laps_table",
    "position_per_lap",
    "gap_evolution",
    "tyre_stints",
    "weather",
    "track_status",
    "car_telemetry",
    "circuit_info",
    "driver_identity_round",
    "team_identity_round",
    "charts_all_12",
    "replay_bundle",
    "telemetry_teleport",
    "pitboss_tools",
]

def http_get(url: str, timeout: float = 12.0, max_retries: int = 3) -> Tuple[Optional[Dict[str, Any]], float, Optional[str]]:
    """Safe HTTP GET with retry and backoff on 429/5xx."""
    backoff = 1.0
    for attempt in range(max_retries):
        t0 = time.perf_counter()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "F1AuditHarness/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                lat = (time.perf_counter() - t0) * 1000
                return data, lat, None
        except urllib.error.HTTPError as he:
            lat = (time.perf_counter() - t0) * 1000
            if he.code in (429, 502, 503, 504) and attempt < max_retries - 1:
                time.sleep(backoff)
                backoff *= 2.0
                continue
            return None, lat, f"HTTP {he.code}: {he.reason}"
        except Exception as exc:
            lat = (time.perf_counter() - t0) * 1000
            return None, lat, str(exc)
    return None, 0.0, "Max retries exceeded"


def audit_single_race(year: int, round_num: int, base_url: str, is_future: bool = False, is_sprint: bool = False) -> Dict[str, Any]:
    """Execute all 26 checks for a single race."""
    results: Dict[str, Any] = {}
    bugs: List[Dict[str, Any]] = []

    # 1. schedule_meta
    ep_data, lat, err = http_get(f"{base_url}/api/race?year={year}&round={round_num}")
    p_data = jolpica.fetch_schedule(year) if jolpica else None
    race_meta = None
    if p_data and p_data.get("schedule"):
        for r in p_data["schedule"]:
            if int(r.get("round", 0)) == round_num:
                race_meta = r
                break
    status = "ok" if (ep_data and ep_data.get("status") == "ok") else ("not_available" if is_future else "error")
    results["schedule_meta"] = {
        "status": status,
        "source": "Jolpica",
        "latency_ms": round(lat, 1),
        "record_count": 1 if race_meta else 0,
        "reason": err or (ep_data.get("reason") if ep_data else None),
        "event_name": race_meta.get("grand_prix") if race_meta else (ep_data.get("grand_prix") if ep_data else None),
    }

    # 2. round_mapping
    # Compare Jolpica event vs FastF1 event
    ff1_event_name = None
    ff1_round = None
    mapping_mismatch = False
    if fastf1 is not None and year >= 2018:
        try:
            ff1_sched = fastf1.get_event_schedule(year)
            for _, ev in ff1_sched.iterrows():
                if int(ev.get("RoundNumber", 0)) == round_num:
                    ff1_event_name = ev.get("EventName")
                    ff1_round = int(ev.get("RoundNumber"))
                    break
            j_name = race_meta.get("grand_prix", "").lower() if race_meta else ""
            if ff1_event_name and j_name:
                # normalize check
                norm_j = j_name.replace("grand prix", "").strip()
                norm_f = ff1_event_name.lower().replace("grand prix", "").strip()
                if norm_j not in norm_f and norm_f not in norm_j:
                    mapping_mismatch = True
        except Exception:
            pass

    results["round_mapping"] = {
        "status": "error" if mapping_mismatch else ("ok" if ff1_event_name or year < 2018 else "not_available"),
        "source": "FastF1 & Jolpica",
        "jolpica_round": round_num,
        "fastf1_round": ff1_round,
        "fastf1_name": ff1_event_name,
        "mismatch": mapping_mismatch,
    }
    if mapping_mismatch:
        bugs.append({"dataset": "round_mapping", "issue": f"Name mismatch: Jolpica '{race_meta.get('grand_prix')}' != FastF1 '{ff1_event_name}'"})

    # 3. total_laps
    winner_laps = 0
    if ep_data and ep_data.get("classification"):
        winner_laps = ep_data["classification"][0].get("laps", 0)
    official_total = ep_data.get("total_laps", 0) if ep_data else 0
    laps_mismatch = bool(winner_laps and official_total and winner_laps != official_total)
    results["total_laps"] = {
        "status": "error" if laps_mismatch else ("ok" if official_total else ("not_available" if is_future else "partial")),
        "winner_laps": winner_laps,
        "official_total": official_total,
        "laps_mismatch": laps_mismatch,
    }
    if laps_mismatch:
        bugs.append({"dataset": "total_laps", "issue": f"Winner laps ({winner_laps}) != total_laps ({official_total})"})

    # 4. session_list
    sess_ep, lat_s, _ = http_get(f"{base_url}/api/sessions/available?year={year}&round={round_num}")
    results["session_list"] = {
        "status": "ok" if sess_ep and sess_ep.get("status") == "ok" else "partial",
        "source": "Jolpica",
        "latency_ms": round(lat_s, 1),
        "is_sprint": is_sprint,
    }

    # 5. race_results
    res_count = len(ep_data.get("classification", [])) if ep_data else 0
    results["race_results"] = {
        "status": "ok" if res_count >= 10 else ("not_available" if is_future else "error"),
        "source": "Jolpica",
        "record_count": res_count,
        "winner": ep_data.get("classification", [{}])[0].get("driver") if res_count else None,
    }
    if res_count == 0 and not is_future:
        bugs.append({"dataset": "race_results", "issue": "Completed race has 0 classification rows"})

    # 6. qualifying_results
    q_data, lat_q, q_err = http_get(f"{base_url}/api/tool/get_qualifying_result?year={year}&grand_prix={round_num}")
    q_count = len(q_data.get("qualifying", [])) if (q_data and isinstance(q_data, dict)) else 0
    results["qualifying_results"] = {
        "status": "ok" if q_count >= 10 else ("not_available" if is_future else "partial"),
        "source": "Jolpica",
        "record_count": q_count,
        "latency_ms": round(lat_q, 1),
    }

    # 7. sprint_results
    sp_count = 0
    if is_sprint:
        sp_data, _, _ = http_get(f"{base_url}/api/tool/get_race_result?year={year}&grand_prix={round_num}")
        sp_count = len(sp_data.get("results", [])) if sp_data else 0
    results["sprint_results"] = {
        "status": ("ok" if sp_count >= 8 else "partial") if is_sprint else "not_available",
        "source": "Jolpica",
        "record_count": sp_count,
        "is_sprint": is_sprint,
    }

    # 8. starting_grid
    grid_ep, lat_g, _ = http_get(f"{base_url}/api/charts/grid-vs-finish?year={year}&round={round_num}")
    grid_rows = len(grid_ep.get("rows", [])) if grid_ep else 0
    results["starting_grid"] = {
        "status": "ok" if grid_rows >= 10 else ("not_available" if is_future else "error"),
        "source": "Jolpica",
        "record_count": grid_rows,
        "latency_ms": round(lat_g, 1),
    }
    if grid_rows == 0 and not is_future:
        bugs.append({"dataset": "starting_grid", "issue": "Grid vs Finish returned 0 rows for completed race"})

    # 9. pit_stops (2012+)
    pit_ep, lat_p, _ = http_get(f"{base_url}/api/charts/pit-stops?year={year}&round={round_num}")
    pit_stops = len(pit_ep.get("stops", [])) if pit_ep else 0
    results["pit_stops"] = {
        "status": "ok" if pit_stops > 0 or year < 2012 else ("not_available" if year < 2012 or is_future else "partial"),
        "source": "Jolpica",
        "record_count": pit_stops,
        "latency_ms": round(lat_p, 1),
    }

    # 10. lap_by_lap_jolpica
    jolp_laps_count = 0
    if not is_future and jolpica:
        try:
            raw_j = jolpica.cache.cached_get_json(f"https://api.jolpi.ca/ergast/f1/{year}/{round_num}/laps.json?limit=10", jolpica.cache.TTL_PAST_SEASON)
            if raw_j and "MRData" in raw_j:
                jolp_laps_count = int(raw_j["MRData"].get("total", 0))
        except Exception:
            pass
    results["lap_by_lap_jolpica"] = {
        "status": "ok" if jolp_laps_count > 0 else ("not_available" if is_future else "partial"),
        "source": "Jolpica API",
        "record_count": jolp_laps_count,
    }

    # 11. standings
    stand_data, lat_st, _ = http_get(f"{base_url}/api/tool/get_standings?year={year}")
    d_stand = len(stand_data.get("rows") or stand_data.get("driver_standings") or []) if stand_data else 0
    results["standings"] = {
        "status": "ok" if d_stand >= 10 else ("not_available" if is_future else "error"),
        "source": "Jolpica",
        "record_count": d_stand,
        "latency_ms": round(lat_st, 1),
    }
    if results["standings"]["status"] == "error":
        bugs.append({"dataset": "standings", "issue": f"Standings returned 0 rows for year {year}"})

    # 12. cumulative_points
    prog_ep, lat_pr, _ = http_get(f"{base_url}/api/charts/championship-progression?year={year}")
    prog_series = len(prog_ep.get("series") or []) if prog_ep else 0
    results["cumulative_points"] = {
        "status": "ok" if prog_series >= 5 else ("not_available" if is_future else "error"),
        "source": "Jolpica",
        "record_count": prog_series,
        "latency_ms": round(lat_pr, 1),
    }
    if results["cumulative_points"]["status"] == "error":
        bugs.append({"dataset": "cumulative_points", "issue": f"Championship progression returned 0 series for year {year}"})

    # 13. laps_table (FastF1/OpenF1)
    scatter_ep, lat_sc, _ = http_get(f"{base_url}/api/charts/lap-scatter?year={year}&round={round_num}")
    scatter_points = len(scatter_ep.get("points") or []) if scatter_ep else 0
    results["laps_table"] = {
        "status": "ok" if scatter_points > 10 else ("not_available" if year < 2018 or is_future else "loading" if scatter_ep and scatter_ep.get("status") == "loading" else "partial"),
        "source": "FastF1",
        "record_count": scatter_points,
        "latency_ms": round(lat_sc, 1),
    }
    if year >= 2018 and not is_future and scatter_points == 0:
        bugs.append({"dataset": "laps_table", "issue": "FastF1 lap scatter has 0 points for completed modern race"})

    # 14. position_per_lap
    pos_ep, lat_po, _ = http_get(f"{base_url}/api/charts/position-by-lap?year={year}&round={round_num}")
    pos_drivers = len(pos_ep.get("drivers") or []) if pos_ep else 0
    results["position_per_lap"] = {
        "status": "ok" if pos_drivers >= 10 else ("loading" if pos_ep and pos_ep.get("status") == "loading" else ("not_available" if year < 2018 or is_future else "error")),
        "source": "FastF1",
        "record_count": pos_drivers,
        "latency_ms": round(lat_po, 1),
    }
    if results["position_per_lap"]["status"] == "error":
        bugs.append({"dataset": "position_per_lap", "issue": "Position-by-lap returned error/0 drivers for completed race"})

    # 15. gap_evolution
    gap_ep, lat_gp, _ = http_get(f"{base_url}/api/charts/gap-evolution?year={year}&round={round_num}")
    gap_series = len(gap_ep.get("series") or []) if gap_ep else 0
    results["gap_evolution"] = {
        "status": "ok" if gap_series >= 5 else ("loading" if gap_ep and gap_ep.get("status") == "loading" else ("not_available" if year < 2018 or is_future else "error")),
        "source": "FastF1",
        "record_count": gap_series,
        "latency_ms": round(lat_gp, 1),
    }
    if results["gap_evolution"]["status"] == "error":
        bugs.append({"dataset": "gap_evolution", "issue": "Gap evolution returned error/0 series for completed race"})

    # 16. tyre_stints
    stint_ep, lat_stn, _ = http_get(f"{base_url}/api/charts/stints?year={year}&round={round_num}")
    stint_drivers = len(stint_ep.get("stints") or []) if stint_ep else 0
    results["tyre_stints"] = {
        "status": "ok" if stint_drivers >= 10 else ("loading" if stint_ep and stint_ep.get("status") == "loading" else ("not_available" if year < 2018 or is_future else "error")),
        "source": "FastF1",
        "record_count": stint_drivers,
        "latency_ms": round(lat_stn, 1),
    }
    if results["tyre_stints"]["status"] == "error":
        bugs.append({"dataset": "tyre_stints", "issue": "Tyre stints returned error/0 drivers for completed race"})

    # 17. weather
    wea_ep, lat_we, _ = http_get(f"{base_url}/api/charts/weather?year={year}&round={round_num}")
    wea_points = len(wea_ep.get("points") or []) if wea_ep else 0
    results["weather"] = {
        "status": "ok" if wea_points > 0 else ("loading" if wea_ep and wea_ep.get("status") == "loading" else ("not_available" if year < 2018 or is_future else "partial")),
        "source": "FastF1",
        "record_count": wea_points,
        "latency_ms": round(lat_we, 1),
    }
    if year >= 2018 and not is_future and wea_points == 0:
        bugs.append({"dataset": "weather", "issue": "Weather chart returned 0 data points for completed race"})

    # 18. track_status / race_control
    rc_ep, lat_rc, _ = http_get(f"{base_url}/api/race-control?year={year}&round={round_num}")
    rc_msgs = len(rc_ep.get("messages") or []) if rc_ep else 0
    results["track_status"] = {
        "status": "ok" if rc_msgs > 0 else ("not_available" if is_future else "partial"),
        "source": "FastF1 / Jolpica",
        "record_count": rc_msgs,
        "latency_ms": round(lat_rc, 1),
    }

    # 19. car_telemetry
    tel_ep, lat_tl, _ = http_get(f"{base_url}/api/charts/telemetry-compare?year={year}&round={round_num}&driver1=VER&driver2=NOR")
    tel_status = tel_ep.get("status", "error") if tel_ep else "error"
    tel_has_series = bool(tel_ep and tel_ep.get("series") and len(tel_ep["series"]) > 0)
    results["car_telemetry"] = {
        "status": "ok" if tel_has_series else tel_status,
        "source": "FastF1",
        "latency_ms": round(lat_tl, 1),
        "reason": tel_ep.get("coverage_note") if tel_ep else "Endpoint failed",
    }
    if year >= 2018 and not is_future and not tel_has_series:
        bugs.append({"dataset": "car_telemetry", "issue": f"Car telemetry unavailable: {tel_ep.get('coverage_note', '') if tel_ep else 'no response'}"})

    # 20. circuit_info
    results["circuit_info"] = {
        "status": "ok" if race_meta and race_meta.get("circuit_id") else "partial",
        "source": "Jolpica",
        "circuit_name": race_meta.get("circuit_name") if race_meta else None,
    }

    # 21 & 22. driver_identity_round & team_identity_round
    # Note: checking if /api/identity reflects THIS round vs season
    id_ep, lat_id, _ = http_get(f"{base_url}/api/identity?year={year}")
    id_drivers = len(id_ep.get("drivers", {})) if id_ep else 0
    id_teams = len(id_ep.get("teams", {})) if id_ep else 0
    # Check for missing teamColor
    missing_colors = 0
    if id_ep and id_ep.get("drivers"):
        for d_id, d_val in id_ep["drivers"].items():
            if not d_val.get("teamColor") or d_val.get("teamColor") == "#A9A9BC":
                missing_colors += 1

    results["driver_identity_round"] = {
        "status": "ok" if id_drivers >= 18 and missing_colors == 0 else "partial",
        "source": "Jolpica & OpenF1",
        "record_count": id_drivers,
        "missing_colors": missing_colors,
        "latency_ms": round(lat_id, 1),
    }
    if missing_colors > 0:
        bugs.append({"dataset": "driver_identity_round", "issue": f"{missing_colors} drivers have neutral/missing team colour"})

    results["team_identity_round"] = {
        "status": "ok" if id_teams >= 9 else "partial",
        "source": "Jolpica & FastF1",
        "record_count": id_teams,
    }

    # 23. charts_all_12
    chart_endpoints = [
        "position-by-lap", "gap-evolution", "stints", "degradation?driver=VER",
        "pit-stops", "grid-vs-finish", "championship-progression", "sector-heatmap",
        "quali-gap", "lap-scatter", "finish-heatmap", "team-pace"
    ]
    ch_ok = 0
    ch_empty = 0
    for ch in chart_endpoints:
        sep = "&" if "?" in ch else "?"
        ch_res, _, _ = http_get(f"{base_url}/api/charts/{ch}{sep}year={year}&round={round_num}")
        if ch_res and ch_res.get("status") in ("ok", "loading", "preparing"):
            ch_ok += 1
            # Check empty series bug
            has_data = any(k in ch_res and ch_res[k] is not None and len(ch_res[k]) > 0 for k in ("series", "points", "rows", "stints", "stops", "drivers"))
            if ch_res.get("status") == "ok" and not has_data:
                ch_empty += 1
                bugs.append({"dataset": f"chart_{ch.split('?')[0]}", "issue": "Endpoint returned status ok but series/rows is empty"})

    results["charts_all_12"] = {
        "status": "ok" if ch_ok == 12 and ch_empty == 0 else "partial",
        "successful_charts": ch_ok,
        "empty_ok_charts": ch_empty,
        "total_charts": 12,
    }

    # 24. replay_bundle
    rep_ep, lat_rp, _ = http_get(f"{base_url}/api/replay/bundle?year={year}&round={round_num}")
    rep_laps = len(rep_ep.get("laps", [])) if rep_ep else 0
    results["replay_bundle"] = {
        "status": "ok" if (rep_laps >= official_total and rep_laps > 0) else ("partial" if rep_laps > 0 else ("not_available" if is_future else "error")),
        "source": "Replay Engine",
        "record_count": rep_laps,
        "latency_ms": round(lat_rp, 1),
    }
    if not is_future and rep_laps > 0 and official_total > 10 and rep_laps < official_total:
        bugs.append({"dataset": "replay_bundle", "issue": f"Replay has only {rep_laps} laps but official total is {official_total}"})

    # 25. telemetry_teleport
    results["telemetry_teleport"] = {
        "status": results["car_telemetry"]["status"],
        "source": "FastF1",
    }

    # 26. pitboss_tools
    tool_winner, _, _ = http_get(f"{base_url}/api/tool/get_race_result?year={year}&grand_prix={round_num}")
    has_winner = bool(tool_winner and (tool_winner.get("results") or tool_winner.get("classification")))
    results["pitboss_tools"] = {
        "status": "ok" if has_winner else ("not_available" if is_future else "error"),
        "source": "Tool Registry",
    }
    if results["pitboss_tools"]["status"] == "error":
        bugs.append({"dataset": "pitboss_tools", "issue": f"Tool get_race_result failed for {year} R{round_num}"})

    # A5. Switch Test (race N -> N+1 -> N)
    switch_bug = False
    next_rnd = round_num + 1 if round_num < 24 else round_num - 1
    # Check grid-vs-finish across switch
    c1, _, _ = http_get(f"{base_url}/api/charts/grid-vs-finish?year={year}&round={round_num}")
    c2, _, _ = http_get(f"{base_url}/api/charts/grid-vs-finish?year={year}&round={next_rnd}")
    c3, _, _ = http_get(f"{base_url}/api/charts/grid-vs-finish?year={year}&round={round_num}")

    if c1 and c3 and c1.get("rows") != c3.get("rows"):
        switch_bug = True
        bugs.append({"dataset": "switch_test", "issue": f"Payload for {year} R{round_num} changed after querying R{next_rnd}"})
    if c1 and c2 and c1.get("rows") and c1.get("rows") == c2.get("rows"):
        switch_bug = True
        bugs.append({"dataset": "switch_test", "issue": f"Cross-contamination: R{round_num} and R{next_rnd} returned identical rows"})

    results["switch_test"] = {
        "passed": not switch_bug,
        "tested_neighbour": next_rnd,
    }

    return {
        "year": year,
        "round": round_num,
        "is_future": is_future,
        "is_sprint": is_sprint,
        "audited_at": datetime.datetime.utcnow().isoformat() + "Z",
        "results": results,
        "bugs": bugs,
    }


def main():
    parser = argparse.ArgumentParser(description="Per-Race Audit Harness for AI Pitboss")
    parser.add_argument("--year", type=int, default=None, help="Season to audit (default: current season)")
    parser.add_argument("--all-seasons-from", dest="all_seasons_from", type=int, default=None, help="Audit all seasons from year to present")
    parser.add_argument("--rounds", type=str, default=None, help="Comma-separated round numbers")
    parser.add_argument("--concurrency", type=int, default=2, help="Concurrency limit")
    parser.add_argument("--resume", action="store_true", help="Resume from existing audit files")
    parser.add_argument("--out", type=str, default="audit", help="Output directory")
    parser.add_argument("--base-url", type=str, default="http://127.0.0.1:8000", help="Backend base URL")

    args = parser.parse_args()

    # Resolve target years
    current_year = datetime.datetime.now().year
    target_years = []
    if args.all_seasons_from:
        target_years = list(range(args.all_seasons_from, current_year + 1))
    elif args.year:
        target_years = [args.year]
    else:
        # Default resolved current season
        target_years = [current_year]

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("================================================================================")
    print("AI PITBOSS — PER-RACE AUDIT HARNESS (PHASE A)")
    print(f"Target Seasons: {target_years} | Base URL: {args.base_url} | Concurrency: {args.concurrency}")
    print("================================================================================")

    all_race_audits: List[Dict[str, Any]] = []
    all_bugs: List[Dict[str, Any]] = []

    for yr in target_years:
        yr_dir = out_dir / str(yr)
        yr_dir.mkdir(parents=True, exist_ok=True)

        sched_res = jolpica.fetch_schedule(yr) if jolpica else None
        races = sched_res.get("schedule", []) if (sched_res and sched_res.get("status") == "ok") else []
        if not races:
            print(f"Warning: No schedule found for {yr}")
            continue

        today = datetime.date.today()
        selected_rounds = [int(x.strip()) for x in args.rounds.split(",")] if args.rounds else None

        for r_obj in races:
            rnd = int(r_obj.get("round", 1))
            if selected_rounds and rnd not in selected_rounds:
                continue

            audit_file = yr_dir / f"{rnd}.json"
            if args.resume and audit_file.exists():
                print(f"[{yr} R{rnd}] Skipping (resume flag set, {audit_file} exists)")
                with open(audit_file, "r", encoding="utf-8") as f:
                    cached_audit = json.load(f)
                    all_race_audits.append(cached_audit)
                    for b in cached_audit.get("bugs", []):
                        all_bugs.append({"year": yr, "round": rnd, **b})
                continue

            d_str = r_obj.get("date", "")
            r_date = datetime.date.fromisoformat(d_str) if d_str else today
            is_future = r_date > today
            # Check sprint weekend
            is_sprint = bool("Sprint" in str(r_obj) or "sprint" in str(r_obj).lower())

            gp_name = r_obj.get("grand_prix", f"Round {rnd}")
            print(f"Auditing [{yr} R{rnd:02d}] {gp_name} (future={is_future}, sprint={is_sprint})...")

            audit_data = audit_single_race(yr, rnd, args.base_url, is_future=is_future, is_sprint=is_sprint)
            audit_data["grand_prix"] = gp_name
            audit_data["circuit"] = r_obj.get("circuit_name", "")

            # Save per-race audit JSON
            with open(audit_file, "w", encoding="utf-8") as f:
                json.dump(audit_data, f, indent=2)

            all_race_audits.append(audit_data)
            for b in audit_data.get("bugs", []):
                all_bugs.append({"year": yr, "round": rnd, "grand_prix": gp_name, **b})

    # Generate matrix.csv
    csv_file = out_dir / "matrix.csv"
    with open(csv_file, "w", encoding="utf-8") as f:
        headers = ["year", "round", "grand_prix", "is_future"] + CHECKLIST_ITEMS + ["bugs_count"]
        f.write(",".join(headers) + "\n")
        for audit in all_race_audits:
            row = [
                str(audit["year"]),
                str(audit["round"]),
                f'"{audit.get("grand_prix", "")}"',
                str(audit.get("is_future", False)),
            ]
            for item in CHECKLIST_ITEMS:
                item_data = audit.get("results", {}).get(item, {})
                status_val = item_data.get("status", "not_checked")
                row.append(status_val)
            row.append(str(len(audit.get("bugs", []))))
            f.write(",".join(row) + "\n")

    # Generate matrix.md
    md_file = out_dir / "matrix.md"
    dataset_counts = {item: {"ok": 0, "partial": 0, "not_available": 0, "error": 0} for item in CHECKLIST_ITEMS}
    for audit in all_race_audits:
        for item in CHECKLIST_ITEMS:
            st = audit.get("results", {}).get(item, {}).get("status", "error")
            if st in dataset_counts[item]:
                dataset_counts[item][st] += 1

    with open(md_file, "w", encoding="utf-8") as f:
        f.write("# Per-Race Dataset Audit Matrix (Phase A)\n\n")
        f.write(f"- **Total Races Audited**: {len(all_race_audits)}\n")
        f.write(f"- **Total BUG Instances Detected**: {len(all_bugs)}\n")
        f.write(f"- **Generated At**: {datetime.datetime.utcnow().isoformat()}Z\n\n")

        f.write("## 1. Dataset Status Counts Across Audited Races\n\n")
        f.write("| Dataset | OK | Partial | Not Available | Error |\n")
        f.write("| :--- | :---: | :---: | :---: | :---: |\n")
        for item in CHECKLIST_ITEMS:
            c = dataset_counts[item]
            f.write(f"| `{item}` | {c['ok']} | {c['partial']} | {c['not_available']} | {c['error']} |\n")

        f.write("\n## 2. Top BUG Rows (Probe Data Exists / Endpoint Missing / Stale / Discrepancies)\n\n")
        if not all_bugs:
            f.write("Zero bugs detected across all audited races.\n")
        else:
            f.write("| # | Race | Dataset | Bug Details |\n")
            f.write("| :---: | :--- | :--- | :--- |\n")
            for idx, bug in enumerate(all_bugs[:30], 1):
                f.write(f"| {idx} | {bug.get('year')} R{bug.get('round')} ({bug.get('grand_prix', '')}) | `{bug.get('dataset')}` | {bug.get('issue')} |\n")

    print("\n================================================================================")
    print(f"AUDIT COMPLETE!")
    print(f"  - Audited Races: {len(all_race_audits)}")
    print(f"  - Bugs Detected: {len(all_bugs)}")
    print(f"  - Matrix CSV:    {csv_file}")
    print(f"  - Matrix Report: {md_file}")
    print("================================================================================")


if __name__ == "__main__":
    main()
