# Circuit Data Sources Specification (Phase K0)

This document records the empirical findings of live upstream API probes across Jolpica Circuits, FastF1, Wikipedia REST, Wikidata, OpenStreetMap Overpass, and Open-Meteo.

---

## 1. Upstream Source Matrix

| Domain | Primary Source | Secondary Source | Format / Endpoint | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Circuit Identity** | Jolpica Circuits API | Wikidata | `api.jolpi.ca/ergast/f1/circuits.json` | 78 all-time circuits: `circuitId`, `circuitName`, `Location` (`lat`, `long`, `locality`, `country`), `url`. |
| **Track Geometry (3D/2D)** | FastF1 Position Stream (2018+) | OpenStreetMap Overpass | FastF1 `lap.get_telemetry()` & `mvapi.get_circuit_info()` | **Units**: FastF1 Live Timing coordinates are in **decimetres** ($0.1\text{ m}$). Must multiply $X, Y, Z$ by $0.1$ to convert to standard SI metres. |
| **Corners & Sectors** | FastF1 `CircuitInfo` | OSM Way Geometry | `fastf1.mvapi.get_circuit_info()` | Corner number, letter, angle, track distance, and circuit rotation. |
| **Elevation / Altitude** | Open-Meteo Elevation API | Wikidata (`P2044`) | `api.open-meteo.com/v1/elevation` | Elevation above sea level in metres; relative $Z$ smoothed and zero-referenced to start/finish line. |
| **Climate & Weather** | Open-Meteo Historical Archive | FastF1 Weather Data | `archive-api.open-meteo.com/v1/archive` | Historical race-day temperature, rainfall, and wind speed. |
| **Layout History & Facts** | Wikipedia REST API & Wikidata | Jolpica Race Results | `en.wikipedia.org/api/rest_v1/page/summary/` | Length, opened year, capacity, first GP, and total GPs held. |

---

## 2. FastF1 Geometry & Unit Conversion

- **Position Channel ($X, Y, Z$)**:
  - Live timing coordinates output by Formula 1 timing transponders use decimetres ($1\text{ unit} = 0.1\text{ m}$).
  - E.g., coordinate range for a $5.89\text{ km}$ circuit spans $\sim 10,000$ units ($\sim 1,000\text{ m}$ physical bounding footprint).
  - Conversion formula: $x_{\text{metres}} = X \times 0.1$, $y_{\text{metres}} = Y \times 0.1$, $z_{\text{metres}} = Z \times 0.1$.
- **Circuit Direction**:
  - Determined by computing the signed area (shoelace formula) over the closed 2D $(x, y)$ loop:
    $$\text{Signed Area} = \frac{1}{2} \sum_{i=0}^{n-1} (x_i y_{i+1} - x_{i+1} y_i)$$
  - Positive signed area represents clockwise orientation (standard screen coordinates); negative represents anti-clockwise.
- **Honest Fallback Chain**:
  1. FastF1 fastest valid lap telemetry (2018+).
  2. OpenStreetMap Overpass raceway way/relation near circuit coordinates.
  3. If both lack valid track geometry: `geometry = null` with explicit reason; **never** synthesize or hand-craft a fake track loop.

---

## 3. Licenses, Attribution & Rate Limits

- **OpenStreetMap / Overpass**: ODbL (Open Database License). Requires attribution: *"© OpenStreetMap contributors"*. Concurrency capped with fallback mirrors.
- **Open-Meteo**: Free non-commercial and commercial use with attribution. No API key required; rate-limited to $<10,000$ daily requests.
- **Wikipedia / Wikimedia**: CC BY-SA 4.0. Text summary and images require explicit licence attribution.
