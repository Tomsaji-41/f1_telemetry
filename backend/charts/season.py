"""
backend/charts/season.py
Jolpica-backed chart builders — no FastF1 dependency.
Works for any year including pre-2018.
"""
from typing import Any, Dict, List, Optional

try:
    from backend import cache
    from backend.sources import jolpica as _J
except ImportError:
    import cache
    from sources import jolpica as _J

from .common import envelope, parse_lap_str


# ---------------------------------------------------------------------------
# Internal Jolpica helpers
# These adapt the existing jolpica.py response shapes to the raw data
# expected by the chart builders.
# ---------------------------------------------------------------------------

def _race_results_raw(year: int, rnd: int) -> List[Dict[str, Any]]:
    """Return raw Jolpica Results list or empty list on error."""
    resp = _J.fetch_race_results(year, rnd)
    if resp.get("status") != "ok":
        return []
    return resp.get("results", [])


def _qualifying_raw(year: int, rnd: int) -> List[Dict[str, Any]]:
    """Return raw Jolpica QualifyingResults list or empty list."""
    resp = _J.fetch_qualifying_results(year, rnd)
    if resp.get("status") != "ok":
        return []
    return resp.get("qualifying", [])


def _schedule_raw(year: int) -> List[Dict[str, Any]]:
    """Return raw schedule entries with a synthetic status field."""
    resp = _J.fetch_schedule(year)
    if resp.get("status") != "ok":
        return []
    import datetime
    today = datetime.date.today()
    rows = []
    for r in resp.get("schedule", []):
        date_str = r.get("date", "")
        try:
            race_date = datetime.date.fromisoformat(date_str)
            status = "completed" if race_date < today else "upcoming"
        except ValueError:
            status = "unknown"
        rows.append({**r, "status": status, "race_name": r.get("grand_prix", "")})
    return rows


def _standings_raw(year: int, kind: str = "drivers", after_round: Optional[int] = None) -> List[Dict[str, Any]]:
    """Return standings rows as list; normalised to have Driver.code / Constructor.constructorId."""
    resp = _J.fetch_standings(year, kind=kind, after_round=after_round)
    if resp.get("status") != "ok":
        return []

    out = []
    for row in resp.get("standings", []):
        if kind == "drivers":
            out.append({
                "Driver": {"code": row.get("code") or row.get("driver", "")},
                "points": row.get("points", 0),
            })
        else:
            out.append({
                "Constructor": {"constructorId": row.get("constructor", "")},
                "points": row.get("points", 0),
            })
    return out


def _pit_stops_raw(year: int, rnd: int) -> List[Dict[str, Any]]:
    """Return raw pit stop entries."""
    resp = _J.fetch_pit_stops(year, rnd)
    if resp.get("status") != "ok":
        return []
    return resp.get("pit_stops", [])


# ---------------------------------------------------------------------------
# Grid vs finish
# ---------------------------------------------------------------------------

def grid_vs_finish(year: int, rnd: int) -> Dict[str, Any]:
    try:
        res = _race_results_raw(year, rnd)
        if not res:
            return envelope("Jolpica", "empty", f"No race results for {year} round {rnd}.")

        rows = []
        for r in res:
            code = r.get("code") or (r.get("driver_id", "")[:3].upper() if r.get("driver_id") else "UNK")
            full_name = r.get("driver") or f"{r.get('given_name', '')} {r.get('family_name', '')}".strip() or code
            team = r.get("constructor") or r.get("constructor_name") or r.get("team") or "Unknown"
            grid_pos = r.get("grid", 0)
            finish = r.get("position")
            status = r.get("status", "")

            try:
                grid_val = int(grid_pos) if grid_pos else None
                if grid_val == 0:
                    grid_val = None  # pit-lane start → no grid position
            except (ValueError, TypeError):
                grid_val = None

            try:
                finish_val = int(finish) if finish is not None else None
            except (ValueError, TypeError):
                finish_val = None

            is_dsq = "disqualified" in status.lower()
            is_dnf = bool(status and status != "Finished" and not status.startswith("+") and not is_dsq)
            badge = "DSQ" if is_dsq else ("DNF" if is_dnf else None)

            # Retirements/DSQs are excluded from gained/lost arrows to avoid misleading large drops
            if is_dnf or is_dsq:
                delta = None
            else:
                delta = (
                    None
                    if grid_val is None or finish_val is None
                    else grid_val - finish_val  # positive = gained places
                )

            rows.append(
                {
                    "driverId": r.get("driver_id"),
                    "code": code,
                    "name": full_name,
                    "driver": full_name,
                    "team": team,
                    "grid": grid_val,
                    "finish": finish_val,
                    "delta": delta,
                    "status": status,
                    "badge": badge,
                    "is_dnf": is_dnf,
                    "is_dsq": is_dsq,
                }
            )

        return envelope("Jolpica", rows=rows, series=rows)
    except Exception as exc:
        return envelope("Jolpica", "empty", f"grid_vs_finish error: {exc}", rows=[], series=[])


# ---------------------------------------------------------------------------
# Quali gap
# ---------------------------------------------------------------------------

def quali_gap(year: int, rnd: int) -> Dict[str, Any]:
    try:
        q = _qualifying_raw(year, rnd)
        if not q:
            return envelope("Jolpica", "empty", f"No qualifying results for {year} round {rnd}.")

        rows = []
        final_grid = []
        for r in q:
            times = {
                k: parse_lap_str(r.get(k) or r.get(k.lower()))
                for k in ("Q1", "Q2", "Q3")
            }
            stage = next((k for k in ("Q3", "Q2", "Q1") if times[k]), None)
            code = r.get("code") or (r.get("driver_id", "")[:3].upper() if r.get("driver_id") else "UNK")
            full_name = f"{r.get('given_name', '')} {r.get('family_name', '')}".strip() or code
            team = r.get("constructor_name") or r.get("team") or "Unknown"
            pos_val = int(r.get("position", 0)) if r.get("position") else 0

            row_data = {
                "position": pos_val,
                "code": code,
                "name": full_name,
                "team": team,
                "stage": stage,
                "t_s": times.get(stage),
                "Q1": times["Q1"],
                "Q2": times["Q2"],
                "Q3": times["Q3"],
            }
            rows.append(row_data)
            final_grid.append({
                "position": pos_val,
                "code": code,
                "name": full_name,
                "team": team,
                "best_time_s": times.get(stage),
                "eliminated_in": stage or "Q1",
            })

        final_grid.sort(key=lambda x: x["position"] if x["position"] > 0 else 999)

        # Build segmented stage tables (Q1, Q2, Q3)
        # In each stage compare only the drivers who set a time in that stage to that stage's fastest time
        stages_data: Dict[str, List[Dict[str, Any]]] = {}
        for st in ("Q1", "Q2", "Q3"):
            st_rows = [
                {
                    "code": r["code"],
                    "name": r["name"],
                    "team": r["team"],
                    "time_s": r[st],
                }
                for r in rows
                if r[st] is not None
            ]
            st_rows.sort(key=lambda x: x["time_s"])
            if st_rows:
                fastest = st_rows[0]["time_s"]
                for entry in st_rows:
                    gap = round(entry["time_s"] - fastest, 3)
                    entry["gap_s"] = gap
                    entry["gap_str"] = f"+{gap:.3f}" if gap > 0 else "+0.000"
            stages_data[st] = st_rows

        return envelope(
            "Jolpica",
            rows=rows,
            stages=stages_data,
            final_grid=final_grid,
            axes={"y": {"label": "Gap to fastest in stage", "unit": "s"}},
        )
    except Exception as exc:
        return envelope("Jolpica", "empty", f"quali_gap error: {exc}")


# ---------------------------------------------------------------------------
# Championship progression
# ---------------------------------------------------------------------------

def championship_progression(
    year: int, kind: str = "drivers", top: int = 10
) -> Dict[str, Any]:
    from concurrent.futures import ThreadPoolExecutor

    try:
        rounds = [r for r in _schedule_raw(year) if r["status"] == "completed"]
        if not rounds:
            return envelope("Jolpica", "not_available", f"No completed rounds for {year}.")

        table: Dict[str, Dict[int, float]] = {}

        # Fetch standings concurrently across rounds
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_rnd = {
                executor.submit(_standings_raw, year, kind, int(r["round"])): int(r["round"])
                for r in rounds
            }
            for fut in future_to_rnd:
                rnd = future_to_rnd[fut]
                try:
                    standings_rows = fut.result(timeout=5.0)
                    for s in standings_rows:
                        if kind == "drivers":
                            key = s["Driver"].get("code") or ""
                        else:
                            key = s["Constructor"].get("constructorId") or ""
                        if not key:
                            continue
                        table.setdefault(key, {})[rnd] = float(s.get("points", 0))
                except Exception as e:
                    logger.warning("Error fetching standings for round %d: %s", rnd, e)

        x = [int(r["round"]) for r in rounds]
        if not x:
            return envelope("Jolpica", "not_available", "No round data.")

        last_rnd = x[-1]
        final = sorted(table, key=lambda k: -table[k].get(last_rnd, 0))[:top]
        series = [
            {
                "id": k,
                "code": k,
                "name": k,
                "points": float(table[k].get(last_rnd, 0) or 0),
                "position": idx + 1,
                "y": [table[k].get(n) for n in x]
            }
            for idx, k in enumerate(final)
        ]

        return envelope(
            "Jolpica",
            "ok",
            x=x,
            series=series,
            rounds=[r["race_name"] for r in rounds],
            axes={
                "x": {"label": "Round", "unit": ""},
                "y": {"label": "Points", "unit": "pts"},
            },
        )
    except Exception as exc:
        return envelope("Jolpica", "error", f"championship_progression error: {exc}")


# ---------------------------------------------------------------------------
# Finish heatmap
# ---------------------------------------------------------------------------

def finish_heatmap(year: int) -> Dict[str, Any]:
    from concurrent.futures import ThreadPoolExecutor

    try:
        schedule = _schedule_raw(year)
        completed_rounds = [r for r in schedule if r["status"] == "completed"]
        rows: Dict[str, Dict[int, Optional[int]]] = {}

        # Fetch race results concurrently across completed rounds
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_rnd = {
                executor.submit(_race_results_raw, year, int(r["round"])): int(r["round"])
                for r in completed_rounds
            }
            for fut in future_to_rnd:
                rnd = future_to_rnd[fut]
                try:
                    res_list = fut.result(timeout=5.0)
                    for d in res_list:
                        code = d.get("code") or d.get("driver_id", "")
                        try:
                            pos_val = int(d["position"])
                        except (ValueError, TypeError, KeyError):
                            pos_val = None
                        rows.setdefault(code, {})[rnd] = pos_val
                except Exception as e:
                    logger.warning("Error fetching results for round %d: %s", rnd, e)

        if not rows:
            return envelope("Jolpica", "not_available", f"No finish data for {year}.", rows={}, drivers=[])
        return envelope("Jolpica", "ok", rows=rows, drivers=list(rows.keys()))
    except Exception as exc:
        return envelope("Jolpica", "error", f"finish_heatmap error: {exc}", rows={}, drivers=[])
