"""
backend/charts/routes.py
FastAPI chart router — V7 spec.

All FastF1-backed routes (year >= 2018):
  - Respond within ~100ms with status="preparing" when cold.
  - Return "source_error" or "not_published_yet" with real message on failure.
  - Return cached result instantly on repeat requests.
  - Never expose raw exception strings to the UI.

Jolpica/pit routes call functions directly (no session needed).
"""
import json
import logging
import time
import datetime as _dt
from typing import List, Optional

from fastapi import APIRouter, Query
from starlette.concurrency import run_in_threadpool

try:
    from backend import cache as _cache
    from backend.charts import loader, jobs, race, season, pit
    from backend.charts.common import envelope
except ImportError:
    import cache as _cache
    from charts import loader, jobs, race, season, pit
    from charts.common import envelope

logger = logging.getLogger("charts.routes")

router = APIRouter(prefix="/api/charts", tags=["charts"])


def _resolve_session(year: Optional[int], rnd: Optional[int]) -> Tuple[int, int]:
    if year is None or rnd is None:
        try:
            from backend.sources import jolpica
        except ImportError:
            from sources import jolpica
        latest = jolpica.get_latest_completed_session()
        y = year if year is not None else latest["year"]
        r = rnd if rnd is not None else latest["round"]
        return y, r
    return year, rnd


# ── TTL helpers ─────────────────────────────────────────────────────────────

def _ttl_for(year: int) -> float:
    current = _dt.datetime.now().year
    if year < current:
        return _cache.TTL_PAST_SEASON
    return _cache.TTL_CURRENT_ROUND


def _classify_error(exc: Exception, year: int, rnd: int):
    """Map a loader/builder exception to a user-facing status envelope."""
    msg = str(exc)
    if "datanotloaded" in msg.lower() or "not loaded" in msg.lower():
        return envelope("FastF1", "not_ingested",
                        f"Data not ingested yet for {year} R{rnd}.")
    if "not published yet" in msg.lower() or "not available" in msg.lower():
        return envelope("FastF1", "not_published_yet",
                        f"Session data not published yet for {year} R{rnd}.")
    if "load failed" in msg.lower() or "load incomplete" in msg.lower():
        return envelope("FastF1", "source_error",
                        f"Data source error for {year} R{rnd}. Try again later.")
    return envelope("FastF1", "source_error",
                    f"Unexpected error for {year} R{rnd}. Try again later.")


# ── Core run_chart helper ───────────────────────────────────────────────────

async def run_chart(name: str, year: int, rnd: int, fn, telemetry: bool = False, **kw):
    """
    For FastF1-backed charts:
    1. Check year coverage (< 2018 → outside_coverage).
    2. Check result cache.
    3. peek() for already-loaded session → compute immediately.
    4. Otherwise submit a background load job → return "preparing".
    Builder exceptions → "source_error" or "not_ingested" envelope, never raw strings.
    """
    if year < 2018:
        return envelope(
            "FastF1",
            "outside_coverage",
            "Detailed lap data exists from 2018.",
        )

    key = f"chart:{name}:{year}:{rnd}:{json.dumps(kw, sort_keys=True, default=str)}"

    # Cache hit
    cached = _cache.get_json(key)
    if cached is not None:
        return cached

    # Session already in memory (fully loaded and verified)
    ses = loader.peek(year, rnd, "R", telemetry=telemetry)
    if ses is not None:
        try:
            t0 = time.perf_counter()
            out = await run_in_threadpool(fn, ses, **kw)
            proc_dur = time.perf_counter() - t0
            logger.info("[chart:%s] Warm session in-memory hit for %s R%s (process=%.3fs)", name, year, rnd, proc_dur)
            # Only cache successful results — never cache transient errors
            if out.get("status") == "ok" or ("series" in out or "points" in out or "stints" in out or "stops" in out or "drivers" in out):
                _cache.set_json(key, out, _ttl_for(year))
            return out
        except Exception as exc:
            logger.warning("Chart builder %s failed: %s", name, exc)
            return _classify_error(exc, year, rnd)

    # Kick off background load
    def _load_and_compute():
        t0 = time.perf_counter()
        ses = loader.get_session(year, rnd, "R", telemetry=telemetry)
        t_load = time.perf_counter() - t0

        t1 = time.perf_counter()
        result = fn(ses, **kw)
        t_proc = time.perf_counter() - t1
        t_total = time.perf_counter() - t0

        logger.info(
            "[chart:%s] Cold load timings for %s R%s: load=%.3fs, process=%.3fs, total=%.3fs",
            name, year, rnd, t_load, t_proc, t_total
        )

        # Only cache successful/data results — not error/empty responses
        cacheable_statuses = {"ok"}
        has_data = any(k in result for k in ("series", "points", "stints", "stops", "drivers", "rows", "x"))
        if result.get("status") == "ok" or has_data:
            _cache.set_json(key, result, _ttl_for(year))
        return result

    job = jobs.submit(key, _load_and_compute)
    if job.status == "done" and job.result is not None:
        return job.result
    if job.status == "error":
        return job.to_dict()
    return envelope(
        "FastF1",
        "loading",
        f"Loading {year} round {rnd} — usually ready in 20–40 s.",
        job_id=job.id,
        eta_s=job.eta_s,
    )


# ── Job status ──────────────────────────────────────────────────────────────

@router.get("/job/{job_id}", summary="Poll background chart load job")
async def job_status(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        return envelope("FastF1", "not_found", "Job not found or expired.")
    d = job.to_dict()
    # Map job errors to user-facing statuses
    if d.get("status") == "error":
        msg = d.get("error", "")
        if "datanotloaded" in msg.lower() or "not loaded" in msg.lower():
            d["status"] = "not_ingested"
        elif "not published" in msg.lower():
            d["status"] = "not_published_yet"
        else:
            d["status"] = "source_error"
        d["coverage_note"] = "Data loading failed. Try again later."
    return d


# ── FastF1 race charts ───────────────────────────────────────────────────────

@router.get("/position-changes", include_in_schema=False)
@router.get("/position-by-lap")
async def r_position_by_lap(
    year: Optional[int] = Query(None),
    round: Optional[int] = Query(None),
    drivers: Optional[List[str]] = Query(None),
):
    y, r = _resolve_session(year, round)
    return await run_chart(
        "position", y, r, race.position_by_lap, drivers=drivers
    )


@router.get("/gap-evolution")
async def r_gap_evolution(
    year: Optional[int] = Query(None),
    round: Optional[int] = Query(None),
    drivers: Optional[List[str]] = Query(None),
):
    y, r = _resolve_session(year, round)
    return await run_chart(
        "gap", y, r, race.gap_evolution, drivers=drivers
    )


@router.get("/lap-times", include_in_schema=False)
@router.get("/lap-scatter")
async def r_lap_scatter(
    year: Optional[int] = Query(None),
    round: Optional[int] = Query(None),
    drivers: Optional[List[str]] = Query(None),
):
    y, r = _resolve_session(year, round)
    return await run_chart(
        "scatter", y, r, race.lap_scatter, drivers=drivers
    )


@router.get("/tyre-gantt", include_in_schema=False)
@router.get("/stint-timeline", include_in_schema=False)
@router.get("/stints")
async def r_stints(
    year: Optional[int] = Query(None),
    round: Optional[int] = Query(None),
):
    y, r = _resolve_session(year, round)
    return await run_chart("stints", y, r, race.stints)


@router.get("/degradation")
async def r_degradation(
    driver: str = Query(..., description="3-letter driver code, e.g. VER"),
    year: Optional[int] = Query(None),
    round: Optional[int] = Query(None),
    stint: Optional[int] = Query(None),
):
    y, r = _resolve_session(year, round)
    return await run_chart(
        "degradation", y, r, race.degradation, driver=driver, stint=stint
    )


@router.get("/sector-heatmap")
async def r_sector_heatmap(
    year: Optional[int] = Query(None),
    round: Optional[int] = Query(None),
):
    y, r = _resolve_session(year, round)
    return await run_chart("sector_heatmap", y, r, race.sector_heatmap)


@router.get("/weather")
async def r_weather(
    year: Optional[int] = Query(None),
    round: Optional[int] = Query(None),
):
    y, r = _resolve_session(year, round)
    return await run_chart("weather", y, r, race.weather)


@router.get("/team-pace")
async def r_team_pace(
    year: Optional[int] = Query(None),
    round: Optional[int] = Query(None),
):
    y, r = _resolve_session(year, round)
    return await run_chart("team_pace", y, r, race.team_pace)


# ── Jolpica season charts ────────────────────────────────────────────────────

@router.get("/grid-vs-finish")
async def r_grid_vs_finish(
    year: Optional[int] = Query(None),
    round: Optional[int] = Query(None),
):
    y, r = _resolve_session(year, round)
    key = f"chart:grid_vs_finish:{y}:{r}"
    cached = _cache.get_json(key)
    if cached is not None:
        return cached
    try:
        out = await run_in_threadpool(season.grid_vs_finish, y, r)
        _cache.set_json(key, out, _ttl_for(y))
        return out
    except Exception as exc:
        logger.warning("grid_vs_finish error: %s", exc)
        return envelope("Jolpica", "source_error", str(exc))


@router.get("/quali-gap")
async def r_quali_gap(
    year: Optional[int] = Query(None),
    round: Optional[int] = Query(None),
):
    y, r = _resolve_session(year, round)
    key = f"chart:quali_gap:{y}:{r}"
    cached = _cache.get_json(key)
    if cached is not None:
        return cached
    try:
        out = await run_in_threadpool(season.quali_gap, y, r)
        _cache.set_json(key, out, _ttl_for(y))
        return out
    except Exception as exc:
        logger.warning("quali_gap error: %s", exc)
        return envelope("Jolpica", "source_error", str(exc))


@router.get("/championship-progression")
async def r_championship_progression(
    year: Optional[int] = Query(None),
    kind: str = Query("drivers", pattern="^(drivers|constructors)$"),
    top: int = Query(10, ge=1, le=20),
):
    y, _ = _resolve_session(year, None)
    key = f"chart:champ_prog:{y}:{kind}:{top}"
    cached = _cache.get_json(key)
    if cached is not None:
        return cached
    try:
        out = await run_in_threadpool(season.championship_progression, y, kind, top)
        _cache.set_json(key, out, _ttl_for(y))
        return out
    except Exception as exc:
        logger.warning("championship_progression error: %s", exc)
        return envelope("Jolpica", "source_error", str(exc))


@router.get("/finish-heatmap")
async def r_finish_heatmap(
    year: Optional[int] = Query(None),
):
    y, _ = _resolve_session(year, None)
    key = f"chart:finish_heatmap:{y}"
    cached = _cache.get_json(key)
    if cached is not None:
        return cached
    try:
        out = await run_in_threadpool(season.finish_heatmap, y)
        _cache.set_json(key, out, _ttl_for(y))
        return out
    except Exception as exc:
        logger.warning("finish_heatmap error: %s", exc)
        return envelope("Jolpica", "source_error", str(exc))


# ── Pit stops (Jolpica + optional FastF1 enrichment) ────────────────────────

@router.get("/pit-stops")
async def r_pit_stops(
    year: Optional[int] = Query(None),
    round: Optional[int] = Query(None),
):
    y, r = _resolve_session(year, round)
    key = f"chart:pit_stops:{y}:{r}"
    cached = _cache.get_json(key)
    if cached is not None:
        return cached

    ses = loader.peek(y, r, "R") if y >= 2018 else None
    try:
        out = await run_in_threadpool(pit.pit_stops, y, r, ses)
        _cache.set_json(key, out, _ttl_for(y))
        return out
    except Exception as exc:
        logger.warning("pit_stops error: %s", exc)
        return envelope("Jolpica", "source_error", str(exc))


# ── Telemetry Teleport route ────────────────────────────────────────────────

@router.get("/telemetry-compare")
async def r_telemetry_compare(
    year: Optional[int] = Query(None),
    round: Optional[int] = Query(None),
    driver1: Optional[str] = None,
    driver2: Optional[str] = None,
):
    y, r = _resolve_session(year, round)
    from backend.charts import telemetry as _tel
    return await run_chart(
        "telemetry_compare",
        y,
        r,
        lambda s, **kw: _tel.build_telemetry_compare(s, year=y, rnd=r, **kw),
        telemetry=True,
        driver1=driver1,
        driver2=driver2,
    )
