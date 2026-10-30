import pytest
import time
from backend import cache

def test_build_cache_key_separation():
    k1 = cache.build_cache_key("fastf1", "telemetry", year=2024, round=12, session="R", params={"driver": "VER"})
    k2 = cache.build_cache_key("fastf1", "telemetry", year=2024, round=13, session="R", params={"driver": "VER"})
    k3 = cache.build_cache_key("fastf1", "telemetry", year=2024, round=12, session="Q", params={"driver": "VER"})
    k4 = cache.build_cache_key("fastf1", "telemetry", year=2024, round=12, session="R", params={"driver": "NOR"})

    assert k1 != k2, "Different rounds must have different cache keys"
    assert k1 != k3, "Different sessions must have different cache keys"
    assert k1 != k4, "Different drivers must have different cache keys"
    assert "2024:12:R:driver=VER" in k1

def test_build_cache_key_deterministic_params():
    k1 = cache.build_cache_key("api", "compare", 2024, 1, params={"a": "1", "b": "2"})
    k2 = cache.build_cache_key("api", "compare", 2024, 1, params={"b": "2", "a": "1"})
    assert k1 == k2, "Param ordering must not alter cache key"

def test_cache_refuses_to_cache_errors():
    error_key = cache.build_cache_key("test", "err", 2024, 1)
    cache.set_json(error_key, {"status": "error", "message": "Failed"}, ttl_seconds=3600)
    assert cache.get_json(error_key) is None, "Errors must never be cached"

    loading_key = cache.build_cache_key("test", "loading", 2024, 1)
    cache.set_json(loading_key, {"status": "loading", "progress": 50}, ttl_seconds=3600)
    assert cache.get_json(loading_key) is None, "Loading states must never be cached"

def test_cache_invalidates_mismatched_schema():
    valid_key = cache.build_cache_key("test", "schema", 2024, 1)
    cache.set_json(valid_key, {"status": "ok", "data": 123}, ttl_seconds=60)
    cached = cache.get_json(valid_key)
    assert cached is not None and cached.get("data") == 123

    # Manually tamper schema version
    old_data = {"status": "ok", "data": 123, "_schema_version": "v0_legacy"}
    cache.set(valid_key, cache.json.dumps(old_data), ttl_seconds=60)
    assert cache.get_json(valid_key) is None, "Cache entry with obsolete schema_version must be ignored"

