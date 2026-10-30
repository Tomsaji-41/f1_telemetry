# Team Data Sources Specification (Phase J0)

This document records the empirical findings of live upstream API probes across Jolpica, OpenF1, Wikipedia REST, Wikidata, and Wikimedia Commons.

---

## 1. Upstream Source Matrix

| Field | Primary Source | Secondary Source | Format / Endpoint | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Logo** | Wikidata (`P154`) + Wikimedia Commons | Monogram Fallback | `commons.wikimedia.org/w/api.php` (`prop=imageinfo`) | **Never** use Wikipedia page lead photo (`pageimages`), as it frequently displays cars or personnel. |
| **Team Colour** | OpenF1 / Runtime Identity | Formula 1 Timing Stream | `/api/identity` & OpenF1 `/v1/drivers` | Lightened/contrast checked via WCAG 2.1 helper. |
| **Base / HQ** | Wikidata (`P159`) | Wikipedia REST | Entity JSON `claims.P159` -> Wikidata label | City, Country format. |
| **Inception / Founded** | Wikidata (`P571`) | Wikipedia pageprops | Entity JSON `claims.P571` -> year | Formatted as YYYY. |
| **Team Principal** | Wikidata (`P169` / `P1037`) | Wikipedia extract | Entity JSON `claims.P169` / `P1037` -> label | Current team principal / manager. |
| **Power Unit Supplier** | Wikidata / Jolpica results | OpenF1 team name | Entity JSON or Jolpica engine specs | Ferrari, Mercedes, Honda RBPT, Renault. |
| **First Entry Year** | Jolpica constructor history | Wikidata | `api.jolpi.ca/ergast/f1/constructors/{id}/seasons.json` | First recorded F1 season. |
| **Championship Titles** | Jolpica constructor standings | Historical records | `api.jolpi.ca/ergast/f1/constructorstandings/1.json` | Computed count and list of championship years. |
| **Total Wins / Podiums** | Jolpica constructor results | Jolpica standings | `api.jolpi.ca/ergast/f1/constructors/{id}/results.json` | Historical totals from 1950 to present. |
| **Rebrand Chain** | Wikidata (`P155`, `P1365`, `P156`, `P1366`) | Historical records | Entity JSON follows / replaces claims | Maps historical lineage (e.g. Sauber -> Alfa Romeo -> Stake/Kick -> Audi). |

---

## 2. API Probe Observations

1. **Jolpica Constructor Schema** (`/ergast/f1/constructors/{id}.json`):
   - Returns: `constructorId`, `url` (Wikipedia page), `name`, `nationality`.
   - Does **not** contain logos, headquarters, team principals, or colours.
   - Provides canonical entry point to Wikipedia and historical championship tables.

2. **OpenF1** (`/v1/`):
   - Does not have a standalone `/teams` endpoint.
   - Constructor names and colours are retrieved through `/v1/drivers` (`team_name`, `team_colour`).

3. **Wikipedia REST API** (`/api/rest_v1/page/summary/{title}`):
   - Returns `wikibase_item` (Wikidata QID), `extract`, and article `thumbnail`.
   - `thumbnail` is the lead article image (often a vehicle or team garage), which is **not** suitable as a logo.

4. **Wikidata Entity Claims** (`/wiki/Special:EntityData/{QID}.json`):
   - Property `P154` explicitly designates the official "logo image" filename on Wikimedia Commons.
   - Property `P159` designates "headquarters location".
   - Property `P571` designates "inception".
   - Properties `P155` ("follows") and `P1365` ("replaces") establish the rebrand chain.

5. **Wikimedia Commons Imageinfo** (`action=query&titles=File:{filename}&prop=imageinfo&iiprop=url|size|extmetadata`):
   - Provides high-resolution thumbnail generation (`iiurlwidth=400`).
   - Returns licensing and attribution metadata (`LicenseShortName`, `Artist`, `Credit`, `UsageTerms`).
   - Served via backend proxy (`GET /api/logos/{constructorId}.png?year=`) to respect Wikipedia usage policies and prevent external hotlinking.
