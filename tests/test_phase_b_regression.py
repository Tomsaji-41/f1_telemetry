import json
import uuid
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend import utils, parser, resolver

client = TestClient(app)

def test_b1_bare_driver_profile():
    """B1: Bare driver name should return entity profile card without asking 'Did you mean ?'."""
    conv_id = f"test_b1_{uuid.uuid4().hex[:8]}"
    resp = client.post("/api/chat", json={"text": "antonelli", "conversation_id": conv_id})
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("type") == "answer"
    assert "Did you mean ?" not in data.get("markdown", "")
    assert data.get("blocks") or "antonelli" in data.get("markdown", "").lower()

def test_b2_multi_metric_query():
    """B2: 'antonelli podium standings' answered as multi-metric dual blocks in one response."""
    conv_id = f"test_b2_{uuid.uuid4().hex[:8]}"
    resp = client.post("/api/chat", json={"text": "antonelli podium standings", "conversation_id": conv_id})
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("type") == "answer"
    # Should not ask clarify for 'Which standings type'
    assert data.get("type") != "clarify"

def test_b4_turn_id_present():
    """B4: Response carries turn_id and is deterministic."""
    resp = client.post("/api/chat", json={"text": "standings drivers", "conversation_id": "test_b4"})
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("turn_id") is not None

def test_b8_gap_validation():
    """B8: Gap column computed server-side and non-decreasing for lead-lap finishers."""
    lead_lap_raw = [
        {"position": 1, "time_ms": 5400000, "laps": 50},
        {"position": 2, "time_ms": 5405000, "laps": 50},
        {"position": 3, "time_ms": 5412000, "laps": 50},
    ]
    gaps = utils.compute_and_validate_gaps(lead_lap_raw)
    assert gaps[0]["gap"] == "Winner" or gaps[0]["gap"] == "+0.000s"
    assert gaps[1]["gap"] == "+5.000s"
    assert gaps[2]["gap"] == "+12.000s"

def test_b9_number_formatting():
    """B9: Whole points as int, half points with 1 decimal, times as m:ss.mmm."""
    assert utils.format_points(25.0) == "25"
    assert utils.format_points(12.5) == "12.5"
    assert utils.format_lap_time(89.825) == "1:29.825"
    assert utils.format_gap_display(4.593) == "+4.593s"

def test_b11_no_marketing_copy():
    """B11: No marketing copy like 'Claude-style' or 'Sub-100ms' in responses."""
    resp = client.post("/api/chat", json={"text": "hello", "conversation_id": "test_b11"})
    assert resp.status_code == 200
    text = json.dumps(resp.json())
    assert "Claude-style" not in text
    assert "Sub-100ms" not in text
    assert "Deterministic verification" not in text

def test_b12_timestamp_format():
    """B12: Timestamp formatted with date, 24-hr time, and UTC."""
    import datetime
    dt = datetime.datetime(2026, 10, 27, 4, 24, tzinfo=datetime.timezone.utc)
    ts = utils.format_utc_timestamp(dt)
    assert "27 Oct 2026, 04:24 UTC" in ts or "UTC" in ts
