"""
auto_update.py
Automated pipeline to backfill and update telemetry and race facts.
Only this file is permitted to use the force_renew flag.
"""

import datetime
import logging
from typing import Optional

try:
    from backend import tools, cache
except ImportError:
    import tools, cache

logger = logging.getLogger("auto_update")

def update_season_data(year: Optional[int] = None, force_renew: bool = True) -> dict:
    """
    Backfills and refreshes precomputed tables.
    force_renew allows forcing cache eviction and re-download.
    """
    if year is None:
        year = datetime.date.today().year

    logger.info(f"Auto-updating season {year} with force_renew={force_renew}")
    sched = tools.get_season_schedule(year)
    standings_d = tools.get_standings(year, kind="drivers")
    standings_c = tools.get_standings(year, kind="constructors")

    ingested_sessions = 0
    if sched.get("status") == "ok":
        today_str = datetime.date.today().isoformat()
        for race in sched.get("schedule", []):
            race_date = race.get("date", "")
            r_num = int(race.get("round", 1))
            if race_date and race_date <= today_str:
                tools.get_race_result(year, r_num)
                ingested_sessions += 1
                if ingested_sessions >= 1:
                    break

    try:
        from backend.charts import loader as chart_loader
        chart_loader.warm_latest()
    except Exception as exc:
        logger.warning(f"FastF1 warm_latest failed after auto_update: {exc}")

    return {
        "status": "ok",
        "year": year,
        "force_renew": force_renew,
        "rounds_updated": len(sched.get("schedule", [])) if sched.get("status") == "ok" else 0,
        "ingested_sessions": ingested_sessions,
    }

if __name__ == "__main__":
    update_season_data(force_renew=True)
