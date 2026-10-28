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
TTL_LIVE_SESSION = 15              # 15 seconds

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
                else:
                    cur.execute("DELETE FROM cache WHERE key = ?", (key,))
                    conn.commit()
    except Exception as e:
        logger.warning(f"Cache get error for {key}: {e}")
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

def set_json(key: str, data: Any, ttl_seconds: float) -> None:
    try:
        val = json.dumps(data)
        set(key, val, ttl_seconds)
    except Exception as e:
        logger.warning(f"Cache set_json error for {key}: {e}")

import threading

_cache_stats = {"hits": 0, "misses": 0}

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

    try:
        res = requests.get(url, headers=headers or {}, timeout=15)
        if res.status_code == 200:
            data = res.json()
            set_json(cache_key, data, ttl_seconds)
            return data
        else:
            logger.warning(f"HTTP {res.status_code} fetching {url}")
            return None
    except Exception as e:
        logger.warning(f"Error fetching {url}: {e}")
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
