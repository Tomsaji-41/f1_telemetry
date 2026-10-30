import json
import os
import fastf1.plotting

p = os.path.join(os.path.dirname(fastf1.plotting.__file__), "constants.json")
with open(p, "r", encoding="utf-8") as f:
    data = json.load(f)

for yr in ["2026", "2025", "2024", "2023", "2022"]:
    y_data = data.get(yr, {})
    teams = y_data.get("teams", {})
    print(f"Year {yr} has {len(teams)} teams:")
    for t_name, t_val in list(teams.items())[:6]:
        print(f"  {t_name}: {t_val.get('colors')}")
