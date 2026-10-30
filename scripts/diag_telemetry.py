"""
scripts/diag_telemetry.py
Diagnostic script using plain FastF1 without any app code.
Loads 2024 British GP Race and Qualifying, plus a comparison session.
Prints fastf1 version, car_data keys, pos_data keys, and exact exceptions.
"""
import sys
import traceback
import fastf1

print("================================================================")
print(f"DIAGNOSTIC TELEMETRY PROBE")
print(f"FastF1 Version: {fastf1.__version__}")
print("================================================================")

# Enable cache
fastf1.Cache.enable_cache("f1_cache")

sessions = [
    (2024, 12, "R", "2024 British GP - Race"),
    (2024, 12, "Q", "2024 British GP - Qualifying"),
    (2024, 1, "R", "2024 Bahrain GP - Race"),
]

for year, rnd, stype, label in sessions:
    print(f"\n--- Testing: {label} ({year} Round {rnd} '{stype}') ---")
    try:
        session = fastf1.get_session(year, rnd, stype)
        print(f"Event Resolved: {session.event.get('EventName', 'Unknown')} - Session: {session.name}")
        
        # Load with laps=True, telemetry=True, weather=False, messages=False
        session.load(laps=True, telemetry=True, weather=False, messages=False)
        print(f"Laps loaded: {len(session.laps) if hasattr(session, 'laps') and session.laps is not None else 0}")
        
        # Check car_data
        try:
            car_keys = list(session.car_data.keys())
            print(f"session.car_data: SUCCESS ({len(car_keys)} drivers: {car_keys[:5]})")
        except Exception as c_err:
            print(f"session.car_data: UNAVAILABLE ({type(c_err).__name__}: {c_err})")
            
        # Check pos_data
        try:
            pos_keys = list(session.pos_data.keys())
            print(f"session.pos_data: SUCCESS ({len(pos_keys)} drivers: {pos_keys[:5]})")
        except Exception as p_err:
            print(f"session.pos_data: UNAVAILABLE ({type(p_err).__name__}: {p_err})")

        # Try pick_fastest and get_car_data
        if hasattr(session, "laps") and not session.laps.empty:
            try:
                fastest = session.laps.pick_fastest()
                print(f"Fastest driver: {fastest.get('Driver')} (#{fastest.get('DriverNumber')})")
                cd = fastest.get_car_data()
                print(f"fastest.get_car_data(): SUCCESS (shape={cd.shape})")
            except Exception as f_err:
                print(f"fastest.get_car_data(): FAILED ({type(f_err).__name__}: {f_err})")

    except Exception as e:
        print(f"Session load raised: {type(e).__name__}: {e}")
        traceback.print_exc()

print("\n================================================================")
print("DIAGNOSTIC COMPLETE")
print("================================================================")
