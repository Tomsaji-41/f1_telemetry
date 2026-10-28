import json, sys, time
from datetime import date
from pathlib import Path
import requests

BASE = "https://api.jolpi.ca/ergast/f1"
OUT = "tests/data/golden_facts.jsonl"

def get(path):
    for attempt in range(3):
        try:
            r = requests.get(f"{BASE}/{path}.json", params={"limit": 1000}, timeout=10)
            if r.status_code == 200:
                return r.json()["MRData"]
        except Exception:
            pass
        time.sleep(1 + attempt)
    r.raise_for_status()

def sample_rounds(n):
    return sorted({1, max(1, n // 2), n})

def build(start, end):
    rows = []
    Path(OUT).parent.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    for year in range(start, end + 1):
        try:
            races_data = get(f"{year}")
            races = races_data.get("RaceTable", {}).get("Races", [])
        except Exception as e:
            print(f"Error fetching races for {year}: {e}")
            continue

        done = [r for r in races if r.get("date", "") <= today]
        if not done:
            continue
        for rnd in sample_rounds(len(done)):
            try:
                res_data = get(f"{year}/{rnd}/results")
                res = res_data.get("RaceTable", {}).get("Races", [])
                if not res or not res[0].get("Results"):
                    continue
                race = res[0]
                top = race["Results"][:3]
                rows.append({
                    "kind": "race",
                    "year": year, "round": rnd,
                    "race_name": race["raceName"],
                    "circuit": race["Circuit"]["circuitName"],
                    "locality": race["Circuit"]["Location"]["locality"],
                    "country": race["Circuit"]["Location"]["country"],
                    "date": race["date"],
                    "winner": f'{top[0]["Driver"]["givenName"]} {top[0]["Driver"]["familyName"]}',
                    "p2": top[1]["Driver"]["familyName"] if len(top) > 1 else None,
                    "p3": top[2]["Driver"]["familyName"] if len(top) > 2 else None,
                    "laps": race["Results"][0].get("laps"),
                    "question": f'Who won the {year} {race["raceName"]}?',
                })
                time.sleep(0.2)
            except Exception as e:
                print(f"Error fetching results for {year} round {rnd}: {e}")

        try:
            st = get(f"{year}/driverStandings").get("StandingsTable", {}).get("StandingsLists", [])
            if st:
                s = st[0]
                top3 = [d["Driver"]["familyName"] for d in s.get("DriverStandings", [])[:3]]
                rows.append({
                    "kind": "standings", "year": year, "after_round": int(s["round"]),
                    "total_rounds": len(races), "top3": top3,
                    "leader_points": float(s["DriverStandings"][0]["points"]),
                    "question": f"standings {year} drivers",
                })
        except Exception as e:
            print(f"Error fetching standings for {year}: {e}")

    with open(OUT, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} rows to {OUT}")

if __name__ == "__main__":
    start_year = int(sys.argv[1]) if len(sys.argv) > 1 else 2005
    end_year = int(sys.argv[2]) if len(sys.argv) > 2 else date.today().year
    build(start_year, end_year)
