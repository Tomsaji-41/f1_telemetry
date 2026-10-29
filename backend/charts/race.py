"""
backend/charts/race.py
FastF1-backed chart builders for a single race session.
Every function takes a loaded FastF1 Session and returns a plain dict.
Never raises on missing/empty data — returns envelope with status "empty".
"""
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

try:
    from backend import config
except ImportError:
    import config

from .common import (
    clean_laps,
    drivers_meta,
    envelope,
    ms,
    secs,
    track_annotations,
)


# ---------------------------------------------------------------------------
# Position by lap (bump chart)
# ---------------------------------------------------------------------------

def position_by_lap(
    session, drivers: Optional[List[str]] = None
) -> Dict[str, Any]:
    try:
        laps = session.laps
        if laps is None or laps.empty:
            return envelope("FastF1", "empty", "No lap data for this session.")

        pos = laps.pivot_table(
            index="LapNumber", columns="Driver", values="Position", aggfunc="first"
        )

        try:
            grid = session.results.set_index("Abbreviation")["GridPosition"]
        except Exception:
            grid = pd.Series(dtype=float)

        # Default to race-finish order
        default_codes: List[str] = []
        try:
            default_codes = list(
                session.results.sort_values("Position")["Abbreviation"]
            )
        except Exception:
            default_codes = list(pos.columns)

        codes = [c for c in (drivers or default_codes) if c in pos.columns]
        if not codes:
            return envelope("FastF1", "empty", "No lap positions for this session.")

        x = [0] + [int(i) for i in pos.index]
        meta = drivers_meta(session, codes)
        series = []
        for c in codes:
            g = grid.get(c) if c in grid.index else None
            try:
                first = None if (g is None or pd.isna(g) or g == 0) else int(g)
            except Exception:
                first = None
            ys = [None if pd.isna(v) else int(v) for v in pos[c]]
            series.append({"code": c, "driver": c, "x": x, "y": [first] + ys})

        return envelope(
            "FastF1",
            x=x,
            series=series,
            drivers=meta,
            driver_meta=meta,
            axes={
                "x": {"label": "Lap", "unit": ""},
                "y": {"label": "Position", "unit": ""},
            },
            annotations=track_annotations(laps),
        )
    except Exception as exc:
        return envelope("FastF1", "empty", f"position_by_lap error: {exc}")


# ---------------------------------------------------------------------------
# Gap evolution (gap to lap leader)
# ---------------------------------------------------------------------------

def gap_evolution(
    session, drivers: Optional[List[str]] = None
) -> Dict[str, Any]:
    try:
        laps = session.laps
        if laps is None or laps.empty:
            return envelope("FastF1", "empty", "No lap data for this session.")

        t = laps.pivot_table(
            index="LapNumber", columns="Driver", values="Time", aggfunc="first"
        )
        if t.empty:
            return envelope("FastF1", "empty", "No session timing data.")

        t_secs = t.apply(
            lambda col: col.dt.total_seconds() if hasattr(col, "dt") else col
        )
        gap = t_secs.sub(t_secs.min(axis=1), axis=0)

        codes = [c for c in (drivers or list(gap.columns)) if c in gap.columns]
        meta = drivers_meta(session, codes)
        series = []
        for idx, c in enumerate(codes):
            ys = [None if pd.isna(v) else round(float(v), 3) for v in gap[c]]
            valid_ys = [v for v in ys if v is not None]
            final_v = valid_ys[-1] if valid_ys else 0.0
            gap_str = "Leader" if final_v == 0.0 else f"+{final_v:.3f}s"
            series.append({
                "code": c,
                "driver": c,
                "position": idx + 1,
                "gap": gap_str,
                "gapSec": float(final_v),
                "y": ys,
            })

        return envelope(
            "FastF1",
            x=[int(i) for i in gap.index],
            series=series,
            drivers=meta,
            driver_meta=meta,
            axes={
                "x": {"label": "Lap", "unit": ""},
                "y": {"label": "Gap to lap leader", "unit": "s", "invert": True},
            },
            annotations=track_annotations(laps),
        )
    except Exception as exc:
        return envelope("FastF1", "empty", f"gap_evolution error: {exc}")


# ---------------------------------------------------------------------------
# Lap scatter
# ---------------------------------------------------------------------------

def lap_scatter(
    session, drivers: Optional[List[str]] = None
) -> Dict[str, Any]:
    try:
        raw = session.laps
        if raw is None or raw.empty:
            return envelope("FastF1", "empty", "No lap data for this session.")

        l = clean_laps(raw, keep_flags=True)
        if drivers:
            l = l[l["Driver"].isin(drivers)]

        pts = []
        for r in l.itertuples(index=False):
            compound = getattr(r, "Compound", None)
            tl = getattr(r, "TyreLife", None)
            pts.append(
                {
                    "lap": int(r.LapNumber),
                    "t_s": secs(r.LapTime),
                    "compound": str(compound) if compound and not pd.isna(compound) else None,
                    "tyre_life": int(tl) if tl and not pd.isna(tl) else None,
                    "code": r.Driver,
                    "is_sc": bool(getattr(r, "is_sc", False)),
                }
            )

        codes = sorted({p["code"] for p in pts})
        return envelope(
            "FastF1",
            points=pts[: config.MAX_POINTS],
            drivers=drivers_meta(session, codes),
            axes={
                "x": {"label": "Lap", "unit": ""},
                "y": {"label": "Lap time", "unit": "s"},
            },
            annotations=track_annotations(raw),
        )
    except Exception as exc:
        return envelope("FastF1", "empty", f"lap_scatter error: {exc}")


# ---------------------------------------------------------------------------
# Tyre stints (Gantt)
# ---------------------------------------------------------------------------

def stints(session) -> Dict[str, Any]:
    try:
        laps = session.laps
        if laps is None or (hasattr(laps, "empty") and laps.empty) or len(laps) == 0:
            return envelope("FastF1", "empty", "No lap data for this session.")

        g = (
            laps.groupby(["Driver", "Stint"])
            .agg(
                compound=("Compound", "first"),
                start_lap=("LapNumber", "min"),
                end_lap=("LapNumber", "max"),
                laps=("LapNumber", "count"),
            )
            .reset_index()
        )

        order: List[str] = []
        try:
            order = list(session.results.sort_values("Position")["Abbreviation"])
        except Exception:
            order = sorted(g["Driver"].unique().tolist())

        rows = []
        for r in g.itertuples(index=False):
            compound = str(r.compound) if r.compound and not pd.isna(r.compound) else "UNKNOWN"
            rows.append(
                {
                    "code": r.Driver,
                    "driver": r.Driver,
                    "stint": int(r.Stint),
                    "compound": compound.upper(),
                    "start_lap": int(r.start_lap),
                    "end_lap": int(r.end_lap),
                    "laps": int(r.laps),
                    "length": int(r.laps),
                }
            )

        rows.sort(
            key=lambda r: (
                order.index(r["code"]) if r["code"] in order else 99,
                r["stint"],
            )
        )

        return envelope(
            "FastF1",
            stints=rows,
            series=rows,
            order=order,
            drivers=drivers_meta(session, order),
            axes={"x": {"label": "Lap", "unit": ""}},
        )
    except Exception as exc:
        return envelope("FastF1", "empty", f"stints error: {exc}")


# ---------------------------------------------------------------------------
# Degradation (linear fit per stint)
# ---------------------------------------------------------------------------

def degradation(
    session, driver: str, stint: Optional[int] = None
) -> Dict[str, Any]:
    try:
        raw = session.laps
        if raw is None or raw.empty:
            return envelope("FastF1", "empty", "No lap data for this session.")

        l = clean_laps(raw)
        l = l[l["Driver"] == driver]

        out = []
        for s, grp in l.groupby("Stint"):
            if stint is not None and int(s) != int(stint):
                continue
            grp = grp[grp["TyreLife"].notna()].copy()
            n = len(grp)

            if n < 3:
                out.append(
                    {
                        "stint": int(s),
                        "compound": str(grp["Compound"].iloc[0]).upper() if n else "UNKNOWN",
                        "n": n,
                        "slope_s_per_lap": None,
                        "r2": None,
                        "points": [],
                        "fuel_corrected": True,
                        "low_sample": True,
                    }
                )
                continue

            x = grp["TyreLife"].to_numpy(dtype=float)
            lap_nums = grp["LapNumber"].to_numpy(dtype=float)
            # Fuel correction: each lap burned reduces lap time by FUEL_EFFECT_S_PER_LAP
            y = (
                grp["LapTime"].dt.total_seconds().to_numpy()
                + config.FUEL_EFFECT_S_PER_LAP * lap_nums
            )

            k, b = np.polyfit(x, y, 1)
            pred = k * x + b
            ss_res = float(((y - pred) ** 2).sum())
            ss_tot = float(((y - y.mean()) ** 2).sum())

            out.append(
                {
                    "stint": int(s),
                    "compound": str(grp["Compound"].iloc[0]).upper(),
                    "n": n,
                    "slope_s_per_lap": round(float(k), 4),
                    "r2": None if ss_tot == 0 else round(float(1 - ss_res / ss_tot), 3),
                    "points": [
                        {"tyre_life": float(a), "t_s": round(float(c), 3)}
                        for a, c in zip(x, y)
                    ],
                    "fuel_corrected": True,
                    "low_sample": n < 8,
                }
            )

        return envelope(
            "FastF1",
            stints=out,
            driver=driver,
            drivers=drivers_meta(session, [driver]),
            axes={
                "x": {"label": "Tyre age", "unit": "laps"},
                "y": {"label": "Lap time (fuel corrected)", "unit": "s"},
            },
        )
    except Exception as exc:
        return envelope("FastF1", "empty", f"degradation error: {exc}")


# ---------------------------------------------------------------------------
# Sector heatmap
# ---------------------------------------------------------------------------

def sector_heatmap(session) -> Dict[str, Any]:
    try:
        raw = session.laps
        if raw is None or raw.empty:
            return envelope("FastF1", "empty", "No lap data for this session.")

        l = clean_laps(raw)
        rows = []
        for drv, g in l.groupby("Driver"):
            row: Dict[str, Any] = {"code": drv}
            for i in (1, 2, 3):
                col_name = f"Sector{i}Time"
                if col_name not in g.columns:
                    row[f"s{i}_best_ms"] = None
                    row[f"s{i}_mean_ms"] = None
                    continue
                col = g[col_name].dropna()
                row[f"s{i}_best_ms"] = ms(col.min()) if len(col) else None
                row[f"s{i}_mean_ms"] = (
                    int(col.dt.total_seconds().mean() * 1000) if len(col) else None
                )
            rows.append(row)

        # Compute session-best and gap per sector
        for i in (1, 2, 3):
            vals = [r[f"s{i}_best_ms"] for r in rows if r[f"s{i}_best_ms"] is not None]
            best = min(vals) if vals else None
            for r in rows:
                v = r[f"s{i}_best_ms"]
                r[f"s{i}_gap_ms"] = (
                    None if v is None or best is None else v - best
                )
                r[f"s{i}_session_best"] = v is not None and v == best

        # Ideal lap = sum of best sectors
        for r in rows:
            parts = [r[f"s{i}_best_ms"] for i in (1, 2, 3)]
            r["ideal_ms"] = (
                None if any(p is None for p in parts) else int(sum(parts))
            )

        codes = [r["code"] for r in rows]
        return envelope(
            "FastF1",
            rows=rows,
            drivers=drivers_meta(session, codes),
        )
    except Exception as exc:
        return envelope("FastF1", "empty", f"sector_heatmap error: {exc}")


# ---------------------------------------------------------------------------
# Weather overlay
# ---------------------------------------------------------------------------

def weather(session) -> Dict[str, Any]:
    try:
        w = session.weather_data
        if w is None or w.empty:
            return envelope("FastF1", "empty", "No weather data for this session.")

        laps = session.laps
        starts = laps.groupby("LapNumber")["LapStartTime"].min().dropna()

        def lap_at(t) -> int:
            try:
                t_val = (
                    t.to_timedelta64()
                    if hasattr(t, "to_timedelta64")
                    else np.timedelta64(int(t.total_seconds() * 1e9), "ns")
                )
                return int(np.searchsorted(starts.values, t_val, side="right"))
            except Exception:
                return 0

        rows = []
        for r in w.itertuples(index=False):
            rows.append(
                {
                    "t_s": round(r.Time.total_seconds()) if hasattr(r.Time, "total_seconds") else None,
                    "lap": lap_at(r.Time),
                    "air_c": float(r.AirTemp) if not pd.isna(r.AirTemp) else None,
                    "track_c": float(r.TrackTemp) if not pd.isna(r.TrackTemp) else None,
                    "humidity": float(r.Humidity) if not pd.isna(r.Humidity) else None,
                    "rain": bool(r.Rainfall),
                    "wind_ms": float(r.WindSpeed) if not pd.isna(r.WindSpeed) else None,
                }
            )

        # Calculate rain bands (start_lap, end_lap)
        rain_bands = []
        in_rain = False
        start_lap = 0
        for r in rows:
            if r["rain"] and not in_rain:
                in_rain = True
                start_lap = r["lap"]
            elif not r["rain"] and in_rain:
                in_rain = False
                rain_bands.append({"start_lap": start_lap, "end_lap": r["lap"]})
        if in_rain:
            rain_bands.append({"start_lap": start_lap, "end_lap": rows[-1]["lap"] if rows else start_lap})

        return envelope(
            "FastF1",
            rows=rows,
            rain_bands=rain_bands,
            axes={"x": {"label": "Lap", "unit": ""}, "y": {"label": "Temperature", "unit": "°C"}}
        )
    except Exception as exc:
        if "datanotloaded" in str(exc).lower():
            return envelope("FastF1", "not_ingested", "Data not ingested yet.")
        return envelope("FastF1", "source_error", f"weather error: {exc}")


# ---------------------------------------------------------------------------
# Team pace (pace distribution & median per team)
# ---------------------------------------------------------------------------

def team_pace(session) -> Dict[str, Any]:
    try:
        laps = session.laps
        if laps is None or (hasattr(laps, "empty") and laps.empty) or len(laps) == 0:
            return envelope("FastF1", "empty", "No lap data for this session.")

        cl = clean_laps(laps)
        if cl.empty:
            return envelope("FastF1", "empty", "No valid clean laps.")

        teams: Dict[str, List[float]] = {}
        for r in cl.itertuples(index=False):
            t = getattr(r, "Team", None) or getattr(r, "TeamName", None)
            if not t or pd.isna(t):
                continue
            t_s = secs(getattr(r, "LapTime", None))
            if t_s is not None and t_s > 0:
                teams.setdefault(str(t), []).append(t_s)

        if not teams:
            return envelope("FastF1", "empty", "No team lap times available.")

        summary = []
        for team_name, times in teams.items():
            arr = np.array(times)
            med = float(np.median(arr))
            q25 = float(np.percentile(arr, 25))
            q75 = float(np.percentile(arr, 75))
            summary.append({
                "id": team_name,
                "team": team_name,
                "median_s": round(med, 3),
                "q25_s": round(q25, 3),
                "q75_s": round(q75, 3),
                "iqr_s": round(q75 - q25, 3),
                "laps_count": len(times),
                "y": [round(float(x), 3) for x in sorted(times)],
            })

        summary.sort(key=lambda x: x["median_s"])
        if summary:
            best_med = summary[0]["median_s"]
            for s in summary:
                s["gap_to_best_s"] = round(s["median_s"] - best_med, 3)

        return envelope(
            "FastF1",
            series=summary,
            axes={"y": {"label": "Lap Time", "unit": "s"}, "x": {"label": "Team", "unit": ""}},
        )
    except Exception as exc:
        if "datanotloaded" in str(exc).lower():
            return envelope("FastF1", "not_ingested", "Data not ingested yet.")
        return envelope("FastF1", "source_error", f"team_pace error: {exc}")
