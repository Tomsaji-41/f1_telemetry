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
            out = await run_in_threadpool(fn, ses, **kw)
            # Only cache successful results — never cache transient errors
            if out.get("status") == "ok" or ("series" in out or "points" in out or "stints" in out or "stops" in out or "drivers" in out):
                _cache.set_json(key, out, _ttl_for(year))
            return out
        except Exception as exc:
            logger.warning("Chart builder %s failed: %s", name, exc)
            return _classify_error(exc, year, rnd)

    # Kick off background load
    def _load_and_compute():
        ses = loader.get_session(year, rnd, "R", telemetry=telemetry)
        result = fn(ses, **kw)
        # Only cache successful/data results — not error/empty responses
        cacheable_statuses = {"ok"}
        has_data = any(k in result for k in ("series", "points", "stints", "stops", "drivers", "rows", "x"))
        if result.get("status") == "ok" or has_data:
            _cache.set_json(key, result, _ttl_for(year))
        return result

    job = jobs.submit(key, _load_and_compute)
    return envelope(
        "FastF1",
        "preparing",
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

@router.get("/position-by-lap")
async def r_position_by_lap(
    year: int,
    round: int,
    drivers: Optional[List[str]] = Query(None),
):
    return await run_chart(
        "position", year, round, race.position_by_lap, drivers=drivers
    )


@router.get("/gap-evolution")
async def r_gap_evolution(
    year: int,
    round: int,
    drivers: Optional[List[str]] = Query(None),
):
    return await run_chart(
        "gap", year, round, race.gap_evolution, drivers=drivers
    )


@router.get("/lap-scatter")
async def r_lap_scatter(
    year: int,
    round: int,
    drivers: Optional[List[str]] = Query(None),
):
    return await run_chart(
        "scatter", year, round, race.lap_scatter, drivers=drivers
    )


@router.get("/stints")
async def r_stints(year: int, round: int):
    return await run_chart("stints", year, round, race.stints)


@router.get("/degradation")
async def r_degradation(
    year: int,
    round: int,
    driver: str = Query(..., description="3-letter driver code, e.g. VER"),
    stint: Optional[int] = Query(None),
):
    return await run_chart(
        "degradation", year, round, race.degradation, driver=driver, stint=stint
    )


@router.get("/sector-heatmap")
async def r_sector_heatmap(year: int, round: int):
    return await run_chart("sector_heatmap", year, round, race.sector_heatmap)


@router.get("/weather")
async def r_weather(year: int, round: int):
    return await run_chart("weather", year, round, race.weather)


@router.get("/team-pace")
async def r_team_pace(year: int, round: int):
    return await run_chart("team_pace", year, round, race.team_pace)


# ── Jolpica season charts ────────────────────────────────────────────────────

@router.get("/grid-vs-finish")
async def r_grid_vs_finish(year: int, round: int):
    key = f"chart:grid_vs_finish:{year}:{round}"
    cached = _cache.get_json(key)
    if cached is not None:
        return cached
    try:
        out = await run_in_threadpool(season.grid_vs_finish, year, round)
        _cache.set_json(key, out, _ttl_for(year))
        return out
    except Exception as exc:
        logger.warning("grid_vs_finish error: %s", exc)
        return envelope("Jolpica", "source_error", str(exc))


@router.get("/quali-gap")
async def r_quali_gap(year: int, round: int):
    key = f"chart:quali_gap:{year}:{round}"
    cached = _cache.get_json(key)
    if cached is not None:
        return cached
    try:
        out = await run_in_threadpool(season.quali_gap, year, round)
        _cache.set_json(key, out, _ttl_for(year))
        return out
    except Exception as exc:
        logger.warning("quali_gap error: %s", exc)
        return envelope("Jolpica", "source_error", str(exc))


@router.get("/championship-progression")
async def r_championship_progression(
    year: int,
    kind: str = Query("drivers", pattern="^(drivers|constructors)$"),
    top: int = Query(10, ge=1, le=20),
):
    key = f"chart:champ_prog:{year}:{kind}:{top}"
    cached = _cache.get_json(key)
    if cached is not None:
        return cached
    try:
        out = await run_in_threadpool(season.championship_progression, year, kind, top)
        _cache.set_json(key, out, _ttl_for(year))
        return out
    except Exception as exc:
        logger.warning("championship_progression error: %s", exc)
        return envelope("Jolpica", "source_error", str(exc))


@router.get("/finish-heatmap")
async def r_finish_heatmap(year: int):
    key = f"chart:finish_heatmap:{year}"
    cached = _cache.get_json(key)
    if cached is not None:
        return cached
    try:
        out = await run_in_threadpool(season.finish_heatmap, year)
        _cache.set_json(key, out, _ttl_for(year))
        return out
    except Exception as exc:
        logger.warning("finish_heatmap error: %s", exc)
        return envelope("Jolpica", "source_error", str(exc))


# ── Pit stops (Jolpica + optional FastF1 enrichment) ────────────────────────

@router.get("/pit-stops")
async def r_pit_stops(year: int, round: int):
    key = f"chart:pit_stops:{year}:{round}"
    cached = _cache.get_json(key)
    if cached is not None:
        return cached

    # If session already loaded, enrich with FastF1
    ses = loader.peek(year, round, "R") if year >= 2018 else None
    try:
        out = await run_in_threadpool(pit.pit_stops, year, round, ses)
        _cache.set_json(key, out, _ttl_for(year))
        return out
    except Exception as exc:
        logger.warning("pit_stops error: %s", exc)
        return envelope("Jolpica", "source_error", str(exc))


# ── Telemetry Teleport route ────────────────────────────────────────────────

@router.get("/telemetry-compare")
async def r_telemetry_compare(
    year: int,
    round: int,
    driver1: Optional[str] = None,
    driver2: Optional[str] = None,
):
    from backend.charts import telemetry as _tel
    return await run_chart(
        "telemetry_compare",
        year,
        round,
        lambda s, **kw: _tel.build_telemetry_compare(s, year=year, rnd=round, **kw),
        telemetry=True,
        driver1=driver1,
        driver2=driver2,
    )
