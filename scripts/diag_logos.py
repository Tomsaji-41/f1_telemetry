"""
scripts/diag_logos.py — Trace and print each step of the team logo resolution chain.
"""
import sys
import os
import json
import urllib.request
import urllib.parse
from backend import logos, cache

USER_AGENT = "AI-Pitboss-F1-Telemetry/1.0 (https://github.com/f1_telemetry; telemetry@pitboss.local)"

def run_diagnostics(year: int = 2024):
    print(f"\n=========================================================================================")
    print(f"DIAGNOSTIC TRACE: Team Logos Resolution Pipeline (Season {year})")
    print(f"=========================================================================================\n")

    # Purge existing null entries
    purged = logos.purge_null_logo_cache()
    if purged:
        print(f"[Hygiene] Purged {purged} stale/null logo cache entries on startup.\n")

    j_url = f"https://api.jolpi.ca/ergast/f1/{year}/constructors.json?limit=100"
    req = urllib.request.Request(j_url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=12) as r:
        payload = json.loads(r.read())
    constructors = payload.get("MRData", {}).get("ConstructorTable", {}).get("Constructors", [])

    results = []

    for c in constructors:
        cid = c.get("constructorId")
        name = c.get("name")
        res = logos.resolve_team_logo(cid, year=year)

        failing_step = "NONE (SUCCESS)"
        reason = "Resolved via " + str(res.get("source") or "Wikidata/Commons")

        if not res.get("logoUrl"):
            failing_step = "Step 3/4: No P154 or Trademarked"
            reason = res.get("logoReason") or "No free license logo available"

        results.append({
            "team": f"{name} ({cid})",
            "cid": cid,
            "status": "OK" if res.get("logoUrl") else "NO_LOGO",
            "logoUrl": res.get("logoUrl") or "-",
            "source": res.get("source") or "-",
            "failing_step": failing_step,
            "reason": reason,
        })

    print(f"{'TEAM':<26} | {'STATUS':<8} | {'RESOLVED LOGO URL':<34} | {'FAILING STEP':<30} | {'REASON'}")
    print(f"{'='*130}")
    for r in results:
        t_str = r['team'][:26]
        s_str = r['status'][:8]
        u_str = r['logoUrl'][:34]
        fs_str = r['failing_step'][:30]
        re_str = r['reason'][:40]
        print(f"{t_str:<26} | {s_str:<8} | {u_str:<34} | {fs_str:<30} | {re_str}")
    print(f"{'='*130}\n")

if __name__ == "__main__":
    run_diagnostics(2024)
