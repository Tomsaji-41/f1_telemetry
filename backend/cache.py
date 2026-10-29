import sqlite3
import time
import json
import logging
from typing import Optional, Any
from pathlib import Path
import requests

try:
    from backend import config
except ImportError:
    import config

logger = logging.getLogger("cache")

TTL_PAST_SEASON = 30 * 86400       # 30 days
TTL_CURRENT_ROUND = 86400          # 1 day
TTL_CURRENT_STANDINGS = 600        # 10 minutes
TTL_LIVE_SESSION = 2               # 2 seconds (per Phase 4.1)

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
    conn.commit()
    return conn

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
    val = get(key)
    if val is not None:
        try:
            return json.loads(val)
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
        val = json.dumps(data)
        set(key, val, ttl_seconds)
    except Exception as e:
        logger.warning(f"Cache set_json error for {key}: {e}")

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

    # Deduplicate in-flight requests for the same URL
    tlock = _get_thread_lock(cache_key)
    with tlock:
        # Double check after acquiring lock
        cached = get_json(cache_key)
        if cached is not None:
            _cache_stats["hits"] = _cache_stats.get("hits", 0) + 1
            return cached

        _cache_stats["misses"] = _cache_stats.get("misses", 0) + 1

        # Request with retry and exponential backoff for 429 / 5xx (Phase 1.7)
        max_attempts = 3
        backoff_delay = 1.0
        last_error_reason = None

        for attempt in range(1, max_attempts + 1):
            try:
                res = requests.get(url, headers=headers or {}, timeout=15)
                if res.status_code == 200:
                    data = res.json()
                    set_json(cache_key, data, ttl_seconds)
                    return data
                elif res.status_code == 429:
                    last_error_reason = "rate limited"
                    logger.warning(f"HTTP 429 Rate limited on {url} (attempt {attempt}/{max_attempts})")
                    if attempt < max_attempts:
                        time.sleep(backoff_delay)
                        backoff_delay *= 2.0
                elif res.status_code in (401, 403):
                    last_error_reason = "auth required"
                    logger.warning(f"HTTP {res.status_code} Auth required on {url}")
                    break
                elif res.status_code >= 500:
                    last_error_reason = f"upstream error {res.status_code}"
                    logger.warning(f"HTTP {res.status_code} on {url} (attempt {attempt}/{max_attempts})")
                    if attempt < max_attempts:
                        time.sleep(backoff_delay)
                        backoff_delay *= 1.5
                else:
                    last_error_reason = f"HTTP {res.status_code}"
                    logger.warning(f"HTTP {res.status_code} fetching {url}")
                    break
            except Exception as e:
                last_error_reason = str(e)
                logger.warning(f"Error fetching {url} (attempt {attempt}/{max_attempts}): {e}")
                if attempt < max_attempts:
                    time.sleep(backoff_delay)
                    backoff_delay *= 1.5

        # Fall back to stale cache if Jolpica/upstream is slow, timing out, or down
        stale_data = get_json_stale(cache_key)
        if stale_data is not None:
            logger.warning(f"Serving stale cache for {url} due to upstream failure")
            if isinstance(stale_data, dict):
                stale_data["_is_stale"] = True
            return stale_data

        if last_error_reason:
            return {
                "status": "not_available",
                "reason": f"Upstream API {last_error_reason}",
                "source": "OpenF1" if "openf1" in url else "Jolpica"
            }
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

