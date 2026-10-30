import sys, os
sys.path.insert(0, os.path.abspath("."))
import fastf1
from backend.sources import jolpica

sched = fastf1.get_event_schedule(2024)
jsched = jolpica.fetch_schedule(2024)

print("FastF1 2024 Schedule:")
for _, r in sched.iterrows():
    rnd = r.get("RoundNumber", 0)
    name = r.get("EventName", "")
    if rnd in (11, 12, 13) or "British" in name:
        print(f"  FastF1 Round {rnd}: {name}")

print("\nJolpica 2024 Schedule:")
for r in jsched.get("races", []):
    rnd = int(r.get("round", 0))
    name = r.get("race_name", "")
    if rnd in (11, 12, 13) or "British" in name:
        print(f"  Jolpica Round {rnd}: {name}")
