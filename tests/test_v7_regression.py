import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.sources import jolpica
from backend.charts import season, pit

client = TestClient(app)


def test_v7_pit_stops_codes_and_context():
    """V7-3.B: Driver column shows 3-letter code, full name and team color, not raw IDs.
    Suspect durations flagged 'as reported' and team summary computed."""
    res = pit.pit_stops(2023, 1, session=None)
    assert res.get("status") == "ok"
    stops = res.get("stops", [])
    assert len(stops) > 0

    for s in stops:
        # Code must be a 3-letter uppercase string, not raw id like "max_verstappen"
        assert len(s["code"]) == 3
        assert s["code"].isupper()
        assert s["name"] != s["driver_id"]
        assert "team" in s
        assert "color" in s
        if s["suspect"]:
            assert s["suspect_label"] == "as reported"

    # Team summary must be present
    ts = res.get("team_summary", {})
    assert len(ts) > 0
    for team, data in ts.items():
        assert "median_stop_s" in data
        assert "best_stop_s" in data


def test_v7_qualifying_stage_filter():
    """V7-3.D: In each stage compare only the drivers who set a time in that stage.
    Final grid order table beside it."""
    res = season.quali_gap(2023, 1)
    assert res.get("status") == "ok"
    stages = res.get("stages", {})
    assert "Q1" in stages
    assert "Q2" in stages
    assert "Q3" in stages

    # In Q3, only the top 10 (or drivers who actually ran in Q3) should appear
    q3_drivers = stages["Q3"]
    assert len(q3_drivers) <= 10
    for d in q3_drivers:
        assert d["time_s"] is not None
        assert "gap_s" in d
        assert "gap_str" in d
        assert d["gap_str"].startswith("+")

    # Q1 should have 20 drivers
    assert len(stages["Q1"]) >= 19

    # Final grid order table
    final_grid = res.get("final_grid", [])
    assert len(final_grid) > 0
    assert final_grid[0]["position"] == 1


def test_v7_grid_vs_finish_dnf():
    """V7-3.C: Retirements/DSQs marked with badge and delta is None (excluded from gained/lost arrows).
    Unchanged positions have delta 0."""
    res = season.grid_vs_finish(2023, 1)
    assert res.get("status") == "ok"
    rows = res.get("rows", [])
    assert len(rows) > 0

    for r in rows:
        assert "code" in r
        assert len(r["code"]) == 3
        if r["is_dnf"]:
            assert r["badge"] == "DNF"
            assert r["delta"] is None
        elif r["is_dsq"]:
            assert r["badge"] == "DSQ"
            assert r["delta"] is None
        elif r["grid"] is not None and r["finish"] is not None:
            if r["grid"] == r["finish"]:
                assert r["delta"] == 0


def test_v7_schedule_chips_match_jolpica():
    """V7-4.4: Schedule chips built from schedule API match Jolpica round and race_name."""
    resp = client.get("/api/schedule?year=2023")
    assert resp.status_code == 200
    data = resp.json()
    schedule = data.get("schedule", [])
    assert len(schedule) > 0

    # Compare against raw Jolpica schedule
    jolp = jolpica.fetch_schedule(2023)
    assert jolp.get("status") == "ok"
    j_sched = jolp.get("schedule", [])

    assert len(schedule) == len(j_sched)
    for api_race, j_race in zip(schedule, j_sched):
        assert int(api_race["round"]) == int(j_race["round"])
        expected_name = j_race.get("grand_prix") or j_race.get("race_name")
        assert api_race["race_name"] == expected_name


def test_v7_pending_slot_switch_driver():
    """V7-4.3: While bot waits for Season, user typing 'george russel' triggers
    'Switching to George Russell' instead of keeping the previous driver."""
    import time
    t_stamp = int(time.time() * 1000)
    headers = {"X-Client-Id": f"user_{t_stamp}"}
    conv_id = f"conv_switch_{t_stamp}"

    # Turn 1: user asks for Hamilton strategy
    resp1 = client.post(
        "/api/chat/stream",
        headers=headers,
        json={"message": "hamilton race strategy", "conversation_id": conv_id}
    )
    assert resp1.status_code == 200
    text1 = resp1.text
    assert "event: clarify" in text1

    # Extract pending state from turn 1
    import json
    pending_state = None
    for line in text1.splitlines():
        if line.startswith("data: "):
            try:
                payload = json.loads(line[6:])
                if payload.get("pending_state"):
                    pending_state = payload["pending_state"]
            except Exception:
                pass

    assert pending_state is not None
    assert "hamilton" in str(pending_state).lower()

    # Turn 2: user replies with typo "george russel" instead of a season
    resp2 = client.post(
        "/api/chat/stream",
        headers=headers,
        json={"message": "george russel", "pending_state": pending_state, "conversation_id": conv_id}
    )
    assert resp2.status_code == 200
    text2 = resp2.text
    assert "event: clarify" in text2
    assert "Switching to George Russell" in text2


def test_v7_pending_slot_junk_input():
    """V7-4.3: A lone 'n' or unrecognizable input triggers 'I did not understand that'."""
    import time
    t_stamp = int(time.time() * 1000)
    headers = {"X-Client-Id": f"user_junk_{t_stamp}"}
    conv_id = f"conv_junk_{t_stamp}"

    # Start pending flow
    resp1 = client.post(
        "/api/chat/stream",
        headers=headers,
        json={"message": "verstappen strategy", "conversation_id": conv_id}
    )
    assert resp1.status_code == 200
    text1 = resp1.text

    import json
    pending_state = None
    for line in text1.splitlines():
        if line.startswith("data: "):
            try:
                payload = json.loads(line[6:])
                if payload.get("pending_state"):
                    pending_state = payload["pending_state"]
            except Exception:
                pass

    assert pending_state is not None

    # Reply with lone "n"
    resp2 = client.post(
        "/api/chat/stream",
        headers=headers,
        json={"message": "n", "pending_state": pending_state, "conversation_id": conv_id}
    )
    assert resp2.status_code == 200
    assert "I did not understand that" in resp2.text
