import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_api_seasons():
    resp = client.get("/api/seasons")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["source"] == "Jolpica"
    assert len(data["seasons"]) > 70
    assert 1950 in data["seasons"]

def test_api_schedule():
    resp = client.get("/api/schedule?year=2024")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "schedule" in data
    assert "latest_completed_round" in data
    assert data["total_rounds"] > 0

def test_api_race():
    resp = client.get("/api/race?year=2024&round=1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "classification" in data
    assert len(data["classification"]) > 0
    first = data["classification"][0]
    assert "position" in first
    assert "driver" in first
    assert "team" in first
    assert "team_color" in first

def test_api_standings():
    resp = client.get("/api/standings?year=2024&kind=drivers")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "standings" in data
    assert len(data["standings"]) > 0

def test_api_teams():
    resp = client.get("/api/teams?year=2024")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "teams" in data
    assert len(data["teams"]) > 0
    t = data["teams"][0]
    assert "name" in t
    assert "color" in t
    assert "drivers" in t

def test_api_drivers():
    resp = client.get("/api/drivers?year=2024")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "drivers" in data
    assert len(data["drivers"]) > 0
    d = data["drivers"][0]
    assert "name" in d
    assert "code" in d
    assert "team" in d

def test_api_legends():
    resp = client.get("/api/legends")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "legends" in data
    assert len(data["legends"]) > 0
    leg = data["legends"][0]
    assert "name" in leg
    assert "titles" in leg
    assert leg["titles"] >= 1

def test_api_eras():
    resp = client.get("/api/eras")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "eras" in data
    assert len(data["eras"]) > 0

def test_api_live_status():
    resp = client.get("/api/live/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["mode"] in ["live", "replay"]

