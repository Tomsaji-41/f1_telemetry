"""
tests/test_circuits.py — Unit & Integration tests for Circuit Telemetry, Geometry & Facts (Phase K)
"""
import pytest
from backend import circuits

def test_fetch_all_circuits():
    """Verify catalog returns circuits for both current season and all-time."""
    season_circs = circuits.fetch_all_circuits(year=2024, scope="season")
    assert season_circs.get("status") == "ok"
    c_list = season_circs.get("circuits", [])
    assert len(c_list) >= 20

    all_circs = circuits.fetch_all_circuits(scope="all")
    assert all_circs.get("status") == "ok"
    assert len(all_circs.get("circuits", [])) >= 70

def test_circuit_details_silverstone():
    """Verify rich details, track facts, calculated longest straight, and climate for Silverstone."""
    details = circuits.get_circuit_details("silverstone", year=2024, round_num=12)
    assert details.get("status") == "ok"
    assert details.get("circuit_id") == "silverstone"
    assert "Silverstone" in details.get("name", "")

    tf = details.get("track_facts", {})
    assert tf.get("direction") == "clockwise"
    assert tf.get("corner_count") == 18
    assert tf.get("length_km") is not None
    assert 5.0 <= tf["length_km"] <= 6.5
    assert tf.get("longest_straight_meters") is not None
    assert 700 <= tf["longest_straight_meters"] <= 1000

    rh = details.get("race_history", {})
    assert rh.get("first_gp_year") == 1950
    assert rh.get("lap_record") is not None

def test_circuit_geometry_silverstone():
    """Verify 3D geometry coordinates, units, and corners for Silverstone."""
    geom = circuits.get_circuit_geometry("silverstone", year=2024, round_num=12)
    assert geom.get("status") == "ok"
    assert geom.get("units") == "meters"
    assert geom.get("direction") == "clockwise"
    assert len(geom.get("x", [])) > 100
    assert len(geom.get("y", [])) == len(geom.get("x", []))
    assert len(geom.get("corners", [])) == 18

    c0 = geom["corners"][0]
    assert "number" in c0
    assert "angle" in c0
    assert "distance" in c0

def test_circuit_not_found_honest_limit():
    """Verify unknown circuit returns not_found status with informative reason."""
    bad = circuits.get_circuit_details("non_existent_gp_circuit")
    assert bad.get("status") == "not_found"
    assert "reason" in bad
