import time
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

TEST_RACES = [
    (2024, 1, "2024 Round 1 - Standard modern completed"),
    (2024, 24, "2024 Round 24 - Season finale"),
    (2023, 11, "2023 Round 11 - Mid-season driver swap (Ricciardo)"),
    (2021, 22, "2021 Round 22 - Title decider"),
    (2020, 2, "2020 Round 2 - Styrian GP double-header"),
]

@pytest.mark.parametrize("year,round_num,description", TEST_RACES)
def test_race_classification_contract(year, round_num, description):
    res = client.get(f"/api/race?year={year}&round={round_num}")
    assert res.status_code == 200, f"Failed for {description}"
    data = res.json()
    assert data.get("status") in ("ok", "partial")
    classification = data.get("classification") or []
    assert len(classification) >= 10, f"Expected >= 10 classification rows for {description}, got {len(classification)}"

@pytest.mark.parametrize("year,round_num,description", TEST_RACES)
def test_race_identity_contract(year, round_num, description):
    res = client.get(f"/api/identity?year={year}&round={round_num}")
    assert res.status_code == 200, f"Failed for {description}"
    data = res.json()
    assert data.get("status") == "ok"
    drivers = data.get("drivers", {})
    assert len(drivers) >= 15, f"Expected >= 15 drivers for {description}"
    
    # Assert drivers have valid non-empty team colors
    for did, d in list(drivers.items())[:10]:
        assert d.get("teamColor"), f"Missing teamColor for {did} in {description}"
        assert d["teamColor"].startswith("#"), f"Invalid hex color for {did}: {d['teamColor']}"

@pytest.mark.parametrize("year,round_num,description", TEST_RACES)
def test_grid_vs_finish_contract(year, round_num, description):
    res = client.get(f"/api/charts/grid-vs-finish?year={year}&round={round_num}")
    assert res.status_code == 200, f"Failed for {description}"
    data = res.json()
    assert data.get("status") in ("ok", "partial")
    rows = data.get("rows") or []
    assert len(rows) >= 10, f"Expected >= 10 grid vs finish rows for {description}, got {len(rows)}"
    for r in rows[:5]:
        assert r.get("driverId") or r.get("code"), f"Missing driver identifier in row: {r}"

@pytest.mark.parametrize("year,round_num,description", TEST_RACES)
def test_coverage_endpoint_latency(year, round_num, description):
    t0 = time.perf_counter()
    res = client.get(f"/api/coverage?year={year}&round={round_num}")
    latency_ms = (time.perf_counter() - t0) * 1000
    assert res.status_code == 200
    assert latency_ms < 100, f"Expected coverage response in < 100 ms, took {latency_ms:.1f} ms"

