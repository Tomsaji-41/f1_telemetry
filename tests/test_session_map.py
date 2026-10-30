import pytest
from backend import session_map

def test_normalize_name():
    assert session_map.normalize_name("British Grand Prix") == "british"
    assert session_map.normalize_name("Formula 1 Heineken Dutch Grand Prix 2024") == "heineken dutch 2024"
    assert session_map.normalize_name("Autodromo Enzo e Dino Ferrari") == "enzo e dino ferrari"

def test_session_map_2024():
    mapping = session_map.get_season_mapping(2024)
    assert len(mapping) >= 20, "2024 season should have mapped rounds"
    # Round 1 is Bahrain
    r1 = mapping.get(1)
    assert r1 is not None
    assert "bahrain" in r1["grand_prix"].lower()
    assert r1["fastf1_available"] is True

def test_session_map_unknown_or_cancelled_round():
    # An unrun or invalid round should return safe metadata without throwing
    meta = session_map.get_event_meta(2024, 99)
    assert meta["fastf1_available"] is False
    assert "not found" in meta.get("reason", "").lower()

def test_session_map_2020_double_headers():
    mapping = session_map.get_season_mapping(2020)
    # In 2020:
    # Round 1: Austrian GP (Red Bull Ring)
    # Round 2: Styrian GP (Red Bull Ring)
    # Round 4: British GP (Silverstone)
    # Round 5: 70th Anniversary GP (Silverstone)
    if mapping:
        r1 = mapping.get(1)
        r2 = mapping.get(2)
        if r1 and r2 and r1["fastf1_available"] and r2["fastf1_available"]:
            assert r1["fastf1_name"] != r2["fastf1_name"], "2020 R1 and R2 must have distinct FastF1 event names"
