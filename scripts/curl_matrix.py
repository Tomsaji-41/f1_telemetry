"""
scripts/curl_matrix.py
Generates the route audit matrix across all backend endpoints.
"""
import time
import json
import urllib.request
import urllib.error

ROUTES = [
    # Charts
    ("GET", "/api/charts/position-by-lap?year=2026&round=18"),
    ("GET", "/api/charts/grid-vs-finish?year=2026&round=18"),
    ("GET", "/api/charts/gap-evolution?year=2026&round=18"),
    ("GET", "/api/charts/stints?year=2026&round=18"),
    ("GET", "/api/charts/degradation?year=2026&round=18&driver=VER"),
    ("GET", "/api/charts/pit-stops?year=2026&round=18"),
    ("GET", "/api/charts/sector-heatmap?year=2026&round=18"),
    ("GET", "/api/charts/weather?year=2026&round=18"),
    ("GET", "/api/charts/quali-gap?year=2026&round=18"),
    ("GET", "/api/charts/lap-scatter?year=2026&round=18"),
    ("GET", "/api/charts/championship-progression?year=2026&kind=drivers"),
    ("GET", "/api/charts/finish-heatmap?year=2026"),
    ("GET", "/api/charts/team-pace?year=2026&round=18"),
    
    # Telemetry / Replay
    ("GET", "/api/replay/2026/18/lap/1"),
    ("GET", "/api/live/status"),
    ("GET", "/api/v1/telemetry/2026/18/VER/NOR"),
    
    # Core Data
    ("GET", "/api/sessions/available"),
    ("GET", "/api/schedule?year=2026"),
    ("GET", "/api/standings?year=2026"),
    ("GET", "/api/drivers?year=2026"),
    ("GET", "/api/drivers/ver"),
    ("GET", "/api/teams?year=2026"),
    ("GET", "/api/teams/red_bull"),
    ("GET", "/api/legends"),
    ("GET", "/api/eras"),
    
    # Chat
    ("POST", "/api/chat", {"text": "who won monza 2023"}),
]

BASE_URL = "http://127.0.0.1:8000"

def main():
    print(f"{'Method':<6} | {'Route':<50} | {'Code':<5} | {'Latency':<8} | {'Status':<12} | {'Source':<10} | {'Len(Series)':<11} | {'Error'}")
    print("-" * 135)
    
    for item in ROUTES:
        method = item[0]
        route = item[1]
        body = item[2] if len(item) > 2 else None
        
        url = f"{BASE_URL}{route}"
        t0 = time.time()
        
        req = urllib.request.Request(url, method=method)
        if body:
            data_bytes = json.dumps(body).encode("utf-8")
            req.add_header("Content-Type", "application/json")
        else:
            data_bytes = None
            
        try:
            with urllib.request.urlopen(req, data=data_bytes, timeout=15) as resp:
                latency = f"{(time.time() - t0):.2f}s"
                code = resp.status
                payload = json.loads(resp.read().decode("utf-8"))
                
                status = payload.get("status", "ok")
                source = payload.get("source", "-")
                
                # Check series len
                s = payload.get("series") or payload.get("rows") or payload.get("stints") or payload.get("stops") or payload.get("drivers") or payload.get("schedule") or payload.get("standings") or payload.get("teams") or []
                series_len = len(s) if isinstance(s, list) else "-"
                
                err = payload.get("error") or payload.get("coverage_note") or ""
                if len(err) > 30: err = err[:27] + "..."
                print(f"{method:<6} | {route:<50} | {code:<5} | {latency:<8} | {str(status):<12} | {str(source):<10} | {str(series_len):<11} | {err}")
        except urllib.error.HTTPError as e:
            latency = f"{(time.time() - t0):.2f}s"
            code = e.code
            err_body = e.read().decode("utf-8")
            print(f"{method:<6} | {route:<50} | {code:<5} | {latency:<8} | {'ERROR':<12} | {'-':<10} | {'-':<11} | {err_body[:30]}")
        except Exception as exc:
            latency = f"{(time.time() - t0):.2f}s"
            print(f"{method:<6} | {route:<50} | {'ERR':<5} | {latency:<8} | {'FAIL':<12} | {'-':<10} | {'-':<11} | {str(exc)[:30]}")

if __name__ == "__main__":
    main()
