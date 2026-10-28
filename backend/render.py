import datetime
import json
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("render")

def format_gap(gap_str_or_num: Any) -> Optional[str]:
    if gap_str_or_num is None:
        return None
    val_s = str(gap_str_or_num).strip()
    if not val_s or val_s == "-" or "lap" in val_s.lower():
        return val_s
    if val_s.startswith("+"):
        return val_s
    try:
        f = float(val_s)
        return f"+{f:.3f}s"
    except ValueError:
        return val_s

def make_header(gp_name: str, year: int, source: Optional[str] = None) -> str:
    clean_gp = gp_name if "Grand Prix" in gp_name else f"{gp_name} Grand Prix"
    if source == "previous_turn":
        return f"Race: {clean_gp} {year} (source: previous_turn)"
    return f"Race: {clean_gp} {year}"

def render_driver_strategy(data: Dict[str, Any], gp_name: str, year: int) -> Dict[str, Any]:
    """
    Renders driver_strategy:
    Header line always: 'Race: <Grand Prix name> <year>'
    Line 1: '<Driver> (<Team>), <N> stops, finished P<pos> (<points> pts).'
    Table: Stint | Compound | Laps (start-end) | Length
    Line: 'Stops: lap A (x.xxx s), lap B (x.xxx s)'
    """
    header = make_header(gp_name, year, data.get("source"))

    driver_name = data.get("driver", "Driver")
    team_name = data.get("team", data.get("constructor", "Team"))
    pos = data.get("position", "-")
    points = data.get("points", 0)
    stops_list = data.get("pit_stops", [])
    stints_list = data.get("stints", [])
    num_stops = len(stops_list)

    # Line 1:
    line1 = f"{driver_name} ({team_name}), {num_stops} stop{'s' if num_stops != 1 else ''}, finished P{pos} ({points} pts)."

    # Rules: Stint count must equal stops + 1, else flag 'data mismatch'
    mismatch_warning = ""
    if stints_list and len(stints_list) != num_stops + 1:
        mismatch_warning = "\n*(Note: data mismatch between recorded stints and pit stops)*"

    # Count distinct compounds directly from data
    compounds_used = set()
    table_rows = []
    for s in stints_list:
        stint_num = s.get("stint", len(table_rows) + 1)
        compound = (s.get("compound") or "UNKNOWN").upper()
        compounds_used.add(compound)
        start_lap = s.get("start_lap", s.get("lap_start", 1))
        end_lap = s.get("end_lap", s.get("lap_end", start_lap))
        length = s.get("length", end_lap - start_lap + 1 if end_lap >= start_lap else 1)

        tyre_age = s.get("tyre_age_at_start", s.get("initial_age", 1))
        compound_display = compound
        if tyre_age and tyre_age > 1:
            compound_display += f" (used set, age {tyre_age})"

        table_rows.append(f"| {stint_num} | {compound_display} | {start_lap}-{end_lap} | {length} |")

    table_md = "| Stint | Compound | Laps (start-end) | Length |\n|---|---|---|---|\n" + "\n".join(table_rows) if table_rows else ""

    # Stops line:
    if stops_list:
        stop_strs = []
        for st in stops_list:
            lap = st.get("lap", "-")
            dur = st.get("duration", st.get("stop_time", "-"))
            try:
                dur_float = float(dur)
                dur_str = f"{dur_float:.3f} s"
            except (ValueError, TypeError):
                dur_str = f"{dur} s" if dur != "-" else "-"
            stop_strs.append(f"lap {lap} ({dur_str})")
        stops_line = "Stops: " + ", ".join(stop_strs)
    else:
        stops_line = "Stops: none"

    lines = [header, line1]
    if table_md:
        lines.append(table_md)
    lines.append(stops_line)
    if mismatch_warning:
        lines.append(mismatch_warning)

    markdown = "\n\n".join(lines)

    followups = [
        {"label": "Sector pace", "intent": "sector_analysis"},
        {"label": "Compare with teammate", "intent": "compare_drivers"},
        {"label": "Tyre degradation", "intent": "tyre_degradation"},
        {"label": "Full detail", "intent": "driver_strategy", "depth": "detailed"}
    ]

    return {
        "markdown": markdown,
        "followups": followups,
        "sources": ["FastF1", "Jolpica"]
    }

def render_pit_stops(data: Dict[str, Any], gp_name: str, year: int) -> Dict[str, Any]:
    header = make_header(gp_name, year, data.get("source"))
    stops = data.get("pit_stops", [])
    driver_filter = data.get("driver")

    if not stops:
        return {
            "markdown": f"{header}\n\nNo pit stop data recorded for this session.",
            "followups": [{"label": "Race Result", "intent": "race_result"}],
            "sources": ["Jolpica"]
        }

    # Driver | Stop | Lap | Duration, facts only
    rows = []
    for s in stops[:15]:
        d = s.get("driver", driver_filter or s.get("driver_id", "-"))
        stop_num = s.get("stop", 1)
        lap = s.get("lap", "-")
        dur = s.get("duration", "-")
        try:
            dur_val = f"{float(dur):.3f} s"
        except (ValueError, TypeError):
            dur_val = f"{dur} s" if dur != "-" else "-"
        rows.append(f"| {d} | {stop_num} | {lap} | {dur_val} |")

    table = "| Driver | Stop | Lap | Duration |\n|---|---|---|---|\n" + "\n".join(rows)
    md = f"{header}\n\n{table}"
    followups = [
        {"label": "Race Result", "intent": "race_result"},
        {"label": "Tyre Stints", "intent": "tyre_stints"}
    ]
    if len(stops) > 15:
        followups.append({"label": "Full pit stop list", "intent": "pit_stops", "depth": "detailed"})

    return {
        "markdown": md,
        "followups": followups,
        "sources": ["Jolpica"]
    }

def render_tyre_stints(data: Dict[str, Any], gp_name: str, year: int) -> Dict[str, Any]:
    header = make_header(gp_name, year, data.get("source"))
    stints = data.get("stints", [])

    if not stints:
        return {
            "markdown": f"{header}\n\nNo stint data recorded for this session.",
            "followups": [{"label": "Race Result", "intent": "race_result"}],
            "sources": ["FastF1"]
        }

    # Driver | Stint | Compound | Start | End | Length
    rows = []
    for s in stints[:20]:
        d = s.get("driver", "-")
        stint_num = s.get("stint", 1)
        compound = s.get("compound", "-")
        start = s.get("start_lap", 1)
        end = s.get("end_lap", start)
        length = s.get("length", end - start + 1)
        rows.append(f"| {d} | {stint_num} | {compound} | {start} | {end} | {length} |")

    table = "| Driver | Stint | Compound | Start | End | Length |\n|---|---|---|---|---|---|\n" + "\n".join(rows)
    md = f"{header}\n\n{table}"
    return {
        "markdown": md,
        "followups": [
            {"label": "Pit Stops", "intent": "pit_stops"},
            {"label": "Sector pace", "intent": "sector_analysis"}
        ],
        "sources": ["FastF1"]
    }

def render_winner_or_result(data: Dict[str, Any], gp_name: str, year: int, full_detail: bool = False) -> Dict[str, Any]:
    clean_gp = gp_name if "Grand Prix" in gp_name else f"{gp_name} Grand Prix"
    header = make_header(gp_name, year, data.get("source"))
    results = data.get("results", [])

    if not results:
        return {
            "markdown": f"{header}\n\nNo race classification available.",
            "followups": [{"label": "Schedule", "intent": "schedule"}],
            "sources": ["Jolpica"]
        }

    winner = results[0]
    w_name = winner.get("driver", "Winner")
    w_team = winner.get("constructor", "")
    w_time = winner.get("time", "")

    headline = f"**{w_name}** ({w_team}) won the {clean_gp} {year}"
    if w_time and w_time != "-":
        headline += f" in {w_time}."
    else:
        headline += "."

    limit = 10 if full_detail else 5
    rows = []
    for r in results[:limit]:
        p = r.get("position", "-")
        d = r.get("driver", "-")
        c = r.get("constructor", "-")
        t = r.get("time", "-")
        pts = r.get("points", 0)
        rows.append(f"| P{p} | {d} | {c} | {t} | {pts} |")

    table = "| Pos | Driver | Team | Time / Gap | Pts |\n|---|---|---|---|---|\n" + "\n".join(rows)
    lines = [header, headline, table]

    # Check for shortened race notes
    race_notes = data.get("race_notes")
    if race_notes:
        lines.append(f"*(Note: {race_notes})*")

    followups = [
        {"label": "Pit stops", "intent": "pit_stops"},
        {"label": "Tyre stints", "intent": "tyre_stints"}
    ]
    if not full_detail and len(results) > 5:
        followups.insert(0, {"label": "Full detail (Top 10)", "intent": "race_result", "depth": "detailed"})

    return {
        "markdown": "\n\n".join(lines),
        "followups": followups,
        "sources": ["Jolpica"]
    }

def render_standings(data: Dict[str, Any], year: int, kind: str = "drivers", full_table: bool = False) -> Dict[str, Any]:
    kind_clean = "Constructors" if "constructor" in kind.lower() else "Drivers"
    header = f"World {kind_clean} Championship Standings {year}"
    standings = data.get("rows", data.get("standings", []))
    round_num = data.get("round", data.get("after_round", data.get("season", "-")))
    total_rounds = data.get("total_rounds", "-")
    fetched_at = datetime.datetime.now().strftime("%H:%M")

    if not standings:
        return {
            "markdown": f"**{header}**\n\nNo standings data available for {year}.",
            "followups": [{"label": "Schedule", "value": {"intent": "schedule", "slots": {"year": year}}, "action": "followup"}],
            "sources": ["Jolpica"]
        }

    limit = len(standings) if full_table else 10
    rows = []
    if kind_clean == "Drivers":
        for s in standings[:limit]:
            pos = s.get("position", s.get("pos", "-"))
            d = s.get("driver", "-")
            c = s.get("team", s.get("constructor", "n/a"))
            if not c or c == "-":
                c = "n/a"
            pts = float(s.get("points", 0))
            pts_val = int(pts) if pts == int(pts) else pts
            wins = s.get("wins", 0)
            rows.append(f"| P{pos} | {d} | {c} | {pts_val} | {wins} |")
        table = "| Pos | Driver | Team | Pts | Wins |\n|---|---|---|---|---|\n" + "\n".join(rows)
    else:
        for s in standings[:limit]:
            pos = s.get("position", s.get("pos", "-"))
            c = s.get("team", s.get("constructor", "n/a"))
            if not c or c == "-":
                c = "n/a"
            pts = float(s.get("points", 0))
            pts_val = int(pts) if pts == int(pts) else pts
            wins = s.get("wins", 0)
            rows.append(f"| P{pos} | {c} | {pts_val} | {wins} |")
        table = "| Pos | Team | Pts | Wins |\n|---|---|---|---|\n" + "\n".join(rows)

    footer = f"After round {round_num} of {total_rounds}, fetched {fetched_at}."
    md = f"**{header}**\n\n{table}\n\n{footer}"

    followups = []
    if not full_table and len(standings) > 10:
        followups.append({
            "label": "Full table",
            "value": json.dumps({"intent": "standings", "slots": {"year": year, "kind": kind, "depth": "full"}}),
            "action": "followup"
        })
    alt_kind = "constructors" if kind_clean == "Drivers" else "drivers"
    followups.append({
        "label": f"{alt_kind.capitalize()} standings",
        "value": json.dumps({"intent": "standings", "slots": {"year": year, "kind": alt_kind}}),
        "action": "followup"
    })

    return {
        "markdown": md,
        "followups": followups,
        "sources": ["Jolpica"]
    }

def render_circuit_info(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Renders circuit info: one sentence, no year, no round.
    Example: 'Circuit de Spa-Francorchamps is located in Stavelot, Belgium and hosted its first Formula 1 Grand Prix in 1950.'
    """
    c_name = data.get("circuit_name", "The circuit")
    loc = data.get("locality", "")
    country = data.get("country", "")
    loc_str = f" in {loc}, {country}" if loc and country else f" in {country}" if country else ""
    sentence = f"{c_name} is located{loc_str}."
    return {
        "markdown": sentence,
        "followups": [
            {"label": "Recent race results", "intent": "race_result"},
            {"label": "Schedule", "intent": "schedule"}
        ],
        "sources": ["Jolpica"]
    }

def render_driver_profile(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    driver_profile: 5 lines maximum plus a 'Full career' chip.
    """
    name = data.get("name", "Driver")
    nat = data.get("nationality", "")
    titles = data.get("world_championships", 0)
    wins = data.get("career_wins", 0)
    poles = data.get("career_poles", 0)
    podiums = data.get("career_podiums", 0)
    races = data.get("career_races", 0)
    teams = data.get("teams", [])
    teams_str = ", ".join(teams[:4]) if teams else "N/A"

    lines = [
        f"**{name}** ({nat})",
        f"• World Championships: {titles}",
        f"• Career Records: {wins} wins, {poles} poles, {podiums} podiums in {races} starts",
        f"• Teams: {teams_str}",
    ]
    md = "\n".join(lines[:5])
    return {
        "markdown": md,
        "followups": [{"label": "Full career", "intent": "driver_profile", "depth": "detailed"}],
        "sources": ["Jolpica"]
    }

def render_team_history(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    team_history: 5 lines maximum plus a 'Full career' chip.
    """
    team = data.get("name", "Constructor")
    nat = data.get("nationality", "")
    titles = data.get("championships", 0)
    wins = data.get("total_wins", 0)
    active = data.get("seasons_active", "")

    lines = [
        f"**{team}** ({nat})",
        f"• Constructor Titles: {titles}",
        f"• Race Wins: {wins}",
        f"• Active Seasons: {active}" if active else f"• Total Podiums: {data.get('total_podiums', 0)}",
    ]
    md = "\n".join(lines[:5])
    return {
        "markdown": md,
        "followups": [{"label": "Standings", "intent": "standings", "kind": "constructors"}],
        "sources": ["Jolpica"]
    }

def render_analysis_table_code(
    intent: str,
    data: Dict[str, Any],
    gp_name: str,
    year: int
) -> Tuple[str, Optional[float], Optional[float]]:
    """
    Builds the code-rendered table for analysis intents:
    tyre_degradation / sector_analysis / compare_drivers.
    Returns (table_md, delta_metric, std_error).
    """
    header = make_header(gp_name, year, data.get("source")) + "\n"

    if intent == "tyre_degradation":
        driver = data.get("driver", "Driver")
        stint = data.get("stint", 1)
        slope = data.get("fuel_corrected_deg_per_lap_s")
        r2 = data.get("r_squared")
        laps = data.get("sample_laps", 0)
        table = f"| Metric | Value |\n|---|---|\n| Driver | {driver} |\n| Stint | {stint} |\n| Fuel-Corrected Degradation | {slope:+.3f} s/lap |\n| Sample Size | {laps} laps |\n| R² | {r2:.3f} |"
        return header + table, slope, None

    elif intent == "compare_drivers":
        d1 = data.get("driver_1", "Driver 1")
        d2 = data.get("driver_2", "Driver 2")
        pace_delta = data.get("pace_delta_s")
        std_err = data.get("std_error", 0.05)
        fl_1 = data.get("fastest_lap_1", "-")
        fl_2 = data.get("fastest_lap_2", "-")
        table = f"| Comparison | {d1} | {d2} |\n|---|---|---|\n| Fastest Lap | {fl_1} | {fl_2} |\n| Pace Delta | Baseline | {pace_delta:+.3f} s/lap |"
        return header + table, pace_delta, std_err

    elif intent == "sector_analysis":
        driver = data.get("driver", "Driver")
        s1 = data.get("s1_best", "-")
        s2 = data.get("s2_best", "-")
        s3 = data.get("s3_best", "-")
        table = f"| Sector | {driver} Best |\n|---|---|\n| S1 | {s1} |\n| S2 | {s2} |\n| S3 | {s3} |"
        return header + table, None, None

    return header + str(data), None, None
