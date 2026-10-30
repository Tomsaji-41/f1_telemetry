import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend import identity

client = TestClient(app)

def test_identity_bearman_ferrari_2024_r2():
    # 2024 Round 2: Bearman substituted for Sainz at Ferrari
    data = identity.get_round_identity(2024, 2)
    assert data["status"] == "ok"
    drivers = data["drivers"]
    
    # Check Bearman
    bearman = next((d for did, d in drivers.items() if "bearman" in did or d.get("code") == "BEA"), None)
    assert bearman is not None, "Oliver Bearman should be in 2024 Round 2 driver list"
    assert "ferrari" in bearman["team"].lower() or "ferrari" in bearman["teamId"].lower(), f"Bearman team should be Ferrari, got {bearman['team']}"

    # Teammate in Ferrari should be Leclerc
    ferrari_team = next((t for tid, t in data["teams"].items() if "ferrari" in tid.lower() or "ferrari" in t.get("name", "").lower()), None)
    assert ferrari_team is not None
    assert len(ferrari_team["drivers"]) == 2, f"Ferrari should have 2 drivers for R2, got {ferrari_team['drivers']}"

def test_identity_colapinto_williams_2024_r18():
    # 2024 Round 18: Colapinto at Williams
    data = identity.get_round_identity(2024, 18)
    assert data["status"] == "ok"
    drivers = data["drivers"]
    
    colapinto = next((d for did, d in drivers.items() if "colapinto" in did or d.get("code") == "COL"), None)
    assert colapinto is not None, "Franco Colapinto should be in 2024 Round 18 driver list"
    assert "williams" in colapinto["team"].lower() or "williams" in colapinto["teamId"].lower(), f"Colapinto team should be Williams, got {colapinto['team']}"

def test_api_identity_round_endpoint():
    res = client.get("/api/identity?year=2024&round=2")
    assert res.status_code == 200
    json_data = res.json()
    assert json_data.get("status") == "ok"
    assert json_data.get("round") == 2
    assert "drivers" in json_data

