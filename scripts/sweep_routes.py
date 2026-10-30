"""Route sweep script: tests all registered routes for 500 errors."""
import sys
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

schema = app.openapi()
paths = schema.get("paths", {})

errors = []
successes = []

# Parameter replacements for routes with path parameters
param_map = {
    "{circuit_id}": "monza",
    "{driver}": "verstappen",
    "{driver_id}": "verstappen",
    "{constructor_id}": "red_bull",
    "{team_id}": "red_bull",
    "{year}": "2024",
    "{round}": "1",
    "{round_num}": "1",
    "{driver1}": "verstappen",
    "{driver2}": "norris",
    "{lap_num}": "1",
    "{job_id}": "test-job",
    "{name}": "jolpica",
}

print(f"Sweeping {len(paths)} OpenAPI paths...")

for path, methods in sorted(paths.items()):
    for method in methods:
        if method.lower() != "get":
            continue

        resolved_path = path
        for param, val in param_map.items():
            resolved_path = resolved_path.replace(param, val)

        if "stream" in path:
            print(f"[SSE STREAM SKIP] {path}")
            successes.append((path, resolved_path, "SSE"))
            continue

        try:
            resp = client.get(resolved_path)
            status = resp.status_code
            if status >= 500:
                print(f"[FAIL 500] {path} -> {resolved_path}: {status}")
                errors.append((path, resolved_path, status, resp.text[:200]))
            else:
                successes.append((path, resolved_path, status))
        except Exception as e:
            print(f"[EXCEPTION] {path} -> {resolved_path}: {e}")
            errors.append((path, resolved_path, "EXCEPTION", str(e)))

print(f"\n--- Sweep Results ---")
print(f"Successful non-500 endpoints: {len(successes)}")
print(f"500 / Exception endpoints: {len(errors)}")

if errors:
    print("\nFAILURES:")
    for path, resolved, status, body in errors:
        print(f"  {resolved} -> {status}: {body}")
    sys.exit(1)
else:
    print("All GET endpoints returned non-500!")
