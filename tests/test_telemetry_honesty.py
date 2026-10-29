"""
tests/test_telemetry_honesty.py
Test asserting that missing car data never produces invented series points (Honest Limits rule).
"""
import pytest
import pandas as pd
import numpy as np
from datetime import timedelta
from unittest.mock import MagicMock, patch
from backend.charts import telemetry

class MockLapWithNoCarData(pd.Series):
    def __init__(self, driver="VER", lap_time_sec=90.5, speed_st=325.0):
        super().__init__({
            "Driver": driver,
            "LapTime": timedelta(seconds=lap_time_sec),
            "Sector1Time": timedelta(seconds=30.1),
            "Sector2Time": timedelta(seconds=30.2),
            "Sector3Time": timedelta(seconds=30.2),
            "SpeedST": speed_st,
            "SpeedFL": 300.0,
            "SpeedI1": 280.0,
            "SpeedI2": 290.0,
        })

    def get_car_data(self):
        # Simulate FastF1 KeyError when car_data is not available from timing provider
        raise KeyError("1")

    def get_pos_data(self):
        raise KeyError("1")


class MockLapWithRealCarData(pd.Series):
    def __init__(self, driver="VER", lap_time_sec=91.0, speed_val=315.0):
        super().__init__({
            "Driver": driver,
            "LapTime": timedelta(seconds=lap_time_sec),
            "Sector1Time": timedelta(seconds=30.0),
            "Sector2Time": timedelta(seconds=30.0),
            "Sector3Time": timedelta(seconds=31.0),
            "SpeedST": speed_val,
            "SpeedFL": 295.0,
            "SpeedI1": 275.0,
            "SpeedI2": 285.0,
        })
        dist = np.linspace(0, 5000, 50)
        self.car_df = pd.DataFrame({
            "Distance": dist,
            "Speed": np.full(50, speed_val),
            "Throttle": np.full(50, 100.0),
            "Brake": np.zeros(50, dtype=bool),
            "nGear": np.full(50, 8),
            "RPM": np.full(50, 11500),
            "DRS": np.zeros(50, dtype=int),
        })

    def get_car_data(self):
        df = self.car_df.copy()
        df.add_distance = MagicMock(return_value=df)
        return df

    def get_pos_data(self):
        return pd.DataFrame({
            "Distance": np.linspace(0, 5000, 50),
            "X": np.linspace(0, 100, 50),
            "Y": np.linspace(0, 100, 50)
        })


class MockLapsCollection:
    def __init__(self, l1, l2):
        self.l1 = l1
        self.l2 = l2
        self.Driver = pd.Series([l1["Driver"], l2["Driver"]])

    def __contains__(self, item):
        return item == "Driver"

    def __getitem__(self, item):
        if item == "Driver":
            return self.Driver
        raise KeyError(item)

    def pick_drivers(self, code):
        lap = self.l1 if code == self.l1["Driver"] else self.l2
        mock_subset = MagicMock()
        mock_subset.__len__.return_value = 1
        mock_subset.pick_fastest.return_value = lap
        mock_subset.iterlaps.return_value = [(0, lap)]
        mock_subset.iterrows.return_value = [(0, lap)]
        return mock_subset

    def pick_fastest(self):
        return self.l1


class MockSession:
    def __init__(self, lap_class):
        l1 = lap_class("VER", 90.5, 325.0)
        l2 = lap_class("NOR", 91.2, 320.0)
        self.laps = MockLapsCollection(l1, l2)
        self.results = pd.DataFrame([
            {"Abbreviation": "VER", "FullName": "Max Verstappen", "TeamName": "Red Bull Racing", "TeamColor": "#3671C6"},
            {"Abbreviation": "NOR", "FullName": "Lando Norris", "TeamName": "McLaren", "TeamColor": "#FF8000"},
        ])


def test_missing_car_data_never_produces_invented_series():
    """Honest Limits: When car telemetry is missing, return status 'not_available' without invented series."""
    session = MockSession(MockLapWithNoCarData)

    with patch("backend.charts.loader.peek", return_value=None), \
         patch("backend.charts.loader.get_session", side_effect=RuntimeError("No alt session")):
        out = telemetry.build_telemetry_compare(session, "VER", "NOR", year=2024, rnd=1)

    assert out["status"] == "not_available"
    assert out["traces"] is None, "Fabricated traces must not be produced when car_data is missing!"
    assert out["track_map"] is None, "Parametric track coordinates must not be synthesized!"
    assert out["braking_table"] is None
    assert out["proxies"] is None
    assert "nearest_session" in out
    assert out["nearest_session"] is not None
    assert "year" in out["nearest_session"]
    assert "round" in out["nearest_session"]
    assert "unavailable" in out["coverage_note"].lower()

    # Verify sector and speed-trap comparison contains only real values
    sst = out.get("sector_speed_trap")
    assert sst is not None
    assert sst["speed_st"]["VER"] == 325.0
    assert sst["speed_fl"]["VER"] == 300.0
    assert sst["lap_time"]["VER"] == 90.5


def test_real_car_data_produces_interpolated_traces():
    """Honest Limits: When real car data is present, output traces from real car data."""
    session = MockSession(MockLapWithRealCarData)
    out = telemetry.build_telemetry_compare(session, "VER", "NOR", year=2024, rnd=1)

    assert out["status"] == "ok"
    assert out["traces"] is not None
    assert "driver1" in out["traces"]
    assert "driver2" in out["traces"]
    assert len(out["traces"]["driver1"]["speed"]) == 400
    # Speeds must match real speed_val (325.0 for VER), not synthetic sinusoidal curves
    for s in out["traces"]["driver1"]["speed"]:
        assert abs(s - 325.0) < 0.5
