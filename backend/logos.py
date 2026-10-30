"""
backend/logos.py — Runtime Team Logo Resolution & Backend Image Proxy (Phase J1)

Resolves official team logos at runtime through:
0. Local User Override: LOGO_OVERRIDE_DIR (assets/logos/<constructorId>.svg|png)
1. Jolpica constructor metadata -> Wikipedia URL
2. Wikipedia API: redirects=1, pageprops -> wikibase_item (Wikidata QID), handles disambiguation & P921 main subject
3. Wikidata entity: property "logo image" (P154) claims with qualifiers (P580 start, P582 end, preferred rank)
4. Lineage traversal: follows (P155) / replaces (P1365) for rebrands
5. Wikimedia Commons: imageinfo API for PNG thumbnail (iiurlwidth=400), licence, and attribution
6. Image proxy caching with short TTL for null results and startup null-cache purging.
"""
import os
import re
import json
import logging
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

try:
    from backend import cache, config, http_pool
    from backend.sources import jolpica
except ImportError:
    import cache
    import config
    import http_pool
    from sources import jolpica

logger = logging.getLogger("logos")

USER_AGENT = "AI-Pitboss-F1-Telemetry/1.0 (https://github.com/f1_telemetry; telemetry@pitboss.local)"
LOGOS_DIR = Path(config.DATA_DIR if hasattr(config, "DATA_DIR") else "data") / "logos"
LOGOS_DIR.mkdir(parents=True, exist_ok=True)

# User-supplied override directory (assets/logos/<constructorId>.svg|png)
OVERRIDE_DIR_ENV = os.environ.get("LOGO_OVERRIDE_DIR", "assets/logos")
OVERRIDE_DIR = Path(OVERRIDE_DIR_ENV)
OVERRIDE_DIR.mkdir(parents=True, exist_ok=True)


def _check_local_override(constructor_id: str) -> Optional[Tuple[Path, str]]:
    """Checks if a user-supplied logo override exists for constructor_id."""
    cid_clean = constructor_id.lower().strip()
    for ext in (".svg", ".png", ".jpg", ".jpeg", ".webp"):
        p = OVERRIDE_DIR / f"{cid_clean}{ext}"
        if p.exists() and p.stat().st_size > 0:
            mime = "image/svg+xml" if ext == ".svg" else ("image/png" if ext == ".png" else "image/jpeg")
            return p, mime
    return None


def _http_get_json(url: str, ttl: float = cache.TTL_PAST_SEASON) -> Optional[Dict[str, Any]]:
    """Cached HTTP GET returning JSON via pooled client."""
    cache_key = f"logo_http:{url}"
    cached = cache.get_json(cache_key)
    if cached is not None:
        return cached

    data = http_pool.fetch_json_pooled(url)
    if data is not None:
        cache.set_json(f"logo_http:{url}", data, ttl)
    return data


def _resolve_constructor_entity_from_qid(qid: str) -> Optional[str]:
    """
    If QID represents a general manufacturer presence (Q21484471),
    traverse P921 (main subject) or P1889 (different from) to find the actual F1 team entity.
    """
    url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
    data = _http_get_json(url)
    if not data:
        return None

    entity = data.get("entities", {}).get(qid, {})
    claims = entity.get("claims", {})

    # Check if entity already has P154
    if claims.get("P154"):
        return qid

    # Check P921 (main subject)
    p921_claims = claims.get("P921", [])
    for c in p921_claims:
        target_id = c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
        if target_id:
            # Check if target entity has P154
            sub_url = f"https://www.wikidata.org/wiki/Special:EntityData/{target_id}.json"
            sub_data = _http_get_json(sub_url)
            if sub_data:
                sub_claims = sub_data.get("entities", {}).get(target_id, {}).get("claims", {})
                if sub_claims.get("P154"):
                    return target_id

    return None


def _search_wikidata_f1_team(name: str) -> Optional[str]:
    """
    Search Wikidata search API for Formula One constructor/team,
    picking by exact label or alias match, not fuzzy ranking.
    """
    enc_name = urllib.parse.quote(name)
    url = f"https://www.wikidata.org/w/api.php?action=wbsearchentities&search={enc_name}&language=en&format=json&limit=10"
    data = _http_get_json(url)
    if not data:
        return None

    name_clean = name.lower().strip()
    for item in data.get("search", []):
        qid = item.get("id")
        label = item.get("label", "").lower().strip()
        aliases = [a.lower().strip() for a in item.get("aliases", [])]

        if label == name_clean or name_clean in aliases:
            # Verify it has P154 or is an F1 team
            sub_url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
            sub_data = _http_get_json(sub_url)
            if sub_data:
                sub_claims = sub_data.get("entities", {}).get(qid, {}).get("claims", {})
                if sub_claims.get("P154"):
                    return qid

    return None


def _get_wikidata_qid_from_wikipedia(title: str, team_name: str = "") -> Optional[str]:
    """
    Retrieve wikibase_item (QID) from Wikipedia page title with redirects=1,
    pageprops, disambiguation detection, and P921 main subject resolution.
    """
    clean_title = urllib.parse.quote(title.replace(" ", "_"))
    url = f"https://en.wikipedia.org/w/api.php?action=query&titles={clean_title}&redirects=1&prop=pageprops&format=json"
    data = _http_get_json(url)
    if data:
        pages = data.get("query", {}).get("pages", {})
        for _, page_obj in pages.items():
            if page_obj.get("pageid") and "missing" not in page_obj:
                pageprops = page_obj.get("pageprops", {})
                is_disambig = "disambiguation" in pageprops
                qid = pageprops.get("wikibase_item")
                if qid and not is_disambig:
                    # Check if entity links to team entity via P921
                    resolved_qid = _resolve_constructor_entity_from_qid(qid)
                    return resolved_qid or qid

    # Fallback: search Wikidata for exact constructor name
    if team_name:
        search_qid = _search_wikidata_f1_team(team_name)
        if search_qid:
            return search_qid

    return None


def _extract_p154_filename(qid: str, depth: int = 0) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Extracts P154 (logo image) filename from Wikidata entity.
    Ranking:
    1. Preferred rank claims
    2. Claims without end-time qualifier (P582)
    3. Claims with latest start-time qualifier (P580)
    4. Traverses lineage rebrands (P155/P1365) up to depth 2.
    Returns (filename, resolved_qid, rebrand_note).
    """
    if depth > 2 or not qid:
        return None, None, None

    url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
    data = _http_get_json(url)
    if not data:
        return None, None, None

    entity = data.get("entities", {}).get(qid, {})
    claims = entity.get("claims", {})

    # 1. Direct P154 claims
    p154_claims = claims.get("P154", [])
    if p154_claims:
        candidates = []
        for claim in p154_claims:
            val = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
            if not val or not isinstance(val, str):
                continue
            rank = claim.get("rank", "normal")
            if rank == "deprecated":
                continue
            qualifiers = claim.get("qualifiers", {})
            start_q = qualifiers.get("P580", [{}])[0].get("datavalue", {}).get("value", {}).get("time", "")
            end_q = qualifiers.get("P582", [{}])[0].get("datavalue", {}).get("value", {}).get("time", "")
            has_no_end = not bool(end_q)
            rank_score = 2 if rank == "preferred" else 1

            candidates.append({
                "file": val,
                "rank_score": rank_score,
                "has_no_end": 1 if has_no_end else 0,
                "start": start_q or "",
            })

        if candidates:
            # Sort by rank, then no end date, then latest start date
            candidates.sort(key=lambda c: (c["rank_score"], c["has_no_end"], c["start"]), reverse=True)
            return candidates[0]["file"], qid, None

    # 2. Rebrands / predecessors: follow P155 (follows) or P1365 (replaces) only when same lineage
    for prop in ("P155", "P1365"):
        rel_claims = claims.get(prop, [])
        for rel in rel_claims:
            target_id = rel.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
            if target_id and target_id != qid:
                sub_file, sub_qid, _ = _extract_p154_filename(target_id, depth=depth + 1)
                if sub_file:
                    return sub_file, sub_qid, f"Derived from lineage entity {target_id}"

    return None, qid, None


def purge_null_logo_cache() -> int:
    """Purges cached null or error logo responses from SQLite on startup."""
    try:
        from backend.cache import _get_db
        with _get_db() as conn:
            cursor = conn.execute("SELECT key, value FROM cache WHERE key LIKE 'v2:team_logo_v2:%'")
            to_delete = []
            for row in cursor.fetchall():
                key, val = row[0], row[1]
                try:
                    parsed = json.loads(val)
                    if parsed.get("logoUrl") is None or parsed.get("status") == "error":
                        to_delete.append(key)
                except Exception:
                    pass
            for k in to_delete:
                conn.execute("DELETE FROM cache WHERE key = ?", (k,))
            conn.commit()
            if to_delete:
                logger.info(f"Purged {len(to_delete)} null/failed logo entries from cache.")
            return len(to_delete)
    except Exception as e:
        logger.warning(f"Error purging null logo cache: {e}")
        return 0


def resolve_team_logo(constructor_id: str, year: Optional[int] = None) -> Dict[str, Any]:
    """
    Executes the logo resolution chain with local override priority (J1/P1).
    """
    # 0. Check User-Supplied Override Directory first
    override = _check_local_override(constructor_id)
    if override:
        path, mime = override
        proxy_path = f"/api/logos/{constructor_id}.png"
        if year:
            proxy_path += f"?year={year}"
        return {
            "url": proxy_path,
            "logoUrl": proxy_path,
            "logoSource": "local_override",
            "source": "local_override",
            "logoLicense": "User-supplied / Trademarked",
            "license": "User-supplied / Trademarked",
            "logoAttribution": "Local override asset",
            "attribution": "Local override asset",
            "logoReason": None,
            "reason": None,
            "rawThumbnailUrl": None,
            "filePageUrl": None,
            "coverage_note": f"User override from {OVERRIDE_DIR_ENV}",
        }

    cache_key = cache.build_cache_key("team_logo_v2", constructor_id, year=year)
    cached = cache.get_json(cache_key)
    if cached is not None:
        return cached

    # Step 1: Jolpica constructor metadata
    j_url = f"https://api.jolpi.ca/ergast/f1/constructors/{constructor_id}.json"
    j_data = _http_get_json(j_url)
    wiki_url = None
    team_name = constructor_id.replace("_", " ").title()

    if j_data:
        ctors = j_data.get("MRData", {}).get("ConstructorTable", {}).get("Constructors", [])
        if ctors:
            wiki_url = ctors[0].get("url")
            team_name = ctors[0].get("name", team_name)

    if not wiki_url or "/wiki/" not in wiki_url:
        res = {
            "logoUrl": None,
            "logoSource": None,
            "logoLicense": None,
            "logoAttribution": None,
            "logoReason": f"No Wikipedia URL found in Jolpica constructor records for '{constructor_id}'",
            "filePageUrl": None,
            "rawThumbnailUrl": None,
        }
        # Short TTL for failures (never cache long)
        cache.set_json(cache_key, res, 60)
        return res

    title = wiki_url.split("/wiki/")[-1].strip()

    # Step 2: Wikipedia -> Wikidata QID (following redirects and P921)
    qid = _get_wikidata_qid_from_wikipedia(title, team_name=team_name)
    if not qid:
        res = {
            "logoUrl": None,
            "logoSource": None,
            "logoLicense": None,
            "logoAttribution": None,
            "logoReason": f"No Wikidata QID associated with Wikipedia page '{title}'",
            "filePageUrl": None,
            "rawThumbnailUrl": None,
        }
        cache.set_json(cache_key, res, 60)
        return res

    # Step 3: Extract P154 logo filename with qualifiers
    filename, resolved_qid, lineage_note = _extract_p154_filename(qid)
    if not filename:
        res = {
            "url": None,
            "logoUrl": None,
            "logoSource": None,
            "logoLicense": None,
            "logoAttribution": None,
            "logoReason": f"No property P154 (logo image) found on Wikidata entity {qid} (or its historical lineage)",
            "reason": f"No property P154 (logo image) found on Wikidata entity {qid}",
            "filePageUrl": None,
            "rawThumbnailUrl": None,
        }
        cache.set_json(cache_key, res, 60)
        return res

    # Step 4: Wikimedia Commons imageinfo API for PNG rasterized thumbnail
    enc_file = urllib.parse.quote(filename.replace(" ", "_"))
    c_url = f"https://commons.wikimedia.org/w/api.php?action=query&titles=File:{enc_file}&prop=imageinfo&iiprop=url|size|extmetadata|user&iiurlwidth=400&format=json"
    c_data = _http_get_json(c_url)

    thumb_url = None
    file_page = None
    license_name = "Public Domain / Fair Use"
    attribution = "Wikimedia Commons contributors"

    if c_data:
        pages = c_data.get("query", {}).get("pages", {})
        for _, page in pages.items():
            img_info = page.get("imageinfo", [])
            if img_info:
                info = img_info[0]
                thumb_url = info.get("thumburl") or info.get("url")
                file_page = info.get("descriptionurl")
                meta = info.get("extmetadata", {})
                license_name = meta.get("LicenseShortName", {}).get("value") or meta.get("UsageTerms", {}).get("value") or license_name
                artist = meta.get("Artist", {}).get("value") or meta.get("Credit", {}).get("value")
                if artist:
                    clean_artist = re.sub(r"<[^>]+>", "", artist).strip()
                    if clean_artist:
                        attribution = clean_artist
                break

    if not thumb_url:
        res = {
            "logoUrl": None,
            "logoSource": None,
            "logoLicense": None,
            "logoAttribution": None,
            "logoReason": f"Could not retrieve thumbnail URL from Wikimedia Commons for '{filename}'",
            "filePageUrl": file_page,
            "rawThumbnailUrl": None,
        }
        cache.set_json(cache_key, res, 60)
        return res

    # Step 5: Success
    proxy_path = f"/api/logos/{constructor_id}.png"
    if year:
        proxy_path += f"?year={year}"

    res = {
        "url": proxy_path,
        "logoUrl": proxy_path,
        "logoSource": "wikidata/commons",
        "source": "wikidata/commons",
        "logoLicense": license_name,
        "license": license_name,
        "logoAttribution": attribution,
        "attribution": attribution,
        "logoReason": None,
        "reason": None,
        "rawThumbnailUrl": thumb_url,
        "filePageUrl": file_page,
        "coverage_note": lineage_note or "Current official logo",
    }
    cache.set_json(cache_key, res, cache.TTL_PAST_SEASON)
    return res


def get_logo_image_bytes(constructor_id: str, year: Optional[int] = None) -> Optional[Tuple[bytes, str]]:
    """
    Retrieves and caches the image bytes (and mime-type) for a constructor logo.
    Returns (bytes, mime_type) or None.
    """
    # 0. Check User-Supplied Override first
    override = _check_local_override(constructor_id)
    if override:
        path, mime = override
        with open(path, "rb") as f:
            return f.read(), mime

    file_path = LOGOS_DIR / f"{constructor_id}.png"
    if file_path.exists() and file_path.stat().st_size > 0:
        with open(file_path, "rb") as f:
            return f.read(), "image/png"

    meta = resolve_team_logo(constructor_id, year)
    thumb_url = meta.get("rawThumbnailUrl")
    if not thumb_url:
        return None

    try:
        req = urllib.request.Request(
            thumb_url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "image/png,image/svg+xml,image/*,*/*"
            }
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = resp.read()
            if data:
                with open(file_path, "wb") as f:
                    f.write(data)
                return data, "image/png"
    except Exception as exc:
        logger.warning("Failed to download logo bytes from %s: %s", thumb_url, exc)

    return None
