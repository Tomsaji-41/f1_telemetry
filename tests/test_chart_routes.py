import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

# Statuses that indicate a valid response (data present or gracefully deferred/errored)
_OK_STATUSES = ("preparing", "ok", "not_published_yet", "source_error", "not_ingested", "outside_coverage", "empty")

def _has_data(data: dict) -> bool:
    """True if the response contains any chart data payload."""
    return any(k in data for k in ("series", "points", "stints", "stops", "drivers", "rows", "x"))

def test_chart_position_by_lap():
    resp = client.get("/api/charts/position-by-lap?year=2023&round=1")
    assert resp.status_code == 200
    data = resp.json()
    assert "source" in data
    assert _has_data(data) or (data.get("status") in _OK_STATUSES)
    if "series" in data:
        assert "axes" in data

def test_chart_gap_evolution():
    resp = client.get("/api/charts/gap-evolution?year=2023&round=1")
    assert resp.status_code == 200
    data = resp.json()
    assert "source" in data
    assert _has_data(data) or (data.get("status") in _OK_STATUSES)
    if "series" in data:
        assert "axes" in data

def test_chart_lap_scatter():
    resp = client.get("/api/charts/lap-scatter?year=2023&round=1")
    assert resp.status_code == 200
    data = resp.json()
    assert "source" in data
    # lap_scatter returns "points" (not "series")
    assert _has_data(data) or (data.get("status") in _OK_STATUSES)

def test_chart_stints():
    resp = client.get("/api/charts/stints?year=2023&round=1")
    assert resp.status_code == 200
    data = resp.json()
    assert "source" in data
    assert _has_data(data) or (data.get("status") in _OK_STATUSES)

def test_chart_pit_stops():
    resp = client.get("/api/charts/pit-stops?year=2023&round=1")
    assert resp.status_code == 200
    data = resp.json()
    assert "source" in data
    assert "series" in data

def test_chart_grid_vs_finish():
    resp = client.get("/api/charts/grid-vs-finish?year=2023&round=1")
    assert resp.status_code == 200
    data = resp.json()
    assert "source" in data
    assert "series" in data

def test_chart_championship_progression():
    resp = client.get("/api/charts/championship-progression?year=2023&kind=drivers")
    assert resp.status_code == 200
    data = resp.json()
    assert "source" in data
    assert "series" in data

def test_chart_finish_heatmap():
    resp = client.get("/api/charts/finish-heatmap?year=2023")
    assert resp.status_code == 200
    data = resp.json()
    assert "source" in data
    assert "drivers" in data

def test_chart_team_pace():
    resp = client.get("/api/charts/team-pace?year=2023&round=1")
    assert resp.status_code == 200
    data = resp.json()
    assert "source" in data
    assert _has_data(data) or (data.get("status") in _OK_STATUSES)
