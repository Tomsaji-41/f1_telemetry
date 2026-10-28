import pytest
from backend import tools

def test_pre_2018_fastf1_lap_data_not_available():
    res = tools.get_lap_times(2010, "Monza", "ALO")
    assert res["status"] == "not_available"
    assert "2018" in res["reason"]

def test_future_race_not_available():
    res = tools.get_race_result(2028, "Bahrain")
    assert res["status"] == "not_available"

def test_pre_2012_pit_stops_not_available():
    res = tools.get_pit_stops(2008, "Monza")
    assert res["status"] == "not_available"
    assert "2012" in res["reason"]

def test_circuit_info_spa():
    res = tools.get_circuit_info("Spa")
    assert res["status"] == "ok"
    assert "Spa" in res["circuit_name"]
    assert res["country"].lower() == "belgium"

def test_get_champions_2021():
    res = tools.get_champions(2021, 2021)
    assert res["status"] == "ok"
    assert len(res["champions"]) == 1
    assert "Verstappen" in res["champions"][0]["driver_champion"]
