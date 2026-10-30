import urllib.request
import json

# Check OpenF1 drivers for 2026
url_2026 = "https://api.openf1.org/v1/drivers?year=2026"
try:
    data_2026 = json.loads(urllib.request.urlopen(url_2026).read().decode())
    print("OpenF1 2026 drivers count:", len(data_2026))
    if len(data_2026) > 0:
        print("Sample 2026:", data_2026[0])
except Exception as e:
    print("OpenF1 2026 error:", e)

# Check OpenF1 drivers for 2024
url_2024 = "https://api.openf1.org/v1/drivers?year=2024"
try:
    data_2024 = json.loads(urllib.request.urlopen(url_2024).read().decode())
    print("OpenF1 2024 drivers count:", len(data_2024))
    if len(data_2024) > 0:
        print("Sample 2024:", data_2024[0].get("full_name"), data_2024[0].get("team_name"), data_2024[0].get("team_colour"))
except Exception as e:
    print("OpenF1 2024 error:", e)

# Check FastF1 plotting TEAM_COLORS
try:
    import fastf1.plotting
    print("FastF1 plotting TEAM_COLORS:", len(fastf1.plotting.TEAM_COLORS))
    for k, v in list(fastf1.plotting.TEAM_COLORS.items())[:10]:
        print(f"  {k}: {v}")
except Exception as e:
    print("FastF1 plotting error:", e)
