"""
tests/test_circuits_geometry.py — Tests for circuit geometry resolution, FastF1 telemetry, OSM fallback, and honest limits.
"""
import pytest
from unittest.mock import patch
from backend import circuits


def test_geometry_fastf1_telemetry_resolution():
    """Verify official telemetry coordinates are scaled by 0.1 to SI meters and compute direction."""
    mock_mv_data = {
        "x": [0, 1000, 2000, 2000, 1000, 0, 0, 10, 20, 30],
        "y": [0, 0, 1000, 2000, 2000, 1000, 0, 10, 20, 30],
        "rotation": 45,
        "corners": [
            {"number": 1, "trackPosition": {"x": 1000, "y": 0}, "angle": 90, "length": 500}
        ]
    }
    with patch("backend.circuits._http_get_json", return_value=mock_mv_data), \
         patch("backend.circuits.resolve_mv_circuit_key", return_value="test_key"):
        res = circuits.get_circuit_geometry("test_track", year=2024)
        assert res["status"] == "ok"
        assert res["source"] == "FastF1 MultiViewer"
        assert res["units"] == "meters"
        # 1000 decimetres * 0.1 = 100.0 meters
        assert res["x"][1] == 100.0
        assert res["point_count"] == len(res["x"])
        assert res["corners"][0]["x"] == 100.0
        assert res["direction"] in ("clockwise", "anti-clockwise")


def test_geometry_osm_happy_path():
    """Verify OSM Overpass fallback is invoked and projected when FastF1/MultiViewer is unavailable."""
    mock_circ_info = {
        "MRData": {
            "CircuitTable": {
                "Circuits": [
                    {
                        "circuitId": "monza",
                        "circuitName": "Autodromo Nazionale Monza",
                        "Location": {"lat": "45.6156", "long": "9.2811", "country": "Italy"}
                    }
                ]
            }
        }
    }
    mock_osm_geom = {
        "x": [0.0, 100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0, 900.0, 1000.0],
        "y": [0.0, 50.0, 100.0, 150.0, 200.0, 250.0, 300.0, 350.0, 400.0, 450.0, 500.0],
        "corners": [],
        "source": "OpenStreetMap Overpass",
        "rotation": 0
    }

    with patch("backend.circuits._http_get_json", side_effect=lambda url, *a, **k: mock_circ_info if "circuits/monza.json" in url else None), \
         patch("backend.circuits.resolve_mv_circuit_key", return_value=None), \
         patch("backend.circuits._fetch_osm_overpass_geometry", return_value=mock_osm_geom):
        res = circuits.get_circuit_geometry("monza", year=2024)
        assert res["status"] == "ok"
        assert res["source"] == "OpenStreetMap Overpass"
        assert len(res["x"]) >= 10
        assert res["total_length_meters"] > 0


def test_null_geometry_never_produces_synthetic_path():
    """Verify that when no telemetry or OSM geometry exists, x/y/z are null and status is not_available."""
    mock_circ_info = {
        "MRData": {
            "CircuitTable": {
                "Circuits": [
                    {
                        "circuitId": "historical_track",
                        "circuitName": "Historical Circuit",
                        "Location": {"lat": "0.0", "long": "0.0", "country": "Unknown"}
                    }
                ]
            }
        }
    }
    with patch("backend.circuits._http_get_json", side_effect=lambda url, *a, **k: mock_circ_info if "historical_track.json" in url else None), \
         patch("backend.circuits.resolve_mv_circuit_key", return_value=None), \
         patch("backend.circuits._fetch_osm_overpass_geometry", return_value=None):
        res = circuits.get_circuit_geometry("historical_track")
        assert res["status"] == "not_available"
        assert res["x"] is None
        assert res["y"] is None
        assert res["z"] is None
        assert "reason" in res
        assert "not available" in res["reason"].lower() or "no telemetry" in res["reason"].lower()

