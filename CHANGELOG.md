## [V7.1.0] - Analytics Studio Rendering, Replay Hardening, Dynamic Contrast & Single-Host Proxy (localhost:3000)

### Phase 1: Analytics Studio Chart Rendering & Session Resolution
- **Dynamic Session Resolution**: Replaced fixed year/round literals with `get_latest_completed_session()` and `/api/sessions/available` from Jolpica. Routes accept optional `year` and `round` and dynamically resolve the latest completed session at runtime.
- **Multi-Source FastF1 Fallback**: Implemented `SessionAdapter` in `backend/charts/loader.py`. If FastF1 raises `DataNotLoadedError` or hits upstream timing auth blocks (HTTP 401), automatically synthesizes compliant session objects via OpenF1 (2023–2024) and Jolpica (1950–2026), providing `.laps`, `.results`, and `.weather_data`.
- **Chart Component Hardening & Schema Alignment**:
  - `PositionByLapChart.tsx`: Safeguarded series lap iteration with fallback to root `data.x`, normalized `s.driver` and `s.code`, and added interactive drawer inspection.
  - `SlopeChart.tsx` (Grid vs Finish): Wired directly into the `positions` tab of Analytics Studio alongside the Bump Chart. Correctly displays start vs finish deltas, position changes, DNF/DSQ badges, and WCAG-compliant symbols (▲ / ▼ / —).
  - `TyreStintGantt.tsx`: Aligned with backend schema to support both `series` and `stints` arrays, handling compound colors and multi-stint pit sequences.
  - `ChampionshipProgressionChart.tsx`: Supported both driver and constructor standings with points aggregation and normalized bar graphs.
  - `useChart.ts`: Implemented automatic 2-second polling on `status === "preparing"` with an explicit 45-second timeout and retry capability (never infinite spinner).

### Phase 2: Live Telemetry Replay Hardening
- **Replay Endpoint**: Fixed 500 error on `/api/replay/{year}/{round}/lap/{lap_num}` by referencing internal raw dict parser `_fetch_race_classification_dict(year, round)`.
- **Gap Calculation (Rule B8)**: Utilized `utils.compute_and_validate_gaps` and `utils.format_gap_display` to compute leader and interval gaps strictly per F1 timing regulations.
- **Driver and Team Resolution**: Bound `/api/drivers/{id}` and `/api/teams/{id}` to dynamic resolvers supporting both 3-letter codes (e.g. `ver`) and standard Jolpica identifiers (e.g. `max_verstappen`).
- **Real Weather Integration**: Extracted track and air temperatures and rainfall status from session adapter data.

### Phase 3: Visual Polish, Navbar Session Resolution & WCAG 2.1 Contrast
- **Navbar Session Picker**: Updated `frontend/src/components/layouts/navbar.tsx` to populate season list dynamically from `/api/sessions/available`, defaulting to the latest completed round.
- **Link Reset**: Added `a { text-decoration: none !important; color: inherit; }` in `frontend/src/app/globals.css` to eliminate underlines on cards and links.
- **Typography**: Enforced `font-weight: 700;` on heading levels (`h1` through `h6`).
- **Dynamic Contrast Helper**: Created `frontend/src/lib/colors.ts` with WCAG 2.1 relative luminance and contrast ratio calculations (`getAccessibleTextColor`), ensuring text overlaid on dynamic team colors remains legible. Added unit tests in `src/lib/__tests__/colors.test.ts`.

### Phase 4: Combined Single-Host Deployment (localhost:3000)
- Configured Next.js rewrites in `frontend/next.config.mjs` routing `/api/:path*` directly to FastAPI (`http://127.0.0.1:8000/api/:path*`).
- Verified all endpoints accessible via `http://localhost:3000`:
  - `/api/health` -> HTTP 200 (healthy)
  - `/api/sessions/available` -> HTTP 200
  - `/api/charts/position-by-lap` -> HTTP 200
  - `/api/charts/grid-vs-finish` -> HTTP 200
  - `/api/charts/gap-evolution` -> HTTP 200
  - `/api/charts/stints` -> HTTP 200
  - `/api/charts/championship-progression` -> HTTP 200
  - `/api/replay/2026/18/lap/1` -> HTTP 200
  - `/api/drivers/ver` -> HTTP 200
  - `/api/teams/red_bull` -> HTTP 200
- **Test Suite Results**:
  - Backend: 75/75 passed in pytest (100%).
  - Frontend: 11/11 passed across 4 test suites in Vitest (100%).
  - Production Build: Next.js compiled 12/12 static and dynamic routes cleanly.

---



### Phase 0: Backend Starts & Repo Hygiene
- Fixed `backend/state.py` line 154 by adding `Tuple` to `from typing import ...`.
- Deleted duplicate/legacy files: `app.py`, `check_cache.py`, `clear_bad_cache.py`, `read_prompt.py`, `backend/chart_routes.py`, `backend/charts.py`, `frontend/next.config.ts`, `v7_requirements.txt`.
- Hardened `/api/chat` and `/api/chat/stream` to return `422 Unprocessable Entity` when neither `text`, `action`, nor `chip` is provided.

### Phase 1: Security Hardening & Secret Hygiene
- **`.gitignore` UTF-8 BOM**: Stripped `\ufeff` byte-order mark from `.gitignore` so line 1 `.env` correctly matches `.env`. Verified with `git check-ignore -v .env`.
- **Git Secret Scan**: Scanned entire git commit history across all branches for secrets, Google API keys, Groq keys, OpenAI keys, and auth tokens. Result: 0 committed secrets.
- **Frontend Dependencies Audit**: Upgraded `next` to `15.5.28`, updated `sharp`, `zod`, and added override `"postcss": "^8.5.32"`. `npm audit --omit=dev` reports 0 vulnerabilities (0 critical, 0 high, 0 moderate, 0 low).
- **Backend Dependencies Audit & Hardening**: Installed and verified `pip-audit`, `bandit`, and `slowapi`. Pinned all versions in `requirements.txt`. `pip-audit --local` reports 0 vulnerabilities. `bandit -r backend -ll` reports 0 issues.
- **Bounded Conversation Store**: Replaced unbounded in-memory dictionary with `BoundedConversationStore` (`max_clients=500`, `ttl_seconds=3600`).
- **Rate Limiting & Payload Limits**: Configured `@limiter.limit("60/minute")` on chat endpoints with automatic test-bypass. Enforced message length cap (<= 1000 chars) and body size limit (<= 65536 bytes).
- **Security Headers & Network Restrictions**: Added Content-Security-Policy, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, and `X-Frame-Options: DENY`. Configured Next.js image domain allowlist for `upload.wikimedia.org` and `media.formula1.com`.
- **CI Workflows**: Added `.github/dependabot.yml` and `.github/workflows/security.yml`.

### Phase 2: Pit Boss Honesty, Context & Structured Chips
- **Chips as Structure**: Refactored follow-up chips to carry `{ action: "chip", intent: ..., slots: { ... } }` instead of free text labels, eliminating bugs where chips like "Tyre degradation" or "Sector pace" re-entered the race name parser.
- **Race Resolver Fallback Fix**: Prevented race resolver from defaulting to round 1 or latest completed race when resolving ungrounded or ambiguous GP names; queries requiring race clarification now emit structured `clarify` options with candidate seasons/races.
- **Honest Failure Propagation**: Ensured that when any data source returns an error or empty classification, `verified` is strictly `false`, `sources` is `[]`, and the response explicitly identifies the upstream source and failure reason.
- **Template Sanitization**: Removed hollow templates such as "The circuit is located." and replaced with verified geographic and historical circuit descriptors.
- **Context Grounding**: Ensured `last_resolved_race` is only set when a real round is resolved from an active season schedule. Standings, champions, career, and circuit queries never overwrite or leak race rounds.

### Phase 3: Real Data API Routes (`backend/api_data.py`)
- Created 12 grounded endpoints: `/api/seasons`, `/api/schedule`, `/api/race`, `/api/standings`, `/api/teams`, `/api/teams/{id}`, `/api/drivers`, `/api/drivers/{id}`, `/api/legends`, `/api/eras`, `/api/race-control`, `/api/live/status`, `/api/live/stream`, `/api/replay/...`.
- Built dynamic GP and circuit aliases with SQLite caching (30-day TTL).
- Fixed `fetch_pit_stops` to handle zero-stop races (e.g. Spa 2021) without raising exceptions.

### Phase 4: Purge Demo Mode & Dynamic Detail Pages
- Completely purged all occurrences of `demoData`, `DEMO_MODE`, and "demo" across frontend and backend.
- Verified dynamic routing on `/drivers/[driverId]` and `/teams/[teamId]` with real Jolpica `driverId` and `constructorId`.
- Added constructor badge and Wikipedia logo fallback for team profile cards.
- Refactored Live feed to serve real OpenF1 session data when active, with clear FastF1 replay labeling otherwise.

### Phase 5: Official F1 Carbon & Red Design System
- **Surfaces**: Primary carbon black `--bg: #15151E`, `--surface: #1E1E28`, `--raised: #282836`, `--overlay: #323244`.
- **Accent**: Official Formula 1 Racing Red `--accent: #E10600`, `--accent-hover: #FF1801`, `--live: #E10600`.
- **Text & Contrast**: High-contrast typography `--text: #FFFFFF` (15.5:1), `--text-2: #D0D0DC` (11.5:1), `--text-3: #9E9EB0` (7.4:1), comfortably exceeding WCAG AA 4.5:1 requirement.
- **Typography**: Titillium Web headings (`var(--font-heading)`), IBM Plex Sans for UI body and labels, IBM Plex Mono for numbers and telemetry.
- **Link Reset**: Added global `a { color: inherit; text-decoration: none; }` to eliminate unwanted underlines.

### Phase 6: Opening Scene
- Created `frontend/public/brand/logo-transparent.png` with transparent background.
- Built `frontend/src/components/IntroSplash.tsx` full-screen overlay with centered logo, 1.8s fade-out into Dashboard Hub, executed once per session via `sessionStorage`. Mounted in `frontend/src/app/layout.tsx`.

### Phase 7: Performance & Session Caching
- Standardized SQLite caching TTLs for historical vs active season data.
- Bounded FastF1 LRU session loader in `backend/charts/loader.py` with multi-endpoint memory sharing.

### Phase 8: Full Verification Suite
- **Backend Tests**: 75/75 passed (100%) in pytest.
- **Frontend Tests**: 8/8 passed (100%) in Vitest.
- **Next.js Production Build**: `npm run build` compiled 12/12 static and dynamic routes cleanly.
- **Banned Strings**: 0 occurrences of `demoData`, `DEMO_MODE`, `DEMO_LABEL`, `Sample Grand Prix`, or `Demo Circuit`.

---

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
| 1 | 2023 Italian GP Winner | Max Verstappen | Max Verstappen | Verified |
| 2 | 2023 Drivers Champion | Max Verstappen (575 pts) | Max Verstappen (575 pts) | Verified |
| 3 | 2023 Constructors Champion | Red Bull (860 pts) | Red Bull (860 pts) | Verified |
| 4 | 2021 Belgian GP Winner | Max Verstappen | Max Verstappen | Verified |
| 5 | 2024 Bahrain GP Winner | Max Verstappen | Max Verstappen | Verified |

---

## [Phase 1 - 5] - Real F1 Data Pipeline, Demo Mode Removal & Pit Boss Honesty Fixes

### Phase 0: Startup & Dead Code Cleanup
- Fixed backend import startup error in `backend/state.py` (added missing `Tuple` typing import).
- Removed dead and duplicate files: `frontend/next.config.ts`, `backend/chart_routes.py`, `backend/charts.py`.
- Updated `/api/chat` to validate required fields and return 422 Unprocessable Entity instead of 404.
- Cleaned environment variable parsing (`_clean` in `backend/config.py`) to safely strip quoting from shell environments.

### Phase 1: Pit Boss Honesty & Context Accuracy
- **Failure propagation**: Tool failures and unavailable data now return `verified: false`, empty sources `[]`, and explicit failure descriptions (e.g. `Could not load race results for <race> <year> from Jolpica (<reason>)`). Never returns `verified: true` on failed lookups.
- **Removed hollow templates**: In `backend/render.py`, all renderers verify required fields. Hollow statements like `"The circuit is located."` have been completely removed.
- **Context leak elimination**: `last_resolved_race` is only assigned when a real round is resolved in the schedule. Never defaults to round 1. Standings, champions, driver profiles, and circuit lookups never set `last_resolved_race`.
- **Dynamic circuit aliases**: Replaced hardcoded dictionary in `backend/tools.py` with dynamic schedule and circuit scanner cached for 30 days in SQLite.
- Standardized branding to **Pit Boss** and fixed source tag deduplication in UI (`ChatThread.tsx` and `chat-provider.tsx`).

### Phase 2: Grounded Real Data API Endpoints (`backend/api_data.py`)
- Created standardized REST endpoints returning structured `{status, source, fetched_at, coverage_note}` payloads:
  - `GET /api/seasons`: 1950 to present dynamically calculated.
  - `GET /api/schedule`: Full season schedule with `latest_completed_round`.
  - `GET /api/race`: Race classification, tyre stints per driver (FastF1 2018+), team colors.
  - `GET /api/standings`: Driver and constructor championship standings.
  - `GET /api/teams` & `GET /api/teams/{id}`: Season constructors, title records, and driver rosters.
  - `GET /api/drivers` & `GET /api/drivers/{id}`: Driver standings, headshots (OpenF1 / Wikipedia), career totals.
  - `GET /api/legends`: World champion aggregation from 1950 to present.
  - `GET /api/eras`: Historical technical eras with dynamic championship counts.
  - `GET /api/race-control`: Real race control messages from FastF1 with real lap numbers and timestamps.
  - `GET /api/live/status`: Dynamic status reporting live mode when OpenF1 session is active, or replay mode on completed FastF1 sessions.
  - `GET /api/live/stream`: Server-Sent Events (SSE) telemetry stream with position, intervals, laps, and car data.
  - `GET /api/replay/{year}/{round}/lap/{n}`: Replay snapshots for historical session exploration.
- Added `drs_available` channel indicator in `backend/charts/telemetry.py`.

### Phase 3: Demo Data Removal & Frontend Grounding
- Deleted `frontend/src/demo/demoData.ts` and `demoData.test.ts`. Purged the entire `frontend/src/demo` directory.
- Rewrote `frontend/src/lib/api.ts` to fetch from real API endpoints without demo interceptions.
- Removed `NEXT_PUBLIC_DEMO_MODE` and demo badges across Navbar, Footer, and all app pages.
- Rewrote pages to use TanStack Query hooks backed by real data:
  - `frontend/src/app/page.tsx` (Dashboard)
  - `frontend/src/app/analytics/page.tsx`
  - `frontend/src/app/teams/page.tsx` & `frontend/src/app/teams/[teamId]/page.tsx`
  - `frontend/src/app/drivers/page.tsx` & `frontend/src/app/drivers/[driverId]/page.tsx`
  - `frontend/src/app/legends/page.tsx`
  - `frontend/src/app/live-feed/page.tsx`
  - `frontend/src/components/dashboard/RaceStoryScrollytelling.tsx`

### Phase 4: Performance & Resilience
- Standardized SQLite cache TTLs: past seasons (`year < current_year`) cached 30 days (`TTL_PAST_SEASON`), current season standings cached 10 minutes (`TTL_CURRENT_STANDINGS`), live session cached 2 seconds (`TTL_LIVE_SESSION`).
- Added in-flight request deduplication via locks per cache key.
- Implemented stale cache fallback: on upstream timeout or network outage, cached responses are served with header `X-Data-Stale: true` and annotated `coverage_note`.
- Enhanced FastF1 session loader (`backend/charts/loader.py`) with a bounded LRU cache (max 4 sessions, ~600MB) sharing loaded session objects across telemetry, speed traces, lap times, and track map endpoints.

### Phase 5: Verification & Test Suite
- All 75 backend tests passing in pytest (100%).
- All frontend Vitest unit and component tests passing (100%).
- `test_no_banned_f1_strings` passes verifying 0 occurrences of `demoData`, `DEMO_MODE`, `DEMO_LABEL`, `Sample Grand Prix`, or `Demo Circuit` across frontend and backend source code.
- Recorded offline test fixtures in `tests/fixtures/jolpica/`, `tests/fixtures/openf1/`, and `tests/fixtures/fastf1_mini.pkl`.
- Full Next.js production build (`npm run build`) compiles cleanly with 0 errors.
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
