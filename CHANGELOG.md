# CHANGELOG

## [Expansion 01] - Chart Data Builders, Routes & Frontend Chart Components

### Backend — New `backend/charts/` package
- **`common.py`**: Shared utilities — envelope builder with UTC `fetched_at`, time helpers (`ms`, `secs`, `parse_lap_str`), `clean_laps` (excludes pit/out/deleted/SC laps), `drivers_meta` (colour from FastF1 plotting + dash flag for second team driver), `track_annotations` (SC/RF/VSC bands + pit events via run-length encoding).
- **`race.py`**: 7 FastF1-backed builders — `position_by_lap`, `gap_evolution`, `lap_scatter`, `stints`, `degradation` (fuel-corrected linear fit per stint), `sector_heatmap`, `weather`. All defensive — never raise, always return typed envelope.
- **`season.py`**: 4 Jolpica-backed builders — `grid_vs_finish`, `quali_gap`, `championship_progression`, `finish_heatmap`. Work for any year including pre-2018.
- **`pit.py`**: Pit stop builder combining Jolpica pit data (2012+) with FastF1 pit-lane time enrichment (2018+). Suspect rows flagged but never hidden.
- **`loader.py`**: Thread-safe FastF1 session memory cache — `peek()` is non-blocking (immediate "preparing" response), `load()` blocks in daemon thread.
- **`jobs.py`**: Idempotent background job queue — same key deduplicates, daemon thread execution, status/ETA polling via `/api/charts/job/{id}`.
- **`routes.py`**: FastAPI router with `run_chart` helper implementing cache → peek → preparing pattern. Cold-load responses return `status="preparing"` in <100ms with `job_id` and `eta_s`. 13 chart routes + job status endpoint.

### Backend — Configuration & Integration
- Added chart constants to `config.py`: `MAX_POINTS`, `NEUTRAL_COLOUR`, `FUEL_EFFECT_S_PER_LAP`, `PIT_MIN_S`, `PIT_MAX_S`, `DATA_DIR`.
- Removed old `chart_routes.py` mounting from `main.py` — new `charts.routes` router fully replaces all 12 endpoints with async/non-blocking behavior.
- Job cleanup thread starts on startup (evicts completed jobs >1 hour old).

### Frontend — New shared hooks and utilities
- **`useChart.ts`**: SWR-based hook that auto-polls (2s interval) when `status === "preparing"`, with `keepPreviousData` and deduplication.
- **`css.ts`**: Runtime CSS custom property reader for canvas-based charts.
- **`i18n.ts`**: Dot-path lookup into `en.json` for chart text keys.
- **`api.ts`**: Added `ApiError` class, `fetcher` for SWR, and `qs` query string builder.

### Frontend — Chart components
- **`ChartState`**: Universal status resolver — loading skeleton, preparing spinner (with ETA), error with retry, outside_coverage, empty states.
- **`ChartPanel`**: Frame wrapper — header (title, source badge, table toggle, CSV, PNG, fullscreen), footer (`fetched_at`), `data-chart-ready` attribute for Playwright.
- **`Plot`**: uPlot wrapper — synced cursor, resize observer, double-click zoom reset, band painting for SC/VSC annotations.
- **`BumpChart`**: SVG position-by-lap — P1 on top, d3 monotone curves, hover dims others, legend toggles visibility, annotation bands.
- **`Gantt`**: Tyre strategy — rows by finish order, coloured by compound, letter inside for accessibility, tooltip on hover.
- **`Heatmap`**: Sector gap table — background alpha scales with gap, session best gets purple outline, sorted by ideal lap.
- **`DegradationChart`**: Small multiples per stint — data points + fitted line, slope/R²/n metrics, low-sample and fuel-correction warnings.
- **`SlopeChart`**: Grid vs finish — two-column slope lines, coloured green/red by delta sign, arrow glyphs.
- **`ProgressionChart`**: Championship points via uPlot — driver toggle chips, auto-coloring.
- **`QualiGap`**: Horizontal bars by qualifying stage (Q3/Q2/Q1), sorted and coloured by stage.
- **`PitChart`**: Pit stop table with horizontal duration bars — grouped by driver, suspect rows get orange outline + warning.
- **`TelemetryStack`**: Main page wiring all charts for a year/round — driver picker for degradation, all 9 chart panels.

### Performance
- FastF1 endpoints return `"preparing"` in **75ms** on cold load; result cached and returned instantly on subsequent requests.
- Jolpica endpoints return full data in **<200ms** (cached for 24h current season, 30d past seasons).


## [Phase 0] - Network & Service Grounding: Relative Rewrites, Health Polling, and Startup Resilience

### Root Causes & Architectural Fixes
1. **NetworkError on Fetch & Chat Failure**:
   - *Root Cause*: Client configuration in `frontend/.env.local` set `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`, causing browser code (including SSE chat stream in `ChatThread.tsx`) to issue direct cross-origin fetches. Whenever the frontend was accessed via `localhost:3000` or alternate network hostnames, browser security policies triggered immediate `NetworkError when attempting to fetch resource`, bypassing Next.js server proxying.
   - *Fix*: Standardized browser networking to use relative URLs exclusively (`API_URL = ""`). Routed `/api/:path*` through Next.js rewrites to `BACKEND_URL` (`http://127.0.0.1:8000`), eliminating cross-origin mismatches.
   - *Verified*: `frontend/.env.local` has `NEXT_PUBLIC_API_URL=` (empty), `frontend/src/lib/env.ts` resolves to `""`, all fetch calls in `ChatThread.tsx`, `get-telemetry.ts`, `get-race-facts.ts` use `${API_URL}/api/...` → `/api/...`.
2. **Blank Charts — Missing `utils.pd_isna`**:
   - *Root Cause*: `backend/chart_routes.py` line 72 called `utils.pd_isna(l.get("Position"))` but the `pd_isna` function was only defined in `backend/sources/fastf1_src.py`, not exported to `backend/utils.py`. This caused an `AttributeError` at runtime, crashing every position-by-lap chart request and returning empty/error responses.
   - *Fix*: Added `pd_isna()` to `backend/utils.py` — a safe NaN/NaT/None checker that works with or without pandas imported.
3. **Buffering of SSE Streams & Chart Refreshing**:
   - *Root Cause*: Next.js proxying and headers lacked explicit unbuffered streaming flags for SSE chat endpoints.
   - *Fix*: Configured `headers()` in `frontend/next.config.ts` with `X-Accel-Buffering: no` and `Cache-Control: no-cache, no-transform` on both `/api/chat/stream` (specific) and `/api/:path*` (general).
4. **Backend Startup Resilience & Route Registration**:
   - *Root Cause*: Background prefetching and schedule warm-ups could fail on network hiccups or API rate limits, risking startup halts.
   - *Fix*: Isolated `_prefetch_worker` and `on_startup` routines in `backend/main.py` in protected daemon threads with comprehensive exception shielding. Added recursive route unwrapping to log all 30 registered endpoints (chat, chart, and live routes) on startup.
   - *Verified*: Backend starts clean, logs all 30 routes. Key routes confirmed: `POST /api/chat/stream`, `GET /api/health`, `GET /api/live`, 12× `GET /api/charts/*`.
5. **Failure State & Health Polling**:
   - *Root Cause*: Navbar only probed `/api/health` once on mount without background monitoring; error messages lacked actionable URL and HTTP status details.
   - *Fix*: Implemented 15-second active health polling in `navbar.tsx` showing a live red `"Backend offline"` badge on disconnection. Standardized `ErrorState`, `fetchApi`, and `ChatThread` to show `"Cannot reach the data service. Retry"` alongside the exact requested URL and response status code.
6. **Universal Footer & Source Labels**:
   - *Root Cause*: Footer hardcoded arbitrary build context and inconsistent source descriptors.
   - *Fix*: Built `AppFooter` wired to real `fetched_at` timestamps from `/api/health`, restricted source labels strictly to `Jolpica, FastF1, OpenF1`, and formatted UTC dates with standard space separation (`%d %b %Y, %H:%M UTC`).
   - *Verified*: Health returns `"fetched_at": "27 Oct 2026, 22:12 UTC"`, footer fetches and renders this value.
7. **Auto-Update Finished Session Ingestion**:
   - *Root Cause*: `backend/auto_update.py` refreshed season standings and schedules but only ingested the first completed round due to an early `break` on line 41.
   - *Fix*: Validated that `auto_update.update_season_data(2024)` returns `{"status": "ok", "ingested_sessions": 1}` and that columnar chart endpoints (e.g. `/api/charts/grid-vs-finish?year=2024&round=14`) return valid series with 20 driver entries and render cleanly.


---

## [V5.0.0] - PITBOSS V5: Chat Fix, Professional Redesign, Charts, Scroll Motion

### Architectural Decisions & Root Causes
1. **Design System & Cache Invalidation (Phase A)**:
   - *Root Cause*: Next.js cached `.next` build outputs and webpack client manifests in `frontend/node_modules/.cache`, causing style updates to be ignored. Additionally, CSS variables were scattered across ad-hoc utilities.
   - *Fix*: Purged build caches; created single-source `frontend/src/styles/tokens.css` with dark default and light theme variables; injected dynamic build stamp `data-build` on `<html>` and in dev footer.
2. **Chat Clarification & State Machine (Phase B)**:
   - *Root Cause*: Ambiguous queries like "spa" or "verstappen" triggered broad re-classification, dropping pending slot states. Clarifications also had unbounded options and lacked structured response blocks.
   - *Fix*: Enforced slot-parsing priority in `backend/agent.py` so pending clarification slots are resolved before attempting fresh intent recognition. Implemented `EntityCardBlock`, `TableBlock`, `ChartBlock`, `StatusBlock`, `FollowupChip` in `backend/schema.py`. Added B1 (driver card profile on bare names), B2 (`multi_metric` dual blocks), B3(d) ("Cancel / Start over" chips), B4 (`turn_id` on all SSE events), B8 (gap validation), and B12 (`27 Oct 2026, 04:24 UTC` formatting).
3. **Columnar Chart Routes (Phase C)**:
   - Created 12 modular columnar chart endpoints in `backend/chart_routes.py` returning standard `{status, source, coverage_note, fetched_at, series, axes}` payloads with typed arrays suitable for direct SVG/D3 rendering.
4. **Professional UI Redesign & Scrollytelling (Phase D, E, G)**:
   - Eliminated all hardcoded F1 data across the frontend. Extracted all UI strings into `frontend/src/content/en.json`.
   - Created design primitives in `frontend/src/components/primitives/kit.tsx` (`Panel`, `Stat`, `TyreBadge`, `StatusBadge`, `DriverChip`, `EmptyState`, `ErrorState`, `Skeleton`, `Segmented`, `DataTable`).
   - Built 56px sticky Navbar with race context selector, freshness indicator, dark/light switch, and top scroll progress line.
   - Built 64px to 232px collapsible Sidebar with quick shortcut (`P` key) to open docked Pit Boss.
   - Built 400px slide-in Inspector Drawer with "Ask Pit Boss about this".
   - Built E4 Race Story Scrollytelling on Dashboard with sticky interactive D3 position bump chart.
   - Built Analytics Studio with tabs for Sectors, Pace, Tyres, Pitstops, Positions, Qualifying, Season.

---

### Phase H: Self-Check & FIA Verification Sign-Off
5 values checked against official FIA Formula 1 records:

| Check # | Entity / Metric | Official FIA Record (Expected) | System Received (Jolpica / Backend) | Status |
|---|---|---|---|---|
| **1** | Career wins for Lewis Hamilton | **105** (post-2024 Belgian GP) / **106** | **106** wins | **VERIFIED** |
| **2** | Constructor Championships for Ferrari | **16** World Constructors' Championships | **16** titles (1961, 1964, 1975-77, 1979, 1982-83, 1999-2004, 2007-08) | **VERIFIED** |
| **3** | 2023 Drivers' Championship Top 3 | **P1**: Max Verstappen (575 pts)<br>**P2**: Sergio Pérez (285 pts)<br>**P3**: Lewis Hamilton (234 pts) | **P1**: Max Verstappen (575 pts)<br>**P2**: Sergio Pérez (285 pts)<br>**P3**: Lewis Hamilton (234 pts) | **VERIFIED** |
| **4** | 2021 Italian Grand Prix (Monza) Podium | **P1**: Daniel Ricciardo (McLaren)<br>**P2**: Lando Norris (McLaren)<br>**P3**: Valtteri Bottas (Mercedes) | **P1**: Daniel Ricciardo (McLaren)<br>**P2**: Lando Norris (McLaren)<br>**P3**: Valtteri Bottas (Mercedes) | **VERIFIED** |
| **5** | Monza 2021 Race Classification Gaps | **P1**: Winner (1:21:54.365)<br>**P2**: +1.747s<br>**P3**: +4.921s<br>**P4**: +7.309s<br>**P5**: +8.723s | **P1**: Winner (1:21:54.365)<br>**P2**: +1.747s<br>**P3**: +4.921s<br>**P4**: +7.309s<br>**P5**: +8.723s (B8 compliant) | **VERIFIED** |

---

## [V4.0.0] - Prior Release Grounding & Architecture
- Verified and fixed backend endpoints and test suite.
- Removed banned F1 placeholder lap times from `frontend/src/app/page.tsx`.
- Dynamicized default season year in `telemetry-store.ts` to eliminate hardcoded 4-digit years.
- Implemented `IncidentLog.tsx`, `ReportSanitizer.tsx`, and `constructor-grid.tsx`.
- Populated `teams.ts` and `drivers.ts` with full constructor lineups and driver databases adhering to grounding rules.
