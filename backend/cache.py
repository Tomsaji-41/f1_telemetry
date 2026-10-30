import sqlite3
import time
import json
import logging
from typing import Optional, Any
from pathlib import Path
import requests

try:
    from backend import config, http_pool
except ImportError:
    import config
    import http_pool

logger = logging.getLogger("cache")

SCHEMA_VERSION = "v2"

TTL_PAST_SEASON = 30 * 86400       # 30 days
TTL_CURRENT_ROUND = 86400          # 1 day
TTL_CURRENT_STANDINGS = 600        # 10 minutes
TTL_PARTIAL_DATA = 60              # 1 minute for partial bundles
TTL_LIVE_SESSION = 2               # 2 seconds (per Phase 4.1)

def build_cache_key(
    source: str,
    endpoint: str,
    year: Optional[Any] = None,
    round: Optional[Any] = None,
    session: Optional[str] = None,
    params: Optional[dict] = None,
    schema_version: str = SCHEMA_VERSION,
) -> str:
    """Build a deterministic, structured multi-part cache key."""
    y = str(year) if year is not None else "_"
    r = str(round) if round is not None else "_"
    s = str(session) if session is not None else "_"
    p_str = ""
    if params:
        sorted_items = sorted((str(k), str(v)) for k, v in params.items() if v is not None)
        p_str = "&".join(f"{k}={v}" for k, v in sorted_items)
    p_part = f":{p_str}" if p_str else ""
    return f"{schema_version}:{source}:{endpoint}:{y}:{r}:{s}{p_part}"

def _get_db():
    conn = sqlite3.connect(str(config.DB_PATH), timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            key TEXT PRIMARY KEY,
            value TEXT,
            expires_at REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS race_data_status (
            year INTEGER,
            round INTEGER,
            session TEXT,
            dataset TEXT,
            status TEXT,
            records INTEGER,
            reason TEXT,
            updated_at TEXT,
            PRIMARY KEY (year, round, session, dataset)
        )
    """)
    conn.commit()
    return conn

def record_race_data_status(
    year: int,
    round_num: int,
    session: str,
    dataset: str,
    status: str,
    records: int = 0,
    reason: Optional[str] = None
) -> None:
    now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        with _get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO race_data_status
                (year, round, session, dataset, status, records, reason, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (year, round_num, session, dataset, status, records, reason, now_str))
            conn.commit()
    except Exception as exc:
        logger.warning("Failed to record race_data_status: %s", exc)

def get_race_coverage(year: int, round_num: Optional[int] = None) -> List[Dict[str, Any]]:
    try:
        with _get_db() as conn:
            cur = conn.cursor()
            if round_num is not None:
                cur.execute("""
                    SELECT year, round, session, dataset, status, records, reason, updated_at
                    FROM race_data_status
                    WHERE year = ? AND round = ?
                    ORDER BY dataset
                """, (year, round_num))
            else:
                cur.execute("""
                    SELECT year, round, session, dataset, status, records, reason, updated_at
                    FROM race_data_status
                    WHERE year = ?
                    ORDER BY round, dataset
                """, (year,))
            rows = cur.fetchall()
            return [
                {
                    "year": r[0],
                    "round": r[1],
                    "session": r[2],
                    "dataset": r[3],
                    "status": r[4],
                    "records": r[5],
                    "reason": r[6],
                    "updated_at": r[7],
                }
                for r in rows
            ]
    except Exception as exc:
        logger.warning("Failed to get race coverage: %s", exc)
        return []

def get(key: str) -> Optional[str]:
    try:
        with _get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT value, expires_at FROM cache WHERE key = ?", (key,))
            row = cur.fetchone()
            if row:
                val, expires_at = row
                if expires_at > time.time():
                    return val
    except Exception as e:
        logger.warning(f"Cache get error for {key}: {e}")
    return None

def get_stale(key: str) -> Optional[str]:
    """Retrieve raw cached value even if expired (for offline / stale fallback)."""
    try:
        with _get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT value FROM cache WHERE key = ?", (key,))
            row = cur.fetchone()
            if row:
                return row[0]
    except Exception as e:
        logger.warning(f"Cache get_stale error for {key}: {e}")
    return None

def set(key: str, value: str, ttl_seconds: float) -> None:
    try:
        http_pool.evict_l1(key)
        expires_at = time.time() + ttl_seconds
        with _get_db() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, ?)",
                (key, value, expires_at)
            )
            conn.commit()
    except Exception as e:
        logger.warning(f"Cache set error for {key}: {e}")

def get_json(key: str) -> Optional[Any]:
    # 1. Check L1 in-memory micro-cache
    l1 = http_pool.get_l1(key)
    if l1 is not None:
        if isinstance(l1, dict) and "_schema_version" in l1:
            if l1["_schema_version"] != SCHEMA_VERSION:
                http_pool.evict_l1(key)
                return None
        return l1

    # 2. Check persistent SQLite cache
    val = get(key)
    if val is not None:
        try:
            parsed = json.loads(val)
            if isinstance(parsed, dict) and "_schema_version" in parsed:
                if parsed["_schema_version"] != SCHEMA_VERSION:
                    return None
            http_pool.set_l1(key, parsed, 120.0)
            return parsed
        except Exception:
            return None
    return None

def get_json_stale(key: str) -> Optional[Any]:
    """Retrieve JSON cached value even if expired."""
    val = get_stale(key)
    if val is not None:
        try:
            return json.loads(val)
        except Exception:
            return None
    return None

def set_json(key: str, data: Any, ttl_seconds: float) -> None:
    try:
        # Prime Rule 3 & C-1: DO NOT cache errors, empty results, 'loading' state, or partial bundles with a long TTL
        if isinstance(data, dict):
            status = data.get("status")
            if status in ("error", "preparing", "loading", "empty", "source_error", "not_found") or data.get("error"):
                logger.debug(f"Refusing to cache error/loading state for {key}")
                return
            if status == "partial" or data.get("is_partial"):
                ttl_seconds = min(ttl_seconds, TTL_PARTIAL_DATA)
            # Tag schema version
            if not isinstance(data, list):
                data = dict(data)
                data["_schema_version"] = SCHEMA_VERSION
        # Update L1 and SQLite
        http_pool.set_l1(key, data, ttl_seconds)
        val = json.dumps(data)
        set(key, val, ttl_seconds)
    except Exception as e:
        logger.warning(f"Cache set_json error for {key}: {e}")

def get_or_compute_swr(
    key: str,
    compute_fn,
    fresh_ttl: float,
    stale_ttl: float = 86400.0,
) -> Any:
    """
    Stale-While-Revalidate pattern (P3):
    1. If key is fresh: return immediately.
    2. If key is stale (within stale_ttl): return stale value immediately and refresh in background.
    3. If key is missing: compute synchronously, cache, and return.
    """
    cached = get_json(key)
    if cached is not None:
        return cached

    stale = get_json_stale(key)
    if stale is not None:
        import threading
        def _bg_revalidate():
            try:
                val = compute_fn()
                if val:
                    set_json(key, val, fresh_ttl)
            except Exception as exc:
                logger.debug("Background SWR refresh error for %s: %s", key, exc)
        threading.Thread(target=_bg_revalidate, daemon=True).start()
        return stale

    # Cold miss: compute synchronously
    fresh = compute_fn()
    if fresh:
        set_json(key, fresh, fresh_ttl)
    return fresh

import threading
import asyncio

_cache_stats = {"hits": 0, "misses": 0}
_THREAD_LOCKS: dict[str, threading.Lock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()
_ASYNC_LOCKS: dict[str, asyncio.Lock] = {}

def _get_thread_lock(key: str) -> threading.Lock:
    with _THREAD_LOCKS_GUARD:
        if key not in _THREAD_LOCKS:
            _THREAD_LOCKS[key] = threading.Lock()
        return _THREAD_LOCKS[key]

def get_async_lock(key: str) -> asyncio.Lock:
    """Async lock per cache key for in-flight request deduplication."""
    if key not in _ASYNC_LOCKS:
        _ASYNC_LOCKS[key] = asyncio.Lock()
    return _ASYNC_LOCKS[key]

def start_timing_window():
    _cache_stats["hits"] = 0
    _cache_stats["misses"] = 0

def get_timing_cache_status() -> str:
    hits = _cache_stats.get("hits", 0)
    misses = _cache_stats.get("misses", 0)
    if misses > 0 and hits > 0:
        return "mixed"
    if misses > 0:
        return "miss"
    if hits > 0:
        return "hit"
    return "none"

def cached_get_json(url: str, ttl_seconds: float, headers: Optional[dict] = None) -> Optional[Any]:
    cache_key = f"http:{url}"
    cached = get_json(cache_key)
    if cached is not None:
        _cache_stats["hits"] = _cache_stats.get("hits", 0) + 1
        return cached

    _cache_stats["misses"] = _cache_stats.get("misses", 0) + 1

    # Use pooled HTTP manager with singleflight & gzip support
    data = http_pool.fetch_json_pooled(url)
    if data is not None:
        set_json(cache_key, data, ttl_seconds)
        return data

    # Fallback to requests if pooled returned None
    try:
        res = requests.get(url, headers=headers or {}, timeout=12)
        if res.status_code == 200:
            data = res.json()
            set_json(cache_key, data, ttl_seconds)
            return data
    except Exception as e:
        logger.debug("Fallback request failed for %s: %s", url, e)

    # Fall back to stale cache if Jolpica/upstream is slow, timing out, or down
    stale_data = get_json_stale(cache_key)
    if stale_data is not None:
        logger.warning(f"Serving stale cache for {url} due to upstream failure")
        if isinstance(stale_data, dict):
            stale_data["_is_stale"] = True
        return stale_data

    return None

def get_cache_stats() -> dict:
    try:
        with _get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*), SUM(LENGTH(value)) FROM cache WHERE expires_at > ?", (time.time(),))
            count, total_bytes = cur.fetchone()
            return {
                "active_entries": count or 0,
                "total_bytes": total_bytes or 0,
                "db_path": str(config.DB_PATH)
            }
    except Exception as e:
        return {"error": str(e)}

def purge_bad_entries():
    """
    Purge bad cache entries on startup (Phase 1.5):
    - Any entry with status in {'error', 'preparing', 'loading', 'empty', 'source_error'}
    - Any entry containing explicit errors or empty series
    - Any expired entries
    """
    try:
        with _get_db() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM cache WHERE expires_at <= ?", (time.time(),))
            cur.execute("SELECT key, value FROM cache")
            rows = cur.fetchall()
            keys_to_delete = []
            for key, val in rows:
                if not val or not val.strip():
                    keys_to_delete.append(key)
                    continue
                try:
                    obj = json.loads(val)
                    if isinstance(obj, dict):
                        st = obj.get("status")
                        if st in ("error", "preparing", "loading", "empty", "source_error", "not_found"):
                            keys_to_delete.append(key)
                        elif "error" in obj and obj.get("error"):
                            keys_to_delete.append(key)
                except Exception:
                    keys_to_delete.append(key)

            if keys_to_delete:
                cur.executemany("DELETE FROM cache WHERE key = ?", [(k,) for k in keys_to_delete])
                conn.commit()
                logger.info("Purged %d bad/stale cache entries on startup", len(keys_to_delete))
    except Exception as exc:
        logger.warning("Error purging bad cache entries: %s", exc)

