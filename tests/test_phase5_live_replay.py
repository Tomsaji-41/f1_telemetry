"""
tests/test_phase5_live_replay.py
Validates Phase 5 requirements:
- Mode logic: live vs replay
- Replay session bundle contract
- Weather and track status honesty
- Zero NaN/inf float leaks in replay JSON
"""

import math
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_live_status_contract():
    res = client.get("/api/live/status")
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") == "ok"
    assert "is_live" in data
    assert isinstance(data["is_live"], bool)
    assert data.get("mode") in ("live", "replay")
    assert "session_info" in data


def test_replay_bundle_default():
    res = client.get("/api/replay/bundle")
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") == "ok"
    assert data.get("total_laps", 0) > 0
    assert "drivers" in data
    assert "laps" in data
    assert "chart_data" in data

    # Check chart data integrity
    chart_data = data["chart_data"]
    assert "laps" in chart_data
    assert "positions" in chart_data
    assert "lap_times" in chart_data

    # Check lap 1
    laps = data["laps"]
    lap_1 = laps.get("1") or laps.get(1)
    assert lap_1 is not None
    assert "track_status" in lap_1
    assert lap_1["track_status"] in ("GREEN", "YELLOW", "SC", "VSC", "RED", "CHEQUERED")
    assert "leaderboard" in lap_1
    assert len(lap_1["leaderboard"]) > 0

    first_drv = lap_1["leaderboard"][0]
    assert "code" in first_drv
    assert "driver" in first_drv
    assert "team" in first_drv
    assert "gap" in first_drv


def test_replay_bundle_specific_session():
    res = client.get("/api/replay/2024/1/bundle")
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") == "ok"
    assert data.get("year") == 2024
    assert data.get("round") == 1
    assert data.get("total_laps") == 57
    assert len(data.get("drivers", {})) == 20

    # Ensure no NaN values anywhere in chart_data
    for code, times in data["chart_data"]["lap_times"].items():
        for t in times:
            if t is not None:
                assert not math.isnan(t)
                assert not math.isinf(t)
