# AI Pitboss v5: Telemetry, Strategy & Grounded Chatbot

AI Pitboss is a zero-hallucination Formula 1 telemetry, race strategy, and engineering assistant. Built on a strict **Nothing Hardcoded Prime Rule**, the system never hardcodes years, drivers, teams, circuits, results, points, lap times, team colors, or image URLs. Every data point is fetched and computed dynamically at runtime from official and verified APIs (Jolpica, FastF1, OpenF1, Wikipedia).

---

## 1. Data Sources & Coverage Windows

| Source | Coverage Years | Capabilities & Endpoints |
|---|---|---|
| **Jolpica-F1 (REST)** | **1950 – Present** | Schedules, race classifications, qualifying results, championship standings, circuits, drivers, constructors, pit stops (2012+). |
| **FastF1 (Python)** | **2018 – Present** | Lap-by-lap timing, sector analysis (S1/S2/S3), tyre compound stints, tyre degradation modeling, telemetry comparison, weather, race control messages. |
| **OpenF1 (REST)** | **2023 – Present** | Real-time session data, driver headshots, official team hex colors. |
| **Local Cache** | Multi-tier | FastF1 disk cache + SQLite TTL cache for Jolpica & OpenF1 responses. |

### Honest Limits Rule
- Detailed lap, sector, and tyre data exists from **2018 onward only**.
- Pit stop duration and timing data exists from **2012 onward only**.
- OpenF1 live telemetry covers **2023 onward only**.
- Future sessions or unrecorded sessions return an explicit `"not_available"` status rather than fabricated estimates.

---

## 2. Chart Catalogue (12 Columnar Endpoints)

All chart endpoints return a standardized columnar structure:
```json
{
  "status": "ok",
  "source": "FastF1",
  "coverage_note": "Detailed lap data exists from 2018 only.",
  "fetched_at": "2026-10-27T04:24:00Z",
  "series": [...],
  "axes": {"x": {...}, "y": {...}}
}
```

| Route | Description | Visualization Component |
|---|---|---|
| `/api/charts/position-by-lap` | Lap-by-lap driver positions (Bump chart) | `PositionByLapChart` (D3/SVG) |
| `/api/charts/gap-evolution` | Gap to leader in seconds over race distance (Inverted Y) | `GapEvolutionChart` (D3/SVG) |
| `/api/charts/stints` | Compound sequence, start/end lap, pit stop ticks | `TyreStintGantt` (Gantt) |
| `/api/charts/degradation` | Fuel-corrected degradation slope (seconds/lap) | Regression scatter |
| `/api/charts/pit-stops` | Pit stop lap and stationary duration (seconds) | Pit bar timeline |
| `/api/charts/grid-vs-finish` | Starting grid vs finishing position slope | `GridVsFinishChart` (Slope chart) |
| `/api/charts/championship-progression` | Cumulative points progression round by round | `ChampionshipProgressionChart` |
| `/api/charts/sector-heatmap` | S1, S2, S3 best deltas per driver | Heatmap grid |
| `/api/charts/quali-gap` | Qualifying delta to pole (Q1, Q2, Q3) | Delta bar chart |
| `/api/charts/lap-scatter` | Lap time distribution by tyre compound | Compound scatter plot |
| `/api/charts/finish-heatmap` | Driver finishes across full season | Season finish matrix |
| `/api/charts/team-pace` | Median race lap pace delta relative to fastest team | Pace delta box/bar chart |

---

## 3. Chat State Machine & Turn Pipeline

```
User Message
    │
    ▼
[State Check: Pending Slot Clarification?]
    ├── YES ──> Attempt to bind user input to pending slot
    │            ├── Bound successfully ──> Execute Pending Intent with resolved args
    │            └── "Cancel" or "Start over" ──> Clear pending slot & proceed
    │
    └── NO ──> Classify Intent (Parser & NLU)
                 ├── Bare Driver Name ──> Emit `driver_profile` with `EntityCardBlock`
                 ├── Multi-Metric (e.g. "podiums and points") ──> Dual blocks (Podiums + Standings)
                 ├── Missing Critical Slots ──> Prompt Clarification with >= 2 chips + "Cancel / Start over"
                 └── Fully Specified ──> Execute Tools from `TOOL_REGISTRY`
                          │
                          ▼
                   [Verifier Engine]
                   (Validates all numbers against tool returns; rewrites if ungrounded)
                          │
                          ▼
                   [SSE Stream Output]
                   (Includes turn_id, structured blocks, sources, and UTC timestamp)
```

### Response Block Types
- **`EntityCardBlock`**: Rendered for drivers or teams with verified stats, photo, team color, and quick-action chips.
- **`TableBlock`**: Formatted classification, standings, or sector tables with sortable columns and B8-compliant gap formatting (`Winner`, `+X.XXXs`, `+1 Lap`, `DNF`).
- **`ChartBlock`**: Embedded interactive charts directly inside the chat stream.
- **`StatusBlock`**: Grounded status notifications (e.g., honest coverage limit warnings).
- **`FollowupChip`**: Interactive suggestions and clarifications.

---

## 4. How to Add a New Tool

1. **Implement the function in `backend/tools.py`**:
   ```python
   def get_new_metric(year: int, grand_prix: str) -> Dict[str, Any]:
       """
       Detailed docstring describing tool purpose and inputs.
       """
       resolved = resolver.resolve_gp(grand_prix, year)
       if resolved.get("status") != "ok":
           return resolved

       data = ... # fetch from source
       return {
           "status": "ok",
           "metric_value": 42.0,
           "source": "Jolpica",
           "coverage_note": "Available from 2018 to present."
       }
   ```

2. **Register the function in `TOOL_REGISTRY`** (`backend/tools.py`):
   ```python
   TOOL_REGISTRY = [
       ...
       get_new_metric,
   ]
   ```

3. **Add regression tests** in `tests/test_tools.py`.

---

## 5. How to Add a New Chart

1. **Add route in `backend/chart_routes.py`**:
   ```python
   @router.get("/api/charts/my-new-chart")
   def chart_my_new_chart(year: int = 2023, round: int = 14):
       # Pull from FastF1 or Jolpica
       return {
           "status": "ok",
           "source": "FastF1",
           "coverage_note": "Detailed lap data from 2018+",
           "fetched_at": format_utc_timestamp(),
           "series": [...],
           "axes": {"x": {"label": "Lap"}, "y": {"label": "Value"}}
       }
   ```

2. **Wrap in `ChartShell` in `frontend/src/components/charts/`**:
   Use `ChartShell` to automatically inherit F1 shared rules: title, subtitle, source tag, table view toggle, and CSV export.

---

### Quick Start (Combined Frontend & Backend)
Run either launcher from the project root:
```cmd
# Windows Command Prompt / Double-click
run_all.bat

# Or PowerShell
.\run_all.ps1

# Or npm
npm run dev
```
Both servers will start concurrently:
- **Backend API & Swagger Docs**: `http://localhost:8000/docs`
- **Frontend Dashboard**: `http://localhost:3000`

---

### Backend (FastAPI) Individually
```bash
# Activate virtual environment
.venv\Scripts\activate   # Windows
# source .venv/bin/activate # Unix

# Start FastAPI server
.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000
```
- API Documentation: `http://localhost:8000/docs`
- Health Endpoint: `http://localhost:8000/api/health`

### Frontend (Next.js)
```bash
cd frontend
npm run dev
```
- Dashboard Hub: `http://localhost:3000`
- Analytics Studio: `http://localhost:3000/analytics`
- Telemetry: `http://localhost:3000/telemetry`
- Drivers: `http://localhost:3000/drivers`
- Constructors: `http://localhost:3000/teams`
- Dedicated Pit Boss: `http://localhost:3000/pit-boss` (or press `P` anywhere)

### Running Tests
```bash
# Backend pytest suite (53 tests)
.venv\Scripts\python.exe -m pytest tests -v

# Frontend Vitest suite
cd frontend && npm test -- --run
```

---

## 5. User-Supplied Team Logo Overrides

For teams where freely licensed logos are unavailable on Wikimedia Commons due to trademark or copyright restrictions (such as Ferrari or Red Bull), users can supply local logo image files:

- **Configurable Directory**: Set via the `LOGO_OVERRIDE_DIR` environment variable (defaults to `assets/logos/`).
- **File Naming**: Place files named `<constructorId>.svg`, `<constructorId>.png`, or `<constructorId>.jpg` in this directory (e.g. `assets/logos/ferrari.png`, `assets/logos/red_bull.png`, `assets/logos/aston_martin.svg`).
- **Priority**: Files in the override directory always take precedence over runtime Wikidata resolution.
- **Trademark Notice**: Formula 1 team logos, crests, and emblems are registered trademarks of their respective Formula One constructors and entities. Ensure you have the appropriate permissions, rights, and attribution for any custom logo assets you supply.

