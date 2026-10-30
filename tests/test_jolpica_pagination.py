import pytest
from unittest.mock import patch
from backend.sources import jolpica

def test_jolpica_pagination_3_pages():
    # Mock a 3-page Jolpica driver standings response (total = 60, limit = 20)
    page1 = {
        "MRData": {
            "total": "60", "offset": "0", "limit": "20",
            "StandingsTable": {
                "StandingsLists": [{
                    "DriverStandings": [{"driverId": f"d_{i}"} for i in range(1, 21)]
                }]
            }
        }
    }
    page2 = {
        "MRData": {
            "total": "60", "offset": "20", "limit": "20",
            "StandingsTable": {
                "StandingsLists": [{
                    "DriverStandings": [{"driverId": f"d_{i}"} for i in range(21, 41)]
                }]
            }
        }
    }
    page3 = {
        "MRData": {
            "total": "60", "offset": "40", "limit": "20",
            "StandingsTable": {
                "StandingsLists": [{
                    "DriverStandings": [{"driverId": f"d_{i}"} for i in range(41, 61)]
                }]
            }
        }
    }

    url_map = {
        "https://api.jolpi.ca/ergast/f1/2024/driverStandings.json?limit=20&offset=0": page1,
        "https://api.jolpi.ca/ergast/f1/2024/driverStandings.json?limit=20&offset=20": page2,
        "https://api.jolpi.ca/ergast/f1/2024/driverStandings.json?limit=20&offset=40": page3,
    }

    def mock_cached_get(url, ttl, headers=None):
        return url_map.get(url)

    with patch("backend.cache.cached_get_json", side_effect=mock_cached_get), \
         patch("backend.cache.get_json", return_value=None), \
         patch("backend.cache.set_json", return_value=None):
        res = jolpica.fetch_paginated_mrdata("https://api.jolpi.ca/ergast/f1/2024/driverStandings.json", ttl=60, page_size=20)
        assert res is not None
        mr = res["MRData"]
        standings = mr["StandingsTable"]["StandingsLists"][0]["DriverStandings"]
        assert len(standings) == 60, f"Expected 60 merged driver standings, got {len(standings)}"
        assert standings[0]["driverId"] == "d_1"
        assert standings[59]["driverId"] == "d_60"

