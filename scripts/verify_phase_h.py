import json
import sys
import os

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.tools import get_driver_profile, get_team_history, get_standings, get_race_result
from backend.utils import compute_and_validate_gaps

def main():
    ham = get_driver_profile("hamilton")
    fer = get_team_history("ferrari")
    st23 = get_standings(2023, kind="drivers")
    m21 = get_race_result(2021, 14)
    
    gaps_computed = compute_and_validate_gaps(m21.get("results", []))
    
    data = {
        "1_driver_career_wins_hamilton": {
            "driver": ham.get("name"),
            "wins": ham.get("career_wins", ham.get("wins")),
            "championships": ham.get("world_championships", ham.get("championships"))
        },
        "2_team_constructor_titles_ferrari": {
            "team": fer.get("name"),
            "championships": fer.get("championships"),
            "wins": fer.get("wins")
        },
        "3_2023_drivers_standings_top3": [
            {"pos": x.get("position"), "driver": x.get("driver"), "points": x.get("points")}
            for x in st23.get("standings", [])[:3]
        ],
        "4_monza_2021_race_result_top3": [
            {"pos": x.get("position"), "driver": x.get("driver"), "team": x.get("constructor")}
            for x in m21.get("results", [])[:3]
        ],
        "5_monza_2021_gaps": [
            {"pos": x.get("position"), "driver": x.get("driver"), "gap": x.get("gap"), "time": x.get("time"), "gap_valid": x.get("gap_valid")}
            for x in gaps_computed[:5]
        ]
    }
    print(json.dumps(data, indent=2))

if __name__ == "__main__":
    main()
