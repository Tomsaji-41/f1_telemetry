"""
scripts/diag_fastf1.py
Diagnostic tool for FastF1 session loading, caching, and upstream availability.
"""
import sys
import os
import time
import traceback
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fastf1
from backend import config
from backend.sources import jolpica

def main():
    print("=== FastF1 Diagnostic Script ===")
    
    # Check cache dir
    cache_dir = Path(config.CACHE_DIR)
    print(f"Cache directory: {cache_dir}")
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        test_file = cache_dir / "_diag_test.tmp"
        test_file.write_text("ok")
        test_file.unlink()
        cache_writable = True
    except Exception as e:
        cache_writable = False
        print(f"Cache directory write error: {e}")
    print(f"Cache writable: {cache_writable}")

    fastf1.Cache.enable_cache(str(cache_dir))

    # Resolve latest completed session via Jolpica
    try:
        latest = jolpica.get_latest_completed_session()
        latest_year = latest.get("year", 2026)
        round_num = latest.get("round", 18)
        print(f"Latest completed session from Jolpica: Year {latest_year}, Round {round_num} ({latest.get('grand_prix')})")
    except Exception as e:
        print(f"Failed to resolve latest completed session: {e}")
        traceback.print_exc()
        return

    prev_year = latest_year - 1

    targets = [
        ("Latest completed session", latest_year, round_num),
        ("Same round one season earlier", prev_year, round_num),
    ]

    results = {}

    for label, y, r in targets:
        print(f"\n--- Testing {label}: {y} Round {r} ---")
        t0 = time.time()
        try:
            ses = fastf1.get_session(y, r, "R")
            ses.load(laps=True, telemetry=False, weather=True, messages=True)
            elapsed = time.time() - t0
            lap_count = len(ses.laps) if ses.laps is not None else 0
            print(f"SUCCESS: Loaded in {elapsed:.2f}s. Laps: {lap_count}")
            results[(y, r)] = {"success": True, "elapsed": elapsed, "laps": lap_count}
        except Exception as exc:
            elapsed = time.time() - t0
            print(f"FAILURE after {elapsed:.2f}s: {type(exc).__name__}: {exc}")
            traceback.print_exc()
            results[(y, r)] = {"success": False, "elapsed": elapsed, "error": str(exc), "type": type(exc).__name__}

    print("\n=== Interpretation ===")
    latest_ok = results.get((latest_year, round_num), {}).get("success", False)
    prev_ok = results.get((prev_year, round_num), {}).get("success", False)

    if latest_ok and prev_ok:
        print("Both latest and previous season loaded successfully via FastF1.")
    elif prev_ok and not latest_ok:
        print("INTERPRETATION: Older season works, latest fails -> upstream data availability delay, session not published, or FastF1 season parser difference.")
    elif not prev_ok and not latest_ok:
        print("INTERPRETATION: Both fail -> upstream F1 static live-timing authentication restriction (HTTP 401 on livetiming.formula1.com), network issue, or cache issue.")
    else:
        print("INTERPRETATION: Latest succeeded but older failed.")

if __name__ == "__main__":
    main()
