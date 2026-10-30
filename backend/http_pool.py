"""
backend/http_pool.py — High-Performance Pooled HTTP Client with Singleflight & Concurrency Control
(Phase P1 / P3)

Features:
- Connection pooling with Keep-Alive and Gzip decompression (urllib3.PoolManager)
- Per-host bounded concurrency semaphores (prevents 429 rate limit triggers)
- Request Coalescing (Singleflight): concurrent identical URLs share a single upstream network call
- In-memory L1 cache with microsecond hit latency
- Parallel batch execution helper (ThreadPoolExecutor)
"""
import gzip
import json
import logging
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Optional, List, Tuple, Callable
import urllib3
from urllib3.util import Retry

logger = logging.getLogger("http_pool")

USER_AGENT = "AI-Pitboss-F1-Telemetry/1.0 (https://github.com/f1_telemetry; telemetry@pitboss.local)"

# Setup robust connection pool with exponential backoff retries on 429/503
_retries = Retry(
    total=3,
    backoff_factor=0.3,
    status_forcelist=[429, 500, 502, 503, 504],
    raise_on_status=False,
)
_POOL = urllib3.PoolManager(
    num_pools=25,
    maxsize=40,
    retries=_retries,
    headers={
        "User-Agent": USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    },
)

# Per-host bounded concurrency semaphores
_HOST_SEMAPHORES: Dict[str, threading.Semaphore] = {
    "api.jolpi.ca": threading.Semaphore(6),
    "api.openf1.org": threading.Semaphore(6),
    "www.wikidata.org": threading.Semaphore(4),
    "commons.wikimedia.org": threading.Semaphore(4),
    "en.wikipedia.org": threading.Semaphore(6),
    "api.open-meteo.com": threading.Semaphore(4),
    "archive-api.open-meteo.com": threading.Semaphore(4),
    "api.multiviewer.app": threading.Semaphore(6),
}
_DEFAULT_SEMAPHORE = threading.Semaphore(6)

# In-memory L1 micro-cache: key -> (expire_time, json_data)
_L1_CACHE: Dict[str, Tuple[float, Any]] = {}
_L1_LOCK = threading.Lock()
_L1_MAX_ITEMS = 1000

# Singleflight in-flight request tracking
_SINGLEFLIGHT_LOCK = threading.Lock()
_IN_FLIGHT_EVENTS: Dict[str, threading.Event] = {}
_IN_FLIGHT_RESULTS: Dict[str, Any] = {}

# Global worker threadpool for parallel upstream batches
_EXECUTOR = ThreadPoolExecutor(max_workers=16, thread_name_prefix="f1_http")


def _get_host_semaphore(url: str) -> threading.Semaphore:
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.netloc.lower()
        return _HOST_SEMAPHORES.get(host, _DEFAULT_SEMAPHORE)
    except Exception:
        return _DEFAULT_SEMAPHORE


def get_l1(key: str) -> Optional[Any]:
    """Retrieve hot item from L1 in-memory cache."""
    now = time.time()
    with _L1_LOCK:
        entry = _L1_CACHE.get(key)
        if entry:
            exp, data = entry
            if now < exp:
                return data
            else:
                del _L1_CACHE[key]
    return None


def set_l1(key: str, data: Any, ttl_seconds: float = 300.0) -> None:
    """Store item in L1 in-memory cache with LRU eviction when full."""
    exp = time.time() + ttl_seconds
    with _L1_LOCK:
        if len(_L1_CACHE) >= _L1_MAX_ITEMS:
            # Evict oldest 20%
            keys_to_evict = list(_L1_CACHE.keys())[:200]
            for k in keys_to_evict:
                _L1_CACHE.pop(k, None)
        _L1_CACHE[key] = (exp, data)


def evict_l1(key: str) -> None:
    """Evict a specific key from L1 in-memory cache."""
    with _L1_LOCK:
        _L1_CACHE.pop(key, None)


def clear_l1(pattern: Optional[str] = None) -> None:
    with _L1_LOCK:
        if pattern:
            to_del = [k for k in _L1_CACHE if pattern in k]
            for k in to_del:
                del _L1_CACHE[k]
        else:
            _L1_CACHE.clear()


def fetch_json_pooled(url: str, timeout: float = 12.0) -> Optional[Dict[str, Any]]:
    """
    Fetches JSON from URL using connection pool, Keep-Alive, gzip decoding,
    bounded per-host concurrency, and singleflight request coalescing.
    """
    # 1. L1 Cache Check
    l1_val = get_l1(url)
    if l1_val is not None:
        return l1_val

    # 2. Singleflight Request Coalescing
    with _SINGLEFLIGHT_LOCK:
        if url in _IN_FLIGHT_EVENTS:
            event = _IN_FLIGHT_EVENTS[url]
            is_leader = False
        else:
            event = threading.Event()
            _IN_FLIGHT_EVENTS[url] = event
            is_leader = True

    if not is_leader:
        # Await the leader's network call
        event.wait(timeout=timeout + 2.0)
        with _SINGLEFLIGHT_LOCK:
            return _IN_FLIGHT_RESULTS.get(url)

    # Leader executes the network request
    result = None
    sem = _get_host_semaphore(url)
    with sem:
        try:
            resp = _POOL.request("GET", url, timeout=timeout)
            if resp.status == 200:
                raw_data = resp.data
                # Decompress if gzipped
                if resp.headers.get("Content-Encoding") == "gzip" or (
                    len(raw_data) >= 2 and raw_data[:2] == b"\x1f\x8b"
                ):
                    try:
                        raw_data = gzip.decompress(raw_data)
                    except Exception:
                        pass
                result = json.loads(raw_data.decode("utf-8"))
                set_l1(url, result, ttl_seconds=180.0)
            elif resp.status in (404, 400):
                logger.debug("HTTP %d for %s", resp.status, url)
            else:
                logger.warning("HTTP %d for %s", resp.status, url)
        except Exception as exc:
            logger.debug("Request failed for %s: %s", url, exc)
        finally:
            with _SINGLEFLIGHT_LOCK:
                _IN_FLIGHT_RESULTS[url] = result
                event.set()
                # Clean up event after brief propagation
                def _cleanup(u=url):
                    time.sleep(0.5)
                    with _SINGLEFLIGHT_LOCK:
                        _IN_FLIGHT_EVENTS.pop(u, None)
                        _IN_FLIGHT_RESULTS.pop(u, None)
                threading.Thread(target=_cleanup, daemon=True).start()

    return result


def fetch_parallel(urls: List[str], timeout: float = 12.0) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Executes multiple HTTP JSON requests concurrently in the threadpool.
    Returns mapping of url -> json_data.
    """
    results: Dict[str, Optional[Dict[str, Any]]] = {}
    future_to_url = {
        _EXECUTOR.submit(fetch_json_pooled, u, timeout): u for u in urls
    }
    for fut in as_completed(future_to_url):
        u = future_to_url[fut]
        try:
            results[u] = fut.result()
        except Exception:
            results[u] = None
    return results

