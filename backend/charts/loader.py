"""
backend/charts/loader.py
Thread-safe FastF1 session loader with per-key locking.

A session is published to the shared registry ONLY after load() returns
successfully and access to laps/results/weather_data is verified.
peek() never returns a partial object.
"""
import logging
import threading
from typing import Dict, Optional, Tuple

logger = logging.getLogger("charts.loader")

try:
    import fastf1
    from fastf1.core import DataNotLoadedError
except ImportError:
    fastf1 = None  # type: ignore
    DataNotLoadedError = Exception

# (year, rnd, session_type, telemetry) → FastF1 Session
_REG: Dict[Tuple[int, int, str, bool], object] = {}
_LOCKS: Dict[Tuple[int, int, str, bool], threading.Lock] = {}
_GUARD = threading.Lock()


def _key(year: int, rnd: int, ident: str, telemetry: bool = False) -> Tuple[int, int, str, bool]:
    return (int(year), int(rnd), ident.upper(), bool(telemetry))


def peek(year: int, rnd: int, ident: str = "R", telemetry: bool = False):
    """Return a fully-loaded cached session or None. Never blocks, never returns partial."""
    return _REG.get(_key(year, rnd, ident, telemetry))


def get_session(year: int, rnd: int, ident: str = "R", telemetry: bool = False):
    """
    Load a FastF1 session (blocking, thread-safe).
    - One lock per (year, rnd, ident, telemetry) so concurrent requests wait.
    - Session published only after load + verification.
    - Raises RuntimeError with descriptive message on failure.
    """
    k = _key(year, rnd, ident, telemetry)

    # Fast path: already loaded
    if k in _REG:
        return _REG[k]

    # Acquire per-key lock (create if needed)
    with _GUARD:
        lock = _LOCKS.setdefault(k, threading.Lock())

    with lock:
        # Double-check: another thread may have loaded while we waited
        if k in _REG:
            return _REG[k]

        if fastf1 is None:
            raise RuntimeError("FastF1 is not installed")

        logger.info("Loading FastF1 session %s R%s %s (telemetry=%s)", year, rnd, ident, telemetry)

        try:
            ses = fastf1.get_session(year, rnd, ident)
            ses.load(
                laps=True,
                telemetry=telemetry,
                weather=True,
                messages=True,
            )
        except Exception as exc:
            logger.warning("FastF1 load failed for %s R%s %s: %s", year, rnd, ident, exc)
            raise RuntimeError(f"FastF1 load failed for {year} R{rnd} {ident}: {exc}") from exc

        # Verify access to critical data parts
        try:
            _laps = ses.laps
            _results = ses.results
            _weather = ses.weather_data
        except DataNotLoadedError as exc:
            raise RuntimeError(f"Load incomplete for {k}: {exc}") from exc

        # Verify we have meaningful lap data
        if _laps is None or len(_laps) < 10:
            raise RuntimeError(
                f"Lap data not published yet for {year} R{rnd} {ident} "
                f"(got {len(_laps) if _laps is not None else 0} laps)"
            )

        # Publish ONLY when fully loaded and verified
        _REG[k] = ses
        logger.info(
            "Published FastF1 session %s R%s %s: %d laps, %d drivers",
            year, rnd, ident,
            len(_laps),
            len(_results) if _results is not None else 0,
        )
        return ses


# Backward compat alias
load = get_session


def evict(year: int, rnd: int, ident: str = "R", telemetry: bool = False):
    """Remove a session from the cache."""
    k = _key(year, rnd, ident, telemetry)
    _REG.pop(k, None)


def warm_latest():
    """
    Warm up the cache with the latest completed race session.
    Called on startup and after auto_update. Non-fatal on error.
    """
    try:
        try:
            from backend.sources import jolpica
        except ImportError:
            from sources import jolpica

        import datetime
        current_year = datetime.date.today().year
        sched = jolpica.fetch_schedule(current_year)
        if sched.get("status") != "ok":
            return

        today = datetime.date.today()
        latest_rnd = None
        for race in reversed(sched.get("schedule", [])):
            try:
                race_date = datetime.date.fromisoformat(race.get("date", ""))
                if race_date < today:
                    latest_rnd = int(race.get("round", 0))
                    break
            except (ValueError, TypeError):
                continue

        if latest_rnd:
            logger.info("Warming cache for %s R%s", current_year, latest_rnd)
            get_session(current_year, latest_rnd, "R", telemetry=False)
    except Exception as exc:
        logger.warning("Warm-up failed (non-fatal): %s", exc)
