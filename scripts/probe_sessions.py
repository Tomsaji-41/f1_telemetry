import fastf1
import fastf1.api

fastf1.Cache.enable_cache("f1_cache")

test_sessions = [
    (2023, 1, "R"),
    (2023, 22, "R"),
    (2022, 1, "R"),
    (2021, 1, "R"),
    (2024, 1, "R"),
    (2024, 12, "R"),
]

for y, r, s in test_sessions:
    try:
        ses = fastf1.get_session(y, r, s)
        ev_name = ses.event["EventName"] if hasattr(ses, "event") else "Unknown"
        cdata = fastf1.api.car_data(ses.api_path)
        print(f"{y} R{r} {s} ({ev_name}): SUCCESS ({len(cdata)} drivers: {list(cdata.keys())[:5]})")
    except Exception as e:
        print(f"{y} R{r} {s}: FAILED ({type(e).__name__}: {e})")

