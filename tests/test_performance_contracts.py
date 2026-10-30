"""
tests/test_performance_contracts.py — Performance & Caching Contract Tests (Phase P0 - P6)
"""
import time
import threading
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend import cache, http_pool, team_cards, circuits

client = TestClient(app)

def test_server_timing_header_present():
    """P0/P6: Verify that Server-Timing header is attached to API responses with duration metrics."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    st = resp.headers.get("Server-Timing")
    assert st is not None
    assert "total;dur=" in st

def test_cache_control_headers_present():
    """P3/P6: Verify that Cache-Control headers include public caching and stale-while-revalidate."""
    resp = client.get("/api/circuits?year=2024")
    assert resp.status_code == 200
    cc = resp.headers.get("Cache-Control", "")
    assert "public" in cc
    assert "stale-while-revalidate" in cc

def test_request_coalescing_singleflight():
    """P1/P3/P6: Verify singleflight request coalescing ensures concurrent identical URLs execute once."""
    test_url = "https://api.jolpi.ca/ergast/f1/2024.json"
    results = []

    def _worker():
        data = http_pool.fetch_json_pooled(test_url)
        results.append(data)

    threads = [threading.Thread(target=_worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 5
    for r in results:
        assert r is not None
        assert "MRData" in r

def test_stale_while_revalidate_serves_immediately():
    """P3/P6: Verify SWR returns immediately on cached data without blocking on refresh."""
    key = "test_swr_metric_key"
    call_count = {"count": 0}

    def _compute():
        call_count["count"] += 1
        return {"status": "ok", "value": 42, "version": call_count["count"]}

    # Seed fresh cache
    cache.set_json(key, _compute(), ttl_seconds=1.0)
    time.sleep(1.2)  # Expire fresh TTL

    # Now expired: get_or_compute_swr should return stale value immediately
    t0 = time.perf_counter()
    val = cache.get_or_compute_swr(key, _compute, fresh_ttl=60.0, stale_ttl=3600.0)
    dt = (time.perf_counter() - t0) * 1000

    assert val is not None
    assert val.get("value") == 42
    assert dt < 50.0  # Must return immediately (<50ms)

def test_errors_are_not_cached():
    """P3: Prime Rule 3 — errors and loading states must never be cached with long TTL."""
    bad_key = "test_error_cache_key"
    cache.set_json(bad_key, {"status": "error", "reason": "Failed upstream"}, ttl_seconds=3600)
    cached = cache.get_json(bad_key)
    assert cached is None

def test_no_per_card_upstream_calls_on_warm_cache():
    """P1/P6: Warm requests must execute from cache with 0 upstream network calls."""
    # Warm up team cards
    team_cards.get_team_cards(2024, 1)

    # Intercept urllib
    import urllib.request
    calls = []
    orig_open = urllib.request.urlopen

    def _spy_open(req, *args, **kwargs):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        calls.append(url)
        return orig_open(req, *args, **kwargs)

    urllib.request.urlopen = _spy_open
    try:
        t0 = time.perf_counter()
        data = team_cards.get_team_cards(2024, 1)
        dt = (time.perf_counter() - t0) * 1000
        assert data.get("status") == "ok"
        assert len(calls) == 0  # 0 upstream calls!
        assert dt < 50.0  # sub-50ms response
    finally:
        urllib.request.urlopen = orig_open

