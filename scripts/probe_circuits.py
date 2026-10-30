"""
scripts/probe_circuits.py — Plain-library probe for FastF1 position telemetry & OSM Overpass raceway geometry.
No app code used here — purely probing the upstream libraries and APIs.
"""
import sys
import json
import urllib.request
import urllib.parse
import fastf1
from backend import config

def probe_fastf1_lap_position():
    print("=== Probing FastF1 Lap Position Telemetry ===")
    try:
        fastf1.Cache.enable_cache(str(config.CACHE_DIR))
        session = fastf1.get_session(2024, 1, "R")
        session.load(laps=True, telemetry=True, weather=False, messages=False)
        fastest_lap = session.laps.pick_fastest()
        driver = fastest_lap.get("Driver", "UNK")
        d_num = fastest_lap.get("DriverNumber", "1")
        lap_time = fastest_lap.get("LapTime")
        print(f"Fastest lap in 2024 R1 R: Driver={driver} (#{d_num}), LapTime={lap_time}")

        # Check session.pos_data keys and types
        if hasattr(session, "pos_data") and session.pos_data:
            print("session.pos_data keys:", list(session.pos_data.keys())[:5])
            print("key types:", [type(k) for k in list(session.pos_data.keys())[:3]])
            # Check str vs int access
            p_str = session.pos_data.get(str(d_num))
            p_int = session.pos_data.get(int(d_num)) if str(d_num).isdigit() else None
            print(f"Lookup str({d_num}): {p_str is not None}, int({d_num}): {p_int is not None}")
        else:
            print("session.pos_data is empty or not loaded from F1 livetiming stream.")

        try:
            pos_data = fastest_lap.get_pos_data()
            print(f"lap.get_pos_data() shape: {pos_data.shape}")
        except KeyError as ke:
            print(f"lap.get_pos_data() raised KeyError: {ke} (str vs int or missing driver in pos_data)")
        except Exception as e:
            print(f"lap.get_pos_data() error: {type(e).__name__}: {e}")

    except Exception as e:
        print(f"FastF1 probe error: {e}")

def probe_overpass_circuit():
    print("\n=== Probing OSM Overpass API for Monza (Bbox: 45.60, 9.26, 45.63, 9.30) ===")
    query = """[out:json][timeout:25];
(
  way["highway"="raceway"](45.60, 9.26, 45.63, 9.30);
  relation["highway"="raceway"](45.60, 9.26, 45.63, 9.30);
);
out geom;"""
    endpoints = [
        "https://overpass.kumi.systems/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
        "https://overpass-api.de/api/interpreter"
    ]
    for url in endpoints:
        req = urllib.request.Request(
            url,
            data=urllib.parse.urlencode({"data": query}).encode("utf-8"),
            headers={"User-Agent": "AI-Pitboss-F1-Telemetry/1.0 (telemetry@pitboss.local)"}
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                res = json.loads(resp.read())
                elems = res.get("elements", [])
                print(f"Overpass {url} SUCCESS: {len(elems)} elements found")
                for el in elems[:3]:
                    name = el.get("tags", {}).get("name", "unnamed")
                    geom = el.get("geometry", [])
                    print(f"  Element {el.get('type')} #{el.get('id')} '{name}': {len(geom)} points")
                return True
        except Exception as e:
            print(f"Overpass {url} error: {e}")
    return False

if __name__ == "__main__":
    probe_fastf1_lap_position()
    probe_overpass_circuit()
