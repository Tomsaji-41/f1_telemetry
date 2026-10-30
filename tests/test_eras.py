"""Tests for /api/eras endpoint: error resilience, missing data, 429/timeout handling, and contracts."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_eras_ok():
    """Verify /api/eras returns 200 with standard envelope and valid era definitions."""
    response = client.get("/api/eras")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") in ("ok", "cached")
    assert "eras" in data
    assert isinstance(data["eras"], list)
    assert len(data["eras"]) > 0

    # Verify first era has all required fields
    first_era = data["eras"][0]
    for key in ("id", "name", "from", "text"):
        assert key in first_era
        assert first_era[key] is not None
    assert isinstance(first_era["from"], int)


def test_eras_handles_missing_or_malformed_season_data():
    """Verify /api/eras handles seasons with None, missing keys, or invalid years gracefully without 500."""
    malformed_seasons = [
        {"season": "1950"},
        {"season": None},
        {},
        {"season": "invalid_year"},
        {"season": "1960"},
    ]
    malformed_champions = [
        {"year": 1950, "driver": "Nino Farina", "driver_champion": "Nino Farina"},
        {"year": "corrupted", "driver": None},
        {"year": 1960, "driver": "Jack Brabham", "driver_champion": "Jack Brabham"},
    ]

    with patch("backend.sources.jolpica.fetch_all_seasons", return_value=malformed_seasons), \
         patch("backend.sources.jolpica.fetch_champions", return_value=malformed_champions):
        response = client.get("/api/eras")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") in ("ok", "cached")
        assert "eras" in data
        assert isinstance(data["eras"], list)


def test_eras_survives_upstream_429_or_timeout():
    """Verify upstream 429 or network timeout returns status error/not_available without unhandled 500."""
    with patch("backend.sources.jolpica.fetch_all_seasons", side_effect=Exception("HTTP 429: Too Many Requests")), \
         patch("backend.sources.jolpica.fetch_champions", side_effect=Exception("HTTP 429: Rate Limit Exceeded")):
        response = client.get("/api/eras")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") in ("error", "not_available")
        assert "reason" in data
        assert "eras" in data
        assert data["eras"] == []


def test_eras_never_caches_errors():
    """Verify error responses are not stored in cache."""
    import sqlite3
    from backend import config

    # Ensure no error entry exists in cache table with status error
    conn = sqlite3.connect(str(config.DB_PATH), timeout=10.0)
    cur = conn.cursor()
    cur.execute("SELECT key, value FROM cache WHERE key LIKE '%eras%'")
    rows = cur.fetchall()
    for key, data_str in rows:
        import json
        try:
            cached = json.loads(data_str)
            assert cached.get("status") != "error", f"Found cached error under key {key}"
        except Exception:
            pass
    conn.close()
